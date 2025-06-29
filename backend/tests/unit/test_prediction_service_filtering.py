"""
Tests for prediction service filtering functionality.

This module tests the enhanced prediction service methods that support
filtering by train ID, time range, and future trains.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from trackcast.services.prediction import PredictionService
from trackcast.utils import get_eastern_now
from trackcast.db.models import Train, ModelData, PredictionData


class TestPredictionServiceFiltering:
    """Test filtering functionality in PredictionService."""

    @patch('trackcast.services.prediction.TrackPredictionPipeline')
    def test_run_prediction_with_train_id_filter(self, mock_pipeline_class, db_session):
        """Test running predictions with train ID filter."""
        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline_class.find_latest_model.return_value = {
            "model_path": "test_model.pth",
            "metadata_path": "test_metadata.json", 
            "scaler_path": "test_scaler.pkl",
            "version": "1.0.0",
            "timestamp": "2023-01-01T00:00:00"
        }
        mock_pipeline_class.return_value = mock_pipeline
        mock_pipeline.predict.return_value = [{"1": 0.8, "2": 0.2}]
        mock_pipeline.get_prediction_factors.return_value = []
        
        # Create test data
        train = Train(
            train_id="7001",
            line="Northeast Corridor",
            destination="Trenton",
            departure_time=datetime.utcnow() + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        model_data = ModelData(feature_version="1.0")
        db_session.add(model_data)
        db_session.flush()
        train.model_data_id = model_data.id
        
        db_session.add(train)
        db_session.commit()
        
        # Test prediction service with train ID filter
        service = PredictionService(db_session)
        success, stats = service.run_prediction(train_id="7001")
        
        assert success is True
        assert stats["trains_processed"] == 1
        assert stats["trains_predicted"] == 1
        assert stats["filters"]["train_id"] == "7001"

    @patch('trackcast.services.prediction.TrackPredictionPipeline')
    def test_run_prediction_with_time_range_filter(self, mock_pipeline_class, db_session):
        """Test running predictions with time range filter."""
        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline_class.find_latest_model.return_value = {
            "model_path": "test_model.pth",
            "metadata_path": "test_metadata.json",
            "scaler_path": "test_scaler.pkl", 
            "version": "1.0.0",
            "timestamp": "2023-01-01T00:00:00"
        }
        mock_pipeline_class.return_value = mock_pipeline
        mock_pipeline.predict.return_value = [{"1": 0.8, "2": 0.2}]
        mock_pipeline.get_prediction_factors.return_value = []
        
        now = get_eastern_now()
        
        # Create test trains at different times
        trains_data = [
            ("7001", now + timedelta(hours=1)),   # Within range
            ("7002", now + timedelta(hours=6)),   # Within range
            ("7003", now + timedelta(hours=15)),  # Outside range
        ]
        
        trains = []
        for train_id, departure_time in trains_data:
            train = Train(
                train_id=train_id,
                line="Northeast Corridor",
                destination="Trenton",
                departure_time=departure_time,
                origin_station_code="NY",
                data_source="njtransit"
            )
            
            model_data = ModelData(feature_version="1.0")
            db_session.add(model_data)
            db_session.flush()
            train.model_data_id = model_data.id
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # Test prediction service with time range filter
        service = PredictionService(db_session)
        start_time = now
        end_time = now + timedelta(hours=12)
        success, stats = service.run_prediction(time_range=(start_time, end_time))
        
        assert success is True
        assert stats["trains_processed"] == 2  # Only trains within range
        assert stats["trains_predicted"] == 2
        assert stats["filters"]["time_range"] == [start_time.isoformat(), end_time.isoformat()]

    @patch('trackcast.services.prediction.TrackPredictionPipeline')
    def test_run_prediction_with_future_only_filter(self, mock_pipeline_class, db_session):
        """Test running predictions with future only filter."""
        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline_class.find_latest_model.return_value = {
            "model_path": "test_model.pth",
            "metadata_path": "test_metadata.json",
            "scaler_path": "test_scaler.pkl",
            "version": "1.0.0", 
            "timestamp": "2023-01-01T00:00:00"
        }
        mock_pipeline_class.return_value = mock_pipeline
        mock_pipeline.predict.return_value = [{"1": 0.8, "2": 0.2}]
        mock_pipeline.get_prediction_factors.return_value = []
        
        now = get_eastern_now()
        
        # Create test trains - past and future
        trains_data = [
            ("7001", now - timedelta(hours=1)),  # Past
            ("7002", now + timedelta(hours=1)),  # Future
            ("7003", now + timedelta(hours=2)),  # Future
        ]
        
        trains = []
        for train_id, departure_time in trains_data:
            train = Train(
                train_id=train_id,
                line="Northeast Corridor",
                destination="Trenton",
                departure_time=departure_time,
                origin_station_code="NY",
                data_source="njtransit"
            )
            
            model_data = ModelData(feature_version="1.0")
            db_session.add(model_data)
            db_session.flush()
            train.model_data_id = model_data.id
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # Test prediction service with future only filter
        service = PredictionService(db_session)
        success, stats = service.run_prediction(future_only=True)
        
        assert success is True
        assert stats["trains_processed"] == 2  # Only future trains
        assert stats["trains_predicted"] == 2
        assert stats["filters"]["future_only"] is True


class TestPredictionServiceClearing:
    """Test clearing functionality in PredictionService."""

    def test_clear_predictions_with_train_id(self, db_session):
        """Test clearing predictions for specific train ID."""
        # Create train with prediction
        train = Train(
            train_id="7001",
            line="Northeast Corridor", 
            destination="Trenton",
            departure_time=datetime.utcnow() + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        prediction_data = PredictionData(
            track_probabilities={"1": 0.8, "2": 0.2},
            prediction_factors=[],
            model_version="test"
        )
        
        db_session.add_all([train, prediction_data])
        db_session.flush()
        train.prediction_data_id = prediction_data.id
        db_session.commit()
        
        # Test clearing predictions for specific train
        service = PredictionService(db_session)
        success, stats = service.clear_predictions(train_id="7001")
        
        assert success is True
        assert stats["filters"]["train_id"] == "7001"
        assert "trains_cleared" in stats
        assert "predictions_deleted" in stats

    def test_clear_predictions_with_time_range(self, db_session):
        """Test clearing predictions for time range."""
        now = get_eastern_now()
        
        # Create trains with predictions at different times
        trains_data = [
            ("7001", now + timedelta(hours=1)),   # Within range
            ("7002", now + timedelta(hours=15)),  # Outside range
        ]
        
        trains = []
        predictions = []
        
        for train_id, departure_time in trains_data:
            train = Train(
                train_id=train_id,
                line="Northeast Corridor",
                destination="Trenton", 
                departure_time=departure_time,
                origin_station_code="NY",
                data_source="njtransit"
            )
            
            prediction = PredictionData(
                track_probabilities={"1": 0.8, "2": 0.2},
                prediction_factors=[],
                model_version="test"
            )
            
            trains.append(train)
            predictions.append(prediction)
        
        db_session.add_all(trains + predictions)
        db_session.flush()
        
        # Link predictions to trains
        for train, prediction in zip(trains, predictions):
            train.prediction_data_id = prediction.id
            
        db_session.commit()
        
        # Test clearing predictions for time range
        service = PredictionService(db_session)
        start_time = now
        end_time = now + timedelta(hours=12)
        success, stats = service.clear_predictions(time_range=(start_time, end_time))
        
        assert success is True
        assert stats["filters"]["time_range"] == [start_time.isoformat(), end_time.isoformat()]

    def test_clear_predictions_with_future_only(self, db_session):
        """Test clearing predictions for future trains only."""
        now = get_eastern_now()
        
        # Create trains with predictions - past and future
        trains_data = [
            ("7001", now - timedelta(hours=1)),  # Past
            ("7002", now + timedelta(hours=1)),  # Future
        ]
        
        trains = []
        predictions = []
        
        for train_id, departure_time in trains_data:
            train = Train(
                train_id=train_id,
                line="Northeast Corridor",
                destination="Trenton",
                departure_time=departure_time,
                origin_station_code="NY",
                data_source="njtransit"
            )
            
            prediction = PredictionData(
                track_probabilities={"1": 0.8, "2": 0.2},
                prediction_factors=[],
                model_version="test"
            )
            
            trains.append(train)
            predictions.append(prediction)
        
        db_session.add_all(trains + predictions)
        db_session.flush()
        
        # Link predictions to trains
        for train, prediction in zip(trains, predictions):
            train.prediction_data_id = prediction.id
            
        db_session.commit()
        
        # Test clearing predictions for future trains only
        service = PredictionService(db_session)
        success, stats = service.clear_predictions(future_only=True)
        
        assert success is True
        assert stats["filters"]["future_only"] is True

    def test_clear_predictions_no_filters_uses_clear_all(self, db_session):
        """Test that clear_predictions with no filters calls clear_all_predictions."""
        # Create train with prediction
        train = Train(
            train_id="7001",
            line="Northeast Corridor",
            destination="Trenton",
            departure_time=datetime.utcnow() + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        prediction_data = PredictionData(
            track_probabilities={"1": 0.8, "2": 0.2},
            prediction_factors=[],
            model_version="test"
        )
        
        db_session.add_all([train, prediction_data])
        db_session.flush()
        train.prediction_data_id = prediction_data.id
        db_session.commit()
        
        # Test clearing all predictions when no filters provided
        service = PredictionService(db_session)
        success, stats = service.clear_predictions()
        
        assert success is True
        assert stats["filters"]["train_id"] is None
        assert stats["filters"]["time_range"] is None  
        assert stats["filters"]["future_only"] is False
        assert "trains_cleared" in stats
        assert "predictions_deleted" in stats


class TestPredictionServiceErrorHandling:
    """Test error handling in prediction service filtering methods."""

    def test_run_prediction_no_trains_found(self, db_session):
        """Test prediction service when no trains match filters."""
        service = PredictionService(db_session)
        
        # Test with train ID that doesn't exist
        success, stats = service.run_prediction(train_id="99999")
        
        assert success is True  # No error, just no work to do
        assert stats["trains_processed"] == 0
        assert stats["trains_predicted"] == 0
        assert stats["filters"]["train_id"] == "99999"

    def test_clear_predictions_nonexistent_train(self, db_session):
        """Test clearing predictions for non-existent train."""
        service = PredictionService(db_session)
        
        # Test clearing predictions for non-existent train
        success, stats = service.clear_predictions(train_id="99999")
        
        # Should still succeed (train not found is handled gracefully)
        assert success is True
        assert stats["filters"]["train_id"] == "99999"

    @patch('trackcast.services.prediction.logger')
    def test_prediction_service_logs_filters(self, mock_logger, db_session):
        """Test that prediction service logs filter information."""
        service = PredictionService(db_session)
        
        # Run prediction with filters
        service.run_prediction(train_id="7001", future_only=True)
        
        # Verify logging includes filter information
        mock_logger.info.assert_called()
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        filter_log = next((call for call in log_calls if "train_id=7001" in call), None)
        assert filter_log is not None
        assert "future_only=True" in filter_log