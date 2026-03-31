"""
Unit tests for PATH GTFS-based segment travel times.

Tests the segment time lookup, cumulative time calculation,
fallback behavior, and multi-observation averaging logic.
"""

from datetime import datetime, timedelta, timezone

import pytest

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.segment_times import (
    DEFAULT_MINUTES_PER_SEGMENT,
    SegmentTimesMap,
    clear_cache,
    get_cumulative_time,
)
from trackrat.models.database import JourneyStop

# =============================================================================
# TEST DATA
# =============================================================================

# Realistic segment times for NWK-WTC route (862): PNK-PHR-PJS-PGR-PEX-PWC
NWK_WTC_SEGMENTS: list[tuple[str, str, float]] = [
    ("PNK", "PHR", 4.0),  # Newark to Harrison: 4 min
    ("PHR", "PJS", 5.0),  # Harrison to Journal Square: 5 min
    ("PJS", "PGR", 2.0),  # JSQ to Grove Street: 2 min
    ("PGR", "PEX", 2.0),  # Grove to Exchange Place: 2 min
    ("PEX", "PWC", 3.0),  # Exchange Place to WTC: 3 min
]

# HOB-33 route (859): PHO-PCH-P9S-P14-P23-P33
HOB_33_SEGMENTS: list[tuple[str, str, float]] = [
    ("PHO", "PCH", 5.0),  # Hoboken to Christopher St: 5 min (under Hudson)
    ("PCH", "P9S", 2.0),  # Christopher to 9th St: 2 min
    ("P9S", "P14", 2.0),  # 9th to 14th: 2 min
    ("P14", "P23", 2.0),  # 14th to 23rd: 2 min
    ("P23", "P33", 2.0),  # 23rd to 33rd: 2 min
]

SAMPLE_SEGMENT_TIMES: SegmentTimesMap = {
    "862": NWK_WTC_SEGMENTS,
    "859": HOB_33_SEGMENTS,
}

NWK_WTC_STOPS = ["PNK", "PHR", "PJS", "PGR", "PEX", "PWC"]
HOB_33_STOPS = ["PHO", "PCH", "P9S", "P14", "P23", "P33"]


# =============================================================================
# get_cumulative_time TESTS
# =============================================================================


class TestGetCumulativeTime:
    """Tests for the cumulative time calculation function."""

    def test_same_index_returns_zero(self):
        """Travel time from a stop to itself is zero."""
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 2, 2, "862")
        assert result == 0.0

    def test_single_segment(self):
        """Travel time for one segment uses GTFS data."""
        # PNK to PHR = 4 minutes
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 1, "862")
        assert result == 4.0

    def test_multiple_segments(self):
        """Travel time across multiple segments sums correctly."""
        # PNK to PJS = 4 + 5 = 9 minutes
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 2, "862")
        assert result == 9.0

    def test_full_route(self):
        """Travel time for entire NWK-WTC route."""
        # PNK to PWC = 4 + 5 + 2 + 2 + 3 = 16 minutes
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 5, "862")
        assert result == 16.0

    def test_mid_route_segment(self):
        """Travel time between non-origin stops."""
        # PJS to PEX = 2 + 2 = 4 minutes
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 2, 4, "862")
        assert result == 4.0

    def test_hob_33_full_route(self):
        """Travel time for entire HOB-33 route."""
        # PHO to P33 = 5 + 2 + 2 + 2 + 2 = 13 minutes
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, HOB_33_STOPS, 0, 5, "859")
        assert result == 13.0

    def test_reversed_indices_handled(self):
        """Reversed from/to indices still return correct time."""
        forward = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 3, "862")
        reversed_result = get_cumulative_time(
            SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 3, 0, "862"
        )
        assert forward == reversed_result

    def test_fallback_when_no_route_data(self):
        """Falls back to DEFAULT_MINUTES_PER_SEGMENT when route not in map."""
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 3, "99999")
        assert result == 3 * DEFAULT_MINUTES_PER_SEGMENT

    def test_fallback_when_route_id_none(self):
        """Falls back to default when route_id is None."""
        result = get_cumulative_time(SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 3, None)
        assert result == 3 * DEFAULT_MINUTES_PER_SEGMENT

    def test_fallback_when_empty_segment_times(self):
        """Falls back to default when segment_times map is empty."""
        result = get_cumulative_time({}, NWK_WTC_STOPS, 0, 3, "862")
        assert result == 3 * DEFAULT_MINUTES_PER_SEGMENT

    def test_fallback_when_segment_missing_in_route(self):
        """Falls back to default if a segment pair is missing from route data."""
        # Only has first segment, rest are missing
        partial: SegmentTimesMap = {"862": [("PNK", "PHR", 4.0)]}
        # PNK to PJS requires 2 segments but only first exists
        result = get_cumulative_time(partial, NWK_WTC_STOPS, 0, 2, "862")
        # Should fall back to default for the whole range
        assert result == 2 * DEFAULT_MINUTES_PER_SEGMENT

    def test_gtfs_times_differ_from_flat_3_min(self):
        """GTFS times are NOT simply N*3 - verifies we're actually using GTFS data."""
        flat_3_min = 5 * DEFAULT_MINUTES_PER_SEGMENT  # 15 min for 5 segments
        gtfs_result = get_cumulative_time(
            SAMPLE_SEGMENT_TIMES, NWK_WTC_STOPS, 0, 5, "862"
        )
        assert (
            gtfs_result != flat_3_min
        ), f"GTFS result ({gtfs_result}) should differ from flat 3min ({flat_3_min})"


# =============================================================================
# MULTI-OBSERVATION AVERAGING TESTS
# =============================================================================

ET = timezone(timedelta(hours=-5))


class TestComputeAveragedOriginDeparture:
    """Tests for the weighted-average origin departure computation."""

    def setup_method(self):
        self.collector = PathCollector()

    def _make_stop(
        self,
        station_code: str,
        sequence: int,
        actual_arrival: datetime | None = None,
        actual_departure: datetime | None = None,
        has_departed: bool = False,
    ) -> JourneyStop:
        """Create a JourneyStop for testing."""
        stop = JourneyStop()
        stop.station_code = station_code
        stop.stop_sequence = sequence
        stop.actual_arrival = actual_arrival
        stop.actual_departure = actual_departure
        stop.has_departed_station = has_departed
        stop.scheduled_arrival = None
        stop.scheduled_departure = None
        stop.updated_arrival = None
        stop.updated_departure = None
        return stop

    def test_single_observation_returns_implied_origin(self):
        """Single observation should return implied origin based on GTFS times."""
        # Train observed at PHR (index 1) at 10:04
        # With GTFS times: PNK->PHR = 4 min, so implied origin = 10:00
        observed_time = datetime(2026, 1, 19, 10, 4, 0, tzinfo=ET)
        stops = [
            self._make_stop("PNK", 1),
            self._make_stop("PHR", 2, actual_arrival=observed_time, has_departed=True),
            self._make_stop("PJS", 3),
            self._make_stop("PGR", 4),
            self._make_stop("PEX", 5),
            self._make_stop("PWC", 6),
        ]

        result = self.collector._compute_averaged_origin_departure(
            stops, NWK_WTC_STOPS, SAMPLE_SEGMENT_TIMES, "862"
        )

        assert result is not None
        expected = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        assert abs((result - expected).total_seconds()) < 1

    def test_two_observations_averaged(self):
        """Two observations should produce a weighted average."""
        # Stop PHR (idx 1, 4 min from origin): observed at 10:04 → implied origin 10:00
        # Stop PJS (idx 2, 9 min from origin): observed at 10:10 → implied origin 10:01
        # Weight for PHR: 1/4 = 0.25
        # Weight for PJS: 1/9 ≈ 0.111
        # Average should be closer to PHR's implication (10:00) since it has higher weight
        stops = [
            self._make_stop("PNK", 1),
            self._make_stop(
                "PHR",
                2,
                actual_arrival=datetime(2026, 1, 19, 10, 4, 0, tzinfo=ET),
                has_departed=True,
            ),
            self._make_stop(
                "PJS",
                3,
                actual_arrival=datetime(2026, 1, 19, 10, 10, 0, tzinfo=ET),
                has_departed=True,
            ),
            self._make_stop("PGR", 4),
            self._make_stop("PEX", 5),
            self._make_stop("PWC", 6),
        ]

        result = self.collector._compute_averaged_origin_departure(
            stops, NWK_WTC_STOPS, SAMPLE_SEGMENT_TIMES, "862"
        )

        assert result is not None
        # PHR implies 10:00:00, PJS implies 10:01:00
        # Weighted avg: (10:00*0.25 + 10:01*0.111) / (0.25 + 0.111) ≈ 10:00:18
        # Should be between 10:00 and 10:01, closer to 10:00
        implied_phr = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        implied_pjs = datetime(2026, 1, 19, 10, 1, 0, tzinfo=ET)
        assert implied_phr <= result <= implied_pjs

    def test_closer_observations_weighted_higher(self):
        """Closer stations should have more influence on the average."""
        # Two scenarios with same observations but different order
        # Verify closer station dominates
        close_time = datetime(2026, 1, 19, 10, 4, 0, tzinfo=ET)  # PHR, 4 min away
        far_time = datetime(2026, 1, 19, 10, 18, 0, tzinfo=ET)  # PWC, 16 min away

        stops = [
            self._make_stop("PNK", 1),
            self._make_stop("PHR", 2, actual_arrival=close_time, has_departed=True),
            self._make_stop("PJS", 3),
            self._make_stop("PGR", 4),
            self._make_stop("PEX", 5),
            self._make_stop("PWC", 6, actual_arrival=far_time, has_departed=True),
        ]

        result = self.collector._compute_averaged_origin_departure(
            stops, NWK_WTC_STOPS, SAMPLE_SEGMENT_TIMES, "862"
        )

        assert result is not None
        # PHR implies origin at 10:00, PWC implies origin at 10:02
        # PHR weight (1/4=0.25) >> PWC weight (1/16=0.0625)
        # Result should be much closer to 10:00 than 10:02
        implied_phr = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        diff_seconds = abs((result - implied_phr).total_seconds())
        assert (
            diff_seconds < 30
        ), f"Result should be within 30s of PHR implication, was {diff_seconds}s away"

    def test_no_observations_returns_none(self):
        """Returns None when no stops have actual times."""
        stops = [
            self._make_stop("PNK", 1),
            self._make_stop("PHR", 2),
            self._make_stop("PJS", 3),
        ]

        result = self.collector._compute_averaged_origin_departure(
            stops, NWK_WTC_STOPS, SAMPLE_SEGMENT_TIMES, "862"
        )
        assert result is None

    def test_origin_observation_gets_highest_weight(self):
        """Origin stop observation should dominate the average."""
        origin_time = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        far_time = datetime(2026, 1, 19, 10, 18, 0, tzinfo=ET)  # implies 10:02

        stops = [
            self._make_stop("PNK", 1, actual_departure=origin_time, has_departed=True),
            self._make_stop("PHR", 2),
            self._make_stop("PJS", 3),
            self._make_stop("PGR", 4),
            self._make_stop("PEX", 5),
            self._make_stop("PWC", 6, actual_arrival=far_time, has_departed=True),
        ]

        result = self.collector._compute_averaged_origin_departure(
            stops, NWK_WTC_STOPS, SAMPLE_SEGMENT_TIMES, "862"
        )

        assert result is not None
        # Origin weight is 10.0, PWC weight is 1/16 = 0.0625
        # Should be extremely close to 10:00
        diff_seconds = abs((result - origin_time).total_seconds())
        assert (
            diff_seconds < 2
        ), f"Origin observation should dominate, was {diff_seconds}s away"


class TestRecomputeStopTimes:
    """Tests for recomputing stop times from averaged origin departure."""

    def setup_method(self):
        self.collector = PathCollector()

    def _make_stop(
        self,
        station_code: str,
        sequence: int,
        has_departed: bool = False,
        updated_arrival: datetime | None = None,
        updated_departure: datetime | None = None,
    ) -> JourneyStop:
        stop = JourneyStop()
        stop.station_code = station_code
        stop.stop_sequence = sequence
        stop.has_departed_station = has_departed
        stop.scheduled_arrival = None
        stop.scheduled_departure = None
        stop.actual_arrival = None
        stop.actual_departure = None
        stop.updated_arrival = updated_arrival
        stop.updated_departure = updated_departure
        return stop

    def test_recomputes_non_departed_stops(self):
        """Non-departed stops get updated times based on averaged origin."""
        origin_time = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        stops = [
            self._make_stop("PNK", 1, has_departed=True),
            self._make_stop("PHR", 2, has_departed=True),
            self._make_stop("PJS", 3, has_departed=False),
            self._make_stop("PGR", 4, has_departed=False),
            self._make_stop("PEX", 5, has_departed=False),
            self._make_stop("PWC", 6, has_departed=False),
        ]

        self.collector._recompute_stop_times(
            stops, NWK_WTC_STOPS, origin_time, SAMPLE_SEGMENT_TIMES, "862"
        )

        # PJS (idx 2): cumulative = 4+5 = 9 min → 10:09
        assert stops[2].updated_arrival == origin_time + timedelta(minutes=9)
        assert stops[2].updated_departure == origin_time + timedelta(minutes=9)

        # PGR (idx 3): cumulative = 4+5+2 = 11 min → 10:11
        assert stops[3].updated_arrival == origin_time + timedelta(minutes=11)
        assert stops[3].updated_departure == origin_time + timedelta(minutes=11)

        # PEX (idx 4): cumulative = 4+5+2+2 = 13 min → 10:13
        assert stops[4].updated_arrival == origin_time + timedelta(minutes=13)
        assert stops[4].updated_departure == origin_time + timedelta(minutes=13)

        # PWC (idx 5, terminus): cumulative = 16 min → 10:16
        # Terminus: updated_arrival set, updated_departure NOT set
        assert stops[5].updated_arrival == origin_time + timedelta(minutes=16)

    def test_does_not_modify_departed_stops(self):
        """Departed stops are left unchanged."""
        origin_time = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        departed_arrival = datetime(2026, 1, 19, 10, 4, 30, tzinfo=ET)
        stops = [
            self._make_stop("PNK", 1, has_departed=True),
            self._make_stop(
                "PHR",
                2,
                has_departed=True,
                updated_arrival=departed_arrival,
            ),
            self._make_stop("PJS", 3, has_departed=False),
        ]

        self.collector._recompute_stop_times(
            stops, NWK_WTC_STOPS, origin_time, SAMPLE_SEGMENT_TIMES, "862"
        )

        # Departed stop should keep its existing time
        assert stops[1].updated_arrival == departed_arrival

    def test_terminus_has_no_departure(self):
        """Terminus stop should not get updated_departure."""
        origin_time = datetime(2026, 1, 19, 10, 0, 0, tzinfo=ET)
        stops = [
            self._make_stop("PNK", 1, has_departed=True),
            self._make_stop("PHR", 2, has_departed=True),
            self._make_stop("PJS", 3, has_departed=True),
            self._make_stop("PGR", 4, has_departed=True),
            self._make_stop("PEX", 5, has_departed=True),
            self._make_stop("PWC", 6, has_departed=False),
        ]

        self.collector._recompute_stop_times(
            stops, NWK_WTC_STOPS, origin_time, SAMPLE_SEGMENT_TIMES, "862"
        )

        # Terminus gets arrival but not departure
        assert stops[5].updated_arrival == origin_time + timedelta(minutes=16)
        assert stops[5].updated_departure is None


class TestClearCache:
    """Tests for segment time cache clearing."""

    def test_clear_cache_resets(self):
        """clear_cache should reset the module-level cache."""
        from trackrat.collectors.path import segment_times

        # Set cache to something
        segment_times._cached_segment_times = {"test": []}
        clear_cache()
        assert segment_times._cached_segment_times is None
