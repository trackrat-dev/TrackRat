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
