"""Tests for platform field population in train consolidation."""

import pytest
from datetime import datetime, timedelta
from trackcast.db.models import Train, TrainStop
from trackcast.services.train_consolidation import TrainConsolidationService


class TestPlatformConsolidation:
    """Test platform field population in consolidation service."""

    @pytest.fixture
    def consolidation_service(self):
        """Create a consolidation service instance."""
        return TrainConsolidationService()

    @pytest.fixture
    def base_time(self):
        """Create a base datetime for consistent testing."""
        return datetime(2025, 6, 21, 12, 0, 0)

    def create_train_with_stops(self, train_id, origin_code, track, base_time, station_codes=None):
        """Helper to create a train with stops."""
        if station_codes is None:
            station_codes = ["NY", "NP", "TR"]
            
        train = Train(
            id=hash(f"{train_id}_{origin_code}") % 1000000,  # Unique ID
            train_id=train_id,
            origin_station_code=origin_code,
            origin_station_name=f"{origin_code} Station",
            departure_time=base_time,
            track=track,
            track_assigned_at=base_time if track else None,
            data_source="njtransit",
            status="",
            updated_at=base_time,
            created_at=base_time
        )
        
        # Create stops
        stops = []
        stop_time = base_time
        for i, station_code in enumerate(station_codes):
            stop = TrainStop(
                train_id=train.id,
                station_code=station_code,
                station_name=f"{station_code} Station",
                scheduled_time=stop_time,
                departed=False,  # Use consistent departure status for consolidation
                created_at=base_time
            )
            stops.append(stop)
            stop_time += timedelta(minutes=20)
        
        train.stops = stops
        return train

    def test_platform_populated_for_origin_station(self, consolidation_service, base_time):
        """Test that platform is populated for the origin station."""
        train = self.create_train_with_stops("123", "NY", "13", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Find NY stop
        ny_stop = next((s for s in result['stops'] if s['station_code'] == 'NY'), None)
        assert ny_stop is not None
        assert ny_stop['platform'] == '13'

    def test_platform_not_populated_for_non_origin_stations(self, consolidation_service, base_time):
        """Test that platform is not populated for non-origin stations."""
        train = self.create_train_with_stops("123", "NY", "13", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Check non-origin stops
        for stop in result['stops']:
            if stop['station_code'] != 'NY':
                assert stop['platform'] is None

    def test_multiple_trains_different_origins_populate_correct_platforms(self, consolidation_service, base_time):
        """Test that when consolidating trains from different origins, each gets the correct platform."""
        # Train from NY with track 13
        train_ny = self.create_train_with_stops("123", "NY", "13", base_time)
        
        # Train from NP with track 4 (same train ID for consolidation)
        train_np = self.create_train_with_stops("123", "NP", "4", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train_ny, train_np])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Check that each station has the platform from its origin train
        platforms = {stop['station_code']: stop['platform'] for stop in result['stops']}
        
        assert platforms['NY'] == '13', f"Expected NY platform '13', got {platforms['NY']}"
        assert platforms['NP'] == '4', f"Expected NP platform '4', got {platforms['NP']}"
        assert platforms['TR'] is None, f"Expected TR platform None, got {platforms['TR']}"

    def test_platform_populated_when_stop_already_exists(self, consolidation_service, base_time):
        """Test platform population when stop already exists in consolidation map."""
        # Create two trains with same route but different origins
        train1 = self.create_train_with_stops("123", "NY", "13", base_time)
        train2 = self.create_train_with_stops("123", "NP", "4", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train1, train2])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Both NY and NP should have their respective platforms
        platforms = {stop['station_code']: stop['platform'] for stop in result['stops']}
        assert platforms['NY'] == '13'
        assert platforms['NP'] == '4'

    def test_no_platform_when_train_has_no_track(self, consolidation_service, base_time):
        """Test that no platform is set when train has no track."""
        train = self.create_train_with_stops("123", "NY", None, base_time)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # All stops should have no platform
        for stop in result['stops']:
            assert stop['platform'] is None

    def test_empty_track_string_treated_as_no_track(self, consolidation_service, base_time):
        """Test that empty string track is treated as no track."""
        train = self.create_train_with_stops("123", "NY", "", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # All stops should have no platform
        for stop in result['stops']:
            assert stop['platform'] is None

    def test_platform_overwrite_logic_when_multiple_sources(self, consolidation_service, base_time):
        """Test platform overwrite logic when multiple trains provide platform for same stop."""
        # Create trains where both could provide platform for NY
        train1 = self.create_train_with_stops("123", "NY", "13", base_time)
        train2 = self.create_train_with_stops("123", "NY", "14", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train1, train2])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Should use the first platform (no overwrite since platform already exists)
        ny_stop = next((s for s in result['stops'] if s['station_code'] == 'NY'), None)
        assert ny_stop is not None
        assert ny_stop['platform'] == '13'  # First train's platform

    def test_platform_update_when_existing_stop_has_no_platform(self, consolidation_service, base_time):
        """Test that platform is updated when existing stop has no platform."""
        # This tests the logic in the else branch where we update platform if none exists
        train1 = self.create_train_with_stops("123", "TR", None, base_time)  # No track
        train2 = self.create_train_with_stops("123", "NY", "13", base_time)   # Has track for NY
        
        consolidated = consolidation_service.consolidate_trains([train1, train2])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        platforms = {stop['station_code']: stop['platform'] for stop in result['stops']}
        
        # NY should get platform from train2
        assert platforms['NY'] == '13'
        # TR should remain None (train1 is origin but has no track)
        assert platforms['TR'] is None

    def test_platform_with_whitespace_only_track_treated_as_no_track(self, consolidation_service, base_time):
        """Test that whitespace-only track is treated as no track."""
        train = self.create_train_with_stops("123", "NY", "   ", base_time)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # All stops should have no platform (whitespace track is ignored)
        for stop in result['stops']:
            assert stop['platform'] is None

    def test_platform_with_different_station_codes(self, consolidation_service, base_time):
        """Test platform population with different station codes."""
        stations = ["WAS", "BWI", "BAL", "NY"]
        train = self.create_train_with_stops("123", "WAS", "A", base_time, stations)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Only WAS (origin) should have platform
        platforms = {stop['station_code']: stop['platform'] for stop in result['stops']}
        assert platforms['WAS'] == 'A'
        assert platforms['BWI'] is None
        assert platforms['BAL'] is None
        assert platforms['NY'] is None

    def test_no_stops_doesnt_crash(self, consolidation_service, base_time):
        """Test that trains with no stops don't cause crashes."""
        train = Train(
            id=1,
            train_id="123",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            departure_time=base_time,
            track="13",
            track_assigned_at=base_time,
            data_source="njtransit",
            status="",
            updated_at=base_time,
            created_at=base_time
        )
        train.stops = []  # No stops
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        assert len(result['stops']) == 0

    def test_stops_without_station_codes_are_skipped(self, consolidation_service, base_time):
        """Test that stops without station codes are properly skipped."""
        train = self.create_train_with_stops("123", "NY", "13", base_time)
        
        # Add a stop without station code
        bad_stop = TrainStop(
            train_id=train.id,
            station_code=None,  # Missing station code
            station_name="Unknown Station",
            scheduled_time=base_time + timedelta(hours=1),
            departed=False,
            created_at=base_time
        )
        train.stops.append(bad_stop)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Should only have stops with station codes
        station_codes = [stop['station_code'] for stop in result['stops']]
        assert None not in station_codes
        assert 'NY' in station_codes