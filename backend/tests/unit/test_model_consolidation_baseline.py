"""
Baseline tests for model consolidation - captures current API response format.

These tests ensure that after model consolidation, the API responses remain 
identical to preserve iOS app compatibility.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from trackcast.api.models import (
    TrainResponse,
    TrainStop,
    PredictionData,
    ModelData,
    TrainListResponse,
    ConsolidatedTrainResponse,
)
from trackcast.db.models import Train, TrainStop as DBTrainStop, PredictionData as DBPredictionData
from trackcast.utils import get_eastern_now


class TestCurrentAPIResponseFormat:
    """Test current API response format to ensure no breaking changes."""

    def test_train_response_json_structure(self):
        """Test the exact JSON structure of TrainResponse."""
        # Create a TrainResponse with all fields
        response = TrainResponse(
            id=1,
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
            created_at=datetime(2025, 5, 9, 9, 0, 0),
            track_assigned_at=datetime(2025, 5, 9, 10, 25, 0),
            track_released_at=None,
            delay_minutes=0,
            train_split="train",
            journey_completion_status="in_progress",
            stops_last_updated=datetime(2025, 5, 9, 10, 0, 0),
            journey_validated_at=datetime(2025, 5, 9, 10, 0, 0),
            prediction_data=None,
            stops=None,
        )
        
        # Convert to dict and verify structure
        response_dict = response.model_dump()
        
        # Verify all required fields are present
        expected_fields = {
            "id", "train_id", "origin_station_code", "origin_station_name",
            "data_source", "line", "line_code", "destination", "departure_time",
            "status", "track", "created_at", "track_assigned_at", "track_released_at",
            "delay_minutes", "train_split", "journey_completion_status",
            "stops_last_updated", "journey_validated_at", "prediction_data", "stops"
        }
        
        assert set(response_dict.keys()) == expected_fields
        
        # Verify field types and values
        assert response_dict["id"] == 1
        assert response_dict["train_id"] == "3829"
        assert response_dict["origin_station_code"] == "NY"
        assert response_dict["data_source"] == "njtransit"
        assert response_dict["line"] == "Northeast Corrdr"
        assert response_dict["destination"] == "Trenton"
        assert response_dict["status"] == "BOARDING"
        assert response_dict["track"] == "13"
        assert response_dict["prediction_data"] is None
        assert response_dict["stops"] is None

    def test_train_stop_json_structure(self):
        """Test the exact JSON structure of TrainStop."""
        stop = TrainStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_arrival=datetime(2025, 5, 9, 10, 30, 0),
            scheduled_departure=datetime(2025, 5, 9, 10, 35, 0),
            actual_arrival=datetime(2025, 5, 9, 10, 32, 0),
            actual_departure=None,
            estimated_arrival=datetime(2025, 5, 9, 10, 30, 0),
            pickup_only=False,
            dropoff_only=False,
            departed=True,
            stop_status="DEPARTED",
        )
        
        stop_dict = stop.model_dump()
        
        # Verify all fields are present
        expected_fields = {
            "station_code", "station_name", "scheduled_arrival", "scheduled_departure",
            "actual_arrival", "actual_departure", "estimated_arrival", "pickup_only",
            "dropoff_only", "departed", "stop_status"
        }
        
        assert set(stop_dict.keys()) == expected_fields
        
        # Verify field values
        assert stop_dict["station_code"] == "NY"
        assert stop_dict["station_name"] == "New York Penn Station"
        assert stop_dict["pickup_only"] is False
        assert stop_dict["dropoff_only"] is False
        assert stop_dict["departed"] is True
        assert stop_dict["stop_status"] == "DEPARTED"

    def test_prediction_data_json_structure(self):
        """Test the exact JSON structure of PredictionData."""
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
            created_at=datetime(2025, 5, 9, 10, 0, 0),
        )
        
        prediction_dict = prediction.model_dump()
        
        # Verify all fields are present
        expected_fields = {
            "track_probabilities", "prediction_factors", "model_version", "created_at"
        }
        
        assert set(prediction_dict.keys()) == expected_fields
        
        # Verify field values
        assert prediction_dict["track_probabilities"] == {"13": 0.85, "12": 0.15}
        assert len(prediction_dict["prediction_factors"]) == 1
        assert prediction_dict["model_version"] == "1.0.0_NY"
        
        # Verify prediction factor structure
        factor = prediction_dict["prediction_factors"][0]
        assert factor["feature"] == "line_Northeast Corrdr"
        assert factor["importance"] == 0.45
        assert factor["direction"] == "positive"
        assert factor["explanation"] == "Northeast Corridor trains often use track 13"

    def test_train_list_response_json_structure(self):
        """Test the exact JSON structure of TrainListResponse."""
        # Create a complete train response
        train_response = TrainResponse(
            id=1,
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            status="BOARDING",
            track="13",
            created_at=datetime(2025, 5, 9, 9, 0, 0),
            stops=[
                TrainStop(
                    station_code="NY",
                    station_name="New York Penn Station",
                    scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
                    departed=True,
                    stop_status="DEPARTED",
                )
            ],
            prediction_data=PredictionData(
                track_probabilities={"13": 0.85, "12": 0.15},
                prediction_factors=[],
                model_version="1.0.0_NY",
                created_at=datetime(2025, 5, 9, 10, 0, 0),
            ),
        )
        
        # Create list response
        list_response = TrainListResponse(
            metadata={
                "timestamp": "2025-05-09T10:30:00",
                "model_version": "1.0.0",
                "train_count": 1,
                "page": 1,
                "total_pages": 1,
            },
            trains=[train_response],
        )
        
        response_dict = list_response.model_dump()
        
        # Verify top-level structure
        assert "metadata" in response_dict
        assert "trains" in response_dict
        
        # Verify metadata structure
        metadata = response_dict["metadata"]
        assert "timestamp" in metadata
        assert "model_version" in metadata
        assert "train_count" in metadata
        assert "page" in metadata
        assert "total_pages" in metadata
        
        # Verify trains list
        trains = response_dict["trains"]
        assert len(trains) == 1
        assert trains[0]["train_id"] == "3829"
        assert trains[0]["track"] == "13"
        assert "stops" in trains[0]
        assert "prediction_data" in trains[0]

    def test_train_response_with_null_values(self):
        """Test TrainResponse with null/None values - common in real data."""
        response = TrainResponse(
            id=1,
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            created_at=datetime(2025, 5, 9, 9, 0, 0),
            # These fields can be None
            line_code=None,
            status=None,
            track=None,
            track_assigned_at=None,
            track_released_at=None,
            delay_minutes=None,
            train_split=None,
            journey_completion_status=None,
            stops_last_updated=None,
            journey_validated_at=None,
            prediction_data=None,
            stops=None,
        )
        
        response_dict = response.model_dump()
        
        # Verify None values are preserved
        assert response_dict["line_code"] is None
        assert response_dict["status"] is None
        assert response_dict["track"] is None
        assert response_dict["track_assigned_at"] is None
        assert response_dict["track_released_at"] is None
        assert response_dict["delay_minutes"] is None
        assert response_dict["train_split"] is None
        assert response_dict["journey_completion_status"] is None
        assert response_dict["stops_last_updated"] is None
        assert response_dict["journey_validated_at"] is None
        assert response_dict["prediction_data"] is None
        assert response_dict["stops"] is None

    def test_train_stop_with_null_values(self):
        """Test TrainStop with null/None values - common in real data."""
        stop = TrainStop(
            station_name="New York Penn Station",
            # These fields can be None
            station_code=None,
            scheduled_arrival=None,
            scheduled_departure=None,
            actual_arrival=None,
            actual_departure=None,
            estimated_arrival=None,
            pickup_only=False,
            dropoff_only=False,
            departed=False,
            stop_status=None,
        )
        
        stop_dict = stop.model_dump()
        
        # Verify None values are preserved
        assert stop_dict["station_code"] is None
        assert stop_dict["scheduled_arrival"] is None
        assert stop_dict["scheduled_departure"] is None
        assert stop_dict["actual_arrival"] is None
        assert stop_dict["actual_departure"] is None
        assert stop_dict["estimated_arrival"] is None
        assert stop_dict["stop_status"] is None
        
        # Verify boolean defaults
        assert stop_dict["pickup_only"] is False
        assert stop_dict["dropoff_only"] is False
        assert stop_dict["departed"] is False


class TestManualConversionBaseline:
    """Test the current manual conversion process to establish baseline."""

    def test_manual_db_to_api_conversion(self, db_session):
        """Test current manual conversion from DB models to API models."""
        # Create SQLAlchemy models
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
            delay_minutes=0,
            created_at=datetime(2025, 5, 9, 9, 0, 0),
        )
        
        db_stop = DBTrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
            departed=True,
            stop_status="DEPARTED",
        )
        
        db_session.add(db_train)
        db_session.add(db_stop)
        db_session.commit()
        
        # Manual conversion (current approach)
        api_stop = TrainStop(
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
        
        # Verify manual conversion matches expected values
        assert api_stop.station_code == "NY"
        assert api_stop.station_name == "New York Penn Station"
        assert api_stop.departed is True
        assert api_stop.stop_status == "DEPARTED"
        
        # Store this as the baseline format
        baseline_stop_dict = api_stop.model_dump()
        
        # This is the exact format we need to preserve after consolidation
        expected_fields = {
            "station_code", "station_name", "scheduled_arrival", "scheduled_departure",
            "actual_arrival", "actual_departure", "estimated_arrival", "pickup_only",
            "dropoff_only", "departed", "stop_status"
        }
        
        assert set(baseline_stop_dict.keys()) == expected_fields

    def test_json_serialization_datetime_format(self):
        """Test that datetime serialization format is preserved."""
        response = TrainResponse(
            id=1,
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            created_at=datetime(2025, 5, 9, 9, 0, 0),
            track_assigned_at=datetime(2025, 5, 9, 10, 25, 0),
        )
        
        # Convert to JSON and back to verify datetime handling
        json_str = response.model_dump_json()
        parsed_json = json.loads(json_str)
        
        # Verify datetime format (ISO format expected)
        assert "departure_time" in parsed_json
        assert "created_at" in parsed_json
        assert "track_assigned_at" in parsed_json
        
        # Should be ISO format strings
        assert isinstance(parsed_json["departure_time"], str)
        assert isinstance(parsed_json["created_at"], str)
        assert isinstance(parsed_json["track_assigned_at"], str)
        
        # Should be parseable back to datetime
        departure_time = datetime.fromisoformat(parsed_json["departure_time"])
        assert departure_time == datetime(2025, 5, 9, 10, 30, 0)


class TestConsolidationResponseBaseline:
    """Test consolidated response format - critical for iOS compatibility."""

    def test_consolidated_response_structure(self):
        """Test the structure of consolidated train responses."""
        # This is a complex nested structure that must be preserved exactly
        consolidated_response = ConsolidatedTrainResponse(
            train_id="3829",
            consolidated_id="3829_2025-05-09",
            origin_station={"code": "NY", "name": "New York Penn Station", "departure_time": "2025-05-09T10:30:00"},
            destination="Trenton",
            line="Northeast Corrdr",
            line_code="NEC",
            data_sources=[
                {
                    "origin": "NY",
                    "data_source": "njtransit",
                    "last_update": "2025-05-09T10:30:00",
                    "status": "BOARDING",
                    "track": "13",
                    "delay_minutes": 0,
                    "db_id": 1,
                }
            ],
            track_assignment={
                "track": "13",
                "assigned_at": "2025-05-09T10:25:00",
                "assigned_by": "NY",
                "source": "njtransit",
            },
            status_summary={
                "current_status": "BOARDING",
                "delay_minutes": 0,
                "on_time_performance": "On Time",
            },
            stops=[
                {
                    "station_code": "NY",
                    "station_name": "New York Penn Station",
                    "scheduled_departure": "2025-05-09T10:30:00",
                    "departed": True,
                    "departed_confirmed_by": ["NY"],
                    "stop_status": "DEPARTED",
                    "platform": "13",
                    "pickup_only": False,
                    "dropoff_only": False,
                    "scheduled_arrival": None,
                    "actual_arrival": None,
                    "actual_departure": None,
                }
            ],
            consolidation_metadata={
                "source_count": 1,
                "last_update": "2025-05-09T10:30:00",
                "confidence_score": 0.95,
            },
        )
        
        response_dict = consolidated_response.model_dump()
        
        # Verify all required top-level fields
        expected_fields = {
            "train_id", "consolidated_id", "origin_station", "destination",
            "line", "line_code", "data_sources", "track_assignment", "status_summary",
            "stops", "consolidation_metadata", "current_position", "prediction_data", 
            "status_v2", "progress"
        }
        
        assert set(response_dict.keys()) == expected_fields
        
        # Verify nested structure integrity
        assert "code" in response_dict["origin_station"]
        assert "name" in response_dict["origin_station"]
        assert "departure_time" in response_dict["origin_station"]
        
        assert len(response_dict["data_sources"]) == 1
        assert "origin" in response_dict["data_sources"][0]
        assert "data_source" in response_dict["data_sources"][0]
        assert "db_id" in response_dict["data_sources"][0]
        
        assert "track" in response_dict["track_assignment"]
        assert "assigned_by" in response_dict["track_assignment"]
        
        assert "current_status" in response_dict["status_summary"]
        assert "on_time_performance" in response_dict["status_summary"]
        
        assert len(response_dict["stops"]) == 1
        assert "departed_confirmed_by" in response_dict["stops"][0]
        
        assert "source_count" in response_dict["consolidation_metadata"]
        assert "confidence_score" in response_dict["consolidation_metadata"]