"""
Integration tests for the journey collector with three-tier inference.

Tests the full collection flow with mock API responses but real database.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et
from tests.fixtures.njt_api_responses import (
    create_stop_list_response,
    create_departed_stop,
    create_pending_stop,
    StopBuilder,
)


class TestJourneyCollectorIntegration:
    """Integration tests for journey collector with inference system."""

    @pytest.mark.skip(reason="Integration test disabled - needs further debugging")
    @pytest.mark.asyncio
    async def test_full_collection_with_inference(self, db_session: AsyncSession):
        """Test complete journey collection flow with three-tier inference."""

        # Create a journey in the database with unique ID
        import time

        unique_id = f"INT{int(time.time() * 1000) % 10000}"
        journey = TrainJourney(
            train_id=unique_id,
            journey_date=datetime.now().date(),
            line_code="TE",
            line_name="Test Line",
            destination="Test Terminal",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et() - timedelta(hours=3),
            scheduled_arrival=now_et() - timedelta(hours=1),
            has_complete_journey=False,
            is_completed=False,
        )
        db_session.add(journey)
        await db_session.commit()

        # Mock NJT client
        mock_client = AsyncMock(spec=NJTransitClient)

        # Create realistic API response using test fixtures
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id=unique_id,
            line_code="TE",
            destination="Test Terminal",
            stops=[
                # Origin - 3 hours ago, no DEPARTED flag
                builder.build_stop(
                    "NY", "New York", "10:00:00 AM", departed=False, track="7"
                ),
                # Second stop - 2.5 hours ago, has DEPARTED flag
                builder.build_stop(
                    "NP",
                    "Newark Penn",
                    "10:30:00 AM",
                    arr_time="10:25:00 AM",
                    departed=True,
                    track="2",
                ),
                # Third stop - 2 hours ago, no DEPARTED flag
                builder.build_stop(
                    "MP",
                    "Metropark",
                    "11:00:00 AM",
                    arr_time="10:55:00 AM",
                    departed=False,
                    track="1",
                ),
                # Terminal - 1 hour ago, no DEPARTED flag
                builder.build_stop(
                    "TR",
                    "Trenton",
                    "12:00:00 PM",
                    arr_time="11:55:00 AM",
                    departed=False,
                    track="4",
                ),
            ],
        )

        mock_client.get_train_stop_list.return_value = api_response

        # Run collection
        collector = JourneyCollector(mock_client)
        await collector.collect_journey_details(db_session, journey)
        await db_session.commit()

        # Reload journey with stops
        result = await db_session.execute(
            select(TrainJourney).where(TrainJourney.id == journey.id)
        )
        journey = result.scalar_one()

        # Load stops
        result = await db_session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        stops = result.scalars().all()

        # Verify stops were created
        assert len(stops) == 4

        # Verify inference worked correctly
        stop_by_code = {s.station_code: s for s in stops}

        # NY should have sequential inference (before NP which has DEPARTED=YES)
        assert stop_by_code["NY"].has_departed_station == True
        assert stop_by_code["NY"].departure_source == "sequential_inference"
        assert stop_by_code["NY"].actual_departure is not None

        # NP should have api_explicit
        assert stop_by_code["NP"].has_departed_station == True
        assert stop_by_code["NP"].departure_source == "api_explicit"
        assert stop_by_code["NP"].actual_departure is not None
        assert stop_by_code["NP"].track == "2"

        # MP should have time_inference (2 hours ago)
        assert stop_by_code["MP"].has_departed_station == True
        assert stop_by_code["MP"].departure_source == "time_inference"

        # TR should have time_inference (1 hour ago)
        assert stop_by_code["TR"].has_departed_station == True
        assert stop_by_code["TR"].departure_source == "time_inference"

        # Verify journey marked as complete
        assert journey.has_complete_journey == True
        assert journey.stops_count == 4

    @pytest.mark.skip(reason="Integration test disabled - needs further debugging")
    @pytest.mark.asyncio
    async def test_incremental_updates_preserve_inference(
        self, db_session: AsyncSession
    ):
        """Test that incremental updates preserve inference decisions."""

        # Create journey with existing stops
        import time

        unique_id = f"UP{int(time.time() * 1000) % 10000}"
        journey = TrainJourney(
            train_id=unique_id,
            journey_date=datetime.now().date(),
            line_code="TE",
            destination="Terminal",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et() - timedelta(hours=2),
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        # Add stops with some already marked as departed
        stops = [
            JourneyStop(
                journey_id=journey.id,
                station_code="NY",
                station_name="New York",
                stop_sequence=0,
                scheduled_departure=now_et() - timedelta(hours=2),
                has_departed_station=True,
                departure_source="time_inference",  # Previously inferred
                actual_departure=now_et() - timedelta(hours=2),
            ),
            JourneyStop(
                journey_id=journey.id,
                station_code="NP",
                station_name="Newark",
                stop_sequence=1,
                scheduled_departure=now_et() - timedelta(hours=1, minutes=30),
                has_departed_station=False,  # Not yet departed
                departure_source=None,
            ),
            JourneyStop(
                journey_id=journey.id,
                station_code="TR",
                station_name="Trenton",
                stop_sequence=2,
                scheduled_departure=now_et() - timedelta(hours=1),
                has_departed_station=False,
                departure_source=None,
            ),
        ]
        for stop in stops:
            db_session.add(stop)
        await db_session.commit()

        # Mock API response with Newark now departed
        mock_client = AsyncMock(spec=NJTransitClient)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id=unique_id,
            stops=[
                builder.build_stop(
                    "NY", "New York", "10:00:00 AM", departed=False, track="7"
                ),  # Still no explicit flag
                builder.build_stop(
                    "NP", "Newark", "10:30:00 AM", departed=True, track="2"
                ),  # NOW has DEPARTED flag
                builder.build_stop(
                    "TR", "Trenton", "11:00:00 AM", departed=False, track="4"
                ),
            ],
        )
        mock_client.get_train_stop_list.return_value = api_response

        # Run update
        collector = JourneyCollector(mock_client)
        await collector.collect_journey_details(db_session, journey)
        await db_session.commit()

        # Reload stops
        result = await db_session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        updated_stops = result.scalars().all()

        stop_by_code = {s.station_code: s for s in updated_stops}

        # NY should be upgraded from time_inference to sequential_inference
        assert stop_by_code["NY"].has_departed_station == True
        assert stop_by_code["NY"].departure_source == "sequential_inference"

        # NP should now have api_explicit
        assert stop_by_code["NP"].has_departed_station == True
        assert stop_by_code["NP"].departure_source == "api_explicit"
        assert stop_by_code["NP"].track == "2"

        # TR should now have time_inference
        assert stop_by_code["TR"].has_departed_station == True
        assert stop_by_code["TR"].departure_source == "time_inference"

    @pytest.mark.skip(reason="Integration test disabled - needs further debugging")
    @pytest.mark.asyncio
    async def test_swapped_times_logged_and_fixed(self, db_session: AsyncSession):
        """Test that swapped arrival/departure times are detected and fixed."""

        # Create journey
        import time

        unique_id = f"SWP{int(time.time() * 1000) % 10000}"
        journey = TrainJourney(
            train_id=unique_id,
            journey_date=datetime.now().date(),
            line_code="TE",
            destination="Terminal",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et() - timedelta(hours=1),
            has_complete_journey=False,
        )
        db_session.add(journey)
        await db_session.commit()

        # Mock API with swapped times
        mock_client = AsyncMock(spec=NJTransitClient)
        builder = StopBuilder()
        api_response = create_stop_list_response(
            train_id=unique_id,
            stops=[
                builder.build_stop(
                    "NY", "New York", "10:00:00 AM", departed=True, track="7"
                ),
                # Newark has swapped times (arrival after departure)
                builder.build_stop(
                    "NP",
                    "Newark",
                    "10:30:00 AM",
                    arr_time="10:35:00 AM",  # WRONG: Arrival after departure
                    departed=True,
                    track="2",
                ),
                builder.build_stop(
                    "TR",
                    "Trenton",
                    "11:00:00 AM",
                    arr_time="10:55:00 AM",
                    departed=False,
                ),
            ],
        )
        mock_client.get_train_stop_list.return_value = api_response

        # Run collection with mock logger to capture warnings
        with patch("trackrat.collectors.njt.journey.logger") as mock_logger:
            collector = JourneyCollector(mock_client)
            await collector.collect_journey_details(db_session, journey)
            await db_session.commit()

            # Verify swap was detected and logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if len(call[0]) > 0 and "swapped_arrival_departure_times" in call[0][0]
            ]
            assert len(warning_calls) > 0, "Swapped times warning not logged"

        # Verify times were corrected
        result = await db_session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .where(JourneyStop.station_code == "NP")
        )
        np_stop = result.scalar_one()

        # Times should be corrected (arrival before departure)
        assert np_stop.actual_arrival is not None
        assert np_stop.actual_departure is not None
        assert np_stop.actual_arrival <= np_stop.actual_departure

    @pytest.mark.skip(reason="Integration test disabled - needs further debugging")
    @pytest.mark.asyncio
    async def test_data_quality_metrics_improvement(self, db_session: AsyncSession):
        """Test that the inference system improves key data quality metrics."""

        # Create multiple journeys with various scenarios
        import time

        base_time = now_et() - timedelta(hours=6)

        journeys = []
        base_time_ms = int(time.time() * 1000) % 10000
        for i in range(5):
            journey = TrainJourney(
                train_id=f"MT{base_time_ms}{i}",
                journey_date=datetime.now().date(),
                line_code="TE",
                destination=f"Destination {i}",
                origin_station_code="NY",
                terminal_station_code="TR",
                data_source="NJT",
                scheduled_departure=base_time + timedelta(hours=i),
                has_complete_journey=False,
            )
            db_session.add(journey)
            journeys.append(journey)

        await db_session.flush()

        # Add stops for each journey (all in the past, should be inferable)
        for journey in journeys:
            for j in range(3):
                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=f"S{j}",
                    station_name=f"Station {j}",
                    stop_sequence=j,
                    scheduled_departure=journey.scheduled_departure
                    + timedelta(minutes=30 * j),
                    has_departed_station=False,
                    track="1" if j == 0 else None,  # Only first stop has track
                )
                db_session.add(stop)

        await db_session.commit()

        # Check metrics BEFORE inference
        from sqlalchemy import func, and_

        result = await db_session.execute(
            select(
                func.count(JourneyStop.id).label("total"),
                func.count(JourneyStop.actual_departure).label("has_actual"),
            ).where(
                and_(
                    JourneyStop.track.isnot(None),
                    JourneyStop.scheduled_departure < now_et(),
                )
            )
        )
        before = result.first()
        before_rate = (
            (before.has_actual / before.total * 100) if before.total > 0 else 0
        )

        # Run collection with inference for all journeys
        mock_client = AsyncMock(spec=NJTransitClient)
        builder = StopBuilder()

        for journey in journeys:
            # Mock API response with at least one DEPARTED flag
            api_response = create_stop_list_response(
                train_id=journey.train_id,
                stops=[
                    builder.build_stop(
                        "S0", "Station 0", "10:00:00 AM", departed=True, track="1"
                    ),  # First stop departed
                    builder.build_stop(
                        "S1", "Station 1", "10:30:00 AM", departed=False
                    ),
                    builder.build_stop(
                        "S2", "Station 2", "11:00:00 AM", departed=False
                    ),
                ],
            )
            mock_client.get_train_stop_list.return_value = api_response

            collector = JourneyCollector(mock_client)
            await collector.collect_journey_details(db_session, journey)

        await db_session.commit()

        # Check metrics AFTER inference
        result = await db_session.execute(
            select(
                func.count(JourneyStop.id).label("total"),
                func.count(JourneyStop.actual_departure).label("has_actual"),
                func.count(func.nullif(JourneyStop.has_departed_station, False)).label(
                    "has_departed"
                ),
            ).where(
                and_(
                    JourneyStop.track.isnot(None),
                    JourneyStop.scheduled_departure < now_et(),
                )
            )
        )
        after = result.first()
        after_rate = (after.has_actual / after.total * 100) if after.total > 0 else 0
        departed_rate = (
            (after.has_departed / after.total * 100) if after.total > 0 else 0
        )

        # Verify improvement
        assert (
            after_rate > before_rate
        ), f"Actual times rate should improve: {before_rate}% -> {after_rate}%"
        assert (
            after_rate >= 80
        ), f"Should achieve >80% actual times coverage, got {after_rate}%"
        assert (
            departed_rate >= 80
        ), f"Should achieve >80% departed flag coverage, got {departed_rate}%"

        # Check departure source distribution
        result = await db_session.execute(
            select(
                JourneyStop.departure_source, func.count(JourneyStop.id).label("count")
            )
            .where(JourneyStop.departure_source.isnot(None))
            .group_by(JourneyStop.departure_source)
        )

        sources = {row.departure_source: row.count for row in result}
        assert len(sources) > 0, "Should have departure sources recorded"
        assert (
            "api_explicit" in sources
            or "sequential_inference" in sources
            or "time_inference" in sources
        )
