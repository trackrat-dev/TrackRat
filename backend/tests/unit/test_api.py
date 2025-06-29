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
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None
        
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
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None

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


class TestContextPredictionAPI:
    """Tests for context-aware prediction functionality."""

    def test_validation_allows_from_station_code_only(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that validation allows from_station_code without to_station_code."""
        # Create mock train with prediction data
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3765"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
        mock_train.destination = "Princeton Junction"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T14:30:00")
        mock_train.status = "BOARDING"
        mock_train.track = "13"
        mock_train.origin_station_code = "MP"  # Changed to MP so predictions are relevant
        mock_train.origin_station_name = "Metropark"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T14:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T14:25:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None
        
        # Mock prediction data for MP origin train
        mock_prediction = MagicMock()
        mock_prediction.track_probabilities = {"4": 0.85, "3": 0.15}  # MP tracks
        mock_prediction.prediction_factors = [{"feature": "hour_sin", "importance": 0.4, "direction": "positive", "explanation": "Afternoon departure pattern"}]
        mock_prediction.model_version = "1.0.0_MP"  # Metropark model
        mock_prediction.created_at = datetime.fromisoformat("2025-05-09T14:20:00")
        mock_train.prediction_data = mock_prediction

        # Mock train stops including MP
        from trackcast.api.models import TrainStop
        mock_stops = [
            TrainStop(station_code="MP", station_name="Metropark", scheduled_time="2025-05-09T14:30:00", departed=False),
            TrainStop(station_code="NP", station_name="Newark Penn Station", scheduled_time="2025-05-09T14:45:00", departed=False),
            TrainStop(station_code="NY", station_name="New York Penn Station", scheduled_time="2025-05-09T15:00:00", departed=False)
        ]

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = mock_stops

        # Test API call with from_station_code only (should NOT trigger validation error)
        response = test_client.get("/api/trains?from_station_code=MP")
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert "trains" in data
        assert len(data["trains"]) == 1
        
        # Verify train data
        train = data["trains"][0]
        assert train["train_id"] == "3765"
        # With new filtering: MP origin train with MP context should show predictions
        assert train["prediction_data"] is not None
        assert train["prediction_data"]["model_version"] == "1.0.0_MP"
        assert "4" in train["prediction_data"]["track_probabilities"]

    def test_validation_blocks_to_station_code_only(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that validation blocks to_station_code without from_station_code."""
        # Test API call with to_station_code only (should trigger validation error)
        response = test_client.get("/api/trains?to_station_code=TR")
        
        # Verify validation error
        assert response.status_code == 400
        error_data = response.json()
        # Check for error message in various possible locations
        error_message = error_data.get("detail") or error_data.get("message") or str(error_data)
        assert "to_station_code requires from_station_code to be provided" in error_message

    def test_validation_allows_both_station_codes(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that validation allows both from_station_code and to_station_code (journey planning)."""
        # Create mock train
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3765"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
        mock_train.destination = "Trenton"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T14:30:00")
        mock_train.status = "BOARDING"
        mock_train.track = "4"
        mock_train.origin_station_code = "NY"
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T14:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T14:25:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        mock_train.prediction_data = None
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []

        # Test API call with both station codes (should work - journey planning)
        response = test_client.get("/api/trains?from_station_code=MP&to_station_code=TR")
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert "trains" in data
        assert len(data["trains"]) == 1

    def test_validation_blocks_same_station_codes(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that validation blocks identical from_station_code and to_station_code."""
        # Test API call with same station codes (should trigger validation error)
        response = test_client.get("/api/trains?from_station_code=MP&to_station_code=MP")
        
        # Verify validation error
        assert response.status_code == 400
        error_data = response.json()
        # Check for error message in various possible locations
        error_message = error_data.get("detail") or error_data.get("message") or str(error_data)
        assert "from_station_code and to_station_code cannot be the same" in error_message

    def test_validation_allows_no_station_codes(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that validation allows neither station code (original behavior)."""
        # Create mock train
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3829"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
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
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None
        
        # Mock original prediction data (NY model)
        mock_prediction = MagicMock()
        mock_prediction.track_probabilities = {"13": 0.7, "14": 0.3}  # NY tracks
        mock_prediction.prediction_factors = [{"feature": "hour_sin", "importance": 0.3, "direction": "positive", "explanation": "Morning departure pattern"}]
        mock_prediction.model_version = "1.0.0_NY"  # NY model
        mock_prediction.created_at = datetime.fromisoformat("2025-05-09T09:00:00")
        mock_train.prediction_data = mock_prediction

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []

        # Test API call without station codes (should work - original behavior)
        response = test_client.get("/api/trains")
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert "trains" in data
        assert len(data["trains"]) == 1
        
        # Verify original prediction data is preserved
        train = data["trains"][0]
        assert train["prediction_data"]["model_version"] == "1.0.0_NY"
        assert "13" in train["prediction_data"]["track_probabilities"]

    @patch('trackcast.api.routers.trains._filter_prediction_by_station_context')
    def test_context_prediction_enrichment_called(self, mock_filter_context, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that context prediction enrichment is called when from_station_code is provided."""
        # Create mock train
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3765"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
        mock_train.destination = "Princeton Junction"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T14:30:00")
        mock_train.status = "BOARDING"
        mock_train.track = ""
        mock_train.origin_station_code = "NY"
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T14:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T14:25:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        mock_train.prediction_data = None
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []
        mock_filter_context.return_value = mock_train  # Return the same train

        # Test API call with from_station_code
        response = test_client.get("/api/trains?from_station_code=MP")
        
        # Verify context prediction filtering was called
        assert response.status_code == 200
        mock_filter_context.assert_called_once()
        # Verify it was called with the correct station code
        call_args = mock_filter_context.call_args
        assert call_args[0][1] == "MP"  # Second argument should be the station code

    @patch('trackcast.api.routers.trains._filter_prediction_by_station_context')
    def test_context_prediction_enrichment_not_called_without_station(self, mock_filter_context, test_client, mock_train_repository, mock_train_stop_repository):
        """Test that context prediction filtering is NOT called when from_station_code is not provided."""
        # Create mock train
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3829"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
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
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = []

        # Test API call without from_station_code
        response = test_client.get("/api/trains")
        
        # Verify context prediction filtering was NOT called
        assert response.status_code == 200
        mock_filter_context.assert_not_called()

    def test_ios_context_prediction_scenario(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test the specific iOS scenario: train details with from_station_code context filtering."""
        # Create mock train that originated from NY but user is asking about MP context
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3765"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
        mock_train.destination = "Princeton Junction"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T14:30:00")
        mock_train.status = "BOARDING"
        mock_train.track = "13"  # Original NY track assignment
        mock_train.origin_station_code = "NY"  # Train originated from NY
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T14:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T14:25:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None
        
        # Mock NY prediction data (will be filtered out for MP context)
        mock_prediction = MagicMock()
        mock_prediction.track_probabilities = {"13": 0.8, "14": 0.2}  # NY tracks
        mock_prediction.prediction_factors = [{"feature": "destination", "importance": 0.5, "direction": "positive", "explanation": "Princeton Junction trains typically use track 13 at NY Penn"}]
        mock_prediction.model_version = "1.0.0_NY"  # NY model, not MP model
        mock_prediction.created_at = datetime.fromisoformat("2025-05-09T14:20:00")
        mock_train.prediction_data = mock_prediction

        # Mock train stops - train doesn't actually stop at MP in this case
        from trackcast.api.models import TrainStop  
        mock_stops = [
            TrainStop(station_code="NY", station_name="New York Penn Station", scheduled_time="2025-05-09T14:30:00", departed=False),
            TrainStop(station_code="NP", station_name="Newark Penn Station", scheduled_time="2025-05-09T14:45:00", departed=False),
            TrainStop(station_code="TR", station_name="Trenton", scheduled_time="2025-05-09T15:15:00", departed=False)
        ]

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = mock_stops

        # Simulate iOS API call: train details with MP context (but train doesn't stop at MP)
        response = test_client.get("/api/trains?train_id=3765&from_station_code=MP&include_predictions=true")
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert "trains" in data
        assert len(data["trains"]) == 1
        
        # Verify we get the train but without predictions (filtered out)
        train = data["trains"][0]
        assert train["train_id"] == "3765"
        assert train["origin_station_code"] == "NY"  # Train still originated from NY
        
        # With new filtering: NY predictions are hidden for MP context since train doesn't stop at MP
        assert train["prediction_data"] is None  # Predictions filtered out
        
        # Verify repository was called with correct parameters
        mock_train_repository.get_trains.assert_called_once()
        call_kwargs = mock_train_repository.get_trains.call_args.kwargs
        assert call_kwargs["train_id"] == "3765"
        assert call_kwargs["from_station_code"] == "MP"

    def test_ios_context_prediction_scenario_with_relevant_predictions(self, test_client, mock_train_repository, mock_train_stop_repository):
        """Test iOS scenario where context matches origin - predictions should be shown."""
        # Create mock train that originated from NY and user is asking about NY context
        mock_train = MagicMock(spec=Train)
        mock_train.id = 1
        mock_train.train_id = "3765"
        mock_train.line = "Northeast Corrdr"
        mock_train.line_code = "NEC"
        mock_train.destination = "Princeton Junction"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T14:30:00")
        mock_train.status = "BOARDING"
        mock_train.track = "13"
        mock_train.origin_station_code = "NY"  # Train originated from NY
        mock_train.origin_station_name = "New York Penn Station"
        mock_train.data_source = "njtransit"
        mock_train.created_at = datetime.fromisoformat("2025-05-09T14:00:00")
        mock_train.updated_at = datetime.fromisoformat("2025-05-09T14:25:00")
        mock_train.track_assigned_at = None
        mock_train.track_released_at = None
        mock_train.delay_minutes = None
        mock_train.train_split = None
        
        # Add new API response fields
        mock_train.journey_completion_status = "in_progress"
        mock_train.stops_last_updated = None
        mock_train.journey_validated_at = None
        
        # Mock NY prediction data (should be shown for NY context)
        mock_prediction = MagicMock()
        mock_prediction.track_probabilities = {"13": 0.8, "14": 0.2}  # NY tracks
        mock_prediction.prediction_factors = [{"feature": "destination", "importance": 0.5, "direction": "positive", "explanation": "Princeton Junction trains typically use track 13 at NY Penn"}]
        mock_prediction.model_version = "1.0.0_NY"  # NY model
        mock_prediction.created_at = datetime.fromisoformat("2025-05-09T14:20:00")
        mock_train.prediction_data = mock_prediction

        # Mock train stops including NY
        from trackcast.api.models import TrainStop  
        mock_stops = [
            TrainStop(station_code="NY", station_name="New York Penn Station", scheduled_time="2025-05-09T14:30:00", departed=False),
            TrainStop(station_code="NP", station_name="Newark Penn Station", scheduled_time="2025-05-09T14:45:00", departed=False),
            TrainStop(station_code="TR", station_name="Trenton", scheduled_time="2025-05-09T15:15:00", departed=False)
        ]

        # Configure mocks
        mock_train_repository.get_trains.return_value = ([mock_train], 1)
        mock_train_stop_repository.get_stops_for_train.return_value = mock_stops

        # iOS API call: train details with NY context (origin matches context)
        response = test_client.get("/api/trains?train_id=3765&from_station_code=NY&include_predictions=true")
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert "trains" in data
        assert len(data["trains"]) == 1
        
        # Verify we get the train WITH predictions (origin matches context)
        train = data["trains"][0]
        assert train["train_id"] == "3765"
        assert train["origin_station_code"] == "NY"
        
        # NY origin with NY context should show predictions
        assert train["prediction_data"] is not None
        assert train["prediction_data"]["model_version"] == "1.0.0_NY"
        assert "13" in train["prediction_data"]["track_probabilities"]