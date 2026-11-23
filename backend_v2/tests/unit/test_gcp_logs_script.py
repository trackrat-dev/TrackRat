"""Unit tests for ``.claude/scripts/gcp-logs.py`` entry formatting (issue #1984).

The daily production health check reads backend errors through this helper.
Exceptions such as ``httpx.ConnectTimeout`` stringify to ``""``, so a failure
logged as ``error=str(e)`` showed up in the report as a bare ``error=`` with no
hint of what went wrong, even though the backend also logs ``error_type``.
The helper has a hyphenated filename outside the package, so it is loaded by
file path via ``importlib``.
"""

import copy
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import requests
from structlog.testing import capture_logs

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.ridepath_client import RidePathClient

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / ".claude" / "scripts" / "gcp-logs.py"
)


@pytest.fixture(scope="module")
def gcp_logs():
    """Load .claude/scripts/gcp-logs.py as an importable module."""
    assert _SCRIPT_PATH.exists(), f"missing script: {_SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("gcp_logs", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _app_entry(**payload):
    """Wrap fields the way Cloud Logging delivers a cos_containers JSON line."""
    return {"timestamp": "2026-11-17T00:02:34.123Z", "jsonPayload": payload}


def test_format_app_entry_shows_error_type(gcp_logs):
    line = gcp_logs.format_app_entry(
        _app_entry(
            event="ridepath_api_failed",
            level="error",
            logger="trackrat.collectors.path.ridepath_client",
            error="",
            error_type="ConnectTimeout",
        )
    )
    print(f"formatted: {line}")
    assert line == (
        "[2026-11-17T00:02:34] ERROR [collectors.path.ridepath_client]: "
        "ridepath_api_failed | error= | error_type=ConnectTimeout"
    )


def test_format_app_entry_without_error_type_is_unchanged(gcp_logs):
    line = gcp_logs.format_app_entry(
        _app_entry(
            event="njt_api_request_failed",
            level="error",
            logger="trackrat.collectors.njt.client",
            error="boom",
        )
    )
    print(f"formatted: {line}")
    assert line == (
        "[2026-11-17T00:02:34] ERROR [collectors.njt.client]: "
        "njt_api_request_failed | error=boom"
    )
    assert "error_type" not in line


@pytest.mark.asyncio
async def test_path_connect_timeout_is_diagnosable_in_report(gcp_logs, db_session):
    """Contract test: a real PATH fetch failure reaches the report with its type.

    The RidePATH client and PathCollector run unmodified; only the network
    transport refuses to connect, as it did during the 2026-11-16 egress burst.
    Each captured event is formatted exactly as the health check prints it.
    """

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("", request=request)

    client = RidePathClient()
    client._session = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    collector = PathCollector(client=client)
    try:
        with capture_logs() as captured:
            result = await collector.collect(db_session)
    finally:
        await client.close()

    print(f"collect result: {result}")
    failures = {
        e["event"]: e
        for e in captured
        if e["event"] in ("ridepath_api_failed", "path_api_failed")
    }
    print(f"captured failure events: {failures}")
    assert set(failures) == {"ridepath_api_failed", "path_api_failed"}
    assert result["error"] == "", "ConnectTimeout('') stringifies to empty"

    for event, payload in failures.items():
        line = gcp_logs.format_app_entry(_app_entry(**payload))
        print(f"{event} -> {line}")
        assert "error_type=ConnectTimeout" in line, line


# --- Instance discovery (issue #1994) ---
#
# The Cloud Logging API is replaced by a page sequence recorded from its
# documented entries:list shape; the live API cannot be made to return an
# empty page with a continuation token on demand.

_NOW = datetime(2026, 11, 23, 8, 0, tzinfo=UTC)


def _host_entry(hostname, instance_id, timestamp="2026-11-23T07:59:00.123456Z"):
    return {
        "timestamp": timestamp,
        "resource": {"labels": {"instance_id": instance_id}},
        "jsonPayload": {"_HOSTNAME": hostname},
    }


class _Pages:
    """Serve entries:list responses in order and record each request body."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.bodies = []

    def post(self, url, json=None, headers=None):
        self.bodies.append(copy.deepcopy(json))
        page = self.pages.pop(0)
        return type("Resp", (), {"json": lambda self: page})()


@pytest.fixture
def pages(monkeypatch):
    def install(*responses):
        recorder = _Pages(responses)
        monkeypatch.setattr(requests, "post", recorder.post)
        return recorder

    return install


def test_discovery_follows_an_empty_page_with_a_continuation_token(gcp_logs, pages):
    """An empty first page is not "no instance" while a token says to continue."""
    recorder = pages(
        {"nextPageToken": "t1"},
        {"entries": [_host_entry("trackrat-production-b2jw", "650014")]},
    )
    result = gcp_logs.discover_instance_id("tok", "production", now=_NOW)
    print(f"result={result} requests={len(recorder.bodies)}")
    assert result == (
        "650014",
        "trackrat-production-b2jw",
        "2026-11-23T07:59:00.123456Z",
    )
    assert recorder.bodies[1]["pageToken"] == "t1"


def test_discovery_filter_is_time_bounded(gcp_logs, pages):
    recorder = pages({"entries": [_host_entry("trackrat-staging-6n6x", "419629")]})
    gcp_logs.discover_instance_id("tok", "staging", now=_NOW)
    log_filter = recorder.bodies[0]["filter"]
    print(f"filter={log_filter}")
    assert 'jsonPayload._HOSTNAME=~"^trackrat-staging-"' in log_filter
    assert 'timestamp>="2026-10-24T08:00:00Z"' in log_filter


def test_discovery_reports_absent_when_no_page_matches(gcp_logs, pages):
    recorder = pages({"nextPageToken": "t1"}, {})
    assert gcp_logs.discover_instance_id("tok", "staging", now=_NOW) == (
        None,
        None,
        None,
    )
    assert len(recorder.bodies) == 2


def test_discovery_page_budget_is_bounded(gcp_logs, pages):
    recorder = pages(*[{"nextPageToken": f"t{i}"} for i in range(50)])
    assert gcp_logs.discover_instance_id("tok", "staging", now=_NOW) == (
        None,
        None,
        None,
    )
    assert len(recorder.bodies) == gcp_logs.DISCOVERY_MAX_PAGES


def test_discovery_exits_on_api_error(gcp_logs, pages, capsys):
    pages({"error": {"message": "Permission denied"}})
    with pytest.raises(SystemExit):
        gcp_logs.discover_instance_id("tok", "staging", now=_NOW)
    assert "Permission denied" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("timestamp", "stale"),
    [
        ("2026-11-23T07:59:00.123456789Z", False),
        ("2026-11-23T07:00:00Z", False),
        ("2026-11-23T06:59:59.999Z", True),
        ("2026-10-17T00:00:00Z", True),
    ],
)
def test_is_stale(gcp_logs, timestamp, stale):
    assert gcp_logs.is_stale(timestamp, _NOW) is stale
