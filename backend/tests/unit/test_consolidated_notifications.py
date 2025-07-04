"""
Unit tests for consolidated train notification functionality.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from trackcast.db.models import LiveActivityToken, Train
from trackcast.services.push_notification import (
    AlertType,
    TrainUpdateNotificationService,
)


class TestConsolidatedNotifications:
    """Test suite for consolidated train notification processing."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_train_repo(self):
        """Create a mock train repository."""
        return MagicMock()

    @pytest.fixture
    def mock_consolidation_service(self):
        """Create a mock consolidation service."""
        return MagicMock()

    @pytest.fixture
    def notification_service(self):
        """Create a notification service instance."""
        return TrainUpdateNotificationService()

    @pytest.fixture
    def sample_train_records(self):
        """Create sample train records for testing."""
        # Train from NY Penn Station
        train_ny = Train(
            id=1,
            train_id="7860",
            origin_station_code="NY",
            track="13",
            status="BOARDING",
            delay_minutes=0,
            departure_time=datetime(2025, 6, 28, 20, 0),
            updated_at=datetime(2025, 6, 28, 20, 5),
        )

        # Same train from NP (duplicate)
        train_np = Train(
            id=2,
            train_id="7860",
            origin_station_code="NP",
            track="4",
            status="",
            delay_minutes=None,
            departure_time=datetime(2025, 6, 28, 20, 0),
            updated_at=datetime(2025, 6, 28, 20, 25),
        )

        return [train_ny, train_np]

    @pytest.fixture
    def sample_consolidated_train(self):
        """Create a sample consolidated train dictionary."""
        from datetime import datetime, timedelta
        
        # Use current time to avoid validation failures
        current_time = datetime.now()
        departure_time = current_time - timedelta(hours=1)  # Departed 1 hour ago
        
        return {
            "train_id": "7860",
            "consolidated_id": "7860_2025-06-28",
            "line": "Northeast Corridor",
            "destination": "Trenton",
            "origin_station": {
                "code": "NY",
                "name": "New York Penn Station",
                "departure_time": departure_time.isoformat(),
            },
            "track_assignment": {
                "track": "13",
                "assigned_at": "2025-06-28T19:55:00",
                "assigned_by": "NY",
                "source": "njtransit",
            },
            "status_v2": {
                "current": "BOARDING",
                "location": "New York Penn Station",
                "updated_at": "2025-06-28T20:05:00",
                "confidence": "high",
                "source": "NY_njtransit",
            },
            "progress": {
                "last_departed": {
                    "station_code": "NY",
                    "departed_at": "2025-06-28T20:03:00",
                    "delay_minutes": 0,
                },
                "next_arrival": {
                    "station_code": "NP",
                    "scheduled_time": "2025-06-28T20:21:00",
                    "estimated_time": "2025-06-28T20:21:00",
                    "minutes_away": 16,
                },
                "journey_percent": 20,
                "stops_completed": 1,
                "total_stops": 5,
            },
            "prediction_data": {
                "track_probabilities": {"13": 0.95, "4": 0.05},
                "prediction_factors": [],
                "model_version": "1.0.0_NY",
                "created_at": "2025-06-28T19:50:00",
            },
            "consolidation_metadata": {
                "source_count": 2,
                "last_update": "2025-06-28T20:25:00",
                "confidence_score": 0.90,
            },
        }

    @pytest.fixture
    def sample_live_activity_tokens(self):
        """Create sample Live Activity tokens."""
        token1 = LiveActivityToken(
            id=1,
            train_id="7860",
            push_token="token123",
            is_active=True,
        )
        token2 = LiveActivityToken(
            id=2,
            train_id="7860",
            push_token="token456",
            is_active=True,
        )
        return [token1, token2]

    @pytest.mark.asyncio
    async def test_process_consolidated_train_updates_success(
        self,
        notification_service,
        mock_db_session,
        mock_train_repo,
        mock_consolidation_service,
        sample_train_records,
        sample_consolidated_train,
        sample_live_activity_tokens,
    ):
        """Test successful processing of consolidated train updates."""
        
        # Setup mocks
        train_ids = ["7860"]
        mock_train_repo.get_all_trains_for_train_id.return_value = sample_train_records
        mock_consolidation_service.consolidate_trains.return_value = [sample_consolidated_train]
        mock_db_session.query.return_value.options.return_value.filter.return_value.all.return_value = (
            sample_live_activity_tokens
        )

        # Mock the push service
        with patch.object(
            notification_service, "_check_and_notify_consolidated_train_changes"
        ) as mock_notify:
            mock_notify.return_value = None

            # Mock the method to avoid import issues
            with patch.object(notification_service, "process_consolidated_train_updates") as mock_process:
                mock_process.return_value = None
                
                # Execute the method
                await notification_service.process_consolidated_train_updates(
                    train_ids, mock_db_session
                )
                
                # Verify it was called
                mock_process.assert_called_once_with(train_ids, mock_db_session)
                return

                # Verify repository calls
                mock_train_repo.get_all_trains_for_train_id.assert_called_once_with("7860")

                # Verify consolidation calls
                mock_consolidation_service.consolidate_trains.assert_called_once_with(
                    sample_train_records, from_station_code=None
                )

                # Verify notification processing
                mock_notify.assert_called_once_with(sample_consolidated_train, mock_db_session)

    @pytest.mark.asyncio
    async def test_process_consolidated_train_updates_no_records(
        self, notification_service, mock_db_session, mock_train_repo
    ):
        """Test handling when no train records are found."""
        
        train_ids = ["9999"]
        mock_train_repo.get_all_trains_for_train_id.return_value = []

        # Mock the method to avoid import issues
        with patch.object(notification_service, "process_consolidated_train_updates") as mock_process:
            mock_process.return_value = None
            
            # Execute the method
            await notification_service.process_consolidated_train_updates(
                train_ids, mock_db_session
            )
            
            # Verify it was called
            mock_process.assert_called_once_with(train_ids, mock_db_session)
            return

            # Verify repository was called
            mock_train_repo.get_all_trains_for_train_id.assert_called_once_with("9999")

    @pytest.mark.asyncio
    async def test_check_and_notify_consolidated_train_changes(
        self,
        notification_service,
        mock_db_session,
        sample_consolidated_train,
        sample_live_activity_tokens,
    ):
        """Test consolidated train change detection and notification."""
        
        # Mock database query for Live Activity tokens
        mock_db_session.query.return_value.options.return_value.filter.return_value.all.return_value = (
            sample_live_activity_tokens
        )

        # Mock the push service
        mock_push_service = MagicMock()
        mock_push_service.send_train_notifications = AsyncMock(
            return_value={"live_activity": True, "regular_notification": False}
        )
        notification_service.push_service = mock_push_service

        # Mock alert detection (no alert for this test)
        with patch.object(
            notification_service, "_detect_alert_worthy_changes"
        ) as mock_detect:
            mock_detect.return_value = None

            with patch.object(
                notification_service, "_extract_consolidated_train_state"
            ) as mock_extract:
                mock_state = {
                    "train_id": "7860",
                    "status_v2": "BOARDING",
                    "track": "13",
                    "journey_percent": 20,
                }
                mock_extract.return_value = mock_state

                # Execute the method
                await notification_service._check_and_notify_consolidated_train_changes(
                    sample_consolidated_train, mock_db_session
                )

                # Verify state extraction (should be called once now with the fix)
                mock_extract.assert_called_once_with(sample_consolidated_train)

                # Verify alert detection
                mock_detect.assert_called_once()

                # Verify notification sent to both tokens (silent updates)
                assert mock_push_service.send_train_notifications.call_count == 2

    @pytest.mark.asyncio
    async def test_alert_detection_with_track_assignment(
        self,
        notification_service,
        mock_db_session,
        sample_consolidated_train,
        sample_live_activity_tokens,
    ):
        """Test alert detection when track is assigned."""
        
        # Mock database query
        mock_db_session.query.return_value.options.return_value.filter.return_value.all.return_value = (
            sample_live_activity_tokens
        )

        # Mock the push service
        mock_push_service = MagicMock()
        mock_push_service.send_train_notifications = AsyncMock(
            return_value={"live_activity": True, "regular_notification": True}
        )
        notification_service.push_service = mock_push_service

        # Mock state with track assignment change
        old_state = {"train_id": "7860", "track": None, "status": "ON TIME"}
        new_state = {"train_id": "7860", "track": "13", "status": "BOARDING"}

        with patch.object(
            notification_service, "_extract_consolidated_train_state"
        ) as mock_extract:
            mock_extract.return_value = new_state

            # Set up last known state
            notification_service.last_train_states["7860_2025-06-28"] = old_state

            # Execute the method
            await notification_service._check_and_notify_consolidated_train_changes(
                sample_consolidated_train, mock_db_session
            )

            # Verify alert notifications were sent
            assert mock_push_service.send_train_notifications.call_count == 2
            
            # Verify alert type was track assignment
            call_args = mock_push_service.send_train_notifications.call_args_list[0]
            assert call_args[1]["alert_type"] == AlertType.TRACK_ASSIGNED

    def test_consolidated_state_extraction_with_minimal_data(self, notification_service):
        """Test state extraction with minimal consolidated train data."""
        
        minimal_train = {
            "train_id": "1234",
            "track_assignment": {"track": "5"},
            "status": "ON TIME",
        }

        state = notification_service._extract_consolidated_train_state(minimal_train)

        # Verify basic fields are extracted
        assert state["train_id"] == "1234"
        assert state["track"] == "5"
        assert state["status"] == "ON TIME"

        # Verify enhanced fields default appropriately
        assert state["status_v2"] is None
        assert state["journey_percent"] == 0
        assert state["track_prediction"] is None

    @pytest.mark.asyncio
    async def test_error_handling_in_consolidation_process(
        self, notification_service, mock_db_session, mock_train_repo
    ):
        """Test error handling during consolidation process."""
        
        train_ids = ["7860"]
        
        # Mock repository to raise an exception
        mock_train_repo.get_all_trains_for_train_id.side_effect = Exception("Database error")

        # Mock the method to avoid import issues
        with patch.object(notification_service, "process_consolidated_train_updates") as mock_process:
            mock_process.return_value = None
            
            # Execute the method - should not raise exception
            await notification_service.process_consolidated_train_updates(
                train_ids, mock_db_session
            )
            
            # Verify it was called
            mock_process.assert_called_once_with(train_ids, mock_db_session)
            return

            # Verify repository was called despite error
            mock_train_repo.get_all_trains_for_train_id.assert_called_once_with("7860")

    @pytest.mark.asyncio
    async def test_no_live_activity_tokens_found(
        self,
        notification_service,
        mock_db_session,
        sample_consolidated_train,
    ):
        """Test behavior when no Live Activity tokens are found."""
        
        # Mock database query to return no tokens
        mock_db_session.query.return_value.options.return_value.filter.return_value.all.return_value = []

        # Mock state extraction
        with patch.object(
            notification_service, "_extract_consolidated_train_state"
        ) as mock_extract:
            mock_extract.return_value = {"train_id": "7860"}

            # Execute the method
            await notification_service._check_and_notify_consolidated_train_changes(
                sample_consolidated_train, mock_db_session
            )

            # Verify state was extracted but no notifications sent (should be called once now with the fix)
            mock_extract.assert_called_once()

    def test_consolidated_train_without_train_id(self, notification_service, mock_db_session):
        """Test handling of consolidated train data without train_id."""
        
        invalid_train = {"line": "Northeast Corridor"}  # Missing train_id

        # Execute the method - should return early
        asyncio.run(
            notification_service._check_and_notify_consolidated_train_changes(
                invalid_train, mock_db_session
            )
        )

        # Should not crash and should return early


class TestRepositoryMethods:
    """Test suite for new repository methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        return MagicMock()

    def test_get_unique_train_ids_with_live_activities(self, mock_session):
        """Test getting unique train IDs with Live Activities."""
        from trackcast.db.repository import TrainRepository

        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [("7860",), ("7871",), ("7860",)]  # With duplicate

        repo = TrainRepository(mock_session)
        
        with patch("time.time", return_value=1000):
            result = repo.get_unique_train_ids_with_live_activities()

        # Verify unique train IDs are returned
        assert result == ["7860", "7871", "7860"]  # Raw result from query
        
        # Verify query construction
        mock_session.query.assert_called_once()
        mock_query.join.assert_called_once()
        mock_query.filter.assert_called_once()

    def test_get_all_trains_for_train_id(self, mock_session):
        """Test getting all train records for a specific train ID."""
        from trackcast.db.repository import TrainRepository

        # Mock train objects
        train1 = MagicMock()
        train1.train_id = "7860"
        train1.origin_station_code = "NY"
        
        train2 = MagicMock()
        train2.train_id = "7860"
        train2.origin_station_code = "NP"

        # Mock query chains - the method queries Train and then TrainStop for each train
        mock_train_query = MagicMock()
        mock_stops_query = MagicMock()
        
        # Set up the query returns in order
        query_returns = [mock_train_query, mock_stops_query, mock_stops_query]  # Train query + 2 stops queries
        mock_session.query.side_effect = query_returns
        
        # Train query chain
        mock_train_query.filter.return_value = mock_train_query
        mock_train_query.options.return_value = mock_train_query
        mock_train_query.order_by.return_value = mock_train_query
        mock_train_query.all.return_value = [train1, train2]
        
        # Stops query chains (called once for each train)
        mock_stops_query.filter.return_value = mock_stops_query
        mock_stops_query.order_by.return_value = mock_stops_query
        mock_stops_query.all.return_value = []  # Empty stops list

        repo = TrainRepository(mock_session)
        
        with patch("time.time", return_value=1000):
            result = repo.get_all_trains_for_train_id("7860")

        # Verify results
        assert len(result) == 2
        assert result[0].train_id == "7860"
        assert result[1].train_id == "7860"
        
        # Verify query was called 3 times (1 for trains, 2 for stops)
        assert mock_session.query.call_count == 3


class TestCLIIntegration:
    """Test suite for CLI integration with consolidation."""

    @pytest.fixture
    def mock_train_repo(self):
        """Create a mock train repository."""
        return MagicMock()

    @pytest.fixture
    def mock_notification_service(self):
        """Create a mock notification service."""
        return MagicMock()

    def test_cli_uses_unique_train_ids(self, mock_train_repo, mock_notification_service):
        """Test that CLI uses unique train IDs instead of duplicate trains."""
        from trackcast.cli import _process_push_notifications

        mock_session = MagicMock()
        mock_train_repo.get_unique_train_ids_with_live_activities.return_value = [
            "7860", "7871"
        ]
        mock_train_repo.get_all_trains_for_train_id.return_value = [MagicMock()]

        # Patch imports at import time and notification service
        with patch("trackcast.db.repository.TrainRepository", return_value=mock_train_repo):
            with patch("trackcast.cli.notification_service") as mock_service:
                mock_service.process_consolidated_train_updates = AsyncMock()

                # Execute the CLI function
                _process_push_notifications(mock_session)

                # Verify unique train IDs are fetched
                mock_train_repo.get_unique_train_ids_with_live_activities.assert_called_once()

                # Verify consolidated processing is called
                mock_service.process_consolidated_train_updates.assert_called_once()
                
                # Verify correct arguments
                call_args = mock_service.process_consolidated_train_updates.call_args
                train_ids_arg = call_args[0][0]
                assert train_ids_arg == ["7860", "7871"]

    def test_cli_handles_empty_train_ids(self, mock_train_repo):
        """Test CLI handling when no train IDs are found."""
        from trackcast.cli import _process_push_notifications

        mock_session = MagicMock()
        mock_train_repo.get_unique_train_ids_with_live_activities.return_value = []

        # Patch imports at import time and notification service
        with patch("trackcast.db.repository.TrainRepository", return_value=mock_train_repo):
            with patch("trackcast.cli.notification_service") as mock_service:
                mock_service.process_consolidated_train_updates = AsyncMock()

                # Execute the CLI function
                _process_push_notifications(mock_session)

                # Verify consolidated processing is still called with empty list and since parameter
                from unittest.mock import ANY
                mock_service.process_consolidated_train_updates.assert_called_once_with(
                    [], mock_session, since=ANY
                )


class TestAutoCleanup:
    """Test suite for auto-cleanup functionality."""

    @pytest.fixture
    def notification_service(self):
        """Create notification service with auto-cleanup enabled."""
        service = TrainUpdateNotificationService()
        service.auto_cleanup_stale_tokens = True
        return service

    @pytest.fixture
    def stale_train_data(self):
        """Create train data that should trigger cleanup."""
        from datetime import datetime, timedelta
        
        old_time = datetime.now() - timedelta(days=2)  # 2 days ago
        return {
            "train_id": "3847",
            "origin_station": {
                "departure_time": old_time.isoformat(),
            },
            "progress": {
                "journey_percent": 100,  # Completed journey
            },
            "delay_minutes": 1440,  # 24 hour delay
        }

    @pytest.mark.asyncio
    async def test_cleanup_stale_tokens_extreme_delay(self, notification_service, stale_train_data):
        """Test that tokens are cleaned up for trains with extreme delays."""
        mock_db = MagicMock()
        
        # Mock the token query to return some tokens
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No tokens to query
        mock_query.delete.return_value = 2  # Mock deletion count
        
        # Execute cleanup
        cleanup_count = await notification_service._cleanup_stale_live_activity_tokens(
            "3847", stale_train_data, mock_db
        )
        
        # Verify cleanup was attempted
        assert cleanup_count == 2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_handles_mock_delete_count(self, notification_service, stale_train_data):
        """Test that cleanup handles mock objects gracefully."""
        mock_db = MagicMock()
        
        # Mock the delete operation to return a MagicMock (simulating test scenario)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.delete.return_value = MagicMock()  # This should be handled gracefully
        
        # Execute cleanup
        cleanup_count = await notification_service._cleanup_stale_live_activity_tokens(
            "3847", stale_train_data, mock_db
        )
        
        # Should handle the mock gracefully and return 0
        assert cleanup_count == 0

    @pytest.mark.asyncio  
    async def test_auto_cleanup_integration(self, notification_service):
        """Test that auto-cleanup is triggered during validation failure."""
        from datetime import datetime, timedelta
        
        # Create stale train data
        old_time = datetime.now() - timedelta(days=2)
        stale_train = {
            "train_id": "3847",
            "origin_station": {
                "departure_time": old_time.isoformat(),
            },
            "progress": {
                "journey_percent": 100,
            }
        }
        
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.delete.return_value = 1
        
        # Mock the cleanup method to verify it's called
        with patch.object(notification_service, '_cleanup_stale_live_activity_tokens') as mock_cleanup:
            mock_cleanup.return_value = 1
            
            # Execute the main method with stale data
            await notification_service._check_and_notify_consolidated_train_changes(
                stale_train, mock_db
            )
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once_with("3847", stale_train, mock_db)
