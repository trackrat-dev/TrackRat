"""Unit tests for TrainStopRepository with focus on time normalization bug."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainStopRepository
from trackcast.services.station_mapping import StationMapper


class TestTrainStopRepository:
    """Test cases for TrainStopRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def stop_repo(self, mock_session):
        """Create a TrainStopRepository instance."""
        return TrainStopRepository(mock_session)

    @pytest.fixture
    def sample_train(self):
        """Create a sample train for testing."""
        return Train(
            id=1,
            train_id="3862",
            origin_station_code="NY",
            departure_time=datetime(2025, 6, 18, 17, 49, 0),
            data_source="njtransit",
        )

    def test_fuzzy_time_matching_fix(self, stop_repo, mock_session, sample_train):
        """
        Test that stops with different time precision are correctly matched
        using fuzzy time matching, preventing incorrect "inactive" marking.
        
        This tests that:
        - DB has stop with time 18:36:18 (with seconds)
        - Incoming has stop with time 18:36:00 (minute precision)
        - They should match via fuzzy matching and NOT mark the stop as inactive
        """
        # Setup existing stop with seconds (as stored in DB)
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 18),  # Has seconds!
            departure_time=datetime(2025, 6, 18, 18, 37, 0),
            is_active=True,
            stop_status="OnTime",
            departed=False,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )
        
        # Mock the query to return our existing stop
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query
        
        # Incoming stop data with minute precision (no seconds)
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:36:00",  # Minute precision, no seconds
                "departure_time": "2025-06-18T18:37:00",
                "stop_status": "OnTime",
                "departed": False,
            }
        ]
        
        # Mock station mapper
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Mock fuzzy time matching - 18:36:18 should match 18:36:00 within 5 minutes
            def fuzzy_time_match(time1, time2, tolerance_seconds=300):
                """Simulate fuzzy time matching within tolerance."""
                # For this test: 18:36:18 and 18:36:00 should match (18 seconds difference)
                return True  # Within tolerance
            
            mock_mapper.times_match_within_tolerance.side_effect = fuzzy_time_match
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert_train_stops
            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Verify the stop was NOT marked as inactive
            assert existing_stop.is_active is True
            assert existing_stop.api_removed_at is None
            
            # Verify session.commit was called
            mock_session.commit.assert_called_once()

    def test_multiple_stops_at_same_station_different_times(self, stop_repo, mock_session, sample_train):
        """
        Test that multiple stops at the same station with different times are handled correctly.
        This ensures the scheduled_time is part of the matching key.
        """
        # Two stops at same station but different times (more than 60 minutes apart)
        existing_stops = [
            TrainStop(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                data_source="njtransit",
                station_code="NP",
                station_name="Newark Penn Station",
                scheduled_time=datetime(2025, 6, 18, 16, 20, 0),  # First stop - 2+ hours before second
                is_active=True,
                data_version=1,
                audit_trail=[],
                last_seen_at=datetime.utcnow(),
            ),
            TrainStop(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                data_source="njtransit",
                station_code="NP", 
                station_name="Newark Penn Station",
                scheduled_time=datetime(2025, 6, 18, 18, 30, 15),  # Second stop
                is_active=True,
                data_version=1,
                audit_trail=[],
                last_seen_at=datetime.utcnow(),
            ),
        ]
        
        # Mock the query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = existing_stops
        mock_session.query.return_value = mock_query
        
        # Track which stops get added to session (new stops)
        added_stops = []
        mock_session.add.side_effect = lambda stop: added_stops.append(stop)
        
        # Incoming data has only the second stop (normalized)
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:30:00",  # Matches second stop when normalized
                "departed": False,
            }
        ]
        
        # Mock station mapper with fuzzy matching
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Mock fuzzy time matching to properly control behavior
            def mock_fuzzy_match(time1, time2, tolerance_seconds=300):
                """Mock fuzzy time matching for this specific test."""
                # Convert to datetime objects for comparison
                if isinstance(time1, datetime):
                    t1 = time1
                elif isinstance(time1, str):
                    t1 = datetime.fromisoformat(time1.replace('Z', '+00:00').split('+')[0])
                else:
                    return False
                    
                if isinstance(time2, datetime):
                    t2 = time2
                elif isinstance(time2, str):
                    t2 = datetime.fromisoformat(time2.replace('Z', '+00:00').split('+')[0])
                else:
                    return False
                
                # Calculate absolute difference in seconds
                diff = abs((t1 - t2).total_seconds())
                
                # For this test:
                # - First stop: 16:20:00 vs incoming 18:30:00 = 7800 seconds (2h 10min) > 3600 sec tolerance
                # - Second stop: 18:30:15 vs incoming 18:30:00 = 15 seconds < 3600 sec tolerance
                result = diff <= tolerance_seconds
                print(f"Fuzzy match: {time1} vs {time2} = {diff}s, within {tolerance_seconds}s? {result}")
                return result
            
            mock_mapper.times_match_within_tolerance.side_effect = mock_fuzzy_match
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            
            # First stop should be marked inactive (time doesn't match within 60-minute tolerance)
            # 16:20:00 vs 18:30:00 is 2h 10min - beyond tolerance
            assert existing_stops[0].is_active is False
            assert existing_stops[0].api_removed_at is not None
            
            # Second stop should remain active (matched by fuzzy time matching within tolerance)
            # 18:30:15 vs 18:30:00 is only 15 seconds difference - well within 60-minute tolerance
            assert existing_stops[1].is_active is True
            assert existing_stops[1].api_removed_at is None

    def test_stop_reactivation_after_being_marked_inactive(self, stop_repo, mock_session, sample_train):
        """
        Test that a stop previously marked as inactive gets reactivated when it 
        reappears in the API data using fuzzy time matching.
        """
        # Setup existing inactive stop
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 30),
            is_active=False,  # Previously marked inactive
            api_removed_at=datetime(2025, 6, 18, 17, 0, 0),
            audit_trail=[
                {
                    "timestamp": "2025-06-18T17:00:00",
                    "action": "removed_from_api",
                    "note": "Stop no longer present in API response",
                }
            ],
            data_version=1,
            last_seen_at=datetime.utcnow(),
        )
        
        # Mock the query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query
        
        # Stop reappears in incoming data (within fuzzy tolerance)
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station", 
                "scheduled_time": "2025-06-18T18:37:00",  # 30 seconds diff - within tolerance
                "departed": False,
            }
        ]
        
        # Mock station mapper with fuzzy matching
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Mock fuzzy time matching - 18:36:30 vs 18:37:00 = 30 seconds (within tolerance)
            mock_mapper.times_match_within_tolerance.return_value = True
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Stop should be reactivated
            assert existing_stop.is_active is True
            assert existing_stop.api_removed_at is None
            
            # Check audit trail was updated
            assert len(existing_stop.audit_trail) == 2
            assert existing_stop.audit_trail[1]["action"] == "updated"
            assert existing_stop.audit_trail[1]["note"] == "Stop reappeared in API"

    def test_edge_case_near_minute_boundary_with_fuzzy_matching(self, stop_repo, mock_session, sample_train):
        """
        Test that fuzzy matching handles times near minute boundaries correctly.
        E.g., 18:36:59 vs 18:37:00 is only 1 second difference - well within tolerance.
        """
        # Existing stop at 59 seconds
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 59),  # 1 second before 18:37:00
            is_active=True,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )
        
        # Mock the query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query
        
        # Incoming data at 18:37:00
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:37:00",
                "departed": False,
            }
        ]
        
        # Mock station mapper with fuzzy matching
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Mock fuzzy time matching - 18:36:59 vs 18:37:00 = 1 second (well within tolerance)
            mock_mapper.times_match_within_tolerance.return_value = True
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Stop should NOT be marked inactive (times match within fuzzy tolerance)
            assert existing_stop.is_active is True
            assert existing_stop.api_removed_at is None

    def test_null_scheduled_time_handling(self, stop_repo, mock_session, sample_train):
        """
        Test that stops with null scheduled times are handled correctly.
        """
        # Mix of stops with and without scheduled times
        existing_stops = [
            TrainStop(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                data_source="njtransit",
                station_code="NP",
                station_name="Newark Penn Station",
                scheduled_time=None,  # No scheduled time
                is_active=True,
                data_version=1,
                audit_trail=[],
                last_seen_at=datetime.utcnow(),
            ),
            TrainStop(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                data_source="njtransit",
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_time=datetime(2025, 6, 18, 19, 0, 0),
                is_active=True,
                data_version=1,
                audit_trail=[],
                last_seen_at=datetime.utcnow(),
            ),
        ]
        
        # Mock the query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = existing_stops
        mock_session.query.return_value = mock_query
        
        # Incoming data also has null scheduled time for Newark
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": None,
                "departed": False,
            },
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T19:00:00",
                "departed": False,
            },
        ]
        
        # Mock station mapper with fuzzy matching
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Mock fuzzy time matching to handle None values and valid times
            def mock_fuzzy_match_with_null(time1, time2, tolerance_seconds=300):
                """Handle fuzzy matching with potential None values."""
                # If either time is None, they match only if both are None
                if time1 is None or time2 is None:
                    return time1 is None and time2 is None
                # Otherwise use standard fuzzy matching logic
                return True  # For this test, the NY stop times match
            
            mock_mapper.times_match_within_tolerance.side_effect = mock_fuzzy_match_with_null
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Both stops should remain active
            assert all(stop.is_active for stop in existing_stops)
            assert all(stop.api_removed_at is None for stop in existing_stops)