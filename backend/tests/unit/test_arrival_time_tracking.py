"""
Tests for arrival time tracking functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trackcast.db.models import Train, TrainStop
from trackcast.utils import get_eastern_now
from trackcast.services.train_stop_updater import TrainStopUpdater
from trackcast.services.journey_validator import JourneyValidator


class TestTrainStopUpdater:
    """Test the TrainStopUpdater service."""
    
    def test_should_refresh_stops_never_updated(self):
        """Test that stops should be refreshed if never updated."""
        train = Train(
            train_id="1234",
            data_source="njtransit",
            status="BOARDING",
            stops_last_updated=None
        )
        
        updater = TrainStopUpdater(Mock(), Mock())
        assert updater.should_refresh_stops(train) is True
    
    def test_should_refresh_stops_stale_data(self):
        """Test that stops should be refreshed if data is stale."""
        train = Train(
            train_id="1234",
            data_source="njtransit",
            status="DEPARTED",
            stops_last_updated=get_eastern_now() - timedelta(minutes=10)
        )
        
        updater = TrainStopUpdater(Mock(), Mock())
        assert updater.should_refresh_stops(train) is True
    
    def test_should_not_refresh_stops_fresh_data(self):
        """Test that stops should not be refreshed if data is fresh."""
        train = Train(
            train_id="1234",
            data_source="njtransit",
            status="BOARDING",
            stops_last_updated=get_eastern_now() - timedelta(minutes=3)
        )
        
        updater = TrainStopUpdater(Mock(), Mock())
        assert updater.should_refresh_stops(train) is False
    
    def test_should_not_refresh_stops_completed_journey(self):
        """Test that stops should not be refreshed if journey is complete."""
        train = Train(
            train_id="1234",
            data_source="njtransit",
            status="DEPARTED",
            stops_last_updated=get_eastern_now() - timedelta(minutes=10),
            journey_completion_status="completed"
        )
        
        updater = TrainStopUpdater(Mock(), Mock())
        assert updater.should_refresh_stops(train) is False
    
    
    def test_parse_nj_datetime(self):
        """Test parsing NJ Transit datetime format."""
        updater = TrainStopUpdater(Mock(), Mock())
        
        # Valid datetime
        dt = updater._parse_nj_datetime("30-May-2024 10:52:30 AM")
        assert dt == datetime(2024, 5, 30, 10, 52, 30)
        
        # Invalid datetime
        dt = updater._parse_nj_datetime("invalid")
        assert dt is None
        
        # Empty datetime
        dt = updater._parse_nj_datetime("")
        assert dt is None
    
    @patch('trackcast.services.train_stop_updater.logger')
    def test_process_stop_updates(self, mock_logger):
        """Test processing stop updates from API response."""
        # Mock repository
        stop_repo = Mock()
        train_repo = Mock()
        
        # Create test stop
        existing_stop = TrainStop(
            train_id="1234",
            train_departure_time=datetime(2024, 5, 30, 10, 0),
            station_name="Long Branch",
            data_source="njtransit",
            scheduled_arrival=datetime(2024, 5, 30, 10, 52),
            departed=False
        )
        
        stop_repo.get_stop_by_train_and_station.return_value = existing_stop
        stop_repo.update.return_value = existing_stop
        
        # Create updater
        updater = TrainStopUpdater(train_repo, stop_repo)
        
        # Test data from API
        train = Train(
            train_id="1234",
            departure_time=datetime(2024, 5, 30, 10, 0),
            data_source="njtransit"
        )
        
        stops_data = [
            {
                "STATIONNAME": "Long Branch",
                "TIME": "30-May-2024 10:52:30 AM",
                "DEP_TIME": "30-May-2024 10:53:30 AM",
                "DEPARTED": "YES",
                "STOP_STATUS": "OnTime"
            }
        ]
        
        # Process updates
        is_complete = updater._process_stop_updates(train, stops_data)
        
        # Verify the stop was updated
        assert existing_stop.actual_arrival == datetime(2024, 5, 30, 10, 52, 30)
        assert existing_stop.actual_departure == datetime(2024, 5, 30, 10, 53, 30)
        assert existing_stop.departed is True
        assert existing_stop.stop_status == "OnTime"
        assert is_complete is True
        
        # Verify repository was called
        stop_repo.update.assert_called_once_with(existing_stop)


class TestJourneyValidator:
    """Test the JourneyValidator service."""
    
    def test_estimate_next_check_with_stops(self):
        """Test estimating next check time with stop data."""
        train_repo = Mock()
        stop_repo = Mock()
        
        # Mock stops
        stops = [
            Mock(scheduled_time=datetime(2024, 5, 30, 10, 0)),
            Mock(scheduled_time=datetime(2024, 5, 30, 11, 0)),
            Mock(scheduled_time=datetime(2024, 5, 30, 12, 0))
        ]
        stop_repo.get_stops_for_train.return_value = stops
        
        validator = JourneyValidator(train_repo, stop_repo)
        train = Train(train_id="1234", departure_time=datetime(2024, 5, 30, 10, 0))
        
        # Mock get_eastern_now to return a time before the last stop + 30 minutes
        with patch('trackcast.services.journey_validator.get_eastern_now') as mock_get_eastern_now:
            mock_get_eastern_now.return_value = datetime(2024, 5, 30, 9, 0)  # Before all stops
            next_check = validator._estimate_next_check(train)
        
        # Should be 30 minutes after last stop
        expected = datetime(2024, 5, 30, 12, 30)
        assert next_check == expected
    
    def test_estimate_next_check_no_stops(self):
        """Test estimating next check time without stop data."""
        train_repo = Mock()
        stop_repo = Mock()
        
        # No stops
        stop_repo.get_stops_for_train.return_value = []
        
        validator = JourneyValidator(train_repo, stop_repo)
        train = Train(train_id="1234", departure_time=datetime(2024, 5, 30, 10, 0))
        
        with patch('trackcast.services.journey_validator.get_eastern_now') as mock_get_eastern_now:
            mock_get_eastern_now.return_value = datetime(2024, 5, 30, 10, 0)
            next_check = validator._estimate_next_check(train)
        
        # Should be 2 hours from now
        expected = datetime(2024, 5, 30, 12, 0)
        assert next_check == expected