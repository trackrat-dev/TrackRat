"""Unit tests for fuzzy time matching functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from trackcast.services.station_mapping import StationMapper


class TestFuzzyTimeMatching:
    """Test cases for fuzzy time matching with 5-minute tolerance."""

    @pytest.fixture
    def station_mapper(self):
        """Create a StationMapper instance."""
        return StationMapper()

    def test_exact_time_match(self, station_mapper):
        """Test that exact times match."""
        time1 = "2025-06-18T18:36:00"
        time2 = "2025-06-18T18:36:00"
        
        assert station_mapper.times_match_within_tolerance(time1, time2) is True

    def test_time_match_within_5_minutes(self, station_mapper):
        """Test times within 5-minute tolerance match."""
        base_time = "2025-06-18T18:36:00"
        
        # Test various differences within 5 minutes
        test_cases = [
            "2025-06-18T18:36:30",   # +30 seconds
            "2025-06-18T18:35:30",   # -30 seconds
            "2025-06-18T18:38:00",   # +2 minutes
            "2025-06-18T18:34:00",   # -2 minutes
            "2025-06-18T18:41:00",   # +5 minutes (exactly at tolerance)
            "2025-06-18T18:31:00",   # -5 minutes (exactly at tolerance)
        ]
        
        for test_time in test_cases:
            assert station_mapper.times_match_within_tolerance(base_time, test_time) is True, \
                f"Time {test_time} should match {base_time} within 5 minutes"

    def test_time_mismatch_beyond_5_minutes(self, station_mapper):
        """Test times beyond 5-minute tolerance don't match."""
        base_time = "2025-06-18T18:36:00"
        
        # Test various differences beyond 5 minutes
        test_cases = [
            "2025-06-18T18:41:01",   # +5 minutes 1 second
            "2025-06-18T18:30:59",   # -5 minutes 1 second
            "2025-06-18T18:46:00",   # +10 minutes
            "2025-06-18T18:26:00",   # -10 minutes
            "2025-06-18T19:36:00",   # +1 hour
            "2025-06-18T17:36:00",   # -1 hour
        ]
        
        for test_time in test_cases:
            assert station_mapper.times_match_within_tolerance(base_time, test_time) is False, \
                f"Time {test_time} should NOT match {base_time} beyond 5 minutes"

    def test_datetime_object_matching(self, station_mapper):
        """Test matching with datetime objects instead of strings."""
        dt1 = datetime(2025, 6, 18, 18, 36, 0)
        dt2 = datetime(2025, 6, 18, 18, 38, 0)  # +2 minutes
        dt3 = datetime(2025, 6, 18, 18, 42, 0)  # +6 minutes
        
        assert station_mapper.times_match_within_tolerance(dt1, dt2) is True
        assert station_mapper.times_match_within_tolerance(dt1, dt3) is False

    def test_mixed_types_matching(self, station_mapper):
        """Test matching between datetime objects and strings."""
        dt1 = datetime(2025, 6, 18, 18, 36, 0)
        str2 = "2025-06-18T18:38:00"  # +2 minutes
        str3 = "2025-06-18T18:42:00"  # +6 minutes
        
        assert station_mapper.times_match_within_tolerance(dt1, str2) is True
        assert station_mapper.times_match_within_tolerance(str2, dt1) is True
        assert station_mapper.times_match_within_tolerance(dt1, str3) is False

    def test_none_handling(self, station_mapper):
        """Test proper handling of None values."""
        time1 = "2025-06-18T18:36:00"
        
        # Both None should match
        assert station_mapper.times_match_within_tolerance(None, None) is True
        
        # One None should not match
        assert station_mapper.times_match_within_tolerance(time1, None) is False
        assert station_mapper.times_match_within_tolerance(None, time1) is False

    def test_custom_tolerance(self, station_mapper):
        """Test custom tolerance values."""
        base_time = "2025-06-18T18:36:00"
        test_time = "2025-06-18T18:37:30"  # +1.5 minutes
        
        # Should match with 2-minute tolerance
        assert station_mapper.times_match_within_tolerance(
            base_time, test_time, tolerance_seconds=120
        ) is True
        
        # Should not match with 1-minute tolerance
        assert station_mapper.times_match_within_tolerance(
            base_time, test_time, tolerance_seconds=60
        ) is False

    def test_edge_case_boundary_conditions(self, station_mapper):
        """Test exact boundary conditions for tolerance."""
        base_time = datetime(2025, 6, 18, 18, 36, 0)
        
        # Exactly 5 minutes difference
        time_plus_300 = base_time + timedelta(seconds=300)
        time_minus_300 = base_time - timedelta(seconds=300)
        
        # Should match at exactly 300 seconds
        assert station_mapper.times_match_within_tolerance(base_time, time_plus_300) is True
        assert station_mapper.times_match_within_tolerance(base_time, time_minus_300) is True
        
        # Should not match at 301 seconds
        time_plus_301 = base_time + timedelta(seconds=301)
        time_minus_301 = base_time - timedelta(seconds=301)
        
        assert station_mapper.times_match_within_tolerance(base_time, time_plus_301) is False
        assert station_mapper.times_match_within_tolerance(base_time, time_minus_301) is False

    def test_invalid_time_format_handling(self, station_mapper):
        """Test handling of invalid time formats."""
        valid_time = "2025-06-18T18:36:00"
        invalid_times = [
            "not-a-time",
            "2025-13-45T25:70:99",  # Invalid date/time
            "",
            "18:36:00",  # Missing date
            123,  # Wrong type
            [],  # Wrong type
        ]
        
        for invalid_time in invalid_times:
            # Should return False for invalid formats, not raise exceptions
            assert station_mapper.times_match_within_tolerance(valid_time, invalid_time) is False
            assert station_mapper.times_match_within_tolerance(invalid_time, valid_time) is False

    def test_timezone_handling(self, station_mapper):
        """Test handling of timezone information."""
        # Times with Z timezone indicator
        time_utc = "2025-06-18T18:36:00Z"
        time_local = "2025-06-18T18:36:00"
        
        # Should match (both treated as same timezone)
        assert station_mapper.times_match_within_tolerance(time_utc, time_local) is True

    def test_microsecond_precision(self, station_mapper):
        """Test that microsecond differences are handled correctly."""
        time1 = "2025-06-18T18:36:00.123456"
        time2 = "2025-06-18T18:36:00.654321"
        
        # Microsecond differences should still match within tolerance
        assert station_mapper.times_match_within_tolerance(time1, time2) is True

    def test_performance_with_large_differences(self, station_mapper):
        """Test performance with very large time differences."""
        base_time = "2025-06-18T18:36:00"
        future_time = "2026-06-18T18:36:00"  # +1 year
        
        # Should quickly determine mismatch for large differences
        assert station_mapper.times_match_within_tolerance(base_time, future_time) is False

    def test_real_world_api_scenarios(self, station_mapper):
        """Test scenarios similar to real API data mismatches."""
        # Scenario 1: NJ Transit (with seconds) vs Amtrak (minute precision)
        nj_time = "2025-06-18T18:36:18"  # From NJ Transit API
        amtrak_time = "2025-06-18T18:36:00"  # From Amtrak API
        
        assert station_mapper.times_match_within_tolerance(nj_time, amtrak_time) is True
        
        # Scenario 2: Different rounding from same source
        time_with_seconds = "2025-06-18T18:36:45"
        time_rounded_up = "2025-06-18T18:37:00"
        
        assert station_mapper.times_match_within_tolerance(time_with_seconds, time_rounded_up) is True
        
        # Scenario 3: Schedule updates (small adjustments)
        scheduled_time = "2025-06-18T18:36:00"
        updated_time = "2025-06-18T18:38:00"  # 2-minute delay
        
        assert station_mapper.times_match_within_tolerance(scheduled_time, updated_time) is True

    def test_symmetric_matching(self, station_mapper):
        """Test that time matching is symmetric (A matches B iff B matches A)."""
        test_pairs = [
            ("2025-06-18T18:36:00", "2025-06-18T18:38:00"),  # Should match
            ("2025-06-18T18:36:00", "2025-06-18T18:42:00"),  # Should not match
            ("2025-06-18T18:36:18", "2025-06-18T18:36:00"),  # Should match
        ]
        
        for time1, time2 in test_pairs:
            result1 = station_mapper.times_match_within_tolerance(time1, time2)
            result2 = station_mapper.times_match_within_tolerance(time2, time1)
            
            assert result1 == result2, \
                f"Matching should be symmetric: {time1} vs {time2}"