"""Tests for the API module."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

# We'll patch the database dependency for testing
from trackcast.api.routers.trains import get_train_repository, get_train_stop_repository
from trackcast.db.models import Train


@pytest.fixture
def mock_train_repository():
    """Create a mock train repository."""
    return MagicMock()


@pytest.fixture
def mock_train_stop_repository():
    """Create a mock train stop repository."""
    return MagicMock()


@pytest.fixture
def test_client(mock_train_repository, mock_train_stop_repository):
    """Create a test client for the FastAPI app with mocked dependencies."""
    from trackcast.api.app import app

    # Override the dependencies
    app.dependency_overrides[get_train_repository] = lambda: mock_train_repository
    app.dependency_overrides[get_train_stop_repository] = lambda: mock_train_stop_repository

    # Create and return the test client
    client = TestClient(app)

    yield client

    # Clean up after test
    app.dependency_overrides.clear()


class TestTrainsAPI:
    """Tests for the trains API endpoints."""
    
    def test_get_trains(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test getting the list of trains."""
        # Create mock Train objects
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3829"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"  # Provide string value instead of MagicMock
        mock_train.destination = "Trenton"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T09:19:00")
        mock_train.status = ""
        mock_train.track = ""
        mock_train.origin_station_code = "NY"
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T08:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T08:00:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        
        # Mock prediction data
        mock_prediction = MagicMock()
        mock_prediction.track_probabilities = {"1": 0.1, "2": 0.7, "3": 0.2}
        mock_prediction.prediction_factors = [{"feature": "hour_sin", "importance": 0.3, "direction": "positive", "explanation": "Test explanation"}]
        mock_prediction.model_version = "test"
        mock_prediction.created_at = datetime.fromisoformat("2025-05-09T09:00:00")
        mock_train.prediction_data = mock_prediction

        # Configure the mock to return our test data
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []

        # Make the API request
        response = test_client.get("/api/trains")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert "metadata" in data
        assert "trains" in data
        assert len(data["trains"]) == 1
        assert data["trains"][0]["train_id"] == "3829"

        # Test response format matches API schema
        train = data["trains"][0]
        assert "id" in train
        assert "train_id" in train
        assert "line" in train
        assert "destination" in train
        assert "departure_time" in train
        assert "track" in train
        assert "status" in train
        assert "prediction_data" in train
    
    def test_get_trains_with_filters(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test getting trains with filtering parameters."""
        # Create mock Train object
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3829"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"  # Provide string value instead of MagicMock
        mock_train.destination = "Trenton"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T09:19:00")
        mock_train.status = ""
        mock_train.track = ""
        mock_train.origin_station_code = "NY"
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T08:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T08:00:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        mock_train.prediction_data = None

        # Configure the mock to return the same data for any query
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []

        # Test filtering by train_id
        response = test_client.get("/api/trains?train_id=3829")
        assert response.status_code == 200
        assert len(response.json()["trains"]) == 1

        # Test filtering by line
        response = test_client.get("/api/trains?line=Northeast%20Corrdr")
        assert response.status_code == 200

        # Test filtering by departure time range
        response = test_client.get(
            "/api/trains?departure_time_after=2025-05-09T09:00:00&departure_time_before=2025-05-09T10:00:00"
        )
        assert response.status_code == 200

        # Test filtering by has_prediction
        response = test_client.get("/api/trains?has_prediction=true")
        assert response.status_code == 200

        # Verify repository was called
        assert mock_train_repository.get_trains.call_count == 4