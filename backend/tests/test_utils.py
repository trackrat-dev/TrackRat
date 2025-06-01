"""Test utility functions for TrackCast."""

import pytest
from unittest.mock import patch

# Import the test db_session fixture
from tests.conftest import get_db_session_for_tests

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