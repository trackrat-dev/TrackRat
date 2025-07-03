"""
Comprehensive tests for consolidated models.

Tests that the new consolidated models produce identical output to the current
manual conversion approach, ensuring zero breaking changes for the iOS app.
"""

import json
import pytest
from datetime import datetime
from typing import Dict, Any

from trackcast.api.models import (
    TrainResponse as OriginalTrainResponse,
    TrainStop as OriginalTrainStop,
    PredictionData as OriginalPredictionData,
)
from trackcast.api.models_consolidated import (
    TrainResponse as ConsolidatedTrainResponse,
    TrainStopResponse as ConsolidatedTrainStopResponse,
    PredictionDataResponse as ConsolidatedPredictionDataResponse,
)
from trackcast.db.models import Train, TrainStop, PredictionData, ModelData


class TestConsolidatedModelsEquivalence:
    """Test that consolidated models produce identical output to manual conversion."""

    def test_train_stop_consolidated_vs_manual(self, db_session):
        """Test that ConsolidatedTrainStopResponse matches manual conversion exactly."""
        # Create SQLAlchemy TrainStop
        db_stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_arrival=datetime(2025, 5, 9, 10, 28, 0),
            scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
            actual_arrival=datetime(2025, 5, 9, 10, 29, 0),
            actual_departure=datetime(2025, 5, 9, 10, 32, 0),
            estimated_arrival=datetime(2025, 5, 9, 10, 28, 0),
            pickup_only=False,
            dropoff_only=False,
            departed=True,
            stop_status="DEPARTED",
        )
        
        db_session.add(db_stop)
        db_session.commit()
        
        # Manual conversion (current approach)
        manual_stop = OriginalTrainStop(
            station_code=getattr(db_stop, "station_code", None),
            station_name=getattr(db_stop, "station_name", ""),
            scheduled_arrival=getattr(db_stop, "scheduled_arrival", None),
            scheduled_departure=getattr(db_stop, "scheduled_departure", None),
            actual_arrival=getattr(db_stop, "actual_arrival", None),
            actual_departure=getattr(db_stop, "actual_departure", None),
            estimated_arrival=getattr(db_stop, "estimated_arrival", None),
            pickup_only=bool(getattr(db_stop, "pickup_only", False)),
            dropoff_only=bool(getattr(db_stop, "dropoff_only", False)),
            departed=bool(getattr(db_stop, "departed", False)),
            stop_status=getattr(db_stop, "stop_status", None),
        )
        
        # Automatic conversion (new approach)
        consolidated_stop = ConsolidatedTrainStopResponse.model_validate(db_stop)
        
        # Compare serialized output
        manual_dict = manual_stop.model_dump()
        consolidated_dict = consolidated_stop.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify specific fields
        assert consolidated_dict["station_code"] == "NY"
        assert consolidated_dict["station_name"] == "New York Penn Station"
        assert consolidated_dict["departed"] is True
        assert consolidated_dict["stop_status"] == "DEPARTED"
        assert consolidated_dict["pickup_only"] is False
        assert consolidated_dict["dropoff_only"] is False

    def test_train_stop_with_null_values_consolidated_vs_manual(self, db_session):
        """Test null value handling matches between manual and automatic conversion."""
        # Create SQLAlchemy TrainStop with null values
        db_stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code=None,  # Null value
            station_name="Test Station",
            scheduled_arrival=None,  # Null value
            scheduled_departure=None,  # Null value
            actual_arrival=None,  # Null value
            actual_departure=None,  # Null value
            estimated_arrival=None,  # Null value
            pickup_only=False,
            dropoff_only=False,
            departed=False,
            stop_status=None,  # Null value
        )
        
        db_session.add(db_stop)
        db_session.commit()
        
        # Manual conversion (current approach)
        manual_stop = OriginalTrainStop(
            station_code=getattr(db_stop, "station_code", None),
            station_name=getattr(db_stop, "station_name", ""),
            scheduled_arrival=getattr(db_stop, "scheduled_arrival", None),
            scheduled_departure=getattr(db_stop, "scheduled_departure", None),
            actual_arrival=getattr(db_stop, "actual_arrival", None),
            actual_departure=getattr(db_stop, "actual_departure", None),
            estimated_arrival=getattr(db_stop, "estimated_arrival", None),
            pickup_only=bool(getattr(db_stop, "pickup_only", False)),
            dropoff_only=bool(getattr(db_stop, "dropoff_only", False)),
            departed=bool(getattr(db_stop, "departed", False)),
            stop_status=getattr(db_stop, "stop_status", None),
        )
        
        # Automatic conversion (new approach)
        consolidated_stop = ConsolidatedTrainStopResponse.model_validate(db_stop)
        
        # Compare serialized output
        manual_dict = manual_stop.model_dump()
        consolidated_dict = consolidated_stop.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify null values are preserved
        assert consolidated_dict["station_code"] is None
        assert consolidated_dict["scheduled_arrival"] is None
        assert consolidated_dict["scheduled_departure"] is None
        assert consolidated_dict["actual_arrival"] is None
        assert consolidated_dict["actual_departure"] is None
        assert consolidated_dict["estimated_arrival"] is None
        assert consolidated_dict["stop_status"] is None
        
        # Verify non-null values
        assert consolidated_dict["station_name"] == "Test Station"
        assert consolidated_dict["departed"] is False

    def test_prediction_data_consolidated_vs_manual(self, db_session):
        """Test that ConsolidatedPredictionDataResponse matches manual conversion exactly."""
        # Create SQLAlchemy PredictionData
        db_prediction = PredictionData(
            track_probabilities={"13": 0.85, "12": 0.15},
            prediction_factors=[
                {
                    "feature": "line_Northeast Corrdr",
                    "importance": 0.45,
                    "direction": "positive",
                    "explanation": "Northeast Corridor trains often use track 13"
                },
                {
                    "feature": "destination_Trenton",
                    "importance": 0.3,
                    "direction": "positive", 
                    "explanation": "Trenton trains prefer track 13"
                }
            ],
            model_version="1.0.0_NY",
        )
        
        db_session.add(db_prediction)
        db_session.commit()
        
        # Manual conversion (current approach) - note: this is often implicit in the API
        manual_prediction = OriginalPredictionData(
            track_probabilities=db_prediction.track_probabilities,
            prediction_factors=db_prediction.prediction_factors,
            model_version=db_prediction.model_version,
            created_at=db_prediction.created_at,
        )
        
        # Automatic conversion (new approach)
        consolidated_prediction = ConsolidatedPredictionDataResponse.model_validate(db_prediction)
        
        # Compare serialized output
        manual_dict = manual_prediction.model_dump()
        consolidated_dict = consolidated_prediction.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify specific fields
        assert consolidated_dict["track_probabilities"] == {"13": 0.85, "12": 0.15}
        assert consolidated_dict["model_version"] == "1.0.0_NY"
        assert len(consolidated_dict["prediction_factors"]) == 2
        
        # Verify properties work the same
        assert manual_prediction.top_track == consolidated_prediction.top_track == "13"
        assert manual_prediction.top_probability == consolidated_prediction.top_probability == 0.85

    def test_train_response_consolidated_vs_manual_minimal(self, db_session):
        """Test TrainResponse conversion for minimal train record."""
        # Create minimal SQLAlchemy Train (required fields only)
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
        )
        
        db_session.add(db_train)
        db_session.commit()
        
        # Manual conversion (simplified version of what the API does)
        manual_train = OriginalTrainResponse(
            id=db_train.id,
            train_id=db_train.train_id,
            origin_station_code=db_train.origin_station_code,
            origin_station_name=db_train.origin_station_name,
            data_source=db_train.data_source,
            line=db_train.line,
            line_code=db_train.line_code,
            destination=db_train.destination,
            departure_time=db_train.departure_time,
            status=db_train.status,
            track=db_train.track,
            created_at=db_train.created_at,
            track_assigned_at=db_train.track_assigned_at,
            track_released_at=db_train.track_released_at,
            delay_minutes=db_train.delay_minutes,
            train_split=db_train.train_split,
            journey_completion_status=db_train.journey_completion_status,
            stops_last_updated=db_train.stops_last_updated,
            journey_validated_at=db_train.journey_validated_at,
            prediction_data=None,
            stops=None,
        )
        
        # Automatic conversion (new approach)
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Compare the core fields (excluding relationships for now)
        manual_dict = manual_train.model_dump(exclude={"prediction_data", "stops"})
        consolidated_dict = consolidated_train.model_dump(exclude={"prediction_data", "stops"})
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify specific core fields
        assert consolidated_dict["id"] == db_train.id
        assert consolidated_dict["train_id"] == "3829"
        assert consolidated_dict["origin_station_code"] == "NY"
        assert consolidated_dict["data_source"] == "njtransit"
        assert consolidated_dict["line"] == "Northeast Corrdr"
        assert consolidated_dict["destination"] == "Trenton"

    def test_train_response_consolidated_vs_manual_full(self, db_session):
        """Test TrainResponse conversion for full train record with all fields."""
        # Create full SQLAlchemy Train
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            line_code="NEC",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status="BOARDING",
            track="13",
            track_assigned_at=datetime(2025, 5, 9, 10, 25, 0),
            track_released_at=None,
            delay_minutes=2,
            train_split="train",
            journey_completion_status="in_progress",
            journey_validated_at=datetime(2025, 5, 9, 10, 0, 0),
            next_validation_check=datetime(2025, 5, 9, 11, 0, 0),
            stops_last_updated=datetime(2025, 5, 9, 10, 15, 0),
        )
        
        db_session.add(db_train)
        db_session.commit()
        
        # Manual conversion (what the API currently does)
        manual_train = OriginalTrainResponse(
            id=db_train.id,
            train_id=db_train.train_id,
            origin_station_code=db_train.origin_station_code,
            origin_station_name=db_train.origin_station_name,
            data_source=db_train.data_source,
            line=db_train.line,
            line_code=db_train.line_code,
            destination=db_train.destination,
            departure_time=db_train.departure_time,
            status=db_train.status,
            track=db_train.track,
            created_at=db_train.created_at,
            track_assigned_at=db_train.track_assigned_at,
            track_released_at=db_train.track_released_at,
            delay_minutes=db_train.delay_minutes,
            train_split=db_train.train_split,
            journey_completion_status=db_train.journey_completion_status,
            stops_last_updated=db_train.stops_last_updated,
            journey_validated_at=db_train.journey_validated_at,
            prediction_data=None,
            stops=None,
        )
        
        # Automatic conversion (new approach)
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Compare all fields except relationships
        manual_dict = manual_train.model_dump(exclude={"prediction_data", "stops"})
        consolidated_dict = consolidated_train.model_dump(exclude={"prediction_data", "stops"})
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify all filled fields
        assert consolidated_dict["track"] == "13"
        assert consolidated_dict["status"] == "BOARDING"
        assert consolidated_dict["delay_minutes"] == 2
        assert consolidated_dict["train_split"] == "train"
        assert consolidated_dict["journey_completion_status"] == "in_progress"


class TestConsolidatedModelsProperties:
    """Test that consolidated models have the same computed properties."""

    def test_train_response_properties(self, db_session):
        """Test that TrainResponse properties work identically."""
        # Create train with track
        db_train_with_track = Train(
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
        
        db_session.add(db_train_with_track)
        db_session.commit()
        
        # Convert to consolidated model
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train_with_track)
        
        # Test properties match SQLAlchemy model
        assert consolidated_train.has_track == db_train_with_track.has_track == True
        assert consolidated_train.is_boarding == db_train_with_track.is_boarding == True
        assert consolidated_train.is_departed == db_train_with_track.is_departed == False
        assert consolidated_train.is_delayed == db_train_with_track.is_delayed == False

    def test_train_response_properties_no_track(self, db_session):
        """Test properties with no track assigned."""
        # Create train without track
        db_train_no_track = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status=None,
            track=None,
        )
        
        db_session.add(db_train_no_track)
        db_session.commit()
        
        # Convert to consolidated model
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train_no_track)
        
        # Test properties match SQLAlchemy model
        assert consolidated_train.has_track == db_train_no_track.has_track == False
        assert consolidated_train.is_boarding == db_train_no_track.is_boarding == False
        assert consolidated_train.is_departed == db_train_no_track.is_departed == False
        assert consolidated_train.is_delayed == db_train_no_track.is_delayed == False

    def test_prediction_data_properties(self, db_session):
        """Test that PredictionDataResponse properties work identically."""
        db_prediction = PredictionData(
            track_probabilities={"13": 0.85, "12": 0.10, "14": 0.05},
            prediction_factors=[],
            model_version="1.0.0_NY",
        )
        
        db_session.add(db_prediction)
        db_session.commit()
        
        # Convert to consolidated model
        consolidated_prediction = ConsolidatedPredictionDataResponse.model_validate(db_prediction)
        
        # Test properties match SQLAlchemy model
        assert consolidated_prediction.top_track == db_prediction.top_track == "13"
        assert consolidated_prediction.top_probability == db_prediction.top_probability == 0.85


class TestJSONSerialization:
    """Test that JSON serialization produces identical results."""

    def test_datetime_serialization_format(self, db_session):
        """Test that datetime fields serialize to the same format."""
        # Create train with various datetime fields
        test_time = datetime(2025, 5, 9, 10, 30, 0)
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=test_time,
            track_assigned_at=test_time,
        )
        
        db_session.add(db_train)
        db_session.commit()
        
        # Manual conversion
        manual_train = OriginalTrainResponse(
            id=db_train.id,
            train_id=db_train.train_id,
            origin_station_code=db_train.origin_station_code,
            origin_station_name=db_train.origin_station_name,
            data_source=db_train.data_source,
            line=db_train.line,
            destination=db_train.destination,
            departure_time=db_train.departure_time,
            created_at=db_train.created_at,
            track_assigned_at=db_train.track_assigned_at,
        )
        
        # Automatic conversion
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Compare JSON output
        manual_json = manual_train.model_dump_json()
        consolidated_json = consolidated_train.model_dump_json()
        
        manual_dict = json.loads(manual_json)
        consolidated_dict = json.loads(consolidated_json)
        
        # Datetime fields should serialize identically
        assert manual_dict["departure_time"] == consolidated_dict["departure_time"]
        assert manual_dict["track_assigned_at"] == consolidated_dict["track_assigned_at"]
        assert manual_dict["created_at"] == consolidated_dict["created_at"]
        
        # They should all be ISO format strings
        assert isinstance(manual_dict["departure_time"], str)
        assert isinstance(consolidated_dict["departure_time"], str)

    def test_null_field_serialization(self, db_session):
        """Test that null fields serialize identically."""
        # Create train with null fields
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            # These are null
            line_code=None,
            track=None,
            status=None,
            track_assigned_at=None,
            delay_minutes=None,
        )
        
        db_session.add(db_train)
        db_session.commit()
        
        # Manual conversion
        manual_train = OriginalTrainResponse(
            id=db_train.id,
            train_id=db_train.train_id,
            origin_station_code=db_train.origin_station_code,
            origin_station_name=db_train.origin_station_name,
            data_source=db_train.data_source,
            line=db_train.line,
            line_code=db_train.line_code,  # None
            destination=db_train.destination,
            departure_time=db_train.departure_time,
            track=db_train.track,  # None
            status=db_train.status,  # None
            created_at=db_train.created_at,
            track_assigned_at=db_train.track_assigned_at,  # None
            delay_minutes=db_train.delay_minutes,  # None
        )
        
        # Automatic conversion
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Compare null field handling
        manual_dict = manual_train.model_dump()
        consolidated_dict = consolidated_train.model_dump()
        
        # Null fields should be handled identically
        assert manual_dict["line_code"] == consolidated_dict["line_code"] == None
        assert manual_dict["track"] == consolidated_dict["track"] == None
        assert manual_dict["status"] == consolidated_dict["status"] == None
        assert manual_dict["track_assigned_at"] == consolidated_dict["track_assigned_at"] == None
        assert manual_dict["delay_minutes"] == consolidated_dict["delay_minutes"] == None


class TestBackwardCompatibility:
    """Test that existing code patterns still work."""

    def test_consolidated_models_work_as_response_types(self):
        """Test that consolidated models can be used as FastAPI response types."""
        # This simulates how the models would be used in FastAPI
        
        # Create sample data
        sample_train_data = {
            "id": 1,
            "train_id": "3829",
            "origin_station_code": "NY",
            "origin_station_name": "New York Penn Station",
            "data_source": "njtransit",
            "line": "Northeast Corrdr",
            "destination": "Trenton",
            "departure_time": datetime(2025, 5, 9, 10, 30, 0),
            "created_at": datetime(2025, 5, 9, 9, 0, 0),
            "updated_at": datetime(2025, 5, 9, 9, 0, 0),
        }
        
        # Should be able to create the model directly
        train_response = ConsolidatedTrainResponse(**sample_train_data)
        
        # Should be serializable to JSON
        json_output = train_response.model_dump_json()
        assert "train_id" in json_output
        assert "3829" in json_output
        
        # Should be serializable to dict
        dict_output = train_response.model_dump()
        assert dict_output["train_id"] == "3829"
        assert dict_output["origin_station_code"] == "NY"

    def test_list_response_structure_preserved(self):
        """Test that list response structure is preserved."""
        from trackcast.api.models_consolidated import TrainListResponseConsolidated
        
        # Create sample list response
        sample_trains = [
            ConsolidatedTrainResponse(
                id=1,
                train_id="3829",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time=datetime(2025, 5, 9, 10, 30, 0),
                created_at=datetime(2025, 5, 9, 9, 0, 0),
                updated_at=datetime(2025, 5, 9, 9, 0, 0),
            )
        ]
        
        list_response = TrainListResponseConsolidated(
            metadata={
                "timestamp": "2025-05-09T10:30:00",
                "model_version": "1.0.0",
                "train_count": 1,
                "page": 1,
                "total_pages": 1,
            },
            trains=sample_trains,
        )
        
        # Should match the existing structure
        response_dict = list_response.model_dump()
        assert "metadata" in response_dict
        assert "trains" in response_dict
        assert len(response_dict["trains"]) == 1
        assert response_dict["trains"][0]["train_id"] == "3829"