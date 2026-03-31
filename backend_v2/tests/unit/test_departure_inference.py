"""
Unit tests for the three-tier departure inference system.

Tests the core logic without making real API calls.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et, ET


class TestDepartureInference:
    """Test the three-tier departure inference system."""

    @pytest.fixture
    def mock_njt_client(self):
        """Create a mock NJT client."""
        client = MagicMock()
        client.get_train_stop_list = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_njt_client):
        """Create a JourneyCollector with mock client."""
        return JourneyCollector(mock_njt_client)

    @pytest.fixture
    def mock_session(self):
        """Create a properly mocked AsyncSession."""
        from unittest.mock import AsyncMock, Mock

        session = AsyncMock(spec=AsyncSession)

        # Mock the result object that SQLAlchemy returns
        mock_result = Mock()
        # Handle the full chain: result.scalars().unique().all()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = []  # Empty list for no data
        mock_scalars.all.return_value = []  # For direct .scalars().all() calls
        mock_scalars.first.return_value = None  # For .first() calls
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = None
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []

        session.execute = AsyncMock(return_value=mock_result)
        session.scalar = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.rollback = AsyncMock()
        session.delete = AsyncMock()  # Async in newer SQLAlchemy
        session.add = Mock()  # Non-async
        session.add_all = Mock()  # Non-async

        return session

    @pytest.fixture
    def sample_journey(self):
        """Create a sample journey for testing."""
        journey = TrainJourney(
            id=1,
            train_id="TEST_123",
            journey_date=datetime.now().date(),
            line_code="TE",
            destination="Test Destination",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et() - timedelta(hours=2),
            has_complete_journey=True,
        )

        # Add stops with various scenarios
        journey.stops = [
            JourneyStop(
                journey_id=1,
                station_code="NY",
                station_name="New York",
                stop_sequence=0,
                scheduled_departure=now_et() - timedelta(hours=2),
                has_departed_station=False,
            ),
            JourneyStop(
                journey_id=1,
                station_code="NP",
                station_name="Newark Penn",
                stop_sequence=1,
                scheduled_departure=now_et() - timedelta(hours=1, minutes=30),
                scheduled_arrival=now_et() - timedelta(hours=1, minutes=35),
                has_departed_station=False,
            ),
            JourneyStop(
                journey_id=1,
                station_code="MP",
                station_name="Metropark",
                stop_sequence=2,
                scheduled_departure=now_et() - timedelta(hours=1),
                scheduled_arrival=now_et() - timedelta(hours=1, minutes=5),
                has_departed_station=False,
            ),
            JourneyStop(
                journey_id=1,
                station_code="TR",
                station_name="Trenton",
                stop_sequence=3,
                scheduled_departure=now_et() + timedelta(hours=1),
                scheduled_arrival=now_et() + timedelta(minutes=55),
                has_departed_station=False,
            ),
        ]

        return journey

    @pytest.mark.skip(reason="Complex database mocking - covered by integration tests")
    async def test_tier1_api_explicit(self, collector, sample_journey, mock_session):
        """Test Tier 1: API explicit DEPARTED flag."""
        session = mock_session

        # Set up the mock to return the stops from sample_journey when queried
        def mock_execute_side_effect(stmt):
            # Create a mock result that returns the relevant stop
            mock_result = Mock()
            mock_scalars = Mock()

            # Check if this is a query for a specific stop
            # For simplicity, we'll return the matching stop from sample_journey
            for stop in sample_journey.stops:
                if hasattr(stmt, "whereclause") and stop.station_code in str(stmt):
                    mock_scalars.scalar_one_or_none.return_value = stop
                    mock_result.scalar_one_or_none.return_value = stop
                    break
            else:
                mock_scalars.scalar_one_or_none.return_value = None
                mock_result.scalar_one_or_none.return_value = None

            mock_result.scalars.return_value = mock_scalars
            mock_result.scalar.return_value = None
            return mock_result

        session.execute.side_effect = mock_execute_side_effect

        # Create API response with DEPARTED="YES" for Newark
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="NO",
                TIME="10:00:00 AM",
                DEP_TIME="10:00:00 AM",
                ARR_TIME=None,
                TRACK=None,
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="YES",  # Explicitly departed
                TIME="10:30:00 AM",
                DEP_TIME="10:35:00 AM",
                ARR_TIME="10:30:00 AM",
                TRACK="2",
            ),
            MagicMock(
                ITEM="MP | Metropark",
                STATION_2CHAR="MP",
                STATIONNAME="Metropark",
                DEPARTED="NO",
                TIME="11:00:00 AM",
                DEP_TIME="11:05:00 AM",
                ARR_TIME="11:00:00 AM",
                TRACK=None,
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",
                TIME="12:00:00 PM",
                DEP_TIME=None,
                ARR_TIME="12:00:00 PM",
                TRACK=None,
            ),
        ]

        await collector.update_journey_stops(session, sample_journey, api_stops)

        # Verify Newark marked as departed with api_explicit
        np_stop = next(s for s in sample_journey.stops if s.station_code == "NP")
        assert np_stop.has_departed_station == True
        assert np_stop.departure_source == "api_explicit"
        assert np_stop.actual_departure is not None
        assert np_stop.actual_arrival is not None

    @pytest.mark.skip(reason="Complex database mocking - covered by integration tests")
    async def test_tier2_sequential_inference(
        self, collector, sample_journey, mock_session
    ):
        """Test Tier 2: Sequential inference from later departed stop."""
        session = mock_session

        # API says Metropark (seq 2) has departed, so NY (seq 0) and NP (seq 1) must have too
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="NO",  # API doesn't say departed
                TIME="10:00:00 AM",
                DEP_TIME="10:00:00 AM",
                ARR_TIME=None,
                TRACK="7",
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="NO",  # API doesn't say departed
                TIME="10:30:00 AM",
                DEP_TIME="10:35:00 AM",
                ARR_TIME="10:30:00 AM",
                TRACK="2",
            ),
            MagicMock(
                ITEM="MP | Metropark",
                STATION_2CHAR="MP",
                STATIONNAME="Metropark",
                DEPARTED="YES",  # This one has departed
                TIME="11:00:00 AM",
                DEP_TIME="11:05:00 AM",
                ARR_TIME="11:00:00 AM",
                TRACK="1",
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",
                TIME="12:00:00 PM",
                DEP_TIME=None,
                ARR_TIME="12:00:00 PM",
                TRACK=None,
            ),
        ]

        await collector.update_journey_stops(session, sample_journey, api_stops)

        # Verify NY and NP marked as departed with sequential_inference
        ny_stop = next(s for s in sample_journey.stops if s.station_code == "NY")
        assert ny_stop.has_departed_station == True
        assert ny_stop.departure_source == "sequential_inference"
        assert ny_stop.actual_departure is not None

        np_stop = next(s for s in sample_journey.stops if s.station_code == "NP")
        assert np_stop.has_departed_station == True
        assert np_stop.departure_source == "sequential_inference"
        assert np_stop.actual_departure is not None

    async def test_tier3_time_inference(self, collector, sample_journey, mock_session):
        """Test Tier 3: Time-based inference for old stops.

        Verifies that stops whose scheduled_departure is >5min in the past
        get has_departed_station=True and departure_source='time_inference',
        but do NOT get actual_departure or actual_arrival set (no real data).
        """
        session = mock_session

        # Make session.scalar return matching stops from sample_journey
        # so update_journey_stops modifies existing stops in-place.
        # Stops are sorted by time (NY, NP, MP, TR), so scalar is called
        # in that order — one call per stop.
        stops_by_code = {s.station_code: s for s in sample_journey.stops}
        stop_order = ["NY", "NP", "MP", "TR"]
        scalar_calls = iter(stop_order)

        async def scalar_side_effect(stmt):
            try:
                code = next(scalar_calls)
                return stops_by_code[code]
            except StopIteration:
                return None

        session.scalar = AsyncMock(side_effect=scalar_side_effect)

        # No stops marked as departed by API — all DEPARTED="NO"
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="NO",
                TIME="10:00:00 AM",
                DEP_TIME="10:00:00 AM",
                ARR_TIME=None,
                TRACK="7",
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="NO",
                TIME="10:30:00 AM",
                DEP_TIME="10:35:00 AM",
                ARR_TIME="10:30:00 AM",
                TRACK="2",
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
            MagicMock(
                ITEM="MP | Metropark",
                STATION_2CHAR="MP",
                STATIONNAME="Metropark",
                DEPARTED="NO",
                TIME="11:00:00 AM",
                DEP_TIME="11:05:00 AM",
                ARR_TIME="11:00:00 AM",
                TRACK="1",
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",
                TIME="12:00:00 PM",
                DEP_TIME=None,
                ARR_TIME="12:00:00 PM",
                TRACK=None,
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
        ]

        await collector.update_journey_stops(session, sample_journey, api_stops)

        # Verify old stops marked as departed with time_inference,
        # but actual_departure is NOT set (no real data to use).
        ny_stop = stops_by_code["NY"]
        assert ny_stop.has_departed_station == True
        assert ny_stop.departure_source == "time_inference"
        assert (
            ny_stop.actual_departure is None
        ), "Tier 3 must not set actual_departure from schedule data"
        assert (
            ny_stop.actual_arrival is None
        ), "Tier 3 must not set actual_arrival for time-inferred stops"

        np_stop = stops_by_code["NP"]
        assert np_stop.has_departed_station == True
        assert np_stop.departure_source == "time_inference"
        assert (
            np_stop.actual_departure is None
        ), "Tier 3 must not set actual_departure from schedule data"

        mp_stop = stops_by_code["MP"]
        assert mp_stop.has_departed_station == True
        assert mp_stop.departure_source == "time_inference"
        assert (
            mp_stop.actual_departure is None
        ), "Tier 3 must not set actual_departure from schedule data"

        # Trenton is in the future, should NOT be marked departed
        tr_stop = stops_by_code["TR"]
        assert tr_stop.has_departed_station == False
        assert tr_stop.departure_source is None

    @pytest.mark.skip(reason="Complex database mocking - covered by integration tests")
    async def test_swapped_times_correction(
        self, collector, sample_journey, mock_session
    ):
        """Test detection and correction of swapped arrival/departure times."""
        session = mock_session

        # API with swapped times (arrival > departure for intermediate stop)
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="YES",
                TIME="10:00:00 AM",
                DEP_TIME="10:00:00 AM",
                ARR_TIME=None,  # Origin has no arrival
                TRACK="7",
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="YES",
                TIME="10:30:00 AM",
                # SWAPPED: Arrival after departure (NJT API bug)
                DEP_TIME="10:30:00 AM",  # Earlier
                ARR_TIME="10:35:00 AM",  # Later (should be earlier!)
                TRACK="2",
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",
                TIME="12:00:00 PM",
                DEP_TIME=None,  # Terminal has no departure
                ARR_TIME="12:00:00 PM",
                TRACK=None,
            ),
        ]

        # Mock the logger to capture warning
        with patch("trackrat.collectors.njt.journey.logger") as mock_logger:
            await collector.update_journey_stops(session, sample_journey, api_stops[:3])

            # Verify swap was detected and logged
            mock_logger.warning.assert_called()
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "swapped_arrival_departure_times" in str(call)
            ]
            assert len(warning_calls) > 0

        # Verify times were corrected (arrival should be before departure)
        np_stop = next(s for s in sample_journey.stops if s.station_code == "NP")
        if np_stop.actual_arrival and np_stop.actual_departure:
            assert np_stop.actual_arrival <= np_stop.actual_departure

    @pytest.mark.asyncio
    async def test_scheduled_times_immutable(
        self, collector, sample_journey, mock_session
    ):
        """Test that scheduled times are never modified after initial set."""
        session = mock_session

        # Save original scheduled times
        original_scheduled = {
            stop.station_code: {
                "departure": stop.scheduled_departure,
                "arrival": stop.scheduled_arrival,
            }
            for stop in sample_journey.stops
        }

        # API with different times
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="YES",
                TIME="11:00:00 AM",  # Different time
                DEP_TIME="11:00:00 AM",
                ARR_TIME=None,
                TRACK="7",
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="YES",
                TIME="11:30:00 AM",  # Different time
                DEP_TIME="11:35:00 AM",
                ARR_TIME="11:30:00 AM",
                TRACK="2",
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
        ]

        await collector.update_journey_stops(session, sample_journey, api_stops[:2])

        # Verify scheduled times unchanged
        for stop in sample_journey.stops:
            if stop.station_code in original_scheduled:
                assert (
                    stop.scheduled_departure
                    == original_scheduled[stop.station_code]["departure"]
                )
                assert (
                    stop.scheduled_arrival
                    == original_scheduled[stop.station_code]["arrival"]
                )

    @pytest.mark.skip(reason="Complex database mocking - covered by integration tests")
    async def test_all_tiers_combined(self, collector, sample_journey, mock_session):
        """Test all three tiers working together in priority order."""
        session = mock_session

        # Complex scenario with all three tiers applicable
        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="NO",  # Will get sequential inference
                TIME="10:00:00 AM",
                DEP_TIME="10:00:00 AM",
                ARR_TIME=None,
                TRACK="7",
            ),
            MagicMock(
                ITEM="NP | Newark Penn",
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                DEPARTED="YES",  # Explicit API flag (Tier 1)
                TIME="10:30:00 AM",
                DEP_TIME="10:35:00 AM",
                ARR_TIME="10:30:00 AM",
                TRACK="2",
            ),
            MagicMock(
                ITEM="MP | Metropark",
                STATION_2CHAR="MP",
                STATIONNAME="Metropark",
                DEPARTED="NO",  # Will get time inference
                TIME="11:00:00 AM",
                DEP_TIME="11:05:00 AM",
                ARR_TIME="11:00:00 AM",
                TRACK="1",
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",  # Future, won't be marked
                TIME="12:00:00 PM",
                DEP_TIME=None,
                ARR_TIME="12:00:00 PM",
                TRACK=None,
            ),
        ]

        await collector.update_journey_stops(session, sample_journey, api_stops)

        # Verify correct tier was used for each stop
        ny_stop = next(s for s in sample_journey.stops if s.station_code == "NY")
        assert (
            ny_stop.departure_source == "sequential_inference"
        )  # Before explicit stop

        np_stop = next(s for s in sample_journey.stops if s.station_code == "NP")
        assert np_stop.departure_source == "api_explicit"  # Has DEPARTED=YES

        mp_stop = next(s for s in sample_journey.stops if s.station_code == "MP")
        assert mp_stop.departure_source == "time_inference"  # Old enough
        assert (
            mp_stop.actual_departure is None
        ), "Tier 3 must not set actual_departure from schedule data"

        tr_stop = next(s for s in sample_journey.stops if s.station_code == "TR")
        assert tr_stop.departure_source is None  # Future stop

    @pytest.mark.asyncio
    async def test_edge_case_no_stops(self, collector, mock_session):
        """Test handling of journey with no stops."""
        session = mock_session
        journey = TrainJourney(
            id=1, train_id="EMPTY", journey_date=datetime.now().date(), stops=[]
        )

        # Should handle gracefully
        await collector.update_journey_stops(session, journey, [])
        assert len(journey.stops) == 0

    @pytest.mark.asyncio
    async def test_edge_case_all_future(self, collector, mock_session):
        """Test when all stops are in the future."""
        session = mock_session

        future_time = now_et() + timedelta(hours=2)
        journey = TrainJourney(
            id=1,
            train_id="FUTURE",
            journey_date=datetime.now().date(),
            stops=[
                JourneyStop(
                    journey_id=1,
                    station_code="NY",
                    station_name="New York",
                    stop_sequence=0,
                    scheduled_departure=future_time,
                    has_departed_station=False,
                ),
                JourneyStop(
                    journey_id=1,
                    station_code="TR",
                    station_name="Trenton",
                    stop_sequence=1,
                    scheduled_departure=future_time + timedelta(hours=1),
                    has_departed_station=False,
                ),
            ],
        )

        api_stops = [
            MagicMock(
                ITEM="NY | New York",
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                DEPARTED="NO",
                TIME="02:00:00 PM",
                DEP_TIME="02:00:00 PM",
                ARR_TIME=None,
                TRACK=None,
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
            MagicMock(
                ITEM="TR | Trenton",
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                DEPARTED="NO",
                TIME="03:00:00 PM",
                DEP_TIME=None,
                ARR_TIME="03:00:00 PM",
                TRACK=None,
                SCHED_ARR_DATE=None,
                SCHED_DEP_DATE=None,
                PICKUP=None,
                DROPOFF=None,
            ),
        ]

        await collector.update_journey_stops(session, journey, api_stops)

        # No stops should be marked as departed
        for stop in journey.stops:
            assert stop.has_departed_station == False
            assert stop.departure_source is None
