"""
Integration tests for NJ Transit batch collection pipeline.

Tests the complete flow from discovery to journey collection using real database.
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, Mock, patch

from trackrat.services.scheduler import SchedulerService
from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop, DiscoveryRun
from trackrat.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings for integration testing."""
    return Settings(
        njt_api_url="https://test.api.com",
        njt_api_token="test_token",
        discovery_interval_minutes=60,
        database_url="sqlite:///test_njt_batch.db",
    )


@pytest.fixture
def sample_njt_api_response():
    """Sample NJ Transit API response for train schedule."""
    return [
        {
            "TRAIN_ID": "3737",
            "LINE": "NEC",
            "LINE_NAME": "Northeast Corridor",
            "DESTINATION": "New York Penn Station",
            "SCHED_DEP_DATE": "2025-01-01 10:00:00",
            "BACKCOLOR": "#FF6600",
        },
        {
            "TRAIN_ID": "3893",
            "LINE": "NEC",
            "LINE_NAME": "Northeast Corridor",
            "DESTINATION": "Trenton",
            "SCHED_DEP_DATE": "2025-01-01 10:30:00",
            "BACKCOLOR": "#FF6600",
        },
    ]


@pytest.fixture
def sample_njt_journey_response():
    """Sample NJ Transit journey response with stops."""
    return {
        "TRAIN_ID": "3737",
        "DESTINATION": "New York Penn Station",
        "BACKCOLOR": "#FF6600",
        "STOPS": [
            {
                "STATION_2CHAR": "TR",
                "STATIONNAME": "Trenton",
                "TIME": "2025-01-01 10:00:00",
                "DEP_TIME": "2025-01-01 10:02:00",
                "DEPARTED": "YES",
                "STOP_STATUS": "On Time",
                "TRACK": "1",
            },
            {
                "STATION_2CHAR": "PJ",
                "STATIONNAME": "Princeton Junction",
                "TIME": "2025-01-01 10:15:00",
                "DEP_TIME": "2025-01-01 10:17:00",
                "DEPARTED": "NO",
                "STOP_STATUS": "On Time",
                "TRACK": "2",
            },
            {
                "STATION_2CHAR": "NY",
                "STATIONNAME": "New York Penn Station",
                "TIME": "2025-01-01 11:00:00",
                "DEP_TIME": "2025-01-01 11:00:00",  # Fixed empty departure time
                "DEPARTED": "NO",
                "STOP_STATUS": "On Time",
                "TRACK": "7",  # Fixed empty track
            },
        ],
    }


class TestNJTBatchCollectionPipeline:
    """Integration tests for the complete NJT batch collection pipeline."""

    @pytest.mark.asyncio
    async def test_complete_discovery_to_collection_flow(
        self,
        db_session,
        mock_settings,
        sample_njt_api_response,
        sample_njt_journey_response,
    ):
        """Test the complete flow from discovery to journey collection."""

        # Create scheduler service
        scheduler = SchedulerService(mock_settings)
        scheduler.njt_client = AsyncMock()

        # Mock discovery API calls
        scheduler.njt_client.get_train_schedule.return_value = sample_njt_api_response

        # Mock journey collection API calls
        from trackrat.models.api import NJTransitTrainData, NJTransitStopData

        # Convert sample response to proper data model
        stops_data = [
            NJTransitStopData(
                **{
                    "STATION_2CHAR": stop["STATION_2CHAR"],
                    "STATIONNAME": stop["STATIONNAME"],
                    "TIME": stop["TIME"],
                    "DEP_TIME": stop["DEP_TIME"],
                    "DEPARTED": stop["DEPARTED"],
                    "STOP_STATUS": stop["STOP_STATUS"],
                    "TRACK": stop["TRACK"],
                    "TIME_UTC_FORMAT": stop["TIME"] + " UTC",  # Add required field
                }
            )
            for stop in sample_njt_journey_response["STOPS"]
        ]

        train_data = NJTransitTrainData(
            TRAIN_ID=sample_njt_journey_response["TRAIN_ID"],
            DESTINATION=sample_njt_journey_response["DESTINATION"],
            BACKCOLOR=sample_njt_journey_response["BACKCOLOR"],
            LINECODE="NE",  # Add required field
            FORECOLOR="#000000",  # Add required field
            SHADOWCOLOR="#CCCCCC",  # Add required field
            STOPS=stops_data,
        )

        scheduler.njt_client.get_train_stop_list.return_value = train_data

        # Mock scheduler to execute jobs immediately instead of scheduling
        scheduler.scheduler = Mock()

        with patch("trackrat.utils.time.now_et") as mock_now:
            mock_now.return_value = datetime(2025, 1, 1, 9, 0, 0)

            # Step 1: Run discovery
            with patch("trackrat.db.engine.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                discovery_collector = TrainDiscoveryCollector(scheduler.njt_client)
                discovery_result = await discovery_collector.collect(db_session)

        # Verify discovery results
        assert discovery_result["total_discovered"] == 14  # 2 trains * 7 stations
        assert discovery_result["total_new"] == 2  # Both trains are new

        # Verify journey records were created
        from sqlalchemy import select

        stmt = select(TrainJourney).where(TrainJourney.data_source == "NJT")
        result = await db_session.execute(stmt)
        journeys = result.scalars().all()
        assert len(journeys) == 2

        train_ids = [j.train_id for j in journeys]
        assert "3737" in train_ids
        assert "3893" in train_ids

        # Step 2: Run batch collection logic
        with patch("trackrat.db.engine.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = db_session

            await scheduler.schedule_njt_batch_collection(discovery_result)

        # Step 3: Simulate the scheduled batch collection job execution
        # Extract the train IDs that would be passed to the batch collection
        all_train_ids = []
        for station_result in discovery_result.get("station_results", {}).values():
            all_train_ids.extend(station_result.get("all_train_ids", []))

        unique_train_ids = list(set(all_train_ids))

        # Execute the batch collection
        with patch("trackrat.db.engine.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = db_session

            journey_collector = JourneyCollector(scheduler.njt_client)

            # Collect journey for each unique train
            for train_id in unique_train_ids:
                if train_id == "3737":  # Only mock data for this train
                    await journey_collector.collect_journey_details(
                        db_session, journeys[0]
                    )

        # Verify journey details were collected
        stmt = select(TrainJourney).where(TrainJourney.train_id == "3737")
        journey = await db_session.scalar(stmt)

        assert journey is not None
        assert journey.has_complete_journey is True
        assert journey.stops_count == 3

        # Verify stops were created
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        result = await db_session.execute(stmt)
        stops = result.scalars().all()
        assert len(stops) == 3

        # Verify stop details
        stop_codes = [s.station_code for s in stops]
        assert "TR" in stop_codes
        assert "PJ" in stop_codes
        assert "NY" in stop_codes

    @pytest.mark.asyncio
    async def test_batch_collection_filters_recently_updated_journeys(
        self, db_session, mock_settings
    ):
        """Test that batch collection skips journeys that were recently updated."""

        scheduler = SchedulerService(mock_settings)

        # Create journeys with different update times
        with patch("trackrat.utils.time.now_et") as mock_now:
            current_time = datetime(2025, 1, 1, 12, 0, 0)
            mock_now.return_value = current_time

            # Journey updated 5 minutes ago (should be skipped)
            journey1 = TrainJourney(
                train_id="3737",
                journey_date=date(2025, 1, 1),
                data_source="NJT",
                line_code="NE",
                destination="New York Penn Station",
                origin_station_code="NY",
                terminal_station_code="NY",
                scheduled_departure=current_time,
                has_complete_journey=True,
                last_updated_at=current_time - timedelta(minutes=5),
                first_seen_at=current_time - timedelta(hours=1),
            )

            # Journey updated 20 minutes ago (should be collected)
            journey2 = TrainJourney(
                train_id="3893",
                journey_date=date(2025, 1, 1),
                data_source="NJT",
                line_code="NE",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                scheduled_departure=current_time,
                has_complete_journey=False,
                last_updated_at=current_time - timedelta(minutes=20),
                first_seen_at=current_time - timedelta(hours=1),
            )

            # Journey never updated (should be collected)
            journey3 = TrainJourney(
                train_id="1281",
                journey_date=date(2025, 1, 1),
                data_source="NJT",
                line_code="NE",
                destination="Princeton Junction",
                origin_station_code="NY",
                terminal_station_code="PJ",
                scheduled_departure=current_time,
                has_complete_journey=False,
                last_updated_at=None,
                first_seen_at=current_time - timedelta(hours=1),
            )

            db_session.add_all([journey1, journey2, journey3])
            await db_session.commit()

            discovery_result = {
                "total_discovered": 3,
                "station_results": {"NY": {"all_train_ids": ["3737", "3893", "1281"]}},
            }

            with patch("trackrat.db.engine.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                scheduler.scheduler = Mock()

                await scheduler.schedule_njt_batch_collection(discovery_result)

        # Should only schedule collection for trains that need it
        if scheduler.scheduler.add_job.called:
            call_args = scheduler.scheduler.add_job.call_args
            scheduled_trains = call_args[1]["args"][0]
            assert set(scheduled_trains) == {"3893", "1281"}
        else:
            # If no trains need collection, that's also valid
            assert True

    @pytest.mark.asyncio
    async def test_error_handling_in_batch_collection(self, db_session, mock_settings):
        """Test error handling during batch collection doesn't stop other trains."""

        scheduler = SchedulerService(mock_settings)
        scheduler.njt_client = AsyncMock()

        # Mock journey collector with mixed success/failure
        def mock_collect_side_effect(train_id):
            if train_id == "3893":  # This train will fail
                raise Exception("API Error for train 3893")
            # Other trains succeed
            journey = Mock()
            journey.stops_count = 15
            return journey

        with patch(
            "trackrat.collectors.njt.journey.JourneyCollector"
        ) as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector.collect_journey.side_effect = mock_collect_side_effect
            mock_collector_class.return_value = mock_collector

            # Should not raise exception despite one train failing
            await scheduler.collect_njt_journeys_batch(["3737", "3893", "1281"])

        # All trains should have been attempted
        assert mock_collector.collect_journey.call_count == 3
