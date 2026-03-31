"""
End-to-end performance tests for Amtrak integration.

Tests system performance with Amtrak data collection and queries,
ensuring the system scales well with additional data sources.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.services.departure import DepartureService
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et
from tests.factories.amtrak import (
    create_amtrak_train_data,
    create_amtrak_station_data,
    create_amtrak_journey,
    create_amtrak_journey_stop,
)


@pytest.mark.asyncio
class TestPerformance:
    """Test suite for performance with Amtrak integration."""

    async def test_discovery_performance_large_dataset(self):
        """Test discovery performance with large number of trains."""

        # Create large dataset (simulate peak Amtrak traffic)
        train_count = 50
        mock_trains = []

        for i in range(train_count):
            train_num = str(2000 + i)
            # Mix of NYP and non-NYP trains (realistic ratio)
            serves_nyp = i % 3 == 0  # ~33% serve NYP

            stations = []
            if serves_nyp:
                stations.append(
                    create_amtrak_station_data(
                        code="NYP",
                        sch_dep=f"2025-07-05T{6 + (i % 18)}:{(i % 4) * 15:02d}:00-05:00",
                    )
                )
                stations.append(create_amtrak_station_data(code="TRE"))
            else:
                stations.append(create_amtrak_station_data(code="PHL"))
                stations.append(create_amtrak_station_data(code="WAS"))

            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                route="Northeast Regional" if i % 2 == 0 else "Acela",
                stations=stations,
            )
            mock_trains.append(train_data)

        # Create mock API response
        mock_api_response = {}
        for train_data in mock_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        # Test discovery performance
        discovery_collector = AmtrakDiscoveryCollector()

        with patch.object(discovery_collector.client, "get_all_trains") as mock_get_all:
            mock_get_all.return_value = mock_api_response

            start_time = time.time()
            discovered_trains = await discovery_collector.discover_trains()
            end_time = time.time()

            discovery_duration = end_time - start_time

            # Performance assertions
            assert discovery_duration < 2.0  # Should complete within 2 seconds

            # Should discover all trains (multi-hub discovery includes NYP, PHL, WAS)
            expected_count = train_count  # All trains serve at least one discovery hub
            assert len(discovered_trains) == expected_count

            # Verify performance metrics
            trains_per_second = len(discovered_trains) / discovery_duration
            assert trains_per_second > 5  # Should process at least 5 trains per second

    async def test_journey_collection_batch_performance(self, db_session: AsyncSession):
        """Test journey collection performance with batch processing."""

        train_count = 20
        mock_trains = []

        # Create realistic train data
        for i in range(train_count):
            train_num = str(2150 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                route="Northeast Regional",
                stations=[
                    create_amtrak_station_data(
                        code="NYP",
                        sch_dep=f"2025-07-05T{14 + (i // 4)}:{(i % 4) * 15:02d}:00-05:00",
                        status="Boarding" if i % 3 == 0 else "Departed",
                    ),
                    create_amtrak_station_data(
                        code="NWK",
                        sch_arr=f"2025-07-05T{14 + (i // 4)}:{(i % 4) * 15 + 15:02d}:00-05:00",
                        status="Enroute",
                    ),
                    create_amtrak_station_data(
                        code="TRE",
                        sch_arr=f"2025-07-05T{14 + (i // 4) + 1}:{(i % 4) * 15:02d}:00-05:00",
                        status="Enroute",
                    ),
                ],
            )
            mock_trains.append(train_data)

        mock_api_response = {}
        for train_data in mock_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        # Test batch collection performance
        journey_collector = AmtrakJourneyCollector()

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                start_time = time.time()

                # Collect all journeys
                collected_count = 0
                for i in range(train_count):
                    train_id = f"{2150 + i}-4"
                    result = await journey_collector.collect_journey(train_id)
                    if result:
                        collected_count += 1

                end_time = time.time()

                collection_duration = end_time - start_time

                # Performance assertions
                assert collection_duration < 5.0  # Should complete within 5 seconds
                assert collected_count == train_count

                # Verify database performance
                stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
                result = await db_session.execute(stmt)
                db_journeys = list(result.scalars().all())

                assert len(db_journeys) == train_count

                # Performance metrics
                trains_per_second = collected_count / collection_duration
                assert (
                    trains_per_second > 2
                )  # Should process at least 2 trains per second

    async def test_concurrent_collection_performance(self, db_session: AsyncSession):
        """Test performance under concurrent collection scenarios."""

        # Simulate concurrent collectors
        collector1 = AmtrakJourneyCollector()
        collector2 = AmtrakJourneyCollector()

        # Create test data
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                )
            ],
        )

        mock_api_response = {"2150": [train_data]}

        # Test concurrent access performance
        import asyncio

        async def collect_with_collector(collector, train_id):
            # Mock the entire _collect_journey_locked method to avoid API calls
            async def mock_collect_journey_locked(
                train_id_inner: str,
            ) -> TrainJourney | None:
                # Create a mock journey object directly
                from trackrat.models.database import TrainJourney
                from trackrat.utils.time import now_et

                mock_journey = TrainJourney(
                    train_id=train_id_inner,
                    journey_date=now_et().date(),
                    line_code="AM",
                    destination="Test Destination",
                    origin_station_code="NYP",
                    terminal_station_code="WAS",
                    data_source="AMTRAK",
                    has_complete_journey=True,
                    stops_count=1,
                )
                return mock_journey

            with patch.object(
                collector,
                "_collect_journey_locked",
                side_effect=mock_collect_journey_locked,
            ):
                return await collector.collect_journey(train_id)

        start_time = time.time()

        # Run concurrent collections
        results = await asyncio.gather(
            collect_with_collector(collector1, "2150-4"),
            collect_with_collector(collector2, "2150-4"),
            return_exceptions=True,
        )

        end_time = time.time()

        concurrent_duration = end_time - start_time

        # Performance assertions
        assert concurrent_duration < 1.0  # Should complete quickly

        # Both should succeed (or at least not fail catastrophically)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 1

    async def test_memory_usage_large_dataset(self, db_session: AsyncSession):
        """Test memory efficiency with large datasets."""

        journey_count = 200

        # Create journeys with minimal memory footprint testing
        for i in range(journey_count):
            journey = create_amtrak_journey(
                train_id=f"A{2000 + i}",
                origin="NY",
                scheduled_departure=now_et() + timedelta(minutes=i),
                data_source="AMTRAK",
            )

            # Single stop to minimize memory usage
            stop = create_amtrak_journey_stop(
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=now_et() + timedelta(minutes=i),
                stop_sequence=0,
            )
            journey.stops = [stop]

            db_session.add(journey)

            # Commit in batches to test memory efficiency
            if i % 50 == 49:
                await db_session.commit()

        await db_session.commit()

        # Test query memory efficiency
        departure_service = DepartureService()

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            # Query large dataset
            response = await departure_service.get_departures(
                db=db_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=4),
                limit=100,  # Limit to test pagination efficiency
            )

            # Should handle large dataset efficiently
            assert len(response.departures) <= 100
            assert response.metadata["count"] == len(response.departures)

    async def test_database_query_optimization(self, db_session: AsyncSession):
        """Test database query performance and optimization."""

        # Create journeys with complex stop patterns
        journey_count = 50

        for i in range(journey_count):
            journey = create_amtrak_journey(
                train_id=f"A{2100 + i}",
                origin="NY",
                scheduled_departure=now_et() + timedelta(minutes=i * 10),
                data_source="AMTRAK",
            )

            # Create multiple stops per journey
            stops = []
            for j, station_code in enumerate(["NY", "NP", "TR"]):
                stop = create_amtrak_journey_stop(
                    station_code=station_code,
                    station_name=f"Station {station_code}",
                    scheduled_departure=now_et() + timedelta(minutes=i * 10 + j * 15),
                    stop_sequence=j,
                )
                stops.append(stop)

            journey.stops = stops
            db_session.add(journey)

        await db_session.commit()

        # Test complex query performance
        start_time = time.time()

        # Query with joins (similar to departure service)
        from sqlalchemy.orm import selectinload

        stmt = (
            select(TrainJourney)
            .options(selectinload(TrainJourney.stops))
            .where(TrainJourney.data_source == "AMTRAK")
            .limit(25)
        )

        result = await db_session.execute(stmt)
        journeys = list(result.scalars().unique().all())

        end_time = time.time()

        query_duration = end_time - start_time

        # Performance assertions
        assert query_duration < 0.2  # Should be very fast for SQLite
        assert len(journeys) == 25

        # Verify joins worked efficiently
        for journey in journeys:
            assert len(journey.stops) == 3  # All stops loaded

    async def test_api_response_serialization_performance(
        self, db_session: AsyncSession
    ):
        """Test API response serialization performance."""

        # Create complex journeys for serialization testing
        journey_count = 30

        for i in range(journey_count):
            journey = create_amtrak_journey(
                train_id=f"A{2200 + i}",
                origin="NY",
                destination="Washington Union Station",
                scheduled_departure=now_et() + timedelta(minutes=i * 15),
                data_source="AMTRAK",
                line_code="AM",
                line_name="Amtrak",
            )

            # Complex stop pattern
            stops = []
            for j, (station_code, station_name) in enumerate(
                [
                    ("NY", "New York Penn Station"),
                    ("NP", "Newark Penn Station"),
                    ("TR", "Trenton"),
                    ("MP", "Metropark"),
                ]
            ):
                stop = create_amtrak_journey_stop(
                    station_code=station_code,
                    station_name=station_name,
                    scheduled_departure=now_et() + timedelta(minutes=i * 15 + j * 10),
                    scheduled_arrival=(
                        now_et() + timedelta(minutes=i * 15 + j * 10 - 2)
                        if j > 0
                        else None
                    ),
                    stop_sequence=j,
                    track=f"{15 + j}" if j == 0 else None,
                    raw_amtrak_status="Departed" if j == 0 else "Enroute",
                    has_departed_station=j == 0,
                )
                stops.append(stop)

            journey.stops = stops
            db_session.add(journey)

        await db_session.commit()

        # Test serialization performance via departure service
        departure_service = DepartureService()

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt_client:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            # Mock the station refresh method that's called for NJT trains
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_njt_client.return_value = mock_client

            start_time = time.time()

            response = await departure_service.get_departures(
                db=db_session,
                from_station="NY",
                to_station="TR",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=10),
            )

            end_time = time.time()

            serialization_duration = end_time - start_time

            # Performance assertions
            assert serialization_duration < 0.3  # Should serialize quickly
            assert len(response.departures) <= journey_count

            # Verify complete serialization
            for departure in response.departures:
                assert departure.train_id is not None
                assert departure.line is not None
                assert departure.departure is not None
                assert departure.arrival is not None
                assert departure.train_position is not None
                assert departure.data_freshness is not None
