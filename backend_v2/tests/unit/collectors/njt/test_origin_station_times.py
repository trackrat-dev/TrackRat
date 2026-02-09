"""
Unit tests for origin station time normalization.

Tests the fix for the bug where trains departing from origin stations (like NY Penn)
were showing as "early" when they were actually delayed, due to NJT API having
inverted TIME/DEP_TIME semantics at origin stations.

Bug discovery:
- Train 3871 showed "26m early" from NY Penn when it was actually delayed
- Root cause: At origin, TIME=original schedule, DEP_TIME=actual departure
- At intermediate stops: TIME=actual arrival, DEP_TIME=original schedule
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.journey import (
    JourneyCollector,
    normalize_njt_stop_times,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et

from tests.fixtures.njt_api_responses import StopBuilder, create_stop_list_response


class TestNormalizeNjtStopTimes:
    """Unit tests for the normalize_njt_stop_times function."""

    def test_origin_station_delayed_train(self):
        """Test origin station with delayed train (TIME < DEP_TIME).

        Simulates Train 3871 scenario:
        - TIME = 05:24 PM (original schedule)
        - DEP_TIME = 05:50 PM (actual departure, 26 min delayed)
        """
        time_field = datetime(2026, 1, 28, 17, 24, 0, tzinfo=ET)  # 5:24 PM
        dep_time_field = datetime(2026, 1, 28, 17, 50, 0, tzinfo=ET)  # 5:50 PM

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=True,
            has_departed=True,
        )

        # At origin: scheduled = TIME, actual = DEP_TIME
        assert result["scheduled_arrival"] is None  # No arrival at origin
        assert result["scheduled_departure"] == time_field  # 5:24 PM (original)
        assert result["actual_arrival"] is None  # No arrival at origin
        assert result["actual_departure"] == dep_time_field  # 5:50 PM (actual)

        # Verify delay calculation would be correct
        delay_minutes = (
            result["actual_departure"] - result["scheduled_departure"]
        ).total_seconds() / 60
        assert delay_minutes == 26  # +26 min delay, NOT -26 min early!

    def test_origin_station_on_time_train(self):
        """Test origin station with on-time train (TIME == DEP_TIME)."""
        time_field = datetime(2026, 1, 28, 18, 47, 0, tzinfo=ET)
        dep_time_field = datetime(2026, 1, 28, 18, 47, 0, tzinfo=ET)

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=True,
            has_departed=True,
        )

        assert result["scheduled_departure"] == time_field
        assert result["actual_departure"] == dep_time_field

        # Delay should be 0
        delay_minutes = (
            result["actual_departure"] - result["scheduled_departure"]
        ).total_seconds() / 60
        assert delay_minutes == 0

    def test_origin_station_not_departed(self):
        """Test origin station before train departs."""
        time_field = datetime(2026, 1, 28, 20, 31, 0, tzinfo=ET)
        dep_time_field = datetime(2026, 1, 28, 20, 42, 0, tzinfo=ET)

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=True,
            has_departed=False,  # Not yet departed
        )

        assert result["scheduled_departure"] == time_field
        assert result["actual_departure"] is None  # No actual yet

    def test_intermediate_station_delayed_train(self):
        """Test intermediate station with delayed train.

        Simulates Secaucus scenario:
        - TIME = 06:42:30 PM (actual arrival, delayed)
        - DEP_TIME = 06:00 PM (original schedule)
        """
        time_field = datetime(2026, 1, 28, 18, 42, 30, tzinfo=ET)  # 6:42:30 PM
        dep_time_field = datetime(2026, 1, 28, 18, 0, 0, tzinfo=ET)  # 6:00 PM

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=False,
            has_departed=True,
        )

        # At intermediate: scheduled = DEP_TIME, actual = TIME
        assert (
            result["scheduled_arrival"] == time_field
        )  # First observation captures live estimate
        assert (
            result["scheduled_departure"] == dep_time_field
        )  # 6:00 PM (original schedule)
        assert result["actual_arrival"] == time_field  # 6:42:30 PM (actual)
        assert (
            result["actual_departure"] == time_field
        )  # Same as arrival for intermediate

        # Delay calculation (using departure times)
        delay_minutes = (
            result["actual_departure"] - result["scheduled_departure"]
        ).total_seconds() / 60
        assert delay_minutes == 42.5  # +42.5 min delay

    def test_intermediate_station_on_time(self):
        """Test intermediate station with on-time train."""
        time_field = datetime(2026, 1, 28, 18, 56, 52, tzinfo=ET)
        dep_time_field = datetime(2026, 1, 28, 18, 56, 30, tzinfo=ET)

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=False,
            has_departed=True,
        )

        # On-time: TIME ≈ DEP_TIME
        delay_minutes = (
            result["actual_departure"] - result["scheduled_departure"]
        ).total_seconds() / 60
        assert abs(delay_minutes) < 1  # Less than 1 minute difference

    def test_intermediate_station_not_departed(self):
        """Test intermediate station before train arrives."""
        time_field = datetime(2026, 1, 28, 20, 47, 30, tzinfo=ET)
        dep_time_field = datetime(2026, 1, 28, 20, 48, 30, tzinfo=ET)

        result = normalize_njt_stop_times(
            time_field=time_field,
            dep_time_field=dep_time_field,
            is_origin_station=False,
            has_departed=False,
        )

        assert result["scheduled_departure"] == dep_time_field
        assert result["actual_arrival"] == time_field  # Live estimate continues
        assert result["actual_departure"] is None  # Not departed yet

    def test_none_time_fields(self):
        """Test handling of None time fields."""
        result = normalize_njt_stop_times(
            time_field=None,
            dep_time_field=None,
            is_origin_station=True,
            has_departed=False,
        )

        assert result["scheduled_arrival"] is None
        assert result["scheduled_departure"] is None
        assert result["actual_arrival"] is None
        assert result["actual_departure"] is None


@pytest.fixture
def mock_njt_client():
    """Mock NJ Transit client."""
    from unittest.mock import AsyncMock

    client = AsyncMock(spec=NJTransitClient)
    return client


@pytest.fixture
def journey_collector(mock_njt_client):
    """Create journey collector with mocked client."""
    return JourneyCollector(mock_njt_client)


class TestOriginStationDelayCalculation:
    """Integration tests for origin station delay calculation."""

    @pytest.mark.asyncio
    async def test_delayed_train_from_ny_penn_shows_correct_delay(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that a delayed train from NY Penn shows positive delay, not early.

        Replicates the Train 3871 bug:
        - Original schedule: 5:24 PM
        - Actual departure: 5:50 PM
        - Should show: +26 min delay
        - Was showing: 26 min early (BUG)
        """
        # Create journey with NY Penn as origin
        journey = TrainJourney(
            train_id="3871",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",  # New York Penn Station
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create API response simulating Train 3871's actual data
        # Key: At origin (NY), TIME < DEP_TIME indicates delay
        builder = StopBuilder()

        # Build stops with explicit TIME and DEP_TIME values
        origin_stop = MagicMock()
        origin_stop.STATION_2CHAR = "NY"
        origin_stop.STATIONNAME = "New York Penn Station"
        origin_stop.TIME = "28-Jan-2026 05:24:00 PM"  # Original schedule
        origin_stop.DEP_TIME = "28-Jan-2026 05:50:00 PM"  # Actual departure (delayed)
        origin_stop.DEPARTED = "YES"
        origin_stop.TRACK = "7"
        origin_stop.PICKUP = None
        origin_stop.DROPOFF = None
        origin_stop.STOP_STATUS = "BOARDING"
        origin_stop.SCHED_ARR_DATE = None
        origin_stop.SCHED_DEP_DATE = None

        intermediate_stop = MagicMock()
        intermediate_stop.STATION_2CHAR = "SE"
        intermediate_stop.STATIONNAME = "Secaucus Upper Lvl"
        intermediate_stop.TIME = "28-Jan-2026 06:42:30 PM"  # Actual arrival (delayed)
        intermediate_stop.DEP_TIME = "28-Jan-2026 06:00:00 PM"  # Original schedule
        intermediate_stop.DEPARTED = "YES"
        intermediate_stop.TRACK = None
        intermediate_stop.PICKUP = None
        intermediate_stop.DROPOFF = None
        intermediate_stop.STOP_STATUS = "Late"
        intermediate_stop.SCHED_ARR_DATE = None
        intermediate_stop.SCHED_DEP_DATE = None

        api_response = create_stop_list_response(
            train_id="3871",
            line_code="NE",
            destination="Trenton",
            stops=[origin_stop, intermediate_stop],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process the API response
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify origin stop times are normalized correctly
        stmt = select(JourneyStop).where(
            JourneyStop.journey_id == journey.id,
            JourneyStop.station_code == "NY",
        )
        origin_result = await db_session.scalar(stmt)

        assert origin_result is not None

        # scheduled_departure should be TIME (original schedule: 5:24 PM ET)
        # Note: Database stores times in UTC, so we convert to ET for comparison
        assert origin_result.scheduled_departure is not None
        scheduled_et = origin_result.scheduled_departure.astimezone(ET)
        assert scheduled_et.hour == 17
        assert scheduled_et.minute == 24

        # actual_departure should be DEP_TIME (actual: 5:50 PM ET)
        assert origin_result.actual_departure is not None
        actual_et = origin_result.actual_departure.astimezone(ET)
        assert actual_et.hour == 17
        assert actual_et.minute == 50

        # scheduled_arrival should be None (no arrival at origin)
        assert origin_result.scheduled_arrival is None

        # actual_arrival should be None (no arrival at origin)
        assert origin_result.actual_arrival is None

        # Verify delay is POSITIVE (delayed), not negative (early)
        delay_seconds = (
            origin_result.actual_departure - origin_result.scheduled_departure
        ).total_seconds()
        delay_minutes = delay_seconds / 60

        assert delay_minutes == 26, f"Expected +26 min delay, got {delay_minutes}"
        assert delay_minutes > 0, "Delay should be positive (train was late, not early)"

    @pytest.mark.asyncio
    async def test_intermediate_stop_delay_still_works(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Verify intermediate stop delay calculation wasn't broken by the fix."""
        journey = TrainJourney(
            train_id="3871",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Build stops
        origin_stop = MagicMock()
        origin_stop.STATION_2CHAR = "NY"
        origin_stop.STATIONNAME = "New York Penn Station"
        origin_stop.TIME = "28-Jan-2026 05:24:00 PM"
        origin_stop.DEP_TIME = "28-Jan-2026 05:50:00 PM"
        origin_stop.DEPARTED = "YES"
        origin_stop.TRACK = None
        origin_stop.PICKUP = None
        origin_stop.DROPOFF = None
        origin_stop.STOP_STATUS = "BOARDING"
        origin_stop.SCHED_ARR_DATE = None
        origin_stop.SCHED_DEP_DATE = None

        intermediate_stop = MagicMock()
        intermediate_stop.STATION_2CHAR = "SE"
        intermediate_stop.STATIONNAME = "Secaucus Upper Lvl"
        intermediate_stop.TIME = (
            "28-Jan-2026 06:42:30 PM"  # Actual (delayed by ~42 min)
        )
        intermediate_stop.DEP_TIME = "28-Jan-2026 06:00:00 PM"  # Original schedule
        intermediate_stop.DEPARTED = "YES"
        intermediate_stop.TRACK = None
        intermediate_stop.PICKUP = None
        intermediate_stop.DROPOFF = None
        intermediate_stop.STOP_STATUS = "Late"
        intermediate_stop.SCHED_ARR_DATE = None
        intermediate_stop.SCHED_DEP_DATE = None

        api_response = create_stop_list_response(
            train_id="3871",
            line_code="NE",
            destination="Trenton",
            stops=[origin_stop, intermediate_stop],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify intermediate stop
        stmt = select(JourneyStop).where(
            JourneyStop.journey_id == journey.id,
            JourneyStop.station_code == "SE",
        )
        secaucus = await db_session.scalar(stmt)

        assert secaucus is not None

        # scheduled_departure should be DEP_TIME (6:00 PM ET)
        # Note: Database stores times in UTC, so we convert to ET for comparison
        scheduled_et = secaucus.scheduled_departure.astimezone(ET)
        assert scheduled_et.hour == 18
        assert scheduled_et.minute == 0

        # actual_departure should be TIME (6:42:30 PM ET)
        actual_et = secaucus.actual_departure.astimezone(ET)
        assert actual_et.hour == 18
        assert actual_et.minute == 42

        # Delay should be ~42 minutes
        delay_seconds = (
            secaucus.actual_departure - secaucus.scheduled_departure
        ).total_seconds()
        delay_minutes = delay_seconds / 60

        assert 42 <= delay_minutes <= 43, f"Expected ~42 min delay, got {delay_minutes}"

    @pytest.mark.asyncio
    async def test_on_time_train_from_origin(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that an on-time train from origin shows zero delay."""
        journey = TrainJourney(
            train_id="3875",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # On-time train: TIME == DEP_TIME at origin
        origin_stop = MagicMock()
        origin_stop.STATION_2CHAR = "NY"
        origin_stop.STATIONNAME = "New York Penn Station"
        origin_stop.TIME = "28-Jan-2026 06:47:00 PM"
        origin_stop.DEP_TIME = "28-Jan-2026 06:47:00 PM"  # Same as TIME
        origin_stop.DEPARTED = "YES"
        origin_stop.TRACK = "5"
        origin_stop.PICKUP = None
        origin_stop.DROPOFF = None
        origin_stop.STOP_STATUS = "BOARDING"
        origin_stop.SCHED_ARR_DATE = None
        origin_stop.SCHED_DEP_DATE = None

        api_response = create_stop_list_response(
            train_id="3875",
            line_code="NE",
            destination="Trenton",
            stops=[origin_stop],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        stmt = select(JourneyStop).where(
            JourneyStop.journey_id == journey.id,
            JourneyStop.station_code == "NY",
        )
        origin_result = await db_session.scalar(stmt)

        # Both should be 6:47 PM
        assert origin_result.scheduled_departure == origin_result.actual_departure

        # Zero delay
        delay = (
            origin_result.actual_departure - origin_result.scheduled_departure
        ).total_seconds()
        assert delay == 0

    @pytest.mark.asyncio
    async def test_train_not_yet_departed_from_origin(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that a train not yet departed has no actual_departure."""
        # Use future times to ensure time-based inference doesn't trigger
        # (Tier 3 inference triggers when scheduled_departure < now - 5 minutes)
        future_scheduled = now_et() + timedelta(hours=1)
        future_actual = future_scheduled + timedelta(minutes=11)

        journey = TrainJourney(
            train_id="3880",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",  # Trenton origin
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=future_scheduled,
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Format times in NJT API format (e.g., "28-Jan-2026 08:31:00 PM")
        time_str = future_scheduled.strftime("%d-%b-%Y %I:%M:%S %p")
        dep_time_str = future_actual.strftime("%d-%b-%Y %I:%M:%S %p")

        origin_stop = MagicMock()
        origin_stop.STATION_2CHAR = "TR"
        origin_stop.STATIONNAME = "Trenton"
        origin_stop.TIME = time_str  # Scheduled departure (future)
        origin_stop.DEP_TIME = dep_time_str  # Actual departure time (future)
        origin_stop.DEPARTED = "NO"  # Not yet departed
        origin_stop.TRACK = "1"
        origin_stop.PICKUP = None
        origin_stop.DROPOFF = None
        origin_stop.STOP_STATUS = "ON TIME"
        origin_stop.SCHED_ARR_DATE = None
        origin_stop.SCHED_DEP_DATE = None

        api_response = create_stop_list_response(
            train_id="3880",
            line_code="NE",
            destination="New York",
            stops=[origin_stop],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        stmt = select(JourneyStop).where(
            JourneyStop.journey_id == journey.id,
            JourneyStop.station_code == "TR",
        )
        origin_result = await db_session.scalar(stmt)

        # scheduled_departure should be set from TIME field
        assert origin_result.scheduled_departure is not None
        scheduled_et = origin_result.scheduled_departure.astimezone(ET)
        assert scheduled_et.hour == future_scheduled.hour
        assert scheduled_et.minute == future_scheduled.minute

        # actual_departure should be None (not departed yet)
        assert origin_result.actual_departure is None
        assert origin_result.has_departed_station is False
