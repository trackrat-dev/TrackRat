"""
Tests for the route history endpoint statistics calculations.

Tests _calculate_route_stats directly to verify:
- Cancellation rate is returned as a percentage (0-100), not a fraction
- Departure delay is calculated at the origin station
- Arrival delay is calculated at the destination station
- Delay categories are correctly assigned
- Empty journey lists return zero defaults
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from trackrat.api.routes import _calculate_route_stats


def _make_stop(
    station_code: str,
    stop_sequence: int,
    scheduled_departure: datetime | None = None,
    actual_departure: datetime | None = None,
    scheduled_arrival: datetime | None = None,
    actual_arrival: datetime | None = None,
    track: str | None = None,
) -> MagicMock:
    """Create a mock JourneyStop with the given fields."""
    stop = MagicMock()
    stop.station_code = station_code
    stop.stop_sequence = stop_sequence
    stop.scheduled_departure = scheduled_departure
    stop.actual_departure = actual_departure
    stop.scheduled_arrival = scheduled_arrival
    stop.actual_arrival = actual_arrival
    stop.track = track
    return stop


def _make_journey(
    stops: list[MagicMock],
    is_cancelled: bool = False,
) -> MagicMock:
    """Create a mock TrainJourney with the given stops."""
    journey = MagicMock()
    journey.stops = stops
    journey.is_cancelled = is_cancelled
    return journey


BASE_TIME = datetime(2025, 6, 15, 8, 0, 0, tzinfo=timezone.utc)


class TestCalculateRouteStatsEmpty:
    """Verify correct defaults when no journeys are provided."""

    def test_empty_journeys_returns_zeros(self):
        result = _calculate_route_stats([], "NY")

        assert result["on_time_percentage"] == 0.0
        assert result["average_delay_minutes"] == 0.0
        assert result["average_departure_delay_minutes"] == 0.0
        assert result["cancellation_rate"] == 0.0
        assert result["delay_breakdown"] == {
            "on_time": 0,
            "slight": 0,
            "significant": 0,
            "major": 0,
        }
        assert result["track_usage"] == {}


class TestCancellationRate:
    """Verify cancellation_rate is a percentage (0-100), not a fraction (0-1).

    This was the root cause of the iOS "1009% Cancelled" bug - the backend
    returns a percentage but iOS multiplied by 100 again.
    """

    def test_cancellation_rate_is_percentage(self):
        """10 journeys, 2 cancelled = 20% (not 0.2)."""
        journeys = []
        for i in range(10):
            stops = [
                _make_stop(
                    "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
                ),
                _make_stop(
                    "TR",
                    1,
                    scheduled_arrival=BASE_TIME + timedelta(hours=1),
                    actual_arrival=BASE_TIME + timedelta(hours=1),
                ),
            ]
            journeys.append(_make_journey(stops, is_cancelled=(i < 2)))

        result = _calculate_route_stats(journeys, "NY")

        # Must be 20.0, not 0.2
        assert result["cancellation_rate"] == 20.0, (
            f"Expected 20.0% but got {result['cancellation_rate']}. "
            "cancellation_rate should be a percentage (0-100)."
        )

    def test_zero_cancellation_rate(self):
        """All trains running = 0% cancelled."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")
        assert result["cancellation_rate"] == 0.0

    def test_full_cancellation_rate(self):
        """All trains cancelled = 100%."""
        stops = [
            _make_stop("NY", 0),
            _make_stop("TR", 1),
        ]
        journeys = [_make_journey(stops, is_cancelled=True)]
        result = _calculate_route_stats(journeys, "NY")
        assert result["cancellation_rate"] == 100.0


class TestDepartureDelay:
    """Verify departure delay is calculated at the origin station."""

    def test_departure_delay_at_origin(self):
        """Train departs 10 minutes late from origin."""
        stops = [
            _make_stop(
                "NY",
                0,
                scheduled_departure=BASE_TIME,
                actual_departure=BASE_TIME + timedelta(minutes=10),
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=5),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")

        assert (
            result["average_departure_delay_minutes"] == 10.0
        ), f"Expected 10m departure delay, got {result['average_departure_delay_minutes']}"
        assert (
            result["average_delay_minutes"] == 5.0
        ), f"Expected 5m arrival delay, got {result['average_delay_minutes']}"

    def test_departure_delay_only_at_specified_origin(self):
        """Departure delay uses the origin_station parameter, not just the first stop."""
        stops = [
            _make_stop(
                "SE",
                0,  # Secaucus (not the origin we care about)
                scheduled_departure=BASE_TIME - timedelta(minutes=30),
                actual_departure=BASE_TIME - timedelta(minutes=20),  # 10 min late
            ),
            _make_stop(
                "NY",
                1,  # Penn Station (our origin)
                scheduled_departure=BASE_TIME,
                actual_departure=BASE_TIME + timedelta(minutes=3),  # 3 min late
            ),
            _make_stop(
                "TR",
                2,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")

        # Should use NY departure delay (3min), not SE (10min)
        assert result["average_departure_delay_minutes"] == 3.0

    def test_departure_delay_zero_when_on_time(self):
        """Train departs on time = 0 delay."""
        stops = [
            _make_stop(
                "NY",
                0,
                scheduled_departure=BASE_TIME,
                actual_departure=BASE_TIME,
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")
        assert result["average_departure_delay_minutes"] == 0.0

    def test_departure_delay_average_across_journeys(self):
        """Average departure delay across multiple trains."""
        journeys = []
        for delay_mins in [0, 5, 10, 15]:
            stops = [
                _make_stop(
                    "NY",
                    0,
                    scheduled_departure=BASE_TIME,
                    actual_departure=BASE_TIME + timedelta(minutes=delay_mins),
                ),
                _make_stop(
                    "TR",
                    1,
                    scheduled_arrival=BASE_TIME + timedelta(hours=1),
                    actual_arrival=BASE_TIME + timedelta(hours=1),
                ),
            ]
            journeys.append(_make_journey(stops))

        result = _calculate_route_stats(journeys, "NY")
        # Average of 0, 5, 10, 15 = 7.5
        assert result["average_departure_delay_minutes"] == 7.5

    def test_departure_delay_excludes_no_actual(self):
        """When actual_departure is missing, departure delay is not counted."""
        stops = [
            _make_stop(
                "NY",
                0,
                scheduled_departure=BASE_TIME,
                actual_departure=None,  # No actual data
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")
        # No data points for departure delay
        assert result["average_departure_delay_minutes"] == 0.0


class TestArrivalDelay:
    """Verify arrival delay is calculated at the last stop (destination)."""

    def test_arrival_delay_at_destination(self):
        """Train arrives 8 minutes late at the destination."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=8),
            ),
        ]
        journeys = [_make_journey(stops)]
        result = _calculate_route_stats(journeys, "NY")
        assert result["average_delay_minutes"] == 8.0


class TestDelayCategories:
    """Verify delay breakdown buckets match documented thresholds."""

    def test_on_time_threshold(self):
        """5 minutes or less = on_time."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=5),
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        assert result["delay_breakdown"]["on_time"] == 100

    def test_slight_delay_threshold(self):
        """6-15 minutes = slight."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=10),
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        assert result["delay_breakdown"]["slight"] == 100

    def test_significant_delay_threshold(self):
        """16-30 minutes = significant."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=25),
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        assert result["delay_breakdown"]["significant"] == 100

    def test_major_delay_threshold(self):
        """Over 30 minutes = major."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1, minutes=45),
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        assert result["delay_breakdown"]["major"] == 100


class TestTrackUsage:
    """Verify track usage is counted at origin station only."""

    def test_track_usage_at_origin(self):
        stops = [
            _make_stop(
                "NY",
                0,
                scheduled_departure=BASE_TIME,
                actual_departure=BASE_TIME,
                track="5",
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
                track="3",
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        assert result["track_usage"] == {"5": 100}

    def test_track_usage_ignores_destination(self):
        """Track at destination should not appear in track_usage."""
        stops = [
            _make_stop(
                "NY", 0, scheduled_departure=BASE_TIME, actual_departure=BASE_TIME
            ),
            _make_stop(
                "TR",
                1,
                scheduled_arrival=BASE_TIME + timedelta(hours=1),
                actual_arrival=BASE_TIME + timedelta(hours=1),
                track="7",
            ),
        ]
        result = _calculate_route_stats([_make_journey(stops)], "NY")
        # NY has no track, TR track should not count
        assert result["track_usage"] == {}
