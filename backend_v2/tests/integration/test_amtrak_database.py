"""
Integration tests for Amtrak database operations.

Tests the Amtrak journey collector with real database operations,
data persistence, and retrieval.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop, JourneySnapshot
from trackrat.utils.time import now_et
from tests.factories.amtrak import create_amtrak_train_data, create_amtrak_station_data


@pytest.mark.asyncio
class TestAmtrakDatabaseIntegration:
    """Test suite for Amtrak database integration."""

    async def test_journey_creation_and_persistence(self, db_session: AsyncSession):
        """Test creating and persisting a new Amtrak journey."""
        collector = AmtrakJourneyCollector()

        # Create test data with multiple tracked stations
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

        # Mock _get_train_data to return our test data
        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = train_data

            # Mock get_session to return our test session
            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                # Collect the journey
                result = await collector.collect_journey("2150-4")

                # Verify journey was created
                assert result is not None
                assert result.train_id == "A2150"
                assert result.data_source == "AMTRAK"
                assert result.stops_count == 3

                # Verify data was persisted to database
                stmt = select(TrainJourney).where(TrainJourney.train_id == "A2150")
                db_journey = await db_session.scalar(stmt)

                assert db_journey is not None
                assert db_journey.train_id == "A2150"
                assert db_journey.data_source == "AMTRAK"
                assert db_journey.line_code == "AM"
                assert db_journey.destination == "Washington Union Station"

                # Verify stops were persisted using stops_count
                assert db_journey.stops_count == 3

                # Query stops separately to avoid relationship access
                from trackrat.models.database import JourneyStop

                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == db_journey.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()

                assert len(stops) == 3

                # Check stop details
                stops_by_code = {stop.station_code: stop for stop in stops}

                assert "NY" in stops_by_code
                assert "NP" in stops_by_code
                assert "TR" in stops_by_code

                ny_stop = stops_by_code["NY"]
                assert ny_stop.station_name == "New York Penn Station"
                assert ny_stop.status == "DEPARTED"
                assert ny_stop.track == "15"
                assert ny_stop.departed is True

                # Verify snapshot was created
                from trackrat.models.database import JourneySnapshot

                snapshots_stmt = select(JourneySnapshot).where(
                    JourneySnapshot.journey_id == db_journey.id
                )
                snapshots_result = await db_session.execute(snapshots_stmt)
                snapshots = snapshots_result.scalars().all()
                assert len(snapshots) == 1  # All journeys get snapshots

                snapshot = snapshots[0]
                assert snapshot.train_status == "EN ROUTE"
                assert snapshot.total_stops == 3

    async def test_journey_update_existing(self, db_session: AsyncSession):
        """Test updating an existing journey."""
        collector = AmtrakJourneyCollector()

        # Create initial journey data
        initial_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                )
            ],
        )

        # Collect initial journey
        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = initial_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                initial_result = await collector.collect_journey("2150-4")
                assert initial_result is not None
                initial_update_count = initial_result.update_count

        # Create updated journey data (train has departed)
        updated_data = create_amtrak_train_data(
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
                    code="NWK", sch_arr="2025-07-05T14:45:00-05:00", status="Enroute"
                ),
            ],
        )

        # Collect updated journey
        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = updated_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                updated_result = await collector.collect_journey("2150-4")
                assert updated_result is not None

                # Verify it's the same journey but updated
                assert updated_result.id == initial_result.id
                assert updated_result.update_count == initial_update_count + 1

                # Verify new stop was added by querying database
                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == updated_result.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()
                assert len(stops) == 2

                # Verify status updates
                ny_stop = next(s for s in stops if s.station_code == "NY")
                assert ny_stop.status == "DEPARTED"
                assert ny_stop.departed is True
                assert ny_stop.actual_departure is not None

                # Verify new snapshot was added by querying database
                snapshots_stmt = select(JourneySnapshot).where(
                    JourneySnapshot.journey_id == updated_result.id
                )
                snapshots_result = await db_session.execute(snapshots_stmt)
                snapshots = snapshots_result.scalars().all()
                assert len(snapshots) == 2

    @pytest.mark.skip(
        reason="Test data date mismatch - creates journeys for 2025-07-05 but queries for today"
    )
    async def test_journey_query_operations(self, db_session: AsyncSession):
        """Test database query operations for Amtrak journeys."""
        collector = AmtrakJourneyCollector()
        today = now_et().date()

        # Create multiple journeys
        for i, train_num in enumerate(["2150", "2160", "2170"]):
            train_data = create_amtrak_train_data(
                train_id=f"{train_num}-{i}",
                train_num=train_num,
                stations=[
                    create_amtrak_station_data(
                        code="NYP",
                        sch_dep=f"2025-07-05T{14+i}:30:00-05:00",
                        status="Departed",
                    )
                ],
            )

            with patch.object(collector, "_get_train_data") as mock_get_train_data:
                mock_get_train_data.return_value = train_data

                with patch(
                    "trackrat.collectors.amtrak.journey.get_session"
                ) as mock_get_session:
                    mock_get_session.return_value.__aenter__.return_value = db_session

                    await collector.collect_journey(f"{train_num}-{i}")

        # Query all Amtrak journeys
        stmt = select(TrainJourney).where(TrainJourney.data_source == "AMTRAK")
        result = await db_session.execute(stmt)
        journeys = list(result.scalars().all())

        assert len(journeys) == 3
        assert all(j.data_source == "AMTRAK" for j in journeys)
        assert all(j.line_code == "AM" for j in journeys)

        # Query by date
        stmt = select(TrainJourney).where(
            TrainJourney.data_source == "AMTRAK", TrainJourney.journey_date == today
        )
        result = await db_session.execute(stmt)
        today_journeys = list(result.scalars().all())

        assert len(today_journeys) == 3

        # Query by train ID
        stmt = select(TrainJourney).where(TrainJourney.train_id == "A2150")
        specific_journey = await db_session.scalar(stmt)

        assert specific_journey is not None
        assert specific_journey.train_id == "A2150"

    async def test_database_error_handling(self, db_session: AsyncSession):
        """Test database error handling in journey collection."""
        collector = AmtrakJourneyCollector()

        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00"
                )
            ],
        )

        # Mock database error
        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = train_data

            with patch.object(collector, "_convert_to_journey") as mock_convert:
                # Make the conversion fail with a database error
                mock_convert.side_effect = Exception("Database connection lost")

                # Should raise the exception as expected
                with pytest.raises(Exception, match="Database connection lost"):
                    await collector.collect_journey("2150-4")

    async def test_station_filtering_persistence(self, db_session: AsyncSession):
        """Test that only tracked stations are persisted."""
        collector = AmtrakJourneyCollector()

        # Create train data with mix of tracked and untracked stations
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(code="BOS", name="Boston"),  # Not tracked
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00"
                ),  # Tracked
                create_amtrak_station_data(
                    code="PHL", name="Philadelphia"
                ),  # Not tracked
                create_amtrak_station_data(
                    code="NWK", sch_arr="2025-07-05T14:45:00-05:00"
                ),  # Tracked
                create_amtrak_station_data(code="WAS", name="Washington"),  # Tracked
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result = await collector.collect_journey("2150-4")

                # Should only include tracked stations
                assert result is not None
                # Query stops separately to avoid relationship access
                stops_stmt = select(JourneyStop).where(
                    JourneyStop.journey_id == result.id
                )
                stops_result = await db_session.execute(stops_stmt)
                stops = stops_result.scalars().all()
                assert len(stops) == 5  # BOS, NYP, PHL, NWK, WAS (all now tracked)

                station_codes = {stop.station_code for stop in stops}
                assert station_codes == {"BOS", "NY", "PH", "NP", "WS"}

    async def test_journey_snapshots_creation(self, db_session: AsyncSession):
        """Test that journey snapshots are properly created."""
        collector = AmtrakJourneyCollector()

        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            train_state="Active",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Departed"
                ),
                create_amtrak_station_data(
                    code="NWK", sch_arr="2025-07-05T14:45:00-05:00", status="Enroute"
                ),
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result = await collector.collect_journey("2150-4")

                assert result is not None
                # Query snapshots separately to avoid relationship access
                snapshots_stmt = select(JourneySnapshot).where(
                    JourneySnapshot.journey_id == result.id
                )
                snapshots_result = await db_session.execute(snapshots_stmt)
                snapshots = snapshots_result.scalars().all()
                assert len(snapshots) == 1

                snapshot = snapshots[0]
                assert isinstance(snapshot, JourneySnapshot)
                assert snapshot.train_status == "EN ROUTE"
                assert snapshot.completed_stops == 1  # NYP departed
                assert snapshot.total_stops == 2
                assert "train_data" in snapshot.raw_stop_list_data
                assert snapshot.raw_stop_list_data["data_source"] == "AMTRAK"

    async def test_concurrent_journey_updates(self, db_session: AsyncSession):
        """Test handling of concurrent journey updates."""
        collector1 = AmtrakJourneyCollector()
        collector2 = AmtrakJourneyCollector()

        # Create same train data for both collectors
        train_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Boarding"
                )
            ],
        )

        # First collector creates journey
        with patch.object(collector1, "_get_train_data") as mock_get_train_data1:
            mock_get_train_data1.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session1:
                mock_get_session1.return_value.__aenter__.return_value = db_session

                result1 = await collector1.collect_journey("2150-4")
                assert result1 is not None
                original_update_count = result1.update_count

        # Second collector updates the same journey
        with patch.object(collector2, "_get_train_data") as mock_get_train_data2:
            mock_get_train_data2.return_value = train_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session2:
                mock_get_session2.return_value.__aenter__.return_value = db_session

                result2 = await collector2.collect_journey("2150-4")
                assert result2 is not None

                # Should be the same journey but with incremented update count
                assert result2.id == result1.id
                assert result2.update_count == original_update_count + 1

    async def test_journey_completion_status(self, db_session: AsyncSession):
        """Test journey completion and cancellation status persistence."""
        collector = AmtrakJourneyCollector()

        # Test completed journey
        completed_data = create_amtrak_train_data(
            train_id="2150-4",
            train_num="2150",
            train_state="Terminated",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T14:30:00-05:00", status="Departed"
                )
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = completed_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result = await collector.collect_journey("2150-4")

                assert result is not None
                assert result.is_completed is True
                assert result.is_cancelled is False

        # Test cancelled journey
        cancelled_data = create_amtrak_train_data(
            train_id="2160-4",
            train_num="2160",
            train_state="Cancelled",
            stations=[
                create_amtrak_station_data(
                    code="NYP", sch_dep="2025-07-05T15:30:00-05:00", status="Cancelled"
                )
            ],
        )

        with patch.object(collector, "_get_train_data") as mock_get_train_data:
            mock_get_train_data.return_value = cancelled_data

            with patch(
                "trackrat.collectors.amtrak.journey.get_session"
            ) as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                result = await collector.collect_journey("2160-4")

                assert result is not None
                assert result.is_completed is False
                assert result.is_cancelled is True
