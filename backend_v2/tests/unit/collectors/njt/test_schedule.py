"""
Tests for NJ Transit schedule discovery collector.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import ScheduleDiscoveryCollector
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture
def mock_njt_client():
    """Create a mock NJ Transit client."""
    return MagicMock(spec=NJTransitClient)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def schedule_collector(mock_njt_client):
    """Create a schedule discovery collector."""
    return ScheduleDiscoveryCollector(mock_njt_client)


@pytest.mark.asyncio
async def test_discover_station_schedule_new_trains(
    schedule_collector, mock_njt_client, mock_session
):
    """Test discovering new scheduled trains."""
    # Mock schedule API response
    future_time = now_et() + timedelta(hours=3)
    mock_njt_client.get_train_schedule = AsyncMock(
        return_value=[
            {
                "TRAIN_ID": "3923",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": future_time.strftime("%m/%d/%Y %I:%M:%S %p"),
                "BACKCOLOR": "#EE4B2B",
            },
            {
                "TRAIN_ID": "3925",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": (future_time + timedelta(hours=1)).strftime(
                    "%m/%d/%Y %I:%M:%S %p"
                ),
                "BACKCOLOR": "#EE4B2B",
            },
        ]
    )

    # No existing journeys
    mock_session.scalar.return_value = None

    result = await schedule_collector.discover_station_schedule(mock_session, "NY")

    assert result["trains_discovered"] == 2
    assert result["new_trains"] == 2
    assert mock_session.add.call_count == 2

    # Verify journey was created correctly
    added_journey = mock_session.add.call_args_list[0][0][0]
    assert isinstance(added_journey, TrainJourney)
    assert added_journey.train_id == "3923"
    assert added_journey.data_source_type == "schedule"
    assert added_journey.schedule_collected_at is not None


@pytest.mark.asyncio
async def test_discover_station_schedule_skip_past_trains(
    schedule_collector, mock_njt_client, mock_session
):
    """Test that past trains are skipped."""
    # Mock schedule API response with past train
    past_time = now_et() - timedelta(hours=2)
    mock_njt_client.get_train_schedule = AsyncMock(
        return_value=[
            {
                "TRAIN_ID": "3923",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": past_time.strftime("%m/%d/%Y %I:%M:%S %p"),
                "BACKCOLOR": "#EE4B2B",
            }
        ]
    )

    result = await schedule_collector.discover_station_schedule(mock_session, "NY")

    assert result["trains_discovered"] == 1
    assert result["new_trains"] == 0
    assert mock_session.add.call_count == 0


@pytest.mark.asyncio
async def test_discover_station_schedule_skip_amtrak(
    schedule_collector, mock_njt_client, mock_session
):
    """Test that Amtrak trains are skipped."""
    future_time = now_et() + timedelta(hours=3)
    mock_njt_client.get_train_schedule = AsyncMock(
        return_value=[
            {
                "TRAIN_ID": "A123",  # Amtrak train
                "LINE": "AC",
                "LINE_NAME": "Acela",
                "DESTINATION": "Boston",
                "SCHED_DEP_DATE": future_time.strftime("%m/%d/%Y %I:%M:%S %p"),
            }
        ]
    )

    result = await schedule_collector.discover_station_schedule(mock_session, "NY")

    assert result["trains_discovered"] == 1
    assert result["new_trains"] == 0
    assert mock_session.add.call_count == 0


@pytest.mark.asyncio
async def test_discover_station_schedule_existing_realtime(
    schedule_collector, mock_njt_client, mock_session
):
    """Test that existing realtime trains are not updated."""
    future_time = now_et() + timedelta(hours=3)
    mock_njt_client.get_train_schedule = AsyncMock(
        return_value=[
            {
                "TRAIN_ID": "3923",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": future_time.strftime("%m/%d/%Y %I:%M:%S %p"),
            }
        ]
    )

    # Mock existing realtime journey
    existing_journey = MagicMock()
    existing_journey.data_source_type = "realtime"
    mock_session.scalar.return_value = existing_journey

    result = await schedule_collector.discover_station_schedule(mock_session, "NY")

    assert result["trains_discovered"] == 1
    assert result["new_trains"] == 0
    assert mock_session.add.call_count == 0