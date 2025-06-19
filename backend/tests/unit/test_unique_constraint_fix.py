"""Unit tests for unique constraint violation fix in TrainStopRepository."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation

from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainStopRepository
from trackcast.services.station_mapping import StationMapper


class TestUniqueConstraintFix:
    """Test cases for the unique constraint violation fix."""

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
            train_id="3879",
            origin_station_code="NY",
            departure_time=datetime(2025, 6, 18, 20, 31, 0),
            data_source="njtransit",
        )

    def test_unique_constraint_violation_exact_match_reactivation(self, stop_repo, mock_session, sample_train):
        """
        Test that when fuzzy matching fails but an exact match exists (inactive),
        the system reactivates the existing stop instead of trying to create a duplicate.
        
        This simulates the real-world scenario where:
        1. A stop exists but is marked inactive
        2. The same stop reappears with EXACT same values (violating unique constraint)
        3. Fuzzy matching fails to identify it
        4. System should find exact match and reactivate instead of creating new
        """
        # Create existing inactive stop with exact values that will conflict
        existing_stop = TrainStop()
        existing_stop.id = 38343  # Matching the error log
        existing_stop.train_id = "3879"
        existing_stop.train_departure_time = datetime(2025, 6, 18, 20, 31, 0)
        existing_stop.data_source = "njtransit"
        existing_stop.station_code = "NP"
        existing_stop.station_name = "Newark Penn Station"
        existing_stop.scheduled_time = datetime(2025, 6, 18, 19, 37, 7)  # Exact time from error
        existing_stop.departure_time = datetime(2025, 6, 18, 19, 38, 45)
        existing_stop.is_active = False  # Key: stop is inactive
        existing_stop.last_seen_at = datetime(2025, 6, 18, 23, 31, 31)

        # Mock the queries - initial query returns existing stop, exact match query also returns it
        def mock_query_side_effect(*args):
            """Mock different query behaviors based on call pattern."""
            mock_q = Mock()
            mock_q.filter.return_value = mock_q
            mock_q.all.return_value = [existing_stop]  # For initial query
            mock_q.first.return_value = existing_stop  # For exact match query
            return mock_q
            
        mock_session.query.side_effect = mock_query_side_effect

        # Track what gets added to session (should be nothing - no new stops)
        added_stops = []
        mock_session.add.side_effect = lambda stop: added_stops.append(stop)

        # Incoming stop data with EXACT same values (would cause unique constraint violation)
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": datetime(2025, 6, 18, 19, 37, 7),  # Exact match
                "departure_time": datetime(2025, 6, 18, 19, 38, 45),  # Exact match
                "stop_status": "OnTime",
                "departed": True,
            }
        ]

        # Mock station mapper with fuzzy matching that FAILS (simulating the bug)
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Simulate fuzzy matching failure (the root cause of the bug)
            mock_mapper.times_match_within_tolerance.return_value = False
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert_train_stops
            result = stop_repo.upsert_train_stops(
                train_id="3879",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Verify the existing stop was reactivated instead of creating new
            assert existing_stop.is_active is True
            
            # Verify no new stops were added (which would cause constraint violation)
            assert len(added_stops) == 0
            
            # Verify session.commit was called
            mock_session.commit.assert_called_once()
            
            # Verify we got the reactivated stop back
            assert len(result) == 1
            assert result[0] is existing_stop

    def test_multiple_inactive_stops_exact_match_selection(self, stop_repo, mock_session, sample_train):
        """
        Test that when multiple inactive stops exist, exact matching finds the right one.
        """
        # Create multiple inactive stops at same station with different times
        inactive_stop_1 = TrainStop()
        inactive_stop_1.train_id = "3879"
        inactive_stop_1.train_departure_time = sample_train.departure_time
        inactive_stop_1.data_source = "njtransit"
        inactive_stop_1.station_code = "NP"
        inactive_stop_1.station_name = "Newark Penn Station"
        inactive_stop_1.scheduled_time = datetime(2025, 6, 18, 19, 30, 0)  # Different time
        inactive_stop_1.is_active = False
        
        
        inactive_stop_1.last_seen_at = datetime.utcnow()

        inactive_stop_2 = TrainStop()
        inactive_stop_2.train_id = "3879"
        inactive_stop_2.train_departure_time = sample_train.departure_time
        inactive_stop_2.data_source = "njtransit"
        inactive_stop_2.station_code = "NP"
        inactive_stop_2.station_name = "Newark Penn Station"
        inactive_stop_2.scheduled_time = datetime(2025, 6, 18, 19, 37, 7)  # Exact match target
        inactive_stop_2.is_active = False
        
        
        inactive_stop_2.last_seen_at = datetime.utcnow()

        # Mock the queries for this test
        def mock_query_side_effect(*args):
            """Mock different query behaviors based on call pattern."""
            mock_q = Mock()
            mock_q.filter.return_value = mock_q
            mock_q.all.return_value = [inactive_stop_1, inactive_stop_2]  # For initial query
            mock_q.first.return_value = inactive_stop_2  # For exact match query (matches stop_2)
            return mock_q
            
        mock_session.query.side_effect = mock_query_side_effect

        # Track what gets added
        added_stops = []
        mock_session.add.side_effect = lambda stop: added_stops.append(stop)

        # Incoming data matches only the second stop exactly
        incoming_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": datetime(2025, 6, 18, 19, 37, 7),  # Matches stop_2
                "departed": False,
            }
        ]

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Fuzzy matching fails for both
            mock_mapper.times_match_within_tolerance.return_value = False
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            stop_repo.upsert_train_stops(
                train_id="3879",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Only the exactly matching stop should be reactivated
            assert inactive_stop_1.is_active is False  # Should remain inactive
            assert inactive_stop_2.is_active is True   # Should be reactivated
            
            # No new stops should be created
            assert len(added_stops) == 0

    def test_fallback_to_exact_match_when_fuzzy_fails(self, stop_repo, mock_session, sample_train):
        """
        Test the complete fallback logic:
        1. Try fuzzy matching (fails)
        2. Fall back to exact matching (succeeds)
        3. Reactivate existing stop
        """
        # Create inactive stop
        existing_stop = TrainStop()
        existing_stop.train_id = "3879"
        existing_stop.train_departure_time = sample_train.departure_time
        existing_stop.data_source = "njtransit"
        existing_stop.station_code = "TR"
        existing_stop.station_name = "Trenton"
        existing_stop.scheduled_time = datetime(2025, 6, 18, 20, 27, 22)  # From error logs
        existing_stop.is_active = False
        
        
        existing_stop.last_seen_at = datetime.utcnow()

        # Mock the queries - both the initial query and the exact match query
        mock_query_initial = Mock()
        mock_query_initial.filter.return_value = mock_query_initial
        mock_query_initial.all.return_value = [existing_stop]  # Initial query returns existing stop
        
        mock_query_exact = Mock() 
        mock_query_exact.filter.return_value = mock_query_exact
        mock_query_exact.first.return_value = existing_stop  # Exact match query finds the stop
        
        # Use side_effect to return different mocks for different calls
        mock_session.query.side_effect = [mock_query_initial, mock_query_exact]

        # Incoming data with exact same constraint values
        incoming_stops = [
            {
                "station_code": "TR",
                "station_name": "Trenton",
                "scheduled_time": datetime(2025, 6, 18, 20, 27, 22),  # Exact match
                "departed": True,
            }
        ]

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Fuzzy matching fails (simulating precision issues)
            mock_mapper.times_match_within_tolerance.return_value = False
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            result = stop_repo.upsert_train_stops(
                train_id="3879",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Should find and reactivate the existing stop
            assert existing_stop.is_active is True
            assert len(result) == 1
            assert result[0] is existing_stop

    def test_no_exact_match_creates_new_stop(self, stop_repo, mock_session, sample_train):
        """
        Test that when neither fuzzy nor exact matching finds a stop, 
        a new stop is created (normal behavior).
        """
        # No existing stops
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.first.return_value = None  # For exact match query
        mock_session.query.return_value = mock_query

        # Track what gets added
        added_stops = []
        mock_session.add.side_effect = lambda stop: added_stops.append(stop)

        # Incoming stop data
        incoming_stops = [
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": datetime(2025, 6, 18, 20, 3, 0),
                "departed": False,
            }
        ]

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            mock_mapper.times_match_within_tolerance.return_value = False
            mock_mapper.get_code_for_name.return_value = None
            
            # Call upsert
            result = stop_repo.upsert_train_stops(
                train_id="3879",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )
            
            # Should create exactly one new stop
            assert len(added_stops) == 1
            assert len(result) == 1
            assert result[0] is added_stops[0]
            
            # New stop should have correct properties
            new_stop = added_stops[0]
            assert new_stop.train_id == "3879"
            assert new_stop.station_name == "New York Penn Station"
            assert new_stop.is_active is True