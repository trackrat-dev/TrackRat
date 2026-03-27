"""
Unit tests for WMATA API client.

Tests parsing of predictions, train positions, and incidents
from the WMATA developer API.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from trackrat.collectors.wmata.client import (
    WMATAClient,
    WMATAIncident,
    WMATAPrediction,
    WMATATrainPosition,
)


class TestWMATAClient:
    """Tests for WMATAClient."""

    @pytest.fixture
    def client(self):
        """Create a WMATAClient for testing."""
        return WMATAClient(api_key="test-key", timeout=10.0)

    @pytest.fixture
    def sample_predictions_response(self):
        """Sample response from GetPrediction/All endpoint."""
        return {
            "Trains": [
                {
                    "Car": "8",
                    "Destination": "Shady Gr",
                    "DestinationCode": "A15",
                    "DestinationName": "Shady Grove",
                    "Group": "2",
                    "Line": "RD",
                    "LocationCode": "A01",
                    "LocationName": "Metro Center",
                    "Min": "5",
                },
                {
                    "Car": "6",
                    "Destination": "Glenmont",
                    "DestinationCode": "B11",
                    "DestinationName": "Glenmont",
                    "Group": "1",
                    "Line": "RD",
                    "LocationCode": "A01",
                    "LocationName": "Metro Center",
                    "Min": "ARR",
                },
                {
                    "Car": "-",
                    "Destination": "No Passenger",
                    "DestinationCode": None,
                    "DestinationName": "No Passenger",
                    "Group": "1",
                    "Line": "RD",
                    "LocationCode": "A02",
                    "LocationName": "Farragut North",
                    "Min": "3",
                },
                {
                    "Car": "8",
                    "Destination": "Largo",
                    "DestinationCode": "G05",
                    "DestinationName": "Downtown Largo",
                    "Group": "1",
                    "Line": "BL",
                    "LocationCode": "C05",
                    "LocationName": "Rosslyn",
                    "Min": "---",
                },
            ]
        }

    @pytest.fixture
    def sample_positions_response(self):
        """Sample response from TrainPositions endpoint."""
        return {
            "TrainPositions": [
                {
                    "TrainId": "042",
                    "TrainNumber": "305",
                    "CarCount": 8,
                    "DirectionNum": 1,
                    "CircuitId": 1234,
                    "DestinationStationCode": "A15",
                    "LineCode": "RD",
                    "SecondsAtLocation": 15,
                    "ServiceType": "Normal",
                },
                {
                    "TrainId": "099",
                    "TrainNumber": "110",
                    "CarCount": 6,
                    "DirectionNum": 2,
                    "CircuitId": 5678,
                    "DestinationStationCode": None,
                    "LineCode": None,
                    "SecondsAtLocation": 0,
                    "ServiceType": "NoPassengers",
                },
            ]
        }

    @pytest.fixture
    def sample_incidents_response(self):
        """Sample response from Incidents endpoint."""
        return {
            "Incidents": [
                {
                    "IncidentID": "ABC123",
                    "Description": "Red Line: Delays due to a signal problem at Metro Center.",
                    "IncidentType": "Delay",
                    "LinesAffected": "RD; ",
                    "DateUpdated": "2026-03-25T14:21:28",
                },
                {
                    "IncidentID": "DEF456",
                    "Description": "Blue/Orange/Silver: Single tracking between Rosslyn and Arlington Cemetery.",
                    "IncidentType": "Alert",
                    "LinesAffected": "BL; OR; SV; ",
                    "DateUpdated": "2026-03-25T15:00:00",
                },
            ]
        }

    # === Prediction Tests ===

    @pytest.mark.asyncio
    async def test_get_all_predictions_success(
        self, client, sample_predictions_response
    ):
        """Test successful fetch and parsing of predictions."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()

        # "No Passenger" train should be filtered out, "---" should parse but with None minutes
        assert len(predictions) == 3
        assert all(isinstance(p, WMATAPrediction) for p in predictions)

    @pytest.mark.asyncio
    async def test_prediction_parsing_numeric_minutes(
        self, client, sample_predictions_response
    ):
        """Test that numeric minutes are parsed correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()

        shady_grove = [p for p in predictions if p.destination_code == "A15"]
        assert len(shady_grove) == 1
        assert shady_grove[0].minutes == 5
        assert shady_grove[0].is_arriving is False
        assert shady_grove[0].is_boarding is False
        assert shady_grove[0].line == "RD"
        assert shady_grove[0].location_code == "A01"
        assert shady_grove[0].car_count == 8

    @pytest.mark.asyncio
    async def test_prediction_parsing_arr(self, client, sample_predictions_response):
        """Test that ARR is parsed as arriving with 0 minutes."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()

        glenmont = [p for p in predictions if p.destination_code == "B11"]
        assert len(glenmont) == 1
        assert glenmont[0].minutes == 0
        assert glenmont[0].is_arriving is True
        assert glenmont[0].is_boarding is False

    @pytest.mark.asyncio
    async def test_prediction_filtering_no_passenger(
        self, client, sample_predictions_response
    ):
        """Test that No Passenger trains are filtered out."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()

        no_pass = [p for p in predictions if p.destination_name == "No Passenger"]
        assert len(no_pass) == 0

    @pytest.mark.asyncio
    async def test_prediction_parsing_dashes(self, client, sample_predictions_response):
        """Test that --- minutes result in None."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()

        largo = [p for p in predictions if p.destination_code == "G05"]
        assert len(largo) == 1
        assert largo[0].minutes is None

    @pytest.mark.asyncio
    async def test_predictions_cache(self, client, sample_predictions_response):
        """Test that predictions are cached within TTL."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        await client.get_all_predictions()
        await client.get_all_predictions()

        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_predictions_cache_expiry(self, client, sample_predictions_response):
        """Test that cache expires after TTL."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_predictions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        await client.get_all_predictions()
        client._pred_cache_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        await client.get_all_predictions()

        assert mock_session.get.call_count == 2

    # === Train Position Tests ===

    @pytest.mark.asyncio
    async def test_get_train_positions_success(self, client, sample_positions_response):
        """Test successful fetch and parsing of train positions."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_positions_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        positions = await client.get_train_positions()

        # NoPassengers train should be filtered out
        assert len(positions) == 1
        assert isinstance(positions[0], WMATATrainPosition)
        assert positions[0].train_id == "042"
        assert positions[0].line_code == "RD"
        assert positions[0].car_count == 8

    # === Incident Tests ===

    @pytest.mark.asyncio
    async def test_get_incidents_success(self, client, sample_incidents_response):
        """Test successful fetch and parsing of incidents."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_incidents_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        incidents = await client.get_incidents()

        assert len(incidents) == 2
        assert all(isinstance(i, WMATAIncident) for i in incidents)

    @pytest.mark.asyncio
    async def test_incident_lines_parsing(self, client, sample_incidents_response):
        """Test that LinesAffected semicolon string is parsed into list."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_incidents_response
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        incidents = await client.get_incidents()

        rd_incident = [i for i in incidents if i.incident_id == "ABC123"]
        assert len(rd_incident) == 1
        assert rd_incident[0].lines_affected == ["RD"]

        multi_line = [i for i in incidents if i.incident_id == "DEF456"]
        assert len(multi_line) == 1
        assert set(multi_line[0].lines_affected) == {"BL", "OR", "SV"}

    @pytest.mark.asyncio
    async def test_get_all_predictions_http_error(self, client):
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
            await client.get_all_predictions()

    @pytest.mark.asyncio
    async def test_empty_predictions_response(self, client):
        """Test handling of empty predictions response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"Trains": []}
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        predictions = await client.get_all_predictions()
        assert predictions == []
