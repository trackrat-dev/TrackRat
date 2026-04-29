"""
Unit tests for AmtrakClient.

Tests HTTP client behavior with mocked responses, caching, and error handling.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timedelta

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.models.api import AmtrakTrainData
from tests.fixtures.amtrak_api_responses import (
    AMTRAK_FULL_RESPONSE,
    API_ERROR_RESPONSE,
    TRAIN_MISSING_OBJECT_ID,
    TRAIN_NULL_TIMESTAMPS,
)


class TestAmtrakClient:
    """Test suite for AmtrakClient."""

    @pytest.fixture
    def client(self):
        """Create an AmtrakClient instance for testing."""
        return AmtrakClient(timeout=10.0)

    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        mock_resp = AsyncMock()
        # Use Mock instead of AsyncMock for json() since it returns data, not a coroutine
        mock_resp.json = Mock(return_value=AMTRAK_FULL_RESPONSE)
        mock_resp.raise_for_status = Mock(return_value=None)
        mock_resp.text = str(AMTRAK_FULL_RESPONSE)
        return mock_resp

    async def test_successful_api_response(self, client, mock_response):
        """Test successful API response parsing."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        result = await client.get_all_trains()

        # Verify API was called - now uses dateless endpoint only
        assert mock_session.get.call_count == 1
        # Should call the dateless endpoint
        first_call_url = mock_session.get.call_args_list[0][0][0]
        assert first_call_url == "https://api-v3.amtraker.com/v3/trains"

        # Verify response structure
        assert isinstance(result, dict)
        assert "2150" in result
        assert "141" in result
        assert "280" in result
        assert "350" in result

        # Verify train data was parsed correctly
        acela_trains = result["2150"]
        assert len(acela_trains) == 1
        assert isinstance(acela_trains[0], AmtrakTrainData)
        assert acela_trains[0].trainID == "2150-5"
        assert acela_trains[0].routeName == "Acela"

    async def test_cache_behavior(self, client, mock_response):
        """Test that caching works correctly."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        # First call should hit API (may call multiple times due to fallback logic)
        result1 = await client.get_all_trains()
        initial_call_count = mock_session.get.call_count

        # Second call within TTL should use cache
        result2 = await client.get_all_trains()
        assert mock_session.get.call_count == initial_call_count  # No additional calls

        # Results should be identical
        assert result1 == result2

    async def test_cache_expiration(self, client, mock_response):
        """Test that cache expires after TTL."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        # First call
        await client.get_all_trains()
        initial_call_count = mock_session.get.call_count

        # Simulate cache expiration by setting old cache time
        client._cache_time = datetime.now() - timedelta(seconds=client._cache_ttl + 1)

        # Second call should hit API again
        await client.get_all_trains()
        # Should have made at least one more call (may be more due to fallback logic)
        assert mock_session.get.call_count > initial_call_count

    async def test_cache_clearing(self, client, mock_response):
        """Test manual cache clearing."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        # Populate cache
        await client.get_all_trains()
        assert client._cache
        assert client._cache_time

        # Clear cache
        client.clear_cache()
        assert not client._cache
        assert client._cache_time is None

    async def test_http_error_handling(self, client):
        """Test handling of HTTP errors."""
        mock_session = AsyncMock()
        mock_error_response = AsyncMock()
        mock_error_response.status_code = 500
        mock_error_response.text = "Internal Server Error"

        http_error = httpx.HTTPStatusError(
            "Server error", request=AsyncMock(), response=mock_error_response
        )
        mock_session.get.side_effect = http_error
        client._session = mock_session

        with pytest.raises(Exception):  # Should propagate the error
            await client.get_all_trains()

    async def test_timeout_handling(self, client):
        """Test handling of request timeouts."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = httpx.TimeoutException("Request timeout")
        client._session = mock_session

        with pytest.raises(httpx.TimeoutException):
            await client.get_all_trains()

    async def test_invalid_json_handling(self, client):
        """Test handling of invalid JSON responses."""
        mock_session = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.json = Mock(side_effect=ValueError("Invalid JSON"))
        mock_resp.raise_for_status = Mock(return_value=None)
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        with pytest.raises(Exception):
            await client.get_all_trains()

    async def test_data_validation_with_missing_fields(self, client):
        """Test parsing with missing optional fields."""
        # Create response with missing objectID
        response_with_missing_fields = {"63": [TRAIN_MISSING_OBJECT_ID]}

        mock_session = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.json = Mock(return_value=response_with_missing_fields)
        mock_resp.raise_for_status = Mock(return_value=None)
        mock_resp.text = str(response_with_missing_fields)
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        result = await client.get_all_trains()

        # Should parse successfully despite missing objectID
        assert "63" in result
        train = result["63"][0]
        assert train.trainID == "63-5"
        assert train.objectID is None  # Should be None for missing field

    async def test_null_timestamps_parsed_successfully(self, client):
        """Test that trains with null createdAt/updatedAt are parsed without error.

        Regression test for issue #1061: the Amtrak upstream API intermittently
        returns null for createdAt/updatedAt on long-distance and seasonal trains.
        Previously these were required str fields, causing Pydantic to reject the
        entire train record silently.
        """
        response_with_null_timestamps = {"50": [TRAIN_NULL_TIMESTAMPS]}

        mock_session = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.json = Mock(return_value=response_with_null_timestamps)
        mock_resp.raise_for_status = Mock(return_value=None)
        mock_resp.text = str(response_with_null_timestamps)
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        result = await client.get_all_trains()

        assert "50" in result, f"Train 50 should be parsed; got keys: {list(result.keys())}"
        train = result["50"][0]
        assert isinstance(train, AmtrakTrainData)
        assert train.trainID == "50-5"
        assert train.routeName == "Cardinal"
        assert train.createdAt is None
        assert train.updatedAt is None
        assert train.trainState == "Predeparture"

    async def test_null_timestamps_no_warning_logged(self, client):
        """Verify null-timestamp trains don't trigger failed_to_parse_train warnings."""
        from structlog.testing import LogCapture
        import structlog

        cap = LogCapture()
        structlog.configure(processors=[cap])

        response_with_null_timestamps = {"50": [TRAIN_NULL_TIMESTAMPS]}

        mock_session = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.json = Mock(return_value=response_with_null_timestamps)
        mock_resp.raise_for_status = Mock(return_value=None)
        mock_resp.text = str(response_with_null_timestamps)
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        await client.get_all_trains()

        parse_failures = [
            e for e in cap.entries if e.get("event") == "failed_to_parse_train"
        ]
        assert len(parse_failures) == 0, (
            f"Null-timestamp trains should not emit failed_to_parse_train; "
            f"got: {parse_failures}"
        )

    async def test_get_train_by_id_from_cache(self, client, mock_response):
        """Test retrieving specific train by ID from cache."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        # Populate cache
        await client.get_all_trains()

        # Test successful lookup
        train = client.get_train_by_id("2150-5")
        assert train is not None
        assert train.trainID == "2150-5"
        assert train.routeName == "Acela"

        # Test non-existent train
        missing_train = client.get_train_by_id("9999-5")
        assert missing_train is None

    async def test_get_train_by_id_without_cache(self, client):
        """Test retrieving train by ID when cache is empty."""
        # Empty cache
        client.clear_cache()

        train = client.get_train_by_id("2150-5")
        assert train is None

    async def test_context_manager(self, client):
        """Test async context manager behavior."""
        async with client:
            # Should be able to use client
            assert client._session is None  # Session created lazily

        # Session should be closed after context
        # Note: close() will be called but session may still be None if never used

    async def test_base_client_interface(self, client, mock_response):
        """Test that client satisfies BaseClient interface."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        # get_train_data should work the same as get_all_trains
        result = await client.get_train_data()

        assert isinstance(result, dict)
        assert "2150" in result

    async def test_session_lazy_creation(self, client):
        """Test that HTTP session is created lazily."""
        # Session should be None initially
        assert client._session is None

        # Accessing session property should create it
        session = client.session
        assert session is not None
        assert isinstance(session, httpx.AsyncClient)

        # Should return same session on subsequent calls
        assert client.session is session

    async def test_session_headers(self, client):
        """Test that session has correct headers."""
        session = client.session

        assert session.headers["User-Agent"] == "TrackRat-V2/1.0"
        assert session.headers["Accept"] == "application/json"

    async def test_logging_on_success(self, client, mock_response, caplog):
        """Test that successful requests are logged."""
        from structlog.testing import LogCapture
        import structlog

        # Use structlog's testing capability
        cap = LogCapture()
        structlog.configure(processors=[cap])

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        await client.get_all_trains()

        # Should log fetching and success messages
        assert len(cap.entries) > 0, "Expected log entries"
        fetching_entry = next(
            (
                entry
                for entry in cap.entries
                if entry.get("event") == "fetching_amtrak_trains"
            ),
            None,
        )
        assert (
            fetching_entry is not None
        ), f"Expected 'fetching_amtrak_trains' event in {cap.entries}"

        # Also check for success message
        success_entries = [
            entry
            for entry in cap.entries
            if entry.get("event") == "amtrak_data_fetched"
        ]
        assert (
            len(success_entries) > 0
        ), f"Expected 'amtrak_data_fetched' event in {cap.entries}"

    async def test_logging_on_error(self, client, caplog):
        """Test that errors are logged."""
        from structlog.testing import LogCapture
        import structlog

        # Use structlog's testing capability
        cap = LogCapture()
        structlog.configure(processors=[cap])

        mock_session = AsyncMock()
        mock_session.get.side_effect = httpx.TimeoutException("Timeout")
        client._session = mock_session

        with pytest.raises(httpx.TimeoutException):
            await client.get_all_trains()

        # Should log error - now uses different event names due to fallback logic
        assert len(cap.entries) > 0, "Expected log entries"
        # Check for any error-related event (dated_api_failed or amtrak_api_fallback_failed)
        error_entries = [
            entry
            for entry in cap.entries
            if "error" in entry or "failed" in entry.get("event", "")
        ]
        assert len(error_entries) > 0, f"Expected error-related event in {cap.entries}"
