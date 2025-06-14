import pytest
from unittest import mock
import time as std_time # Keep a reference to the original time module

# Import the service and its metric objects
from backend.trackcast.services.prediction import (
    PredictionService,
    MODEL_INFERENCE_TIME,
    TRAINS_PROCESSED_TOTAL,
    TRACK_PREDICTION_CONFIDENCE,
    MODEL_PREDICTION_ACCURACY, # Though not tested for setting value, can check it exists
)
from backend.trackcast.db.models import Train, ModelData, PredictionData
from sqlalchemy.orm import Session

# Helper to get Prometheus metric values
def get_histogram_count(histogram):
    return histogram.collect()[0].samples[0].value # _count sample

def get_histogram_sum(histogram):
    return histogram.collect()[1].samples[0].value # _sum sample

def get_counter_value(counter):
    samples = counter.collect()[0].samples
    return samples[0].value if samples else 0.0

@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    session = mock.Mock(spec=Session)
    session.commit = mock.Mock()
    session.rollback = mock.Mock()
    session.add = mock.Mock()
    session.query = mock.Mock() # Further mocking might be needed depending on query usage
    return session

@pytest.fixture
def prediction_service(mock_db_session):
    """Provides a PredictionService instance with a mocked DB session."""
    return PredictionService(db_session=mock_db_session)

@pytest.fixture
def mock_train_with_features():
    """Creates a mock Train object with associated ModelData."""
    train = Train(
        id=1,
        train_id="T123",
        origin_station_code="NY",
        departure_time=std_time.time(), # Use std_time for non-mocked time
        model_data_id=1
    )
    # Simulate that train.model_data is available (normally a relationship)
    train.model_data = ModelData(id=1, features={"feature1": 1.0, "feature2": 0.5})
    return train

# --- MODEL_INFERENCE_TIME Tests ---

@mock.patch("backend.trackcast.services.prediction.TrackPredictionPipeline") # Mock the class
def test_model_inference_time_recorded(MockTrackPredictionPipeline, prediction_service, mock_train_with_features, mock_db_session):
    # Configure the mock pipeline instance and its predict method
    mock_pipeline_instance = MockTrackPredictionPipeline.return_value
    mock_pipeline_instance.predict.return_value = [{"trackA": 0.8, "trackB": 0.2}] # Sample prediction

    # Mock model loading to succeed and set up a dummy model_info
    prediction_service.models[mock_train_with_features.origin_station_code] = mock_pipeline_instance
    prediction_service.model_infos[mock_train_with_features.origin_station_code] = {"version": "1.0", "model_path": "dummy"}


    # Mock time.time() to control duration
    mock_time = mock.Mock(spec=std_time) # Ensure it behaves like the time module
    mock_time.time = mock.Mock(side_effect=[10.0, 10.5]) # Start time, end time

    initial_count = get_histogram_count(MODEL_INFERENCE_TIME)
    initial_sum = get_histogram_sum(MODEL_INFERENCE_TIME)

    with mock.patch("time.time", side_effect=[10.0, 10.5]): # Mock time.time() used by the service
        # We need to ensure _predict_train is called.
        # If _predict_train is internal, test through a public method that calls it.
        # Let's assume predict_train (if it exists and calls _predict_train) or run_prediction.
        # For this unit test, directly calling _predict_train is fine if it's the SUT for this metric.
        # The method _predict_train saves to DB, so mock PredictionDataRepository methods
        mock_prediction_repo = mock.Mock()
        mock_prediction_repo.create_prediction.return_value = PredictionData(id=1, track_probabilities={})
        prediction_service.prediction_repo = mock_prediction_repo

        prediction_service._predict_train(mock_train_with_features)

    assert get_histogram_count(MODEL_INFERENCE_TIME) == initial_count + 1
    # The sum should increase by 0.5 (10.5 - 10.0)
    # Floating point precision can be an issue, so use approx
    assert get_histogram_sum(MODEL_INFERENCE_TIME) == pytest.approx(initial_sum + 0.5)


# --- TRAINS_PROCESSED_TOTAL Tests ---

def test_trains_processed_total_increments(prediction_service, mock_train_with_features):
    initial_value = get_counter_value(TRAINS_PROCESSED_TOTAL)

    # Mock the repository method that run_prediction uses to get trains
    mock_train_repo = mock.Mock()
    mock_train_repo.get_trains_needing_predictions.return_value = [mock_train_with_features, mock_train_with_features] # Simulate 2 trains
    prediction_service.train_repo = mock_train_repo

    # Mock model loading to avoid errors if _load_model_for_station is called
    with mock.patch.object(prediction_service, "_load_model_for_station", return_value=True):
        # Mock _predict_train to prevent its actual execution complexities for this test
        with mock.patch.object(prediction_service, "_predict_train", return_value=mock.Mock(spec=PredictionData)):
            prediction_service.run_prediction()

    assert get_counter_value(TRAINS_PROCESSED_TOTAL) == initial_value + 2


# --- TRACK_PREDICTION_CONFIDENCE Tests ---

@mock.patch("backend.trackcast.services.prediction.TrackPredictionPipeline")
def test_track_prediction_confidence_observed(MockTrackPredictionPipeline, prediction_service, mock_train_with_features, mock_db_session):
    mock_pipeline_instance = MockTrackPredictionPipeline.return_value
    # Ensure the prediction returns a dictionary with probabilities
    mock_pipeline_instance.predict.return_value = [{"trackA": 0.85, "trackB": 0.15}]

    prediction_service.models[mock_train_with_features.origin_station_code] = mock_pipeline_instance
    prediction_service.model_infos[mock_train_with_features.origin_station_code] = {"version": "1.0", "model_path": "dummy"}

    initial_count = get_histogram_count(TRACK_PREDICTION_CONFIDENCE)
    initial_sum = get_histogram_sum(TRACK_PREDICTION_CONFIDENCE)

    # Mock the prediction repo for saving
    mock_prediction_repo = mock.Mock()
    mock_prediction_repo.create_prediction.return_value = PredictionData(id=1, track_probabilities={})
    prediction_service.prediction_repo = mock_prediction_repo

    # Mock time.time() as it's called by the inference timer wrapper
    with mock.patch("time.time", side_effect=[10.0, 10.1]):
         prediction_service._predict_train(mock_train_with_features)

    assert get_histogram_count(TRACK_PREDICTION_CONFIDENCE) == initial_count + 1
    assert get_histogram_sum(TRACK_PREDICTION_CONFIDENCE) == pytest.approx(initial_sum + 0.85)

# --- MODEL_PREDICTION_ACCURACY Placeholder Test ---
def test_model_prediction_accuracy_metric_exists():
    # This test just ensures the metric object is defined.
    # Actual value testing would require a more complex setup simulating feedback loop.
    assert MODEL_PREDICTION_ACCURACY is not None
    assert MODEL_PREDICTION_ACCURACY._name == "model_prediction_accuracy"
    # No value check as it's not set by current prediction flow directly
```
