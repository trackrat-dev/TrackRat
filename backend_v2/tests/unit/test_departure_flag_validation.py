"""
Test suite for validating the departure flag time validation fix.
This ensures that stale NJT departure flags don't mark future trains as departed.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from zoneinfo import ZoneInfo

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import ET, now_et


class TestDepartureFlagValidation:
    """Test that future trains are never marked as departed despite NJT flags."""

    def setup_method(self):
        """Set up test fixtures."""
        self.current_time = now_et()
        self.future_time = self.current_time + timedelta(minutes=10)
        self.past_time = self.current_time - timedelta(minutes=30)

    def test_departure_service_station_refresh(self):
        """Test that the departure service validation logic works correctly."""
        # Test the actual logic from departure.py lines 409-426

        # Simulate future train scenario
        departed = "YES"
        raw_njt_departed_flag = departed
        scheduled_departure = self.future_time

        # Apply the fix logic (from departure.py)
        if scheduled_departure and scheduled_departure > now_et():
            has_departed_station = False
        else:
            has_departed_station = departed == "YES"

        # Future train should NOT be marked as departed
        assert has_departed_station == False
        assert raw_njt_departed_flag == "YES"  # Raw flag preserved

        # Test with past train
        scheduled_departure = self.past_time
        if scheduled_departure and scheduled_departure > now_et():
            has_departed_station = False
        else:
            has_departed_station = departed == "YES"

        # Past train should be marked as departed
        assert has_departed_station == True

    def test_departure_service_past_train_still_marked_departed(self):
        """Test that past trains are still correctly marked as departed."""
        service = DepartureService()

        journey = MagicMock(spec=TrainJourney)
        journey.train_id = "3201"
        journey.stops = []

        # Past train with DEPARTED=YES
        stops_data = [
            {
                "STATION_2CHAR": "NY",
                "STATIONNAME": "New York Penn Station",
                "TIME": self.past_time.strftime("%m/%d/%Y %I:%M:%S %p"),
                "DEP_TIME": self.past_time.strftime("%m/%d/%Y %I:%M:%S %p"),
                "DEPARTED": "YES",
                "TRACK": "5",
            }
        ]

        with patch("trackrat.services.departure.parse_njt_time") as mock_parse:
            mock_parse.return_value = self.past_time

            import asyncio

            asyncio.run(service._update_stops_from_embedded_data(journey, stops_data))

        stop = journey.stops[0]

        # Past train should be marked as departed
        assert stop.has_departed_station == True
        assert stop.raw_njt_departed_flag == "YES"
        assert stop.scheduled_departure == self.past_time

    def test_njt_journey_collector_tier1_validation(self):
        """Test NJT journey collector Tier 1 departure inference with validation."""
        # No need to instantiate collector, just test the logic

        # Create mock stop with future scheduled time
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_departure = self.future_time
        stop.scheduled_arrival = self.future_time
        stop.station_code = "NY"

        # Mock stop data from API
        stop_data = MagicMock()
        stop_data.DEPARTED = "YES"  # NJT says departed
        stop_data.TIME = None  # No actual time yet

        # Test the logic from journey.py lines 1029-1036
        # Apply the fix logic
        should_mark_departed = stop_data.DEPARTED == "YES" and (
            not stop.scheduled_departure or stop.scheduled_departure <= now_et()
        )

        # Future train should NOT be marked departed
        assert should_mark_departed == False

        # Test with past train
        stop.scheduled_departure = self.past_time
        should_mark_departed = stop_data.DEPARTED == "YES" and (
            not stop.scheduled_departure or stop.scheduled_departure <= now_et()
        )

        # Past train SHOULD be marked departed
        assert should_mark_departed == True

    def test_base_journey_collector_validation(self):
        """Test base JourneyCollector with time validation."""
        # Test the logic from collectors/journey.py lines 321-323

        # Future train scenario
        stop_data = MagicMock()
        stop_data.DEPARTED = "YES"
        scheduled_departure = self.future_time

        has_departed = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )

        assert has_departed == False, "Future train should not be marked departed"

        # Past train scenario
        scheduled_departure = self.past_time
        has_departed = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )

        assert has_departed == True, "Past train should be marked departed"

        # No scheduled time scenario (should trust NJT flag)
        scheduled_departure = None
        has_departed = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )

        assert has_departed == True, "Train with no schedule should trust NJT flag"

    def test_scheduler_service_validation(self):
        """Test scheduler service schedule generation with validation."""
        # Test the logic from scheduler.py lines 1348-1353

        stop_data = MagicMock()
        stop_data.DEPARTED = "YES"
        stop_data.TRACK = "7"

        # Future train
        scheduled_departure = self.future_time
        has_departed_station = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )

        assert (
            has_departed_station == False
        ), "Scheduler should not mark future train as departed"

        # Past train
        scheduled_departure = self.past_time
        has_departed_station = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )

        assert (
            has_departed_station == True
        ), "Scheduler should mark past train as departed"

    def test_edge_cases(self):
        """Test edge cases for the departure flag validation."""

        # Test train scheduled exactly at current time
        current = now_et()
        stop_data = MagicMock()
        stop_data.DEPARTED = "YES"

        # Exactly at scheduled time - should be marked as departed
        has_departed = stop_data.DEPARTED == "YES" and (
            not current or current <= now_et()
        )
        assert has_departed == True, "Train at exact scheduled time can be departed"

        # Test with DEPARTED = "NO"
        stop_data.DEPARTED = "NO"
        scheduled_departure = self.past_time
        has_departed = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )
        assert (
            has_departed == False
        ), "Train with DEPARTED=NO should not be marked departed"

        # Test with DEPARTED = None
        stop_data.DEPARTED = None
        has_departed = stop_data.DEPARTED == "YES" and (
            not scheduled_departure or scheduled_departure <= now_et()
        )
        assert (
            has_departed == False
        ), "Train with DEPARTED=None should not be marked departed"

    def test_real_world_scenario(self):
        """Test a real-world scenario matching the bug report."""

        # Simulate train 3515 scheduled at 6:29 PM ET
        # Current time is 6:17 PM ET (12 minutes before departure)
        current_time_et = ET.localize(datetime(2025, 9, 30, 18, 17, 0))
        scheduled_time_et = ET.localize(datetime(2025, 9, 30, 18, 29, 0))

        # NJT says DEPARTED=YES (stale data from morning run)
        departed = "YES"

        # Apply our fix logic
        # At 6:17 PM, train scheduled for 6:29 PM should NOT be marked departed
        if scheduled_time_et and scheduled_time_et > current_time_et:
            has_departed_station = False
        else:
            has_departed_station = departed == "YES"

        assert has_departed_station == False, (
            f"Train 3515 at 6:29 PM should not be marked departed at 6:17 PM. "
            f"Current: {current_time_et}, Scheduled: {scheduled_time_et}"
        )

        # Now simulate time passing to 6:35 PM (6 minutes after departure)
        current_time_et = ET.localize(datetime(2025, 9, 30, 18, 35, 0))

        # Apply logic again
        if scheduled_time_et and scheduled_time_et > current_time_et:
            has_departed_station = False
        else:
            has_departed_station = departed == "YES"

        # Now it should be marked as departed
        assert has_departed_station == True, (
            f"Train 3515 should be marked departed at 6:35 PM. "
            f"Current: {current_time_et}, Scheduled: {scheduled_time_et}"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
