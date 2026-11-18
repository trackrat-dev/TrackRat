"""Unit tests for ``.claude/scripts/gcp-logs.py`` entry formatting (issue #1984).

The daily production health check reads backend errors through this helper.
Exceptions such as ``httpx.ConnectTimeout`` stringify to ``""``, so a failure
logged as ``error=str(e)`` showed up in the report as a bare ``error=`` with no
hint of what went wrong, even though the backend also logs ``error_type``.
The helper has a hyphenated filename outside the package, so it is loaded by
file path via ``importlib``.
"""

import importlib.util
from pathlib import Path

import httpx
import pytest
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
