"""
Unit tests for RidePathClient.

Tests the native PATH RidePATH API client for real-time arrival data.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from trackrat.collectors.path.ridepath_client import (
    PathArrival,
    RidePathClient,
    RIDEPATH_API_URL,
)


class TestRidePathClient:
    """Tests for RidePathClient."""

    @pytest.fixture
    def client(self):
        """Create a RidePathClient for testing."""
        return RidePathClient(timeout=10.0)

    @pytest.fixture
    def sample_api_response(self):
        """Sample response from the RidePATH API."""
        return {
            "results": [
                {
                    "consideredStation": "JSQ",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "World Trade Center",
                                    "arrivalTimeMessage": "4 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "8 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "4D92FB",
                                },
                            ],
                        },
                        {
                            "label": "ToNJ",
                            "messages": [
                                {
                                    "headSign": "Newark",
                                    "arrivalTimeMessage": "2 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                            ],
                        },
                    ],
                },
                {
                    "consideredStation": "WTC",
                    "destinations": [
                        {
                            "label": "ToNJ",
                            "messages": [
                                {
                                    "headSign": "Newark",
                                    "arrivalTimeMessage": "10 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                            ],
                        },
                    ],
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_get_all_arrivals_success(self, client, sample_api_response):
        """Test successful fetch of all arrivals."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 4  # 3 from JSQ + 1 from WTC
        assert all(isinstance(a, PathArrival) for a in arrivals)

        # Check JSQ -> WTC arrival
        wtc_arrivals = [a for a in arrivals if a.headsign == "World Trade Center"]
        assert len(wtc_arrivals) == 1
        assert wtc_arrivals[0].station_code == "PJS"  # Journal Square
        assert wtc_arrivals[0].minutes_away == 4
        assert wtc_arrivals[0].direction == "ToNY"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_with_cache(self, client, sample_api_response):
        """Test that caching prevents redundant API calls."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        # First call - should hit API
        arrivals1 = await client.get_all_arrivals()

        # Second call - should use cache
        arrivals2 = await client.get_all_arrivals()

        # API should only be called once
        assert mock_session.get.call_count == 1
        assert arrivals1 == arrivals2

    @pytest.mark.asyncio
    async def test_get_all_arrivals_cache_expiry(self, client, sample_api_response):
        """Test that cache expires after TTL."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        # First call
        await client.get_all_arrivals()

        # Expire cache
        client._cache_time = datetime.now() - timedelta(seconds=60)

        # Second call - should hit API again
        await client.get_all_arrivals()

        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error(self, client):
        """Test handling of HTTP errors."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=AsyncMock(),
                response=AsyncMock(status_code=500),
            )
        )
        client._session = mock_session

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_all_arrivals()

    @pytest.mark.asyncio
    async def test_get_all_arrivals_unknown_station(self, client):
        """Test that unknown station codes are skipped gracefully."""
        response_data = {
            "results": [
                {
                    "consideredStation": "UNKNOWN",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "Test",
                                    "arrivalTimeMessage": "5 min",
                                    "lastUpdated": "2026-01-19T07:00:00-05:00",
                                    "lineColor": "000000",
                                },
                            ],
                        },
                    ],
                },
            ]
        }

        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = response_data

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 0  # Unknown station skipped

    def test_parse_minutes_valid(self, client):
        """Test parsing various minute formats."""
        assert client._parse_minutes("14 min") == 14
        assert client._parse_minutes("1 min") == 1
        assert client._parse_minutes("0 min") == 0

    def test_parse_minutes_arriving(self, client):
        """Test parsing 'Arriving' message."""
        assert client._parse_minutes("Arriving") == 0
        assert client._parse_minutes("arriving now") == 0

    def test_parse_minutes_invalid(self, client):
        """Test parsing invalid formats returns None."""
        assert client._parse_minutes("") is None
        assert client._parse_minutes("invalid") is None
        assert client._parse_minutes(None) is None

    def test_parse_timestamp_valid(self, client):
        """Test parsing valid ISO timestamps."""
        ts = client._parse_timestamp("2026-01-19T07:36:57.674251-05:00")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 1
        assert ts.day == 19

    def test_parse_timestamp_invalid(self, client):
        """Test parsing invalid timestamps returns None."""
        assert client._parse_timestamp("") is None
        assert client._parse_timestamp("invalid") is None
        assert client._parse_timestamp(None) is None

    def test_clear_cache(self, client):
        """Test cache clearing."""
        client._cache = [
            PathArrival(
                station_code="PJS",
                headsign="Test",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now(),
                line_color="000000",
                last_updated=None,
            )
        ]
        client._cache_time = datetime.now()

        client.clear_cache()

        assert client._cache is None
        assert client._cache_time is None

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        # Access session to create it
        _ = client.session

        await client.close()

        assert client._session is None
