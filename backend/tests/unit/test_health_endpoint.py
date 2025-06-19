"""Tests for the enhanced health endpoint with database metrics."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from trackcast.api.app import app
from trackcast.db.connection import get_db


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def test_client(mock_db_session):
    """Create a test client with mocked database dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Tests for the health endpoint."""

    def test_health_endpoint_basic_structure(self, test_client, mock_db_session):
        """Test that health endpoint returns expected structure."""
        # Mock database connection check
        mock_db_session.execute.return_value = True
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model_NY.pt", "model_TR.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            # Mock external API responses
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check basic structure
            assert "status" in data
            assert "timestamp" in data
            assert "checks" in data
            
            # Verify all checks are present
            assert "database" in data["checks"]
            assert "models" in data["checks"]
            assert "environment" in data["checks"]

    def test_health_endpoint_with_database_metrics(self, test_client, mock_db_session):
        """Test health endpoint with database metrics when DB is healthy."""
        # Mock database connection success
        mock_db_session.execute.return_value = True
        
        # Mock time references
        current_time = datetime.utcnow()
        
        # Create a flexible mock that handles all query patterns
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        
        # Handle both direct scalar calls and filter->scalar chains
        mock_query.scalar.return_value = current_time - timedelta(minutes=2)  # For func.max queries
        
        # Create filter mock that can handle chained calls
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter  # Allow chaining
        
        # Set up scalar results for filtered queries
        scalar_results = [
            50,   # trains_last_hour
            1200, # trains_last_24h
            35,   # trains_with_predictions
            40,   # trains_with_tracks
            15,   # active_trains
            5,    # trains_missing_fields
        ]
        mock_filter.scalar.side_effect = scalar_results
        
        # Handle group_by queries for source breakdown
        mock_group = MagicMock()
        mock_filter.group_by.return_value = mock_group
        mock_query.group_by.return_value = mock_group
        
        # Return values for group_by().all() calls
        group_results = [
            [("njtransit", 30), ("amtrak", 20)],   # by data source
            [("NY", 25), ("TR", 15), ("NP", 10)]   # by station
        ]
        mock_group.all.side_effect = group_results
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model_NY.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            # Mock external API responses
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify database metrics are present
            assert "database_metrics" in data["checks"]
            db_metrics = data["checks"]["database_metrics"]
            
            # Check all metric categories
            assert "basic_counts" in db_metrics
            assert "data_freshness" in db_metrics
            assert "source_breakdown" in db_metrics
            assert "quality_metrics" in db_metrics
            
            # Verify basic counts
            counts = db_metrics["basic_counts"]
            assert counts["trains_last_hour"] == 50
            assert counts["trains_last_24h"] == 1200
            assert counts["trains_with_predictions_last_hour"] == 35
            assert counts["trains_with_tracks_last_hour"] == 40
            assert counts["active_trains"] == 15
            assert counts["trains_missing_critical_fields"] == 5
            
            # Verify quality metrics
            quality = db_metrics["quality_metrics"]
            assert quality["track_assignment_rate"] == 80.0  # 40/50 * 100
            assert quality["prediction_rate"] == 70.0  # 35/50 * 100
            assert quality["missing_fields_rate"] == 10.0  # 5/50 * 100

    def test_health_endpoint_with_stale_data_warning(self, test_client, mock_db_session):
        """Test health endpoint shows warning when data is stale."""
        # Mock database connection success
        mock_db_session.execute.return_value = True
        
        # Mock time references - data is 10 minutes old
        current_time = datetime.utcnow()
        stale_time = current_time - timedelta(minutes=10)
        
        # Create a flexible mock that handles all query patterns
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        
        # Handle both direct scalar calls and filter->scalar chains
        mock_query.scalar.return_value = stale_time  # For func.max queries - return stale time
        
        # Create filter mock that can handle chained calls
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter  # Allow chaining
        
        # Set up scalar results for filtered queries
        scalar_results = [
            10,   # trains_last_hour
            500,  # trains_last_24h
            5,    # trains_with_predictions
            8,    # trains_with_tracks
            5,    # active_trains
            0,    # trains_missing_fields
        ]
        mock_filter.scalar.side_effect = scalar_results
        
        # Handle group_by queries for source breakdown
        mock_group = MagicMock()
        mock_filter.group_by.return_value = mock_group
        mock_query.group_by.return_value = mock_group
        
        # Return empty results for group_by().all() calls (no recent data)
        mock_group.all.return_value = []
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check that database metrics show warning status
            db_metrics = data["checks"]["database_metrics"]
            assert db_metrics["status"] == "warning"
            
            # Verify stale data warning is true
            assert db_metrics["data_freshness"]["stale_data_warning"] is True
            assert db_metrics["data_freshness"]["minutes_since_last_train"] > 5

    def test_health_endpoint_database_failure(self, test_client, mock_db_session):
        """Test health endpoint when database connection fails."""
        # Mock database connection failure
        mock_db_session.execute.side_effect = Exception("Database connection failed")
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            # Should return 503 when database is unhealthy
            assert response.status_code == 503
            data = response.json()
            
            assert data["status"] == "unhealthy"
            assert data["checks"]["database"]["status"] == "unhealthy"
            assert "Database connection failed" in data["checks"]["database"]["message"]
            
            # Database metrics should not be present when DB is down
            assert "database_metrics" not in data["checks"]

    def test_health_endpoint_database_metrics_error(self, test_client, mock_db_session):
        """Test health endpoint handles errors during metrics collection gracefully."""
        # Mock database connection success
        mock_db_session.execute.return_value = True
        
        # Mock query failure during metrics collection
        mock_query = MagicMock()
        mock_db_session.query.side_effect = Exception("Query failed")
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Database should be healthy but metrics should show error
            assert data["checks"]["database"]["status"] == "healthy"
            assert data["checks"]["database_metrics"]["status"] == "error"
            assert "Failed to gather database metrics" in data["checks"]["database_metrics"]["message"]

    def test_health_endpoint_no_trains_in_database(self, test_client, mock_db_session):
        """Test health endpoint when database has no trains."""
        # Mock database connection success
        mock_db_session.execute.return_value = True
        
        # Create a flexible mock that handles all query patterns
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        
        # Handle both direct scalar calls and filter->scalar chains
        mock_query.scalar.return_value = None  # For func.max queries - no data
        
        # Create filter mock that can handle chained calls
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter  # Allow chaining
        
        # Set up scalar results for filtered queries - all zeros
        mock_filter.scalar.return_value = 0
        
        # Handle group_by queries for source breakdown
        mock_group = MagicMock()
        mock_filter.group_by.return_value = mock_group
        mock_query.group_by.return_value = mock_group
        
        # Return empty results for group_by().all() calls
        mock_group.all.return_value = []
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            db_metrics = data["checks"]["database_metrics"]
            
            # All counts should be 0
            counts = db_metrics["basic_counts"]
            assert all(v == 0 for v in counts.values())
            
            # Rates should be 0 (not NaN or error)
            quality = db_metrics["quality_metrics"]
            assert quality["track_assignment_rate"] == 0
            assert quality["prediction_rate"] == 0
            assert quality["missing_fields_rate"] == 0
            
            # No recent train/prediction times
            assert db_metrics["data_freshness"]["most_recent_train"] is None
            assert db_metrics["data_freshness"]["most_recent_prediction"] is None

    @patch.dict(os.environ, {"MODEL_PATH": "/custom/models", "TRACKCAST_ENV": "test", "DATABASE_URL": "postgresql://test"})
    def test_health_endpoint_environment_check(self, test_client, mock_db_session):
        """Test health endpoint environment configuration check."""
        # Mock database connection success
        mock_db_session.execute.return_value = True
        
        # Create a flexible mock that handles all query patterns
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        
        # Handle both direct scalar calls and filter->scalar chains
        mock_query.scalar.return_value = None  # For func.max queries
        
        # Create filter mock that can handle chained calls
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter  # Allow chaining
        
        # Set up scalar results for filtered queries - all zeros
        mock_filter.scalar.return_value = 0
        
        # Handle group_by queries for source breakdown
        mock_group = MagicMock()
        mock_filter.group_by.return_value = mock_group
        mock_query.group_by.return_value = mock_group
        
        # Return empty results for group_by().all() calls
        mock_group.all.return_value = []
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["model.pt"]), \
             patch("httpx.AsyncClient") as mock_http_client:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check environment configuration
            env_check = data["checks"]["environment"]
            assert env_check["status"] == "healthy"
            assert env_check["message"] == "All required environment variables configured"