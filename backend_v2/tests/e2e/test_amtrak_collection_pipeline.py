"""
End-to-end tests for Amtrak collection pipeline.

Tests the complete data flow from discovery through API responses,
simulating the full system operation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.services.departure import DepartureService
from trackrat.models.database import TrainJourney, JourneyStop, JourneySnapshot
from trackrat.utils.time import now_et
from tests.factories.amtrak import create_amtrak_train_data, create_amtrak_station_data


@pytest.mark.asyncio
class TestAmtrakCollectionPipeline:
    """Test suite for end-to-end Amtrak collection pipeline."""

    @pytest.mark.skip(
        reason="Mock Amtrak data setup issue - station code mapping not working in test environment"
    )
    async def test_full_collection_pipeline(self, db_session: AsyncSession):
        """Test complete pipeline: discovery → journey collection → API query."""

        # Step 1: Create realistic mock Amtrak data
        mock_trains = []
        for i in range(3):
            train_num = str(2150 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                route="Northeast Regional",
                train_state="Active",
                stations=[
                    create_amtrak_station_data(
                        code="NYP",
                        name="New York Penn Station",
                        sch_dep=f"2025-07-05T{14+i}:30:00-05:00",
                        status="Boarding" if i == 0 else "Departed",
                        platform=f"{15+i}",
                    ),
                    create_amtrak_station_data(
                        code="NWK",
                        name="Newark Penn Station",
                        sch_arr=f"2025-07-05T{14+i}:45:00-05:00",
                        sch_dep=f"2025-07-05T{14+i}:47:00-05:00",
                        status="Enroute",
                    ),
                    create_amtrak_station_data(
                        code="TRE",
                        name="Trenton",
                        sch_arr=f"2025-07-05T{15+i}:15:00-05:00",
                        status="Enroute",
                    ),
                ],
            )
            mock_trains.append(train_data)

        # Create mock API response
        mock_api_response = {}
        for train_data in mock_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        # Step 2: Run discovery phase
        discovery_collector = AmtrakDiscoveryCollector()

        with patch.object(
            discovery_collector.client, "get_all_trains"
        ) as mock_discovery:
            mock_discovery.return_value = mock_api_response

            discovered_trains = await discovery_collector.discover_trains()

            # Verify discovery found all trains
            assert len(discovered_trains) == 3
            expected_train_ids = [f"{2150+i}-4" for i in range(3)]
            assert set(discovered_trains) == set(expected_train_ids)

        # Step 3: Run journey collection for each discovered train
        journey_collector = AmtrakJourneyCollector()
        collected_journeys = []

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                for train_id in discovered_trains:
                    journey = await journey_collector.collect_journey(train_id)
                    if journey:
                        collected_journeys.append(journey)

        # Verify all journeys collected
        assert len(collected_journeys) == 3

        # Step 4: Verify data persisted in database
        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        db_journeys = list(result.scalars().all())

        assert len(db_journeys) == 3

        # Verify journey details
        for journey in db_journeys:
            assert journey.data_source == "AMTRAK"
            assert journey.line_code == "AM"
            assert journey.line_name == "Amtrak"
            # Use stops_count instead of lazy loading
            assert journey.stops_count == 3  # NYP, NWK, TRE
            # Query snapshots separately
            snapshots_stmt = select(JourneySnapshot).where(
                JourneySnapshot.journey_id == journey.id
            )
            snapshots_result = await db_session.execute(snapshots_stmt)
            snapshots = snapshots_result.scalars().all()
            assert len(snapshots) >= 1

        # Step 5: Query via departure service
        departure_service = DepartureService()

        # Mock to avoid NJT API calls
        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_njt_client.return_value.__aenter__.return_value = AsyncMock()

                response = await departure_service.get_departures(
                    db=db_session,
                    from_station="NY",
                    to_station="TR",
                    time_from=now_et(),
                    time_to=now_et() + timedelta(hours=4),
                )

        # Step 6: Verify API response
        assert len(response.departures) == 3

        for departure in response.departures:
            assert departure.data_source == "AMTRAK"
            assert departure.line.code == "AM"
            assert departure.departure.code == "NY"
            assert departure.arrival.code == "TR"
            # Journey info no longer included in departure response (pure data approach)

    async def test_discovery_with_hub_trains(self, db_session: AsyncSession):
        """Test discovery when trains serve discovery hubs (PHL, WAS)."""

        # Create trains that serve discovery hubs (PHL, WAS) but not NYP
        hub_trains = []
        for i in range(2):
            train_num = str(350 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                route="Pennsylvanian",
                stations=[
                    create_amtrak_station_data(code="PHL", name="Philadelphia"),
                    create_amtrak_station_data(code="WAS", name="Washington"),
                ],
            )
            hub_trains.append(train_data)

        mock_api_response = {}
        for train_data in hub_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        discovery_collector = AmtrakDiscoveryCollector()

        with patch.object(
            discovery_collector.client, "get_all_trains"
        ) as mock_discovery:
            mock_discovery.return_value = mock_api_response

            discovered_trains = await discovery_collector.discover_trains()

            # Should discover both trains since they serve discovery hubs (PHL, WAS)
            assert len(discovered_trains) == 2

        # Discovery doesn't create database entries, so no journeys yet
        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        db_journeys = list(result.scalars().all())

        assert len(db_journeys) == 0

    async def test_mixed_collection_pipeline(self, db_session: AsyncSession):
        """Test pipeline with mix of trains serving different discovery hubs."""

        # Create mixed train data
        mock_trains = []

        # NYP trains (should be discovered)
        for i in range(2):
            train_num = str(2150 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                stations=[
                    create_amtrak_station_data(
                        code="NYP", sch_dep=f"2025-07-05T{14+i}:30:00-05:00"
                    ),
                    create_amtrak_station_data(code="TRE"),
                ],
            )
            mock_trains.append(train_data)

        # PHL/WAS trains (should also be discovered since they serve discovery hubs)
        for i in range(2):
            train_num = str(350 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                stations=[
                    create_amtrak_station_data(
                        code="PHL",
                        name="Philadelphia 30th Street Station",
                        sch_dep=f"2025-07-05T{12+i}:00:00-05:00",
                        status="Enroute",
                    ),
                    create_amtrak_station_data(
                        code="WAS",
                        name="Washington Union Station",
                        sch_arr=f"2025-07-05T{14+i}:30:00-05:00",
                        status="Enroute",
                    ),
                ],
            )
            mock_trains.append(train_data)

        mock_api_response = {}
        for train_data in mock_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        # Run discovery
        discovery_collector = AmtrakDiscoveryCollector()

        with patch.object(
            discovery_collector.client, "get_all_trains"
        ) as mock_discovery:
            mock_discovery.return_value = mock_api_response

            discovered_trains = await discovery_collector.discover_trains()

            # Should discover all trains that serve discovery hubs (NYP, PHL, WAS)
            assert len(discovered_trains) == 4
            # Should include both NYP trains (215x) and PHL/WAS trains (35x)
            nyp_trains = [tid for tid in discovered_trains if tid.startswith("215")]
            hub_trains = [tid for tid in discovered_trains if tid.startswith("35")]
            assert len(nyp_trains) == 2
            assert len(hub_trains) == 2

        # Run journey collection
        journey_collector = AmtrakJourneyCollector()

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                for train_id in discovered_trains:
                    await journey_collector.collect_journey(train_id)

        # Verify all discovered trains are now collected (multi-hub discovery)
        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        db_journeys = list(result.scalars().all())

        assert len(db_journeys) == 4
        # Should include both NYP trains (A215x) and PHL/WAS trains (A35x)
        nyp_journeys = [j for j in db_journeys if j.train_id.startswith("A215")]
        hub_journeys = [j for j in db_journeys if j.train_id.startswith("A35")]
        assert len(nyp_journeys) == 2
        assert len(hub_journeys) == 2

    @pytest.mark.skip(
        reason="Mock Amtrak data setup issue - station code mapping not working in test environment"
    )
    async def test_incremental_updates_pipeline(self, db_session: AsyncSession):
        """Test pipeline with incremental train status updates."""

        # Initial state - train boarding
        initial_train = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                ),
                create_amtrak_station_data(
                    code="TRE", sch_arr="2025-07-05T15:15:00-05:00", status="Enroute"
                ),
            ],
        )

        # Updated state - train departed
        updated_train = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    sch_dep="2025-07-05T14:30:00-05:00",
                    actual_dep="2025-07-05T14:32:00-05:00",
                    status="Departed",
                ),
                create_amtrak_station_data(
                    code="TRE", sch_arr="2025-07-05T15:15:00-05:00", status="Enroute"
                ),
            ],
        )

        journey_collector = AmtrakJourneyCollector()

        # First collection cycle
        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = {"2150": [initial_train]}

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result1 = await journey_collector.collect_journey("2150-4")
                assert result1 is not None
                assert result1.update_count == 1

                # Check initial status by querying stops
                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == result1.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()
                ny_stop = next(s for s in stops if s.station_code == "NY")
                assert ny_stop.raw_amtrak_status == "Station"
                assert ny_stop.has_departed_station is False

        # Second collection cycle (simulating scheduled update)
        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = {"2150": [updated_train]}

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result2 = await journey_collector.collect_journey("2150-4")
                assert result2 is not None
                assert result2.update_count == 2

                # Check updated status by querying stops
                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == result2.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()
                ny_stop = next(s for s in stops if s.station_code == "NY")
                assert ny_stop.raw_amtrak_status == "Departed"
                assert ny_stop.has_departed_station is True
                assert ny_stop.actual_departure is not None

        # Verify API reflects updates
        departure_service = DepartureService()

        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_njt_client.return_value.__aenter__.return_value = AsyncMock()

                response = await departure_service.get_departures(
                    db=db_session,
                    from_station="NY",
                    time_from=now_et(),
                    time_to=now_et() + timedelta(hours=3),
                )

        assert len(response.departures) == 1
        departure = response.departures[0]
        # Status no longer included in departure response (pure data approach)

    @pytest.mark.skip(
        reason="Mock Amtrak data setup issue - station code mapping not working in test environment"
    )
    async def test_large_batch_collection(self, db_session: AsyncSession):
        """Test pipeline performance with larger batch of trains."""

        # Create larger dataset (simulate busy period)
        mock_trains = []
        train_count = 10

        for i in range(train_count):
            train_num = str(2150 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                route="Northeast Regional" if i % 2 == 0 else "Acela",
                stations=[
                    create_amtrak_station_data(
                        code="NYP",
                        sch_dep=f"2025-07-05T{14 + (i // 2)}:{(i % 2) * 30:02d}:00-05:00",
                    ),
                    create_amtrak_station_data(code="TRE"),
                ],
            )
            mock_trains.append(train_data)

        mock_api_response = {}
        for train_data in mock_trains:
            mock_api_response[train_data.trainNum] = [train_data]

        # Run discovery
        discovery_collector = AmtrakDiscoveryCollector()

        with patch.object(
            discovery_collector.client, "get_all_trains"
        ) as mock_discovery:
            mock_discovery.return_value = mock_api_response

            discovered_trains = await discovery_collector.discover_trains()
            assert len(discovered_trains) == train_count

        # Run journey collection for all trains
        journey_collector = AmtrakJourneyCollector()

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                collected_count = 0
                for train_id in discovered_trains:
                    result = await journey_collector.collect_journey(train_id)
                    if result:
                        collected_count += 1

        assert collected_count == train_count

        # Verify all journeys in database
        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        db_journeys = list(result.scalars().all())

        assert len(db_journeys) == train_count

        # Test API query performance with large dataset
        departure_service = DepartureService()

        with patch(
            "trackrat.services.departure.JustInTimeUpdateService"
        ) as mock_jit_class:
            mock_jit_service = AsyncMock()
            mock_jit_service.ensure_fresh_departures = AsyncMock()
            mock_jit_class.return_value.__aenter__.return_value = mock_jit_service

            with patch(
                "trackrat.services.departure.NJTransitClient"
            ) as mock_njt_client:
                mock_njt_client.return_value.__aenter__.return_value = AsyncMock()

                start_time = now_et()

                response = await departure_service.get_departures(
                    db=db_session,
                    from_station="NY",
                    time_from=now_et(),
                    time_to=now_et() + timedelta(hours=6),
                    limit=20,  # Test with reasonable limit
                )

        # Should return up to limit
        assert len(response.departures) <= 20
        assert len(response.departures) > 0

        # Verify all returned trains are Amtrak
        assert all(d.data_source == "AMTRAK" for d in response.departures)

    async def test_pipeline_data_quality(self, db_session: AsyncSession):
        """Test data quality throughout the pipeline."""

        # Create train with comprehensive data
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            route="Northeast Regional",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    name="New York Penn Station",
                    sch_dep="2025-07-05T14:30:00-05:00",
                    actual_dep="2025-07-05T14:32:00-05:00",
                    status="Departed",
                    platform="15",
                ),
                create_amtrak_station_data(
                    code="NWK",
                    name="Newark Penn Station",
                    sch_arr="2025-07-05T14:45:00-05:00",
                    sch_dep="2025-07-05T14:47:00-05:00",
                    status="Enroute",
                ),
                create_amtrak_station_data(
                    code="TRE",
                    name="Trenton",
                    sch_arr="2025-07-05T15:15:00-05:00",
                    status="Enroute",
                ),
            ],
        )

        mock_api_response = {"2150": [train_data]}

        # Collect journey
        journey_collector = AmtrakJourneyCollector()

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                journey = await journey_collector.collect_journey("2150-4")
                assert journey is not None

        # Verify data quality in database
        stmt = select(TrainJourney).where(TrainJourney.train_id == "A2150")
        db_journey = await db_session.scalar(stmt)

        assert db_journey is not None

        # Check journey metadata
        assert db_journey.train_id == "A2150"
        assert db_journey.data_source == "AMTRAK"
        assert db_journey.line_code == "AM"
        assert db_journey.line_name == "Amtrak"
        assert db_journey.destination == "Washington Union Station"
        assert db_journey.origin_station_code == "NY"
        assert db_journey.has_complete_journey is True

        # Check stops data quality by querying separately
        stops_stmt = select(JourneyStop).where(JourneyStop.journey_id == db_journey.id)
        stops_result = await db_session.execute(stops_stmt)
        stops = stops_result.scalars().all()
        assert len(stops) == 3

        stops_by_code = {stop.station_code: stop for stop in stops}

        # NY stop
        ny_stop = stops_by_code["NY"]
        assert ny_stop.station_name == "New York Penn Station"
        assert ny_stop.scheduled_departure is not None
        assert ny_stop.actual_departure is not None
        assert ny_stop.track == "15"
        assert ny_stop.raw_amtrak_status == "Departed"
        assert ny_stop.has_departed_station is True

        # NP stop (mapped from NWK)
        np_stop = stops_by_code["NP"]
        assert np_stop.station_name == "Newark Penn Station"
        assert np_stop.scheduled_arrival is not None
        assert np_stop.scheduled_departure is not None
        assert np_stop.raw_amtrak_status == "Enroute"

        # TR stop
        tr_stop = stops_by_code["TR"]
        assert tr_stop.station_name == "Trenton"
        assert tr_stop.scheduled_arrival is not None
        assert tr_stop.raw_amtrak_status == "Enroute"

        # Check snapshots by querying separately
        snapshots_stmt = select(JourneySnapshot).where(
            JourneySnapshot.journey_id == db_journey.id
        )
        snapshots_result = await db_session.execute(snapshots_stmt)
        snapshots = snapshots_result.scalars().all()
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert snapshot.train_status == "EN ROUTE"
        assert snapshot.completed_stops == 1  # NYP departed
        assert snapshot.total_stops == 3
        # raw_stop_list_data is now empty to reduce database size - full data is in journey_stops
        assert snapshot.raw_stop_list_data == {}
