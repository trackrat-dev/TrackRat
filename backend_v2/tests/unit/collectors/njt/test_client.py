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
            # Note: get_train_schedule method was removed

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

        # Note: get_train_schedule method was removed

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
