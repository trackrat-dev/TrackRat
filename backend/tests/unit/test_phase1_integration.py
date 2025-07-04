"""
Phase 1 Integration Tests: End-to-end testing of consolidated models.

This tests the complete flow from SQLAlchemy models to API responses using
the new consolidated approach vs the current manual approach.
"""

import json
import pytest
from datetime import datetime
from typing import List

from trackcast.api.models import TrainListResponse, TrainResponse as OriginalTrainResponse
from trackcast.api.models_consolidated import (
    TrainListResponseConsolidated,
    TrainResponse as ConsolidatedTrainResponse,
    TrainStopResponse as ConsolidatedTrainStopResponse,
    PredictionDataResponse as ConsolidatedPredictionDataResponse,
)
from trackcast.db.models import Train, TrainStop, PredictionData


class TestCompleteFlowIntegration:
    """Test the complete flow from database to API response."""

    def test_complete_train_with_stops_and_predictions(self, db_session):
        """Test complete conversion flow with train, stops, and predictions."""
        # Create complete SQLAlchemy models
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
            delay_minutes=2,
        )
        
        db_stops = [
            TrainStop(
                train_id="3829",
                train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
                departed=True,
                stop_status="DEPARTED",
            ),
            TrainStop(
                train_id="3829",
                train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
                station_code="NP",
                station_name="Newark Penn Station",
                scheduled_arrival=datetime(2025, 5, 9, 10, 45, 0),
                scheduled_departure=datetime(2025, 5, 9, 10, 47, 0),
                departed=False,
                stop_status="",
            ),
            TrainStop(
                train_id="3829",
                train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
                station_code="TR",
                station_name="Trenton Transit Center",
                scheduled_arrival=datetime(2025, 5, 9, 11, 15, 0),
                departed=False,
                stop_status="",
            ),
        ]
        
        db_prediction = PredictionData(
            track_probabilities={"13": 0.85, "12": 0.10, "14": 0.05},
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
        
        # Save to database
        db_session.add_all([db_train, db_prediction] + db_stops)
        db_session.commit()
        
        # Link prediction to train
        db_train.prediction_data_id = db_prediction.id
        db_session.commit()
        
        # === CURRENT MANUAL APPROACH (simulated) ===
        from trackcast.api.models import TrainStop as OriginalTrainStop, PredictionData as OriginalPredictionData
        
        # Manual stop conversion
        manual_stops = []
        for stop in db_stops:
            manual_stops.append(
                OriginalTrainStop(
                    station_code=getattr(stop, "station_code", None),
                    station_name=getattr(stop, "station_name", ""),
                    scheduled_arrival=getattr(stop, "scheduled_arrival", None),
                    scheduled_departure=getattr(stop, "scheduled_departure", None),
                    actual_arrival=getattr(stop, "actual_arrival", None),
                    actual_departure=getattr(stop, "actual_departure", None),
                    estimated_arrival=getattr(stop, "estimated_arrival", None),
                    pickup_only=bool(getattr(stop, "pickup_only", False)),
                    dropoff_only=bool(getattr(stop, "dropoff_only", False)),
                    departed=bool(getattr(stop, "departed", False)),
                    stop_status=getattr(stop, "stop_status", None),
                )
            )
        
        # Manual prediction conversion
        manual_prediction = OriginalPredictionData(
            track_probabilities=db_prediction.track_probabilities,
            prediction_factors=db_prediction.prediction_factors,
            model_version=db_prediction.model_version,
            created_at=db_prediction.created_at,
        )
        
        # Manual train conversion
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
            prediction_data=manual_prediction,
            stops=manual_stops,
        )
        
        # === NEW CONSOLIDATED APPROACH ===
        
        # Automatic conversion
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Automatic stop conversion
        consolidated_stops = [
            ConsolidatedTrainStopResponse.model_validate(stop) for stop in db_stops
        ]
        consolidated_train.stops = consolidated_stops
        
        # Automatic prediction conversion
        consolidated_prediction = ConsolidatedPredictionDataResponse.model_validate(db_prediction)
        consolidated_train.prediction_data = consolidated_prediction
        
        # === COMPARE RESULTS ===
        
        # Convert both to dictionaries for comparison
        manual_dict = manual_train.model_dump()
        consolidated_dict = consolidated_train.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify specific nested structures
        assert len(manual_dict["stops"]) == len(consolidated_dict["stops"]) == 3
        assert manual_dict["stops"][0]["station_code"] == consolidated_dict["stops"][0]["station_code"] == "NY"
        assert manual_dict["stops"][0]["departed"] == consolidated_dict["stops"][0]["departed"] == True
        
        assert manual_dict["prediction_data"]["track_probabilities"] == consolidated_dict["prediction_data"]["track_probabilities"]
        assert manual_dict["prediction_data"]["model_version"] == consolidated_dict["prediction_data"]["model_version"]
        
        # Verify JSON serialization is identical
        manual_json = manual_train.model_dump_json()
        consolidated_json = consolidated_train.model_dump_json()
        
        manual_parsed = json.loads(manual_json)
        consolidated_parsed = json.loads(consolidated_json)
        
        assert manual_parsed == consolidated_parsed

    def test_train_list_response_equivalence(self, db_session):
        """Test that TrainListResponse structures are equivalent."""
        # Create multiple trains
        trains = []
        for i in range(3):
            train = Train(
                train_id=f"382{i}",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time=datetime(2025, 5, 9, 10 + i, 30, 0),  # 10:30, 11:30, 12:30
                track=f"1{i + 3}",
                status="BOARDING",
            )
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # === MANUAL APPROACH ===
        manual_train_responses = []
        for train in trains:
            manual_train_responses.append(
                OriginalTrainResponse(
                    id=train.id,
                    train_id=train.train_id,
                    origin_station_code=train.origin_station_code,
                    origin_station_name=train.origin_station_name,
                    data_source=train.data_source,
                    line=train.line,
                    line_code=train.line_code,
                    destination=train.destination,
                    departure_time=train.departure_time,
                    status=train.status,
                    track=train.track,
                    created_at=train.created_at,
                    prediction_data=None,
                    stops=None,
                )
            )
        
        manual_list_response = TrainListResponse(
            metadata={
                "timestamp": "2025-05-09T10:30:00",
                "model_version": "1.0.0",
                "train_count": 3,
                "page": 1,
                "total_pages": 1,
            },
            trains=manual_train_responses,
        )
        
        # === CONSOLIDATED APPROACH ===
        consolidated_train_responses = [
            ConsolidatedTrainResponse.model_validate(train) for train in trains
        ]
        
        consolidated_list_response = TrainListResponseConsolidated(
            metadata={
                "timestamp": "2025-05-09T10:30:00",
                "model_version": "1.0.0",
                "train_count": 3,
                "page": 1,
                "total_pages": 1,
            },
            trains=consolidated_train_responses,
        )
        
        # === COMPARE RESULTS ===
        manual_dict = manual_list_response.model_dump()
        consolidated_dict = consolidated_list_response.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify structure
        assert "metadata" in manual_dict
        assert "trains" in manual_dict
        assert len(manual_dict["trains"]) == 3
        assert manual_dict["trains"][0]["train_id"] == "3820"
        assert manual_dict["trains"][1]["train_id"] == "3821"
        assert manual_dict["trains"][2]["train_id"] == "3822"

    def test_null_handling_comprehensive(self, db_session):
        """Test comprehensive null value handling across all models."""
        # Create train with mostly null values (minimal required fields only)
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            # All optional fields are None/null
        )
        
        # Create stop with mostly null values
        db_stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_name="Test Station",
            # Most fields are None/null
        )
        
        db_session.add_all([db_train, db_stop])
        db_session.commit()
        
        # === MANUAL APPROACH ===
        from trackcast.api.models import TrainStop as OriginalTrainStop
        
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
            status=db_train.status,  # None
            track=db_train.track,  # None
            created_at=db_train.created_at,
            track_assigned_at=db_train.track_assigned_at,  # None
            track_released_at=db_train.track_released_at,  # None
            delay_minutes=db_train.delay_minutes,  # None
            train_split=db_train.train_split,  # None
            journey_completion_status=db_train.journey_completion_status,  # None
            stops_last_updated=db_train.stops_last_updated,  # None
            journey_validated_at=db_train.journey_validated_at,  # None
            prediction_data=None,
            stops=[manual_stop],
        )
        
        # === CONSOLIDATED APPROACH ===
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        consolidated_stop = ConsolidatedTrainStopResponse.model_validate(db_stop)
        consolidated_train.stops = [consolidated_stop]
        
        # === COMPARE RESULTS ===
        manual_dict = manual_train.model_dump()
        consolidated_dict = consolidated_train.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify null handling
        assert manual_dict["line_code"] == consolidated_dict["line_code"] == None
        assert manual_dict["status"] == consolidated_dict["status"] == None
        assert manual_dict["track"] == consolidated_dict["track"] == None
        assert manual_dict["stops"][0]["station_code"] == consolidated_dict["stops"][0]["station_code"] == None
        assert manual_dict["stops"][0]["stop_status"] == consolidated_dict["stops"][0]["stop_status"] == None

    def test_performance_comparison(self, db_session):
        """Test that consolidated approach isn't significantly slower."""
        import time
        
        # Create test data
        trains = []
        for i in range(10):  # Small batch for quick testing
            train = Train(
                train_id=f"test{i:04d}",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time=datetime(2025, 5, 9, 10, i, 0),
                track=f"{i % 20 + 1}",
            )
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # === TIME MANUAL APPROACH ===
        start_time = time.time()
        
        manual_responses = []
        for train in trains:
            manual_responses.append(
                OriginalTrainResponse(
                    id=train.id,
                    train_id=train.train_id,
                    origin_station_code=train.origin_station_code,
                    origin_station_name=train.origin_station_name,
                    data_source=train.data_source,
                    line=train.line,
                    line_code=train.line_code,
                    destination=train.destination,
                    departure_time=train.departure_time,
                    status=train.status,
                    track=train.track,
                    created_at=train.created_at,
                    prediction_data=None,
                    stops=None,
                )
            )
        
        manual_time = time.time() - start_time
        
        # === TIME CONSOLIDATED APPROACH ===
        start_time = time.time()
        
        consolidated_responses = [
            ConsolidatedTrainResponse.model_validate(train) for train in trains
        ]
        
        consolidated_time = time.time() - start_time
        
        # Verify they produce the same results
        manual_dicts = [r.model_dump() for r in manual_responses]
        consolidated_dicts = [r.model_dump() for r in consolidated_responses]
        
        assert manual_dicts == consolidated_dicts
        
        # Performance shouldn't be significantly worse (allow 2x slower at most)
        assert consolidated_time <= manual_time * 2.0, f"Consolidated approach too slow: {consolidated_time:.4f}s vs {manual_time:.4f}s"
        
        print(f"Performance comparison:")
        print(f"  Manual approach: {manual_time:.4f}s")
        print(f"  Consolidated approach: {consolidated_time:.4f}s")
        print(f"  Ratio: {consolidated_time / manual_time:.2f}x")


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_required_fields(self):
        """Test handling of missing required fields."""
        # This should fail validation
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConsolidatedTrainResponse(
                # Missing required fields like train_id, line, etc.
                id=1,
                origin_station_code="NY",
            )

    def test_invalid_field_types(self):
        """Test handling of invalid field types."""
        # This should fail validation
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConsolidatedTrainResponse(
                id="not_an_int",  # Should be int
                train_id="3829",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time="not_a_datetime",  # Should be datetime
                created_at=datetime.now(),
            )

    def test_extra_fields_ignored(self, db_session):
        """Test that extra fields from SQLAlchemy are properly ignored."""
        # Create SQLAlchemy model
        db_train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            # This field exists in SQLAlchemy but not in API response
            next_validation_check=datetime(2025, 5, 9, 11, 0, 0),
        )
        
        db_session.add(db_train)
        db_session.commit()
        
        # Should convert successfully, ignoring the extra field
        consolidated_train = ConsolidatedTrainResponse.model_validate(db_train)
        
        # Extra field should not be in the output
        response_dict = consolidated_train.model_dump()
        assert "next_validation_check" not in response_dict
        assert "updated_at" not in response_dict
        
        # But all expected fields should be there
        assert "train_id" in response_dict
        assert "origin_station_code" in response_dict
        assert "created_at" in response_dict