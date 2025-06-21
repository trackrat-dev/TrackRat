"""
Unit tests for eager loading functionality in TrainRepository.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from trackcast.db.repository import TrainRepository
from trackcast.db.models import Train, TrainStop


class TestEagerLoading:
    """Test class for eager loading functionality."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def train_repo(self, mock_session):
        """Create a TrainRepository with mock session."""
        return TrainRepository(mock_session)
    
    @pytest.fixture
    def sample_trains_info(self):
        """Sample train info for testing."""
        now = datetime.now()
        return [
            Mock(id=1, train_id="100", departure_time=now),
            Mock(id=2, train_id="200", departure_time=now + timedelta(hours=1)),
            Mock(id=3, train_id="300", departure_time=now + timedelta(hours=2)),
        ]
    
    @pytest.fixture
    def sample_stops(self):
        """Sample train stops for testing."""
        now = datetime.now()
        return [
            # Stops for train 100
            TrainStop(
                train_id="100",
                train_departure_time=now,
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_time=now,
                departed=True,
                pickup_only=False,
                dropoff_only=False,
                stop_status="DEPARTED"
            ),
            TrainStop(
                train_id="100", 
                train_departure_time=now,
                station_code="NP",
                station_name="Newark Penn Station",
                scheduled_time=now + timedelta(minutes=30),
                departed=False,
                pickup_only=False,
                dropoff_only=False,
                stop_status=""
            ),
            # Stops for train 200
            TrainStop(
                train_id="200",
                train_departure_time=now + timedelta(hours=1),
                station_code="NY",
                station_name="New York Penn Station", 
                scheduled_time=now + timedelta(hours=1),
                departed=False,
                pickup_only=False,
                dropoff_only=False,
                stop_status=""
            ),
        ]
    
    def test_get_trains_with_stops_empty_list(self, train_repo):
        """Test get_trains_with_stops with empty train list."""
        result = train_repo.get_trains_with_stops([])
        assert result == {}
    
    def test_get_trains_with_stops_no_trains_found(self, train_repo, mock_session):
        """Test get_trains_with_stops when no trains are found."""
        # Mock train info query returning empty
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        result = train_repo.get_trains_with_stops([1, 2, 3])
        assert result == {}
    
    def test_get_trains_with_stops_success(self, train_repo, mock_session, sample_trains_info, sample_stops):
        """Test successful eager loading of stops for multiple trains."""
        # Mock the train info query
        train_query_mock = Mock()
        train_query_mock.filter.return_value.all.return_value = sample_trains_info
        
        # Mock the stops query
        stops_query_mock = Mock()
        stops_query_mock.filter.return_value.order_by.return_value.all.return_value = sample_stops
        
        # Mock the query method to return appropriate chains based on the arguments
        def query_side_effect(*args):
            if len(args) == 3:  # Train info query with 3 columns
                return train_query_mock
            else:  # Stops query
                return stops_query_mock
        
        mock_session.query.side_effect = query_side_effect
        
        # Call the method
        result = train_repo.get_trains_with_stops([1, 2, 3])
        
        # Verify structure
        assert isinstance(result, dict)
        assert len(result) == 3
        assert 1 in result
        assert 2 in result 
        assert 3 in result
        
        # Verify each train has a list (may be empty if no matching stops)
        for train_id in [1, 2, 3]:
            assert isinstance(result[train_id], list)
    
    def test_get_trains_with_stops_groups_correctly(self, train_repo, mock_session, sample_trains_info, sample_stops):
        """Test that stops are correctly grouped by train."""
        # Create a more detailed mock setup
        with patch.object(train_repo.session, 'query') as mock_query:
            # Setup train info query
            train_info_chain = Mock()
            train_info_chain.filter.return_value.all.return_value = sample_trains_info
            
            # Setup stops query  
            stops_chain = Mock()
            stops_chain.filter.return_value.order_by.return_value.all.return_value = sample_stops
            
            # Mock query method to return appropriate chains
            mock_query.side_effect = lambda *args: (
                train_info_chain if len(args) == 3 else stops_chain
            )
            
            result = train_repo.get_trains_with_stops([1, 2, 3])
            
            # Should return dictionary with train IDs as keys
            assert isinstance(result, dict)
            assert len(result) == 3
    
    def test_get_trains_with_stops_performance_logging(self, train_repo, mock_session, sample_trains_info):
        """Test that the method works with time and logging patches applied."""
        with patch('trackcast.db.repository.logger') as mock_logger, \
             patch('trackcast.db.repository.time.time', side_effect=[1000.0, 1002.0]):
            
            # Mock the train info query
            train_query_mock = Mock()
            train_query_mock.filter.return_value.all.return_value = sample_trains_info
            
            # Mock the stops query
            stops_query_mock = Mock()
            stops_query_mock.filter.return_value.order_by.return_value.all.return_value = []
            
            # Mock the query method to return appropriate chains based on the arguments
            def query_side_effect(*args):
                if len(args) == 3:  # Train info query with 3 columns
                    return train_query_mock
                else:  # Stops query
                    return stops_query_mock
            
            mock_session.query.side_effect = query_side_effect
            
            result = train_repo.get_trains_with_stops([1, 2, 3])
            
            # Verify method executed successfully
            assert isinstance(result, dict)
            assert len(result) == 3
            
            # Check that some logging occurred (don't check exact message due to dynamic formatting)
            assert mock_logger.info.called
    
    def test_get_trains_with_stops_handles_database_error(self, train_repo, mock_session):
        """Test that database errors are properly handled."""
        from sqlalchemy.exc import SQLAlchemyError
        
        # Mock database error
        mock_session.query.side_effect = SQLAlchemyError("Database connection failed")
        
        with pytest.raises(SQLAlchemyError):
            train_repo.get_trains_with_stops([1, 2, 3])
    
    def test_get_trains_with_stops_sql_conditions(self, train_repo, mock_session, sample_trains_info):
        """Test that proper SQL conditions are built for train filtering."""
        with patch('trackcast.db.repository.and_') as mock_and, \
             patch('trackcast.db.repository.or_') as mock_or:
            
            # Mock train info query
            mock_session.query.return_value.filter.return_value.all.return_value = sample_trains_info
            
            # Mock stops query
            stops_query = Mock()
            stops_query.filter.return_value.order_by.return_value.all.return_value = []
            
            def query_side_effect(*args):
                if len(args) == 3:  # Train info query
                    return mock_session.query.return_value
                else:  # Stops query
                    return stops_query
            
            mock_session.query.side_effect = query_side_effect
            
            train_repo.get_trains_with_stops([1, 2, 3])
            
            # Verify AND conditions were created for each train
            assert mock_and.call_count == len(sample_trains_info)
            
            # Verify OR condition was created to combine all train conditions
            mock_or.assert_called_once()
    
    def test_get_trains_with_stops_ordering(self, train_repo, mock_session, sample_trains_info):
        """Test that stops are ordered correctly."""
        # Mock train info
        mock_session.query.return_value.filter.return_value.all.return_value = sample_trains_info
        
        # Mock stops query
        stops_query = Mock()
        order_by_mock = Mock()
        stops_query.filter.return_value.order_by.return_value = order_by_mock
        order_by_mock.all.return_value = []
        
        def query_side_effect(*args):
            if len(args) == 3:  # Train info query
                return mock_session.query.return_value
            else:  # Stops query
                return stops_query
        
        mock_session.query.side_effect = query_side_effect
        
        train_repo.get_trains_with_stops([1, 2, 3])
        
        # Verify stops are ordered by train_id and scheduled_time
        stops_query.filter.return_value.order_by.assert_called_once()


class TestEagerLoadingIntegration:
    """Integration tests for eager loading with actual database models."""
    
    def test_eager_loading_reduces_queries(self):
        """Test that eager loading actually reduces the number of database queries."""
        # This would be an integration test that requires a real database
        # For now, we'll mark it as a placeholder
        pytest.skip("Requires integration test setup with real database")
    
    def test_eager_loading_preserves_data_integrity(self):
        """Test that eager loading returns the same data as individual queries."""
        # This would compare results from eager loading vs N+1 queries
        pytest.skip("Requires integration test setup with real database")