"""
Tests for data collectors.
"""

import pytest
from datetime import date
from unittest.mock import Mock
from sqlalchemy import select

from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et, parse_njt_time


@pytest.mark.asyncio
async def test_train_discovery_collector(db_session):
    """Test train discovery collector."""
    from unittest.mock import AsyncMock

    # Use unique train ID to avoid conflicts
    import time

    unique_train_id = f"TEST{int(time.time() * 1000) % 100000}"

    # Create a properly configured mock client
    mock_njt_client = AsyncMock()

    # Configure async mock return value for get_train_schedule_with_stops
    async def mock_get_schedule(station_code):
        return {
            "ITEMS": [
                {
                    "TRAIN_ID": unique_train_id,
                    "LINE": "NE",
                    "LINE_NAME": "Northeast Corridor",
                    "DESTINATION": "Trenton",
                    "SCHED_DEP_DATE": now_et().strftime("%d-%b-%Y %I:%M:%S %p"),
                    "BACKCOLOR": "#F7505E",
                }
            ]
        }

    mock_njt_client.get_train_schedule_with_stops = mock_get_schedule
    mock_njt_client.close = AsyncMock()
    mock_njt_client.__aenter__ = AsyncMock(return_value=mock_njt_client)
    mock_njt_client.__aexit__ = AsyncMock(return_value=None)

    # Patch DISCOVERY_STATIONS to only test NY, and patch get_session to use test db_session
    from unittest.mock import patch
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_session():
        yield db_session

    with (
        patch("trackrat.collectors.njt.discovery.DISCOVERY_STATIONS", ["NY"]),
        patch("trackrat.collectors.njt.discovery.get_session", mock_get_session),
    ):
        collector = TrainDiscoveryCollector(mock_njt_client)
        result = await collector.collect()

    assert result["stations_processed"] == 1
    assert result["total_discovered"] == 1
    assert result["total_new"] == 1

    # Verify journey was created with unique ID
    from sqlalchemy import select

    query_result = await db_session.execute(
        select(TrainJourney).filter_by(train_id=unique_train_id)
    )
    journey = query_result.scalar()

    assert journey is not None
    assert journey.train_id == unique_train_id
    assert journey.line_code == "NE"
    assert journey.destination == "Trenton"
    assert journey.has_complete_journey is False
