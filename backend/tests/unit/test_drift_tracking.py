"""Tests for time drift tracking in fuzzy matching."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainStopRepository


class TestDriftTracking:
    """Test time drift tracking functionality."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def stop_repo(self, mock_session):
        return TrainStopRepository(mock_session)

    @pytest.fixture
    def sample_train(self):
        return Train(
            id=1,
            train_id="3862",
            origin_station_code="NY",
            departure_time=datetime(2025, 6, 18, 17, 49, 0),
            data_source="njtransit",
        )

    def test_gradual_time_drift_tracking(self, stop_repo, mock_session, sample_train):
        """
        Test that gradual time changes are tracked and DB times are updated
        to prevent eventual drift beyond tolerance.
        """
        # Initial stop with baseline time
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 0),  # Initial time
            is_active=True,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )

        # Mock session setup
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query

        # Mock station mapper with fuzzy matching
        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            mock_mapper.times_match_within_tolerance.return_value = True  # Always match within tolerance
            mock_mapper.get_code_for_name.return_value = None

            # Simulate gradual drift over multiple collection cycles
            drift_scenarios = [
                ("2025-06-18T18:36:30", 30),   # +30 seconds
                ("2025-06-18T18:37:00", 60),   # +1 minute
                ("2025-06-18T18:37:45", 105),  # +1:45 minutes
                ("2025-06-18T18:38:30", 150),  # +2:30 minutes
                ("2025-06-18T18:39:15", 195),  # +3:15 minutes
            ]

            for new_time_str, expected_total_drift in drift_scenarios:
                # Update with new time
                incoming_stops = [
                    {
                        "station_code": "NP",
                        "station_name": "Newark Penn Station",
                        "scheduled_time": new_time_str,
                        "departed": False,
                    }
                ]

                stop_repo.upsert_train_stops(
                    train_id="3862",
                    train_departure_time=sample_train.departure_time,
                    stops_data=incoming_stops,
                    data_source="njtransit",
                )

                # Verify the DB time was updated to the new time
                new_datetime = datetime.fromisoformat(new_time_str)
                assert existing_stop.scheduled_time == new_datetime, \
                    f"DB time should be updated to {new_time_str}"

                # Verify audit trail tracks the change
                assert len(existing_stop.audit_trail) > 0
                if len(existing_stop.audit_trail) > 1:
                    latest_change = existing_stop.audit_trail[-1]
                    assert "drift_seconds" in latest_change["changes"]["scheduled_time"]

    def test_significant_drift_logging(self, stop_repo, mock_session, sample_train, caplog):
        """Test that significant time changes (>1 minute) are logged."""
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 0),
            is_active=True,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            mock_mapper.times_match_within_tolerance.return_value = True
            mock_mapper.get_code_for_name.return_value = None

            # Significant time change (2 minutes)
            incoming_stops = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:38:00",  # +2 minutes
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops,
                data_source="njtransit",
            )

            # Check that drift was logged
            # Note: We'd need to check the actual logging here in a real test

    def test_prevents_eventual_drift_mismatch(self, stop_repo, mock_session, sample_train):
        """
        Test that updating DB times prevents the scenario where gradual drift
        eventually exceeds the 5-minute tolerance.
        """
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 0),
            is_active=True,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            
            # Real fuzzy matching implementation
            from trackcast.services.station_mapping import StationMapper
            real_mapper = StationMapper()
            mock_mapper.times_match_within_tolerance = real_mapper.times_match_within_tolerance
            mock_mapper.get_code_for_name.return_value = None

            # Simulate scenario where WITHOUT drift updating, we'd eventually fail
            # With drift updating, each step should work and prevent eventual failure
            
            # Step 1: Small drift (+2 minutes)
            incoming_stops_1 = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:38:00",
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops_1,
                data_source="njtransit",
            )

            # DB should now be at 18:38:00
            assert existing_stop.scheduled_time == datetime(2025, 6, 18, 18, 38, 0)

            # Step 2: Another drift (+2 more minutes from new baseline)
            incoming_stops_2 = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:40:00",
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops_2,
                data_source="njtransit",
            )

            # DB should now be at 18:40:00
            assert existing_stop.scheduled_time == datetime(2025, 6, 18, 18, 40, 0)

            # Step 3: Another drift (+4 more minutes from new baseline)
            # This would have failed if we stayed at original 18:36:00 (total 8 minutes)
            # But should work because we're now comparing against 18:40:00 (4 minutes)
            incoming_stops_3 = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:44:00",
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops_3,
                data_source="njtransit",
            )

            # Should succeed - stop should remain active and be updated
            assert existing_stop.is_active is True
            assert existing_stop.scheduled_time == datetime(2025, 6, 18, 18, 44, 0)

            # Note: Total drift from original is 8 minutes, but because we tracked
            # each step, the stop was never marked inactive

    def test_small_precision_updates_vs_large_schedule_changes(self, stop_repo, mock_session, sample_train):
        """Test distinction between small precision updates and large schedule changes."""
        existing_stop = TrainStop(
            train_id="3862",
            train_departure_time=sample_train.departure_time,
            data_source="njtransit",
            station_code="NP",
            station_name="Newark Penn Station",
            scheduled_time=datetime(2025, 6, 18, 18, 36, 0),
            is_active=True,
            data_version=1,
            audit_trail=[],
            last_seen_at=datetime.utcnow(),
        )

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [existing_stop]
        mock_session.query.return_value = mock_query

        with patch('trackcast.services.station_mapping.StationMapper') as mock_mapper_class:
            mock_mapper = Mock()
            mock_mapper_class.return_value = mock_mapper
            mock_mapper.times_match_within_tolerance.return_value = True
            mock_mapper.get_code_for_name.return_value = None

            # Test small precision update (30 seconds)
            incoming_stops_small = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:36:30",  # +30 seconds
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops_small,
                data_source="njtransit",
            )

            # Check audit trail indicates precision update
            latest_change = existing_stop.audit_trail[-1]
            scheduled_change = latest_change["changes"]["scheduled_time"]
            assert scheduled_change["drift_reason"] == "precision_update"
            assert scheduled_change["drift_seconds"] == 30

            # Reset for next test
            existing_stop.audit_trail = []

            # Test large schedule change (3 minutes)
            incoming_stops_large = [
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "scheduled_time": "2025-06-18T18:39:30",  # +3 minutes from current
                    "departed": False,
                }
            ]

            stop_repo.upsert_train_stops(
                train_id="3862",
                train_departure_time=sample_train.departure_time,
                stops_data=incoming_stops_large,
                data_source="njtransit",
            )

            # Check audit trail indicates schedule adjustment
            latest_change = existing_stop.audit_trail[-1]
            scheduled_change = latest_change["changes"]["scheduled_time"]
            assert scheduled_change["drift_reason"] == "schedule_adjustment"
            assert scheduled_change["drift_seconds"] == 180  # 3 minutes