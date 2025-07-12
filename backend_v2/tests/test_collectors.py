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


@pytest.mark.skip(
    reason="Test database isolation issue - train exists from previous test run"
)
@pytest.mark.asyncio
async def test_train_discovery_collector(db_session, mock_njt_client):
    """Test train discovery collector."""
    collector = TrainDiscoveryCollector(mock_njt_client)

    # Override discovery stations for testing
    collector.DISCOVERY_STATIONS = ["NY"]

    result = await collector.collect(db_session)

    assert result["stations_processed"] == 1
    assert result["total_discovered"] == 1
    assert result["total_new"] == 1

    # Verify journey was created
    from sqlalchemy import select

    result = await db_session.execute(select(TrainJourney).filter_by(train_id="3840"))
    journey = result.scalar()

    assert journey is not None
    assert journey.train_id == "3840"
    assert journey.line_code == "NE"
    assert journey.destination == "Trenton"
    assert journey.has_complete_journey is False
