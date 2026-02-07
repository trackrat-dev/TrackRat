"""Tests for MTA common utilities (departure inference, journey metadata, completion)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from trackrat.collectors.mta_common import (
    LIRR_ORIGIN_TERMINALS,
    MNR_ORIGIN_TERMINALS,
    ORIGIN_TRAVEL_BUFFER,
    build_complete_stops,
    check_journey_completed,
    infer_missing_origin,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.models.database import JourneyStop, TrainJourney


def _make_stop(
    station_code: str,
    stop_sequence: int,
    scheduled_arrival: datetime,
    actual_departure: datetime | None = None,
    actual_arrival: datetime | None = None,
    has_departed_station: bool = False,
    departure_source: str | None = None,
) -> MagicMock:
    """Create a mock JourneyStop with all required fields."""
    stop = MagicMock(spec=JourneyStop)
    stop.station_code = station_code
    stop.stop_sequence = stop_sequence
    stop.scheduled_arrival = scheduled_arrival
    stop.actual_departure = actual_departure
    stop.actual_arrival = actual_arrival
    stop.has_departed_station = has_departed_station
    stop.departure_source = departure_source
    return stop


class TestUpdateStopDepartureStatus:
    """Tests for update_stop_departure_status()."""

    def test_stop_with_actual_departure_in_past_is_marked_departed(self):
        """Path A: stop has actual_departure in the past -> departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "time_inference"

    def test_stop_with_actual_arrival_in_past_is_marked_departed(self):
        """Path A fallback: stop has actual_arrival (no departure) in the past."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_arrival=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True

    def test_stop_with_actual_departure_in_future_is_not_departed(self):
        """Path A: stop with actual_departure in the future is not departed."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=30)

        stop = _make_stop("GCT", 1, future, actual_departure=future)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is False

    def test_stop_with_scheduled_time_past_grace_period_is_departed(self):
        """Path B: no actuals, scheduled time + 2min grace < now -> departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, scheduled_arrival=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "time_inference"

    def test_stop_with_scheduled_time_within_grace_period_is_not_departed(self):
        """Path B: scheduled time + grace < now is false -> not departed."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(seconds=30)

        stop = _make_stop("GCT", 1, scheduled_arrival=recent)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is False

    def test_sequential_consistency_fills_earlier_stops(self):
        """Path C: if stop 3 is departed, stops 1 and 2 must be too."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)

        stop1 = _make_stop("A", 1, scheduled_arrival=past)
        stop2 = _make_stop("B", 2, scheduled_arrival=past)
        stop3 = _make_stop("C", 3, scheduled_arrival=past, actual_departure=past)

        # Stop 3 has actual_departure in the past, but stops 1 and 2 have no actuals.
        # However, stops 1 and 2 also have scheduled_arrival in the past,
        # so Path B should mark them as departed directly.
        # For a purer test, set scheduled_arrival in the future for stops 1 and 2.
        stop1.scheduled_arrival = now + timedelta(minutes=10)
        stop1.actual_departure = None
        stop1.actual_arrival = None
        stop2.scheduled_arrival = now + timedelta(minutes=10)
        stop2.actual_departure = None
        stop2.actual_arrival = None

        update_stop_departure_status([stop1, stop2, stop3], now)

        assert stop3.has_departed_station is True  # Path A
        assert stop1.has_departed_station is True  # Path C (sequential consistency)
        assert stop2.has_departed_station is True  # Path C (sequential consistency)
        assert stop1.departure_source == "sequential_consistency"
        assert stop2.departure_source == "sequential_consistency"

    def test_sequential_consistency_sets_actual_times_from_schedule(self):
        """Path C: sequential fill uses scheduled_arrival for missing actual times."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)
        scheduled = now - timedelta(minutes=20)

        stop1 = _make_stop("A", 1, scheduled_arrival=scheduled)
        stop1.actual_departure = None
        stop1.actual_arrival = None
        stop1.scheduled_arrival = now + timedelta(
            minutes=10
        )  # Future, so Path B won't trigger

        stop2 = _make_stop("B", 2, scheduled_arrival=past, actual_departure=past)

        update_stop_departure_status([stop1, stop2], now)

        assert stop1.has_departed_station is True
        assert stop1.actual_departure == stop1.scheduled_arrival
        assert stop1.actual_arrival == stop1.scheduled_arrival

    def test_empty_stops_list_does_not_raise(self):
        """Empty list should be handled gracefully."""
        now = datetime.now(timezone.utc)
        update_stop_departure_status([], now)  # Should not raise

    def test_stops_without_stop_sequence_are_handled(self):
        """Stops with stop_sequence=None should not break the function."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        stop.stop_sequence = None

        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True

    def test_preserves_existing_departure_source(self):
        """Should not overwrite departure_source if already set."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        stop.departure_source = "api_explicit"

        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "api_explicit"

    def test_multi_stop_journey_realistic(self):
        """Realistic MNR journey: GCT -> 125th -> Croton with mixed states."""
        now = datetime.now(timezone.utc)

        stop_gct = _make_stop(
            "GCT",
            1,
            scheduled_arrival=now - timedelta(minutes=60),
            actual_departure=now - timedelta(minutes=58),
        )
        stop_125 = _make_stop(
            "M125",
            2,
            scheduled_arrival=now - timedelta(minutes=50),
            actual_arrival=now - timedelta(minutes=48),
        )
        stop_croton = _make_stop(
            "MCRH",
            3,
            scheduled_arrival=now + timedelta(minutes=20),
        )

        update_stop_departure_status([stop_gct, stop_125, stop_croton], now)

        assert stop_gct.has_departed_station is True  # Path A: actual_departure in past
        assert stop_125.has_departed_station is True  # Path A: actual_arrival in past
        assert stop_croton.has_departed_station is False  # Future scheduled, no actuals


class TestUpdateJourneyMetadata:
    """Tests for update_journey_metadata()."""

    def test_sets_last_updated_at(self):
        """Should set last_updated_at to now."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = 0

        update_journey_metadata(journey, now)

        assert journey.last_updated_at == now

    def test_increments_update_count(self):
        """Should increment update_count."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = 5

        update_journey_metadata(journey, now)

        assert journey.update_count == 6

    def test_initializes_update_count_from_none(self):
        """Should handle None update_count (first update)."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = None

        update_journey_metadata(journey, now)

        assert journey.update_count == 1


class TestCheckJourneyCompleted:
    """Tests for check_journey_completed()."""

    def test_marks_completed_when_terminal_stop_departed(self):
        """Journey is completed when terminal stop has departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop1 = _make_stop("GCT", 1, past, actual_departure=past)
        stop1.has_departed_station = True
        stop2 = _make_stop("MPOK", 2, past, actual_arrival=past)
        stop2.has_departed_station = True

        check_journey_completed(journey, [stop1, stop2])

        assert journey.is_completed is True
        assert journey.actual_arrival == past

    def test_not_completed_when_terminal_stop_not_departed(self):
        """Journey is not completed when terminal stop hasn't departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)
        future = now + timedelta(minutes=20)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop1 = _make_stop("GCT", 1, past)
        stop1.has_departed_station = True
        stop2 = _make_stop("MPOK", 2, future)
        stop2.has_departed_station = False

        check_journey_completed(journey, [stop1, stop2])

        assert journey.is_completed is False

    def test_empty_stops_does_not_raise(self):
        """Empty stops list should be handled gracefully."""
        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        check_journey_completed(journey, [])

        assert journey.is_completed is False

    def test_does_not_revert_completed_journey(self):
        """Should not change is_completed if already True."""
        now = datetime.now(timezone.utc)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = True

        stop = _make_stop("GCT", 1, now)
        stop.has_departed_station = False

        check_journey_completed(journey, [stop])

        # Should still be True (not reverted)
        assert journey.is_completed is True

    def test_uses_scheduled_arrival_as_fallback(self):
        """Should use scheduled_arrival when actual_arrival is None."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop = _make_stop("MPOK", 1, scheduled_arrival=past)
        stop.has_departed_station = True
        stop.actual_arrival = None

        check_journey_completed(journey, [stop])

        assert journey.is_completed is True
        assert journey.actual_arrival == past

    def test_finds_terminal_by_max_stop_sequence(self):
        """Terminal stop is the one with highest stop_sequence, not last in list."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        # Stops out of order in list
        stop_terminal = _make_stop("MPOK", 5, past, actual_arrival=past)
        stop_terminal.has_departed_station = True
        stop_mid = _make_stop("MCRH", 3, past)
        stop_mid.has_departed_station = True

        check_journey_completed(journey, [stop_mid, stop_terminal])

        assert journey.is_completed is True


def _make_arrival(
    station_code: str,
    arrival_time: datetime,
    departure_time: datetime | None = None,
    delay_seconds: int = 0,
    track: str | None = None,
) -> MagicMock:
    """Create a mock GTFS-RT arrival (LirrArrival/MnrArrival compatible)."""
    arr = MagicMock()
    arr.station_code = station_code
    arr.arrival_time = arrival_time
    arr.departure_time = departure_time
    arr.delay_seconds = delay_seconds
    arr.track = track
    return arr


def _make_static_stop(
    station_code: str,
    stop_sequence: int,
    arrival_time: datetime,
    departure_time: datetime | None = None,
) -> dict:
    """Create a static stop dict matching GTFSService.get_static_stop_times() output."""
    return {
        "station_code": station_code,
        "stop_sequence": stop_sequence,
        "arrival_time": arrival_time,
        "departure_time": departure_time or arrival_time,
    }


class TestBuildCompleteStops:
    """Tests for build_complete_stops()."""

    def test_backfills_missing_origin_stop(self):
        """LIRR RT feed drops origin (GCT) from outbound trips.
        Static has GCT->WDD->JAM, RT only has WDD->JAM.
        Result should include GCT as a departed stop with scheduled times."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("GCT", 1, base, base + timedelta(minutes=1)),
            _make_static_stop("WDD", 2, base + timedelta(minutes=10)),
            _make_static_stop("JAM", 3, base + timedelta(minutes=20)),
        ]

        rt_arrivals = [
            _make_arrival(
                "WDD", base + timedelta(minutes=10), delay_seconds=60, track="3"
            ),
            _make_arrival("JAM", base + timedelta(minutes=20), delay_seconds=60),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        assert origin == "GCT"
        assert terminal == "JAM"
        assert len(merged) == 3

        # GCT: backfilled from static, marked as departed
        gct = merged[0]
        assert gct["station_code"] == "GCT"
        assert gct["stop_sequence"] == 1
        assert gct["scheduled_arrival"] == base
        assert gct["actual_arrival"] is None
        assert gct["actual_departure"] is None
        assert gct["track"] is None
        assert gct["has_departed"] is True

        # WDD: has RT data — actual_arrival is the predicted time (no delay added)
        wdd = merged[1]
        assert wdd["station_code"] == "WDD"
        assert wdd["stop_sequence"] == 2
        assert wdd["scheduled_arrival"] == base + timedelta(minutes=10)
        assert wdd["actual_arrival"] == base + timedelta(minutes=10)
        assert wdd["track"] == "3"
        assert wdd["has_departed"] is False

    def test_noop_merge_when_rt_has_all_stops(self):
        """When RT already has all stops (MNR typical case), merge is a no-op.
        All stops should use RT data, none marked as already departed."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("GCT", 1, base),
            _make_static_stop("M125", 2, base + timedelta(minutes=5)),
            _make_static_stop("MCRH", 3, base + timedelta(minutes=30)),
        ]

        rt_arrivals = [
            _make_arrival("GCT", base, delay_seconds=0, track="21"),
            _make_arrival("M125", base + timedelta(minutes=5), delay_seconds=30),
            _make_arrival("MCRH", base + timedelta(minutes=30), delay_seconds=30),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        assert origin == "GCT"
        assert terminal == "MCRH"
        assert len(merged) == 3

        # All stops should have RT actual data, none departed
        for stop in merged:
            assert stop["actual_arrival"] is not None
            assert stop["has_departed"] is False

        # GCT should have track from RT
        assert merged[0]["track"] == "21"

    def test_multiple_missing_origin_stops(self):
        """When RT is missing multiple stops at the beginning.
        Static: A->B->C->D, RT: C->D. A and B should be marked departed."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("A", 1, base),
            _make_static_stop("B", 2, base + timedelta(minutes=5)),
            _make_static_stop("C", 3, base + timedelta(minutes=10)),
            _make_static_stop("D", 4, base + timedelta(minutes=15)),
        ]

        rt_arrivals = [
            _make_arrival("C", base + timedelta(minutes=10)),
            _make_arrival("D", base + timedelta(minutes=15)),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        assert origin == "A"
        assert terminal == "D"
        assert len(merged) == 4
        assert merged[0]["has_departed"] is True  # A
        assert merged[1]["has_departed"] is True  # B
        assert merged[2]["has_departed"] is False  # C (has RT)
        assert merged[3]["has_departed"] is False  # D (has RT)

    def test_rt_stop_not_in_static_appended(self):
        """Safety fallback: RT has a stop not in static schedule.
        Should be appended and logged as a warning."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("GCT", 1, base),
            _make_static_stop("JAM", 2, base + timedelta(minutes=20)),
        ]

        rt_arrivals = [
            _make_arrival("JAM", base + timedelta(minutes=20)),
            _make_arrival("UNKNOWN", base + timedelta(minutes=25), track="5"),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        assert origin == "GCT"
        assert terminal == "JAM"
        assert len(merged) == 3  # GCT + JAM + UNKNOWN appended

        unknown = merged[2]
        assert unknown["station_code"] == "UNKNOWN"
        assert unknown["track"] == "5"

    def test_stop_sequence_from_static(self):
        """Merged stops should use stop_sequence from static, not RT order."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("GCT", 10, base),
            _make_static_stop("WDD", 20, base + timedelta(minutes=10)),
            _make_static_stop("JAM", 30, base + timedelta(minutes=20)),
        ]

        rt_arrivals = [
            _make_arrival("WDD", base + timedelta(minutes=10)),
            _make_arrival("JAM", base + timedelta(minutes=20)),
        ]

        merged, _, _ = build_complete_stops(rt_arrivals, static_stops)

        assert merged[0]["stop_sequence"] == 10  # GCT from static
        assert merged[1]["stop_sequence"] == 20  # WDD from static
        assert merged[2]["stop_sequence"] == 30  # JAM from static

    def test_actual_times_use_predicted_rt_times(self):
        """GTFS-RT arrival_time/departure_time are already predicted times.
        actual_arrival/departure should use them directly, not add delay."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)
        delay = 120  # 2 minutes

        static_stops = [
            _make_static_stop("WDD", 1, base),
        ]

        rt_arrivals = [
            _make_arrival(
                "WDD",
                base,
                departure_time=base + timedelta(minutes=1),
                delay_seconds=delay,
            ),
        ]

        merged, _, _ = build_complete_stops(rt_arrivals, static_stops)

        wdd = merged[0]
        assert wdd["actual_arrival"] == base
        assert wdd["actual_departure"] == base + timedelta(minutes=1)

    def test_all_unmapped_static_stops_returns_empty_list(self):
        """When all static stops have station_code=None (unmapped GTFS stops),
        build_complete_stops should return an empty merged list so the caller
        falls through to origin inference."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        # Simulate static stops with no internal station code mapping
        static_stops = [
            {
                "station_code": None,
                "stop_sequence": 1,
                "arrival_time": base,
                "departure_time": base,
            },
            {
                "station_code": None,
                "stop_sequence": 2,
                "arrival_time": base + timedelta(minutes=10),
                "departure_time": base + timedelta(minutes=10),
            },
        ]

        rt_arrivals = [
            _make_arrival("WDD", base + timedelta(minutes=10)),
            _make_arrival("JAM", base + timedelta(minutes=20)),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        # Empty list — caller should treat this the same as no static data
        assert merged == []
        assert origin == "WDD"
        assert terminal == "JAM"

    def test_duplicate_station_code_in_static_deduped(self):
        """When static schedule maps multiple GTFS stops to the same internal
        station_code, build_complete_stops should deduplicate them.
        This prevents unique_journey_stop constraint violations."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        # Static has the same station "M125" at two different stop_sequences
        # (e.g., different GTFS platform IDs mapped to the same station_code)
        static_stops = [
            _make_static_stop("GCT", 1, base),
            _make_static_stop("M125", 2, base + timedelta(minutes=5)),
            _make_static_stop("M125", 3, base + timedelta(minutes=6)),
            _make_static_stop("MCRH", 4, base + timedelta(minutes=30)),
        ]

        rt_arrivals = [
            _make_arrival("GCT", base, track="21"),
            _make_arrival("M125", base + timedelta(minutes=5), track="1"),
            _make_arrival("MCRH", base + timedelta(minutes=30)),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        assert origin == "GCT"
        assert terminal == "MCRH"
        # Should be 3 stops, not 4 — duplicate M125 removed
        assert len(merged) == 3
        station_codes = [s["station_code"] for s in merged]
        assert station_codes == ["GCT", "M125", "MCRH"]

        # M125 should have the RT data (not the static-only backfill)
        m125 = merged[1]
        assert m125["actual_arrival"] == base + timedelta(minutes=5)
        assert m125["track"] == "1"

    def test_duplicate_station_code_prefers_rt_data(self):
        """When deduplicating, the entry with real-time data should be kept
        over the static-only backfill entry."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        # Static has station "B" twice: once before the first RT stop (will be
        # backfilled as departed) and once after (will match RT data via pop)
        static_stops = [
            _make_static_stop("B", 1, base),
            _make_static_stop("A", 2, base + timedelta(minutes=5)),
            _make_static_stop("B", 3, base + timedelta(minutes=10)),
        ]

        # RT only has A and B — B matches the second static occurrence
        # because rt_by_station.pop() matches the first static "B"
        rt_arrivals = [
            _make_arrival("A", base + timedelta(minutes=5)),
            _make_arrival("B", base + timedelta(minutes=10), track="2"),
        ]

        merged, origin, terminal = build_complete_stops(rt_arrivals, static_stops)

        # Should deduplicate B — keep the one with RT data
        assert len(merged) == 2
        station_codes = [s["station_code"] for s in merged]
        assert station_codes == ["B", "A"]

        # First B entry (from pop) should have RT data
        b_stop = merged[0]
        assert b_stop["actual_arrival"] is not None
        assert b_stop["track"] == "2"

    def test_rt_stop_with_no_departure_time(self):
        """RT stop with departure_time=None should set actual_departure=None."""
        base = datetime(2026, 2, 6, 8, 0, 0, tzinfo=timezone.utc)

        static_stops = [
            _make_static_stop("JAM", 1, base),
        ]

        rt_arrivals = [
            _make_arrival("JAM", base, departure_time=None, delay_seconds=30),
        ]

        merged, _, _ = build_complete_stops(rt_arrivals, static_stops)

        assert merged[0]["actual_departure"] is None
        assert merged[0]["actual_arrival"] == base


class TestInferMissingOrigin:
    """Tests for infer_missing_origin()."""

    def test_lirr_outbound_non_terminal_returns_penn_station(self):
        """Outbound LIRR train whose first stop is Woodside (not a terminal)
        should infer Penn Station (NY) as the origin."""
        result = infer_missing_origin("WDD", direction_id=0, data_source="LIRR")
        assert result == "NY"

    def test_lirr_outbound_jamaica_returns_penn_station(self):
        """Outbound train first seen at Jamaica (not a terminal) should
        infer Penn Station."""
        result = infer_missing_origin("JAM", direction_id=0, data_source="LIRR")
        assert result == "NY"

    def test_lirr_outbound_penn_station_returns_none(self):
        """Outbound train whose first stop IS Penn Station needs no inference."""
        result = infer_missing_origin("NY", direction_id=0, data_source="LIRR")
        assert result is None

    def test_lirr_outbound_atlantic_terminal_returns_none(self):
        """First stop is Atlantic Terminal — already a terminal, no inference."""
        result = infer_missing_origin("LAT", direction_id=0, data_source="LIRR")
        assert result is None

    def test_lirr_outbound_grand_central_returns_none(self):
        """First stop is Grand Central Madison — already a terminal, no inference."""
        result = infer_missing_origin("GCT", direction_id=0, data_source="LIRR")
        assert result is None

    def test_lirr_outbound_hunterspoint_returns_none(self):
        """First stop is Hunterspoint Avenue — already a terminal, no inference."""
        result = infer_missing_origin("HPA", direction_id=0, data_source="LIRR")
        assert result is None

    def test_lirr_inbound_returns_none(self):
        """Inbound trains (direction_id=1) never need origin inference."""
        result = infer_missing_origin("BTA", direction_id=1, data_source="LIRR")
        assert result is None

    def test_mnr_outbound_non_terminal_returns_grand_central(self):
        """Outbound MNR train whose first stop is not GCT should infer GCT."""
        result = infer_missing_origin("M125", direction_id=0, data_source="MNR")
        assert result == "GCT"

    def test_mnr_outbound_grand_central_returns_none(self):
        """MNR train starting at GCT needs no inference."""
        result = infer_missing_origin("GCT", direction_id=0, data_source="MNR")
        assert result is None

    def test_mnr_inbound_returns_none(self):
        """Inbound MNR trains never need origin inference."""
        result = infer_missing_origin("MCRH", direction_id=1, data_source="MNR")
        assert result is None

    def test_unknown_data_source_returns_none(self):
        """Unknown data source should return None (no inference config)."""
        result = infer_missing_origin("FOO", direction_id=0, data_source="NJT")
        assert result is None

    def test_lirr_terminals_include_all_four(self):
        """Verify LIRR_ORIGIN_TERMINALS has the expected terminal stations."""
        assert LIRR_ORIGIN_TERMINALS == frozenset({"NY", "LAT", "GCT", "HPA"})

    def test_mnr_terminals_only_grand_central(self):
        """Verify MNR_ORIGIN_TERMINALS is just GCT."""
        assert MNR_ORIGIN_TERMINALS == frozenset({"GCT"})

    def test_origin_travel_buffer_is_ten_minutes(self):
        """Verify the travel buffer constant is 10 minutes."""
        assert ORIGIN_TRAVEL_BUFFER == timedelta(minutes=10)
