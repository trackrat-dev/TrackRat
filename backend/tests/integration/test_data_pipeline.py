"""Integration tests for the complete data pipeline."""
import pytest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta

from trackcast.data.collectors import NJTransitCollector
from trackcast.services.data_collector import DataCollectorService
from trackcast.services.feature_engineering import FeatureEngineeringService
from trackcast.services.prediction import PredictionService
from trackcast.db.repository import TrainRepository, ModelDataRepository, PredictionDataRepository
from trackcast.db.models import Train, ModelData, PredictionData


class TestCompletePipeline:
    """Integration tests for the complete TrackCast data pipeline."""
    
    @pytest.fixture
    def mock_api_response(self):
        """Create a sample NJ Transit API response."""
        return {
            "ITEMS": [
                {
                    "TRAIN_ID": "3829",
                    "LINE": "Northeast Corrdr",
                    "DESTINATION": "Trenton",
                    "SCHED_DEP_DATE": "09-May-2025 09:19:00 AM",
                    "TRACK": "",
                    "STATUS": " ",
                },
                {
                    "TRAIN_ID": "6317",
                    "LINE": "Morristown Line",
                    "DESTINATION": "Summit",
                    "SCHED_DEP_DATE": "09-May-2025 09:22:00 AM",
                    "TRACK": "10",
                    "STATUS": "BOARDING",
                }
            ]
        }
    
    def test_full_pipeline_integration(self, db_session, mock_api_response, test_config):
        """Test the full data pipeline from API to predictions."""
        # 1. Set up mock for data collection
        with patch("trackcast.services.data_collector.NJTransitCollector.collect") as mock_collect:
            # Mock the collect method to return our test data
            mock_collect.return_value = {"data": mock_api_response, "timestamp": datetime.now().isoformat()}
            
            # Create real collector with mocked API
            collector = NJTransitCollector(test_config)
            
            # 2. Set up repositories with real database session
            train_repo = TrainRepository(db_session)
            model_data_repo = ModelDataRepository(db_session)
            prediction_repo = PredictionDataRepository(db_session)
            
            # 3. Set up services
            data_service = DataCollectorService(db_session)
            
            # 4. Create mock feature engineering pipeline
            mock_pipeline = MagicMock()
            mock_pipeline.process.return_value = {
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
            
            # Mock the feature pipeline
            with patch("trackcast.features.pipelines.FeaturePipeline", return_value=mock_pipeline):
                # Initialize the feature service with just the db_session
                feature_service = FeatureEngineeringService(db_session)
            
            # 5. Create mock inference engine
            mock_inference = MagicMock()
            mock_inference.predict.return_value = {
                "track_probabilities": {"1": 0.1, "2": 0.7, "3": 0.2},
                "prediction_factors": [{"feature": "hour_sin", "importance": 0.3}],
                "model_version": "test"
            }
            
            # Mock the model loading
            with patch.object(PredictionService, "_load_model_for_station", return_value=True):
                # Mock the prediction method
                with patch.object(PredictionService, "_predict_train", return_value=mock_inference):
                    prediction_service = PredictionService(db_session)
            
            # Execute pipeline stages
            
            # Stage 1: Collect and store data
            # Since we have no real collectors configured in test env, directly process test data
            processed_trains, _ = collector.run()
            success, processing_stats = data_service._process_train_data_for_station(
                processed_trains, "NY", "New York Penn Station"
            )
            assert success == True
            
            # Check trains were saved to db
            trains = db_session.query(Train).all()
            # There might be different number of trains in the database, let's just check that at least our two test trains are there
            assert len(trains) > 0

            # Check if our test trains are in the database
            test_trains = db_session.query(Train).filter(
                (Train.train_id == "3829") | (Train.train_id == "6317")
            ).all()
            assert len(test_trains) == 2
            
            # Stage 2: Process features
            success, stats = feature_service.process_pending_trains()
            assert success == True
            
            # Check model data was saved to db
            model_data_records = db_session.query(ModelData).all()
            assert len(model_data_records) == 2
            
            # Verify train records were updated with model_data_id
            trains = db_session.query(Train).all()
            for train in trains:
                assert train.model_data_id is not None
            
            # Stage 3: Generate predictions
            success, stats = prediction_service.run_prediction()
            assert success == True
            
            # Check predictions were saved to db
            prediction_records = db_session.query(PredictionData).all()
            assert len(prediction_records) == 2
            
            # Verify train records were updated with prediction_data_id
            trains = db_session.query(Train).all()
            for train in trains:
                assert train.prediction_data_id is not None
            
            # Full pipeline validation
            # Get a train with its related data
            complete_train = db_session.query(Train).first()
            assert complete_train is not None
            assert complete_train.model_data_id is not None
            assert complete_train.prediction_data_id is not None
            
            # Validate model data format
            model_data = db_session.query(ModelData).filter_by(id=complete_train.model_data_id).first()
            assert model_data is not None
            assert "hour_sin" in model_data.__dict__
            assert "line_features" in model_data.__dict__
            
            # Validate prediction data format
            prediction = db_session.query(PredictionData).filter_by(id=complete_train.prediction_data_id).first()
            assert prediction is not None
            assert "track_probabilities" in prediction.__dict__
            assert "prediction_factors" in prediction.__dict__