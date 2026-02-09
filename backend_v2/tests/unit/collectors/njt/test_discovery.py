"""
Unit tests for NJ Transit discovery collector.

Tests the TrainDiscoveryCollector class with focus on the new batch collection features.
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, date

from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.models.database import TrainJourney, DiscoveryRun
from trackrat.utils.time import now_et


@asynccontextmanager
async def _mock_savepoint():
    """Mock async context manager for session.begin_nested()."""
    yield


def _make_session_mock():
    """Create an AsyncMock session that supports begin_nested() as async CM."""
    mock_session = AsyncMock()
    mock_session.add = Mock()
    mock_session.begin_nested = lambda: _mock_savepoint()
    return mock_session


@pytest.fixture
def mock_njt_client():
    """Mock NJ Transit client."""
    client = AsyncMock()
    client.get_train_schedule_with_stops_with_stops = AsyncMock()
    return client


@pytest.fixture
def discovery_collector(mock_njt_client):
    """Create discovery collector with mocked client."""
    return TrainDiscoveryCollector(mock_njt_client)


@pytest.fixture
def sample_train_data():
    """Sample train data from NJ Transit API."""
    return [
        {
            "TRAIN_ID": "3737",
            "LINE": "NEC",
            "LINE_NAME": "Northeast Corridor",
            "DESTINATION": "New York Penn Station",
            "SCHED_DEP_DATE": "2025-01-01 10:00:00",
            "BACKCOLOR": "#FF6600",
        },
        {
            "TRAIN_ID": "3893",
            "LINE": "NEC",
            "LINE_NAME": "Northeast Corridor",
            "DESTINATION": "Trenton",
            "SCHED_DEP_DATE": "2025-01-01 10:30:00",
            "BACKCOLOR": "#FF6600",
        },
        {
            "TRAIN_ID": "1281",
            "LINE": "NJCL",
            "LINE_NAME": "North Jersey Coast Line",
            "DESTINATION": "Long Branch",
            "SCHED_DEP_DATE": "2025-01-01 11:00:00",
            "BACKCOLOR": "#0066CC",
        },
    ]


class TestTrainDiscoveryCollector:
    """Test cases for TrainDiscoveryCollector."""

    @pytest.mark.asyncio
    async def test_discover_station_trains_returns_all_train_ids(
        self, discovery_collector, sample_train_data
    ):
        """Test that discover_station_trains returns all discovered train IDs."""
        # Mock the session and client
        mock_session = AsyncMock()
        discovery_collector.njt_client.get_train_schedule_with_stops.return_value = {
            "ITEMS": sample_train_data
        }

        # Mock database operations
        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        # Mock the process_discovered_trains method
        with patch.object(
            discovery_collector,
            "process_discovered_trains",
            return_value={"3737", "1281"},  # Only 2 are new
        ) as mock_process:

            result = await discovery_collector.discover_station_trains(
                mock_session, "NY"
            )

        # Verify all train IDs are returned
        assert "all_train_ids" in result
        assert set(result["all_train_ids"]) == {"3737", "3893", "1281"}
        assert result["trains_discovered"] == 3
        assert result["new_trains"] == 2
        assert set(result["new_train_ids"]) == {"3737", "1281"}

        # Verify client was called correctly
        discovery_collector.njt_client.get_train_schedule_with_stops.assert_called_once_with(
            "NY"
        )

        # Verify process_discovered_trains was called
        mock_process.assert_called_once_with(mock_session, "NY", sample_train_data)

    @pytest.mark.asyncio
    async def test_discover_station_trains_handles_empty_response(
        self, discovery_collector
    ):
        """Test handling of empty train schedule response."""
        mock_session = AsyncMock()
        discovery_collector.njt_client.get_train_schedule_with_stops.return_value = {
            "ITEMS": []
        }

        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        with patch.object(
            discovery_collector, "process_discovered_trains", return_value=set()
        ):
            result = await discovery_collector.discover_station_trains(
                mock_session, "NY"
            )

        assert result["all_train_ids"] == []
        assert result["trains_discovered"] == 0
        assert result["new_trains"] == 0
        assert result["new_train_ids"] == []

    @pytest.mark.asyncio
    async def test_discover_station_trains_filters_invalid_train_ids(
        self, discovery_collector
    ):
        """Test that invalid or empty train IDs are filtered out."""
        invalid_train_data = [
            {"TRAIN_ID": "3737", "SCHED_DEP_DATE": "2025-01-01 10:00:00"},
            {"TRAIN_ID": "", "SCHED_DEP_DATE": "2025-01-01 10:30:00"},  # Empty
            {"TRAIN_ID": "   ", "SCHED_DEP_DATE": "2025-01-01 11:00:00"},  # Whitespace
            {"SCHED_DEP_DATE": "2025-01-01 11:30:00"},  # Missing TRAIN_ID
            {"TRAIN_ID": "1281", "SCHED_DEP_DATE": "2025-01-01 12:00:00"},
        ]

        mock_session = AsyncMock()
        discovery_collector.njt_client.get_train_schedule_with_stops.return_value = {
            "ITEMS": invalid_train_data
        }

        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        with patch.object(
            discovery_collector,
            "process_discovered_trains",
            return_value={"3737", "1281"},
        ):
            result = await discovery_collector.discover_station_trains(
                mock_session, "NY"
            )

        # Should only include valid train IDs
        assert set(result["all_train_ids"]) == {"3737", "1281"}
        assert result["trains_discovered"] == 5  # Total items in response
        assert result["new_trains"] == 2

    @pytest.mark.asyncio
    async def test_discover_station_trains_handles_api_error(self, discovery_collector):
        """Test error handling when API call fails."""
        mock_session = AsyncMock()
        discovery_collector.njt_client.get_train_schedule_with_stops.side_effect = (
            Exception("API Error")
        )

        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        result = await discovery_collector.discover_station_trains(mock_session, "NY")

        # Should return error result
        assert result["trains_discovered"] == 0
        assert result["new_trains"] == 0
        assert "error" in result
        assert result["error"] == "API Error"

    @pytest.mark.asyncio
    async def test_collect_aggregates_all_train_ids(self, discovery_collector):
        """Test that collect method aggregates train IDs from all stations."""
        # Mock discover_station_trains to return different results for each station
        # Need to include all discovery stations: NY, NP, TR, LB, PL, DN, MP, HB, HG, GL, ND, HQ, DV, JA, RA, ST
        station_results = {
            "NY": {
                "trains_discovered": 3,
                "new_trains": 1,
                "new_train_ids": ["3737"],
                "all_train_ids": ["3737", "3893", "1281"],
            },
            "NP": {
                "trains_discovered": 2,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": ["3737", "4501"],  # 3737 overlaps
            },
            "TR": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "LB": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "PL": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "DN": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "MP": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "HB": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "HG": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "GL": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "ND": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "HQ": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "DV": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "JA": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "RA": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "ST": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
            "SV": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
        }

        mock_session = AsyncMock()

        with patch.object(
            discovery_collector, "discover_station_trains"
        ) as mock_discover:
            # Return different results for each station
            mock_discover.side_effect = lambda session, station: station_results[
                station
            ]

            result = await discovery_collector.collect(mock_session)

        # Verify aggregation
        assert result["stations_processed"] == 17  # Updated discovery stations count
        assert result["total_discovered"] == 5  # 3 + 2 (from NY and NP stations)
        assert result["total_new"] == 1  # 1 (from NY station)

        # Verify station_results contains all station data
        assert "station_results" in result
        assert len(result["station_results"]) == 17

        # Verify discover_station_trains was called for each discovery station
        assert mock_discover.call_count == 17

    @pytest.mark.asyncio
    async def test_process_discovered_trains_creates_journey_records(
        self, discovery_collector, sample_train_data
    ):
        """Test that process_discovered_trains creates journey records correctly."""
        mock_session = _make_session_mock()

        # Mock database query to return no existing journeys (all are new)
        mock_session.scalar = AsyncMock(return_value=None)

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            # Mock time parsing
            mock_parse_time.side_effect = [
                datetime(2025, 1, 1, 10, 0, 0),
                datetime(2025, 1, 1, 10, 30, 0),
                datetime(2025, 1, 1, 11, 0, 0),
            ]

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 9, 0, 0)

                result = await discovery_collector.process_discovered_trains(
                    mock_session, "NY", sample_train_data
                )

        # All trains should be new
        assert result == {"3737", "3893", "1281"}

        # Verify session.add was called 3 times (once per train)
        assert mock_session.add.call_count == 3

    @pytest.mark.asyncio
    async def test_process_discovered_trains_skips_amtrak_trains(
        self, discovery_collector
    ):
        """Test that Amtrak trains are skipped during NJT discovery."""
        mock_session = _make_session_mock()

        mock_session.scalar = AsyncMock(return_value=None)  # No existing journey

        # Sample data with mix of NJT and Amtrak trains
        sample_train_data = [
            {
                "TRAIN_ID": "3840",  # NJT train (numeric)
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "DESTINATION": "Trenton",
                "LINE": "Northeast Corridor",
            },
            {
                "TRAIN_ID": "A2151",  # Amtrak train (A + digits)
                "SCHED_DEP_DATE": "11-Jan-2025 10:30:00 AM",
                "DESTINATION": "Washington",
                "LINE": "Northeast Corridor",
            },
            {
                "TRAIN_ID": "A98",  # Another Amtrak train
                "SCHED_DEP_DATE": "11-Jan-2025 11:00:00 AM",
                "DESTINATION": "Boston",
                "LINE": "Northeast Corridor",
            },
            {
                "TRAIN_ID": "5126",  # Another NJT train
                "SCHED_DEP_DATE": "11-Jan-2025 11:30:00 AM",
                "DESTINATION": "Princeton Junction",
                "LINE": "Northeast Corridor",
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            # Mock time parsing
            mock_parse_time.side_effect = [
                datetime(2025, 1, 1, 10, 0, 0),  # 3840
                datetime(2025, 1, 1, 11, 30, 0),  # 5126 (A2151 and A98 skipped)
            ]

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 9, 0, 0)

                result = await discovery_collector.process_discovered_trains(
                    mock_session, "NY", sample_train_data
                )

        # Only NJT trains should be processed (Amtrak trains skipped)
        assert result == {"3840", "5126"}

        # Verify session.add was called only 2 times (Amtrak trains skipped)
        assert mock_session.add.call_count == 2

        # Verify parse_njt_time was called only for NJT trains
        assert mock_parse_time.call_count == 2

    @pytest.mark.asyncio
    async def test_amtrak_train_id_patterns(self, discovery_collector):
        """Test that various Amtrak train ID patterns are correctly identified."""
        mock_session = _make_session_mock()

        mock_session.scalar = AsyncMock(return_value=None)

        # Test various Amtrak train ID patterns
        test_cases = [
            {
                "TRAIN_ID": "A2151",  # Typical Amtrak format
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": True,
            },
            {
                "TRAIN_ID": "A98",  # Short Amtrak ID
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": True,
            },
            {
                "TRAIN_ID": "A1",  # Single digit Amtrak
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": True,
            },
            {
                "TRAIN_ID": "3840",  # NJT numeric
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": False,
            },
            {
                "TRAIN_ID": "AB123",  # Not pure A + digits
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": False,
            },
            {
                "TRAIN_ID": "A",  # Just "A"
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": False,
            },
            {
                "TRAIN_ID": "Amtrak123",  # Starts with A but not pure pattern
                "SCHED_DEP_DATE": "11-Jan-2025 10:00:00 AM",
                "expected_skipped": False,
            },
        ]

        expected_processed = [
            case for case in test_cases if not case["expected_skipped"]
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.side_effect = [
                datetime(2025, 1, 1, 10, 0, 0) for _ in expected_processed
            ]

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 9, 0, 0)

                result = await discovery_collector.process_discovered_trains(
                    mock_session, "NY", test_cases
                )

        # Only non-Amtrak trains should be processed
        expected_train_ids = {case["TRAIN_ID"] for case in expected_processed}
        assert result == expected_train_ids

        # Verify session.add was called only for non-Amtrak trains
        assert mock_session.add.call_count == len(expected_processed)
