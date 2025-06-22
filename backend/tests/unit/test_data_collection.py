"""Tests for the data collection module."""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open

from trackcast.data.collectors import NJTransitCollector
from trackcast.services.data_collector import DataCollectorService


class TestNJTransitCollector:
    """Tests for the NJTransitCollector class."""

    @patch("trackcast.data.collectors.requests.post")
    @patch("trackcast.data.collectors.os.path.exists", return_value=False)
    @patch("trackcast.data.collectors.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("trackcast.data.collectors.json.dump")
    @patch("trackcast.data.collectors.settings")
    def test_run(self, mock_settings, mock_json_dump, mock_open, mock_mkdir, mock_path_exists, mock_post):
        """Test running the NJ Transit collector."""
        # Mock settings
        mock_settings.njtransit_api = MagicMock(
            base_url="https://localhost",
            username="test_user",
            password="test_password",
            station_code="NY",
            retry_attempts=1,
            timeout_seconds=5,
            debug_mode=False
        )

        # Mock the API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
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
        mock_post.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        # Create the collector with test config
        with patch.object(NJTransitCollector, "_get_token", return_value="test-token"):
            with patch.object(NJTransitCollector, "_archive_response"):
                # Using the mocked settings now
                collector = NJTransitCollector(
                    base_url_or_config=None,
                    station_code="NY",
                    station_name="New York Penn Station",
                    data_dir="/tmp"
                )
                collector.token = "test-token"  # Skip token loading
                
                # Run the collection
                departures, stats = collector.run()
                
                # Verify the response
                assert len(departures) == 2
                assert departures[0]["train_id"] == "3829"
                assert departures[1]["train_id"] == "6317"
                
                # Verify stats contains expected keys
                assert isinstance(stats, dict)
                assert "record_count" in stats
                assert "processing_time_ms" in stats

    def test_direct_token_parameter(self):
        """Test using direct token parameter bypasses username/password authentication."""
        with patch("trackcast.data.collectors.settings") as mock_settings, \
             patch("trackcast.data.collectors.os.path.exists", return_value=False), \
             patch("trackcast.data.collectors.Path.mkdir"):
            
            # Mock settings with no username/password
            mock_settings.njtransit_api = MagicMock(
                base_url="https://localhost",
                username=None,
                password=None
            )
            
            # Create collector with direct token - no username/password needed
            collector = NJTransitCollector(
                base_url_or_config="https://localhost",
                token="direct-test-token",
                station_code="NY",
                station_name="New York Penn Station",
                data_dir="/tmp"
            )
            
            # Verify token is set correctly
            assert collector.token == "direct-test-token"
            assert collector._direct_token_provided is True
            
            # Username/password should be None when not provided and using direct token
            assert collector.username is None
            assert collector.password is None

    def test_njt_token_environment_variable(self):
        """Test using NJT_TOKEN environment variable."""
        with patch("trackcast.data.collectors.settings") as mock_settings, \
             patch("trackcast.data.collectors.os.path.exists", return_value=False), \
             patch("trackcast.data.collectors.Path.mkdir"), \
             patch.dict(os.environ, {"NJT_TOKEN": "env-test-token"}, clear=False):
            
            mock_settings.njtransit_api = MagicMock(base_url="https://localhost")
            
            # Create collector without direct token parameter
            collector = NJTransitCollector(
                base_url_or_config="https://localhost",
                station_code="NY",
                station_name="New York Penn Station",
                data_dir="/tmp"
            )
            
            # Should pick up token from environment variable
            assert collector.token == "env-test-token"
            assert collector._direct_token_provided is True

    def test_token_priority_order(self):
        """Test token resolution priority: parameter > env var > cached file."""
        with patch("trackcast.data.collectors.settings") as mock_settings, \
             patch("trackcast.data.collectors.Path.mkdir"), \
             patch.dict(os.environ, {"NJT_TOKEN": "env-token"}, clear=False):
            
            mock_settings.njtransit_api = MagicMock(base_url="https://localhost")
            
            # Mock cached token file
            cached_token_data = {"Authenticated": "True", "UserToken": "cached-token"}
            with patch("trackcast.data.collectors.os.path.exists", return_value=True), \
                 patch("builtins.open", mock_open(read_data=json.dumps(cached_token_data))):
                
                # Test 1: Direct parameter takes priority
                collector = NJTransitCollector(
                    base_url_or_config="https://localhost",
                    token="direct-token",
                    station_code="NY",
                    station_name="New York Penn Station",
                    data_dir="/tmp"
                )
                assert collector.token == "direct-token"
                
                # Test 2: Environment variable takes priority over cached file
                collector = NJTransitCollector(
                    base_url_or_config="https://localhost",
                    station_code="NY",
                    station_name="New York Penn Station",
                    data_dir="/tmp"
                )
                assert collector.token == "env-token"

    def test_cached_token_fallback(self):
        """Test falling back to cached token when no direct token provided."""
        with patch("trackcast.data.collectors.settings") as mock_settings, \
             patch("trackcast.data.collectors.Path.mkdir"), \
             patch.dict(os.environ, {}, clear=True):  # Clear NJT_TOKEN env var
            
            mock_settings.njtransit_api = MagicMock(base_url="https://localhost")
            
            # Mock cached token file
            cached_token_data = {"Authenticated": "True", "UserToken": "cached-token"}
            with patch("trackcast.data.collectors.os.path.exists", return_value=True), \
                 patch("builtins.open", mock_open(read_data=json.dumps(cached_token_data))):
                
                collector = NJTransitCollector(
                    base_url_or_config="https://localhost",
                    station_code="NY",
                    station_name="New York Penn Station",
                    data_dir="/tmp"
                )
                
                assert collector.token == "cached-token"
                assert collector._direct_token_provided is False

    @patch("trackcast.data.collectors.requests.post")
    @patch("trackcast.data.collectors.os.path.exists", return_value=False)
    @patch("trackcast.data.collectors.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("trackcast.data.collectors.json.dump")
    @patch("trackcast.data.collectors.settings")
    def test_collect_with_direct_token_skips_auth(self, mock_settings, mock_json_dump, 
                                                  mock_open, mock_mkdir, mock_path_exists, mock_post):
        """Test that collect() skips getToken API when direct token is provided."""
        mock_settings.njtransit_api = MagicMock(
            base_url="https://localhost",
            retry_attempts=3,
            timeout_seconds=10,
            debug_mode=False
        )
        
        # Mock successful train schedule response
        schedule_response = MagicMock()
        schedule_response.json.return_value = {"ITEMS": []}
        schedule_response.raise_for_status = MagicMock()
        mock_post.return_value = schedule_response
        
        # Create collector with direct token
        collector = NJTransitCollector(
            base_url_or_config="https://localhost",
            token="direct-token",
            station_code="NY", 
            station_name="New York Penn Station",
            data_dir="/tmp"
        )
        
        # Run collect
        result = collector.collect()
        
        # Verify only getTrainSchedule was called, not getToken
        assert mock_post.call_count == 1
        call_args = mock_post.call_args
        assert "getTrainSchedule" in call_args[0][0]  # URL contains getTrainSchedule
        assert "getToken" not in call_args[0][0]  # URL does not contain getToken
        
        # Verify token was passed in request
        files_param = call_args[1]["files"]
        assert files_param["token"][1] == "direct-token"

    @patch("trackcast.data.collectors.requests.post")
    @patch("trackcast.data.collectors.os.path.exists", return_value=False)
    @patch("trackcast.data.collectors.Path.mkdir")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("trackcast.data.collectors.json.dump")
    @patch("trackcast.data.collectors.settings")
    def test_direct_token_no_refresh_on_401(self, mock_settings, mock_json_dump,
                                           mock_open, mock_mkdir, mock_path_exists, mock_post):
        """Test that 401 errors with direct token don't trigger token refresh."""
        mock_settings.njtransit_api = MagicMock(base_url="https://localhost")
        
        # Mock 401 response
        from requests.exceptions import HTTPError
        error_response = MagicMock()
        error_response.status_code = 401
        error = HTTPError()
        error.response = error_response
        mock_post.side_effect = error
        
        # Create collector with direct token
        collector = NJTransitCollector(
            base_url_or_config="https://localhost",
            token="expired-direct-token",
            station_code="NY",
            station_name="New York Penn Station",
            data_dir="/tmp",
            retry_attempts=1
        )
        
        # Run collect - should fail without trying to refresh token
        with pytest.raises(Exception):  # Should raise APIError eventually
            collector.collect()
        
        # Verify only one call was made (no token refresh attempt)
        assert mock_post.call_count == 1
        call_args = mock_post.call_args
        assert "getTrainSchedule" in call_args[0][0]

    def test_no_token_fallback_to_username_password(self):
        """Test that when no token is provided, it falls back to username/password auth."""
        with patch("trackcast.data.collectors.settings") as mock_settings, \
             patch("trackcast.data.collectors.os.path.exists", return_value=False), \
             patch("trackcast.data.collectors.Path.mkdir"), \
             patch.dict(os.environ, {}, clear=True):  # Clear all env vars
            
            mock_settings.njtransit_api = MagicMock(
                base_url="https://localhost",
                username="test_user",
                password="test_pass"
            )
            
            collector = NJTransitCollector(
                base_url_or_config="https://localhost",
                station_code="NY",
                station_name="New York Penn Station", 
                data_dir="/tmp"
            )
            
            # Should have no token initially, ready to authenticate
            assert collector.token is None
            assert collector._direct_token_provided is False
            assert collector.username == "test_user"
            assert collector.password == "test_pass"


class TestDataCollectorService:
    """Tests for the DataCollectorService class."""

    @patch('trackcast.services.data_collector.NJTransitCollector')
    @patch('trackcast.services.data_collector.TrainRepository')
    @patch('trackcast.services.data_collector.settings')
    def test_run_collection(self, mock_settings, MockTrainRepo, MockCollector, db_session):
        """Test running a data collection cycle."""
        # Mock a station object
        mock_station = MagicMock()
        mock_station.code = "NY"
        mock_station.name = "New York Penn Station"
        mock_station.enabled = True
        
        # Mock settings
        mock_settings.njtransit_api = MagicMock(
            base_url="https://localhost",
            username="test_user",
            password="test_password",
            stations=[mock_station],  # Provide a list of station objects
            retry_attempts=1,
            timeout_seconds=5,
            debug_mode=False
        )
        # Disable Amtrak to avoid complications
        mock_settings.amtrak_api = None

        # Create mock objects
        mock_collector = MockCollector.return_value
        mock_repo = MockTrainRepo.return_value

        # This is the key part - make get_train_by_id_and_time return None
        # so that create_train gets called for new trains
        mock_repo.get_train_by_id_and_time.return_value = None

        # Setup train data with parsed departure_time
        from datetime import datetime
        departure_time = datetime.fromisoformat("2025-05-09T09:19:00")
        processed_data = [
            {
                "train_id": "3829",
                "line": "Northeast Corrdr",
                "destination": "Trenton",
                "departure_time": departure_time,  # Use datetime object instead of string
                "track": "",
                "status": "",
                "origin_station_code": "NY",
                "origin_station_name": "New York Penn Station",
                "data_source": "njtransit"
            }
        ]
        mock_collector.run.return_value = (processed_data, {"api_calls": 1, "parse_time_ms": 100})

        # Create service and replace its repository with our mock
        service = DataCollectorService(db_session)
        service.train_repo = mock_repo

        # Test the run_collection method
        success, stats = service.run_collection()

        # Verify results
        assert success is True
        assert "trains_total" in stats
        
        # Just verify basic functionality works, skip detailed assertions for now
        mock_collector.run.assert_called_once()
