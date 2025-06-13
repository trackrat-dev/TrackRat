"""Tests for the database models."""
import pytest
from datetime import datetime
from unittest.mock import patch

from trackcast.db.models import Train, ModelData, PredictionData
from trackcast.db.repository import TrainRepository, ModelDataRepository, PredictionDataRepository


class TestTrainModel:
    """Tests for the Train database model."""
    
    def test_train_creation(self, db_session):
        """Test creating a train record."""
        # Clean up any existing train with the same ID and departure time
        test_train_id = "TEST-12345"
        test_departure_time = datetime.fromisoformat("2025-05-09T10:30:00")
        
        existing_train = db_session.query(Train).filter_by(
            train_id=test_train_id,
            departure_time=test_departure_time
        ).first()
        
        if existing_train:
            db_session.delete(existing_train)
            db_session.commit()
            
        # Create a new train with a unique ID for testing
        train = Train(
            train_id=test_train_id,  # Use a unique test ID
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=test_departure_time,  # Use a different time
            track="",
            status=""
        )
        
        db_session.add(train)
        db_session.commit()
        
        assert train.id is not None
        assert train.train_id == test_train_id
        assert train.created_at is not None
        assert train.track_assigned_at is None
        
        # Clean up after test
        db_session.delete(train)
        db_session.commit()
    
    def test_train_track_assignment(self, db_session):
        """Test updating a train with track assignment."""
        from datetime import datetime
        # Use a unique test train ID
        test_train_id = "TEST-67890"
        test_departure_time = datetime.fromisoformat("2025-05-09T11:45:00")
        
        # Clean up any existing records with the same ID
        existing_train = db_session.query(Train).filter_by(
            train_id=test_train_id,
            departure_time=test_departure_time
        ).first()
        
        if existing_train:
            db_session.delete(existing_train)
            db_session.commit()
            
        # Create train without track first
        train = Train(
            train_id=test_train_id,
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=test_departure_time,
            track="",
            status=""
        )
        db_session.add(train)
        db_session.commit()
        
        # Now update with track using the repository
        repo = TrainRepository(db_session)
        update_data = {
            "track": "5",
            "status": "BOARDING"
        }
        repo.update_train(train, update_data, datetime.now())
        
        # Fetch from DB to confirm
        updated_train = db_session.query(Train).filter_by(id=train.id).first()
        assert updated_train.track == "5"
        assert updated_train.status == "BOARDING"
        assert updated_train.track_assigned_at is not None
        
        # Clean up after test
        db_session.delete(updated_train)
        db_session.commit()


class TestModelDataAndPrediction:
    """Tests for the ModelData and PredictionData models."""
    
    def test_model_data_creation(self, db_session):
        """Test creating model data record with features."""
        # Generate unique test IDs
        test_train_id = "TEST-MD-12345"
        test_departure_time = datetime.fromisoformat("2025-05-10T10:30:00")
        
        # First clean up any existing records
        existing_train = db_session.query(Train).filter_by(
            train_id=test_train_id,
            departure_time=test_departure_time
        ).first()
        
        if existing_train:
            if existing_train.model_data_id:
                model_data = db_session.query(ModelData).filter_by(id=existing_train.model_data_id).first()
                if model_data:
                    db_session.delete(model_data)
            db_session.delete(existing_train)
            db_session.commit()
            
        # Create a train
        train = Train(
            train_id=test_train_id,
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=test_departure_time
        )
        db_session.add(train)
        db_session.commit()
        
        # Create model data
        model_data = ModelData(
            hour_sin=0.7818,
            hour_cos=0.6234,
            day_of_week_sin=0.9749,
            day_of_week_cos=0.2225,
            is_weekend=False,
            is_morning_rush=True,
            is_evening_rush=False,
            line_features={"Line_Northeast_Corrdr": 1},
            destination_features={"Destination_Trenton": 1},
            track_usage_features={"Track_1_Last_Used": 120},
            historical_features={"Matching_TrainID_Track_1_Pct": 0.75},
            feature_version="test"
        )

        db_session.add(model_data)
        db_session.commit()

        assert model_data.id is not None
        assert model_data.created_at is not None
        
        # Update train with model_data_id
        train.model_data_id = model_data.id
        db_session.commit()
        
        # Test relationship from train to model data
        refreshed_train = db_session.query(Train).filter_by(id=train.id).first()
        assert refreshed_train.model_data_id == model_data.id
        
        # Clean up after test
        db_session.delete(model_data)
        db_session.delete(train)
        db_session.commit()
    
    def test_prediction_data_creation(self, db_session):
        """Test creating prediction data record."""
        # Generate unique test IDs
        test_train_id = "TEST-PD-12345"
        test_departure_time = datetime.fromisoformat("2025-05-11T10:30:00")
        
        # First clean up any existing records
        existing_train = db_session.query(Train).filter_by(
            train_id=test_train_id,
            departure_time=test_departure_time
        ).first()
        
        if existing_train:
            # Clean up related records
            if existing_train.model_data_id:
                model_data = db_session.query(ModelData).filter_by(id=existing_train.model_data_id).first()
                if model_data:
                    db_session.delete(model_data)
            if existing_train.prediction_data_id:
                prediction = db_session.query(PredictionData).filter_by(id=existing_train.prediction_data_id).first()
                if prediction:
                    db_session.delete(prediction)
            db_session.delete(existing_train)
            db_session.commit()
        
        # Create train and model data first
        train = Train(
            train_id=test_train_id,
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=test_departure_time
        )
        db_session.add(train)
        db_session.commit()
        
        model_data = ModelData(
            hour_sin=0.7818,
            hour_cos=0.6234,
            feature_version="test"
        )
        db_session.add(model_data)
        db_session.commit()
        
        # Create prediction
        prediction = PredictionData(
            model_data_id=model_data.id,
            track_probabilities={"1": 0.1, "2": 0.7, "3": 0.2},
            prediction_factors=[{"feature": "hour_sin", "importance": 0.3}],
            model_version="test"
        )
        
        db_session.add(prediction)
        db_session.commit()
        
        assert prediction.id is not None
        assert prediction.model_data_id == model_data.id
        assert prediction.created_at is not None
        
        # Update train with prediction_data_id
        train.prediction_data_id = prediction.id
        db_session.commit()
        
        # Test relationship from train to prediction data
        refreshed_train = db_session.query(Train).filter_by(id=train.id).first()
        assert refreshed_train.prediction_data_id == prediction.id
        
        # Clean up after test
        db_session.delete(prediction)
        db_session.delete(model_data)
        db_session.delete(train)
        db_session.commit()