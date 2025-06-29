"""
Tests for repository filtering functionality.

This module tests the new filtering methods added to TrainRepository
for the enhanced prediction generation and clearing features.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from trackcast.db.models import Train, ModelData, PredictionData
from trackcast.utils import get_eastern_now
from trackcast.db.repository import TrainRepository


class TestTrainRepositoryFiltering:
    """Test filtering methods in TrainRepository."""

    def test_get_trains_needing_predictions_basic(self, db_session):
        """Test basic get_trains_needing_predictions functionality."""
        repo = TrainRepository(db_session)
        
        # Create test trains
        train1 = Train(
            train_id="7001",
            line="Northeast Corridor",
            destination="Trenton",
            departure_time=datetime.utcnow() + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        train2 = Train(
            train_id="7002", 
            line="Northeast Corridor",
            destination="Princeton Junction",
            departure_time=datetime.utcnow() + timedelta(hours=2),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        # Create model data for train1 only
        model_data1 = ModelData(feature_version="1.0")
        db_session.add(model_data1)
        db_session.flush()
        train1.model_data_id = model_data1.id
        
        db_session.add_all([train1, train2])
        db_session.commit()
        
        # Test: should return only train1 (has features, no predictions)
        trains = repo.get_trains_needing_predictions()
        assert len(trains) == 1
        assert trains[0].train_id == "7001"

    def test_get_trains_needing_predictions_with_train_id_filter(self, db_session):
        """Test filtering by train ID."""
        repo = TrainRepository(db_session)
        
        # Create test trains with features
        trains = []
        for i in range(3):
            train = Train(
                train_id=f"700{i+1}",
                line="Northeast Corridor",
                destination="Trenton",
                departure_time=datetime.utcnow() + timedelta(hours=i+1),
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
        
        # Test: filter by specific train ID
        filtered_trains = repo.get_trains_needing_predictions(train_id="7002")
        assert len(filtered_trains) == 1
        assert filtered_trains[0].train_id == "7002"

    def test_get_trains_needing_predictions_with_time_range_filter(self, db_session):
        """Test filtering by time range."""
        repo = TrainRepository(db_session)
        
        now = get_eastern_now()
        
        # Create test trains at different times
        times = [
            now + timedelta(hours=1),  # Within range
            now + timedelta(hours=6),  # Within range  
            now + timedelta(hours=15), # Outside range
        ]
        
        trains = []
        for i, departure_time in enumerate(times):
            train = Train(
                train_id=f"700{i+1}",
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
        
        # Test: filter by time range (next 12 hours)
        start_time = now
        end_time = now + timedelta(hours=12)
        filtered_trains = repo.get_trains_needing_predictions(
            time_range=(start_time, end_time)
        )
        
        assert len(filtered_trains) == 2
        train_ids = {t.train_id for t in filtered_trains}
        assert train_ids == {"7001", "7002"}

    def test_get_trains_needing_predictions_with_future_only_filter(self, db_session):
        """Test filtering for future trains only."""
        repo = TrainRepository(db_session)
        
        now = get_eastern_now()
        
        # Create test trains - past and future
        times = [
            now - timedelta(hours=1),  # Past
            now + timedelta(hours=1),  # Future
            now + timedelta(hours=2),  # Future
        ]
        
        trains = []
        for i, departure_time in enumerate(times):
            train = Train(
                train_id=f"700{i+1}",
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
        
        # Test: filter for future trains only
        filtered_trains = repo.get_trains_needing_predictions(future_only=True)
        
        assert len(filtered_trains) == 2
        train_ids = {t.train_id for t in filtered_trains}
        assert train_ids == {"7002", "7003"}

    def test_get_future_trains_all(self, db_session):
        """Test getting all future trains."""
        repo = TrainRepository(db_session)
        
        now = get_eastern_now()
        
        # Create test trains - past and future
        times = [
            now - timedelta(hours=1),  # Past
            now + timedelta(hours=1),  # Future
            now + timedelta(hours=2),  # Future
        ]
        
        trains = []
        for i, departure_time in enumerate(times):
            train = Train(
                train_id=f"700{i+1}",
                line="Northeast Corridor",
                destination="Trenton",
                departure_time=departure_time,
                origin_station_code="NY", 
                data_source="njtransit"
            )
            trains.append(train)
        
        db_session.add_all(trains)
        db_session.commit()
        
        # Test: get all future trains (with or without predictions)
        future_trains = repo.get_future_trains(include_predictions=True)
        
        assert len(future_trains) == 2
        train_ids = {t.train_id for t in future_trains}
        assert train_ids == {"7002", "7003"}

    def test_get_future_trains_needing_predictions_only(self, db_session):
        """Test getting future trains that need predictions only."""
        repo = TrainRepository(db_session)
        
        now = get_eastern_now()
        
        # Create future trains - some with features, some with predictions
        train1 = Train(
            train_id="7001",
            line="Northeast Corridor",
            destination="Trenton",
            departure_time=now + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        train2 = Train(
            train_id="7002", 
            line="Northeast Corridor",
            destination="Princeton Junction",
            departure_time=now + timedelta(hours=2),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        # Give both trains features
        model_data1 = ModelData(feature_version="1.0")
        model_data2 = ModelData(feature_version="1.0")
        db_session.add_all([model_data1, model_data2])
        db_session.flush()
        train1.model_data_id = model_data1.id
        train2.model_data_id = model_data2.id
        
        # Give train2 predictions
        prediction_data = PredictionData(
            model_data_id=model_data2.id,
            track_probabilities={"1": 0.5, "2": 0.5},
            prediction_factors=[],
            model_version="test"
        )
        db_session.add(prediction_data)
        db_session.flush()
        train2.prediction_data_id = prediction_data.id
        
        db_session.add_all([train1, train2])
        db_session.commit()
        
        # Test: get future trains needing predictions only
        future_trains = repo.get_future_trains(include_predictions=False)
        
        assert len(future_trains) == 1
        assert future_trains[0].train_id == "7001"


class TestTrainRepositoryClearingMethods:
    """Test prediction clearing methods in TrainRepository."""

    def test_clear_predictions_for_train_existing(self, db_session):
        """Test clearing predictions for an existing train."""
        repo = TrainRepository(db_session)
        
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
        
        # Test: clear predictions for the train
        stats = repo.clear_predictions_for_train("7001")
        
        assert stats["train_found"] is True
        assert stats["train_had_prediction"] is True
        assert stats["trains_cleared"] == 1
        assert stats["predictions_deleted"] == 1
        
        # Verify train has no prediction reference
        db_session.refresh(train)
        assert train.prediction_data_id is None
        
        # Verify prediction data was deleted
        remaining_predictions = db_session.query(PredictionData).count()
        assert remaining_predictions == 0

    def test_clear_predictions_for_train_nonexistent(self, db_session):
        """Test clearing predictions for a non-existent train."""
        repo = TrainRepository(db_session)
        
        # Test: clear predictions for non-existent train
        stats = repo.clear_predictions_for_train("99999")
        
        assert stats["train_found"] is False
        assert stats["trains_cleared"] == 0
        assert stats["predictions_deleted"] == 0

    def test_clear_predictions_for_train_no_predictions(self, db_session):
        """Test clearing predictions for a train that has no predictions."""
        repo = TrainRepository(db_session)
        
        # Create train without predictions
        train = Train(
            train_id="7001",
            line="Northeast Corridor",
            destination="Trenton",
            departure_time=datetime.utcnow() + timedelta(hours=1),
            origin_station_code="NY",
            data_source="njtransit"
        )
        
        db_session.add(train)
        db_session.commit()
        
        # Test: clear predictions for train with no predictions
        stats = repo.clear_predictions_for_train("7001")
        
        assert stats["train_found"] is True
        assert stats["train_had_prediction"] is False
        assert stats["trains_cleared"] == 0
        assert stats["predictions_deleted"] == 0

    def test_clear_predictions_for_future_trains(self, db_session):
        """Test clearing predictions for future trains."""
        repo = TrainRepository(db_session)
        
        now = get_eastern_now()
        
        # Create trains - past and future with predictions
        trains_data = [
            ("7001", now - timedelta(hours=1)),  # Past
            ("7002", now + timedelta(hours=1)),  # Future
            ("7003", now + timedelta(hours=2)),  # Future
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
        
        # Test: clear predictions for future trains only
        stats = repo.clear_predictions_for_future_trains()
        
        assert stats["trains_cleared"] == 2  # Only future trains
        assert stats["predictions_deleted"] == 2
        
        # Verify past train still has prediction
        past_train = db_session.query(Train).filter(Train.train_id == "7001").first()
        assert past_train.prediction_data_id is not None
        
        # Verify future trains have no predictions
        future_trains = db_session.query(Train).filter(
            Train.train_id.in_(["7002", "7003"])
        ).all()
        for train in future_trains:
            assert train.prediction_data_id is None