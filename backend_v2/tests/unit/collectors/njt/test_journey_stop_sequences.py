"""
Unit tests for journey stop sequence fixes.

Tests phantom stop deletion and SQLAlchemy dirty tracking to prevent
the bug where Trenton appears after Hamilton due to duplicate stop_sequence values.
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

from tests.fixtures.njt_api_responses import StopBuilder, create_stop_list_response


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
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
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
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
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
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
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
