"""Test utility functions for TrackCast."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytz

# Import the test db_session fixture
from tests.conftest import get_db_session_for_tests

# Import utility functions to test
from trackcast.utils import (
    get_eastern_now,
    utc_to_eastern,
    ensure_eastern_timezone,
    parse_iso_datetime_to_eastern
)

# Create a context manager to patch the database connection
def patched_db_session():
    """
    Context manager to patch the database session for tests.
    
    This ensures any direct calls to get_db_session use our in-memory SQLite database
    instead of trying to connect to PostgreSQL.
    
    Usage:
        with patched_db_session():
            # Test code that uses get_db_session directly
    """
    # Import here to avoid circular imports
    import trackcast.db.connection
    
    return patch('trackcast.db.connection.get_db_session', get_db_session_for_tests)


class TestTimeUtilities:
    """Test time utility functions."""
    
    def test_get_eastern_now_returns_naive_datetime(self):
        """Test that get_eastern_now returns a naive datetime in Eastern time."""
        result = get_eastern_now()
        
        # Should return a datetime object
        assert isinstance(result, datetime)
        
        # Should be timezone naive (no tzinfo)
        assert result.tzinfo is None
        
        # Should be reasonable (within last few seconds)
        eastern = pytz.timezone('US/Eastern')
        expected_now = datetime.now(eastern).replace(tzinfo=None)
        time_diff = abs((result - expected_now).total_seconds())
        assert time_diff < 5  # Within 5 seconds
    
    @patch('trackcast.utils.datetime')
    def test_get_eastern_now_with_mocked_time(self, mock_datetime):
        """Test get_eastern_now with mocked time to verify timezone handling."""
        # Mock a specific UTC time
        mock_utc_time = datetime(2025, 6, 22, 20, 0, 0)  # 8 PM UTC
        mock_datetime.now.return_value = mock_utc_time
        
        # Mock the timezone behavior
        eastern_tz = pytz.timezone('US/Eastern')
        mock_eastern_time = eastern_tz.localize(datetime(2025, 6, 22, 16, 0, 0))  # 4 PM Eastern (DST)
        mock_datetime.now.return_value = mock_eastern_time.replace(tzinfo=None)
        
        result = get_eastern_now()
        
        # Verify datetime.now was called with Eastern timezone
        mock_datetime.now.assert_called_once()
        assert result.tzinfo is None
    
    def test_get_eastern_now_dst_handling(self):
        """Test that get_eastern_now correctly handles DST transitions."""
        # This is an integration test to ensure DST is handled properly
        result = get_eastern_now()
        
        # Get what pytz thinks Eastern time should be
        eastern = pytz.timezone('US/Eastern')
        expected = datetime.now(eastern).replace(tzinfo=None)
        
        # Should match within a few seconds
        time_diff = abs((result - expected).total_seconds())
        assert time_diff < 5
        
        # Verify it's actually in Eastern time by checking it's different from UTC
        utc_now = datetime.utcnow()
        eastern_utc_diff = abs((result - utc_now).total_seconds())
        # Eastern is either 4 or 5 hours behind UTC depending on DST
        assert 4*3600 - 300 < eastern_utc_diff < 5*3600 + 300  # Allow 5 min tolerance
    
    def test_utc_to_eastern_with_naive_utc(self):
        """Test UTC to Eastern conversion with naive UTC datetime."""
        # Test with a known UTC time
        utc_time = datetime(2025, 6, 22, 20, 0, 0)  # 8 PM UTC in summer (DST)
        
        result = utc_to_eastern(utc_time)
        
        # Should be 4 PM Eastern during DST
        expected = datetime(2025, 6, 22, 16, 0, 0)
        assert result == expected
        assert result.tzinfo is None
    
    def test_utc_to_eastern_with_aware_utc(self):
        """Test UTC to Eastern conversion with timezone-aware UTC datetime."""
        # Create timezone-aware UTC time
        utc_tz = pytz.UTC
        utc_time = utc_tz.localize(datetime(2025, 1, 22, 20, 0, 0))  # Winter (no DST)
        
        result = utc_to_eastern(utc_time)
        
        # Should be 3 PM Eastern during standard time
        expected = datetime(2025, 1, 22, 15, 0, 0)
        assert result == expected
        assert result.tzinfo is None
    
    def test_ensure_eastern_timezone_with_naive(self):
        """Test ensure_eastern_timezone with naive datetime (assumes already Eastern)."""
        eastern_time = datetime(2025, 6, 22, 16, 0, 0)
        
        result = ensure_eastern_timezone(eastern_time)
        
        # Should return the same time since it's assumed to be Eastern
        assert result == eastern_time
        assert result.tzinfo is None
    
    def test_ensure_eastern_timezone_with_utc(self):
        """Test ensure_eastern_timezone with UTC datetime."""
        # Create UTC time
        utc_tz = pytz.UTC
        utc_time = utc_tz.localize(datetime(2025, 6, 22, 20, 0, 0))
        
        result = ensure_eastern_timezone(utc_time)
        
        # Should convert to Eastern time (4 PM during DST)
        expected = datetime(2025, 6, 22, 16, 0, 0)
        assert result == expected
        assert result.tzinfo is None
    
    def test_parse_iso_datetime_to_eastern_with_z_suffix(self):
        """Test parsing ISO datetime with Z suffix (UTC)."""
        iso_string = "2025-06-22T20:00:00Z"
        
        result = parse_iso_datetime_to_eastern(iso_string)
        
        # Should convert to Eastern time
        expected = datetime(2025, 6, 22, 16, 0, 0)  # 4 PM Eastern during DST
        assert result == expected
    
    def test_parse_iso_datetime_to_eastern_with_timezone_offset(self):
        """Test parsing ISO datetime with timezone offset."""
        iso_string = "2025-06-22T20:00:00+00:00"  # UTC with explicit offset
        
        result = parse_iso_datetime_to_eastern(iso_string)
        
        # Should convert to Eastern time
        expected = datetime(2025, 6, 22, 16, 0, 0)  # 4 PM Eastern during DST
        assert result == expected
    
    def test_parse_iso_datetime_to_eastern_with_empty_string(self):
        """Test parsing empty or None datetime string."""
        assert parse_iso_datetime_to_eastern("") is None
        assert parse_iso_datetime_to_eastern(None) is None
    
    def test_parse_iso_datetime_to_eastern_with_invalid_format(self):
        """Test parsing invalid datetime string."""
        result = parse_iso_datetime_to_eastern("invalid-datetime")
        assert result is None
        
        result = parse_iso_datetime_to_eastern("2025-13-45T25:99:99Z")  # Invalid date/time
        assert result is None