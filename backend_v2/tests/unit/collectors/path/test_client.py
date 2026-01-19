"""
Unit tests for PathClient.

Tests Transiter API communication, response parsing, and caching.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from trackrat.collectors.path.client import (
    PathClient,
    PathStopTime,
    TRANSITER_BASE_URL,
)


class TestPathStopTime:
    """Tests for PathStopTime model."""

    def test_from_transiter_valid_data(self):
        """Test parsing valid Transiter stop time data."""
        data = {
            "trip": {
                "id": "trip_123",
                "route": {"id": "859"},
                "destination": {"name": "33rd Street"},
                "directionId": 0,
            },
            "departure": {"time": "1705000000"},
            "arrival": {"time": "1705000000"},
            "headsign": "33rd St",
        }

        result = PathStopTime.from_transiter(data)

        assert result is not None
        assert result.trip_id == "trip_123"
        assert result.route_id == "859"
        # Headsign prefers trip.destination.name over data.headsign
        assert result.headsign == "33rd Street"
        assert result.direction_id == 0
        assert result.departure_time is not None
        assert result.arrival_time is not None

    def test_from_transiter_missing_trip_id(self):
        """Test parsing fails gracefully when trip_id is missing."""
        data = {
            "trip": {"route": {"id": "859"}},
            "departure": {"time": "1705000000"},
        }

        result = PathStopTime.from_transiter(data)

        assert result is None

    def test_from_transiter_missing_route_id(self):
        """Test parsing fails gracefully when route_id is missing."""
        data = {
            "trip": {"id": "trip_123"},
            "departure": {"time": "1705000000"},
        }

        result = PathStopTime.from_transiter(data)

        assert result is None

    def test_from_transiter_no_times(self):
        """Test parsing succeeds when times are missing (optional)."""
        data = {
            "trip": {
                "id": "trip_123",
                "route": {"id": "859"},
            },
            "departure": {},
            "arrival": {},
        }

        result = PathStopTime.from_transiter(data)

        assert result is not None
        assert result.departure_time is None
        assert result.arrival_time is None

    def test_from_transiter_headsign_fallback_to_destination(self):
        """Test headsign falls back to destination name when headsign is empty."""
        data = {
            "trip": {
                "id": "trip_123",
                "route": {"id": "859"},
                "destination": {"name": "World Trade Center"},
            },
            "departure": {"time": "1705000000"},
        }

        result = PathStopTime.from_transiter(data)

        assert result is not None
        assert result.headsign == "World Trade Center"


class TestPathClient:
    """Tests for PathClient."""

    @pytest.fixture
    def client(self):
        """Create a PathClient instance for testing."""
        return PathClient(timeout=10.0)

    def test_initialization(self, client):
        """Test client initializes with correct defaults."""
        assert client.base_url == TRANSITER_BASE_URL
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache == {}
        assert client._cache_time == {}

    def test_session_property_creates_session(self, client):
        """Test session property lazily creates httpx client."""
        assert client._session is None
        session = client.session
        assert session is not None
        assert isinstance(session, httpx.AsyncClient)

    def test_session_property_reuses_session(self, client):
        """Test session property returns same session on repeated calls."""
        session1 = client.session
        session2 = client.session
        assert session1 is session2

    async def test_close_clears_session(self, client):
        """Test close method clears the session."""
        _ = client.session  # Create session
        assert client._session is not None
        await client.close()
        assert client._session is None

    async def test_context_manager(self, client):
        """Test async context manager entry and exit."""
        async with client as c:
            assert c is client
        assert client._session is None

    def test_cache_validation_empty(self, client):
        """Test cache is invalid when empty."""
        assert not client._is_cache_valid("26735")

    def test_cache_validation_valid(self, client):
        """Test cache is valid when recently populated."""
        client._cache["26735"] = [PathStopTime(trip_id="t1", route_id="r1")]
        client._cache_time["26735"] = datetime.now()
        assert client._is_cache_valid("26735")

    def test_cache_validation_expired(self, client):
        """Test cache is invalid when expired."""
        client._cache["26735"] = [PathStopTime(trip_id="t1", route_id="r1")]
        client._cache_time["26735"] = datetime.now() - timedelta(seconds=60)
        assert not client._is_cache_valid("26735")

    def test_clear_cache(self, client):
        """Test clear_cache empties all cache data."""
        client._cache["26735"] = [PathStopTime(trip_id="t1", route_id="r1")]
        client._cache_time["26735"] = datetime.now()

        client.clear_cache()

        assert client._cache == {}
        assert client._cache_time == {}

    @pytest.mark.asyncio
    async def test_get_station_arrivals_returns_cached(self, client):
        """Test get_station_arrivals returns cached data when valid."""
        expected = [PathStopTime(trip_id="t1", route_id="r1")]
        client._cache["26735"] = expected
        client._cache_time["26735"] = datetime.now()

        result = await client.get_station_arrivals("26735")

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_station_arrivals_parses_response(self, client):
        """Test get_station_arrivals parses Transiter API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stopTimes": [
                {
                    "trip": {
                        "id": "trip_abc",
                        "route": {"id": "859"},
                        "destination": {"name": "33rd Street"},
                    },
                    "departure": {"time": "1705000000"},
                    "arrival": {"time": "1705000000"},
                    "headsign": "33rd St via Hoboken",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client.get_station_arrivals("26735")

        assert len(result) == 1
        assert result[0].trip_id == "trip_abc"
        assert result[0].route_id == "859"
        # Headsign prefers trip.destination.name over data.headsign
        assert result[0].headsign == "33rd Street"

    @pytest.mark.asyncio
    async def test_get_station_arrivals_handles_empty_response(self, client):
        """Test get_station_arrivals handles empty stopTimes array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"stopTimes": []}
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client.get_station_arrivals("26735")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_station_arrivals_handles_http_error(self, client):
        """Test get_station_arrivals returns empty list on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client.get_station_arrivals("invalid_stop")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_station_arrivals_handles_network_error(self, client):
        """Test get_station_arrivals returns empty list on network error."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.ConnectError("Failed"))
        client._session = mock_session

        result = await client.get_station_arrivals("26735")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_station_arrivals_updates_cache(self, client):
        """Test get_station_arrivals populates cache after successful fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stopTimes": [
                {
                    "trip": {"id": "trip_xyz", "route": {"id": "860"}},
                    "departure": {"time": "1705000000"},
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        await client.get_station_arrivals("26740")

        assert "26740" in client._cache
        assert "26740" in client._cache_time
        assert len(client._cache["26740"]) == 1
