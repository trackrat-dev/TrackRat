"""
Integration tests for Amtrak scheduler integration.

Tests how Amtrak collectors work with the scheduler system,
including timing, coordination, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, Mock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from trackrat.collectors.amtrak.discovery import AmtrakDiscoveryCollector
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop, JourneySnapshot
from trackrat.utils.time import now_et
from tests.factories.amtrak import create_amtrak_train_data, create_amtrak_station_data


@pytest.mark.asyncio
class TestAmtrakSchedulerIntegration:
    """Test suite for Amtrak scheduler integration."""

    async def test_discovery_to_journey_workflow(self, db_session: AsyncSession):
        """Test the complete workflow from discovery to journey collection."""
        discovery_collector = AmtrakDiscoveryCollector()
        journey_collector = AmtrakJourneyCollector()

        # Mock Amtrak API data
        mock_train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                ),
                create_amtrak_station_data(
                    code="NWK", sch_arr="2025-07-05T14:45:00-05:00", status="Enroute"
                ),
            ],
        )

        # Convert to proper format - discovery expects AmtrakTrainData objects
        mock_api_response = {
            "2150": [mock_train_data]  # Already an AmtrakTrainData object
        }

        # Step 1: Discovery phase
        with patch.object(discovery_collector.client, "get_all_trains") as mock_get_all:
            mock_get_all.return_value = mock_api_response

            trains = await discovery_collector.discover_trains()

            assert len(trains) == 1
            assert trains[0] == "2150-4"

        # Step 2: Journey collection phase
        # Journey collector also needs the same format
        with patch.object(journey_collector.client, "get_all_trains") as mock_get_all:
            mock_get_all.return_value = mock_api_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                journey = await journey_collector.collect_journey("2150-4")

                assert journey is not None
                assert journey.train_id == "A2150"
                # Use stops_count instead of lazy loading
                assert journey.stops_count == 2

        # Verify journey is in database
        from sqlalchemy import select

        stmt = select(TrainJourney).where(TrainJourney.train_id == "A2150")
        db_journey = await db_session.scalar(stmt)

        assert db_journey is not None
        assert db_journey.data_source == "AMTRAK"

    async def test_concurrent_collection_handling(self, db_session: AsyncSession):
        """Test handling of concurrent collection requests."""
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

        # Mock both collectors to return same data
        with (
            patch.object(collector1, "_get_train_data") as mock1,
            patch.object(collector2, "_get_train_data") as mock2,
        ):

            mock1.return_value = train_data
            mock2.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                # Collect same train with both collectors
                result1 = await collector1.collect_journey("2150-4")
                result2 = await collector2.collect_journey("2150-4")

                # Both should succeed
                assert result1 is not None
                assert result2 is not None

                # Should be same journey but with final update count reflecting both updates
                assert result1.id == result2.id
                # Both references point to the same updated object
                assert result1.update_count == result2.update_count == 2

    async def test_discovery_scheduling_frequency(self):
        """Test that discovery collector can be run repeatedly."""
        collector = AmtrakDiscoveryCollector()

        # Mock stable API response
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00"
                )
            ],
        )

        mock_response = {"2150": [train_data]}  # Use AmtrakTrainData object

        with patch.object(collector.client, "get_all_trains") as mock_get_all:
            mock_get_all.return_value = mock_response

            # Run discovery multiple times (simulating scheduled runs)
            results = []
            for _ in range(3):
                trains = await collector.discover_trains()
                results.append(trains)

            # Should consistently return same train
            assert all(len(trains) == 1 for trains in results)
            assert all(trains[0] == "2150-4" for trains in results)

            # Should have called API each time
            assert mock_get_all.call_count == 3

    async def test_journey_collection_scheduling(self, db_session: AsyncSession):
        """Test that journey collection can be run repeatedly for updates."""
        collector = AmtrakJourneyCollector()

        # Initial state - train boarding
        initial_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                )
            ],
        )

        # Updated state - train departed
        updated_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP",
                    sch_dep="2025-07-05T14:30:00-05:00",
                    actual_dep="2025-07-05T14:32:00-05:00",
                    status="Departed",
                )
            ],
        )

        # First collection (initial state)
        with patch.object(collector, "_get_train_data") as mock_get_data:
            mock_get_data.return_value = initial_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result1 = await collector.collect_journey("2150-4")
                assert result1 is not None
                assert result1.update_count == 1

                # Check initial status by querying stops
                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == result1.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()
                ny_stop = next(s for s in stops if s.station_code == "NY")
                assert ny_stop.raw_amtrak_status == "Boarding"  # Raw status, not mapped
                assert ny_stop.has_departed_station is False

        # Second collection (updated state)
        with patch.object(collector, "_get_train_data") as mock_get_data:
            mock_get_data.return_value = updated_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result2 = await collector.collect_journey("2150-4")
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

    async def test_scheduler_data_freshness(self, db_session: AsyncSession):
        """Test that scheduler maintains data freshness."""
        collector = AmtrakJourneyCollector()

        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                )
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_data:
            mock_get_data.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
                    # Set initial time
                    start_time = datetime(2025, 7, 5, 14, 0, 0)
                    mock_now.return_value = start_time

                    result = await collector.collect_journey("2150-4")
                    assert result is not None

                    initial_updated_at = result.last_updated_at

                    # Simulate time passing and another collection
                    later_time = start_time + timedelta(minutes=15)
                    mock_now.return_value = later_time

                    result2 = await collector.collect_journey("2150-4")
                    assert result2 is not None

                    # Should have updated timestamp
                    assert result2.last_updated_at > initial_updated_at

    async def test_scheduler_bulk_operations(self, db_session: AsyncSession):
        """Test scheduler handling multiple trains efficiently."""
        discovery_collector = AmtrakDiscoveryCollector()
        journey_collector = AmtrakJourneyCollector()

        # Create multiple trains
        train_data_list = []
        for i in range(5):
            train_num = str(2150 + i)
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-4",
                train_num=train_num,
                stations=[
                    create_amtrak_station_data(
                        code="NYP",
                        sch_dep=f"2025-07-05T{14+i}:30:00-05:00",
                        status="Boarding",
                    )
                ],
            )
            train_data_list.append(train_data)

        # Mock discovery response
        mock_response = {}
        for i, train_data in enumerate(train_data_list):
            train_num = str(2150 + i)
            mock_response[train_num] = [train_data]  # Use AmtrakTrainData objects

        # Discovery phase
        with patch.object(
            discovery_collector.client, "get_all_trains"
        ) as mock_discovery:
            mock_discovery.return_value = mock_response

            discovered_trains = await discovery_collector.discover_trains()
            assert len(discovered_trains) == 5

        # Journey collection phase for all discovered trains
        collected_journeys = []

        with patch.object(journey_collector.client, "get_all_trains") as mock_journey:
            mock_journey.return_value = mock_response

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                for train_id in discovered_trains:
                    journey = await journey_collector.collect_journey(train_id)
                    if journey:
                        collected_journeys.append(journey)

        # Verify all journeys collected
        assert len(collected_journeys) == 5
        assert all(j.data_source == "AMTRAK" for j in collected_journeys)

        # Verify database contains all journeys
        from sqlalchemy import select

        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        db_journeys = list(result.scalars().all())

        assert len(db_journeys) == 5

    async def test_scheduler_memory_efficiency(self):
        """Test that collectors don't hold unnecessary data between runs."""
        collector = AmtrakJourneyCollector()

        # Verify collector starts clean
        assert not hasattr(collector, "_cached_data")

        # Mock some data
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00"
                )
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_data:
            mock_get_data.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_session = AsyncMock()

                # Mock synchronous database operations
                mock_session.add = Mock()

                mock_get_session.return_value.__aenter__.return_value = mock_session

                # Run collection
                await collector.collect_journey("2150-4")

                # Collector should not cache the data persistently
                assert not hasattr(collector, "_cached_journeys")
                assert not hasattr(collector, "_cached_responses")

    async def test_scheduler_run_method_interface(self):
        """Test that collectors implement the scheduler interface correctly."""
        discovery_collector = AmtrakDiscoveryCollector()
        journey_collector = AmtrakJourneyCollector()

        # Test discovery collector run method
        with patch.object(discovery_collector, "discover_trains") as mock_discover:
            mock_discover.return_value = ["2150-4", "2160-4"]

            result = await discovery_collector.run()

            assert isinstance(result, dict)
            assert "discovered_trains" in result
            assert "data_source" in result
            assert result["data_source"] == "AMTRAK"
            assert result["discovered_trains"] == 2

        # Test journey collector run method
        result = await journey_collector.run()

        assert isinstance(result, dict)
        assert "trains_processed" in result
        assert "successful" in result
        assert "failed" in result
        assert "data_source" in result
        assert result["data_source"] == "AMTRAK"
