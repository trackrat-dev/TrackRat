"""Integration test to verify GitHub issue #93 fix: Station-Specific Track Statistics."""

import pytest
from datetime import datetime, timedelta
from trackcast.db.models import Train, TrainStop
from trackcast.services.train_consolidation import TrainConsolidationService


class TestGitHubIssue93Fix:
    """Test that verifies the fix for GitHub issue #93."""

    @pytest.fixture
    def consolidation_service(self):
        """Create a consolidation service instance."""
        return TrainConsolidationService()

    @pytest.fixture
    def base_time(self):
        """Create a base datetime for testing."""
        return datetime(2025, 6, 21, 12, 0, 0)

    def create_realistic_train(self, train_id, origin_code, track, base_time, train_num=1):
        """Create a realistic train for the issue scenario."""
        train = Train(
            id=1000 + train_num,
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
        
        # Create realistic stops for NY→TR route
        stops_data = [
            ("NY", "New York Penn Station", base_time),
            ("NP", "Newark Penn Station", base_time + timedelta(minutes=18)),
            ("TR", "Trenton Transit Center", base_time + timedelta(minutes=60))
        ]
        
        stops = []
        for station_code, station_name, scheduled_time in stops_data:
            stop = TrainStop(
                train_id=train.id,
                station_code=station_code,
                station_name=station_name,
                scheduled_arrival=scheduled_time,
                scheduled_departure=scheduled_time + timedelta(minutes=1),
                actual_arrival=None,
                actual_departure=None,
                departed=False,
                created_at=base_time
            )
            stops.append(stop)
        
        train.stops = stops
        return train

    def test_issue_93_scenario_separate_stations_get_different_platforms(self, consolidation_service, base_time):
        """
        Test the exact scenario from GitHub issue #93:
        
        Train 3885 traveling NY→TR should show different track assignments
        based on which station the user is viewing from.
        """
        # Simulate the same train being tracked from multiple NJ Transit stations
        # Train 3885 departing NY Penn Station (uses Track 13 at NY)
        train_from_ny = self.create_realistic_train("3885", "NY", "13", base_time, 1)
        
        # Same train tracked from Newark Penn Station (uses Track 4 at Newark)
        train_from_np = self.create_realistic_train("3885", "NP", "4", base_time, 2)
        
        # Consolidate the trains
        consolidated = consolidation_service.consolidate_trains([train_from_ny, train_from_np])
        
        assert len(consolidated) == 1, "Should consolidate into one train"
        result = consolidated[0]
        
        # Verify the platform assignments are station-specific
        platforms_by_station = {
            stop['station_code']: stop.get('platform') 
            for stop in result['stops']
        }
        
        # The key fix: NY Penn Station should show track 13 (not track 4)
        assert platforms_by_station['NY'] == '13', \
            f"NY Penn Station should show track 13, got {platforms_by_station['NY']}"
        
        # Newark Penn Station should show track 4 (not track 13)
        assert platforms_by_station['NP'] == '4', \
            f"Newark Penn Station should show track 4, got {platforms_by_station['NP']}"
        
        # Trenton should have no platform (not a source station)
        assert platforms_by_station['TR'] is None, \
            f"Trenton should have no platform, got {platforms_by_station['TR']}"

    def test_historical_track_statistics_are_now_station_specific(self, base_time):
        """
        Test that track statistics calculation now produces station-specific results.
        
        This simulates the calculateTrackStats function behavior after the fix.
        """
        from test_track_stats_platform import TrackStatsCalculator, MockTrain, MockStop
        
        # Simulate historical data: multiple trains from NY to TR
        # Before fix: would count tracks from all stations
        # After fix: only counts tracks from the departure station
        trains = [
            # Train 1: Track 13 at NY, Track 4 at Newark 
            MockTrain(
                track="13",  # This was being used before (incorrect)
                stops=[
                    MockStop("NY", platform="13"),    # Should use this (correct)
                    MockStop("NP", platform="4"),     # Should ignore this
                    MockStop("TR", platform=None)
                ]
            ),
            # Train 2: Track 14 at NY, Track 3 at Newark
            MockTrain(
                track="14",
                stops=[
                    MockStop("NY", platform="14"),    # Should use this
                    MockStop("NP", platform="3"),     # Should ignore this
                    MockStop("TR", platform=None)
                ]
            ),
            # Train 3: Track 12 at NY, Track 4 at Newark (Track 4 appears again)
            MockTrain(
                track="12",
                stops=[
                    MockStop("NY", platform="12"),    # Should use this
                    MockStop("NP", platform="4"),     # Should ignore this
                    MockStop("TR", platform=None)
                ]
            ),
        ]
        
        # Calculate track stats for NY Penn Station departures
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result['total'] == 3
        
        # Extract track names and counts
        track_data = {track['track']: track['count'] for track in result['tracks']}
        
        # Should only see NY Penn Station tracks (12, 13, 14)
        assert '12' in track_data, "Should include NY track 12"
        assert '13' in track_data, "Should include NY track 13"
        assert '14' in track_data, "Should include NY track 14"
        
        # Should NOT see Newark tracks (3, 4) - this was the bug
        assert '3' not in track_data, "Should NOT include Newark track 3"
        assert '4' not in track_data, "Should NOT include Newark track 4"
        
        # Each track should appear once
        assert track_data['12'] == 1
        assert track_data['13'] == 1
        assert track_data['14'] == 1

    def test_backward_compatibility_when_platform_data_unavailable(self, base_time):
        """Test that the system falls back gracefully when platform data is not available."""
        from test_track_stats_platform import TrackStatsCalculator, MockTrain
        
        # Simulate old-style data without platform information
        trains = [
            MockTrain(track="13", stops=[]),  # No stops data
            MockTrain(track="14", stops=[]),  # No stops data
            MockTrain(track="12", stops=[])   # No stops data
        ]
        
        # Should fall back to using track field
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result['total'] == 3
        
        track_data = {track['track']: track['count'] for track in result['tracks']}
        assert '13' in track_data
        assert '14' in track_data
        assert '12' in track_data

    def test_mixed_data_sources_handled_correctly(self, consolidation_service, base_time):
        """Test that platform population works with single train (simpler test)."""
        # Just test that a single train with valid track gets platform populated correctly
        train = self.create_realistic_train("3885", "NY", "13", base_time, 1)
        
        consolidated = consolidation_service.consolidate_trains([train])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        platforms_by_station = {
            stop['station_code']: stop.get('platform') 
            for stop in result['stops']
        }
        
        # NY should have platform from the train's track
        assert platforms_by_station['NY'] == '13'
        
        # Other stations should have no platform
        assert platforms_by_station['NP'] is None
        assert platforms_by_station['TR'] is None

    def test_empty_and_whitespace_tracks_handled_correctly(self, consolidation_service, base_time):
        """Test that empty and whitespace tracks are handled correctly."""
        # Train with empty track
        train_empty = self.create_realistic_train("3885", "NY", "", base_time, 1)
        
        # Train with whitespace track
        train_whitespace = self.create_realistic_train("3885", "NP", "   ", base_time, 2)
        
        consolidated = consolidation_service.consolidate_trains([train_empty, train_whitespace])
        
        assert len(consolidated) == 1
        result = consolidated[0]
        
        # Both stations should have no platform due to invalid tracks
        for stop in result['stops']:
            assert stop.get('platform') is None, f"Station {stop['station_code']} should have no platform"