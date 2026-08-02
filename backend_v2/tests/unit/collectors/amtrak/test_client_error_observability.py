"""Error-path observability for AmtrakClient (issue #1725).

Production logged `amtrak_api_failed | error=` with nothing after it. The
handler logged a bare `str(e)` and neither `error_type` nor `exc_info`, so
when the exception was an argless `httpx.ReadTimeout` the entry carried no
diagnostic content whatsoever beyond the URL — it did not even name the class
that was raised. That is worse than the NJT equivalent, which at least logged
`error_type`.

The per-train parse handler had the same bare `str(e)`, and there it can go
the other way: a Pydantic ValidationError stringifies to a multi-line report
echoing the offending payload, once per malformed train.
"""

import httpx
import pytest
import structlog
from structlog.testing import LogCapture
from unittest.mock import AsyncMock, Mock

from trackrat.collectors.amtrak.client import (
    AMTRAK_PARSE_ERROR_MAX_CHARS,
    AmtrakClient,
)


@pytest.fixture
def client():
    return AmtrakClient(timeout=10.0)


@pytest.fixture
def log_output():
    """Capture structlog entries, restoring the global config afterwards.

    structlog.configure is process-global; the older tests in this package
    leave a LogCapture installed, which would swallow later output.
    """
    captured = LogCapture()
    original = structlog.get_config()
    structlog.configure(processors=[captured])
    yield captured
    structlog.configure(**original)


def _entry(log_output, event):
    matches = [e for e in log_output.entries if e.get("event") == event]
    assert matches, (
        f"expected a {event!r} entry, got: "
        f"{[e.get('event') for e in log_output.entries]}"
    )
    return matches[0]


class TestApiFailureIsAlwaysDescribed:
    @pytest.mark.asyncio
    async def test_argless_read_timeout_logs_a_non_empty_error(
        self, client, log_output
    ):
        """The exact production entry: `amtrak_api_failed | error=`."""
        exc = httpx.ReadTimeout("")
        assert str(exc) == "", "precondition: this exception stringifies empty"

        session = AsyncMock()
        session.get = AsyncMock(side_effect=exc)
        client._session = session

        with pytest.raises(httpx.ReadTimeout):
            await client.get_all_trains()

        entry = _entry(log_output, "amtrak_api_failed")
        assert entry["error"], (
            f"error field must never be empty — this entry previously said "
            f"only that something, somewhere, failed: {entry!r}"
        )
        assert "ReadTimeout" in entry["error"]
        assert (
            entry["error_type"] == "ReadTimeout"
        ), f"error_type was missing entirely on this path: {entry!r}"
        assert entry["url"], "the URL context must be kept"

    @pytest.mark.asyncio
    async def test_exception_with_a_message_is_not_replaced_by_its_repr(
        self, client, log_output
    ):
        session = AsyncMock()
        session.get = AsyncMock(side_effect=httpx.ConnectError("name resolution"))
        client._session = session

        with pytest.raises(httpx.ConnectError):
            await client.get_all_trains()

        entry = _entry(log_output, "amtrak_api_failed")
        assert entry["error"] == "name resolution"
        assert entry["error_type"] == "ConnectError"

    @pytest.mark.asyncio
    async def test_exception_is_reraised_unchanged(self, client):
        """The handler logs and re-raises; callers rely on the original type."""
        original = httpx.ReadTimeout("")
        session = AsyncMock()
        session.get = AsyncMock(side_effect=original)
        client._session = session

        with pytest.raises(httpx.ReadTimeout) as exc_info:
            await client.get_all_trains()

        assert exc_info.value is original


class TestParseFailuresAreBounded:
    @pytest.mark.asyncio
    async def test_validation_error_is_truncated_and_typed(self, client, log_output):
        """A malformed payload must not dump its whole validation report."""
        # A train dict whose fields are wrong enough to fail validation, with a
        # large value so the resulting report echoes something substantial.
        bad_train = {"trainNum": "99", "junk": "q" * 20_000, "lat": "not-a-number"}
        response = AsyncMock()
        response.json = Mock(return_value={"99": [bad_train]})
        response.raise_for_status = Mock(return_value=None)
        response.text = "{}"

        session = AsyncMock()
        session.get = AsyncMock(return_value=response)
        client._session = session

        await client.get_all_trains()

        entry = _entry(log_output, "failed_to_parse_train")
        assert (
            len(entry["error"]) <= AMTRAK_PARSE_ERROR_MAX_CHARS + 100
        ), f"parse error must be bounded, got {len(entry['error'])} chars"
        assert entry["error"], "error field must not be empty"
        assert entry[
            "error_type"
        ], f"error_type was missing on this path too: {entry!r}"
        assert entry["train_num"] == "99"
