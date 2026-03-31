"""Unit tests for ground-truth-validate.py compare_route() and helper functions.

Tests the core matching logic without network access. All inputs are constructed
in-memory so these tests run fast and deterministically.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

import pytest

# Add scripts dir so we can import the validation module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))

from importlib import import_module

# Import the script as a module (filename has hyphens, so use importlib)
gtv = import_module("ground-truth-validate")

GroundTruthArrival = gtv.GroundTruthArrival
TrackRatDeparture = gtv.TrackRatDeparture
compare_route = gtv.compare_route
format_delta = gtv.format_delta
parse_arrival_minutes = gtv.parse_arrival_minutes
parse_arrival_seconds = gtv.parse_arrival_seconds


# --- Helpers ---

NOW = datetime(2026, 2, 22, 15, 0, 0, tzinfo=timezone.utc)


def _gt(
    minutes_offset: int = 0,
    station: str = "NWK",
    dest: str = "WTC",
    train_id: str = "",
    track: str | None = None,
) -> GroundTruthArrival:
    """Build a GroundTruthArrival with sensible defaults."""
    expected = NOW + timedelta(minutes=minutes_offset)
    return GroundTruthArrival(
        station_code=station,
        destination_code=dest,
        expected_time=expected,
        line_color="#FF6600",
        headsign=f"Train to {dest}",
        minutes_away=max(0, minutes_offset),
        train_id=train_id,
        track=track,
    )


def _tr(
    minutes_offset: int = 0,
    train_id: str = "T1",
    dest: str = "WTC",
    track: str | None = None,
    is_cancelled: bool = False,
    observation_type: str = "OBSERVED",
) -> TrackRatDeparture:
    """Build a TrackRatDeparture with sensible defaults."""
    dep_time = NOW + timedelta(minutes=minutes_offset)
    return TrackRatDeparture(
        train_id=train_id,
        destination_code=dest,
        destination_name=f"Station {dest}",
        departure_time=dep_time,
        line_code="NEC",
        line_color="#FF6600",
        observation_type=observation_type,
        track=track,
        is_cancelled=is_cancelled,
    )


# --- Tests for format_delta ---


class TestFormatDelta:
    def test_seconds_only(self):
        assert format_delta(45) == "45s"

    def test_exact_minutes(self):
        assert format_delta(120) == "2m"

    def test_minutes_and_seconds(self):
        assert format_delta(125) == "2m 5s"

    def test_zero(self):
        assert format_delta(0) == "0s"

    def test_negative_uses_absolute(self):
        assert format_delta(-90) == "1m 30s"


# --- Tests for parse_arrival_minutes ---


class TestParseArrivalMinutes:
    def test_numeric_minutes(self):
        assert parse_arrival_minutes("14 min") == 14

    def test_arriving(self):
        assert parse_arrival_minutes("Arriving") == 0

    def test_now(self):
        assert parse_arrival_minutes("now") == 0

    def test_empty(self):
        assert parse_arrival_minutes("") is None

    def test_none(self):
        assert parse_arrival_minutes("") is None

    def test_garbage(self):
        # "unknown" contains "now" substring, so returns 0
        assert parse_arrival_minutes("unknown") == 0

    def test_truly_unrecognized(self):
        assert parse_arrival_minutes("delayed") is None

    def test_whitespace(self):
        assert parse_arrival_minutes("  5 min  ") == 5


# --- Tests for compare_route ---


class TestCompareRouteBasicMatching:
    """Test the core matching logic of compare_route."""

    def test_exact_time_match(self):
        """GT and TR at the same time should match with 0 delta."""
        gt = [_gt(minutes_offset=10)]
        tr = [_tr(minutes_offset=10)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].delta_seconds == 0
        assert len(result.missing) == 0
        assert len(result.phantoms) == 0

    def test_match_within_tolerance(self):
        """GT and TR within tolerance should match."""
        gt = [_gt(minutes_offset=10)]
        tr = [_tr(minutes_offset=12)]  # 2 minutes later
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].delta_seconds == 120  # 2 min = 120s
        assert len(result.missing) == 0

    def test_no_match_outside_tolerance(self):
        """GT and TR outside tolerance should not match."""
        gt = [_gt(minutes_offset=10)]
        tr = [_tr(minutes_offset=20)]  # 10 minutes later, way outside 3-min tolerance
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 0
        assert len(result.missing) == 1
        assert len(result.phantoms) == 1

    def test_empty_gt(self):
        """Empty GT list should produce empty result (early return, no phantom check)."""
        tr = [_tr(minutes_offset=10)]
        result = compare_route([], tr, "NWK", "WTC", tolerance_minutes=3)

        # compare_route returns early when no relevant GT, so phantoms aren't populated
        assert len(result.matches) == 0
        assert len(result.missing) == 0
        assert len(result.phantoms) == 0

    def test_empty_tr(self):
        """Empty TR list should produce all GT as missing."""
        gt = [_gt(minutes_offset=10)]
        result = compare_route(gt, [], "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 0
        assert len(result.missing) == 1
        assert len(result.phantoms) == 0

    def test_empty_both(self):
        """No GT at origin should produce empty result."""
        result = compare_route([], [], "NWK", "WTC", tolerance_minutes=3)
        assert len(result.matches) == 0
        assert len(result.missing) == 0
        assert len(result.phantoms) == 0


class TestCompareRouteFiltering:
    """Test that compare_route filters GT by origin/destination."""

    def test_filters_by_origin(self):
        """GT at a different station should be ignored."""
        gt = [_gt(minutes_offset=10, station="HOB")]  # Different station
        tr = [_tr(minutes_offset=10)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        # HOB GT is not at NWK, so no relevant GT
        assert len(result.matches) == 0
        assert len(result.missing) == 0

    def test_filters_by_destination(self):
        """GT with a different destination should be ignored."""
        gt = [_gt(minutes_offset=10, dest="HOB")]  # Different destination
        tr = [_tr(minutes_offset=10)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 0
        assert len(result.missing) == 0


class TestCompareRouteTrainIdMatching:
    """Test that train ID matching is preferred over time-only matching."""

    def test_prefers_id_match_over_closer_time(self):
        """When train IDs match, prefer that over a closer time match."""
        gt = [_gt(minutes_offset=10, train_id="1234")]
        tr = [
            _tr(minutes_offset=10, train_id="9999"),  # Exact time, wrong ID
            _tr(minutes_offset=12, train_id="1234"),  # 2min off, right ID
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].tr.train_id == "1234"
        assert result.matches[0].delta_seconds == 120

    def test_falls_back_to_time_when_no_id(self):
        """Without train IDs, closer time match should win."""
        gt = [_gt(minutes_offset=10)]  # No train_id
        tr = [
            _tr(minutes_offset=12, train_id="A"),  # 2 min off
            _tr(minutes_offset=10, train_id="B"),  # Exact match
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].tr.train_id == "B"  # Closer time wins


class TestCompareRouteMultipleTrains:
    """Test matching with multiple GT and TR entries."""

    def test_multiple_matches(self):
        """Multiple GT entries should each match a separate TR entry."""
        gt = [_gt(minutes_offset=10), _gt(minutes_offset=20)]
        tr = [
            _tr(minutes_offset=10, train_id="A"),
            _tr(minutes_offset=20, train_id="B"),
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 2
        assert len(result.missing) == 0
        assert len(result.phantoms) == 0

    def test_one_match_one_missing(self):
        """One GT should match, one should be missing."""
        gt = [_gt(minutes_offset=10), _gt(minutes_offset=30)]
        tr = [_tr(minutes_offset=11)]  # Only close to the first GT
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert len(result.missing) == 1
        assert result.missing[0].expected_time == NOW + timedelta(minutes=30)

    def test_no_double_matching(self):
        """A TR entry should only be used once, even if close to multiple GT."""
        gt = [_gt(minutes_offset=10), _gt(minutes_offset=11)]
        tr = [_tr(minutes_offset=10)]  # Close to both GTs
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert len(result.missing) == 1


class TestCompareRouteArrivingUnmatched:
    """Test the arriving_unmatched (gray zone) behavior."""

    def test_arriving_train_unmatched_is_warn(self):
        """GT with minutes_away=0 that doesn't match goes to arriving_unmatched."""
        gt = [_gt(minutes_offset=0)]  # Arriving now
        gt[0].minutes_away = 0
        tr = []  # No TR data
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.arriving_unmatched) == 1
        assert len(result.missing) == 0

    def test_non_arriving_train_unmatched_is_missing(self):
        """GT with minutes_away > 0 that doesn't match goes to missing."""
        gt = [_gt(minutes_offset=10)]
        tr = []
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.missing) == 1
        assert len(result.arriving_unmatched) == 0


class TestCompareRoutePhantoms:
    """Test phantom (unmatched TrackRat) detection."""

    def test_unmatched_tr_is_phantom(self):
        """TR with no matching GT should be a phantom."""
        # Need at least one relevant GT to avoid early return
        gt = [_gt(minutes_offset=5)]
        tr = [
            _tr(minutes_offset=5, train_id="match"),  # Matches GT
            _tr(minutes_offset=30, train_id="phantom"),  # No GT match -> phantom
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert len(result.phantoms) == 1
        assert result.phantoms[0].train_id == "phantom"

    def test_cancelled_tr_separated_from_phantoms(self):
        """Cancelled TR entries should go to cancelled_in_tr, not phantoms."""
        # Need at least one relevant GT to avoid early return
        gt = [_gt(minutes_offset=5)]
        tr = [
            _tr(minutes_offset=5, train_id="match"),  # Matches GT
            _tr(
                minutes_offset=30, is_cancelled=True, train_id="cancelled"
            ),  # Unmatched cancelled
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert len(result.phantoms) == 0
        assert len(result.cancelled_in_tr) == 1
        assert result.cancelled_in_tr[0].train_id == "cancelled"


class TestCompareRouteTrackValidation:
    """Test track assignment comparison."""

    def test_track_match(self):
        """Matching tracks should not flag a mismatch."""
        gt = [_gt(minutes_offset=10, track="5")]
        tr = [_tr(minutes_offset=10, track="5")]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].track_mismatch is False

    def test_track_mismatch(self):
        """Different tracks should flag a mismatch."""
        gt = [_gt(minutes_offset=10, track="5")]
        tr = [_tr(minutes_offset=10, track="3")]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].track_mismatch is True

    def test_gt_track_none_no_mismatch(self):
        """No GT track should not flag a mismatch even if TR has one."""
        gt = [_gt(minutes_offset=10, track=None)]
        tr = [_tr(minutes_offset=10, track="5")]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].track_mismatch is False

    def test_tr_track_none_no_mismatch(self):
        """No TR track should not flag a mismatch even if GT has one."""
        gt = [_gt(minutes_offset=10, track="5")]
        tr = [_tr(minutes_offset=10, track=None)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].track_mismatch is False

    def test_both_track_none_no_mismatch(self):
        """No tracks on either side should not flag a mismatch."""
        gt = [_gt(minutes_offset=10)]
        tr = [_tr(minutes_offset=10)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].track_mismatch is False


class TestCompareRouteCancellation:
    """Test cancellation handling in matching."""

    def test_matched_cancelled_train(self):
        """A cancelled TR that matches a GT by time should still match (caught in reporting)."""
        gt = [_gt(minutes_offset=10, train_id="1234")]
        tr = [_tr(minutes_offset=10, train_id="1234", is_cancelled=True)]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        # It matches by time/ID, cancellation is reported during output
        assert len(result.matches) == 1
        assert result.matches[0].tr.is_cancelled is True

    def test_unmatched_cancelled_goes_to_cancelled_list(self):
        """An unmatched cancelled TR should go to cancelled_in_tr, not phantoms."""
        gt = [_gt(minutes_offset=10)]
        tr = [
            _tr(minutes_offset=10),  # This one matches the GT
            _tr(
                minutes_offset=30, is_cancelled=True
            ),  # This one is unmatched + cancelled
        ]
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert len(result.cancelled_in_tr) == 1
        assert len(result.phantoms) == 0


class TestCompareRouteToleranceBoundary:
    """Test behavior at the exact tolerance boundary."""

    def test_at_exact_tolerance_matches(self):
        """Delta exactly at tolerance should match (<=, not <)."""
        gt = [_gt(minutes_offset=10)]
        tr = [_tr(minutes_offset=13)]  # Exactly 3 min = tolerance
        result = compare_route(gt, tr, "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 1
        assert result.matches[0].delta_seconds == 180

    def test_one_second_over_tolerance_fails(self):
        """Delta one second over tolerance should not match."""
        gt = [_gt(minutes_offset=10)]
        # 3 min 1 sec later
        tr_dep = _tr(minutes_offset=13)
        tr_dep.departure_time += timedelta(seconds=1)
        result = compare_route(gt, [tr_dep], "NWK", "WTC", tolerance_minutes=3)

        assert len(result.matches) == 0
        assert len(result.missing) == 1

    def test_default_tolerance_2min_matches_within_120s(self):
        """Default tolerance of 2.0 min should match trains within 120s."""
        gt = [_gt(minutes_offset=10)]
        # 1 min 50 sec later (110s) — should match with 2.0 min tolerance
        tr_dep = _tr(minutes_offset=11)
        tr_dep.departure_time += timedelta(seconds=50)
        result = compare_route(gt, [tr_dep], "NWK", "WTC", tolerance_minutes=2.0)

        assert len(result.matches) == 1
        assert result.matches[0].delta_seconds == 110

    def test_default_tolerance_2min_rejects_over_120s(self):
        """Default tolerance of 2.0 min should reject trains over 120s away."""
        gt = [_gt(minutes_offset=10)]
        # 2 min 1 sec later (121s) — should NOT match with 2.0 min tolerance
        tr_dep = _tr(minutes_offset=12)
        tr_dep.departure_time += timedelta(seconds=1)
        result = compare_route(gt, [tr_dep], "NWK", "WTC", tolerance_minutes=2.0)

        assert len(result.matches) == 0
        assert len(result.missing) == 1


class TestParseArrivalSeconds:
    """Test parse_arrival_seconds which prefers precise seconds over rounded minutes."""

    def test_uses_seconds_when_available(self):
        """Should use secondsToArrival for precise timing."""
        result = parse_arrival_seconds("422", "7 min")
        assert result == (422, 7)  # 422s = 7m 2s, minutes_away = 7

    def test_seconds_precision_vs_minutes_rounding(self):
        """Seconds gives sub-minute precision that minutes can't."""
        result = parse_arrival_seconds("153", "3 min")
        assert result == (153, 2)  # 153s = 2m 33s, minutes_away = 2 (not 3)

    def test_falls_back_to_minutes_when_no_seconds(self):
        """Should use arrivalTimeMessage when secondsToArrival is absent."""
        result = parse_arrival_seconds(None, "7 min")
        assert result == (420, 7)  # 7 * 60 = 420

    def test_falls_back_to_minutes_when_seconds_invalid(self):
        """Should fall back to minutes when secondsToArrival is not a number."""
        result = parse_arrival_seconds("bad", "7 min")
        assert result == (420, 7)

    def test_returns_none_when_both_unparseable(self):
        """Should return None when neither field is parseable."""
        result = parse_arrival_seconds("bad", "")
        assert result is None

    def test_zero_seconds(self):
        """Zero seconds (arriving) should work."""
        result = parse_arrival_seconds("0", "0 min")
        assert result == (0, 0)

    def test_arriving_message_fallback(self):
        """Should handle 'Arriving' message as fallback."""
        result = parse_arrival_seconds(None, "Arriving")
        assert result == (0, 0)

    def test_large_seconds_value(self):
        """Should handle large countdown values (far-future trains)."""
        result = parse_arrival_seconds("1320", "22 min")
        assert result == (1320, 22)  # 1320s = 22m


class TestCompareRouteFarFuture:
    """Test that far-future unmatched trains go to missing (reporting decides WARN vs FAIL)."""

    def test_far_future_unmatched_gt_still_goes_to_missing(self):
        """compare_route puts all unmatched non-arriving GT into missing.

        The far-future WARN vs FAIL distinction is made in run_validation_loop,
        not in compare_route. This test verifies compare_route behavior is unchanged.
        """
        gt = [_gt(minutes_offset=20)]  # 20 min away, no TR to match
        gt[0].minutes_away = 20
        result = compare_route(gt, [], "NWK", "WTC", tolerance_minutes=2.0)

        assert len(result.missing) == 1
        assert result.missing[0].minutes_away == 20

    def test_near_future_unmatched_also_goes_to_missing(self):
        """Near-future unmatched GT should also go to missing (not arriving_unmatched)."""
        gt = [_gt(minutes_offset=5)]
        gt[0].minutes_away = 5
        result = compare_route(gt, [], "NWK", "WTC", tolerance_minutes=2.0)

        assert len(result.missing) == 1
        assert result.missing[0].minutes_away == 5
