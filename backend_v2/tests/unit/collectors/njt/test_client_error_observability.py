"""Error-path observability for NJTransitClient._make_request (issue #1725).

Production logged entries reading only ``njt_api_request_failed | error=`` and
raised messages ending in a bare colon (``Failed to call
TrainData/getTrainStopList:``), because ``str(e)`` is empty for an exception
constructed with no args — which is exactly what httpx's timeout types are
when raised without a message. The empty string then propagated to every
downstream handler that logs ``error=str(e)``.

Separately, NJT answers some failures with a Cloudflare-style HTML page, and
the whole body was interpolated into the raised message. The nightly stop-list
sweep re-raises that message once per train, so a single upstream fault could
put hundreds of copies of a full HTML document into the logs.

``_make_request`` had no test coverage at all before this file: neither the
HTTP-status branch nor the generic branch was exercised.
"""

import httpx
import pytest
import structlog
from structlog.testing import LogCapture
from unittest.mock import AsyncMock, Mock

from trackrat.collectors.njt.client import (
    NJT_ERROR_BODY_MAX_CHARS,
    NJTransitAPIError,
    NJTransitClient,
)


@pytest.fixture
def log_output():
    """Capture structlog entries, restoring the global config afterwards.

    structlog.configure is process-global; leaking a LogCapture into later
    tests would silently swallow their output.
    """
    captured = LogCapture()
    original = structlog.get_config()
    structlog.configure(processors=[captured])
    yield captured
    structlog.configure(**original)


async def _stubbed_client() -> NJTransitClient:
    """Build a client whose transport is a stub, with no live connections.

    ``NJTransitClient.__init__`` eagerly opens a pooled ``httpx.AsyncClient``;
    replacing ``_client`` without closing that one leaks a connection pool per
    constructed client.
    """
    client = NJTransitClient()
    await client.close()
    client._client = AsyncMock()
    return client


async def _client_with_transport_error(exc: Exception) -> NJTransitClient:
    """Build a client whose POST raises ``exc``, bypassing the network."""
    client = await _stubbed_client()
    client._client.post = AsyncMock(side_effect=exc)
    return client


def _response_raising_for_status(status_code: int, body: str, message: str) -> Mock:
    """Build a response mock whose raise_for_status raises HTTPStatusError."""
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.text = body
    response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            message,
            request=httpx.Request("POST", "https://example.test/api/endpoint"),
            response=response,
        )
    )
    return response


async def _client_with_http_status_error(
    status_code: int, body: str, message: str | None = None
) -> NJTransitClient:
    """Build a client whose POST returns a response that raises for status."""
    client = await _stubbed_client()
    response = _response_raising_for_status(
        status_code,
        body,
        f"Server error '{status_code}'" if message is None else message,
    )
    client._client.post = AsyncMock(return_value=response)
    return client


def _entry(log_output, event):
    matches = [e for e in log_output.entries if e.get("event") == event]
    assert matches, (
        f"expected a {event!r} log entry, got: "
        f"{[e.get('event') for e in log_output.entries]}"
    )
    return matches[0]


class TestArglessExceptionsAreNotLoggedEmpty:
    """The regression: str(e) == '' must never reach the log or the message."""

    @pytest.mark.asyncio
    async def test_argless_read_timeout_logs_a_non_empty_error(self, log_output):
        """httpx.ReadTimeout('') is the exact exception from the issue report."""
        exc = httpx.ReadTimeout("")
        assert str(exc) == "", "precondition: this exception stringifies empty"

        client = await _client_with_transport_error(exc)
        with pytest.raises(NJTransitAPIError):
            await client._make_request("TrainData/getTrainStopList", {})

        entry = _entry(log_output, "njt_api_request_failed")
        assert entry["error"], (
            "error field must never be empty — an entry saying only that "
            f"something failed is the bug: {entry!r}"
        )
        assert (
            "ReadTimeout" in entry["error"]
        ), f"fallback must name the exception class, got: {entry['error']!r}"
        assert entry["error_type"] == "ReadTimeout"
        assert entry["endpoint"] == "TrainData/getTrainStopList"

    @pytest.mark.asyncio
    async def test_argless_read_timeout_raises_a_non_empty_message(self):
        """The wrapped message must not end at the colon.

        Downstream handlers log ``error=str(e)`` on this wrapper, so an empty
        cause here becomes an empty error field in every one of them.
        """
        client = await _client_with_transport_error(httpx.ReadTimeout(""))

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client._make_request("TrainData/getTrainStopList", {})

        message = str(exc_info.value)
        assert not message.rstrip().endswith(
            ":"
        ), f"message must not trail off after the colon: {message!r}"
        assert (
            "ReadTimeout" in message
        ), f"message must identify the underlying failure: {message!r}"
        assert "TrainData/getTrainStopList" in message

    @pytest.mark.asyncio
    async def test_exception_with_a_message_is_passed_through_unchanged(
        self, log_output
    ):
        """The fallback must not clobber a perfectly good message."""
        client = await _client_with_transport_error(
            httpx.ConnectError("connection refused")
        )

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client._make_request("TrainData/getTrainStopList", {})

        assert "connection refused" in str(exc_info.value)
        entry = _entry(log_output, "njt_api_request_failed")
        assert (
            entry["error"] == "connection refused"
        ), f"repr fallback should not fire when str(e) is useful: {entry!r}"
        assert entry["error_type"] == "ConnectError"

    @pytest.mark.asyncio
    async def test_original_exception_is_chained(self):
        """__cause__ must survive so tracebacks stay diagnosable."""
        original = httpx.ReadTimeout("")
        client = await _client_with_transport_error(original)

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client._make_request("TrainData/getTrainStopList", {})

        assert exc_info.value.__cause__ is original


class TestNonJsonErrorBodiesAreBounded:
    """NJT serves HTML error pages; they must not be logged or raised whole."""

    @pytest.mark.asyncio
    async def test_large_html_body_is_truncated_in_the_raised_message(self):
        html = "<html><body>" + ("x" * 20_000) + "</body></html>"
        client = await _client_with_http_status_error(409, html)

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client._make_request("TrainData/getTrainSchedule", {})

        message = str(exc_info.value)
        assert (
            len(message) < 1_000
        ), f"a 20KB body must not reach the message; got {len(message)} chars"
        assert (
            "truncated" in message
        ), f"truncation must be annotated, not silent: {message!r}"
        assert "409" in message, "status code must survive truncation"
        assert "<html>" in message, "the leading bytes are the diagnostic part"

    @pytest.mark.asyncio
    async def test_large_html_body_is_truncated_in_the_log_entry(self, log_output):
        html = "<html>" + ("y" * 20_000)
        client = await _client_with_http_status_error(409, html)

        with pytest.raises(NJTransitAPIError):
            await client._make_request("TrainData/getTrainSchedule", {})

        entry = _entry(log_output, "njt_api_http_error")
        assert len(entry["body_preview"]) < NJT_ERROR_BODY_MAX_CHARS + 100
        assert entry["status_code"] == 409
        assert entry["error_type"] == "HTTPStatusError"
        assert entry["error"], f"error field must not be empty: {entry!r}"

    @pytest.mark.asyncio
    async def test_short_body_is_preserved_verbatim(self):
        """Truncation must not damage a body that already fits."""
        body = '{"error": "invalid token"}'
        client = await _client_with_http_status_error(401, body)

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client._make_request("TrainData/getTrainStopList", {})

        message = str(exc_info.value)
        assert body in message, f"short body must survive intact: {message!r}"
        assert "truncated" not in message

    @pytest.mark.asyncio
    async def test_http_status_error_with_empty_str_still_logs_something(
        self, log_output
    ):
        """The empty-str guard applies to the status branch too."""
        # An HTTPStatusError constructed with an empty message.
        client = await _client_with_http_status_error(500, "boom", message="")

        with pytest.raises(NJTransitAPIError):
            await client._make_request("TrainData/getTrainStopList", {})

        entry = _entry(log_output, "njt_api_http_error")
        assert entry["error"], f"error field must not be empty: {entry!r}"
        assert "HTTPStatusError" in entry["error"]
