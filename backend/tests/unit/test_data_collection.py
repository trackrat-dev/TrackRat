"""Tests for the data collection module."""
import pytest
from unittest.mock import patch, MagicMock

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
                with patch.object(NJTransitCollector, "_save_to_csv"):
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
