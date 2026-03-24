"""
Unit tests for trip search service pure functions.

Tests cover: _departure_to_leg, _make_direct_trip, _orient_transfer,
_find_relevant_transfer_points, and _get_best_time.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from trackrat.config.transfer_points import TransferPoint
from trackrat.models.api import (
    DataFreshness,
    LineInfo,
    StationInfo,
    TrainDeparture,
    TrainPosition,
)
from trackrat.services.trip_search import (
    _departure_to_leg,
    _find_relevant_transfer_points,
    _get_best_time,
    _make_direct_trip,
    _orient_transfer,
)


# --- Test Fixtures ---

def _make_station_info(
    code: str, name: str,
    scheduled: datetime | None = None,
    updated: datetime | None = None,
    actual: datetime | None = None,
    track: str | None = None,
) -> StationInfo:
    return StationInfo(
        code=code, name=name,
        scheduled_time=scheduled, updated_time=updated,
        actual_time=actual, track=track,
    )


def _make_departure(
    train_id: str = "1234",
    from_code: str = "NY",
    from_name: str = "New York Penn Station",
    to_code: str = "TR",
    to_name: str = "Trenton",
    scheduled_dep: datetime | None = None,
    scheduled_arr: datetime | None = None,
    updated_dep: datetime | None = None,
    updated_arr: datetime | None = None,
    actual_dep: datetime | None = None,
    actual_arr: datetime | None = None,
    is_cancelled: bool = False,
    data_source: str = "NJT",
    observation_type: str = "OBSERVED",
    line_code: str = "NEC",
    line_name: str = "Northeast Corridor",
    destination: str = "Trenton",
    has_arrival: bool = True,
) -> TrainDeparture:
    """Build a TrainDeparture with sensible defaults."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    dep_time = scheduled_dep or now + timedelta(minutes=10)
    arr_time = scheduled_arr or dep_time + timedelta(minutes=60)

    departure = _make_station_info(
        from_code, from_name,
        scheduled=dep_time, updated=updated_dep, actual=actual_dep,
    )
    arrival = _make_station_info(
        to_code, to_name,
        scheduled=arr_time, updated=updated_arr, actual=actual_arr,
    ) if has_arrival else None

    return TrainDeparture(
        train_id=train_id,
        journey_date=date.today(),
        line=LineInfo(code=line_code, name=line_name, color="#0000FF"),
        destination=destination,
        departure=departure,
        arrival=arrival,
        train_position=TrainPosition(),
        data_freshness=DataFreshness(
            last_updated=now,
            age_seconds=5,
            update_count=1,
            collection_method="just_in_time",
        ),
        data_source=data_source,
        observation_type=observation_type,
        is_cancelled=is_cancelled,
    )


def _make_transfer_point(
    station_a: str = "NP",
    system_a: str = "NJT",
    station_b: str = "NP",
    system_b: str = "PATH",
    walk_meters: float = 0.0,
    walk_minutes: int = 5,
    same_station: bool = True,
) -> TransferPoint:
    return TransferPoint(
        station_a=station_a, system_a=system_a,
        station_b=station_b, system_b=system_b,
        walk_meters=walk_meters, walk_minutes=walk_minutes,
        same_station=same_station,
    )


# --- Tests ---


class TestGetBestTime:
    """Test _get_best_time priority: actual > updated > scheduled."""

    def test_actual_takes_priority(self):
        now = datetime.now(timezone.utc)
        info = _make_station_info(
            "NY", "Test",
            scheduled=now - timedelta(minutes=5),
            updated=now - timedelta(minutes=2),
            actual=now,
        )
        assert _get_best_time(info) == now

    def test_updated_when_no_actual(self):
        now = datetime.now(timezone.utc)
        updated = now - timedelta(minutes=2)
        info = _make_station_info("NY", "Test", scheduled=now - timedelta(minutes=5), updated=updated)
        assert _get_best_time(info) == updated

    def test_scheduled_as_fallback(self):
        now = datetime.now(timezone.utc)
        info = _make_station_info("NY", "Test", scheduled=now)
        assert _get_best_time(info) == now

    def test_none_when_all_none(self):
        info = _make_station_info("NY", "Test")
        assert _get_best_time(info) is None


class TestDepartureToLeg:
    """Test converting TrainDeparture to TripLeg."""

    def test_basic_conversion(self):
        dep = _make_departure(train_id="5678", from_code="NY", to_code="TR")
        leg = _departure_to_leg(dep)

        assert leg.train_id == "5678"
        assert leg.boarding.code == "NY"
        assert leg.alighting.code == "TR"
        assert leg.data_source == "NJT"
        assert leg.is_cancelled is False

    def test_cancelled_train(self):
        dep = _make_departure(is_cancelled=True)
        leg = _departure_to_leg(dep)
        assert leg.is_cancelled is True

    def test_no_arrival_falls_back_to_departure(self):
        dep = _make_departure(has_arrival=False)
        leg = _departure_to_leg(dep)
        assert leg.alighting.code == dep.departure.code

    def test_preserves_observation_type(self):
        dep = _make_departure(observation_type="SCHEDULED")
        leg = _departure_to_leg(dep)
        assert leg.observation_type == "SCHEDULED"

    def test_preserves_line_info(self):
        dep = _make_departure(line_code="NJCL", line_name="North Jersey Coast Line")
        leg = _departure_to_leg(dep)
        assert leg.line.code == "NJCL"
        assert leg.line.name == "North Jersey Coast Line"


class TestMakeDirectTrip:
    """Test converting a TrainDeparture to a single-leg TripOption."""

    def test_basic_direct_trip(self):
        now = datetime.now(timezone.utc)
        dep = _make_departure(
            scheduled_dep=now + timedelta(minutes=10),
            scheduled_arr=now + timedelta(minutes=70),
        )
        trip = _make_direct_trip(dep)

        assert trip is not None
        assert trip.is_direct is True
        assert len(trip.legs) == 1
        assert len(trip.transfers) == 0
        assert trip.total_duration_minutes == 60

    def test_returns_none_when_no_departure_time(self):
        dep = _make_departure()
        # Clear all times to simulate no departure time
        dep.departure.scheduled_time = None
        dep.departure.updated_time = None
        dep.departure.actual_time = None
        trip = _make_direct_trip(dep)
        assert trip is None

    def test_duration_uses_best_times(self):
        now = datetime.now(timezone.utc)
        dep = _make_departure(
            scheduled_dep=now,
            actual_dep=now + timedelta(minutes=5),  # 5 min late departure
            scheduled_arr=now + timedelta(minutes=60),
            actual_arr=now + timedelta(minutes=65),  # 5 min late arrival
        )
        trip = _make_direct_trip(dep)
        assert trip is not None
        # actual departure -> actual arrival = 60 min
        assert trip.total_duration_minutes == 60

    def test_no_arrival_uses_departure_for_arrival(self):
        dep = _make_departure(has_arrival=False)
        trip = _make_direct_trip(dep)
        assert trip is not None
        # No arrival time → duration is 0
        assert trip.total_duration_minutes == 0


class TestOrientTransfer:
    """Test orienting a transfer point for a specific from->to direction."""

    def test_standard_orientation_a_to_b(self):
        tp = _make_transfer_point(
            station_a="NP", system_a="NJT",
            station_b="NP", system_b="PATH",
        )
        from_systems = {"NJT"}
        to_systems = {"PATH"}

        alight, alight_sys, board, board_sys = _orient_transfer(tp, from_systems, to_systems)
        assert alight == "NP"
        assert alight_sys == "NJT"
        assert board == "NP"
        assert board_sys == "PATH"

    def test_reverse_orientation_b_to_a(self):
        tp = _make_transfer_point(
            station_a="NP", system_a="NJT",
            station_b="NP", system_b="PATH",
        )
        from_systems = {"PATH"}
        to_systems = {"NJT"}

        alight, alight_sys, board, board_sys = _orient_transfer(tp, from_systems, to_systems)
        assert alight == "NP"
        assert alight_sys == "PATH"
        assert board == "NP"
        assert board_sys == "NJT"

    def test_cross_station_transfer(self):
        """Transfer between different physical stations."""
        tp = _make_transfer_point(
            station_a="NP", system_a="NJT",
            station_b="NWK", system_b="PATH",
            walk_meters=200, walk_minutes=5, same_station=False,
        )
        from_systems = {"NJT"}
        to_systems = {"PATH"}

        alight, alight_sys, board, board_sys = _orient_transfer(tp, from_systems, to_systems)
        assert alight == "NP"
        assert board == "NWK"


class TestFindRelevantTransferPoints:
    """Test finding relevant transfer points between system sets."""

    def test_finds_njt_to_path_transfers(self):
        tps = _find_relevant_transfer_points({"NJT"}, {"PATH"})
        assert len(tps) > 0, "Should find NJT <-> PATH transfers"
        for tp in tps:
            systems = {tp.system_a, tp.system_b}
            assert "NJT" in systems or "PATH" in systems

    def test_same_system_returns_empty(self):
        """From and to both NJT — no transfer needed."""
        tps = _find_relevant_transfer_points({"NJT"}, {"NJT"})
        assert len(tps) == 0

    def test_multiple_from_systems(self):
        """When from station is served by multiple systems."""
        tps = _find_relevant_transfer_points({"NJT", "AMTRAK"}, {"PATH"})
        assert len(tps) > 0

    def test_deduplicates(self):
        """Should not return duplicate transfer points."""
        tps = _find_relevant_transfer_points({"NJT", "AMTRAK"}, {"PATH"})
        seen = set()
        for tp in tps:
            key = frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            assert key not in seen, f"Duplicate: {tp.station_a}({tp.system_a}) <-> {tp.station_b}({tp.system_b})"
            seen.add(key)

    def test_nonexistent_system_returns_empty(self):
        tps = _find_relevant_transfer_points({"FAKE_SYSTEM"}, {"PATH"})
        assert len(tps) == 0
