"""
Test configuration and fixtures for TrackRat V2.
"""

import asyncio
import logging
import pytest
import structlog
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from trackrat.settings import Settings, get_settings
from trackrat.main import app
from trackrat.db.engine import get_db
from trackrat.models.database import Base
from trackrat.collectors.njt.client import NJTransitClient


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True, scope="session")
def setup_logging_for_tests():
    """Configure structlog to work with pytest's caplog fixture."""
    # Configure structlog once per session to avoid conflicts
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),  # Use console renderer for test-friendly format
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Don't cache to ensure fresh config
    )

    # Set the logging level to DEBUG for all tests
    logging.getLogger().setLevel(logging.DEBUG)


# Remove custom event_loop fixture to avoid deprecation warning
# pytest-asyncio will provide the default one


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        environment="testing",
        database_url=TEST_DATABASE_URL,
        njt_api_token="test_token",
        debug=False,
        discovery_interval_minutes=60,
        journey_update_interval_minutes=15,
        data_staleness_seconds=60,
    )


@pytest.fixture
async def db_engine(test_settings):
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=None,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def client(test_settings, db_session) -> TestClient:
    """Create a test client with dependency overrides."""
    # Clear settings cache and override settings
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Override database dependency
    async def get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = get_test_db

    # Disable scheduler for tests
    with (
        patch("trackrat.main.get_scheduler") as mock_scheduler,
        patch("trackrat.api.health.get_scheduler") as mock_health_scheduler,
        patch("trackrat.api.trains.NJTransitClient") as mock_njt_client,
    ):
        scheduler = Mock()
        scheduler.start = AsyncMock()
        scheduler.stop = AsyncMock()
        scheduler.get_status = Mock(
            return_value={"running": True, "jobs_count": 0, "active_tasks": []}
        )
        scheduler.scheduler = Mock()
        scheduler.scheduler.running = True
        mock_scheduler.return_value = scheduler
        mock_health_scheduler.return_value = scheduler

        # Mock NJTransit client
        mock_client = AsyncMock(spec=NJTransitClient)
        mock_client.close = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_njt_client.return_value = mock_client

        with TestClient(app) as client:
            yield client

    # Clean up dependency overrides and cache
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def mock_njt_client():
    """Create a mock NJ Transit client."""
    client = AsyncMock(spec=NJTransitClient)

    # Mock responses
    client.get_train_schedule_with_stops.return_value = {
        "ITEMS": [
            {
                "TRAIN_ID": "3840",
                "LINE": "NE",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": "05-Jul-2025 02:30:00 PM",
                "BACKCOLOR": "#F7505E",
            }
        ]
    }

    stop_list_response = Mock(
        TRAIN_ID="3840",
        LINECODE="NE",
        BACKCOLOR="#F7505E",
        FORECOLOR="white",
        SHADOWCOLOR="black",
        DESTINATION="Trenton",
        TRANSFERAT="",
        STOPS=[
            Mock(
                STATION_2CHAR="NY",
                STATIONNAME="New York Penn Station",
                TIME="05-Jul-2025 02:30:00 PM",
                PICKUP="",
                DROPOFF="",
                DEPARTED="NO",
                STOP_STATUS="OnTime",
                DEP_TIME="05-Jul-2025 02:30:00 PM",
                TIME_UTC_FORMAT="05-Jul-2025 06:30:00 PM",
                TRACK="7",
            ),
            Mock(
                STATION_2CHAR="NP",
                STATIONNAME="Newark Penn Station",
                TIME="05-Jul-2025 02:45:00 PM",
                PICKUP="",
                DROPOFF="",
                DEPARTED="NO",
                STOP_STATUS="OnTime",
                DEP_TIME="05-Jul-2025 02:47:00 PM",
                TIME_UTC_FORMAT="05-Jul-2025 06:45:00 PM",
                TRACK=None,
            ),
            Mock(
                STATION_2CHAR="TR",
                STATIONNAME="Trenton",
                TIME="05-Jul-2025 03:45:00 PM",
                PICKUP="",
                DROPOFF="",
                DEPARTED="NO",
                STOP_STATUS="OnTime",
                DEP_TIME="05-Jul-2025 03:45:00 PM",
                TIME_UTC_FORMAT="05-Jul-2025 07:45:00 PM",
                TRACK=None,
            ),
        ],
    )

    # Make dict() return a proper dictionary
    stop_list_response.dict.return_value = {
        "TRAIN_ID": "3840",
        "LINECODE": "NE",
        "BACKCOLOR": "#F7505E",
        "FORECOLOR": "white",
        "SHADOWCOLOR": "black",
        "DESTINATION": "Trenton",
        "TRANSFERAT": "",
        "STOPS": [
            {
                "STATION_2CHAR": "NY",
                "STATIONNAME": "New York Penn Station",
                "TIME": "05-Jul-2025 02:30:00 PM",
                "PICKUP": "",
                "DROPOFF": "",
                "DEPARTED": "NO",
                "STOP_STATUS": "OnTime",
                "DEP_TIME": "05-Jul-2025 02:30:00 PM",
                "TIME_UTC_FORMAT": "05-Jul-2025 06:30:00 PM",
                "TRACK": "7",
            },
            {
                "STATION_2CHAR": "NP",
                "STATIONNAME": "Newark Penn Station",
                "TIME": "05-Jul-2025 02:45:00 PM",
                "PICKUP": "",
                "DROPOFF": "",
                "DEPARTED": "NO",
                "STOP_STATUS": "OnTime",
                "DEP_TIME": "05-Jul-2025 02:47:00 PM",
                "TIME_UTC_FORMAT": "05-Jul-2025 06:45:00 PM",
                "TRACK": None,
            },
            {
                "STATION_2CHAR": "TR",
                "STATIONNAME": "Trenton",
                "TIME": "05-Jul-2025 03:45:00 PM",
                "PICKUP": "",
                "DROPOFF": "",
                "DEPARTED": "NO",
                "STOP_STATUS": "OnTime",
                "DEP_TIME": "05-Jul-2025 03:45:00 PM",
                "TIME_UTC_FORMAT": "05-Jul-2025 07:45:00 PM",
                "TRACK": None,
            },
        ],
    }

    client.get_train_stop_list.return_value = stop_list_response
    client.close = AsyncMock()

    # Make it work as async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    return client
