"""
Unit tests for NJ Transit discovery collector.

Tests the TrainDiscoveryCollector class with focus on the new batch collection features.
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, date

from sqlalchemy.exc import IntegrityError

from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.models.database import TrainJourney, JourneyStop, DiscoveryRun
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

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("trackrat.collectors.njt.discovery.get_session", mock_get_session),
            patch.object(
                discovery_collector, "discover_station_trains"
            ) as mock_discover,
        ):
            # Return different results for each station
            mock_discover.side_effect = lambda session, station: station_results[
                station
            ]

            result = await discovery_collector.collect()

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


class TestPopulateStopTimesFromDiscovery:
    """Tests for _populate_stop_times_from_discovery method."""

    @pytest.fixture
    def collector(self):
        """Create discovery collector with mocked client."""
        return TrainDiscoveryCollector(AsyncMock())

    @pytest.fixture
    def journey(self):
        """Create a mock journey with id and train_id."""
        j = Mock(spec=TrainJourney)
        j.id = 42
        j.train_id = "3737"
        return j

    def _make_stops_data(self, entries):
        """Build STOPS list from simplified tuples: (station_code, time, dep_time)."""
        result = []
        for code, time_str, dep_time_str in entries:
            d = {"STATION_2CHAR": code}
            if time_str is not None:
                d["TIME"] = time_str
            if dep_time_str is not None:
                d["DEP_TIME"] = dep_time_str
            result.append(d)
        return result

    @pytest.mark.asyncio
    async def test_fills_null_fields_on_existing_stop(self, collector, journey):
        """When an existing stop has NULL updated_arrival/updated_departure,
        both fields are populated from the discovery data."""
        mock_session = _make_session_mock()
        existing_stop = Mock(spec=JourneyStop)
        existing_stop.updated_arrival = None
        existing_stop.updated_departure = None
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        parsed_time = datetime(2025, 1, 1, 10, 0, 0)
        parsed_dep = datetime(2025, 1, 1, 10, 1, 0)

        stops_data = self._make_stops_data(
            [
                ("NY", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time",
            side_effect=[parsed_time, parsed_dep],
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        assert existing_stop.updated_arrival == parsed_time
        assert existing_stop.updated_departure == parsed_dep

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_values(self, collector, journey):
        """When an existing stop already has non-NULL times, they are preserved.
        The journey collector data is authoritative and must not be overwritten."""
        mock_session = _make_session_mock()
        original_arrival = datetime(2025, 1, 1, 9, 58, 0)
        original_departure = datetime(2025, 1, 1, 9, 59, 0)
        existing_stop = Mock(spec=JourneyStop)
        existing_stop.updated_arrival = original_arrival
        existing_stop.updated_departure = original_departure
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        stops_data = self._make_stops_data(
            [
                ("NY", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time",
            side_effect=[datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 10, 1)],
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        # Original values must be preserved
        assert existing_stop.updated_arrival == original_arrival
        assert existing_stop.updated_departure == original_departure

    @pytest.mark.asyncio
    async def test_partial_null_fills_only_null_field(self, collector, journey):
        """When only one field is NULL on an existing stop, only that field is updated."""
        mock_session = _make_session_mock()
        original_arrival = datetime(2025, 1, 1, 9, 58, 0)
        existing_stop = Mock(spec=JourneyStop)
        existing_stop.updated_arrival = original_arrival
        existing_stop.updated_departure = None  # Only this is NULL
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        parsed_dep = datetime(2025, 1, 1, 10, 1, 0)
        stops_data = self._make_stops_data(
            [
                ("NY", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time",
            side_effect=[datetime(2025, 1, 1, 10, 0), parsed_dep],
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        assert existing_stop.updated_arrival == original_arrival  # Unchanged
        assert existing_stop.updated_departure == parsed_dep  # Filled

    @pytest.mark.asyncio
    async def test_creates_new_stop_when_not_found(self, collector, journey):
        """When no JourneyStop exists for the station, creates a new one with times."""
        mock_session = _make_session_mock()
        mock_session.scalar = AsyncMock(return_value=None)
        mock_session.flush = AsyncMock()

        parsed_time = datetime(2025, 1, 1, 10, 0, 0)
        parsed_dep = datetime(2025, 1, 1, 10, 1, 0)
        stops_data = self._make_stops_data(
            [
                ("TR", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with (
            patch(
                "trackrat.collectors.njt.discovery.parse_njt_time",
                side_effect=[parsed_time, parsed_dep],
            ),
            patch(
                "trackrat.config.stations.get_station_name",
                return_value="Trenton",
            ),
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        # Verify session.add was called with a JourneyStop
        assert mock_session.add.call_count == 1
        added_stop = mock_session.add.call_args[0][0]
        assert added_stop.journey_id == journey.id
        assert added_stop.station_code == "TR"
        assert added_stop.station_name == "Trenton"
        assert added_stop.updated_arrival == parsed_time
        assert added_stop.updated_departure == parsed_dep

    @pytest.mark.asyncio
    async def test_integrity_error_race_fills_null_fields(self, collector, journey):
        """When creating a new stop races with the journey collector (IntegrityError),
        re-queries the stop and fills NULL fields on the concurrently-created row."""
        mock_session = _make_session_mock()
        mock_session.flush = AsyncMock(side_effect=IntegrityError("dup", {}, None))

        # First scalar call returns None (stop not found), second returns the
        # concurrently-created stop with NULL times
        race_stop = Mock(spec=JourneyStop)
        race_stop.updated_arrival = None
        race_stop.updated_departure = None
        mock_session.scalar = AsyncMock(side_effect=[None, race_stop])

        parsed_time = datetime(2025, 1, 1, 10, 0, 0)
        parsed_dep = datetime(2025, 1, 1, 10, 1, 0)
        stops_data = self._make_stops_data(
            [
                ("TR", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with (
            patch(
                "trackrat.collectors.njt.discovery.parse_njt_time",
                side_effect=[parsed_time, parsed_dep],
            ),
            patch(
                "trackrat.config.stations.get_station_name",
                return_value="Trenton",
            ),
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        # The re-queried stop should have its NULL fields filled
        assert race_stop.updated_arrival == parsed_time
        assert race_stop.updated_departure == parsed_dep

    @pytest.mark.asyncio
    async def test_integrity_error_race_preserves_existing_values(
        self, collector, journey
    ):
        """When IntegrityError race occurs but the concurrent stop already has
        non-NULL times, those values are preserved."""
        mock_session = _make_session_mock()
        mock_session.flush = AsyncMock(side_effect=IntegrityError("dup", {}, None))

        original_arrival = datetime(2025, 1, 1, 9, 55, 0)
        race_stop = Mock(spec=JourneyStop)
        race_stop.updated_arrival = original_arrival
        race_stop.updated_departure = None
        mock_session.scalar = AsyncMock(side_effect=[None, race_stop])

        parsed_time = datetime(2025, 1, 1, 10, 0, 0)
        parsed_dep = datetime(2025, 1, 1, 10, 1, 0)
        stops_data = self._make_stops_data(
            [
                ("TR", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
            ]
        )

        with (
            patch(
                "trackrat.collectors.njt.discovery.parse_njt_time",
                side_effect=[parsed_time, parsed_dep],
            ),
            patch(
                "trackrat.config.stations.get_station_name",
                return_value="Trenton",
            ),
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        # arrival was already set by journey collector — must not be overwritten
        assert race_stop.updated_arrival == original_arrival
        # departure was NULL — should be filled
        assert race_stop.updated_departure == parsed_dep

    @pytest.mark.asyncio
    async def test_skips_empty_station_code(self, collector, journey):
        """Stops with empty or missing STATION_2CHAR are skipped entirely."""
        mock_session = _make_session_mock()
        mock_session.scalar = AsyncMock()

        stops_data = [
            {"STATION_2CHAR": "", "TIME": "01-Jan-2025 10:00:00 AM"},
            {"STATION_2CHAR": "  ", "TIME": "01-Jan-2025 10:00:00 AM"},
            {"TIME": "01-Jan-2025 10:00:00 AM"},  # Missing key
        ]

        await collector._populate_stop_times_from_discovery(
            mock_session, journey, stops_data
        )

        # No database queries should have been made
        mock_session.scalar.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_stop_with_no_time_fields(self, collector, journey):
        """Stops that have a station code but no TIME or DEP_TIME are skipped."""
        mock_session = _make_session_mock()
        mock_session.scalar = AsyncMock()

        stops_data = [
            {"STATION_2CHAR": "NY"},  # No TIME or DEP_TIME at all
            {"STATION_2CHAR": "TR", "TIME": None, "DEP_TIME": None},
        ]

        await collector._populate_stop_times_from_discovery(
            mock_session, journey, stops_data
        )

        mock_session.scalar.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_only_time_no_dep_time(self, collector, journey):
        """When only TIME is present (no DEP_TIME), only updated_arrival is set."""
        mock_session = _make_session_mock()
        existing_stop = Mock(spec=JourneyStop)
        existing_stop.updated_arrival = None
        existing_stop.updated_departure = None
        mock_session.scalar = AsyncMock(return_value=existing_stop)

        parsed_time = datetime(2025, 1, 1, 10, 0, 0)
        stops_data = self._make_stops_data([("NY", "01-Jan-2025 10:00:00 AM", None)])

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time",
            return_value=parsed_time,
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        assert existing_stop.updated_arrival == parsed_time
        assert existing_stop.updated_departure is None

    @pytest.mark.asyncio
    async def test_processes_multiple_stops(self, collector, journey):
        """Multiple stops in the data are all processed correctly."""
        mock_session = _make_session_mock()

        stop_ny = Mock(spec=JourneyStop)
        stop_ny.updated_arrival = None
        stop_ny.updated_departure = None

        stop_tr = Mock(spec=JourneyStop)
        stop_tr.updated_arrival = datetime(2025, 1, 1, 9, 50, 0)  # Already set
        stop_tr.updated_departure = None

        mock_session.scalar = AsyncMock(side_effect=[stop_ny, stop_tr])

        parsed_times = [
            datetime(2025, 1, 1, 10, 0, 0),  # NY TIME
            datetime(2025, 1, 1, 10, 1, 0),  # NY DEP_TIME
            datetime(2025, 1, 1, 10, 30, 0),  # TR TIME
            datetime(2025, 1, 1, 10, 31, 0),  # TR DEP_TIME
        ]
        stops_data = self._make_stops_data(
            [
                ("NY", "01-Jan-2025 10:00:00 AM", "01-Jan-2025 10:01:00 AM"),
                ("TR", "01-Jan-2025 10:30:00 AM", "01-Jan-2025 10:31:00 AM"),
            ]
        )

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time",
            side_effect=parsed_times,
        ):
            await collector._populate_stop_times_from_discovery(
                mock_session, journey, stops_data
            )

        # NY: both NULL -> both filled
        assert stop_ny.updated_arrival == parsed_times[0]
        assert stop_ny.updated_departure == parsed_times[1]
        # TR: arrival was set -> preserved; departure was NULL -> filled
        assert stop_tr.updated_arrival == datetime(2025, 1, 1, 9, 50, 0)
        assert stop_tr.updated_departure == parsed_times[3]
