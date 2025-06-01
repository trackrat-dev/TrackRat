"""Tests for the enhanced train consolidation service with status_v2 and progress fields."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from trackcast.services.train_consolidation import TrainConsolidationService
from trackcast.db.models import Train, TrainStop


class TestEnhancedConsolidation:
    """Tests for the enhanced consolidation features."""
    
    @pytest.fixture
    def consolidation_service(self):
        """Create a consolidation service instance."""
        return TrainConsolidationService()
    
    @pytest.fixture
    def sample_trains(self):
        """Create sample train records for testing."""
        # Create a train that has departed from NY
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "A105"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.line = "REGIONAL"
        train1.line_code = "AM"
        train1.destination = "Washington"
        train1.departure_time = datetime.now() - timedelta(minutes=10)
        train1.status = "DEPARTED"
        train1.track = "8"
        train1.delay_minutes = 1
        train1.updated_at = datetime.now() - timedelta(minutes=5)
        
        # Create stops for train1
        stop1_1 = MagicMock(spec=TrainStop)
        stop1_1.station_code = "NY"
        stop1_1.station_name = "New York Penn Station"
        stop1_1.scheduled_time = datetime.now() - timedelta(minutes=11)
        stop1_1.departure_time = datetime.now() - timedelta(minutes=10)
        stop1_1.departed = True
        stop1_1.stop_status = "DEPARTED"
        stop1_1.pickup_only = False
        stop1_1.dropoff_only = False
        
        stop1_2 = MagicMock(spec=TrainStop)
        stop1_2.station_code = "NP"
        stop1_2.station_name = "Newark Penn Station"
        stop1_2.scheduled_time = datetime.now() + timedelta(minutes=10)
        stop1_2.departure_time = None
        stop1_2.departed = False
        stop1_2.stop_status = ""
        stop1_2.pickup_only = False
        stop1_2.dropoff_only = False
        
        train1.stops = [stop1_1, stop1_2]
        
        # Create a train with BOARDING status from Amtrak (outdated)
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "A105"
        train2.origin_station_code = "NY"
        train2.origin_station_name = "New York Penn Station"
        train2.data_source = "amtrak"
        train2.line = "REGIONAL"
        train2.line_code = "AM"
        train2.destination = "Washington"
        train2.departure_time = datetime.now() - timedelta(minutes=10)
        train2.status = "BOARDING"
        train2.track = "8"
        train2.delay_minutes = 0
        train2.updated_at = datetime.now() - timedelta(minutes=3)  # More recent than train1
        train2.stops = [stop1_1, stop1_2]  # Same stops
        
        return [train1, train2]
    
    def test_status_v2_departed_overrides_boarding(self, consolidation_service, sample_trains):
        """Test that DEPARTED status overrides BOARDING in status_v2."""
        consolidated = consolidation_service.consolidate_trains(sample_trains)
        
        assert len(consolidated) == 1
        train = consolidated[0]
        
        # Check that status_v2 exists
        assert "status_v2" in train
        status_v2 = train["status_v2"]
        
        # Verify the status is EN_ROUTE (not BOARDING)
        assert status_v2["current"] == "EN_ROUTE"
        assert "between" in status_v2["location"]
        assert status_v2["confidence"] == "medium"  # Medium because of conflicting statuses
        assert "NY_njtransit" in status_v2["source"]
        
    def test_progress_tracking(self, consolidation_service, sample_trains):
        """Test that progress tracking is computed correctly."""
        consolidated = consolidation_service.consolidate_trains(sample_trains)
        
        assert len(consolidated) == 1
        train = consolidated[0]
        
        # Check that progress exists
        assert "progress" in train
        progress = train["progress"]
        
        # Verify progress fields
        assert progress["stops_completed"] == 1  # NY has been departed
        assert progress["total_stops"] == 2
        assert progress["journey_percent"] == 50  # 1 of 2 stops completed
        
        # Check last departed
        assert progress["last_departed"] is not None
        assert progress["last_departed"]["station_code"] == "NY"
        assert progress["last_departed"]["delay_minutes"] == 1
        
        # Check next arrival
        assert progress["next_arrival"] is not None
        assert progress["next_arrival"]["station_code"] == "NP"
        assert progress["next_arrival"]["minutes_away"] >= 0
        
    def test_backwards_compatibility(self, consolidation_service, sample_trains):
        """Test that all old fields are still present."""
        consolidated = consolidation_service.consolidate_trains(sample_trains)
        
        assert len(consolidated) == 1
        train = consolidated[0]
        
        # Check all original fields are present
        assert "train_id" in train
        assert "consolidated_id" in train
        assert "origin_station" in train
        assert "destination" in train
        assert "line" in train
        assert "data_sources" in train
        assert "track_assignment" in train
        assert "status_summary" in train
        assert "current_position" in train
        assert "stops" in train
        assert "consolidation_metadata" in train
        
        # Verify old status_summary still works
        assert train["status_summary"]["current_status"] == "In Transit"
        
    def test_scheduled_train_status(self, consolidation_service):
        """Test status_v2 for a scheduled train that hasn't departed yet."""
        # Create a scheduled train
        train = MagicMock(spec=Train)
        train.id = 1
        train.train_id = "7871"
        train.origin_station_code = "NY"
        train.origin_station_name = "New York Penn Station"
        train.data_source = "njtransit"
        train.line = "Northeast Corridor"
        train.line_code = "NEC"
        train.destination = "Trenton"
        train.departure_time = datetime.now() + timedelta(minutes=30)
        train.status = ""
        train.track = None
        train.delay_minutes = 0
        train.updated_at = datetime.now()
        
        # Create future stops
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.station_name = "New York Penn Station"
        stop1.scheduled_time = datetime.now() + timedelta(minutes=30)
        stop1.departure_time = None
        stop1.departed = False
        stop1.stop_status = ""
        stop1.pickup_only = False
        stop1.dropoff_only = False
        
        train.stops = [stop1]
        
        consolidated = consolidation_service.consolidate_trains([train])
        assert len(consolidated) == 1
        
        status_v2 = consolidated[0]["status_v2"]
        assert status_v2["current"] == "SCHEDULED"
        assert "scheduled from" in status_v2["location"]
        assert status_v2["confidence"] == "high"  # Only one source, no conflicts