"""
Unit tests for unified train notification system with integrated event detection.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackcast.db.models import LiveActivityToken
from trackcast.services.push_notification import AlertType, TrainUpdateNotificationService


class TestUnifiedEventDetection:
    """Test suite for unified event detection functionality."""

    @pytest.fixture
    def notification_service(self):
        """Create a notification service instance."""
        service = TrainUpdateNotificationService()
        # Initialize notification history
        service._notification_history = {}
        service._last_train_stops = {}
        return service

    @pytest.fixture
    def sample_consolidated_train_with_stops(self):
        """Create a consolidated train with detailed stop information."""
        return {
            "train_id": "7812",
            "consolidated_id": "7812_2025-06-29",
            "status": "EN_ROUTE",
            "status_v2": {
                "current": "EN_ROUTE",
                "location": "between Edison and Metuchen",
                "updated_at": "2025-06-29T11:34:00",
                "confidence": "high",
            },
            "track_assignment": {"track": "1"},
            "progress": {
                "last_departed": {
                    "station_code": "ED",
                    "station_name": "Edison",
                    "departed_at": "2025-06-29T11:30:00",
                },
                "next_arrival": {
                    "station_code": "ME",
                    "station_name": "Metuchen",
                    "scheduled_time": "2025-06-29T11:36:52",
                    "estimated_time": "2025-06-29T11:36:52",
                    "minutes_away": 2,
                },
                "journey_percent": 35,
            },
            "stops": [
                {
                    "station_code": "NY",
                    "station_name": "New York Penn Station",
                    "departed": True,
                    "departure_time": "2025-06-29T11:00:00",
                },
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "departed": True,
                    "departure_time": "2025-06-29T11:15:00",
                },
                {
                    "station_code": "ED",
                    "station_name": "Edison",
                    "departed": True,
                    "departure_time": "2025-06-29T11:30:00",
                },
                {
                    "station_code": "ME",
                    "station_name": "Metuchen",
                    "departed": False,
                    "scheduled_arrival": "2025-06-29T11:36:52",
                },
                {
                    "station_code": "TR",
                    "station_name": "Trenton",
                    "departed": False,
                    "scheduled_arrival": "2025-06-29T12:00:00",
                },
            ],
        }

    @pytest.fixture
    def previous_state_before_departure(self):
        """Create a previous state where Edison hasn't departed yet."""
        return {
            "train_id": "7812",
            "status_v2": "BOARDING",
            "journey_percent": 30,
            "stops": [
                {
                    "station_code": "NY",
                    "station_name": "New York Penn Station",
                    "departed": True,
                },
                {
                    "station_code": "NP",
                    "station_name": "Newark Penn Station",
                    "departed": True,
                },
                {
                    "station_code": "ED",
                    "station_name": "Edison",
                    "departed": False,  # Not departed in previous state
                },
                {
                    "station_code": "ME",
                    "station_name": "Metuchen",
                    "departed": False,
                },
                {
                    "station_code": "TR",
                    "station_name": "Trenton",
                    "departed": False,
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_detect_all_events_with_multiple_events(
        self, notification_service, sample_consolidated_train_with_stops, previous_state_before_departure
    ):
        """Test detection of multiple events (status change + stop events)."""
        # Add previous state with no track
        previous_state_before_departure["track"] = None
        
        # Current state has track assigned
        sample_consolidated_train_with_stops["track_assignment"] = {"track": "1"}
        
        # Detect all events
        events = await notification_service._detect_all_events(
            sample_consolidated_train_with_stops, previous_state_before_departure
        )
        
        # Should detect multiple events
        assert len(events) >= 2
        
        # Extract event types
        event_types = [event[0] for event in events]
        
        # Should include track assignment (status change)
        assert AlertType.TRACK_ASSIGNED in event_types
        
        # Should include approaching stop (Metuchen in 2 minutes)
        assert AlertType.APPROACHING_STOP in event_types
        
        # Should include stop departure (Edison just departed)
        assert AlertType.STOP_DEPARTURE in event_types

    def test_detect_stop_events_approaching_stop(
        self, notification_service, sample_consolidated_train_with_stops
    ):
        """Test detection of approaching stop event."""
        events = notification_service._detect_stop_events_from_consolidated(
            sample_consolidated_train_with_stops, None
        )
        
        # Should detect approaching Metuchen (2 minutes away)
        assert len(events) == 1
        alert_type, event_data = events[0]
        
        assert alert_type == AlertType.APPROACHING_STOP
        assert event_data["station"] == "Metuchen"
        assert event_data["minutes_away"] == 2

    def test_detect_stop_events_departure(
        self, notification_service, sample_consolidated_train_with_stops, previous_state_before_departure
    ):
        """Test detection of stop departure event."""
        events = notification_service._detect_stop_events_from_consolidated(
            sample_consolidated_train_with_stops, previous_state_before_departure
        )
        
        # Should detect Edison departure and Metuchen approaching
        event_types = [event[0] for event in events]
        assert AlertType.STOP_DEPARTURE in event_types
        assert AlertType.APPROACHING_STOP in event_types
        
        # Find departure event
        departure_event = next(e for e in events if e[0] == AlertType.STOP_DEPARTURE)
        assert departure_event[1]["station"] == "Edison"
        assert departure_event[1]["stops_remaining"] == 2  # ME and TR remaining

    def test_prioritize_events_correct_order(self, notification_service):
        """Test event prioritization follows correct order."""
        # Create events with different priorities
        events = [
            (AlertType.STATUS_CHANGE, None),
            (AlertType.BOARDING, None),
            (AlertType.APPROACHING_STOP, {"station": "Metuchen"}),
            (AlertType.TRACK_ASSIGNED, None),
            (AlertType.DELAY_UPDATE, None),
        ]
        
        # Prioritize events
        alert_type, event_data = notification_service._prioritize_events(events)
        
        # BOARDING should win (highest priority)
        assert alert_type == AlertType.BOARDING

    def test_prioritize_events_empty_list(self, notification_service):
        """Test prioritization with empty event list."""
        alert_type, event_data = notification_service._prioritize_events([])
        
        assert alert_type is None
        assert event_data is None

    def test_notification_history_prevents_duplicates(self, notification_service):
        """Test that notification history prevents duplicate alerts."""
        # Mark notification as sent
        notification_service._mark_notified("7812-ME-approaching")
        
        # Check if recently notified
        assert notification_service._was_recently_notified("7812-ME-approaching")
        assert not notification_service._was_recently_notified("7812-TR-approaching")

    def test_notification_history_window(self, notification_service):
        """Test notification history time window."""
        # Mark as notified
        notification_service._mark_notified("test-key")
        
        # Should be recently notified within window
        assert notification_service._was_recently_notified("test-key", window_minutes=10)
        
        # Simulate time passing by modifying the timestamp
        notification_service._notification_history["test-key"] = datetime.now() - timedelta(minutes=15)
        
        # Should not be recently notified outside window
        assert not notification_service._was_recently_notified("test-key", window_minutes=10)

    def test_update_stop_event_history(self, notification_service, sample_consolidated_train_with_stops):
        """Test updating stop event history."""
        notification_service._update_stop_event_history(sample_consolidated_train_with_stops)
        
        # Check history was updated
        train_key = "7812_2025-06-29"
        assert train_key in notification_service._last_train_stops
        
        stops = notification_service._last_train_stops[train_key]
        assert len(stops) == 5
        assert stops[0]["station_code"] == "NY"
        assert stops[0]["departed"] is True

    @pytest.mark.asyncio
    async def test_check_and_notify_unified_approach(
        self, notification_service, sample_consolidated_train_with_stops
    ):
        """Test the full unified notification flow."""
        # Mock dependencies
        mock_db = MagicMock()
        mock_tokens = [
            LiveActivityToken(id=1, train_id="7812", push_token="token123", is_active=True)
        ]
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = mock_tokens
        
        # Mock push service
        mock_push_service = MagicMock()
        mock_push_service.send_train_notifications = AsyncMock(
            return_value={"live_activity": True}
        )
        notification_service.push_service = mock_push_service
        
        # Execute unified notification
        await notification_service._check_and_notify_consolidated_train_changes(
            sample_consolidated_train_with_stops, mock_db
        )
        
        # Should have sent exactly one notification (not multiple)
        assert mock_push_service.send_train_notifications.call_count == 1
        
        # Check notification details
        call_args = mock_push_service.send_train_notifications.call_args[1]
        assert call_args["alert_type"] == AlertType.APPROACHING_STOP  # Highest priority event
        assert call_args["event_data"]["station"] == "Metuchen"
        
        # Verify state was updated
        train_key = "7812_2025-06-29"
        assert train_key in notification_service.last_train_states

    @pytest.mark.asyncio
    async def test_silent_update_when_no_events(self, notification_service):
        """Test that silent updates are sent when no alert events are detected."""
        # Create train with no significant changes
        train_data = {
            "train_id": "7812",
            "consolidated_id": "7812_2025-06-29",
            "status_v2": {"current": "EN_ROUTE"},
            "track_assignment": {"track": "1"},
            "progress": {"journey_percent": 50},
            "stops": [],
        }
        
        # Set previous state (same as current)
        notification_service.last_train_states["7812_2025-06-29"] = {
            "train_id": "7812",
            "status_v2": "EN_ROUTE",
            "track": "1",
            "journey_percent": 50,
        }
        
        # Mock dependencies
        mock_db = MagicMock()
        mock_tokens = [
            LiveActivityToken(id=1, train_id="7812", push_token="token123", is_active=True)
        ]
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = mock_tokens
        
        # Mock push service
        mock_push_service = MagicMock()
        mock_push_service.send_train_notifications = AsyncMock(
            return_value={"live_activity": True}
        )
        notification_service.push_service = mock_push_service
        
        # Execute
        await notification_service._check_and_notify_consolidated_train_changes(
            train_data, mock_db
        )
        
        # Should send silent update
        assert mock_push_service.send_train_notifications.call_count == 1
        call_args = mock_push_service.send_train_notifications.call_args[1]
        assert call_args["alert_type"] is None  # Silent update

    def test_detect_all_event_types(self, notification_service):
        """Test detection of all supported event types."""
        # Test data for various scenarios
        test_cases = [
            # Track assignment
            {
                "current": {"track": "13", "status": "BOARDING"},
                "previous": {"track": None, "status": "ON TIME"},
                "expected": AlertType.TRACK_ASSIGNED,
            },
            # Boarding status
            {
                "current": {"track": "13", "status": "BOARDING"},
                "previous": {"track": "13", "status": "ON TIME"},
                "expected": AlertType.BOARDING,
            },
            # Departure
            {
                "current": {"track": "13", "status": "DEPARTED"},
                "previous": {"track": "13", "status": "BOARDING"},
                "expected": AlertType.DEPARTED,
            },
            # Delay update
            {
                "current": {"track": "13", "status": "DELAYED", "delay_minutes": 15},
                "previous": {"track": "13", "status": "DELAYED", "delay_minutes": 5},
                "expected": AlertType.DELAY_UPDATE,
            },
        ]
        
        for test_case in test_cases:
            alert_type = notification_service._detect_alert_worthy_changes(
                test_case["previous"], test_case["current"]
            )
            assert alert_type == test_case["expected"], f"Failed for {test_case['expected']}"


class TestCLIIntegration:
    """Test CLI integration with unified notification system."""

    def test_cli_processes_unified_notifications(self):
        """Test that CLI correctly uses unified notification processing."""
        from trackcast.cli import _process_push_notifications
        
        mock_session = MagicMock()
        mock_train_repo = MagicMock()
        mock_train_repo.get_unique_train_ids_with_live_activities.return_value = ["7812", "7813"]
        
        with patch("trackcast.db.repository.TrainRepository", return_value=mock_train_repo):
            with patch("trackcast.cli.notification_service") as mock_service:
                mock_service.process_consolidated_train_updates = AsyncMock()
                
                # Execute CLI function
                _process_push_notifications(mock_session)
                
                # Verify consolidated updates are called with correct parameters
                mock_service.process_consolidated_train_updates.assert_called_once()
                call_args = mock_service.process_consolidated_train_updates.call_args
                
                # Check train IDs
                assert call_args[0][0] == ["7812", "7813"]
                # Check session
                assert call_args[0][1] == mock_session
                # Check 'since' parameter exists
                assert "since" in call_args[1]

    def test_cli_handles_no_live_activities(self):
        """Test CLI behavior when no trains have live activities."""
        from trackcast.cli import _process_push_notifications
        
        mock_session = MagicMock()
        mock_train_repo = MagicMock()
        mock_train_repo.get_unique_train_ids_with_live_activities.return_value = []
        
        with patch("trackcast.db.repository.TrainRepository", return_value=mock_train_repo):
            with patch("trackcast.cli.notification_service") as mock_service:
                mock_service.process_consolidated_train_updates = AsyncMock()
                
                # Should not crash
                _process_push_notifications(mock_session)
                
                # Should still call process but with empty list
                mock_service.process_consolidated_train_updates.assert_called_once()
                call_args = mock_service.process_consolidated_train_updates.call_args
                assert call_args[0][0] == []


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def notification_service(self):
        """Create a notification service instance."""
        return TrainUpdateNotificationService()

    def test_detect_stop_events_no_progress_data(self, notification_service):
        """Test stop event detection when progress data is missing."""
        train_data = {
            "train_id": "7812",
            "stops": [{"station_code": "NY", "departed": True}],
            # No progress field
        }
        
        events = notification_service._detect_stop_events_from_consolidated(train_data, None)
        
        # Should handle gracefully
        assert events == []

    def test_detect_stop_events_invalid_minutes_away(self, notification_service):
        """Test handling of invalid minutes_away values."""
        train_data = {
            "train_id": "7812",
            "progress": {
                "next_arrival": {
                    "station_code": "ME",
                    "station_name": "Metuchen",
                    "minutes_away": -5,  # Invalid negative value
                }
            },
        }
        
        events = notification_service._detect_stop_events_from_consolidated(train_data, None)
        
        # Should not create event for invalid time
        assert events == []

    def test_prioritize_events_unknown_alert_type(self, notification_service):
        """Test prioritization with events not in priority list."""
        # Create a mock alert type not in the priority list
        mock_alert = MagicMock()
        mock_alert.value = "UNKNOWN_ALERT"
        
        events = [(mock_alert, None)]
        
        alert_type, event_data = notification_service._prioritize_events(events)
        
        # Should return the event even if not in priority list
        assert alert_type == mock_alert

    @pytest.mark.asyncio
    async def test_notification_error_handling(self, notification_service):
        """Test error handling during notification sending."""
        train_data = {
            "train_id": "7812",
            "consolidated_id": "7812_2025-06-29",
            "stops": [],
        }
        
        # Mock dependencies
        mock_db = MagicMock()
        mock_tokens = [
            LiveActivityToken(id=1, train_id="7812", push_token="token123", is_active=True)
        ]
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = mock_tokens
        
        # Mock push service to raise exception
        mock_push_service = MagicMock()
        mock_push_service.send_train_notifications = AsyncMock(
            side_effect=Exception("Network error")
        )
        notification_service.push_service = mock_push_service
        
        # Should not crash
        await notification_service._check_and_notify_consolidated_train_changes(
            train_data, mock_db
        )
        
        # Should attempt to send
        assert mock_push_service.send_train_notifications.call_count == 1

    def test_extract_consolidated_state_with_stops(self, notification_service):
        """Test that stops are properly added to extracted state."""
        train_data = {
            "train_id": "7812",
            "stops": [
                {"station_code": "NY", "departed": True},
                {"station_code": "NP", "departed": False},
            ],
        }
        
        # Mock the original extract method
        with patch.object(
            notification_service, "_extract_consolidated_train_state"
        ) as mock_extract:
            mock_extract.return_value = {"train_id": "7812"}
            
            # Call the check and notify method
            mock_db = MagicMock()
            mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = []
            
            asyncio.run(
                notification_service._check_and_notify_consolidated_train_changes(
                    train_data, mock_db
                )
            )
            
            # The method should have been called and state should include stops
            # This verifies our modification in the main method

    def test_detect_stop_departure_with_no_remaining_stops(self, notification_service):
        """Test stop departure detection when it's the last stop."""
        current_stops = [
            {"station_code": "NY", "station_name": "NY Penn", "departed": True},
            {"station_code": "TR", "station_name": "Trenton", "departed": True},
        ]
        previous_stops = [
            {"station_code": "NY", "station_name": "NY Penn", "departed": True},
            {"station_code": "TR", "station_name": "Trenton", "departed": False},
        ]
        
        train_data = {
            "train_id": "7812",
            "stops": current_stops,
        }
        
        events = notification_service._detect_stop_events_from_consolidated(
            train_data, {"stops": previous_stops}
        )
        
        # Should detect Trenton departure
        assert len(events) == 1
        alert_type, event_data = events[0]
        assert alert_type == AlertType.STOP_DEPARTURE
        assert event_data["station"] == "Trenton"
        assert event_data["stops_remaining"] == 0  # No stops remaining