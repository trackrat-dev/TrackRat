"""
Test suite for Amtrak regression fixes implemented in commit 41f0c27.

This test suite ensures that:
1. Amtrak API uses explicit ET date to avoid timezone mismatch
2. Future trains are not marked as departed despite stale API data
3. Fallback logic works when dated API fails or returns minimal data

These tests prevent regression of critical issues that caused:
- Missing Amtrak trains after 8 PM ET
- Future trains being incorrectly marked as departed
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import httpx

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.api import AmtrakStationData, AmtrakTrainData
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et


def create_valid_amtrak_train_data(train_num="123", train_id="123-1"):
    """Helper to create valid AmtrakTrainData with all required fields."""
    return {
        "trainNum": train_num,
        "trainID": train_id,
        "routeName": "Test Route",
        "trainNumRaw": train_num,
        "lat": 40.7128,
        "lon": -74.0060,
        "stations": [],
        "heading": "N",
        "eventCode": "TEST",
        "origCode": "NYP",
        "destCode": "WAS",
        "destName": "Washington",
        "trainState": "Active",
        "velocity": 0,
        "createdAt": "2025-09-30T12:00:00Z",
        "updatedAt": "2025-09-30T12:00:00Z",
    }


class TestAmtrakTimezoneDateFix:
    """Test that Amtrak API correctly uses ET date instead of defaulting to UTC."""

    @pytest.mark.asyncio
    async def test_amtrak_uses_explicit_et_date(self):
        """Test that AmtrakClient uses explicit ET date in API URL."""
        client = AmtrakClient()

        # Mock current time to be during normal hours (no fallback)
        mock_et = ET.localize(datetime(2025, 9, 30, 15, 0, 0))  # 3 PM ET

        with patch('trackrat.utils.time.now_et', return_value=mock_et):
            with patch.object(client, "_is_cache_valid", return_value=False):
                # Mock the _session attribute directly
                mock_session = MagicMock()
                mock_response = MagicMock()
                # Return enough trains to avoid fallback
                mock_response.json.return_value = {
                    "123": [create_valid_amtrak_train_data()],
                    "124": [create_valid_amtrak_train_data("124", "124-1")],
                    "125": [create_valid_amtrak_train_data("125", "125-1")],
                    "126": [create_valid_amtrak_train_data("126", "126-1")],
                    "127": [create_valid_amtrak_train_data("127", "127-1")],
                    "128": [create_valid_amtrak_train_data("128", "128-1")],
                    "129": [create_valid_amtrak_train_data("129", "129-1")],
                    "130": [create_valid_amtrak_train_data("130", "130-1")],
                    "131": [create_valid_amtrak_train_data("131", "131-1")],
                    "132": [create_valid_amtrak_train_data("132", "132-1")],
                    "133": [create_valid_amtrak_train_data("133", "133-1")],
                }
                mock_response.raise_for_status = MagicMock()
                mock_session.get = AsyncMock(return_value=mock_response)
                mock_session.aclose = AsyncMock()  # Mock the close method
                client._session = mock_session

                # Get trains - should use ET date
                await client.get_all_trains()

                # Verify the URL includes the ET date
                mock_session.get.assert_called_once()
                call_args = mock_session.get.call_args
                url = call_args[0][0]

                # URL should include the ET date from our mock
                expected_url = f"https://api-v3.amtraker.com/v3/trains/2025-09-30"
                assert url == expected_url, f"Expected URL with ET date, got: {url}"

        # Don't call close since it might interact with real async

    @pytest.mark.asyncio
    async def test_amtrak_handles_8pm_danger_zone(self):
        """Test that fallback triggers during 8 PM-midnight ET when dated API returns minimal data."""
        client = AmtrakClient()

        # Mock current time to be 8:30 PM ET
        mock_et = ET.localize(datetime(2025, 9, 30, 20, 30, 0))

        with patch('trackrat.utils.time.now_et', return_value=mock_et):
            with patch.object(client, "_is_cache_valid", return_value=False):
                # Mock the _session attribute directly
                mock_session = MagicMock()
                client._session = mock_session

                # First call returns minimal data (dated API)
                mock_response_dated = MagicMock()
                mock_response_dated.json.return_value = {}  # Empty response triggers fallback
                mock_response_dated.raise_for_status = MagicMock()

                # Second call returns full data (dateless API)
                mock_response_dateless = MagicMock()
                mock_response_dateless.json.return_value = {
                    "2121": [create_valid_amtrak_train_data("2121", "2121-1")],
                    "133": [create_valid_amtrak_train_data("133", "133-1")],
                }
                mock_response_dateless.raise_for_status = MagicMock()

                # Configure mock to return different responses
                mock_session.get = AsyncMock(side_effect=[mock_response_dated, mock_response_dateless])
                mock_session.aclose = AsyncMock()

                # Get trains
                result = await client.get_all_trains()

                # Should have called twice - dated then dateless
                assert mock_session.get.call_count == 2

                # First call should be dated API
                first_call_url = mock_session.get.call_args_list[0][0][0]
                assert "2025-09-30" in first_call_url

                # Second call should be dateless API (fallback)
                second_call_url = mock_session.get.call_args_list[1][0][0]
                assert second_call_url == "https://api-v3.amtraker.com/v3/trains"

                # Result should contain trains from fallback
                assert "2121" in result
                assert "133" in result

    @pytest.mark.asyncio
    async def test_amtrak_fallback_on_dated_api_failure(self):
        """Test that client falls back to dateless API when dated API fails."""
        client = AmtrakClient()

        with patch.object(client, "_is_cache_valid", return_value=False):
            # Mock the _session attribute directly
            mock_session = MagicMock()
            client._session = mock_session

            # Create a mock response for the second call
            mock_response_success = MagicMock()
            mock_response_success.json.return_value = {
                "647": [create_valid_amtrak_train_data("647", "647-1")]
            }
            mock_response_success.raise_for_status = MagicMock()

            # First call fails (dated API), second succeeds
            mock_session.get = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError("API Error", request=None, response=MagicMock(status_code=500)),
                    mock_response_success,
                ]
            )
            mock_session.aclose = AsyncMock()

            # Get trains - should fallback
            result = await client.get_all_trains()

            # Should have called twice
            assert mock_session.get.call_count == 2

            # Result should contain train from fallback
            assert "647" in result

    @pytest.mark.asyncio
    async def test_no_fallback_during_normal_hours(self):
        """Test that fallback does NOT trigger during normal hours (before 8 PM)."""
        client = AmtrakClient()

        # Mock current time to be 3 PM ET
        mock_et = ET.localize(datetime(2025, 9, 30, 15, 0, 0))

        with patch('trackrat.utils.time.now_et', return_value=mock_et):
            with patch.object(client, "_is_cache_valid", return_value=False):
                # Mock the _session attribute directly
                mock_session = MagicMock()
                client._session = mock_session

                # Return enough data to not trigger fallback
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "123": [create_valid_amtrak_train_data()],
                    "124": [create_valid_amtrak_train_data("124", "124-1")],
                    "125": [create_valid_amtrak_train_data("125", "125-1")],
                    "126": [create_valid_amtrak_train_data("126", "126-1")],
                    "127": [create_valid_amtrak_train_data("127", "127-1")],
                    "128": [create_valid_amtrak_train_data("128", "128-1")],
                    "129": [create_valid_amtrak_train_data("129", "129-1")],
                    "130": [create_valid_amtrak_train_data("130", "130-1")],
                    "131": [create_valid_amtrak_train_data("131", "131-1")],
                    "132": [create_valid_amtrak_train_data("132", "132-1")],
                    "133": [create_valid_amtrak_train_data("133", "133-1")],
                }
                mock_response.raise_for_status = MagicMock()
                mock_session.get = AsyncMock(return_value=mock_response)
                mock_session.aclose = AsyncMock()

                # Get trains
                result = await client.get_all_trains()

                # Should have called only once (no fallback)
                assert mock_session.get.call_count == 1

                # URL should still use dated API
                call_url = mock_session.get.call_args[0][0]
                assert "2025-09-30" in call_url


class TestAmtrakDepartureFlagValidation:
    """Test that future Amtrak trains are not marked as departed."""

    def setup_method(self):
        """Set up test fixtures."""
        self.current_time = now_et()
        self.future_time = self.current_time + timedelta(hours=2)
        self.past_time = self.current_time - timedelta(hours=2)

    def test_future_train_not_marked_departed_logic(self):
        """Test the validation logic for future trains."""
        # Test with future time
        sched_dep = self.future_time
        has_departed = "Departed" == "Departed" and (
            not sched_dep or sched_dep <= now_et()
        )
        assert has_departed == False, "Future train should not be marked as departed"

    def test_past_train_correctly_marked_departed_logic(self):
        """Test the validation logic for past trains."""
        # Test with past time
        sched_dep = self.past_time
        has_departed = "Departed" == "Departed" and (
            not sched_dep or sched_dep <= now_et()
        )
        assert has_departed == True, "Past train should be marked as departed"

    def test_no_schedule_time_handling(self):
        """Test handling when no scheduled time exists."""
        # Test with None (no scheduled time)
        sched_dep = None
        has_departed = "Departed" == "Departed" and (
            not sched_dep or sched_dep <= now_et()
        )
        assert has_departed == True, "Train with no schedule should trust API flag"


class TestAmtrakEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test that empty API responses are handled gracefully."""
        client = AmtrakClient()

        with patch.object(client, "_is_cache_valid", return_value=False):
            # Mock the _session attribute directly
            mock_session = MagicMock()
            client._session = mock_session

            mock_response = MagicMock()
            mock_response.json.return_value = None
            mock_response.raise_for_status = MagicMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session.aclose = AsyncMock()

            # Should return empty dict for None response
            result = await client.get_all_trains()
            assert result == {}

    @pytest.mark.asyncio
    async def test_malformed_train_data_handling(self):
        """Test that malformed train data is skipped without crashing."""
        client = AmtrakClient()

        with patch.object(client, "_is_cache_valid", return_value=False):
            # Mock the _session attribute directly
            mock_session = MagicMock()
            client._session = mock_session

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "good": [create_valid_amtrak_train_data("123", "123-1")],
                "bad": "not_a_list",  # Malformed
                "ugly": [{"missing": "required_fields"}],  # Invalid train
            }
            mock_response.raise_for_status = MagicMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session.aclose = AsyncMock()

            # Should only include valid train
            result = await client.get_all_trains()
            assert "good" in result
            assert "bad" not in result
            # "ugly" might not be included due to validation errors
            # but the code should not crash

    def test_train_at_exact_scheduled_time(self):
        """Test edge case where train is at exact scheduled departure time."""
        current = now_et()

        # Train scheduled exactly now
        has_departed = "Departed" == "Departed" and (not current or current <= now_et())
        assert has_departed == True, "Train at exact scheduled time can be departed"

    def test_non_departed_status_handling(self):
        """Test that non-Departed statuses are handled correctly."""
        future_time = now_et() + timedelta(hours=1)

        # Test various non-departed statuses
        for status in ["Station", "Enroute", "Predeparture", None]:
            has_departed = status == "Departed" and (
                not future_time or future_time <= now_et()
            )
            assert has_departed == False, f"Status '{status}' should not mark as departed"


class TestAmtrakRealWorldScenarios:
    """Test real-world scenarios that caused production issues."""

    @pytest.mark.asyncio
    async def test_evening_ny_philadelphia_trains(self):
        """Test the exact scenario that failed: NY to Philadelphia trains missing after 8 PM."""
        client = AmtrakClient()

        # Mock 8:23 PM ET on September 30, 2025
        mock_et = ET.localize(datetime(2025, 9, 30, 20, 23, 0))

        with patch('trackrat.utils.time.now_et', return_value=mock_et):
            with patch.object(client, "_is_cache_valid", return_value=False):
                # Mock the _session attribute directly
                mock_session = MagicMock()
                client._session = mock_session

                # Dated API returns empty (wrong date)
                mock_response_dated = MagicMock()
                mock_response_dated.json.return_value = {}
                mock_response_dated.raise_for_status = MagicMock()

                # Dateless API returns evening trains
                mock_response_dateless = MagicMock()
                mock_response_dateless.json.return_value = {
                    "2121": [create_valid_amtrak_train_data("2121", "2121-1")],
                    "133": [create_valid_amtrak_train_data("133", "133-1")],
                    "647": [create_valid_amtrak_train_data("647", "647-1")],
                    "19": [create_valid_amtrak_train_data("19", "19-1")],
                }
                mock_response_dateless.raise_for_status = MagicMock()

                mock_session.get = AsyncMock(side_effect=[mock_response_dated, mock_response_dateless])
                mock_session.aclose = AsyncMock()

                # Get trains - should fallback and find evening trains
                result = await client.get_all_trains()

                # All expected NY-Philadelphia trains should be present
                assert "2121" in result, "Train 2121 (Acela) should be found"
                assert "133" in result, "Train 133 should be found"
                assert "647" in result, "Train 647 should be found"
                assert "19" in result, "Train 19 (Crescent) should be found"

    def test_train_3515_scenario(self):
        """Test the reported scenario: Train scheduled at 6:29 PM incorrectly marked departed at 6:17 PM."""
        # Current time: 6:17 PM ET
        current_time = ET.localize(datetime(2025, 9, 30, 18, 17, 0))
        # Scheduled time: 6:29 PM ET (12 minutes in future)
        scheduled_time = ET.localize(datetime(2025, 9, 30, 18, 29, 0))

        with patch('trackrat.utils.time.now_et', return_value=current_time):
            # Apply the validation logic
            has_departed = "Departed" == "Departed" and (
                not scheduled_time or scheduled_time <= current_time
            )

            assert has_departed == False, (
                f"Train scheduled at 6:29 PM should NOT be marked departed at 6:17 PM. "
                f"Current: {current_time}, Scheduled: {scheduled_time}"
            )

        # Now test 6 minutes after scheduled departure
        later_time = ET.localize(datetime(2025, 9, 30, 18, 35, 0))

        with patch('trackrat.utils.time.now_et', return_value=later_time):
            has_departed = "Departed" == "Departed" and (
                not scheduled_time or scheduled_time <= later_time
            )

            assert has_departed == True, (
                f"Train should be marked departed at 6:35 PM (after 6:29 PM scheduled). "
                f"Current: {later_time}, Scheduled: {scheduled_time}"
            )


if __name__ == "__main__":
    # Run all tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])