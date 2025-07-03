"""
Phase 2 Simple Integration Tests: Direct testing of consolidated functions.

Tests the core consolidated conversion functions without FastAPI complexity.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from trackcast.api.routers.trains_consolidated import (
    _enrich_train_with_stops_consolidated,
)
from trackcast.api.models_consolidated import (
    TrainResponse as ConsolidatedTrainResponse,
    TrainStopResponse as ConsolidatedTrainStopResponse,
)
from trackcast.db.models import Train, TrainStop, PredictionData
from trackcast.db.repository import TrainStopRepository


class TestConsolidatedFunctionIntegration:
    """Test core consolidated functions directly."""

    def test_enrich_train_with_stops_consolidated_basic(self, db_session):
        """Test basic train enrichment with stops using consolidated approach."""
        # Create test SQLAlchemy models
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            track="13",
            status="BOARDING",
        )
        
        stops = [
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
                station_code="TR",
                station_name="Trenton Transit Center",
                scheduled_arrival=datetime(2025, 5, 9, 11, 15, 0),
                departed=False,
                stop_status="",
            ),
        ]
        
        db_session.add_all([train] + stops)
        db_session.commit()
        
        # Mock repository
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = stops
        
        # Test the consolidated function
        result = _enrich_train_with_stops_consolidated(train, mock_stop_repo)
        
        # Verify it returns a ConsolidatedTrainResponse
        assert isinstance(result, ConsolidatedTrainResponse)
        
        # Verify train data is correctly converted
        assert result.train_id == "3829"
        assert result.origin_station_code == "NY"
        assert result.track == "13"
        assert result.status == "BOARDING"
        
        # Verify stops are correctly converted
        assert result.stops is not None
        assert len(result.stops) == 2
        
        # Check first stop
        first_stop = result.stops[0]
        assert isinstance(first_stop, ConsolidatedTrainStopResponse)
        assert first_stop.station_code == "NY"
        assert first_stop.station_name == "New York Penn Station"
        assert first_stop.departed is True
        assert first_stop.stop_status == "DEPARTED"
        
        # Check second stop
        second_stop = result.stops[1]
        assert second_stop.station_code == "TR"
        assert second_stop.station_name == "Trenton Transit Center"
        assert second_stop.departed is False
        assert second_stop.stop_status == ""

    def test_enrich_train_with_stops_consolidated_with_predictions(self, db_session):
        """Test train enrichment with predictions."""
        # Create train with prediction
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
            track="13",
        )
        
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
        
        db_session.add_all([train, prediction])
        db_session.commit()
        
        # Link prediction to train
        train.prediction_data_id = prediction.id
        train.prediction_data = prediction  # Set the relationship
        db_session.commit()
        
        # Mock repository for stops
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = []
        
        # Test the consolidated function
        result = _enrich_train_with_stops_consolidated(train, mock_stop_repo)
        
        # Verify train data
        assert result.train_id == "3829"
        assert result.track == "13"
        
        # Verify prediction data is converted
        assert result.prediction_data is not None
        assert result.prediction_data.track_probabilities == {"13": 0.85, "12": 0.15}
        assert result.prediction_data.model_version == "1.0.0_NY"
        assert len(result.prediction_data.prediction_factors) == 1
        
        # Verify prediction properties work
        assert result.prediction_data.top_track == "13"
        assert result.prediction_data.top_probability == 0.85

    def test_enrich_train_with_stops_consolidated_error_handling(self, db_session):
        """Test error handling in consolidated enrichment."""
        # Create minimal train
        train = Train(
            train_id="3829",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 10, 30, 0),
        )
        
        db_session.add(train)
        db_session.commit()
        
        # Mock repository that raises an exception
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.side_effect = Exception("Database error")
        
        # Should handle the error gracefully
        result = _enrich_train_with_stops_consolidated(train, mock_stop_repo)
        
        # Should still return a valid train response
        assert isinstance(result, ConsolidatedTrainResponse)
        assert result.train_id == "3829"
        assert result.stops == []  # Empty due to error
        assert result.prediction_data is None

    def test_consolidated_vs_manual_conversion_equivalence(self, db_session):
        """Test that consolidated conversion produces identical results to manual conversion."""
        # Create comprehensive test data
        train = Train(
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
            train_split="train",
            journey_completion_status="in_progress",
        )
        
        stops = [
            TrainStop(
                train_id="3829",
                train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
                station_code="NY",
                station_name="New York Penn Station",
                scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
                actual_departure=datetime(2025, 5, 9, 10, 32, 0),
                pickup_only=False,
                dropoff_only=False,
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
                pickup_only=False,
                dropoff_only=False,
                departed=False,
                stop_status=None,
            ),
        ]
        
        db_session.add_all([train] + stops)
        db_session.commit()
        
        # Mock repository
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = stops
        
        # === MANUAL CONVERSION (current approach) ===
        from trackcast.api.models import TrainStop as OriginalTrainStop, TrainResponse as OriginalTrainResponse
        
        # Manual stop conversion
        manual_stops = []
        for stop in stops:
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
        
        # Manual train conversion
        manual_train = OriginalTrainResponse(
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
            track_assigned_at=train.track_assigned_at,
            track_released_at=train.track_released_at,
            delay_minutes=train.delay_minutes,
            train_split=train.train_split,
            journey_completion_status=train.journey_completion_status,
            stops_last_updated=train.stops_last_updated,
            journey_validated_at=train.journey_validated_at,
            prediction_data=None,
            stops=manual_stops,
        )
        
        # === CONSOLIDATED CONVERSION (new approach) ===
        consolidated_train = _enrich_train_with_stops_consolidated(train, mock_stop_repo)
        
        # === COMPARE RESULTS ===
        manual_dict = manual_train.model_dump()
        consolidated_dict = consolidated_train.model_dump()
        
        # They should be identical
        assert manual_dict == consolidated_dict
        
        # Verify specific fields
        assert consolidated_dict["train_id"] == "3829"
        assert consolidated_dict["track"] == "13"
        assert consolidated_dict["status"] == "BOARDING"
        assert consolidated_dict["delay_minutes"] == 2
        assert len(consolidated_dict["stops"]) == 2
        assert consolidated_dict["stops"][0]["departed"] is True
        assert consolidated_dict["stops"][1]["departed"] is False

    def test_train_properties_work_in_consolidated_model(self, db_session):
        """Test that computed properties work correctly in consolidated models."""
        # Test train with track
        train_with_track = Train(
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
        
        db_session.add(train_with_track)
        db_session.commit()
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = []
        
        result = _enrich_train_with_stops_consolidated(train_with_track, mock_stop_repo)
        
        # Test properties match SQLAlchemy model
        assert result.has_track == train_with_track.has_track == True
        assert result.is_boarding == train_with_track.is_boarding == True
        assert result.is_departed == train_with_track.is_departed == False
        assert result.is_delayed == train_with_track.is_delayed == False
        
        # Test train without track
        train_no_track = Train(
            train_id="3830",
            origin_station_code="NY",
            origin_station_name="New York Penn Station",
            data_source="njtransit",
            line="Northeast Corrdr",
            destination="Trenton",
            departure_time=datetime(2025, 5, 9, 11, 30, 0),
            status=None,
            track=None,
        )
        
        db_session.add(train_no_track)
        db_session.commit()
        
        result_no_track = _enrich_train_with_stops_consolidated(train_no_track, mock_stop_repo)
        
        # Test properties with no track
        assert result_no_track.has_track == train_no_track.has_track == False
        assert result_no_track.is_boarding == train_no_track.is_boarding == False
        assert result_no_track.is_departed == train_no_track.is_departed == False
        assert result_no_track.is_delayed == train_no_track.is_delayed == False


class TestConsolidatedPerformanceDirectComparison:
    """Direct performance comparison without FastAPI overhead."""

    def test_conversion_performance_direct(self, db_session):
        """Test conversion performance directly using the functions."""
        import time
        
        # Create test data
        trains = []
        all_stops = []
        
        for i in range(20):  # Moderate batch for testing
            train = Train(
                train_id=f"test{i:04d}",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time=datetime(2025, 5, 9, 10, i % 60, 0),
                track=f"{i % 20 + 1}",
                status="BOARDING" if i % 2 == 0 else "DEPARTED",
            )
            trains.append(train)
            
            # Create stops for each train
            stops = []
            for j in range(3):
                stop = TrainStop(
                    train_id=f"test{i:04d}",
                    train_departure_time=datetime(2025, 5, 9, 10, i % 60, 0),
                    station_code=f"ST{j}",
                    station_name=f"Station {j}",
                    departed=j == 0,  # First stop is departed
                    stop_status="DEPARTED" if j == 0 else "",
                )
                stops.append(stop)
            all_stops.extend(stops)
        
        db_session.add_all(trains + all_stops)
        db_session.commit()
        
        # Mock repository that returns appropriate stops for each train
        mock_stop_repo = Mock(spec=TrainStopRepository)
        
        def get_stops_side_effect(train_id, departure_time):
            return [stop for stop in all_stops if stop.train_id == train_id]
        
        mock_stop_repo.get_stops_for_train.side_effect = get_stops_side_effect
        
        # === TIME MANUAL CONVERSION ===
        from trackcast.api.models import TrainStop as OriginalTrainStop, TrainResponse as OriginalTrainResponse
        
        start_time = time.time()
        
        manual_results = []
        for train in trains:
            stops = [stop for stop in all_stops if stop.train_id == train.train_id]
            
            # Manual stop conversion
            manual_stops = []
            for stop in stops:
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
            
            # Manual train conversion
            manual_train = OriginalTrainResponse(
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
                stops=manual_stops,
                prediction_data=None,
            )
            manual_results.append(manual_train)
        
        manual_time = time.time() - start_time
        
        # === TIME CONSOLIDATED CONVERSION ===
        start_time = time.time()
        
        consolidated_results = []
        for train in trains:
            result = _enrich_train_with_stops_consolidated(train, mock_stop_repo)
            consolidated_results.append(result)
        
        consolidated_time = time.time() - start_time
        
        # === VERIFY RESULTS ARE IDENTICAL ===
        manual_dicts = [r.model_dump() for r in manual_results]
        consolidated_dicts = [r.model_dump() for r in consolidated_results]
        
        assert manual_dicts == consolidated_dicts
        
        # === PERFORMANCE ANALYSIS ===
        speedup = manual_time / consolidated_time if consolidated_time > 0 else float('inf')
        
        print(f"\nDirect Performance Comparison ({len(trains)} trains):")
        print(f"  Manual approach: {manual_time:.6f}s")
        print(f"  Consolidated approach: {consolidated_time:.6f}s")
        print(f"  Speedup factor: {speedup:.2f}x")
        print(f"  Results identical: {manual_dicts == consolidated_dicts}")
        
        # Consolidated should be at least as fast (allow small variance for test environment)
        assert speedup >= 0.8, f"Consolidated approach too slow: {speedup:.2f}x speedup"
        
        # Results should be identical
        assert len(manual_results) == len(consolidated_results) == len(trains)
        
        # Spot check specific results
        first_manual = manual_dicts[0]
        first_consolidated = consolidated_dicts[0]
        assert first_manual["train_id"] == first_consolidated["train_id"]
        assert first_manual["track"] == first_consolidated["track"]
        assert len(first_manual["stops"]) == len(first_consolidated["stops"]) == 3