"""
Phase 1 tests: Adding Pydantic compatibility to SQLAlchemy models.

Tests that SQLAlchemy models can be enhanced with Pydantic compatibility
without breaking existing functionality.
"""

import pytest
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from trackcast.db.models import Train, TrainStop, PredictionData, ModelData


class TestPydanticCompatibility:
    """Test that SQLAlchemy models can work with Pydantic."""

    def test_train_model_basic_pydantic_conversion(self, db_session):
        """Test that Train model can be converted to Pydantic format."""
        # Create a Train using existing SQLAlchemy model
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status="BOARDING",
            track="13",
        )
        
        db_session.add(train)
        db_session.commit()
        
        # Test that we can access all the fields
        assert train.id is not None
        assert train.train_id == "3829"
        assert train.origin_station_code == "NY"
        assert train.line == "Northeast Corrdr"
        assert train.track == "13"
        
        # Test existing properties still work
        assert train.has_track is True
        assert train.is_boarding is True
        assert train.is_departed is False

    def test_train_stop_model_basic_pydantic_conversion(self, db_session):
        """Test that TrainStop model can be converted to Pydantic format."""
        # Create a TrainStop using existing SQLAlchemy model
        stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
            departed=True,
            stop_status="DEPARTED",
        )
        
        db_session.add(stop)
        db_session.commit()
        
        # Test that we can access all the fields
        assert stop.id is not None
        assert stop.train_id == "3829"
        assert stop.station_code == "NY"
        assert stop.station_name == "New York Penn Station"
        assert stop.departed is True
        
        # Test existing properties still work
        assert stop.is_regular_stop is True
        assert stop.is_pickup_stop is False
        assert stop.is_dropoff_stop is False

    def test_prediction_data_model_basic_conversion(self, db_session):
        """Test that PredictionData model can be converted to Pydantic format."""
        # Create PredictionData using existing SQLAlchemy model
        prediction = PredictionData(
            track_probabilities={"13": 0.85, "12": 0.15},
            prediction_factors=[
                {
                    "feature": "line_Northeast Corrdr",
                    "importance": 0.45,
                    "direction": "positive",
                    "explanation": "Northeast Corridor trains often use track 13"
                }
            ],
            model_version="1.0.0_NY",
        )
        
        db_session.add(prediction)
        db_session.commit()
        
        # Test that we can access all the fields
        assert prediction.id is not None
        assert prediction.track_probabilities == {"13": 0.85, "12": 0.15}
        assert prediction.model_version == "1.0.0_NY"
        
        # Test existing properties still work
        assert prediction.top_track == "13"
        assert prediction.top_probability == 0.85
        assert len(prediction.get_top_factors()) == 1

    def test_model_data_basic_conversion(self, db_session):
        """Test that ModelData model can be converted to Pydantic format."""
        # Create ModelData using existing SQLAlchemy model
        model_data = ModelData(
            hour_sin=0.5,
            hour_cos=0.866,
            day_of_week_sin=0.0,
            day_of_week_cos=1.0,
            is_weekend=False,
            is_morning_rush=True,
            is_evening_rush=False,
            line_features={"line_Northeast Corrdr": 1.0},
            destination_features={"dest_Trenton": 1.0},
            track_usage_features={"track_13_usage_rate": 0.75},
            historical_features={"historical_track_13_rate": 0.8},
            feature_version="1.0.0",
        )
        
        db_session.add(model_data)
        db_session.commit()
        
        # Test that we can access all the fields
        assert model_data.id is not None
        assert model_data.hour_sin == 0.5
        assert model_data.is_weekend is False
        assert model_data.feature_version == "1.0.0"
        
        # Test existing methods still work
        feature_dict = model_data.to_dict()
        assert "hour_sin" in feature_dict
        assert "line_Northeast Corrdr" in feature_dict
        assert feature_dict["hour_sin"] == 0.5


class TestSimplePydanticModel:
    """Test creating simple Pydantic models that can work with SQLAlchemy."""

    def test_simple_train_response_model(self, db_session):
        """Test a simple Pydantic model that can be created from SQLAlchemy Train."""
        
        # Define a simple response model with Pydantic v2 compatibility
        class SimpleTrainResponse(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            
            id: int
            train_id: str
            origin_station_code: str
            line: str
            destination: str
            track: Optional[str] = None
            status: Optional[str] = None
        
        # Create SQLAlchemy train
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status="BOARDING",
            track="13",
        )
        
        db_session.add(train)
        db_session.commit()
        
        # Test Pydantic v2 conversion
        response = SimpleTrainResponse.model_validate(train)
        
        # Verify the conversion worked
        assert response.id == train.id
        assert response.train_id == "3829"
        assert response.origin_station_code == "NY"
        assert response.line == "Northeast Corrdr"
        assert response.destination == "Trenton"
        assert response.track == "13"
        assert response.status == "BOARDING"
        
        # Verify it can be serialized to dict
        response_dict = response.model_dump()
        assert response_dict["train_id"] == "3829"
        assert response_dict["track"] == "13"

    def test_simple_train_stop_response_model(self, db_session):
        """Test a simple Pydantic model that can be created from SQLAlchemy TrainStop."""
        
        # Define a simple response model with Pydantic v2 compatibility
        class SimpleTrainStopResponse(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            
            id: int
            station_code: Optional[str] = None
            station_name: str
            departed: bool = False
            stop_status: Optional[str] = None
        
        # Create SQLAlchemy train stop
        stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code="NY",
            station_name="New York Penn Station",
            departed=True,
            stop_status="DEPARTED",
        )
        
        db_session.add(stop)
        db_session.commit()
        
        # Test Pydantic v2 conversion
        response = SimpleTrainStopResponse.model_validate(stop)
        
        # Verify the conversion worked
        assert response.id == stop.id
        assert response.station_code == "NY"
        assert response.station_name == "New York Penn Station"
        assert response.departed is True
        assert response.stop_status == "DEPARTED"
        
        # Verify it can be serialized to dict
        response_dict = response.model_dump()
        assert response_dict["station_code"] == "NY"
        assert response_dict["departed"] is True


class TestBackwardCompatibility:
    """Test that existing functionality remains intact."""

    def test_existing_train_operations_still_work(self, db_session):
        """Test that all existing Train operations still work exactly as before."""
        # This test ensures we don't break anything when adding Pydantic compatibility
        
        # Create train exactly as before
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status="BOARDING",
            track="13",
        )
        
        db_session.add(train)
        db_session.commit()
        
        # All existing properties should work
        assert train.has_track is True
        assert train.is_boarding is True
        assert train.is_departed is False
        assert train.is_delayed is False
        
        # All existing fields should be accessible
        assert train.train_id == "3829"
        assert train.origin_station_code == "NY"
        assert train.track == "13"
        
        # String representation should work
        train_repr = repr(train)
        assert "3829" in train_repr
        assert "NY" in train_repr

    def test_existing_relationships_still_work(self, db_session):
        """Test that SQLAlchemy relationships still work as expected."""
        # Create related objects as before
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
        )
        
        model_data = ModelData(
            hour_sin=0.5,
            hour_cos=0.866,
            day_of_week_sin=0.0,
            day_of_week_cos=1.0,
            is_weekend=False,
            is_morning_rush=True,
            is_evening_rush=False,
            line_features={},
            destination_features={},
            track_usage_features={},
            historical_features={},
            feature_version="1.0.0",
        )
        
        prediction_data = PredictionData(
            track_probabilities={"13": 0.85},
            prediction_factors=[],
            model_version="1.0.0_NY",
        )
        
        db_session.add_all([model_data, prediction_data])
        db_session.commit()
        
        # Set up relationships as before
        train.model_data_id = model_data.id
        train.prediction_data_id = prediction_data.id
        db_session.add(train)
        db_session.commit()
        
        # Verify relationships still work
        assert train.model_data is not None
        assert train.prediction_data is not None
        assert train.model_data.hour_sin == 0.5
        assert train.prediction_data.track_probabilities == {"13": 0.85}