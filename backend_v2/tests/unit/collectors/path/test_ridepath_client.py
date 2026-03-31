"""
Unit tests for RidePathClient.

Tests the native PATH RidePATH API client for real-time arrival data.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from trackrat.collectors.path.ridepath_client import (
    PathArrival,
    RidePathClient,
    RIDEPATH_API_URL,
)


class TestRidePathClient:
    """Tests for RidePathClient."""

    @pytest.fixture
    def client(self):
        """Create a RidePathClient for testing."""
        return RidePathClient(timeout=10.0)

    @pytest.fixture
    def sample_api_response(self):
        """Sample response from the RidePATH API."""
        return {
            "results": [
                {
                    "consideredStation": "JSQ",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "World Trade Center",
                                    "arrivalTimeMessage": "4 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "8 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "4D92FB",
                                },
                            ],
                        },
                        {
                            "label": "ToNJ",
                            "messages": [
                                {
                                    "headSign": "Newark",
                                    "arrivalTimeMessage": "2 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                            ],
                        },
                    ],
                },
                {
                    "consideredStation": "WTC",
                    "destinations": [
                        {
                            "label": "ToNJ",
                            "messages": [
                                {
                                    "headSign": "Newark",
                                    "arrivalTimeMessage": "10 min",
                                    "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
                                    "lineColor": "D93A30",
                                },
                            ],
                        },
                    ],
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_get_all_arrivals_success(self, client, sample_api_response):
        """Test successful fetch of all arrivals."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 4  # 3 from JSQ + 1 from WTC
        assert all(isinstance(a, PathArrival) for a in arrivals)

        # Check JSQ -> WTC arrival
        wtc_arrivals = [a for a in arrivals if a.headsign == "World Trade Center"]
        assert len(wtc_arrivals) == 1
        assert wtc_arrivals[0].station_code == "PJS"  # Journal Square
        assert wtc_arrivals[0].minutes_away == 4
        assert wtc_arrivals[0].direction == "ToNY"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_with_cache(self, client, sample_api_response):
        """Test that caching prevents redundant API calls."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        # First call - should hit API
        arrivals1 = await client.get_all_arrivals()

        # Second call - should use cache
        arrivals2 = await client.get_all_arrivals()

        # API should only be called once
        assert mock_session.get.call_count == 1
        assert arrivals1 == arrivals2

    @pytest.mark.asyncio
    async def test_get_all_arrivals_cache_expiry(self, client, sample_api_response):
        """Test that cache expires after TTL."""
        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        # First call
        await client.get_all_arrivals()

        # Expire cache
        client._cache_time = datetime.now() - timedelta(seconds=60)

        # Second call - should hit API again
        await client.get_all_arrivals()

        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error(self, client):
        """Test handling of HTTP errors."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=AsyncMock(),
                response=AsyncMock(status_code=500),
            )
        )
        client._session = mock_session

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_all_arrivals()

    @pytest.mark.asyncio
    async def test_get_all_arrivals_unknown_station(self, client):
        """Test that unknown station codes are skipped gracefully."""
        response_data = {
            "results": [
                {
                    "consideredStation": "UNKNOWN",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "Test",
                                    "arrivalTimeMessage": "5 min",
                                    "lastUpdated": "2026-01-19T07:00:00-05:00",
                                    "lineColor": "000000",
                                },
                            ],
                        },
                    ],
                },
            ]
        }

        # Mock response - json() and raise_for_status() are sync in httpx
        mock_response = MagicMock()
        mock_response.json.return_value = response_data

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 0  # Unknown station skipped

    def test_parse_minutes_valid(self, client):
        """Test parsing various minute formats."""
        assert client._parse_minutes("14 min") == 14
        assert client._parse_minutes("1 min") == 1
        assert client._parse_minutes("0 min") == 0

    def test_parse_minutes_arriving(self, client):
        """Test parsing 'Arriving' message."""
        assert client._parse_minutes("Arriving") == 0
        assert client._parse_minutes("arriving now") == 0

    def test_parse_minutes_invalid(self, client):
        """Test parsing invalid formats returns None."""
        assert client._parse_minutes("") is None
        assert client._parse_minutes("invalid") is None
        assert client._parse_minutes(None) is None

    def test_parse_timestamp_valid(self, client):
        """Test parsing valid ISO timestamps."""
        ts = client._parse_timestamp("2026-01-19T07:36:57.674251-05:00")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 1
        assert ts.day == 19

    def test_parse_timestamp_invalid(self, client):
        """Test parsing invalid timestamps returns None."""
        assert client._parse_timestamp("") is None
        assert client._parse_timestamp("invalid") is None
        assert client._parse_timestamp(None) is None

    def test_clear_cache(self, client):
        """Test cache clearing."""
        client._cache = [
            PathArrival(
                station_code="PJS",
                headsign="Test",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now(),
                line_color="000000",
                last_updated=None,
            )
        ]
        client._cache_time = datetime.now()

        client.clear_cache()

        assert client._cache is None
        assert client._cache_time is None

    def test_arrival_time_uses_last_updated_baseline(self, client):
        """Test that arrival_time is computed from lastUpdated, not now.

        The RidePATH API's "X min" countdown is relative to when the prediction
        was generated (lastUpdated). Using now instead of lastUpdated inflates
        arrival times by the lag between the two.
        """
        from trackrat.utils.time import now_et

        now = now_et()
        # lastUpdated is 2 minutes behind now (typical API lag)
        last_updated_time = now - timedelta(minutes=2)
        last_updated_str = last_updated_time.isoformat()

        msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lastUpdated": last_updated_str,
            "lineColor": "D93A30",
        }

        arrival = client._parse_arrival_message("PJS", "ToNY", msg, now)

        assert arrival is not None
        # arrival_time should be lastUpdated + 10 min, NOT now + 10 min
        expected = last_updated_time + timedelta(minutes=10)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"arrival_time should be based on lastUpdated, not now. "
            f"Expected ~{expected}, got {arrival.arrival_time} (delta {delta}s)"
        )
        # Verify it's about 2 minutes earlier than the old (now-based) computation
        now_based = now + timedelta(minutes=10)
        offset = (now_based - arrival.arrival_time).total_seconds()
        assert (
            115 < offset < 125
        ), f"arrival_time should be ~120s earlier than now+10min, got {offset}s"

    def test_arrival_time_falls_back_to_now_when_no_last_updated(self, client):
        """Test fallback to now when lastUpdated is missing."""
        from trackrat.utils.time import now_et

        now = now_et()
        msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lineColor": "D93A30",
            # No lastUpdated field
        }

        arrival = client._parse_arrival_message("PJS", "ToNY", msg, now)

        assert arrival is not None
        expected = now + timedelta(minutes=10)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"Without lastUpdated, arrival_time should use now. "
            f"Expected ~{expected}, got {arrival.arrival_time}"
        )

    def test_arrival_time_falls_back_to_now_when_last_updated_stale(self, client):
        """Test fallback to now when lastUpdated is too stale (>5 minutes)."""
        from trackrat.utils.time import now_et

        now = now_et()
        # lastUpdated is 6 minutes behind — too stale to trust
        stale_time = now - timedelta(minutes=6)
        msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lastUpdated": stale_time.isoformat(),
            "lineColor": "D93A30",
        }

        arrival = client._parse_arrival_message("PJS", "ToNY", msg, now)

        assert arrival is not None
        expected = now + timedelta(minutes=10)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"With stale lastUpdated (>5min), should fall back to now. "
            f"Expected ~{expected}, got {arrival.arrival_time}"
        )

    def test_arrival_time_falls_back_to_now_when_last_updated_in_future(self, client):
        """Test fallback to now when lastUpdated is in the future (clock skew)."""
        from trackrat.utils.time import now_et

        now = now_et()
        # lastUpdated is 30 seconds in the future — clock skew
        future_time = now + timedelta(seconds=30)
        msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lastUpdated": future_time.isoformat(),
            "lineColor": "D93A30",
        }

        arrival = client._parse_arrival_message("PJS", "ToNY", msg, now)

        assert arrival is not None
        expected = now + timedelta(minutes=10)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"With future lastUpdated (clock skew), should fall back to now. "
            f"Expected ~{expected}, got {arrival.arrival_time}"
        )

    def test_arrival_time_with_recent_last_updated(self, client):
        """Test that a very recent lastUpdated (few seconds) is used."""
        from trackrat.utils.time import now_et

        now = now_et()
        # lastUpdated is 5 seconds behind — very fresh, should use it
        recent_time = now - timedelta(seconds=5)
        msg = {
            "headSign": "33rd Street",
            "arrivalTimeMessage": "3 min",
            "lastUpdated": recent_time.isoformat(),
            "lineColor": "4D92FB",
        }

        arrival = client._parse_arrival_message("PHO", "ToNY", msg, now)

        assert arrival is not None
        expected = recent_time + timedelta(minutes=3)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"With fresh lastUpdated, arrival_time should use it. "
            f"Expected ~{expected}, got {arrival.arrival_time}"
        )

    def test_arrival_time_timezone_consistency(self, client):
        """Regression: arrival_time must always have pytz ET timezone.

        When baseline is lastUpdated (parsed via fromisoformat with stdlib tz),
        the result must still be normalized to pytz ET — not carry a stdlib
        fixed-offset timezone. This prevents downstream timezone mismatches.
        """
        import pytz
        from trackrat.utils.time import ET, now_et

        now = now_et()

        # Case 1: lastUpdated used (fresh) — result must be pytz ET
        fresh_msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "5 min",
            "lastUpdated": (now - timedelta(seconds=30)).isoformat(),
            "lineColor": "D93A30",
        }
        arrival_fresh = client._parse_arrival_message("PJS", "ToNY", fresh_msg, now)
        assert arrival_fresh is not None
        assert arrival_fresh.arrival_time.tzinfo is not None
        # pytz timezones have a .zone attribute; stdlib fixed-offset does not
        assert hasattr(
            arrival_fresh.arrival_time.tzinfo, "zone"
        ), f"arrival_time should have pytz timezone, got {type(arrival_fresh.arrival_time.tzinfo)}"

        # Case 2: no lastUpdated (fallback to now) — result must also be pytz ET
        no_lu_msg = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "5 min",
            "lineColor": "D93A30",
        }
        arrival_no_lu = client._parse_arrival_message("PJS", "ToNY", no_lu_msg, now)
        assert arrival_no_lu is not None
        assert hasattr(
            arrival_no_lu.arrival_time.tzinfo, "zone"
        ), f"arrival_time should have pytz timezone, got {type(arrival_no_lu.arrival_time.tzinfo)}"

        # Both should have the same timezone type
        assert type(arrival_fresh.arrival_time.tzinfo) == type(
            arrival_no_lu.arrival_time.tzinfo
        )

    def test_arrival_time_staleness_boundary(self, client):
        """Regression: verify behavior at the exact 300-second staleness boundary.

        At exactly 300s, lastUpdated should still be used (0 <= staleness <= 300).
        At 301s, it should fall back to now.
        """
        from trackrat.utils.time import now_et

        now = now_et()

        # Exactly 300 seconds (5 min) — should use lastUpdated
        boundary_time = now - timedelta(seconds=300)
        msg_at_boundary = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lastUpdated": boundary_time.isoformat(),
            "lineColor": "D93A30",
        }
        arrival = client._parse_arrival_message("PJS", "ToNY", msg_at_boundary, now)
        assert arrival is not None
        expected = boundary_time + timedelta(minutes=10)
        delta = abs((arrival.arrival_time - expected).total_seconds())
        assert delta < 1, (
            f"At exactly 300s staleness, should use lastUpdated. "
            f"Expected ~{expected}, got {arrival.arrival_time}"
        )

        # 301 seconds — should fall back to now
        over_boundary = now - timedelta(seconds=301)
        msg_over = {
            "headSign": "World Trade Center",
            "arrivalTimeMessage": "10 min",
            "lastUpdated": over_boundary.isoformat(),
            "lineColor": "D93A30",
        }
        arrival_over = client._parse_arrival_message("PJS", "ToNY", msg_over, now)
        assert arrival_over is not None
        expected_now = now + timedelta(minutes=10)
        delta_now = abs((arrival_over.arrival_time - expected_now).total_seconds())
        assert delta_now < 1, (
            f"At 301s staleness, should fall back to now. "
            f"Expected ~{expected_now}, got {arrival_over.arrival_time}"
        )

    def test_parse_response_uses_last_updated_for_all_arrivals(self, client):
        """Regression: _parse_response must use lastUpdated for every arrival.

        Simulates a realistic scenario where the API data is 90 seconds old.
        All computed arrival_times must be based on lastUpdated, not now.
        This is the primary regression test for the PATH time delay bug.
        """
        from trackrat.utils.time import now_et

        now = now_et()
        last_updated = now - timedelta(seconds=90)
        lu_str = last_updated.isoformat()

        data = {
            "results": [
                {
                    "consideredStation": "JSQ",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "World Trade Center",
                                    "arrivalTimeMessage": "12 min",
                                    "lastUpdated": lu_str,
                                    "lineColor": "D93A30",
                                },
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "6 min",
                                    "lastUpdated": lu_str,
                                    "lineColor": "4D92FB",
                                },
                            ],
                        },
                    ],
                },
                {
                    "consideredStation": "HOB",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "3 min",
                                    "lastUpdated": lu_str,
                                    "lineColor": "4D92FB",
                                },
                            ],
                        },
                    ],
                },
            ]
        }

        # Patch now_et so _parse_response uses our controlled `now`
        with patch("trackrat.collectors.path.ridepath_client.now_et", return_value=now):
            arrivals = client._parse_response(data)

        assert len(arrivals) == 3, f"Expected 3 arrivals, got {len(arrivals)}"

        for arrival in arrivals:
            # Each arrival_time must be based on lastUpdated, not now.
            # If based on now, the offset from lastUpdated would be ~90s too much.
            implied_baseline = arrival.arrival_time - timedelta(
                minutes=arrival.minutes_away
            )
            offset_from_lu = abs((implied_baseline - last_updated).total_seconds())
            offset_from_now = abs((implied_baseline - now).total_seconds())

            assert offset_from_lu < 2, (
                f"arrival {arrival.headsign} at {arrival.station_code}: "
                f"arrival_time should be based on lastUpdated (offset {offset_from_lu:.1f}s), "
                f"but appears based on now (offset {offset_from_now:.1f}s)"
            )
            assert offset_from_now > 85, (
                f"arrival {arrival.headsign} at {arrival.station_code}: "
                f"arrival_time appears to use now as baseline (offset {offset_from_now:.1f}s). "
                f"This is the PATH time delay bug — must use lastUpdated instead."
            )

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        # Access session to create it
        _ = client.session

        await client.close()

        assert client._session is None
