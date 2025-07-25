"""
Integration test for schedule and realtime data merging.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.collectors.njt.schedule import ScheduleDiscoveryCollector
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et


@pytest.mark.asyncio
async def test_schedule_to_realtime_upgrade(db_session, mock_njt_client):
    """Test that schedule trains get upgraded to realtime when discovered."""
    # First, create a schedule train
    future_time = now_et() + timedelta(hours=2)
    journey = TrainJourney(
        train_id="3923",
        journey_date=future_time.date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=future_time,
        data_source="NJT",
        data_source_type="schedule",  # Start as schedule
        schedule_collected_at=now_et(),
        first_seen_at=now_et(),
        last_updated_at=now_et(),
        has_complete_journey=False,
        update_count=1,
    )
    db_session.add(journey)
    await db_session.commit()

    # Verify it's schedule type
    stmt = select(TrainJourney).where(TrainJourney.train_id == "3923")
    result = await db_session.execute(stmt)
    journey = result.scalar_one()
    assert journey.data_source_type == "schedule"

    # Mock realtime discovery response
    mock_njt_client.get_train_schedule_with_stops.return_value = {
        "ITEMS": [
            {
                "TRAIN_ID": "3923",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": future_time.strftime("%m/%d/%Y %I:%M:%S %p"),
                "TRACK": "7",
            }
        ]
    }

    # Run realtime discovery
    collector = TrainDiscoveryCollector(mock_njt_client)
    await collector.discover_station_trains(db_session, "NY")

    # Verify it's now realtime
    await db_session.refresh(journey)
    assert journey.data_source_type == "realtime"


@pytest.mark.asyncio
async def test_schedule_and_realtime_coexist(db_session, mock_njt_client):
    """Test that schedule and realtime trains can coexist."""
    current_time = now_et()

    # Create a realtime train (current)
    realtime_journey = TrainJourney(
        train_id="3921",
        journey_date=current_time.date(),
        line_code="NE",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=current_time + timedelta(minutes=30),
        data_source="NJT",
        data_source_type="realtime",
        first_seen_at=current_time,
        last_updated_at=current_time,
    )

    # Create a schedule train (future)
    schedule_journey = TrainJourney(
        train_id="3955",
        journey_date=current_time.date(),
        line_code="NE",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=current_time + timedelta(hours=6),
        data_source="NJT",
        data_source_type="schedule",
        schedule_collected_at=current_time,
        first_seen_at=current_time,
        last_updated_at=current_time,
    )

    db_session.add_all([realtime_journey, schedule_journey])
    await db_session.commit()

    # Query all NJT trains
    stmt = select(TrainJourney).where(TrainJourney.data_source == "NJT")
    result = await db_session.execute(stmt)
    journeys = list(result.scalars().all())

    assert len(journeys) == 2

    # Verify both types exist
    types = {j.data_source_type for j in journeys}
    assert "realtime" in types
    assert "schedule" in types
