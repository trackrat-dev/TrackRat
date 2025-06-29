"""Tests for the enhanced train consolidation service with status_v2 and progress fields."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import logging

from trackcast.services.train_consolidation import TrainConsolidationService
from trackcast.db.models import Train, TrainStop
from trackcast.utils import get_eastern_now


class TestEnhancedConsolidation:
    """Tests for the enhanced consolidation features."""
    
    @pytest.fixture
    def consolidation_service(self):
        """Create a consolidation service instance."""
        return TrainConsolidationService()
    
    @pytest.fixture
    def sample_trains(self):
        """Create sample train records for testing."""
        # Use Eastern time consistently with the consolidation service
        now = get_eastern_now()
        
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
        train1.departure_time = now - timedelta(minutes=10)
        train1.status = "DEPARTED"
        train1.track = "8"
        train1.delay_minutes = 1
        train1.updated_at = now - timedelta(minutes=5)
        
        # Create stops for train1
        stop1_1 = MagicMock(spec=TrainStop)
        stop1_1.station_code = "NY"
        stop1_1.station_name = "New York Penn Station"
        stop1_1.scheduled_arrival = now - timedelta(minutes=11)
        stop1_1.scheduled_departure = now - timedelta(minutes=10)
        stop1_1.actual_arrival = now - timedelta(minutes=10)  # 1 minute late
        stop1_1.actual_departure = now - timedelta(minutes=9)  # 1 minute late
        stop1_1.departed = True
        stop1_1.stop_status = "DEPARTED"
        stop1_1.pickup_only = False
        stop1_1.dropoff_only = False
        
        stop1_2 = MagicMock(spec=TrainStop)
        stop1_2.station_code = "NP"
        stop1_2.station_name = "Newark Penn Station"
        stop1_2.scheduled_arrival = now + timedelta(minutes=10)
        stop1_2.scheduled_departure = now + timedelta(minutes=15)
        stop1_2.actual_arrival = None
        stop1_2.actual_departure = None
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
        train2.departure_time = now - timedelta(minutes=10)
        train2.status = "BOARDING"
        train2.track = "8"
        train2.delay_minutes = 0
        train2.updated_at = now - timedelta(minutes=3)  # More recent than train1
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
        stop1.scheduled_arrival = datetime.now() + timedelta(minutes=30)
        stop1.scheduled_departure = None
        stop1.actual_arrival = None
        stop1.actual_departure = None
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
    
    def test_departure_time_most_recent_wins(self, consolidation_service, caplog):
        """Test that most recent train's departure time wins during consolidation."""
        # Enable debug logging to verify our logic
        caplog.set_level(logging.DEBUG)
        
        # Create first train with older update timestamp
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "7845"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.line = "Northeast Corridor"
        train1.destination = "Trenton"
        train1.departure_time = datetime.now()
        train1.status = "BOARDING"
        train1.track = "2"
        train1.delay_minutes = 0
        train1.updated_at = datetime.now() - timedelta(minutes=5)  # Older update
        
        # Create stops with initial departure times
        stop1_1 = MagicMock(spec=TrainStop)
        stop1_1.station_code = "NY"
        stop1_1.station_name = "New York Penn Station"
        stop1_1.scheduled_arrival = datetime.now()
        stop1_1.scheduled_departure = datetime.now()  # Original departure time
        stop1_1.actual_arrival = datetime.now()
        stop1_1.actual_departure = datetime.now()
        stop1_1.departed = True
        stop1_1.stop_status = "BOARDING"
        stop1_1.pickup_only = False
        stop1_1.dropoff_only = False
        
        stop1_2 = MagicMock(spec=TrainStop)
        stop1_2.station_code = "NP"
        stop1_2.station_name = "Newark Penn Station"
        stop1_2.scheduled_arrival = datetime.now() + timedelta(minutes=20)
        stop1_2.scheduled_departure = datetime.now() + timedelta(minutes=20)  # Original time
        stop1_2.actual_arrival = None
        stop1_2.actual_departure = None
        stop1_2.departed = False
        stop1_2.stop_status = ""
        stop1_2.pickup_only = False
        stop1_2.dropoff_only = False
        
        train1.stops = [stop1_1, stop1_2]
        
        # Create second train with more recent updates from NJ Transit API
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "7845"
        train2.origin_station_code = "NP"
        train2.origin_station_name = "Newark Penn Station"
        train2.data_source = "njtransit"
        train2.line = "Northeast Corridor"
        train2.destination = "Trenton"
        train2.departure_time = datetime.now() + timedelta(minutes=20)
        train2.status = ""
        train2.track = "4"
        train2.delay_minutes = 1
        train2.updated_at = datetime.now() - timedelta(minutes=1)  # More recent update
        
        # Create stops with updated departure times from dynamic API
        stop2_1 = MagicMock(spec=TrainStop)
        stop2_1.station_code = "NY"
        stop2_1.station_name = "New York Penn Station"
        stop2_1.scheduled_arrival = datetime.now()
        stop2_1.scheduled_departure = datetime.now() + timedelta(seconds=30)  # Updated departure time
        stop2_1.actual_arrival = datetime.now()
        stop2_1.actual_departure = datetime.now() + timedelta(seconds=30)
        stop2_1.departed = True
        stop2_1.stop_status = ""
        stop2_1.pickup_only = False
        stop2_1.dropoff_only = False
        
        stop2_2 = MagicMock(spec=TrainStop)
        stop2_2.station_code = "NP"
        stop2_2.station_name = "Newark Penn Station"
        stop2_2.scheduled_arrival = datetime.now() + timedelta(minutes=20)
        stop2_2.scheduled_departure = datetime.now() + timedelta(minutes=21, seconds=45)  # Updated time
        stop2_2.actual_arrival = None
        stop2_2.actual_departure = None
        stop2_2.departed = False
        stop2_2.stop_status = ""
        stop2_2.pickup_only = False
        stop2_2.dropoff_only = False
        
        train2.stops = [stop2_1, stop2_2]
        
        # Consolidate trains
        consolidated = consolidation_service.consolidate_trains([train1, train2])
        
        assert len(consolidated) == 1
        train = consolidated[0]
        
        # Verify that the more recent departure times were used
        stops = train["stops"]
        ny_stop = next(s for s in stops if s["station_code"] == "NY")
        np_stop = next(s for s in stops if s["station_code"] == "NP")
        
        # The departure times should match train2's times (more recent)
        assert ny_stop["scheduled_departure"] == stop2_1.scheduled_departure.isoformat()
        assert np_stop["scheduled_departure"] == stop2_2.scheduled_departure.isoformat()
        
        # Verify debug logs show the correct decision-making
        assert any("Using more recent scheduled departure from NP" in record.message for record in caplog.records)
    
    def test_departure_time_null_handling(self, consolidation_service):
        """Test handling of null departure times during consolidation."""
        # Create train with no departure times
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "7845"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.line = "Northeast Corridor"
        train1.destination = "Trenton"
        train1.departure_time = datetime.now()
        train1.status = ""
        train1.track = None
        train1.delay_minutes = 0
        train1.updated_at = datetime.now() - timedelta(minutes=5)
        
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.station_name = "New York Penn Station"
        stop1.scheduled_arrival = datetime.now()
        stop1.scheduled_departure = None  # No departure time
        stop1.actual_arrival = None
        stop1.actual_departure = None
        stop1.departed = False
        stop1.stop_status = ""
        stop1.pickup_only = False
        stop1.dropoff_only = False
        
        train1.stops = [stop1]
        
        # Create second train with departure time
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "7845"
        train2.origin_station_code = "NY"
        train2.origin_station_name = "New York Penn Station"
        train2.data_source = "amtrak"
        train2.line = "Northeast Corridor"
        train2.destination = "Trenton"
        train2.departure_time = datetime.now()
        train2.status = ""
        train2.track = None
        train2.delay_minutes = 0
        train2.updated_at = datetime.now()  # More recent
        
        stop2 = MagicMock(spec=TrainStop)
        stop2.station_code = "NY"
        stop2.station_name = "New York Penn Station"
        stop2.scheduled_arrival = datetime.now()
        stop2.scheduled_departure = datetime.now() + timedelta(seconds=15)  # Has departure time
        stop2.actual_arrival = None
        stop2.actual_departure = None
        stop2.departed = False
        stop2.stop_status = ""
        stop2.pickup_only = False
        stop2.dropoff_only = False
        
        train2.stops = [stop2]
        
        # Consolidate trains
        consolidated = consolidation_service.consolidate_trains([train1, train2])
        
        assert len(consolidated) == 1
        train = consolidated[0]
        
        # Verify the departure time from train2 was used
        ny_stop = train["stops"][0]
        assert ny_stop["scheduled_departure"] == stop2.scheduled_departure.isoformat()


class TestTrackAssignmentConsolidation:
    """Tests specifically for track assignment consolidation logic."""
    
    @pytest.fixture
    def consolidation_service(self):
        """Create a consolidation service instance."""
        return TrainConsolidationService()
    
    def test_empty_track_from_true_origin_falls_back_to_other_sources(self, consolidation_service):
        """
        Test that when the true origin station has an empty track,
        the system falls back to other sources with non-empty tracks.
        
        This is the regression test for the bug where train A97 had:
        - NY (true origin) via NJTransit: empty track ""
        - NY via Amtrak: track "14"  
        But consolidation returned null track because it stopped at the empty NJTransit track.
        """
        now = get_eastern_now()
        
        # Train 1: NY origin via NJTransit with EMPTY track (the bug scenario)
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "A97"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.line = "SILVER METEOR-R"
        train1.destination = "Miami"
        train1.departure_time = now
        train1.status = ""
        train1.track = ""  # Empty track - this was causing the bug
        train1.track_assigned_at = None
        train1.delay_minutes = None
        train1.updated_at = now - timedelta(minutes=5)
        
        # Train 2: NY origin via Amtrak with NON-EMPTY track
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "A97"
        train2.origin_station_code = "NY"
        train2.origin_station_name = "New York Penn Station"
        train2.data_source = "amtrak"
        train2.line = "SILVER METEOR-R"
        train2.destination = "Miami"
        train2.departure_time = now
        train2.status = "BOARDING"
        train2.track = "14"  # Has track - should be used
        train2.track_assigned_at = now - timedelta(minutes=10)
        train2.delay_minutes = 7
        train2.updated_at = now - timedelta(minutes=2)
        
        # Train 3: Another station with track (should be ignored due to priority)
        train3 = MagicMock(spec=Train)
        train3.id = 3
        train3.train_id = "A97"
        train3.origin_station_code = "NP"
        train3.origin_station_name = "Newark Penn Station"
        train3.data_source = "njtransit"
        train3.line = "SILVER METEOR-R"
        train3.destination = "Miami"
        train3.departure_time = now + timedelta(minutes=20)
        train3.status = "10 MINS LATE"
        train3.track = "3"
        train3.track_assigned_at = now - timedelta(minutes=3)
        train3.delay_minutes = None
        train3.updated_at = now - timedelta(minutes=1)
        
        # Mock stops for journey matching - need actual stops for true origin detection
        
        # Create stops for train1 (NY origin) - EARLIEST time makes this true origin
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.scheduled_arrival = now - timedelta(minutes=30)  # Earliest time
        train1.stops = [stop1]
        
        # Create stops for train2 (NY origin) 
        stop2 = MagicMock(spec=TrainStop)
        stop2.station_code = "NY"
        stop2.scheduled_arrival = now - timedelta(minutes=30)  # Same time as train1
        train2.stops = [stop2]
        
        # Create stops for train3 (NP origin) - LATER time, not true origin
        stop3 = MagicMock(spec=TrainStop)
        stop3.station_code = "NP"
        stop3.scheduled_arrival = now - timedelta(minutes=10)  # Later than NY
        train3.stops = [stop3]
        
        # Test the _merge_track_assignment method directly
        track_assignment = consolidation_service._merge_track_assignment([train1, train2, train3])
        
        # The track assignment should come from the Amtrak source (train2)
        # not the empty NJTransit source, even though both are from the true origin (NY)
        assert track_assignment["track"] == "14"
        assert track_assignment["assigned_by"] == "NY"
        assert track_assignment["source"] == "amtrak"
        assert track_assignment["assigned_at"] is not None
        
        # Verify it's using train2's data
        expected_time = train2.track_assigned_at.isoformat()
        assert track_assignment["assigned_at"] == expected_time
    
    def test_true_origin_with_track_takes_priority_over_later_stations(self, consolidation_service):
        """
        Test that when the true origin station has a non-empty track,
        it takes priority over tracks from later stations, even if those are more recent.
        """
        now = get_eastern_now()
        
        # Train 1: NY origin with track (should win due to true origin priority)
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "3456"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.track = "12"
        train1.track_assigned_at = now - timedelta(minutes=15)  # Older assignment
        train1.departure_time = now
        train1.updated_at = now - timedelta(minutes=10)
        
        # Train 2: Later station with more recent track assignment
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "3456"
        train2.origin_station_code = "NP"
        train2.origin_station_name = "Newark Penn Station"
        train2.data_source = "njtransit"
        train2.track = "5"
        train2.track_assigned_at = now - timedelta(minutes=2)  # More recent
        train2.departure_time = now + timedelta(minutes=20)
        train2.updated_at = now - timedelta(minutes=1)
        
        # Mock stops for true origin detection
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.scheduled_arrival = now - timedelta(minutes=30)  # Earliest time
        train1.stops = [stop1]
        
        stop2 = MagicMock(spec=TrainStop)
        stop2.station_code = "NP"
        stop2.scheduled_arrival = now - timedelta(minutes=10)  # Later time
        train2.stops = [stop2]
        
        # Test the _merge_track_assignment method directly
        track_assignment = consolidation_service._merge_track_assignment([train1, train2])
        
        # Should use track from true origin (NY), not the more recent one from NP
        assert track_assignment["track"] == "12"
        assert track_assignment["assigned_by"] == "NY"
        assert track_assignment["source"] == "njtransit"
    
    def test_fallback_to_most_recent_when_no_true_origin_track(self, consolidation_service):
        """
        Test that when the true origin has no track assignment,
        the system falls back to the most recent track assignment from any station.
        """
        now = get_eastern_now()
        
        # Train 1: True origin with NO track
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "7890"
        train1.origin_station_code = "NY"
        train1.origin_station_name = "New York Penn Station"
        train1.data_source = "njtransit"
        train1.track = None  # No track
        train1.track_assigned_at = None
        train1.departure_time = now
        train1.updated_at = now - timedelta(minutes=10)
        
        # Train 2: Later station with older track assignment
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "7890"
        train2.origin_station_code = "NP"
        train2.origin_station_name = "Newark Penn Station"
        train2.data_source = "njtransit"
        train2.track = "3"
        train2.track_assigned_at = now - timedelta(minutes=10)
        train2.departure_time = now + timedelta(minutes=20)
        train2.updated_at = now - timedelta(minutes=8)
        
        # Train 3: Later station with MORE RECENT track assignment
        train3 = MagicMock(spec=Train)
        train3.id = 3
        train3.train_id = "7890"
        train3.origin_station_code = "TR"
        train3.origin_station_name = "Trenton"
        train3.data_source = "njtransit"
        train3.track = "7"
        train3.track_assigned_at = now - timedelta(minutes=2)  # Most recent
        train3.departure_time = now + timedelta(minutes=60)
        train3.updated_at = now - timedelta(minutes=1)
        
        # Mock stops for true origin detection
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.scheduled_arrival = now - timedelta(minutes=30)  # Earliest time - true origin
        train1.stops = [stop1]
        
        stop2 = MagicMock(spec=TrainStop)
        stop2.station_code = "NP"
        stop2.scheduled_arrival = now - timedelta(minutes=10)  # Later time
        train2.stops = [stop2]
        
        stop3 = MagicMock(spec=TrainStop)
        stop3.station_code = "TR"
        stop3.scheduled_arrival = now + timedelta(minutes=30)  # Latest time
        train3.stops = [stop3]
        
        # Test the _merge_track_assignment method directly
        track_assignment = consolidation_service._merge_track_assignment([train1, train2, train3])
        
        # Should use the most recent track assignment (train3) since true origin has no track
        assert track_assignment["track"] == "7"
        assert track_assignment["assigned_by"] == "TR"
        assert track_assignment["source"] == "njtransit"
    
    def test_no_track_assignment_when_all_tracks_empty(self, consolidation_service):
        """
        Test that when all trains have empty or null tracks,
        the consolidated result has no track assignment.
        """
        now = get_eastern_now()
        
        # Train 1: Empty track
        train1 = MagicMock(spec=Train)
        train1.id = 1
        train1.train_id = "EMPTY"
        train1.origin_station_code = "NY"
        train1.track = ""
        train1.track_assigned_at = None
        train1.departure_time = now
        train1.updated_at = now
        
        # Train 2: Null track
        train2 = MagicMock(spec=Train)
        train2.id = 2
        train2.train_id = "EMPTY"
        train2.origin_station_code = "NP"
        train2.track = None
        train2.track_assigned_at = None
        train2.departure_time = now + timedelta(minutes=20)
        train2.updated_at = now
        
        # Mock stops for journey matching
        stop1 = MagicMock(spec=TrainStop)
        stop1.station_code = "NY"
        stop1.scheduled_arrival = now - timedelta(minutes=30)
        train1.stops = [stop1]
        
        stop2 = MagicMock(spec=TrainStop)
        stop2.station_code = "NP"
        stop2.scheduled_arrival = now - timedelta(minutes=10)
        train2.stops = [stop2]
        
        # Test the _merge_track_assignment method directly
        track_assignment = consolidation_service._merge_track_assignment([train1, train2])
        
        # Should have no track assignment
        assert track_assignment["track"] is None
        assert track_assignment["assigned_at"] is None
        assert track_assignment["assigned_by"] is None
        assert track_assignment["source"] is None