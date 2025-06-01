"""Tests for the feature engineering module."""
import pytest
from datetime import datetime
import numpy as np
from unittest.mock import patch, MagicMock

from trackcast.features.extractors import TimeFeatureExtractor, CategoricalFeatureExtractor
# Remove unused import
from trackcast.features.pipelines import FeaturePipeline
from trackcast.services.feature_engineering import FeatureEngineeringService


class TestTimeFeatureExtractor:
    """Tests for the TimeFeatureExtractor class."""
    
    def test_extract_time_features(self):
        """Test extracting time features from train data."""
        # Create a mock train object
        mock_train = MagicMock()
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T09:19:00")  # Friday, 9:19 AM

        extractor = TimeFeatureExtractor()
        features = extractor.extract(mock_train)
        
        # Check cyclic time encoding
        assert "hour_sin" in features
        assert "hour_cos" in features
        assert "day_of_week_sin" in features
        assert "day_of_week_cos" in features
        
        # Check binary indicators
        assert "is_weekend" in features
        assert features["is_weekend"] == False  # Friday is not weekend
        assert "is_morning_rush" in features
        assert features["is_morning_rush"] == True  # 9:19 AM is morning rush
        assert "is_evening_rush" in features
        assert features["is_evening_rush"] == False  # 9:19 AM is not evening rush


class TestCategoricalFeatureExtractor:
    """Tests for the CategoricalFeatureExtractor class."""
    
    def test_extract_categorical_features(self, db_session):
        """Test extracting categorical features from train data."""
        # Create a mock train object
        mock_train = MagicMock()
        mock_train.line = "Northeast Corrdr"
        mock_train.destination = "Trenton"

        # Create extractor directly with known categories
        all_lines = ["Northeast Corrdr", "Morristown Line", "Montclair-Boonton"]
        all_destinations = ["Trenton", "Dover", "Summit", "MSU"]
        extractor = CategoricalFeatureExtractor(all_lines=all_lines, all_destinations=all_destinations)

        # Extract features
        features = extractor.extract(mock_train)
        
        # Check one-hot encoding for line
        assert "line_features" in features
        line_features = features["line_features"]
        assert line_features["Line_Northeast_Corrdr"] == 1
        assert line_features["Line_Morristown_Line"] == 0
        
        # Check one-hot encoding for destination
        assert "destination_features" in features
        destination_features = features["destination_features"]
        assert destination_features["Destination_Trenton"] == 1
        assert destination_features["Destination_Dover"] == 0


class TestFeaturePipeline:
    """Tests for the FeaturePipeline class."""
    
    def test_pipeline_execution(self, sample_train_data, db_session):
        """Test executing the full feature engineering pipeline."""
        # Create a mock train object with appropriate attributes
        mock_train = MagicMock()
        mock_train.id = 1
        mock_train.train_id = "3829"
        mock_train.line = "Northeast Corrdr"
        mock_train.destination = "Trenton"
        mock_train.departure_time = datetime.fromisoformat("2025-05-09T09:19:00")
        mock_train.model_data_id = None

        # Create mock extractors
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "hour_sin": 0.7818,
            "hour_cos": 0.6234,
            "day_of_week_sin": 0.9749,
            "day_of_week_cos": 0.2225,
            "is_weekend": False,
            "is_morning_rush": True,
            "is_evening_rush": False,
            "line_features": {"Line_Northeast_Corrdr": 1},
            "destination_features": {"Destination_Trenton": 1},
            "track_usage_features": {"Track_1_Last_Used": 120},
            "historical_features": {"Matching_TrainID_Track_1_Pct": 0.75}
        }

        # Create a pipeline with mocked components
        with patch("trackcast.db.repository.TrainRepository"), \
             patch("trackcast.db.repository.ModelDataRepository"):

            pipeline = FeaturePipeline(
                session=db_session,
                feature_version="test"
            )

            # Replace the real extractors with our mock
            pipeline.extractors = [mock_extractor]

            # Test extracting features for the train
            features = pipeline.extract_features(mock_train)

            # Verify features were extracted correctly
            assert features is not None
            assert "hour_sin" in features
            assert "line_features" in features
            assert "track_usage_features" in features
            assert "historical_features" in features

            # Verify extractor was called with the train object and some reference time
            # Since the reference time is set to datetime.utcnow(), we can't test the exact value
            assert mock_extractor.extract.call_count == 1
            args, kwargs = mock_extractor.extract.call_args
            assert args[0] == mock_train
            assert 'reference_time' in kwargs
            assert isinstance(kwargs['reference_time'], datetime)