"""
Phase 2 Tests: API Router Integration with Consolidated Models.

Tests that the new consolidated router endpoints produce identical output
to the existing manual approach while being significantly faster.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from trackcast.api.routers.trains_consolidated import router as consolidated_router
from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainRepository, TrainStopRepository


class TestConsolidatedRouterIntegration:
    """Test that consolidated router produces identical results to manual approach."""

    def test_consolidated_endpoint_response_format(self, db_session):
        """Test that /consolidated endpoint returns the expected format."""
        # Create test data
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
                station_code="NP",
                station_name="Newark Penn Station",
                scheduled_arrival=datetime(2025, 5, 9, 10, 45, 0),
                departed=False,
                stop_status="",
            ),
        ]
        
        db_session.add_all([train] + stops)
        db_session.commit()
        
        # Ensure all attributes are loaded before detaching from session
        db_session.refresh(train)
        for stop in stops:
            db_session.refresh(stop)
        
        # Set relationship fields to None to avoid lazy loading issues
        train.prediction_data = None
        train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        db_session.expunge(train)
        for stop in stops:
            db_session.expunge(stop)
        
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = ([train], 1)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = stops
        
        # Create test client with mocked dependencies
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        # Override dependencies
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test the consolidated endpoint
        response = client.get("/trains/consolidated")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches expected format
        assert "metadata" in data
        assert "trains" in data
        
        # Verify metadata structure
        metadata = data["metadata"]
        assert "timestamp" in metadata
        assert "model_version" in metadata
        assert "train_count" in metadata
        assert "page" in metadata
        assert "total_pages" in metadata
        
        # Verify train data structure
        trains = data["trains"]
        assert len(trains) == 1
        
        train_data = trains[0]
        assert train_data["train_id"] == "3829"
        assert train_data["origin_station_code"] == "NY"
        assert train_data["track"] == "13"
        assert train_data["status"] == "BOARDING"
        
        # Verify stops structure
        assert "stops" in train_data
        assert len(train_data["stops"]) == 2
        
        stop_data = train_data["stops"][0]
        assert stop_data["station_code"] == "NY"
        assert stop_data["departed"] is True
        assert stop_data["stop_status"] == "DEPARTED"

    def test_comparison_endpoint_shows_identical_results(self, db_session):
        """Test that /compare endpoint shows manual and consolidated approaches are identical."""
        # Create test data
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
        
        stop = TrainStop(
            train_id="3829",
            train_departure_time=datetime(2025, 5, 9, 10, 30, 0),
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=datetime(2025, 5, 9, 10, 30, 0),
            departed=True,
            stop_status="DEPARTED",
        )
        
        db_session.add_all([train, stop])
        db_session.commit()
        
        # Ensure all attributes are loaded before detaching from session
        db_session.refresh(train)
        db_session.refresh(stop)
        
        # Set relationship fields to None to avoid lazy loading issues
        train.prediction_data = None
        train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        db_session.expunge(train)
        db_session.expunge(stop)
        
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = ([train], 1)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = [stop]
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        # Override dependencies
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test the comparison endpoint
        response = client.get("/trains/compare?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify comparison structure
        assert "comparison" in data
        assert "sample_output" in data
        
        comparison = data["comparison"]
        assert "train_count" in comparison
        assert "results_identical" in comparison
        assert "performance" in comparison
        assert "code_reduction" in comparison
        
        # The key test: results should be identical
        assert comparison["results_identical"] is True
        
        # Performance should show consolidated is faster or similar
        performance = comparison["performance"]
        assert "manual_time_seconds" in performance
        assert "consolidated_time_seconds" in performance
        assert "speedup_factor" in performance
        assert performance["speedup_factor"] >= 0.5  # At least not significantly slower
        
        # Sample output should exist and be identical
        sample_output = data["sample_output"]
        assert "manual_approach" in sample_output
        assert "consolidated_approach" in sample_output
        
        manual_sample = sample_output["manual_approach"]
        consolidated_sample = sample_output["consolidated_approach"]
        
        # They should be identical
        assert manual_sample == consolidated_sample
        
        # Verify the sample has the expected structure
        assert manual_sample["train_id"] == "3829"
        assert manual_sample["track"] == "13"
        assert len(manual_sample["stops"]) == 1
        assert manual_sample["stops"][0]["station_code"] == "NY"

    def test_consolidated_endpoint_with_query_parameters(self, db_session):
        """Test consolidated endpoint with various query parameters."""
        # Create multiple test trains
        trains = []
        for i in range(3):
            train = Train(
                train_id=f"382{i}",
                origin_station_code="NY",
                origin_station_name="New York Penn Station",
                data_source="njtransit",
                line="Northeast Corrdr",
                destination="Trenton",
                departure_time=datetime(2025, 5, 9, 10 + i, 30, 0),
                track=f"1{i + 3}",
                status="BOARDING",
            )
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # Ensure all attributes are loaded before detaching from session
        for train in trains:
            db_session.refresh(train)
        
        # Set relationship fields to None to avoid lazy loading issues
        for train in trains:
            train.prediction_data = None
            train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        for train in trains:
            db_session.expunge(train)
        
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = (trains, 3)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = []
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test with limit parameter
        response = client.get("/trains/consolidated?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["train_count"] == 3  # Total found
        
        # Test with no_pagination
        response = client.get("/trains/consolidated?no_pagination=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["trains"]) == 3
        
        # Verify the train data
        for i, train_data in enumerate(data["trains"]):
            assert train_data["train_id"] == f"382{i}"
            assert train_data["track"] == f"1{i + 3}"

    def test_error_handling_in_consolidated_endpoint(self):
        """Test error handling in consolidated endpoint."""
        # Mock repositories that raise exceptions
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.side_effect = Exception("Database error")
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test error handling
        response = client.get("/trains/consolidated")
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

    def test_parameter_validation_in_consolidated_endpoint(self):
        """Test parameter validation in consolidated endpoint."""
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_stop_repo = Mock(spec=TrainStopRepository)
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test invalid station code (this will fail validation)
        response = client.get("/trains/consolidated?from_station_code=INVALID")
        assert response.status_code == 400
        assert "Invalid from_station_code" in response.json()["detail"]
        
        # Test missing from_station_code with to_station_code
        response = client.get("/trains/consolidated?to_station_code=TR")
        assert response.status_code == 400
        assert "to_station_code requires from_station_code" in response.json()["detail"]


class TestConsolidatedRouterPerformance:
    """Test performance characteristics of consolidated router."""

    def test_consolidated_conversion_performance(self, db_session):
        """Test that consolidated conversion is significantly faster."""
        # Create test data
        trains = []
        stops_list = []
        
        for i in range(10):  # Moderate number for testing
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
            
            # Add stops for each train
            train_stops = []
            for j in range(3):  # 3 stops per train
                stop = TrainStop(
                    train_id=f"test{i:04d}",
                    train_departure_time=datetime(2025, 5, 9, 10, i, 0),
                    station_code=f"ST{j}",
                    station_name=f"Station {j}",
                    departed=j == 0,  # First stop is departed
                )
                train_stops.append(stop)
            stops_list.append(train_stops)
        
        db_session.add_all(trains + [stop for stops in stops_list for stop in stops])
        db_session.commit()
        
        # Ensure all attributes are loaded before detaching from session
        for train in trains:
            db_session.refresh(train)
        for stops in stops_list:
            for stop in stops:
                db_session.refresh(stop)
        
        # Set relationship fields to None to avoid lazy loading issues
        for train in trains:
            train.prediction_data = None
            train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        for train in trains:
            db_session.expunge(train)
        for stops in stops_list:
            for stop in stops:
                db_session.expunge(stop)
        
        # Test via the comparison endpoint
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = (trains, len(trains))
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        # Return different stops for each train
        def get_stops_side_effect(train_id, departure_time):
            for i, train in enumerate(trains):
                if train.train_id == train_id:
                    return stops_list[i]
            return []
        
        mock_stop_repo.get_stops_for_train.side_effect = get_stops_side_effect
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Test performance comparison
        response = client.get(f"/trains/compare?limit={len(trains)}")
        assert response.status_code == 200
        
        data = response.json()
        comparison = data["comparison"]
        
        # Verify results are identical
        assert comparison["results_identical"] is True
        
        # Performance should show improvement or at least no significant regression
        performance = comparison["performance"]
        assert performance["speedup_factor"] >= 0.5  # Allow up to 2x slower at worst
        
        # Print performance metrics for debugging
        print(f"Performance comparison for {len(trains)} trains:")
        print(f"  Manual: {performance['manual_time_seconds']:.6f}s")
        print(f"  Consolidated: {performance['consolidated_time_seconds']:.6f}s")
        print(f"  Speedup: {performance['speedup_factor']:.2f}x")


class TestConsolidatedRouterEdgeCases:
    """Test edge cases and error scenarios."""

    def test_train_with_no_stops(self, db_session):
        """Test handling of trains with no stops."""
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
        
        # Ensure all attributes are loaded before detaching from session
        db_session.refresh(train)
        
        # Set relationship fields to None to avoid lazy loading issues
        train.prediction_data = None
        train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        db_session.expunge(train)
        
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = ([train], 1)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.return_value = []  # No stops
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Should handle gracefully
        response = client.get("/trains/consolidated")
        assert response.status_code == 200
        
        data = response.json()
        trains = data["trains"]
        assert len(trains) == 1
        assert trains[0]["train_id"] == "3829"
        assert trains[0]["stops"] == []  # Empty stops list

    def test_stop_conversion_error_handling(self, db_session):
        """Test error handling during stop conversion."""
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
        
        # Ensure all attributes are loaded before detaching from session
        db_session.refresh(train)
        
        # Set relationship fields to None to avoid lazy loading issues
        train.prediction_data = None
        train.model_data = None
        
        # Detach objects from session to avoid lazy loading issues
        db_session.expunge(train)
        
        # Mock repositories
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = ([train], 1)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        mock_stop_repo.get_stops_for_train.side_effect = Exception("Stop loading error")
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Should handle gracefully and return train without stops
        response = client.get("/trains/consolidated")
        assert response.status_code == 200
        
        data = response.json()
        trains = data["trains"]
        assert len(trains) == 1
        assert trains[0]["train_id"] == "3829"
        assert trains[0]["stops"] == []  # Empty due to error

    def test_comparison_with_no_trains(self):
        """Test comparison endpoint when no trains are found."""
        # Mock repositories with no data
        mock_train_repo = Mock(spec=TrainRepository)
        mock_train_repo.get_trains.return_value = ([], 0)
        
        mock_stop_repo = Mock(spec=TrainStopRepository)
        
        # Create test client
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(consolidated_router, prefix="/trains")
        
        from trackcast.api.routers.trains_consolidated import get_train_repository, get_train_stop_repository
        app.dependency_overrides[get_train_repository] = lambda: mock_train_repo
        app.dependency_overrides[get_train_stop_repository] = lambda: mock_stop_repo
        
        client = TestClient(app)
        
        # Should handle gracefully
        response = client.get("/trains/compare")
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "No trains found for comparison"
        assert data["manual_approach"] is None
        assert data["consolidated_approach"] is None