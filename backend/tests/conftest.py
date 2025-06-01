"""Shared pytest fixtures for TrackCast tests."""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Set environment variables for testing
os.environ["TRACKCAST_ENV"] = "test"
os.environ["TRACKCAST_CONFIG"] = os.path.join(os.path.dirname(__file__), "test_config.yaml")

# Monkey patch SQLAlchemy engine creation to work with SQLite
# This must be done before any imports
import sqlalchemy
original_create_engine = sqlalchemy.create_engine

def patched_create_engine(url, **kwargs):
    """Create an SQLAlchemy engine with SQLite compatibility."""
    if url.startswith('sqlite'):
        # Remove incompatible arguments for SQLite
        kwargs.pop('pool_size', None)
        kwargs.pop('max_overflow', None)
    return original_create_engine(url, **kwargs)

# Apply the patch
sqlalchemy.create_engine = patched_create_engine

# Now import the rest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from trackcast.config import load_config, settings
from trackcast.db.connection import Base, SessionLocal

# Create in-memory SQLite database URL for tests
TEST_DB_URL = "sqlite:///:memory:"

# Create the test engine
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

# Create a test session factory
TestSessionFactory = sessionmaker(bind=test_engine)
TestSession = scoped_session(TestSessionFactory)

# Set the database URL in settings to use SQLite
settings._settings.database.url = TEST_DB_URL

# Make sure njtransit_api settings exist (needed for data collector tests)
if not hasattr(settings._settings, "njtransit_api"):
    settings._settings.njtransit_api = type('NJTransitAPISettings', (), {
        'base_url': 'https://localhost',
        'username': 'test_user',
        'password': 'test_password',
        'station_code': 'NY',
        'retry_attempts': 1,
        'timeout': 5,
        'poll_interval': 60,
        'debug_mode': False
    })()

# Initialize the database with tables
Base.metadata.create_all(test_engine)

@pytest.fixture(scope="function")
def db_session():
    """Set up a test database session."""
    # Ensure tables exist at the start of each test
    Base.metadata.create_all(test_engine)

    # Create a session
    session = TestSession()

    # Clear tables before each test (handle errors gracefully)
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    except Exception as e:
        print(f"Warning: Failed to clear tables: {e}")
        session.rollback()

    # Patch the database connection functions
    with patch("trackcast.db.connection.get_db_session", lambda: session):
        with patch("trackcast.db.connection.engine", test_engine):
            with patch("trackcast.db.connection.DATABASE_URL", TEST_DB_URL):
                with patch("trackcast.db.connection.SessionLocal", TestSession):
                    yield session

    # Clean up
    session.close()


@pytest.fixture(scope="session")
def test_config():
    """Load test configuration."""
    test_config_path = os.path.join(os.path.dirname(__file__), "test_config.yaml")
    
    # Create test config if it doesn't exist
    if not os.path.exists(test_config_path):
        test_config = {
            "database": {
                "url": TEST_DB_URL,
                "echo": False
            },
            "api": {
                "host": "127.0.0.1",
                "port": 8000
            },
            "njtransit": {
                "api_url": "https://localhost",
                "poll_interval": 60
            }
        }
        
        with open(test_config_path, "w") as f:
            yaml.dump(test_config, f)
    
    return load_config(config_path=test_config_path)


@pytest.fixture
def mock_njtransit_api():
    """Mock the NJ Transit API client."""
    mock_api = MagicMock()
    
    # Sample response data
    mock_api.get_departures.return_value = {
        "ITEMS": [
            {
                "TRAIN_ID": "3829",
                "LINE": "Northeast Corrdr",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": "09-May-2025 09:19:00 AM",
                "TRACK": "",
                "STATUS": " ",
            },
            {
                "TRAIN_ID": "6317",
                "LINE": "Morristown Line",
                "DESTINATION": "Summit",
                "SCHED_DEP_DATE": "09-May-2025 09:22:00 AM",
                "TRACK": "10",
                "STATUS": "BOARDING",
            }
        ]
    }
    
    return mock_api


@pytest.fixture
def sample_train_data():
    """Sample processed train data for testing."""
    return [
        {
            "train_id": "3829",
            "line": "Northeast Corrdr",
            "destination": "Trenton",
            "departure_time": "2025-05-09T09:19:00",
            "track": "",
            "status": ""
        },
        {
            "train_id": "6317",
            "line": "Morristown Line",
            "destination": "Summit",
            "departure_time": "2025-05-09T09:22:00",
            "track": "10",
            "status": "BOARDING"
        }
    ]
