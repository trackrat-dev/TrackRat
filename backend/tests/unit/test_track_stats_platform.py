"""Tests for track statistics calculation using platform data (simulating iOS logic)."""

import pytest
from typing import List, Dict, Optional


class MockStop:
    """Mock stop object simulating iOS Stop model."""
    
    def __init__(self, station_code: str, platform: Optional[str] = None):
        self.station_code = station_code
        self.platform = platform


class MockTrain:
    """Mock train object simulating iOS Train model."""
    
    def __init__(self, track: Optional[str] = None, stops: Optional[List[MockStop]] = None):
        self.track = track
        self.stops = stops or []


class TrackStatsCalculator:
    """Python implementation of iOS calculateTrackStats logic for testing."""
    
    @staticmethod
    def calculate_track_stats(trains: List[MockTrain], from_station: Optional[str] = None) -> Optional[Dict]:
        """Calculate track statistics with platform data support."""
        track_counts = {}
        total_trains_with_tracks = 0
        
        for train in trains:
            track_used = False
            
            # If we have a fromStation and the train has stops, look for platform data
            if from_station and train.stops:
                # Find the stop that matches the fromStation
                departure_stop = None
                for stop in train.stops:
                    if stop.station_code == from_station:
                        departure_stop = stop
                        break
                
                if departure_stop and departure_stop.platform and departure_stop.platform.strip():
                    # Use the platform from the specific stop
                    track_counts[departure_stop.platform] = track_counts.get(departure_stop.platform, 0) + 1
                    total_trains_with_tracks += 1
                    track_used = True
            
            # Fallback to train track if no platform was used
            if not track_used and train.track and train.track.strip():
                track_counts[train.track] = track_counts.get(train.track, 0) + 1
                total_trains_with_tracks += 1
        
        if total_trains_with_tracks == 0:
            return None
        
        # Sort tracks by count (descending)
        sorted_tracks = sorted(track_counts.items(), key=lambda x: x[1], reverse=True)
        tracks_with_percentages = [
            {
                "track": track,
                "count": count,
                "percentage": int((count / total_trains_with_tracks) * 100)
            }
            for track, count in sorted_tracks
        ]
        
        return {
            "tracks": tracks_with_percentages,
            "total": total_trains_with_tracks
        }


class TestTrackStatsWithPlatform:
    """Test track statistics calculation using platform data."""

    def test_uses_platform_data_when_available(self):
        """Test that platform data is used when available and fromStation is specified."""
        trains = [
            MockTrain(
                track="13",  # This should be ignored
                stops=[
                    MockStop("NY", platform="12"),  # This should be used
                    MockStop("NP", platform="4"),
                ]
            ),
            MockTrain(
                track="13",  # This should be ignored
                stops=[
                    MockStop("NY", platform="14"),  # This should be used
                    MockStop("NP", platform="3"),
                ]
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 2
        
        # Should use platform data (12, 14) not track data (13, 13)
        track_names = [track["track"] for track in result["tracks"]]
        assert "12" in track_names
        assert "14" in track_names
        assert "13" not in track_names

    def test_fallback_to_track_when_no_from_station(self):
        """Test fallback to track field when no fromStation is specified."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("NY", platform="12"),
                    MockStop("NP", platform="4"),
                ]
            ),
            MockTrain(
                track="14",
                stops=[
                    MockStop("NY", platform="15"),
                    MockStop("NP", platform="3"),
                ]
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station=None)
        
        assert result is not None
        assert result["total"] == 2
        
        # Should use track data (13, 14) not platform data
        track_names = [track["track"] for track in result["tracks"]]
        assert "13" in track_names
        assert "14" in track_names
        assert "12" not in track_names
        assert "15" not in track_names

    def test_fallback_to_track_when_no_stops(self):
        """Test fallback to track field when trains have no stops."""
        trains = [
            MockTrain(track="13", stops=[]),
            MockTrain(track="14", stops=[])
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 2
        
        # Should use track data since no stops available
        track_names = [track["track"] for track in result["tracks"]]
        assert "13" in track_names
        assert "14" in track_names

    def test_fallback_to_track_when_station_not_found(self):
        """Test fallback to track when fromStation is not found in stops."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("NP", platform="4"),
                    MockStop("TR", platform="1"),
                ]
            ),
            MockTrain(
                track="14",
                stops=[
                    MockStop("NP", platform="3"),
                    MockStop("TR", platform="2"),
                ]
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 2
        
        # Should use track data since NY station not found in stops
        track_names = [track["track"] for track in result["tracks"]]
        assert "13" in track_names
        assert "14" in track_names

    def test_handles_empty_platform(self):
        """Test handling of empty platform strings."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("NY", platform=""),  # Empty platform
                    MockStop("NP", platform="4"),
                ]
            ),
            MockTrain(
                track="14",
                stops=[
                    MockStop("NY", platform=None),  # Null platform
                    MockStop("NP", platform="3"),
                ]
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 2
        
        # Should fallback to track data since platforms are empty/null
        track_names = [track["track"] for track in result["tracks"]]
        assert "13" in track_names
        assert "14" in track_names

    def test_handles_whitespace_only_platform(self):
        """Test handling of whitespace-only platform strings."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("NY", platform="   "),  # Whitespace only
                    MockStop("NP", platform="4"),
                ]
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 1
        
        # Should fallback to track data since platform is whitespace
        track_names = [track["track"] for track in result["tracks"]]
        assert "13" in track_names

    def test_mixed_platform_and_track_data(self):
        """Test handling when some trains have platform data and others don't."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("NY", platform="12"),  # Has platform
                    MockStop("NP", platform="4"),
                ]
            ),
            MockTrain(
                track="14",
                stops=[
                    MockStop("NY", platform=""),  # No platform, should use track
                    MockStop("NP", platform="3"),
                ]
            ),
            MockTrain(
                track="15",
                stops=[]  # No stops, should use track
            )
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 3
        
        # Should have mix: platform "12" and tracks "14", "15"
        track_names = [track["track"] for track in result["tracks"]]
        assert "12" in track_names  # From platform
        assert "14" in track_names  # From track (empty platform)
        assert "15" in track_names  # From track (no stops)

    def test_percentage_calculation(self):
        """Test that percentages are calculated correctly."""
        trains = [
            MockTrain(stops=[MockStop("NY", platform="12")]),
            MockTrain(stops=[MockStop("NY", platform="12")]),
            MockTrain(stops=[MockStop("NY", platform="12")]),
            MockTrain(stops=[MockStop("NY", platform="14")]),
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is not None
        assert result["total"] == 4
        
        # Track 12 should be 75% (3/4), Track 14 should be 25% (1/4)
        tracks_by_name = {track["track"]: track for track in result["tracks"]}
        assert tracks_by_name["12"]["percentage"] == 75
        assert tracks_by_name["14"]["percentage"] == 25
        assert tracks_by_name["12"]["count"] == 3
        assert tracks_by_name["14"]["count"] == 1

    def test_returns_none_when_no_trains_with_tracks(self):
        """Test that None is returned when no trains have tracks or platforms."""
        trains = [
            MockTrain(track=None, stops=[MockStop("NY", platform=None)]),
            MockTrain(track="", stops=[MockStop("NY", platform="")]),
            MockTrain(track="   ", stops=[MockStop("NY", platform="   ")]),
        ]
        
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        
        assert result is None

    def test_empty_trains_list(self):
        """Test handling of empty trains list."""
        result = TrackStatsCalculator.calculate_track_stats([], from_station="NY")
        assert result is None

    def test_case_sensitive_station_matching(self):
        """Test that station code matching is case sensitive."""
        trains = [
            MockTrain(
                track="13",
                stops=[
                    MockStop("ny", platform="12"),  # lowercase
                    MockStop("NY", platform="14"),  # uppercase
                ]
            )
        ]
        
        # Should match uppercase NY
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="NY")
        assert result is not None
        assert result["tracks"][0]["track"] == "14"
        
        # Should match lowercase ny
        result = TrackStatsCalculator.calculate_track_stats(trains, from_station="ny")
        assert result is not None
        assert result["tracks"][0]["track"] == "12"