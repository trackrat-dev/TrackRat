"""
Unit tests for journey stop sequence fixes.

Tests phantom stop deletion and SQLAlchemy dirty tracking to prevent
the bug where Trenton appears after Hamilton due to duplicate stop_sequence values.
"""

import itertools
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.njt_api_responses import (
    StopBuilder,
    create_schedule_less_secaucus_response,
    create_stop_list_response,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et, parse_njt_time


@pytest.fixture
def mock_njt_client():
    """Mock NJ Transit client."""
    client = AsyncMock(spec=NJTransitClient)
    return client


@pytest.fixture
def journey_collector(mock_njt_client):
    """Create journey collector with mocked client."""
    return JourneyCollector(mock_njt_client)


class TestPhantomStopDeletion:
    """Test phantom stop deletion when API response doesn't include schedule-generated stops."""

    @pytest.mark.asyncio
    async def test_deletes_phantom_trenton_stop_when_not_in_api_response(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that phantom Trenton stop is deleted when API doesn't include it.

        This replicates the bug: schedule generation creates TR stop with sequence=0,
        but actual train starts at Hamilton. The phantom TR stop should be deleted.
        """
        # Create a journey in the database
        journey = TrainJourney(
            train_id="3924",
            journey_date=date.today(),
            line_code="NE",  # 2-char code for Northeast Corridor
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="HL",  # Hamilton is the actual origin
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create phantom Trenton stop (from schedule generation)
        phantom_stop = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",  # Trenton
            station_name="Trenton",
            stop_sequence=0,  # BUG: This conflicts with real first stop
            scheduled_departure=now_et(),
        )
        db_session.add(phantom_stop)
        await db_session.flush()

        # Create API response WITHOUT Trenton (train starts at Hamilton)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3924",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop("HL", "Hamilton", "11:18:00 AM", departed=False),
                builder.build_stop(
                    "PJ", "Princeton Jct", "11:26:00 AM", departed=False
                ),
                builder.build_stop("NY", "New York", "12:00:00 PM", departed=False),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process the API response (should delete phantom TR stop)
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify phantom stop was deleted
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        all_stops = (await db_session.scalars(stmt)).all()

        station_codes = [stop.station_code for stop in all_stops]
        assert "TR" not in station_codes, "Phantom Trenton stop should be deleted"
        assert station_codes == [
            "HL",
            "PJ",
            "NY",
        ], f"Expected HL, PJ, NY but got {station_codes}"

    @pytest.mark.asyncio
    async def test_preserves_all_stops_when_api_includes_them(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that legitimate stops are preserved when API includes them."""
        # Create a journey
        journey = TrainJourney(
            train_id="3932",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create Trenton stop (legitimate, not phantom)
        # Use scheduled_departure=None so it gets updated from API data
        # (The code only updates scheduled times when they're currently None)
        tr_stop = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=0,
            scheduled_departure=None,
        )
        db_session.add(tr_stop)
        await db_session.flush()

        # Create API response that INCLUDES Trenton
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3932",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop("TR", "Trenton", "11:11:00 AM", departed=False),
                builder.build_stop("HL", "Hamilton", "11:18:00 AM", departed=False),
                builder.build_stop(
                    "PJ", "Princeton Jct", "11:26:00 AM", departed=False
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process the API response
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify all stops are preserved
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        all_stops = (await db_session.scalars(stmt)).all()

        station_codes = [stop.station_code for stop in all_stops]
        assert "TR" in station_codes, "Legitimate Trenton stop should be preserved"
        assert station_codes == [
            "TR",
            "HL",
            "PJ",
        ], f"Expected TR, HL, PJ but got {station_codes}"

    @pytest.mark.asyncio
    async def test_deletes_multiple_phantom_stops(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test deletion of multiple phantom stops in one operation."""
        # Create a journey
        journey = TrainJourney(
            train_id="3954",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="PJ",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create multiple phantom stops
        for station in ["TR", "HL"]:
            phantom = JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code=station,
                station_name=station,
                stop_sequence=0,
                scheduled_departure=now_et(),
            )
            db_session.add(phantom)
        await db_session.flush()

        # API response starts at Princeton Junction
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3954",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop(
                    "PJ", "Princeton Jct", "11:26:00 AM", departed=False
                ),
                builder.build_stop(
                    "NB", "New Brunswick", "11:35:00 AM", departed=False
                ),
                builder.build_stop("NY", "New York", "12:00:00 PM", departed=False),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process the API response
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify both phantom stops were deleted
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        all_stops = (await db_session.scalars(stmt)).all()

        station_codes = [stop.station_code for stop in all_stops]
        assert "TR" not in station_codes, "Phantom TR should be deleted"
        assert "HL" not in station_codes, "Phantom HL should be deleted"
        assert station_codes == [
            "PJ",
            "NB",
            "NY",
        ], f"Expected PJ, NB, NY but got {station_codes}"


class TestStopSequenceReordering:
    """Test stop sequence reordering and duplicate prevention."""

    @pytest.mark.asyncio
    async def test_correctly_resequences_stops_after_phantom_deletion(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that stops get correct sequences after phantom stop deletion."""
        # Create journey
        journey = TrainJourney(
            train_id="3956",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="HL",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create phantom TR with sequence=0
        phantom = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=0,
            scheduled_departure=now_et(),
        )
        db_session.add(phantom)
        await db_session.flush()

        # API response
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3956",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop("HL", "Hamilton", "11:18:00 AM", departed=False),
                builder.build_stop(
                    "PJ", "Princeton Jct", "11:26:00 AM", departed=False
                ),
                builder.build_stop("NY", "New York", "12:00:00 PM", departed=False),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify sequences are correct
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        # Check sequences are 0, 1, 2
        sequences = [stop.stop_sequence for stop in stops]
        assert sequences == [0, 1, 2], f"Expected [0, 1, 2] but got {sequences}"

        # Check no duplicates
        assert len(sequences) == len(
            set(sequences)
        ), "Found duplicate stop_sequence values"

        # Check first stop is Hamilton (not Trenton)
        assert stops[0].station_code == "HL", "First stop should be Hamilton"

    @pytest.mark.asyncio
    async def test_no_duplicate_sequences_after_update(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that no duplicate stop_sequence values exist after processing."""
        # Create journey with problematic setup
        journey = TrainJourney(
            train_id="3958",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create stops with duplicate sequences (simulating the bug)
        for station, seq in [("TR", 0), ("HL", 0), ("PJ", 2)]:
            stop = JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code=station,
                station_name=station,
                stop_sequence=seq,
                scheduled_departure=now_et(),
            )
            db_session.add(stop)
        await db_session.flush()

        # API response with correct order
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3958",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop("TR", "Trenton", "11:11:00 AM", departed=False),
                builder.build_stop("HL", "Hamilton", "11:18:00 AM", departed=False),
                builder.build_stop(
                    "PJ", "Princeton Jct", "11:26:00 AM", departed=False
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Verify no duplicates
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        sequences = [stop.stop_sequence for stop in stops]
        assert len(sequences) == len(
            set(sequences)
        ), f"Found duplicate sequences: {sequences}"
        assert sequences == [0, 1, 2], f"Expected [0, 1, 2] but got {sequences}"


class TestSQLAlchemyDirtyTracking:
    """Test that SQLAlchemy properly tracks stop_sequence modifications."""

    @pytest.mark.asyncio
    async def test_stop_sequence_persists_even_when_unchanged(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that assigning the same stop_sequence value still persists (dirty tracking)."""
        # Create journey
        journey = TrainJourney(
            train_id="3960",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create stop with sequence=0
        stop = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=0,
            scheduled_departure=now_et(),
        )
        db_session.add(stop)
        await db_session.flush()

        # API response with same stop (should keep sequence=0)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3960",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop("TR", "Trenton", "11:11:00 AM", departed=False),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process (should assign sequence=0 again with flag_modified)
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()
        await db_session.refresh(stop)

        # Verify sequence is still 0 and persisted correctly
        assert stop.stop_sequence == 0, "Stop sequence should remain 0"

        # Query fresh from database to ensure persistence
        stmt = select(JourneyStop).where(
            JourneyStop.journey_id == journey.id, JourneyStop.station_code == "TR"
        )
        fresh_stop = await db_session.scalar(stmt)
        assert fresh_stop is not None
        assert fresh_stop.stop_sequence == 0, "Stop sequence should persist in database"


class TestCorruptedTimeDataHandling:
    """Test handling of corrupted NJT time data where departure < arrival.

    This tests the fix for train 7840 bug where Trenton showed after Hamilton
    because NJT API returned corrupted data:
    - Trenton: scheduled_arrival=2:08 PM, scheduled_departure=1:58 PM (impossible!)
    - Hamilton: scheduled_arrival=2:03 PM, scheduled_departure=2:04 PM (correct)

    The old logic used `scheduled_arrival or scheduled_departure`, so Trenton (2:08)
    sorted after Hamilton (2:03). The fix uses min(arrival, departure) so Trenton (1:58)
    correctly sorts before Hamilton (2:03).
    """

    @pytest.mark.asyncio
    async def test_corrupted_times_sorted_by_min(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that stops with corrupted times (departure < arrival) sort correctly.

        Simulates the train 7840 bug: Trenton should come before Hamilton,
        but corrupted arrival time would place it after if using arrival-first logic.
        """

        # Create journey
        journey = TrainJourney(
            train_id="7840",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create stops with corrupted Trenton data (mimics the real bug)
        # Trenton: departure 1:58 PM < arrival 2:08 PM (CORRUPTED - impossible!)
        trenton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=1,  # Wrong sequence due to previous bug
            scheduled_arrival=datetime(
                2024, 1, 1, 19, 8, 0, tzinfo=UTC
            ),  # 2:08 PM ET (WRONG)
            scheduled_departure=datetime(
                2024, 1, 1, 18, 58, 0, tzinfo=UTC
            ),  # 1:58 PM ET (correct)
        )
        db_session.add(trenton)

        # Hamilton: normal data (departure > arrival)
        hamilton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="HL",
            station_name="Hamilton",
            stop_sequence=0,  # Wrong sequence due to previous bug
            scheduled_arrival=datetime(
                2024, 1, 1, 19, 3, 30, tzinfo=UTC
            ),  # 2:03:30 PM ET
            scheduled_departure=datetime(
                2024, 1, 1, 19, 4, 30, tzinfo=UTC
            ),  # 2:04:30 PM ET
        )
        db_session.add(hamilton)

        # Princeton Junction: normal data
        princeton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="PJ",
            station_name="Princeton Junction",
            stop_sequence=2,
            scheduled_arrival=datetime(
                2024, 1, 1, 19, 24, 44, tzinfo=UTC
            ),  # 2:24:44 PM ET
            scheduled_departure=datetime(
                2024, 1, 1, 19, 11, 30, tzinfo=UTC
            ),  # 2:11:30 PM ET
        )
        db_session.add(princeton)
        await db_session.flush()

        # Run resequencing (this is what we're testing)
        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        # Verify correct order: Trenton (1:58) -> Hamilton (2:03) -> Princeton (2:11)
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert station_codes == ["TR", "HL", "PJ"], (
            f"Expected Trenton before Hamilton due to min() logic, "
            f"but got {station_codes}"
        )

        # Verify sequences are correct
        sequences = [s.stop_sequence for s in stops]
        assert sequences == [0, 1, 2], f"Expected [0, 1, 2] but got {sequences}"

    @pytest.mark.asyncio
    async def test_normal_times_still_sort_correctly(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that normal stops (departure >= arrival) still sort correctly.

        Ensures the min() fix doesn't break normal cases where arrival < departure.
        """

        # Create journey
        journey = TrainJourney(
            train_id="3924",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # All stops have normal times (arrival < departure)
        stops_data = [
            (
                "TR",
                "Trenton",
                datetime(2024, 1, 1, 18, 55, 0),
                datetime(2024, 1, 1, 18, 58, 0),
            ),
            (
                "HL",
                "Hamilton",
                datetime(2024, 1, 1, 19, 3, 0),
                datetime(2024, 1, 1, 19, 5, 0),
            ),
            (
                "PJ",
                "Princeton Junction",
                datetime(2024, 1, 1, 19, 15, 0),
                datetime(2024, 1, 1, 19, 17, 0),
            ),
        ]

        for i, (code, name, arr, dep) in enumerate(stops_data):
            stop = JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code=code,
                station_name=name,
                stop_sequence=2 - i,  # Reverse order to test sorting
                scheduled_arrival=arr.replace(tzinfo=UTC),
                scheduled_departure=dep.replace(tzinfo=UTC),
            )
            db_session.add(stop)
        await db_session.flush()

        # Run resequencing
        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        # Verify correct order based on arrival times
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "TR",
            "HL",
            "PJ",
        ], f"Expected normal order TR -> HL -> PJ, but got {station_codes}"

    @pytest.mark.asyncio
    async def test_origin_station_with_departure_only(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that origin stations with only departure time sort correctly."""

        # Create journey
        journey = TrainJourney(
            train_id="3926",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Origin station with departure only (no arrival)
        trenton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=1,
            scheduled_arrival=None,  # Origin has no arrival
            scheduled_departure=datetime(2024, 1, 1, 18, 58, 0, tzinfo=UTC),
        )
        db_session.add(trenton)

        # Next stop with both times
        hamilton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="HL",
            station_name="Hamilton",
            stop_sequence=0,
            scheduled_arrival=datetime(2024, 1, 1, 19, 5, 0, tzinfo=UTC),
            scheduled_departure=datetime(2024, 1, 1, 19, 7, 0, tzinfo=UTC),
        )
        db_session.add(hamilton)
        await db_session.flush()

        # Run resequencing
        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        # Verify Trenton (departure 18:58) comes before Hamilton (arrival 19:05)
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "TR",
            "HL",
        ], f"Expected TR before HL, but got {station_codes}"

    @pytest.mark.asyncio
    async def test_terminal_station_with_arrival_only(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that terminal stations with only arrival time sort correctly."""

        # Create journey
        journey = TrainJourney(
            train_id="3928",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # First stop
        trenton = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=1,
            scheduled_arrival=datetime(2024, 1, 1, 18, 55, 0, tzinfo=UTC),
            scheduled_departure=datetime(2024, 1, 1, 18, 58, 0, tzinfo=UTC),
        )
        db_session.add(trenton)

        # Terminal station with arrival only (no departure)
        ny_penn = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_arrival=datetime(2024, 1, 1, 19, 45, 0, tzinfo=UTC),
            scheduled_departure=None,  # Terminal has no departure
        )
        db_session.add(ny_penn)
        await db_session.flush()

        # Run resequencing
        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        # Verify Trenton (18:55) comes before NY (19:45)
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "TR",
            "NY",
        ], f"Expected TR before NY, but got {station_codes}"

    @pytest.mark.asyncio
    async def test_discovery_stop_with_only_updated_times_sorts_by_live_time(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Discovery-populated stops (updated_* only, no scheduled_*) sort by live time.

        Replicates issue #1530: NJT train 3701 (NY -> MP) showed Newark Penn before
        Secaucus. Secaucus was added by the discovery phase, so it had only
        updated_arrival / updated_departure and no scheduled_* times. Previously it
        was bucketed after all scheduled stops (DATETIME_MAX_ET) and rendered out of
        order. It must instead sort by its live time into NY -> SE -> NP.
        """

        journey = TrainJourney(
            train_id="3701",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Matawan",
            origin_station_code="NY",
            terminal_station_code="MP",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Origin: New York Penn, departure only (scheduled).
        ny_penn = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_arrival=None,
            scheduled_departure=datetime(2024, 1, 1, 18, 0, 0, tzinfo=UTC),
        )
        db_session.add(ny_penn)

        # Newark Penn: fully scheduled downstream stop.
        newark = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_arrival=datetime(2024, 1, 1, 18, 18, 0, tzinfo=UTC),
            scheduled_departure=datetime(2024, 1, 1, 18, 20, 0, tzinfo=UTC),
        )
        db_session.add(newark)

        # Secaucus: discovery-populated, only live (updated) times, no schedule and
        # no assigned sequence. Its live time (18:08) is between NY and Newark.
        secaucus = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="SE",
            station_name="Secaucus Junction",
            stop_sequence=None,
            scheduled_arrival=None,
            scheduled_departure=None,
            updated_arrival=datetime(2024, 1, 1, 18, 8, 0, tzinfo=UTC),
            updated_departure=datetime(2024, 1, 1, 18, 9, 0, tzinfo=UTC),
        )
        db_session.add(secaucus)
        await db_session.flush()

        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "NY",
            "SE",
            "NP",
        ], f"Expected NY -> SE -> NP, but got {station_codes}"

    @pytest.mark.asyncio
    async def test_schedule_less_stop_with_early_live_time_cannot_displace_origin(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """A schedule-less stop with an implausibly early live time keeps origin at 0.

        Hardening for issue #1535 (follow-up to the #1530 updated_* fallback).
        The #1530 fallback sorts a schedule-less stop by its earliest live time
        so a discovery-populated stop (e.g. Secaucus) lands in its geographic
        slot. But without a lower bound, a stale or bogus live TIME earlier than
        the origin's scheduled departure would sort the schedule-less stop to
        sequence 0, displacing the origin.

        Here the origin NY departs at 18:00 (scheduled) and a schedule-less stop
        carries updated_arrival 17:45 — before the origin. The fallback must be
        discarded for that stop (its live time is outside the journey's
        scheduled window), so NY stays at sequence 0 and the bogus stop falls to
        the end instead of occupying position 0.
        """

        journey = TrainJourney(
            train_id="3703",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Matawan",
            origin_station_code="NY",
            terminal_station_code="MP",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Origin: New York Penn, scheduled departure 18:00.
        ny_penn = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_arrival=None,
            scheduled_departure=datetime(2024, 1, 1, 18, 0, 0, tzinfo=UTC),
        )
        db_session.add(ny_penn)

        # Newark Penn: fully scheduled downstream stop.
        newark = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_arrival=datetime(2024, 1, 1, 18, 18, 0, tzinfo=UTC),
            scheduled_departure=datetime(2024, 1, 1, 18, 20, 0, tzinfo=UTC),
        )
        db_session.add(newark)

        # Schedule-less stop whose only live time (17:45) is BEFORE the origin's
        # scheduled departure (18:00). This is the #1535 hazard: an implausibly
        # early live time. It must not sort ahead of the origin.
        bogus = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="SE",
            station_name="Secaucus Junction",
            stop_sequence=None,
            scheduled_arrival=None,
            scheduled_departure=None,
            updated_arrival=datetime(2024, 1, 1, 17, 45, 0, tzinfo=UTC),
            updated_departure=None,
        )
        db_session.add(bogus)
        await db_session.flush()

        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        # The origin must stay first; the schedule-less early-live-time stop must
        # fall to the end rather than occupy sequence 0.
        assert station_codes[0] == "NY", (
            "Origin NY must remain at sequence 0; a schedule-less stop with a "
            f"live time before the origin must not displace it. Got {station_codes}"
        )
        assert station_codes == [
            "NY",
            "NP",
            "SE",
        ], f"Expected NY -> NP -> SE (bogus stop bucketed last), got {station_codes}"

        # Sequences must remain a clean 0..N-1 with no duplicates.
        sequences = [s.stop_sequence for s in stops]
        assert sequences == [0, 1, 2], f"Expected [0, 1, 2], got {sequences}"
        assert len(sequences) == len(
            set(sequences)
        ), f"Found duplicate stop_sequence values: {sequences}"

    @pytest.mark.asyncio
    async def test_sequential_inference_with_skipped_departed_flag(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test that sequential inference marks skipped stops as departed.

        This replicates the train 7840 / Princeton Junction bug:
        - NJT API returns DEPARTED=NO for PJ, but DEPARTED=YES for NB (later stop)
        - The sequential inference should mark PJ as departed because a later stop departed
        - The fix sorts stops by time BEFORE inference to ensure correct index order
        """
        # Create journey
        journey = TrainJourney(
            train_id="7840",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create API response simulating the real bug:
        # - Stops have corrupted times (dep_time < arr_time for intermediate stops)
        # - PJ has DEPARTED=NO, but NB has DEPARTED=YES
        # - The API might return stops in wrong order due to corrupted times
        builder = StopBuilder()

        # Note: We intentionally create stops with corrupted times AND out of order
        # to test that the sort-before-inference fix works correctly.
        # In the real bug, PJ was not marked departed because:
        # 1. Its DEPARTED flag was NO
        # 2. Sequential inference failed because stops weren't in geographic order
        api_response = create_stop_list_response(
            train_id="7840",
            line_code="NE",
            destination="New York",
            stops=[
                # TR: normal origin (departed)
                builder.build_stop(
                    "TR",
                    "Trenton",
                    "01:58:00 PM",
                    arr_time="02:08:00 PM",
                    departed=True,
                ),
                # HL: normal stop (departed)
                builder.build_stop(
                    "HL",
                    "Hamilton",
                    "02:04:00 PM",
                    arr_time="02:03:00 PM",
                    departed=True,
                ),
                # PJ: THE BUG - DEPARTED=NO but should be inferred from NB
                # Also has corrupted times (dep < arr)
                builder.build_stop(
                    "PJ",
                    "Princeton Jct",
                    "02:11:00 PM",  # DEP_TIME
                    arr_time="02:24:00 PM",  # TIME - corrupted, later than dep!
                    departed=False,  # BUG: NJT didn't set this
                ),
                # NB: departed (proves PJ must have been passed)
                builder.build_stop(
                    "NB",
                    "New Brunswick",
                    "02:27:00 PM",
                    arr_time="02:39:00 PM",
                    departed=True,
                ),
                # NY: not yet departed (terminal)
                builder.build_stop(
                    "NY",
                    "New York",
                    "03:00:00 PM",
                    arr_time="03:00:00 PM",
                    departed=False,
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process the API response - this should:
        # 1. Sort stops by min(TIME, DEP_TIME) to get geographic order
        # 2. Calculate max_departed_sequence from NB (or later departed stop)
        # 3. Apply sequential inference to mark PJ as departed
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Query stops and check has_departed_station
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        # Create a dict for easy lookup
        stops_by_code = {s.station_code: s for s in stops}

        # Verify PJ was marked as departed via sequential inference
        pj_stop = stops_by_code.get("PJ")
        assert pj_stop is not None, "PJ stop should exist"
        assert pj_stop.has_departed_station is True, (
            f"PJ should be marked as departed via sequential inference, "
            f"but has_departed_station={pj_stop.has_departed_station}, "
            f"departure_source={pj_stop.departure_source}"
        )
        assert pj_stop.departure_source == "sequential_inference", (
            f"PJ departure_source should be 'sequential_inference', "
            f"but got '{pj_stop.departure_source}'"
        )

        # Verify other stops have correct departure status
        assert stops_by_code["TR"].has_departed_station is True
        assert stops_by_code["HL"].has_departed_station is True
        assert stops_by_code["NB"].has_departed_station is True
        # NY might or might not be departed depending on time - just check it exists
        assert "NY" in stops_by_code

    @pytest.mark.asyncio
    async def test_sequential_inference_with_reversed_api_order(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Test sequential inference when API returns stops in completely wrong order.

        This tests the extreme case where NJT API returns stops sorted by
        arrival time (which can be corrupted), resulting in wrong geographic order.
        The sort-before-inference fix should handle this.
        """
        # Create journey
        journey = TrainJourney(
            train_id="9999",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Create API response with stops in WRONG order (by arrival time)
        # Geographic order should be: TR -> HL -> PJ -> NB
        # But we'll provide them sorted by corrupted arrival times
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="9999",
            line_code="NE",
            destination="New York",
            stops=[
                # API returns in wrong order due to sorting by arrival time
                # HL arrives at 02:03 (earliest arrival)
                builder.build_stop(
                    "HL",
                    "Hamilton",
                    "02:04:00 PM",
                    arr_time="02:03:00 PM",
                    departed=True,
                ),
                # TR arrives at 02:08 (but departs at 01:58 - it's the origin!)
                builder.build_stop(
                    "TR",
                    "Trenton",
                    "01:58:00 PM",
                    arr_time="02:08:00 PM",
                    departed=True,
                ),
                # PJ arrives at 02:24 - DEPARTED=NO (the bug)
                builder.build_stop(
                    "PJ",
                    "Princeton Jct",
                    "02:11:00 PM",
                    arr_time="02:24:00 PM",
                    departed=False,
                ),
                # NB arrives at 02:39 - DEPARTED=YES
                builder.build_stop(
                    "NB",
                    "New Brunswick",
                    "02:27:00 PM",
                    arr_time="02:39:00 PM",
                    departed=True,
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        # Process - the sort should reorder to: TR, HL, PJ, NB (by min time)
        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        # Query and verify
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()
        stops_by_code = {s.station_code: s for s in stops}

        # PJ should be marked departed via sequential inference
        pj_stop = stops_by_code.get("PJ")
        assert pj_stop is not None
        assert (
            pj_stop.has_departed_station is True
        ), "PJ should be departed via sequential inference even with wrong API order"

        # Verify correct sequence order (sorted by min departure time)
        # TR: min(01:58, 02:08) = 01:58
        # HL: min(02:04, 02:03) = 02:03
        # PJ: min(02:11, 02:24) = 02:11
        # NB: min(02:27, 02:39) = 02:27
        # Expected order by min time: TR (01:58) -> HL (02:03) -> PJ (02:11) -> NB (02:27)
        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "TR",
            "HL",
            "PJ",
            "NB",
        ], f"Expected TR, HL, PJ, NB order after sorting by min time, got {station_codes}"


class TestScheduleLessStopProductionPath:
    """Production-path regression tests for schedule-less NJT stops (issue #1533).

    The direct ``_resequence_stops`` unit test
    (``test_discovery_stop_with_only_updated_times_sorts_by_live_time``) seeds a
    Secaucus stop with BOTH ``updated_arrival`` and ``updated_departure``. That
    state cannot reach ``_resequence_stops`` in production: the enclosing
    ``update_journey_stops`` pass first overwrites both fields from the current
    getTrainStopList row (``updated_arrival = TIME``, ``updated_departure =
    DEP_TIME``). The real #1530 trigger is an API row carrying **TIME only** —
    at resequence time the stop then has ``updated_arrival`` only and no
    ``scheduled_*`` times.

    These tests drive the full ``update_journey_stops`` pass (overwrite ->
    backfill -> phantom deletion -> resequence -> ``_validate_stop_sequences``)
    so the #1530 fix is exercised on the path that actually produced the bug,
    and cover the adjacent interplay cases (backfill when the API supplies a
    schedule, phantom deletion when the discovery stop is absent from the API).
    """

    async def _seed_ny_mp_journey(self, db_session: AsyncSession) -> TrainJourney:
        """Seed the #1530 journey: train 3701 NY -> Matawan.

        Pre-creates the schedule-generated stops (NY origin, Newark Penn,
        Matawan terminal) with full scheduled times, plus a discovery-populated
        Secaucus stop that has only live (updated) times and no schedule — the
        state that produced the bug. All times use ``parse_njt_time`` so they
        share today's date/timezone with the API-parsed stop-list times the
        tests feed in (a mismatched date would silently break the ordering the
        tests assert).
        """
        journey = TrainJourney(
            train_id="3701",
            journey_date=date.today(),
            line_code="NC",
            line_name="North Jersey Coast",
            destination="Matawan",
            origin_station_code="NY",
            terminal_station_code="MP",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Origin: New York Penn — departure only (scheduled).
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="NY",
                station_name="New York Penn Station",
                stop_sequence=0,
                scheduled_arrival=None,
                scheduled_departure=parse_njt_time("06:00:00 PM"),
            )
        )
        # Newark Penn — fully scheduled downstream stop.
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="NP",
                station_name="Newark Penn Station",
                stop_sequence=1,
                scheduled_arrival=parse_njt_time("06:18:00 PM"),
                scheduled_departure=parse_njt_time("06:20:00 PM"),
            )
        )
        # Matawan — terminal, arrival only.
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="MP",
                station_name="Matawan Station",
                stop_sequence=2,
                scheduled_arrival=parse_njt_time("06:55:00 PM"),
                scheduled_departure=None,
            )
        )
        # Secaucus — discovery-populated: live (updated) times only, no
        # schedule, no assigned sequence. Discovery wrote BOTH updated fields;
        # the collection pass will overwrite them from the API row.
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="SE",
                station_name="Secaucus Junction",
                stop_sequence=None,
                scheduled_arrival=None,
                scheduled_departure=None,
                updated_arrival=parse_njt_time("06:05:00 PM"),
                updated_departure=parse_njt_time("06:06:00 PM"),
            )
        )
        await db_session.flush()
        return journey

    @pytest.mark.asyncio
    async def test_time_only_intermediate_stop_orders_via_update_journey_stops(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Full pass: a TIME-only Secaucus row must land in NY -> SE -> NP -> MP.

        This is the #1530 regression guard on the production path. It fails if
        the ``updated_*`` fallback in ``_resequence_stops.get_sort_key`` is
        reverted — without it, schedule-less Secaucus is bucketed to
        DATETIME_MAX_ET and persists AFTER Newark Penn (NY -> NP -> MP -> SE),
        the exact reported bug — yet it never calls ``_resequence_stops``
        directly.
        """
        journey = await self._seed_ny_mp_journey(db_session)

        api_response = create_schedule_less_secaucus_response(train_id="3701")
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()
        stops_by_code = {s.station_code: s for s in stops}

        station_codes = [s.station_code for s in stops]
        assert station_codes == ["NY", "SE", "NP", "MP"], (
            "TIME-only Secaucus must sort by its live time between NY and NP, "
            f"but persisted order was {station_codes}"
        )

        # Sequences must be a clean 0..N-1 with no duplicates.
        sequences = [s.stop_sequence for s in stops]
        assert sequences == [0, 1, 2, 3], f"Expected [0, 1, 2, 3], got {sequences}"
        assert len(sequences) == len(
            set(sequences)
        ), f"Found duplicate stop_sequence values: {sequences}"

        # Secaucus is the real production state, distinct from the direct unit
        # test: schedule-less, and its discovery-written updated_departure was
        # zeroed by the overwrite of the DEP_TIME-less API row.
        secaucus = stops_by_code["SE"]
        assert secaucus.scheduled_arrival is None, (
            "Secaucus must remain schedule-less (no scheduled_arrival) — this is "
            "what makes the resequencing fallback the code under test."
        )
        assert (
            secaucus.scheduled_departure is None
        ), "Secaucus must remain schedule-less (no scheduled_departure)."
        assert secaucus.updated_departure is None, (
            "The DEP_TIME-less API row must overwrite the discovery-written "
            "updated_departure to None — proving this path differs from the "
            "direct _resequence_stops unit test."
        )
        assert secaucus.updated_arrival == parse_njt_time("06:08:00 PM"), (
            "Secaucus updated_arrival must be overwritten to the live TIME "
            f"(06:08 PM), got {secaucus.updated_arrival}"
        )

    @pytest.mark.asyncio
    async def test_discovery_stop_backfilled_when_api_supplies_schedule(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Adjacent case: a later API row that carries a schedule backfills it.

        A discovery-populated (schedule-less) Secaucus whose collection-time API
        row supplies SCHED_DEP_DATE must have ``scheduled_departure`` backfilled
        and then sort by that immutable schedule, still landing NY -> SE -> NP.
        """
        journey = await self._seed_ny_mp_journey(db_session)

        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3701",
            line_code="NC",
            destination="Matawan",
            stops=[
                builder.build_stop(
                    "NY",
                    "New York Penn",
                    "06:00:00 PM",
                    departed=True,
                    sched_dep_date="06:00:00 PM",
                ),
                # Secaucus now carries an immutable schedule (SCHED_DEP_DATE).
                builder.build_stop(
                    "SE",
                    "Secaucus Junction",
                    "06:09:00 PM",
                    arr_time="06:08:00 PM",
                    departed=False,
                    sched_dep_date="06:07:00 PM",
                ),
                builder.build_stop(
                    "NP",
                    "Newark Penn",
                    "06:20:00 PM",
                    arr_time="06:18:00 PM",
                    departed=False,
                    sched_dep_date="06:20:00 PM",
                ),
                builder.build_stop(
                    "MP",
                    "Matawan",
                    None,
                    arr_time="06:55:00 PM",
                    departed=False,
                    sched_dep_date="06:55:00 PM",
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()
        stops_by_code = {s.station_code: s for s in stops}

        station_codes = [s.station_code for s in stops]
        assert station_codes == [
            "NY",
            "SE",
            "NP",
            "MP",
        ], f"Backfilled Secaucus must order correctly, got {station_codes}"
        assert stops_by_code["SE"].scheduled_departure == parse_njt_time(
            "06:07:00 PM"
        ), (
            "Secaucus scheduled_departure must be backfilled from SCHED_DEP_DATE, "
            f"got {stops_by_code['SE'].scheduled_departure}"
        )

    @pytest.mark.asyncio
    async def test_discovery_stop_phantom_deleted_when_absent_from_api(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """Adjacent case: a discovery stop absent from the API is phantom-deleted.

        If the collection-time stop list omits the discovery-populated Secaucus,
        it is a phantom placeholder and must be removed, leaving NY -> NP -> MP.
        """
        journey = await self._seed_ny_mp_journey(db_session)

        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id="3701",
            line_code="NC",
            destination="Matawan",
            stops=[
                builder.build_stop(
                    "NY",
                    "New York Penn",
                    "06:00:00 PM",
                    departed=True,
                    sched_dep_date="06:00:00 PM",
                ),
                builder.build_stop(
                    "NP",
                    "Newark Penn",
                    "06:20:00 PM",
                    arr_time="06:18:00 PM",
                    departed=False,
                    sched_dep_date="06:20:00 PM",
                ),
                builder.build_stop(
                    "MP",
                    "Matawan",
                    None,
                    arr_time="06:55:00 PM",
                    departed=False,
                    sched_dep_date="06:55:00 PM",
                ),
            ],
        )
        mock_njt_client.get_train_stop_list.return_value = api_response

        await journey_collector.update_journey_stops(
            db_session, journey, api_response.ITEMS
        )
        await db_session.flush()

        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()

        station_codes = [s.station_code for s in stops]
        assert (
            "SE" not in station_codes
        ), f"Discovery Secaucus absent from the API must be phantom-deleted, got {station_codes}"
        assert station_codes == [
            "NY",
            "NP",
            "MP",
        ], f"Expected NY -> NP -> MP after phantom deletion, got {station_codes}"


# ---------------------------------------------------------------------------
# Invariant / field-presence matrix tests for _resequence_stops (issue #1537)
# ---------------------------------------------------------------------------

# The four optional time fields that drive get_sort_key, in the order the code
# consults them. Every combination of present/absent is exercised below.
_TIME_FIELDS = (
    "scheduled_arrival",
    "scheduled_departure",
    "updated_arrival",
    "updated_departure",
)
_FIELD_ABBREV = {
    "scheduled_arrival": "sa",
    "scheduled_departure": "sd",
    "updated_arrival": "ua",
    "updated_departure": "ud",
}
# All 16 presence combinations, as tuples of booleans aligned with _TIME_FIELDS.
_FIELD_PRESENCE_COMBINATIONS = list(itertools.product((False, True), repeat=4))

# Four distinct stops in intended geographic order: origin first, terminal last.
_INVARIANT_STATIONS = [
    ("TR", "Trenton"),
    ("HL", "Hamilton"),
    ("PJ", "Princeton Junction"),
    ("NY", "New York Penn Station"),
]
# Fixed base time. The tests never read the wall clock for their assertions
# (resequencing sorts purely on the stop time fields), so no time-freezing
# library is needed to keep them deterministic — the timestamps are constants.
_INVARIANT_BASE_TIME = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
_INVARIANT_STEP = timedelta(minutes=10)


def _combo_label(combo: tuple[bool, ...]) -> str:
    """Readable parametrize id, e.g. ``sa1_sd0_ua1_ud0``."""
    return "_".join(
        f"{_FIELD_ABBREV[field]}{int(present)}"
        for field, present in zip(_TIME_FIELDS, combo, strict=True)
    )


class TestResequenceInvariants:
    """Invariant tests for ``_resequence_stops`` across the 16 field-presence
    combinations of its four optional time fields (issue #1537).

    Rather than asserting a single hand-picked order, these tests assert the
    ordering *invariants* the resequencer must uphold for every combination:

    - **Origin first / terminal last** — the stop with the earliest effective
      time lands at sequence 0, the latest at sequence N-1.
    - **Contiguous ``0..N-1``** — sequences are dense with no duplicates.
    - **Insertion-order independence** — seeding the same stops in a different
      DB row order must produce the same result (no reliance on stable sort
      over unspecified row order for stops with distinct sort keys).
    - **Idempotence** — a second resequencing pass changes nothing.
    - **No timed stop after an untimed one** — a stop bucketed to
      ``DATETIME_MAX_ET`` can never precede a stop that has a real time.

    Every failure message prints the offending combination and the resulting
    stop set, per the repo's verbose-tests-for-debugging philosophy.
    """

    async def _seed_journey(
        self,
        db_session: AsyncSession,
        combo: tuple[bool, ...],
        insertion_order: list[int],
        train_id: str,
    ) -> TrainJourney:
        """Seed a 4-stop journey where every stop has field presence ``combo``.

        Each stop's present time fields are all set to a distinct,
        strictly-increasing ``effective`` time so its position is unambiguous
        regardless of which fields carry it. Stops are inserted in
        ``insertion_order`` (indices into ``_INVARIANT_STATIONS``) so the test
        can prove the output is independent of DB row order.

        For the empty combination (no time fields) the only ordering signal is
        ``stop_sequence``, so it is seeded to the intended index; for every
        timed combination ``stop_sequence`` is seeded *reversed* to prove the
        time sort overrides a wrong input sequence.
        """
        has_time = any(combo)
        n = len(_INVARIANT_STATIONS)

        journey = TrainJourney(
            train_id=train_id,
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code=_INVARIANT_STATIONS[0][0],
            terminal_station_code=_INVARIANT_STATIONS[-1][0],
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        for idx in insertion_order:
            code, name = _INVARIANT_STATIONS[idx]
            effective = _INVARIANT_BASE_TIME + idx * _INVARIANT_STEP
            stop_kwargs: dict[str, object] = {
                "journey_id": journey.id,
                "journey_date": journey.journey_date,
                "station_code": code,
                "station_name": name,
                "stop_sequence": idx if not has_time else (n - 1 - idx),
                "scheduled_arrival": None,
                "scheduled_departure": None,
                "updated_arrival": None,
                "updated_departure": None,
            }
            for field, present in zip(_TIME_FIELDS, combo, strict=True):
                if present:
                    stop_kwargs[field] = effective
            db_session.add(JourneyStop(**stop_kwargs))

        await db_session.flush()
        return journey

    async def _ordered_stops(
        self, db_session: AsyncSession, journey: TrainJourney
    ) -> list[tuple[str, int]]:
        """Return ``[(station_code, stop_sequence), ...]`` ordered by sequence."""
        stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = (await db_session.scalars(stmt)).all()
        return [(s.station_code, s.stop_sequence) for s in stops]

    @pytest.mark.parametrize("combo", _FIELD_PRESENCE_COMBINATIONS, ids=_combo_label)
    @pytest.mark.asyncio
    async def test_resequence_invariants_over_field_presence_matrix(
        self,
        db_session: AsyncSession,
        journey_collector,
        mock_njt_client,
        combo,
    ):
        """For each of the 16 field-presence combinations, resequencing must
        yield origin-first/terminal-last order, contiguous sequences,
        insertion-order independence, and idempotence."""
        n = len(_INVARIANT_STATIONS)
        intended_codes = [code for code, _ in _INVARIANT_STATIONS]
        label = _combo_label(combo)

        # (1) Seed with REVERSED insertion order and resequence.
        journey_rev = await self._seed_journey(
            db_session, combo, list(range(n - 1, -1, -1)), f"INV_{label}_R"
        )
        await journey_collector._resequence_stops(db_session, journey_rev)
        await db_session.flush()
        result_rev = await self._ordered_stops(db_session, journey_rev)
        codes_rev = [code for code, _ in result_rev]
        seqs_rev = [seq for _, seq in result_rev]

        # Origin first, terminal last, correct geographic order throughout.
        assert codes_rev == intended_codes, (
            f"combo={label}: reversed-insertion resequence produced {codes_rev}, "
            f"expected origin-first/terminal-last order {intended_codes}"
        )
        # Contiguous 0..N-1, no duplicates.
        assert seqs_rev == list(range(n)), (
            f"combo={label}: sequences must be a contiguous 0..N-1 with no "
            f"duplicates, got {seqs_rev} (stops {result_rev})"
        )

        # (2) Insertion-order independence: FORWARD insertion must match exactly.
        journey_fwd = await self._seed_journey(
            db_session, combo, list(range(n)), f"INV_{label}_F"
        )
        await journey_collector._resequence_stops(db_session, journey_fwd)
        await db_session.flush()
        result_fwd = await self._ordered_stops(db_session, journey_fwd)
        assert result_fwd == result_rev, (
            f"combo={label}: DB insertion order changed the result — "
            f"forward-insertion {result_fwd} != reversed-insertion {result_rev}"
        )

        # (3) Idempotence: a second pass must not change anything.
        await journey_collector._resequence_stops(db_session, journey_rev)
        await db_session.flush()
        result_rev_again = await self._ordered_stops(db_session, journey_rev)
        assert result_rev_again == result_rev, (
            f"combo={label}: resequencing is not idempotent — "
            f"{result_rev} became {result_rev_again} on the second pass"
        )

    @pytest.mark.asyncio
    async def test_untimed_stop_cannot_displace_a_timed_stop_from_position_zero(
        self, db_session: AsyncSession, journey_collector, mock_njt_client
    ):
        """A stop with no scheduled/updated time is bucketed to DATETIME_MAX_ET
        and must sort AFTER every timed stop, even if its input ``stop_sequence``
        is 0.

        This is the invariant the ``DATETIME_MAX_ET`` bucketing exists to protect
        (see the comment above ``get_sort_key``): null-time stops must never be
        placed at position 0. Here an untimed stop is deliberately seeded with
        ``stop_sequence=0`` and must still end up behind both timed stops.
        """
        journey = TrainJourney(
            train_id="INV_TIMED_VS_UNTIMED",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            scheduled_departure=now_et(),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.flush()

        # Timed origin (12:00) and timed terminal (12:30).
        timed_origin = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=2,  # deliberately wrong input order
            scheduled_arrival=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            scheduled_departure=datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC),
        )
        timed_terminal = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=3,
            scheduled_arrival=datetime(2024, 1, 1, 12, 30, 0, tzinfo=UTC),
            scheduled_departure=None,
        )
        # Untimed stop with stop_sequence=0 — must NOT grab position 0.
        untimed_low_seq = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="SE",
            station_name="Secaucus Junction",
            stop_sequence=0,
            scheduled_arrival=None,
            scheduled_departure=None,
            updated_arrival=None,
            updated_departure=None,
        )
        # A second untimed stop with a higher sequence — must follow SE and stay
        # behind the timed stops, proving untimed stops keep their relative order.
        untimed_high_seq = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="ND",
            station_name="New Brunswick",
            stop_sequence=9,
            scheduled_arrival=None,
            scheduled_departure=None,
            updated_arrival=None,
            updated_departure=None,
        )
        # Insert in a scrambled order so nothing leans on row order.
        for stop in (untimed_high_seq, timed_terminal, untimed_low_seq, timed_origin):
            db_session.add(stop)
        await db_session.flush()

        await journey_collector._resequence_stops(db_session, journey)
        await db_session.flush()

        result = await self._ordered_stops(db_session, journey)
        codes = [code for code, _ in result]
        seqs = [seq for _, seq in result]

        # Timed stops (by time) come first, untimed (by input sequence) after.
        assert codes == ["TR", "NY", "SE", "ND"], (
            "Timed stops must precede untimed stops (untimed ordered by their "
            f"input sequence), got {result}"
        )
        # The untimed stop seeded at sequence 0 must not be first.
        assert codes[0] == "TR", (
            "A timed stop must hold position 0; an untimed stop with input "
            f"stop_sequence=0 must not displace it. Got order {result}"
        )
        assert seqs == [0, 1, 2, 3], f"Expected contiguous [0, 1, 2, 3], got {seqs}"
