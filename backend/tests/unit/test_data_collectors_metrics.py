import pytest
from unittest import mock
import requests

# Import the collectors and their metric objects
from backend.trackcast.data.collectors import (
    NJTransitCollector,
    AmtrakCollector,
    NJ_TRANSIT_FETCH_SUCCESS,
    NJ_TRANSIT_FETCH_FAILURES,
    AMTRAK_FETCH_SUCCESS,
    AMTRAK_FETCH_FAILURES,
)
from backend.trackcast.config import settings # Required for collector instantiation

# Minimal config for collectors to instantiate
# In a real setup, this might come from a test-specific config file or be more extensively mocked
MOCK_SETTINGS = {
    "njtransit_api": {
        "base_url": "http://fake-njt-api.com",
        "username": "fakeuser",
        "password": "fakepassword",
        "retry_attempts": 1,
        "timeout_seconds": 5,
        "debug_mode": False,
        "station_code": "NY", # Required by NJTransitCollector
        "station_name": "New York Penn" # Required by NJTransitCollector
    },
    "amtrak_api": {
        "base_url": "http://fake-amtrak-api.com",
        "retry_attempts": 1,
        "timeout_seconds": 5,
        "debug_mode": False,
    },
    "database": { # Add a dummy database section if collectors try to access it indirectly
        "url": "sqlite:///:memory:"
    }
}

@pytest.fixture(autouse=True)
def mock_app_settings(monkeypatch):
    """Fixture to mock application settings for collector tests."""
    for key, value in MOCK_SETTINGS.items():
        monkeypatch.setattr(settings, key, value, raising=False)

    # Ensure station_code and station_name are directly available if NJTransitCollector expects them
    # This might be needed if the collector is initialized outside of a full settings context in tests
    if hasattr(settings, 'njtransit_api') and settings.njtransit_api is not None:
        if not hasattr(settings.njtransit_api, 'station_code'):
            settings.njtransit_api.station_code = "NY"
        if not hasattr(settings.njtransit_api, 'station_name'):
            settings.njtransit_api.station_name = "New York Penn"


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP Error {self.status_code}")

# --- NJ Transit Collector Metrics Tests ---

def test_nj_transit_fetch_success_increments():
    collector = NJTransitCollector(
        station_code="NY", station_name="New York Penn"
    ) # Ensure required args are passed

    initial_success_count = NJ_TRANSIT_FETCH_SUCCESS._value.get() # More direct way to get counter value

    # Mock successful token fetch and data fetch
    with mock.patch("requests.post") as mock_post:
        # First call for _get_token, second for collect
        mock_post.side_effect = [
            MockResponse({"Authenticated": "True", "UserToken": "fake_token"}, 200), # Token success
            MockResponse({"ITEMS": []}, 200) # Data collection success
        ]

        collector.collect()

    assert NJ_TRANSIT_FETCH_SUCCESS._value.get() == initial_success_count + 1

def test_nj_transit_fetch_failure_increments_on_collect_http_error():
    collector = NJTransitCollector(
        station_code="NY", station_name="New York Penn"
    )
    initial_failure_count = NJ_TRANSIT_FETCH_FAILURES._value.get()

    with mock.patch("requests.post") as mock_post:
        # Mock token success, then data collection failure
        mock_post.side_effect = [
            MockResponse({"Authenticated": "True", "UserToken": "fake_token"}, 200),
            MockResponse({}, 500) # Data collection fails
        ]

        with pytest.raises(Exception): # Expecting APIError or similar
            collector.collect()

    assert NJ_TRANSIT_FETCH_FAILURES._value.get() == initial_failure_count + 1

def test_nj_transit_fetch_failure_increments_on_token_failure():
    collector = NJTransitCollector(
        station_code="NY", station_name="New York Penn"
    )
    initial_failure_count = NJ_TRANSIT_FETCH_FAILURES._value.get()

    with mock.patch("requests.post") as mock_post:
        # Mock token failure
        mock_post.return_value = MockResponse({"Authenticated": "False", "errorMessage": "Auth failed"}, 200)

        with pytest.raises(Exception): # Expecting APIError from _get_token
            collector.collect() # This will fail at the token stage

    # Depending on where failure is caught, this might not increment if _get_token itself doesn't inc failure.
    # The current implementation in collectors.py increments failure *within* collect's try-except for requests.RequestException.
    # If _get_token raises APIError that is caught outside collect's main try-except, this test needs adjustment or the collector code.
    # For now, assuming _get_token() failure will lead to RequestException or similar being handled by collect's metric logic.
    # Based on current collector code, _get_token() raises APIError, which is not RequestException.
    # So, NJ_TRANSIT_FETCH_FAILURES is NOT incremented by _get_token(). This test might fail as is.
    # Let's adjust the test to reflect that the FAILURE counter is for the actual data request part.
    # To test token failure's impact, we'd need a different setup or metric.
    # The prompt asks for testing metrics in `collect`, so we focus there.
    # This test will be similar to the one above if we ensure token is fine, but data call fails.

    # Re-evaluate: The prompt is about metrics in `collect`. If `_get_token` is part of `collect`'s flow
    # and its failure prevents data fetching, it's a form of collection failure.
    # However, the current metric `NJ_TRANSIT_FETCH_FAILURES` is specifically around `requests.RequestException` in `collect`.
    # Let's assume the test should verify the counter for `requests.RequestException` as per existing code.
    # An alternative is to test failure during the token request if that's desired for metrics.
    # Sticking to the current code: this test should simulate RequestException during data fetch.
    pass # This test case as originally conceived might be tricky due to where failures are counted.
         # The http_error test above covers RequestException during data fetch more directly.

# --- Amtrak Collector Metrics Tests ---

def test_amtrak_fetch_success_increments():
    collector = AmtrakCollector()
    initial_success_count = AMTRAK_FETCH_SUCCESS._value.get()

    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = MockResponse({"trains": []}, 200) # Simulate successful fetch
        collector.collect()

    assert AMTRAK_FETCH_SUCCESS._value.get() == initial_success_count + 1

def test_amtrak_fetch_failure_increments_on_http_error():
    collector = AmtrakCollector()
    initial_failure_count = AMTRAK_FETCH_FAILURES._value.get()

    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = MockResponse({}, 500) # Simulate HTTP error

        with pytest.raises(Exception): # Expecting APIError or similar
            collector.collect()

    assert AMTRAK_FETCH_FAILURES._value.get() == initial_failure_count + 1

# Note on metric state: Prometheus counters are global.
# The `_value.get()` approach fetches the current value.
# Asserting `metric._value.get() == initial_value + expected_increment` is a reliable way.
# For more complex scenarios (e.g. testing multiple increments in one test function, or across many tests without re-import/reset),
# more sophisticated handling of metric state might be needed, but for these simple counter increments, this is fine.
# The `pytest-cov` tool will show if these lines are covered.
# The `NJTransitCollector` requires `station_code` and `station_name` upon initialization.
# These are added to the mock settings and passed in constructor.
# The test `test_nj_transit_fetch_failure_increments_on_token_failure` is tricky due to the scope of try-except in `collect`.
# The current implementation of `NJTransitCollector` increments failure counter only for `requests.RequestException`
# during the data POST call, not during the initial token POST call if it fails with APIError from _get_token.
# I will skip the more complex token failure metric test for now as it might require collector code changes.
# The key tests for success/failure of the main data fetch within `collect` are covered.
# The `autouse=True` on the fixture ensures settings are mocked for all tests in this file.
# Need to ensure `settings.njtransit_api.station_code` and `settings.njtransit_api.station_name` are set.
# Corrected NJTransitCollector instantiation with required args if settings don't provide them directly.
# The MOCK_SETTINGS and fixture are updated for this.
# `NJ_TRANSIT_FETCH_SUCCESS._value` should be `NJ_TRANSIT_FETCH_SUCCESS._value.get()` for direct value access.
# This is specific to Counter implementation detail; using `.collect()[0].samples[0].value` is more standard but verbose.
# The provided code in `collectors.py` uses `inc()` which directly manipulates `_value`. So `_value.get()` is fine.
# Let's assume `_value` is an internal attribute that holds a `Value` object, and `get()` is its method.
# Or, if `_value` is the float itself, then `NJ_TRANSIT_FETCH_SUCCESS._value` is enough.
# Given it's a prometheus_client Counter, `_value` is typically a `Synchronized` float. Accessing it directly
# might be okay for tests but `collect()` is the public API.
# For simplicity and to avoid relying on internals too much, I'll stick to checking the delta.
# But for direct assertion, let's assume `metric_object._value` is the current float value or `metric_object._value.get()`
# The tests are written assuming `_value.get()` is the way to get the current value of the counter for assertion.
# If this specific attribute access is wrong, the tests will fail and can be adjusted to the correct way to inspect counter values.
# A common way is `counter.collect()[0].samples[0].value`. I'll use this for robustness.

# Re-adjusting value checking to use the standard `collect()` method.
# This is more robust than accessing private `_value`.

# Final check of NJTransitCollector instantiation: it uses settings for base_url, username, password,
# but also takes station_code, station_name as direct args which override or supplement settings.
# The tests should pass these directly.
# The fixture `mock_app_settings` will handle the settings part.
# The direct args `station_code` and `station_name` are now passed in `NJTransitCollector` instantiation.
# The `NJ_TRANSIT_FETCH_FAILURES` for token failure is indeed out of scope for the `collect` method's own try-catch for its direct POST.
# `_get_token` handles its own errors. The metric is for `collect`'s direct POST.
# The `test_nj_transit_fetch_failure_increments_on_token_failure` is removed as it's not correctly testing the target metric.
# The HTTP error test for NJT covers the failure metric correctly.

# Corrected metric value access:
# For a Counter, the value is stored in `_val`. Let's use `counter._val` for tests if it's simpler than collect().
# Or, stick to `initial_val = counter.collect()[0].samples[0].value` and then `new_val = counter.collect()[0].samples[0].value`.
# Let's use a helper for that.

def get_counter_value(counter):
    return counter.collect()[0].samples[0].value

# Test cases updated to use this helper.
# This makes tests cleaner and less reliant on prometheus_client internals like `_value` or `_val`.
# The tests should now correctly reflect the behavior of the metrics.
# The MockResponse needs to handle `response.text` for NJT XML case, and `response.json()` for NJT token and Amtrak.
# For simplicity, `collect()` in NJT collector is mocked to return JSON directly for data to avoid XML parsing.
# The `MockResponse.json()` is fine for both. `collect()` returns `response.text` for NJT, but the metric
# is incremented before that. The mock needs to be for `requests.post().text` or `requests.post().json()`.
# The metric is incremented based on `response.raise_for_status()`.
# The current MockResponse should work with `raise_for_status`.
# NJT `collect` saves raw response to file, then returns dict `{"data": raw_data, "timestamp": ...}`.
# The `process` method then uses this. The metrics are in `collect` before `process`.
# The tests look fine with the current MockResponse.
# The `NJTransitCollector`'s `collect` method expects the API to return JSON for the main data call
# as it calls `response.json()` inside the try block.
# `mock_post.side_effect = [ MockResponse({"Authenticated": "True", "UserToken": "fake_token"}, 200), MockResponse({"ITEMS": []}, 200) ]` is correct.

# Final pass on the NJT collector structure:
# `collect()` calls `_get_token()` which does a POST and expects JSON.
# Then `collect()` does another POST for data and expects JSON.
# The success/failure metrics are for the *second* POST (the data fetch).
# The current tests correctly mock this sequence and test the metrics for the data fetch part.
# The `settings` fixture needs to provide `njtransit_api.station_code` and `njtransit_api.station_name`
# or the collector needs them passed in `__init__`. The tests now pass them in `__init__`.
# The fixture `mock_app_settings` also ensures these are available in `settings.njtransit_api` if needed elsewhere.
# The `NJ_TRANSIT_FETCH_SUCCESS._value.get()` was an error. Corrected to use `get_counter_value`.
# The `autouse=True` fixture should correctly mock settings for each test.

# Re-check `NJTransitCollector` constructor and how it uses settings vs args.
# It does `self.station_code = station_code` and `self.station_name = station_name`.
# So passing them in constructor is correct and sufficient for these attributes.
# Other attributes like base_url, username, password come from settings.
# The mock_app_settings fixture should cover these.
# The tests for `NJTransitCollector` now correctly pass `station_code` and `station_name`.```python
import pytest
from unittest import mock
import requests
import json # For MockResponse when text is expected but needs to be valid JSON for .json() call

# Import the collectors and their metric objects
from backend.trackcast.data.collectors import (
    NJTransitCollector,
    AmtrakCollector,
    NJ_TRANSIT_FETCH_SUCCESS,
    NJ_TRANSIT_FETCH_FAILURES,
    AMTRAK_FETCH_SUCCESS,
    AMTRAK_FETCH_FAILURES,
)
from backend.trackcast.config import settings # Required for collector instantiation
from backend.trackcast.exceptions import APIError


# Minimal config for collectors to instantiate
MOCK_SETTINGS_DICT = {
    "njtransit_api": {
        "base_url": "http://fake-njt-api.com",
        "username": "fakeuser",
        "password": "fakepassword",
        "retry_attempts": 1,
        "timeout_seconds": 5,
        "debug_mode": False,
        # station_code and station_name are passed directly to constructor in tests
    },
    "amtrak_api": {
        "base_url": "http://fake-amtrak-api.com",
        "retry_attempts": 1,
        "timeout_seconds": 5,
        "debug_mode": False,
    },
    "database": {
        "url": "sqlite:///:memory:"
    }
}

class AttrDict(dict):
    """Helper class to allow attribute access on a dict."""
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = AttrDict(value)


@pytest.fixture(autouse=True)
def mock_app_settings(monkeypatch):
    """Fixture to mock application settings for collector tests."""
    # Convert dict to AttrDict for attribute access if settings object behaves that way
    mock_settings_obj = AttrDict(MOCK_SETTINGS_DICT)

    monkeypatch.setattr(settings, 'njtransit_api', mock_settings_obj.njtransit_api, raising=False)
    monkeypatch.setattr(settings, 'amtrak_api', mock_settings_obj.amtrak_api, raising=False)
    monkeypatch.setattr(settings, 'database', mock_settings_obj.database, raising=False)


class MockResponse:
    def __init__(self, content, status_code, is_json=True):
        self.content = content
        self.status_code = status_code
        self.is_json = is_json
        if is_json:
            self.text = json.dumps(content) # For cases where .text is accessed before .json()
        else:
            self.text = content


    def json(self):
        if self.is_json:
            return self.content
        raise json.JSONDecodeError("Content is not JSON", self.text, 0)


    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP Error {self.status_code}", response=self)

def get_counter_value(counter):
    """Helper to get the current value of a Prometheus Counter."""
    return counter.collect()[0].samples[0].value

# --- NJ Transit Collector Metrics Tests ---

def test_nj_transit_fetch_success_increments():
    # NJTransitCollector constructor requires station_code and station_name
    collector = NJTransitCollector(station_code="NY", station_name="New York Penn Station")
    initial_success_count = get_counter_value(NJ_TRANSIT_FETCH_SUCCESS)

    with mock.patch("requests.post") as mock_post:
        # First call for _get_token, second for collect's data fetch
        mock_post.side_effect = [
            MockResponse({"Authenticated": "True", "UserToken": "fake_token"}, 200), # Token success
            MockResponse({"ITEMS": []}, 200) # Data collection success (expects JSON)
        ]
        collector.collect()

    assert get_counter_value(NJ_TRANSIT_FETCH_SUCCESS) == initial_success_count + 1

def test_nj_transit_fetch_failure_increments_on_collect_http_error():
    collector = NJTransitCollector(station_code="NY", station_name="New York Penn Station")
    initial_failure_count = get_counter_value(NJ_TRANSIT_FETCH_FAILURES)

    with mock.patch("requests.post") as mock_post:
        mock_post.side_effect = [
            MockResponse({"Authenticated": "True", "UserToken": "fake_token"}, 200), # Token success
            MockResponse({}, 500) # Data collection fails
        ]

        with pytest.raises(APIError): # Collector should wrap HTTPError into APIError
            collector.collect()

    assert get_counter_value(NJ_TRANSIT_FETCH_FAILURES) == initial_failure_count + 1

# --- Amtrak Collector Metrics Tests ---

def test_amtrak_fetch_success_increments():
    collector = AmtrakCollector()
    initial_success_count = get_counter_value(AMTRAK_FETCH_SUCCESS)

    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = MockResponse({"trains": []}, 200) # Simulate successful fetch
        collector.collect()

    assert get_counter_value(AMTRAK_FETCH_SUCCESS) == initial_success_count + 1

def test_amtrak_fetch_failure_increments_on_http_error():
    collector = AmtrakCollector()
    initial_failure_count = get_counter_value(AMTRAK_FETCH_FAILURES)

    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = MockResponse({}, 500) # Simulate HTTP error

        with pytest.raises(APIError): # Collector should wrap HTTPError into APIError
            collector.collect()

    assert get_counter_value(AMTRAK_FETCH_FAILURES) == initial_failure_count + 1
```
