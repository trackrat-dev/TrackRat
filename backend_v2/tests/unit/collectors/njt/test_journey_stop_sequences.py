"""
Unit tests for journey stop sequence fixes.

Tests phantom stop deletion and SQLAlchemy dirty tracking to prevent
the bug where Trenton appears after Hamilton due to duplicate stop_sequence values.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop
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
        tr_stop = JourneyStop(
            journey_id=journey.id,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=0,
            scheduled_departure=now_et(),
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
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
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
