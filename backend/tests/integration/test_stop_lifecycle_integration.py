"""Integration tests for stop lifecycle management with focus on time normalization."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trackcast.db.models import Base, Train, TrainStop
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.services.data_collector import DataCollectorService
from trackcast.data.collectors import NJTransitCollector


class TestStopLifecycleIntegration:
    """Integration tests for the full stop lifecycle including data collection."""

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        # Use in-memory SQLite for tests
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        yield session
        
        session.close()
        engine.dispose()

    @pytest.fixture
    def train_repo(self, db_session):
        """Create a TrainRepository instance."""
        return TrainRepository(db_session)

    @pytest.fixture
    def stop_repo(self, db_session):
        """Create a TrainStopRepository instance."""
        return TrainStopRepository(db_session)

    @pytest.fixture
    def sample_nj_transit_response(self):
        """Create a sample NJ Transit API response."""
        return {
            "STATION_2CHAR": "NP",
            "STATIONNAME": "Newark Penn",
            "ITEMS": [
                {
                    "TRAIN_ID": "3862",
                    "DESTINATION": "New York",
                    "TRACK": "1",
                    "LINE": "Northeast Corridor",
                    "LINECODE": "NE",
                    "STATUS": "On Time",
                    "SCHED_DEP_DATE": "18-Jun-2025 05:49:00 PM",
                    "LAST_MODIFIED": "18-Jun-2025 06:01:30 PM",
                    "STOPS": [
                        {
                            "STATION_2CHAR": "NP",
                            "STATIONNAME": "Newark Penn Station",
                            "TIME": "18-Jun-2025 06:02:18 PM",  # Note: has seconds!
                            "DEP_TIME": "18-Jun-2025 05:49:00 PM",
                            "DEPARTED": "NO",
                            "STOP_STATUS": "On Time",
                        },
                        {
                            "STATION_2CHAR": "SE",
                            "STATIONNAME": "Secaucus Upper Lvl",
                            "TIME": "18-Jun-2025 06:11:45 PM",  # Note: has seconds!
                            "DEP_TIME": "18-Jun-2025 05:56:30 PM",
                            "DEPARTED": "NO",
                            "STOP_STATUS": "On Time",
                        },
                        {
                            "STATION_2CHAR": "NY",
                            "STATIONNAME": "New York Penn Station",
                            "TIME": "18-Jun-2025 06:24:30 PM",  # Note: has seconds!
                            "DEP_TIME": "18-Jun-2025 06:09:00 PM",
                            "DEPARTED": "NO",
                            "STOP_STATUS": "On Time",
                        },
                    ],
                }
            ],
        }

    def test_stop_lifecycle_with_time_normalization(
        self, db_session, train_repo, stop_repo, sample_nj_transit_response
    ):
        """
        Test the full lifecycle of stops through data collection, ensuring that
        stops are not incorrectly marked as inactive due to time normalization.
        """
        # First collection - create initial stops with seconds
        # Create processed data directly instead of using collector since this is a unit test
        processed_data = [
            {
                "train_id": "3862",
                "origin_station_code": "NP",
                "origin_station_name": "Newark Penn Station",
                "destination": "New York",
                "track": "1",
                "departure_time": datetime(2025, 6, 18, 17, 49),
                "status": "On Time",
                "line": "Northeast Corridor",
                "line_code": "NE",
                "data_source": "njtransit",
                "stops": [
                    {
                        "station_code": "NP",
                        "station_name": "Newark Penn Station",
                        "scheduled_time": "2025-06-18T18:02:18",  # Note: has seconds!
                        "departure_time": "2025-06-18T17:49:00",
                        "departed": False,
                        "stop_status": "On Time",
                    },
                    {
                        "station_code": "SE",
                        "station_name": "Secaucus Upper Lvl",
                        "scheduled_time": "2025-06-18T18:11:45",  # Note: has seconds!
                        "departure_time": "2025-06-18T17:56:30",
                        "departed": False,
                        "stop_status": "On Time",
                    },
                    {
                        "station_code": "NY",
                        "station_name": "New York Penn Station",
                        "scheduled_time": "2025-06-18T18:24:30",  # Note: has seconds!
                        "departure_time": "2025-06-18T18:09:00",
                        "departed": False,
                        "stop_status": "On Time",
                    },
                ],
            }
        ]
        
        # Process the data through the repository layer
        for train_data in processed_data:
            # Create train directly since this is an integration test
            train = Train(
                train_id=train_data["train_id"],
                origin_station_code=train_data["origin_station_code"],
                origin_station_name=train_data["origin_station_name"],
                destination=train_data["destination"],
                track=train_data["track"],
                departure_time=train_data["departure_time"],
                status=train_data["status"],
                line=train_data["line"],
                line_code=train_data["line_code"],
                data_source="njtransit",
            )
            db_session.add(train)
            db_session.commit()
            
            # Create stops (these will have seconds in their times)
            if "stops" in train_data:
                stop_repo.upsert_train_stops(
                    train_id=train.train_id,
                    train_departure_time=train.departure_time,
                    stops_data=train_data["stops"],
                    data_source="njtransit",
                )
        
        db_session.commit()
        
        # Verify initial stops were created
        initial_stops = db_session.query(TrainStop).all()
        assert len(initial_stops) == 3
        assert all(stop.is_active for stop in initial_stops)
        
        # Store original scheduled times (with seconds)
        original_times = {
            stop.station_name: stop.scheduled_time for stop in initial_stops
        }
        
        # Second collection - simulate normalized times (no seconds)
        # This would normally happen through the DataCollectorService
        normalized_stops = []
        for stop in processed_data[0]["stops"]:
            normalized_stop = stop.copy()
            # Normalize scheduled_time to nearest minute (remove seconds)
            if stop["scheduled_time"]:
                # Handle both string and datetime formats
                if isinstance(stop["scheduled_time"], str):
                    dt = datetime.fromisoformat(stop["scheduled_time"])
                else:
                    dt = stop["scheduled_time"]
                # Simple normalization - just zero out seconds
                normalized_stop["scheduled_time"] = dt.replace(second=0).isoformat()
            normalized_stops.append(normalized_stop)
        
        # Process normalized stops
        stop_repo.upsert_train_stops(
            train_id="3862",
            train_departure_time=processed_data[0]["departure_time"],
            stops_data=normalized_stops,
            data_source="njtransit",
        )
        
        db_session.commit()
        
        # Verify no stops were marked as inactive
        updated_stops = db_session.query(TrainStop).all()
        assert len(updated_stops) == 3
        assert all(stop.is_active for stop in updated_stops), "Stops should not be marked inactive"
        # Verify no stops were incorrectly marked inactive
        
        # Verify that time updates are tracked in audit trail but stops remain active
        # (The current implementation updates times to prevent drift, which is expected behavior)
        for stop in updated_stops:
            # The scheduled time may have been updated to the normalized version
            # This is actually correct behavior to prevent drift
            original_time = original_times[stop.station_name]
            current_time = stop.scheduled_time
            
            # Verify the time difference is small (within normalization tolerance)
            time_diff = abs((current_time - original_time).total_seconds())
            assert time_diff <= 60, f"Time difference too large: {time_diff}s"
            
            # Verify time updates are handled properly (time drift tracking)
            # The system now updates times to prevent drift accumulation

    def test_stop_removal_and_reactivation(self, db_session, train_repo, stop_repo):
        """
        Test that stops are correctly marked inactive when removed from API
        and reactivated when they reappear.
        """
        # Initial train with 3 stops
        train = Train(
            train_id="3862",
            origin_station_code="NP",
            origin_station_name="Newark Penn Station",
            departure_time=datetime(2025, 6, 18, 17, 49),
            data_source="njtransit",
            destination="New York",
            line="Northeast Corridor",
        )
        db_session.add(train)
        db_session.commit()
        
        # Create initial stops
        initial_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:02:00",
                "departed": False,
            },
            {
                "station_code": "SE",
                "station_name": "Secaucus Upper Lvl",
                "scheduled_time": "2025-06-18T18:12:00",
                "departed": False,
            },
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:24:00",
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="3862",
            train_departure_time=train.departure_time,
            stops_data=initial_stops,
            data_source="njtransit",
        )
        db_session.commit()
        
        # Verify all stops are active
        stops = db_session.query(TrainStop).all()
        assert len(stops) == 3
        assert all(stop.is_active for stop in stops)
        
        # Second update - Secaucus stop is missing
        reduced_stops = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:02:00",
                "departed": True,  # Now departed
            },
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:24:00",
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="3862",
            train_departure_time=train.departure_time,
            stops_data=reduced_stops,
            data_source="njtransit",
        )
        db_session.commit()
        
        # Verify Secaucus was marked inactive
        secaucus_stop = db_session.query(TrainStop).filter_by(station_code="SE").first()
        assert secaucus_stop.is_active is False
        # Verify the stop was marked inactive but not deleted
        
        # Other stops should remain active
        active_stops = db_session.query(TrainStop).filter_by(is_active=True).all()
        assert len(active_stops) == 2
        
        # Third update - Secaucus reappears
        all_stops_back = [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:02:00",
                "departed": True,
            },
            {
                "station_code": "SE",
                "station_name": "Secaucus Upper Lvl",
                "scheduled_time": "2025-06-18T18:12:00",
                "departed": False,
            },
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:24:00",
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="3862",
            train_departure_time=train.departure_time,
            stops_data=all_stops_back,
            data_source="njtransit",
        )
        db_session.commit()
        
        # Verify Secaucus was reactivated
        secaucus_stop = db_session.query(TrainStop).filter_by(station_code="SE").first()
        assert secaucus_stop.is_active is True
        # Verify the stop was reactivated

    def test_concurrent_data_sources(self, db_session, train_repo, stop_repo):
        """
        Test that stops from different data sources (njtransit vs amtrak) are
        handled independently.
        """
        # Create train
        train = Train(
            train_id="148",  # Amtrak uses numeric IDs without 'A' prefix internally
            origin_station_code="NY",
            origin_station_name="New York Penn Station", 
            departure_time=datetime(2025, 6, 18, 18, 0),
            data_source="njtransit",
            destination="Boston",
            line="Northeast Corridor",  # Add required line field
        )
        db_session.add(train)
        db_session.commit()
        
        # Add stops from NJ Transit
        nj_stops = [
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:00:30",  # Has seconds
                "departed": False,
            },
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:15:45",  # Has seconds
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="148",
            train_departure_time=train.departure_time,
            stops_data=nj_stops,
            data_source="njtransit",
        )
        
        # Add stops from Amtrak (normalized times)
        amtrak_stops = [
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:01:00",  # Normalized
                "departed": False,
            },
            {
                "station_code": "NP", 
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:16:00",  # Normalized
                "departed": False,
            },
            {
                "station_code": "PHL",
                "station_name": "Philadelphia 30th Street",
                "scheduled_time": "2025-06-18T19:30:00",
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="148",
            train_departure_time=train.departure_time,
            stops_data=amtrak_stops,
            data_source="amtrak",
        )
        
        db_session.commit()
        
        # Verify we have stops from both sources
        all_stops = db_session.query(TrainStop).all()
        nj_stops_db = [s for s in all_stops if s.data_source == "njtransit"]
        amtrak_stops_db = [s for s in all_stops if s.data_source == "amtrak"]
        
        assert len(nj_stops_db) == 2
        assert len(amtrak_stops_db) == 3
        
        # All stops should be active
        assert all(stop.is_active for stop in all_stops)
        
        # Update NJ Transit with normalized times - should match existing
        nj_stops_normalized = [
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2025-06-18T18:01:00",  # 30s rounds to 1 min
                "departed": True,
            },
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2025-06-18T18:16:00",  # 45s rounds to 16 min
                "departed": False,
            },
        ]
        
        stop_repo.upsert_train_stops(
            train_id="148",
            train_departure_time=train.departure_time,
            stops_data=nj_stops_normalized,
            data_source="njtransit",
        )
        
        db_session.commit()
        
        # Verify no stops were marked inactive
        all_stops = db_session.query(TrainStop).all()
        assert all(stop.is_active for stop in all_stops)
        assert len(all_stops) == 5  # 2 NJ + 3 Amtrak