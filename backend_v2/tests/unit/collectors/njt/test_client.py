"""
Unit tests for NJ Transit API client.

Tests the NJTransitClient class, focusing on response parsing and error handling.
"""

import pytest
from unittest.mock import AsyncMock, Mock
import httpx

from trackrat.collectors.njt.client import (
    NJTransitClient,
    NJTransitAPIError,
    TrainNotFoundError,
)
from trackrat.config import Settings


class TestNJTransitClient:
    """Test cases for NJTransitClient."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            njt_api_url="https://test.api.com",
            njt_api_token="test_token",
        )

    @pytest.fixture
    def client(self, mock_settings):
        """Create a client instance for testing."""
        return NJTransitClient(mock_settings)

    @pytest.mark.asyncio
    async def test_get_train_schedule_with_items_key(self, client):
        """Test parsing response with ITEMS key (actual NJT API format)."""
        # Mock the actual NJT API response structure
        mock_response = {
            "STATION_2CHAR": "NY",
            "STATIONNAME": "New York",
            "STATIONMSGS": [],
            "ITEMS": [
                {
                    "TRAIN_ID": "3840",
                    "DESTINATION": "Trenton",
                    "SCHED_DEP_DATE": "10-Jul-2025 09:32:00 PM",
                    "LINE": "Northeast Corridor",
                    "TRACK": "7",
                    "STATUS": "ON TIME",
                },
                {
                    "TRAIN_ID": "3842",
                    "DESTINATION": "Princeton Junction",
                    "SCHED_DEP_DATE": "10-Jul-2025 10:15:00 PM",
                    "LINE": "Northeast Corridor",
                    "TRACK": "",
                    "STATUS": "5 MIN LATE",
                },
            ],
        }

        # Mock the _make_request method
        client._make_request = AsyncMock(return_value=mock_response)

        # Test the parsing
        trains = await client.get_train_schedule("NY")

        # Verify results
        assert len(trains) == 2
        assert trains[0]["TRAIN_ID"] == "3840"
        assert trains[0]["DESTINATION"] == "Trenton"
        assert trains[1]["TRAIN_ID"] == "3842"
        assert trains[1]["DESTINATION"] == "Princeton Junction"

        # Verify the API was called correctly
        client._make_request.assert_called_once_with(
            "TrainData/getTrainSchedule19Rec", {"station": "NY"}
        )

    @pytest.mark.asyncio
    async def test_get_train_schedule_fallback_parsing(self, client):
        """Test fallback parsing when ITEMS key is not present."""
        # Mock response with legacy format (TRAINS key)
        mock_response = {
            "TRAINS": [
                {
                    "TRAIN_ID": "1234",
                    "DESTINATION": "Dover",
                    "SCHED_DEP_DATE": "10-Jul-2025 11:00:00 PM",
                }
            ]
        }

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("NP")

        assert len(trains) == 1
        assert trains[0]["TRAIN_ID"] == "1234"

    @pytest.mark.asyncio
    async def test_get_train_schedule_empty_items(self, client):
        """Test handling of empty ITEMS array."""
        mock_response = {"STATION_2CHAR": "NY", "STATIONNAME": "New York", "ITEMS": []}

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("NY")

        assert len(trains) == 0

    @pytest.mark.asyncio
    async def test_get_train_schedule_list_response(self, client):
        """Test handling when API returns a list directly."""
        mock_response = [{"TRAIN_ID": "5678", "DESTINATION": "Hoboken"}]

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("HB")

        assert len(trains) == 1
        assert trains[0]["TRAIN_ID"] == "5678"

    @pytest.mark.asyncio
    async def test_get_train_schedule_malformed_response(self, client):
        """Test handling of malformed response."""
        # Response with no recognizable train data structure
        mock_response = {"ERROR": "Some API error", "STATUS": "FAILED"}

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("NY")

        # Should return empty list for unrecognized format
        assert len(trains) == 0

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, client):
        """Test proper context manager usage."""
        async with client as ctx_client:
            # Mock the HTTP client
            ctx_client._client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {"ITEMS": []}
            mock_response.raise_for_status.return_value = None
            mock_response.text = '{"ITEMS": []}'

            ctx_client._client.post = AsyncMock(return_value=mock_response)

            # Test API call
            trains = await ctx_client.get_train_schedule("NY")
            assert trains == []

    @pytest.mark.asyncio
    async def test_api_error_handling(self, client):
        """Test handling of API errors."""
        # Mock HTTP error
        http_error = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=Mock(status_code=404, text="Not Found"),
        )

        client._make_request = AsyncMock(side_effect=NJTransitAPIError("API Error"))

        with pytest.raises(NJTransitAPIError):
            await client.get_train_schedule("INVALID")

    @pytest.mark.asyncio
    async def test_regression_items_key_priority(self, client):
        """
        Regression test: Ensure ITEMS key is checked first.

        This test prevents the bug where the client wasn't finding trains
        because it didn't check the ITEMS key that NJT actually uses.
        """
        # Response that has both ITEMS (correct) and other keys
        mock_response = {
            "STATION_2CHAR": "NY",
            "ITEMS": [{"TRAIN_ID": "CORRECT", "DESTINATION": "From ITEMS"}],
            "TRAINS": [  # Wrong key that might exist in other APIs
                {"TRAIN_ID": "WRONG", "DESTINATION": "From TRAINS"}
            ],
            "data": [  # Another wrong key
                {"TRAIN_ID": "ALSO_WRONG", "DESTINATION": "From data"}
            ],
        }

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("NY")

        # Should get data from ITEMS, not other keys
        assert len(trains) == 1
        assert trains[0]["TRAIN_ID"] == "CORRECT"
        assert trains[0]["DESTINATION"] == "From ITEMS"

    @pytest.mark.asyncio
    async def test_timezone_bug_regression(self, client):
        """
        Regression test: Ensure trains are discovered regardless of timezone.

        This validates that removing the date filter allows discovery
        of trains that would have been filtered out due to timezone mismatches.
        """
        # Mock trains from "tomorrow" (which would have been filtered out)
        mock_response = {
            "ITEMS": [
                {
                    "TRAIN_ID": "LATE_NIGHT_TRAIN",
                    "DESTINATION": "Princeton",
                    # This would be "tomorrow" in UTC but "today" in ET
                    "SCHED_DEP_DATE": "11-Jul-2025 01:30:00 AM",
                    "LINE": "Northeast Corridor",
                }
            ]
        }

        client._make_request = AsyncMock(return_value=mock_response)
        trains = await client.get_train_schedule("NY")

        # Should find the train (date filtering was removed)
        assert len(trains) == 1
        assert trains[0]["TRAIN_ID"] == "LATE_NIGHT_TRAIN"

    @pytest.mark.asyncio
    async def test_get_train_stop_list_none_response(self, client):
        """Test get_train_stop_list with None response raises TrainNotFoundError."""
        client._make_request = AsyncMock(return_value=None)

        with pytest.raises(TrainNotFoundError) as exc_info:
            await client.get_train_stop_list("A643")

        assert "Train A643 not found" in str(exc_info.value)
        assert "API returned None" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_train_stop_list_empty_response(self, client):
        """Test get_train_stop_list with empty dict response raises TrainNotFoundError."""
        client._make_request = AsyncMock(return_value={})

        with pytest.raises(TrainNotFoundError) as exc_info:
            await client.get_train_stop_list("A643")

        assert "Train A643 not found" in str(exc_info.value)
        assert "empty response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_train_stop_list_invalid_type(self, client):
        """Test get_train_stop_list with invalid response type raises NJTransitAPIError."""
        client._make_request = AsyncMock(return_value="invalid string response")

        with pytest.raises(NJTransitAPIError) as exc_info:
            await client.get_train_stop_list("A643")

        assert "Expected dict response" in str(exc_info.value)
        assert "got str" in str(exc_info.value)
