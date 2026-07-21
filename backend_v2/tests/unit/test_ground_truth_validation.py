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
find_stop_order_inversions = gtv.find_stop_order_inversions
check_njt_stop_order = gtv.check_njt_stop_order
fetch_trackrat_train_stop_order = gtv.fetch_trackrat_train_stop_order
compare_by_train_number = gtv.compare_by_train_number
_norm_train_number = gtv._norm_train_number
_septa_rr_arrival_from_entry = gtv._septa_rr_arrival_from_entry
_parse_septa_status_minutes = gtv._parse_septa_status_minutes
ZoneInfo = gtv.ZoneInfo


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
    line_code: str = "NEC",
) -> TrackRatDeparture:
    """Build a TrackRatDeparture with sensible defaults."""
    dep_time = NOW + timedelta(minutes=minutes_offset)
    return TrackRatDeparture(
        train_id=train_id,
        destination_code=dest,
        destination_name=f"Station {dest}",
        departure_time=dep_time,
        line_code=line_code,
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


class TestRunValidationLoopEmptyGroundTruth:
    """Regression coverage for #1230 silent-skip bug.

    When ground truth returns no arrivals for a direction, the validator
    previously SKIPped unconditionally — masking real-time outages on
    registered routes (e.g. Amtrak Empire NY->ALB). The fixed behavior is
    to still fetch TrackRat and emit a WARN when TR has departures the
    provider real-time feed does not.
    """

    @pytest.fixture(autouse=True)
    def reset_counters(self, monkeypatch):
        """Counters are module-level globals; reset before each test."""
        monkeypatch.setattr(gtv, "PASS_COUNT", 0)
        monkeypatch.setattr(gtv, "FAIL_COUNT", 0)
        monkeypatch.setattr(gtv, "WARN_COUNT", 0)
        monkeypatch.setattr(gtv, "SKIP_COUNT", 0)

    def _patch_single_direction(self, monkeypatch, from_st="NY", to_st="ALB"):
        """Stub the route topology so the loop processes exactly one direction."""
        class _FakeRoute:
            stations = (from_st, to_st)

        monkeypatch.setattr(gtv, "get_routes_for_data_source", lambda _ds: [_FakeRoute()])
        monkeypatch.setattr(gtv, "get_station_name", lambda code: code)
        monkeypatch.setattr(gtv, "httpx", _StubHttpx())

    def test_empty_gt_with_tr_departures_emits_warn(self, monkeypatch):
        """GT empty but TR has departures -> WARN (was silent SKIP). #1230."""
        self._patch_single_direction(monkeypatch)
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_departures",
            lambda *_a, **_kw: [_tr(minutes_offset=10, dest="ALB")],
        )

        tested = gtv.run_validation_loop(
            gt_arrivals=[],
            data_source="AMTRAK",
            base_url="http://test",
            tolerance=2.0,
            verbose=False,
        )

        # _deduplicated_route_directions yields both forward and reverse
        # directions for each route, so a single Route -> 2 tested directions.
        assert tested == 2
        assert gtv.WARN_COUNT == 2, "expected WARN per direction when GT empty but TR has data"
        assert gtv.SKIP_COUNT == 0, "must not SKIP when TR has departures"
        assert gtv.FAIL_COUNT == 0

    def test_empty_gt_and_empty_tr_still_skips(self, monkeypatch):
        """Both feeds empty is a legitimate quiet window -> SKIP, not WARN."""
        self._patch_single_direction(monkeypatch)
        monkeypatch.setattr(gtv, "fetch_trackrat_departures", lambda *_a, **_kw: [])

        tested = gtv.run_validation_loop(
            gt_arrivals=[],
            data_source="AMTRAK",
            base_url="http://test",
            tolerance=2.0,
            verbose=False,
        )

        assert tested == 2
        assert gtv.SKIP_COUNT == 2
        assert gtv.WARN_COUNT == 0
        assert gtv.FAIL_COUNT == 0


class _StubHttpx:
    """Minimal httpx replacement so run_validation_loop can construct a Client()."""

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def close(self):
            pass


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


# --- Tests for find_stop_order_inversions (issue #1538) ---


class TestFindStopOrderInversions:
    """Pure stop-order comparison logic: TrackRat order vs provider geographic order."""

    def test_identical_order_no_inversions(self):
        order = ["NY", "SE", "NP", "MP"]
        assert find_stop_order_inversions(order, order) == []

    def test_1530_shape_detected(self):
        """The #1530 bug: Newark Penn (NP) rendered before Secaucus (SE)."""
        tr = ["NY", "NP", "SE"]  # discovery-created SE shoved to the end in TrackRat
        njt = ["NY", "SE", "NP"]  # provider's geographic order
        assert find_stop_order_inversions(tr, njt) == [("NP", "SE")]

    def test_reverse_order_flags_each_adjacent_pair(self):
        tr = ["MP", "NP", "SE", "NY"]
        njt = ["NY", "SE", "NP", "MP"]
        # Every adjacent pair in the fully-reversed common subsequence is inverted.
        assert find_stop_order_inversions(tr, njt) == [
            ("MP", "NP"),
            ("NP", "SE"),
            ("SE", "NY"),
        ]

    def test_ignores_stations_not_in_reference(self):
        """A TrackRat-only station (not in the provider list) is ignored, not flagged."""
        tr = ["NY", "XX", "SE", "NP"]  # XX only in TrackRat
        njt = ["NY", "SE", "NP"]
        assert find_stop_order_inversions(tr, njt) == []

    def test_ignores_stations_not_in_trackrat(self):
        """A reference-only station is ignored; remaining common order is consistent."""
        tr = ["NY", "SE", "NP"]
        njt = ["NY", "SE", "EX", "NP"]  # EX only in the provider list
        assert find_stop_order_inversions(tr, njt) == []

    def test_common_subset_inversion_still_detected(self):
        tr = ["NY", "NP", "XX", "SE"]  # XX ignored; NP before SE is still an inversion
        njt = ["NY", "SE", "NP"]
        assert find_stop_order_inversions(tr, njt) == [("NP", "SE")]

    def test_empty_trackrat_order(self):
        assert find_stop_order_inversions([], ["NY", "SE", "NP"]) == []

    def test_empty_reference_order(self):
        assert find_stop_order_inversions(["NY", "SE", "NP"], []) == []

    def test_duplicate_codes_use_first_occurrence(self):
        """A repeated code keeps its first-occurrence position on both sides."""
        tr = ["NY", "SE", "SE", "NP"]  # SE duplicated in TrackRat
        njt = ["NY", "SE", "NP"]
        assert find_stop_order_inversions(tr, njt) == []

    def test_single_common_station_no_inversion(self):
        assert find_stop_order_inversions(["NY", "AA"], ["NY", "BB"]) == []


# --- Tests for check_njt_stop_order orchestration (issue #1538) ---


class TestCheckNjtStopOrder:
    """Orchestration: sampling, FAIL vs WARN, and PASS counting."""

    @pytest.fixture(autouse=True)
    def reset_counters(self, monkeypatch):
        monkeypatch.setattr(gtv, "PASS_COUNT", 0)
        monkeypatch.setattr(gtv, "FAIL_COUNT", 0)
        monkeypatch.setattr(gtv, "WARN_COUNT", 0)
        monkeypatch.setattr(gtv, "SKIP_COUNT", 0)
        monkeypatch.setattr(gtv, "httpx", _StubHttpx())

    def test_inversion_reported_as_fail_by_default(self, monkeypatch):
        monkeypatch.setattr(
            gtv, "fetch_njt_train_stop_orders", lambda ids: {"3701": ["NY", "SE", "NP"]}
        )
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_train_stop_order",
            lambda *_a, **_kw: ["NY", "NP", "SE"],  # SE after NP -> inversion
        )
        gt = [_gt(train_id="3701")]

        check_njt_stop_order("http://test", gt, verbose=True, warn_only=False)

        assert gtv.FAIL_COUNT == 1
        assert gtv.WARN_COUNT == 0
        assert gtv.PASS_COUNT == 0

    def test_inversion_reported_as_warn_when_flagged(self, monkeypatch):
        monkeypatch.setattr(
            gtv, "fetch_njt_train_stop_orders", lambda ids: {"3701": ["NY", "SE", "NP"]}
        )
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_train_stop_order",
            lambda *_a, **_kw: ["NY", "NP", "SE"],
        )
        gt = [_gt(train_id="3701")]

        check_njt_stop_order("http://test", gt, verbose=False, warn_only=True)

        assert gtv.WARN_COUNT == 1
        assert gtv.FAIL_COUNT == 0
        assert gtv.PASS_COUNT == 0

    def test_correct_order_is_pass(self, monkeypatch):
        monkeypatch.setattr(
            gtv, "fetch_njt_train_stop_orders", lambda ids: {"3701": ["NY", "SE", "NP"]}
        )
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_train_stop_order",
            lambda *_a, **_kw: ["NY", "SE", "NP"],
        )
        gt = [_gt(train_id="3701")]

        check_njt_stop_order("http://test", gt, verbose=False, warn_only=False)

        assert gtv.PASS_COUNT == 1
        assert gtv.FAIL_COUNT == 0
        assert gtv.WARN_COUNT == 0

    def test_no_train_ids_is_noop(self, monkeypatch):
        called = {"njt": False}

        def _should_not_call(_ids):
            called["njt"] = True
            return {}

        monkeypatch.setattr(gtv, "fetch_njt_train_stop_orders", _should_not_call)
        gt = [_gt()]  # no train_id

        check_njt_stop_order("http://test", gt, verbose=False, warn_only=False)

        assert called["njt"] is False
        assert gtv.FAIL_COUNT == 0
        assert gtv.WARN_COUNT == 0
        assert gtv.PASS_COUNT == 0

    def test_unavailable_stop_list_is_skipped_not_failed(self, monkeypatch):
        # Provider stop list unavailable for the sampled train -> omitted from map.
        monkeypatch.setattr(gtv, "fetch_njt_train_stop_orders", lambda ids: {})
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_train_stop_order",
            lambda *_a, **_kw: ["NY", "NP", "SE"],
        )
        gt = [_gt(train_id="3701")]

        check_njt_stop_order("http://test", gt, verbose=False, warn_only=False)

        assert gtv.FAIL_COUNT == 0
        assert gtv.WARN_COUNT == 0
        assert gtv.PASS_COUNT == 0

    def test_sampling_capped_by_sample_size(self, monkeypatch):
        captured = {}

        def _capture(ids):
            captured["ids"] = ids
            return {}

        monkeypatch.setattr(gtv, "fetch_njt_train_stop_orders", _capture)
        gt = [_gt(train_id=str(9000 + i)) for i in range(20)]

        check_njt_stop_order(
            "http://test", gt, verbose=False, warn_only=False, sample_size=5
        )

        assert len(captured["ids"]) == 5


# --- Tests for fetch_trackrat_train_stop_order payload parsing (issue #1538) ---


class _FakeResponse:
    """Minimal httpx.Response stand-in for parsing tests (no mocks of gtv)."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """httpx.Client stand-in returning a fixed TrainDetailsResponse payload."""

    def __init__(self, payload: dict):
        self._payload = payload

    def get(self, url, timeout=None):
        return _FakeResponse(self._payload)


class TestFetchTrackratTrainStopOrder:
    """The /api/v2/trains/{id} response nests stops under ``train`` (issue #1538).

    Reading them from the top level silently returns [] for every real
    response, turning the whole stop-order check into a production no-op while
    the monkeypatched orchestration tests stay green. These tests exercise the
    real parser against the actual TrainDetailsResponse shape.
    """

    def test_reads_stops_from_train_payload_in_sequence_order(self):
        # Real response shape: {"train": {"stops": [...]}}, out of order to
        # prove the sort by stop_sequence is applied.
        payload = {
            "train": {
                "stops": [
                    {"station": {"code": "NP"}, "stop_sequence": 2},
                    {"station": {"code": "NY"}, "stop_sequence": 0},
                    {"station": {"code": "SE"}, "stop_sequence": 1},
                ]
            }
        }
        order = fetch_trackrat_train_stop_order(
            _FakeClient(payload), "http://test", "3701"
        )
        assert order == ["NY", "SE", "NP"], (
            "stops must be read from train.stops and sorted by stop_sequence; "
            f"got {order}"
        )

    def test_top_level_stops_are_ignored(self):
        # A well-formed response has no top-level "stops"; the old code read
        # this and got []. Assert we do not regress to that path.
        payload = {
            "train": {
                "stops": [
                    {"station": {"code": "NY"}, "stop_sequence": 0},
                    {"station": {"code": "TR"}, "stop_sequence": 1},
                ]
            }
        }
        order = fetch_trackrat_train_stop_order(
            _FakeClient(payload), "http://test", "3701"
        )
        assert order == ["NY", "TR"]

    def test_missing_train_key_returns_empty_list(self):
        order = fetch_trackrat_train_stop_order(
            _FakeClient({}), "http://test", "3701"
        )
        assert order == []


# --- Tests for _norm_train_number (issue #1575) ---


class TestNormTrainNumber:
    """SEPTA RR train numbers are unique per service day; the digit sequence
    identifies the train regardless of the inconsistent line prefix between
    SEPTA's Arrivals board and TrackRat's trip_short_name-derived id."""

    def test_strips_line_prefix(self):
        assert _norm_train_number("CHW8312") == "8312"

    def test_bare_number(self):
        assert _norm_train_number("8312") == "8312"

    def test_different_prefixes_same_number_match(self):
        # SEPTA board 'WTR8360' and TrackRat 'CHW8360' must normalize identically.
        assert _norm_train_number("WTR8360") == _norm_train_number("CHW8360") == "8360"

    def test_empty(self):
        assert _norm_train_number("") == ""

    def test_non_numeric_falls_back_to_upper(self):
        assert _norm_train_number("abc") == "ABC"

    def test_non_numeric_whitespace_stripped(self):
        assert _norm_train_number("  ab ") == "AB"


# --- Tests for compare_by_train_number (issue #1575) ---


class TestCompareByTrainNumber:
    """Per-station matching keyed on train number (not route topology).

    This is the core of the #1575 fix: SEPTA RR trips short-turn / through-route,
    so matching by (origin, terminal) pair yielded 0 PASS. Matching on the train
    number at one station guarantees overlap whenever both sources see the train.
    """

    def test_matches_on_number_within_tolerance(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [_tr(minutes_offset=11, train_id="CHW8312")]  # +1min, prefix differs
        result = compare_by_train_number(gt, tr, "SEPR90004", tolerance_minutes=2.0)

        assert len(result.matches) == 1
        m = result.matches[0]
        assert m.delta_seconds == 60
        assert m.within_tolerance is True
        assert result.gt_only == []
        assert result.tr_only == []

    def test_match_outside_tolerance_flagged(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [_tr(minutes_offset=15, train_id="8312")]  # +5 min, over 2-min tolerance
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert len(result.matches) == 1
        assert result.matches[0].delta_seconds == 300
        assert result.matches[0].within_tolerance is False

    def test_signed_delta_negative_when_tr_earlier(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [_tr(minutes_offset=9, train_id="8312")]  # 1 min earlier
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert result.matches[0].delta_seconds == -60
        assert result.matches[0].within_tolerance is True

    def test_gt_train_not_in_trackrat_is_gt_only(self):
        """The old 0-PASS killer: a GT train TrackRat lacks is non-overlap, not FAIL."""
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [_tr(minutes_offset=10, train_id="9999")]
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert result.matches == []
        assert len(result.gt_only) == 1
        assert result.gt_only[0].train_id == "8312"
        assert len(result.tr_only) == 1
        assert result.tr_only[0].train_id == "9999"

    def test_trackrat_train_not_in_gt_is_tr_only(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [
            _tr(minutes_offset=10, train_id="8312"),
            _tr(minutes_offset=20, train_id="7777"),
        ]
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert len(result.matches) == 1
        assert len(result.tr_only) == 1
        assert result.tr_only[0].train_id == "7777"

    def test_gt_without_train_number_is_gt_only(self):
        gt = [_gt(minutes_offset=10, train_id="")]
        tr = [_tr(minutes_offset=10, train_id="8312")]
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert result.matches == []
        assert len(result.gt_only) == 1
        assert len(result.tr_only) == 1  # the numbered TR nobody referenced

    def test_duplicate_tr_number_surfaces_extra_in_tr_only(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        tr = [
            _tr(minutes_offset=10, train_id="8312", dest="A"),
            _tr(minutes_offset=12, train_id="CHW8312", dest="B"),  # same number, dup
        ]
        result = compare_by_train_number(gt, tr, "S", tolerance_minutes=2.0)

        assert len(result.matches) == 1
        assert len(result.tr_only) == 1  # the duplicate isn't silently dropped

    def test_empty_gt(self):
        tr = [_tr(minutes_offset=10, train_id="8312")]
        result = compare_by_train_number([], tr, "S", tolerance_minutes=2.0)

        assert result.matches == []
        assert result.gt_only == []
        assert len(result.tr_only) == 1

    def test_empty_tr(self):
        gt = [_gt(minutes_offset=10, train_id="8312")]
        result = compare_by_train_number(gt, [], "S", tolerance_minutes=2.0)

        assert result.matches == []
        assert len(result.gt_only) == 1
        assert result.tr_only == []

    def test_station_recorded_on_result(self):
        result = compare_by_train_number([], [], "SEPR90228", tolerance_minutes=2.0)
        assert result.station == "SEPR90228"


# --- Tests for _parse_trackrat_departures (issue #1575 refactor) ---


class TestParseTrackratDepartures:
    """The shared /trains/departures response parser, extracted so
    fetch_trackrat_station_departures can reuse it."""

    def test_parses_departure_shape(self):
        payload = {
            "departures": [
                {
                    "train_id": "CHW8312",
                    "destination": "Chestnut Hill West",
                    "observation_type": "OBSERVED",
                    "is_cancelled": False,
                    "line": {"code": "CHW", "color": "#006600"},
                    "arrival": {"code": "SEPR90801"},
                    "departure": {
                        "scheduled_time": "2026-02-22T15:10:00+00:00",
                        "updated_time": "2026-02-22T15:12:00+00:00",
                        "actual_time": None,
                        "track": "3",
                    },
                }
            ]
        }
        deps = gtv._parse_trackrat_departures(payload)

        assert len(deps) == 1
        d = deps[0]
        assert d.train_id == "CHW8312"
        assert d.destination_code == "SEPR90801"
        assert d.observation_type == "OBSERVED"
        assert d.track == "3"
        # Best-available time is updated (actual absent); scheduled preserved too.
        assert d.departure_time == d.updated_time
        assert d.scheduled_time is not None

    def test_skips_entries_without_any_time(self):
        payload = {"departures": [{"train_id": "X", "departure": {}}]}
        assert gtv._parse_trackrat_departures(payload) == []

    def test_empty_payload(self):
        assert gtv._parse_trackrat_departures({}) == []


# --- Tests for run_septa_rr_by_train_number classification (issue #1575) ---


class TestRunSeptaRrByTrainNumber:
    """End-to-end classification: PASS on time-agreement, FAIL only on a genuine
    time disagreement, and near-term non-overlap as WARN (never the old FAIL)."""

    @pytest.fixture(autouse=True)
    def reset_counters(self, monkeypatch):
        monkeypatch.setattr(gtv, "PASS_COUNT", 0)
        monkeypatch.setattr(gtv, "FAIL_COUNT", 0)
        monkeypatch.setattr(gtv, "WARN_COUNT", 0)
        monkeypatch.setattr(gtv, "SKIP_COUNT", 0)
        monkeypatch.setattr(gtv, "httpx", _StubHttpx())

    def test_matched_in_tolerance_is_pass(self, monkeypatch):
        gt = [_gt(minutes_offset=10, station="SEPR90004", train_id="8312")]
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_station_departures",
            lambda *_a, **_kw: [_tr(minutes_offset=11, train_id="CHW8312")],
        )

        stations = gtv.run_septa_rr_by_train_number(gt, "http://test", 2.0, False)

        assert stations == 1
        assert gtv.PASS_COUNT == 1
        assert gtv.FAIL_COUNT == 0

    def test_matched_outside_tolerance_is_fail(self, monkeypatch):
        gt = [_gt(minutes_offset=10, station="SEPR90004", train_id="8312")]
        monkeypatch.setattr(
            gtv,
            "fetch_trackrat_station_departures",
            lambda *_a, **_kw: [_tr(minutes_offset=20, train_id="8312")],
        )

        gtv.run_septa_rr_by_train_number(gt, "http://test", 2.0, False)

        assert gtv.FAIL_COUNT == 1
        assert gtv.PASS_COUNT == 0

    def test_near_term_non_overlap_is_warn_not_fail(self, monkeypatch):
        """The regression this issue is about: a near-term GT train TrackRat
        doesn't have is now WARN, not FAIL."""
        gt = [_gt(minutes_offset=5, station="SEPR90004", train_id="8312")]
        gt[0].minutes_away = 5
        monkeypatch.setattr(
            gtv, "fetch_trackrat_station_departures", lambda *_a, **_kw: []
        )

        gtv.run_septa_rr_by_train_number(
            gt, "http://test", 2.0, False, far_future_minutes=12
        )

        assert gtv.FAIL_COUNT == 0
        assert gtv.WARN_COUNT == 1

    def test_far_future_non_overlap_is_silent_non_verbose(self, monkeypatch):
        gt = [_gt(minutes_offset=40, station="SEPR90004", train_id="8312")]
        gt[0].minutes_away = 40
        monkeypatch.setattr(
            gtv, "fetch_trackrat_station_departures", lambda *_a, **_kw: []
        )

        gtv.run_septa_rr_by_train_number(
            gt, "http://test", 2.0, False, far_future_minutes=12
        )

        assert gtv.FAIL_COUNT == 0
        assert gtv.WARN_COUNT == 0

    def test_window_filters_far_future_gt_before_fetch(self, monkeypatch):
        """GT beyond the time window is dropped before a station is even fetched."""
        future = datetime.now(timezone.utc) + timedelta(minutes=200)
        gt = [
            GroundTruthArrival(
                station_code="SEPR90004",
                destination_code="",
                expected_time=future,
                line_color="",
                headsign="8312",
                minutes_away=200,
                train_id="8312",
            )
        ]
        called = {"fetch": False}

        def _fetch(*_a, **_kw):
            called["fetch"] = True
            return []

        monkeypatch.setattr(gtv, "fetch_trackrat_station_departures", _fetch)

        stations = gtv.run_septa_rr_by_train_number(
            gt, "http://test", 2.0, False, gt_window_minutes=120
        )

        assert stations == 0
        assert called["fetch"] is False

    def test_two_stations_tested_independently(self, monkeypatch):
        gt = [
            _gt(minutes_offset=10, station="SEPR90004", train_id="8312"),
            _gt(minutes_offset=10, station="SEPR90228", train_id="4256"),
        ]

        def _fetch(_client, _base, station, _ds):
            # Only the first station's train is present in TrackRat.
            if station == "SEPR90004":
                return [_tr(minutes_offset=10, train_id="8312")]
            return []

        monkeypatch.setattr(gtv, "fetch_trackrat_station_departures", _fetch)

        stations = gtv.run_septa_rr_by_train_number(gt, "http://test", 2.0, False)

        assert stations == 2
        assert gtv.PASS_COUNT == 1  # SEPR90004 matched
        assert gtv.WARN_COUNT == 1  # SEPR90228 near-term non-overlap
        assert gtv.FAIL_COUNT == 0


class TestSeptaRrArrivalFromEntry:
    """_septa_rr_arrival_from_entry: entry -> GroundTruthArrival conversion.

    Guards the #1591 fix: short-turn trains whose destination isn't in
    _SEPTA_RR_DEST_TO_CODE must be KEPT (the per-station train-number matcher
    ignores destination), while resolved terminating arrivals are still dropped.
    """

    ET = ZoneInfo("America/New_York")
    # NOW is 15:00 UTC == 10:00 ET; a 10:05 ET depart is 5 min away.
    DEPART = "2026-02-22 10:05:00"

    def _entry(self, destination: str, train_id: str = "8360") -> dict:
        return {
            "destination": destination,
            "depart_time": self.DEPART,
            "train_id": train_id,
            "track": "3",
        }

    def test_unresolved_short_turn_destination_is_kept(self):
        # "Malvern" is a real SEPTA short-turn not in _SEPTA_RR_DEST_TO_CODE.
        entry = self._entry("Malvern", train_id="9821")
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90701", NOW, self.ET)

        assert arrival is not None, "short-turn train must not be dropped"
        assert arrival.train_id == "9821"
        assert arrival.station_code == "SEPR90701"
        assert arrival.destination_code == ""  # unresolved -> empty, not dropped
        assert arrival.minutes_away == 5

    def test_resolved_terminating_arrival_is_dropped(self):
        # destination "Trenton" resolves to SEPR90701; querying that same station
        # means the train terminates here with no onward departure.
        entry = self._entry("Trenton", train_id="777")
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90701", NOW, self.ET)

        assert arrival is None

    def test_resolved_through_destination_is_kept_with_code(self):
        # destination "Trenton" (SEPR90701) queried at a different station (30th
        # Street, SEPR90004) is a normal through departure and keeps its code.
        entry = self._entry("Trenton", train_id="4256")
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90004", NOW, self.ET)

        assert arrival is not None
        assert arrival.destination_code == "SEPR90701"
        assert arrival.train_id == "4256"

    def test_unparseable_time_is_dropped(self):
        entry = {"destination": "Malvern", "depart_time": "", "train_id": "1"}
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90701", NOW, self.ET)

        assert arrival is None

    def test_late_train_applies_status_delay_to_schedule(self):
        # SEPTA's depart_time (10:01, sched+dwell) ignores the "6 min" status;
        # the real-time estimate is sched (10:00) + 6 min = 10:06. Comparing
        # against depart_time here would flag a correctly-delayed TrackRat
        # departure as a failure (the bug this fix addresses).
        entry = {
            "destination": "Malvern",
            "sched_time": "2026-02-22 10:00:00",
            "depart_time": "2026-02-22 10:01:00",
            "status": "6 min",
            "train_id": "9756",
        }
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90004", NOW, self.ET)

        assert arrival is not None
        assert arrival.expected_time == datetime(2026, 2, 22, 10, 6, tzinfo=self.ET)
        assert arrival.minutes_away == 6

    def test_on_time_train_uses_depart_time(self):
        # "On Time" (delay 0) keeps the scheduled depart_time (10:05), which
        # carries SEPTA's fixed station dwell over the raw sched_time (10:04).
        entry = {
            "destination": "Malvern",
            "sched_time": "2026-02-22 10:04:00",
            "depart_time": "2026-02-22 10:05:00",
            "status": "On Time",
            "train_id": "8360",
        }
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90004", NOW, self.ET)

        assert arrival is not None
        assert arrival.expected_time == datetime(2026, 2, 22, 10, 5, tzinfo=self.ET)
        assert arrival.minutes_away == 5

    def test_status_delay_without_schedule_falls_back_to_depart(self):
        # No sched_time to anchor the delay on -> fall back to depart_time rather
        # than dropping the entry or mis-applying the delay.
        entry = {
            "destination": "Malvern",
            "depart_time": "2026-02-22 10:05:00",
            "status": "9 min",
            "train_id": "5",
        }
        arrival = _septa_rr_arrival_from_entry(entry, "SEPR90004", NOW, self.ET)

        assert arrival is not None
        assert arrival.expected_time == datetime(2026, 2, 22, 10, 5, tzinfo=self.ET)


class TestParseSeptaStatusMinutes:
    """_parse_septa_status_minutes: SEPTA Arrivals `status` -> minutes late."""

    def test_on_time_is_zero(self):
        assert _parse_septa_status_minutes("On Time") == 0

    def test_on_time_case_insensitive(self):
        assert _parse_septa_status_minutes("on time") == 0

    def test_minutes_late(self):
        assert _parse_septa_status_minutes("6 min") == 6

    def test_double_digit_minutes(self):
        assert _parse_septa_status_minutes("14 min") == 14

    def test_whitespace_tolerant(self):
        assert _parse_septa_status_minutes("  3 min  ") == 3

    def test_empty_is_none(self):
        assert _parse_septa_status_minutes("") is None

    def test_unknown_status_is_none(self):
        # "Suspended" / "Canceled" carry no usable delay -> None (not 0).
        assert _parse_septa_status_minutes("Suspended") is None


class TestProbeLineDeparturesLineCodeFilter:
    """Line-coverage probe must attribute departures to the probed line's own
    ``line_codes``, so a live *sibling* line on a shared segment can't mask a
    line that has actually gone dark (codex review on PR #1597).

    Example: NJT Bergen County's busiest segment (MZ->SF) is also on the Main
    Line, so ``data_sources=NJT`` alone returns Main Line trains even when
    Bergen County is empty.
    """

    STATIONS = ["A", "B", "C", "D"]

    def _patch_fetch(self, monkeypatch, segment_deps):
        """Patch fetch_trackrat_departures to return per-(origin,dest) deps."""

        def fake_fetch(client, base_url, origin, dest, source):
            return list(segment_deps.get((origin, dest), []))

        monkeypatch.setattr(gtv, "fetch_trackrat_departures", fake_fetch)

    def test_sibling_line_alone_reports_empty(self, monkeypatch):
        # Every segment returns ONLY a sibling ("NE") train; the probed line is
        # "NC". With the filter, no segment counts -> line correctly empty.
        sibling = [_tr(train_id="main", line_code="NE")]
        seg = {
            (a, b): sibling
            for a in self.STATIONS
            for b in self.STATIONS
            if a != b
        }
        self._patch_fetch(monkeypatch, seg)
        deps, _direction = gtv._probe_line_departures(
            None, "http://x", "NJT", self.STATIONS, frozenset({"NC"})
        )
        assert deps == [], "sibling-only segment must not mark the line as live"

    def test_own_line_on_later_segment_is_found(self, monkeypatch):
        # Busiest segment (C->D) has only a sibling; the probed line's real
        # train sits on a later candidate (A->B). Probe must skip the masked
        # segment and surface the genuine one.
        seg = {
            ("C", "D"): [_tr(train_id="main", line_code="NE")],
            ("D", "C"): [_tr(train_id="main", line_code="NE")],
            ("A", "B"): [_tr(train_id="bergen", line_code="NC")],
        }
        self._patch_fetch(monkeypatch, seg)
        deps, direction = gtv._probe_line_departures(
            None, "http://x", "NJT", self.STATIONS, frozenset({"NC"})
        )
        assert [d.train_id for d in deps] == ["bergen"]
        assert all(d.line_code == "NC" for d in deps)
        assert direction == "A->B"

    def test_mixed_segment_keeps_only_own_line(self, monkeypatch):
        # A segment carrying both lines returns non-empty, but only the probed
        # line's departures are retained.
        seg = {
            ("C", "D"): [
                _tr(train_id="main", line_code="NE"),
                _tr(train_id="bergen", line_code="NC"),
            ],
        }
        self._patch_fetch(monkeypatch, seg)
        deps, direction = gtv._probe_line_departures(
            None, "http://x", "NJT", self.STATIONS, frozenset({"NC"})
        )
        assert [d.train_id for d in deps] == ["bergen"]
        assert direction == "C->D"

    def test_empty_line_codes_falls_back_to_any_train(self, monkeypatch):
        # LIRR terminal variants have no line_codes (resolved geometrically);
        # filtering by an empty set would drop every train, so the probe must
        # keep the unfiltered any-train behavior.
        seg = {("C", "D"): [_tr(train_id="main", line_code="NE")]}
        self._patch_fetch(monkeypatch, seg)
        deps, direction = gtv._probe_line_departures(
            None, "http://x", "LIRR", self.STATIONS, frozenset()
        )
        assert [d.train_id for d in deps] == ["main"]
        assert direction == "C->D"
