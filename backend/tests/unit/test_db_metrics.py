import pytest
from unittest import mock
import time as std_time # Keep a reference to the original time module

# Import metrics and relevant components
from backend.trackcast.db.repository import (
    TrainRepository,
    DB_QUERY_DURATION_SECONDS
)
from backend.trackcast.db.connection import (
    get_pool_status_metrics,
    DB_CONNECTION_POOL_UTILIZATION,
    engine as db_engine, # Import the engine instance used by connection.py
    settings as db_settings # Import settings to mock database.max_overflow
)
from sqlalchemy.orm import Session
from backend.trackcast.db.models import Train


# Helper to get Prometheus metric values
def get_histogram_count(histogram, labels=None):
    if labels is None:
        labels = {}
    for metric_family in histogram.collect():
        for sample in metric_family.samples:
            if sample.name == histogram._name + "_count" and sample.labels == labels:
                return sample.value
    return 0

def get_histogram_sum(histogram, labels=None):
    if labels is None:
        labels = {}
    for metric_family in histogram.collect():
        for sample in metric_family.samples:
            if sample.name == histogram._name + "_sum" and sample.labels == labels:
                return sample.value
    return 0

def get_gauge_value(gauge, labels=None):
    if labels is None:
        labels = {}
    # Gauge values are directly in samples without _sum or _count suffix
    for metric_family in gauge.collect():
        for sample in metric_family.samples:
            if sample.name == gauge._name and sample.labels == labels:
                return sample.value
    return 0


@pytest.fixture
def mock_sqlalchemy_session():
    """Provides a mock SQLAlchemy session."""
    session = mock.Mock(spec=Session)
    mock_query = mock.Mock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = Train(id=1, train_id="T123") # Sample return
    mock_query.all.return_value = [Train(id=1, train_id="T123")] # Sample return
    mock_query.count.return_value = 1

    session.add = mock.Mock()
    session.commit = mock.Mock()
    session.rollback = mock.Mock()
    return session

# --- DB_QUERY_DURATION_SECONDS Tests (from repository.py) ---

def test_db_query_duration_for_get_train_by_id(mock_sqlalchemy_session):
    repo = TrainRepository(session=mock_sqlalchemy_session)
    query_type_label = {"query_type": "get_train_by_id"}

    initial_count = get_histogram_count(DB_QUERY_DURATION_SECONDS, labels=query_type_label)
    initial_sum = get_histogram_sum(DB_QUERY_DURATION_SECONDS, labels=query_type_label)

    # Mock time.time() to control duration
    with mock.patch("time.time", side_effect=[10.0, 10.123]): # Start time, end time
        repo.get_train_by_id("T123")

    assert get_histogram_count(DB_QUERY_DURATION_SECONDS, labels=query_type_label) == initial_count + 1
    assert get_histogram_sum(DB_QUERY_DURATION_SECONDS, labels=query_type_label) == pytest.approx(initial_sum + 0.123)

def test_db_query_duration_for_create_train(mock_sqlalchemy_session):
    repo = TrainRepository(session=mock_sqlalchemy_session)
    query_type_label = {"query_type": "create_train"}

    initial_count = get_histogram_count(DB_QUERY_DURATION_SECONDS, labels=query_type_label)
    initial_sum = get_histogram_sum(DB_QUERY_DURATION_SECONDS, labels=query_type_label)

    train_data = {
        "train_id": "T456",
        "origin_station_code": "NYP",
        "departure_time": std_time.time() # Using std_time for data
    }

    with mock.patch("time.time", side_effect=[20.0, 20.456]):
        repo.create_train(train_data, timestamp=std_time.time()) # timestamp arg for create_train

    assert get_histogram_count(DB_QUERY_DURATION_SECONDS, labels=query_type_label) == initial_count + 1
    assert get_histogram_sum(DB_QUERY_DURATION_SECONDS, labels=query_type_label) == pytest.approx(initial_sum + 0.456)


# --- DB_CONNECTION_POOL_UTILIZATION Tests (from connection.py) ---

@mock.patch.object(db_engine.pool, 'status') # Mock the status method of the actual engine's pool
@mock.patch.object(db_engine.pool, 'size')   # Mock the size method of the actual engine's pool
def test_db_connection_pool_utilization(mock_pool_size, mock_pool_status):
    # Configure mock return values
    mock_pool_status.return_value = {
        "checkedout": 5,
        "checkedin": 10,
        "overflow": 0 # Current overflow, not max
    }
    mock_pool_size.return_value = 15 # Configured pool size

    # Mock settings for max_overflow if it's used in calculation
    # Assuming settings.database.max_overflow is used.
    # Create a dummy settings object or mock db_settings directly if it's an AttrDict or similar.
    # For simplicity, let's assume db_settings is an object where we can set attributes.
    with mock.patch.object(db_settings, 'database', new_callable=mock.PropertyMock) as mock_db_config:
        mock_db_config.max_overflow = 5 # Configured max_overflow

        initial_value = get_gauge_value(DB_CONNECTION_POOL_UTILIZATION) # Should be 0 or previous test's value

        get_pool_status_metrics()

        # Expected calculation: checkedout / (pool_size + max_overflow)
        # 5 / (15 + 5) = 5 / 20 = 0.25
        assert get_gauge_value(DB_CONNECTION_POOL_UTILIZATION) == pytest.approx(0.25)

def test_db_connection_pool_utilization_no_connections(mock_pool_size, mock_pool_status):
    # Test edge case: pool_size is 0 or not configured (max_possible_connections = 0)
    mock_pool_status.return_value = {"checkedout": 0, "checkedin": 0, "overflow": 0}
    mock_pool_size.return_value = 0

    with mock.patch.object(db_settings, 'database', new_callable=mock.PropertyMock) as mock_db_config:
        mock_db_config.max_overflow = 0

        get_pool_status_metrics()
        # If max_possible_connections is 0, the function should set utilization to 0
        assert get_gauge_value(DB_CONNECTION_POOL_UTILIZATION) == 0.0

def test_db_connection_pool_utilization_status_missing_keys(mock_pool_size, mock_pool_status):
    # Test robustness if pool.status() returns unexpected data
    mock_pool_status.return_value = {} # Missing checkedout/checkedin
    mock_pool_size.return_value = 10

    # The gauge should not change or should be set to a defined value (e.g. 0 or remain as is)
    # and a warning should be logged (not tested here).
    # Let's assume it remains unchanged or is set to 0 if it cannot be calculated.
    # The current implementation does not set the gauge if keys are missing.
    # So, we check it doesn't error and potentially remains at a previous value or 0.

    # Set a known value to see if it changes
    DB_CONNECTION_POOL_UTILIZATION.set(0.888)

    with mock.patch.object(db_settings, 'database', new_callable=mock.PropertyMock) as mock_db_config:
        mock_db_config.max_overflow = 5
        get_pool_status_metrics() # Should log a warning

    # Assert that the gauge value was not updated or reset if calculation failed
    # The current code in get_pool_status_metrics does not set the gauge if keys are missing.
    # So, it should retain its previous value.
    assert get_gauge_value(DB_CONNECTION_POOL_UTILIZATION) == 0.888

    # Reset for other tests
    DB_CONNECTION_POOL_UTILIZATION.set(0)


# Note: These tests assume that the Prometheus metric objects are globally defined and not reset
# between test runs in a single test session (which is typical for Prometheus client).
# The helper functions `get_histogram_count/sum` and `get_gauge_value` are designed to fetch
# current values correctly.
# The mocking of `time.time` is crucial for testing durations.
# The mocking of `engine.pool.status` and `engine.pool.size` is essential for testing pool utilization.
# Remember that `db_settings.database.max_overflow` is also part of the calculation logic.
# The structure of `db_settings` needs to be mockable, e.g. if it's an AttrDict or a class instance.
# Assuming `db_settings.database` is an object with a `max_overflow` attribute.
```
