"""
Unit tests for trip search service.

Tests the pure logic functions used in trip composition:
- _get_best_time: time priority selection
- _departure_to_leg: TrainDeparture -> TripLeg conversion
- _make_direct_trip: single-leg TripOption construction
- get_systems_serving_station: system lookup from route topology
- _find_relevant_transfer_points: transfer point discovery between systems
- _orient_transfer: transfer point orientation for routing
- _empty_response: empty response construction
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from trackrat.config.transfer_points import (
    TransferPoint,
    get_systems_serving_station,
    get_transfer_points,
)
from trackrat.models.api import (
    DataFreshness,
    LineInfo,
    SimpleStationInfo,
    StationInfo,
    TrainDeparture,
    TrainPosition,
    TransferInfo,
    TripLeg,
    TripOption,
)
from trackrat.services.trip_search import (
    MAX_TRANSFER_QUERIES,
    _departure_to_leg,
    _empty_response,
    _filter_unreasonable_durations,
    _find_relevant_transfer_points,
    _get_best_time,
    _get_station_lines_expanded,
    _make_direct_trip,
    _orient_transfer,
    _rank_transfer_points,
)

ET = ZoneInfo("America/New_York")


def _make_station_info(
    code: str = "NY",
    name: str = "New York Penn Station",
    scheduled: datetime | None = None,
    updated: datetime | None = None,
    actual: datetime | None = None,
) -> StationInfo:
    return StationInfo(
        code=code,
        name=name,
        scheduled_time=scheduled,
        updated_time=updated,
        actual_time=actual,
    )


def _make_departure(
    train_id: str = "3456",
    from_code: str = "NP",
    from_name: str = "Newark Penn Station",
    to_code: str = "NY",
    to_name: str = "New York Penn Station",
    dep_time: datetime | None = None,
    arr_time: datetime | None = None,
    data_source: str = "NJT",
    line_code: str = "NE",
    is_cancelled: bool = False,
) -> TrainDeparture:
    now = datetime.now(ET)
    dep = dep_time or now + timedelta(minutes=10)
    arr = arr_time or dep + timedelta(minutes=30)
    return TrainDeparture(
        train_id=train_id,
        journey_date=now.date(),
        line=LineInfo(code=line_code, name="Northeast Corridor", color="#000000"),
        destination="New York Penn Station",
        departure=_make_station_info(code=from_code, name=from_name, scheduled=dep),
        arrival=_make_station_info(code=to_code, name=to_name, scheduled=arr),
        train_position=TrainPosition(),
        data_freshness=DataFreshness(last_updated=now, age_seconds=5, update_count=1),
        data_source=data_source,
        observation_type="OBSERVED",
        is_cancelled=is_cancelled,
    )


class TestGetBestTime:
    """Test time priority: actual > updated > scheduled."""

    def test_returns_actual_when_available(self):
        now = datetime.now(ET)
        info = _make_station_info(
            scheduled=now,
            updated=now + timedelta(minutes=1),
            actual=now + timedelta(minutes=2),
        )
        assert _get_best_time(info) == now + timedelta(minutes=2)

    def test_returns_updated_when_no_actual(self):
        now = datetime.now(ET)
        info = _make_station_info(scheduled=now, updated=now + timedelta(minutes=1))
        assert _get_best_time(info) == now + timedelta(minutes=1)

    def test_returns_scheduled_when_no_actual_or_updated(self):
        now = datetime.now(ET)
        info = _make_station_info(scheduled=now)
        assert _get_best_time(info) == now

    def test_returns_none_when_no_times(self):
        info = _make_station_info()
        assert _get_best_time(info) is None


class TestDepartureToLeg:
    """Test conversion from TrainDeparture to TripLeg."""

    def test_basic_conversion(self):
        dep = _make_departure()
        leg = _departure_to_leg(dep)
        assert leg.train_id == "3456"
        assert leg.line.code == "NE"
        assert leg.data_source == "NJT"
        assert leg.boarding.code == "NP"
        assert leg.alighting.code == "NY"
        assert leg.is_cancelled is False

    def test_cancelled_train(self):
        dep = _make_departure(is_cancelled=True)
        leg = _departure_to_leg(dep)
        assert leg.is_cancelled is True

    def test_preserves_train_position(self):
        dep = _make_departure()
        leg = _departure_to_leg(dep)
        assert leg.train_position is not None


class TestMakeDirectTrip:
    """Test direct trip construction from a single departure."""

    def test_basic_direct_trip(self):
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, arr_time=now + timedelta(minutes=30))
        trip = _make_direct_trip(dep)
        assert trip is not None
        assert trip.is_direct is True
        assert len(trip.legs) == 1
        assert len(trip.transfers) == 0
        assert trip.total_duration_minutes == 30
        assert trip.departure_time == now
        assert trip.arrival_time == now + timedelta(minutes=30)

    def test_returns_none_when_no_departure_time(self):
        dep = _make_departure()
        dep.departure = _make_station_info()  # No times
        trip = _make_direct_trip(dep)
        assert trip is None

    def test_duration_never_negative(self):
        """Duration should be 0 if arrival is somehow before departure."""
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, arr_time=now - timedelta(minutes=5))
        trip = _make_direct_trip(dep)
        assert trip is not None
        assert trip.total_duration_minutes == 0


class TestFindSystemsForStation:
    """Test station-to-system lookup using route topology."""

    def test_ny_penn(self):
        systems = get_systems_serving_station("NY")
        assert "NJT" in systems
        assert "AMTRAK" in systems
        assert "LIRR" in systems

    def test_hoboken_njt(self):
        systems = get_systems_serving_station("HB")
        assert "NJT" in systems

    def test_path_stations(self):
        systems = get_systems_serving_station("PWC")
        assert "PATH" in systems

    def test_unknown_station(self):
        systems = get_systems_serving_station("ZZZZ")
        assert len(systems) == 0


class TestFindRelevantTransferPoints:
    """Test finding transfer points between system sets."""

    def test_njt_to_path(self):
        from_sys = {"NJT"}
        to_sys = {"PATH"}
        transfers = _find_relevant_transfer_points(from_sys, to_sys)
        assert len(transfers) > 0
        # Should find Hoboken and Newark Penn
        station_pairs = {(tp.station_a, tp.station_b) for tp in transfers}
        hoboken_found = any("HB" in pair and "PHO" in pair for pair in station_pairs)
        assert hoboken_found, "Should find Hoboken NJT <-> PATH transfer"

    def test_same_non_subway_system_returns_empty(self):
        transfers = _find_relevant_transfer_points({"NJT"}, {"NJT"})
        assert len(transfers) == 0

    def test_no_connection_returns_empty(self):
        transfers = _find_relevant_transfer_points({"PATCO"}, {"LIRR"})
        assert len(transfers) == 0

    def test_no_duplicates(self):
        from_sys = {"NJT", "AMTRAK"}
        to_sys = {"PATH"}
        transfers = _find_relevant_transfer_points(from_sys, to_sys)
        keys = [
            frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            for tp in transfers
        ]
        assert len(keys) == len(set(keys)), "Duplicate transfers found"

    def test_penn_station_rail_to_subway_transfer_found(self):
        """NJT should transfer to the 34 St-Penn subway complex at NY Penn."""
        transfers = _find_relevant_transfer_points(
            {"NJT"}, {"SUBWAY"}, from_station="TR", to_station="S128"
        )
        station_pairs = {frozenset({tp.station_a, tp.station_b}) for tp in transfers}
        assert frozenset({"NY", "S128"}) in station_pairs
        assert frozenset({"NY", "SA28"}) in station_pairs

    def test_grand_central_rail_to_subway_transfer_found(self):
        """MNR should transfer to the Grand Central-42 St subway complex at GCT."""
        transfers = _find_relevant_transfer_points(
            {"MNR"}, {"SUBWAY"}, from_station="MSTM", to_station="S631"
        )
        station_pairs = {frozenset({tp.station_a, tp.station_b}) for tp in transfers}
        assert frozenset({"GCT", "S631"}) in station_pairs
        assert frozenset({"GCT", "S723"}) in station_pairs
        assert frozenset({"GCT", "S901"}) in station_pairs


class TestStationLinesExpanded:
    """Test line lookup across physical station equivalences."""

    def test_penn_station_rail_code_expands_to_subway_lines(self):
        lines = _get_station_lines_expanded("NY", "SUBWAY")
        assert {"1", "2", "3", "A", "C", "E"} <= set(lines)

    def test_grand_central_rail_code_expands_to_subway_lines(self):
        lines = _get_station_lines_expanded("GCT", "SUBWAY")
        assert {"4", "5", "6", "7", "GS"} <= set(lines)


class TestOrientTransfer:
    """Test transfer point orientation for routing."""

    def test_orient_njt_to_path(self):
        # Get a real NJT<->PATH transfer (Hoboken)
        transfers = get_transfer_points("NJT", "PATH")
        hoboken = [
            tp
            for tp in transfers
            if "HB" in (tp.station_a, tp.station_b)
            and "PHO" in (tp.station_a, tp.station_b)
        ]
        assert len(hoboken) == 1
        tp = hoboken[0]

        alight, alight_sys, board, board_sys = _orient_transfer(
            tp, from_systems={"NJT"}, to_systems={"PATH"}
        )
        # Alight at NJT station, board at PATH station
        assert alight_sys == "NJT"
        assert board_sys == "PATH"
        assert alight == "HB"
        assert board == "PHO"

    def test_orient_reverse_direction(self):
        transfers = get_transfer_points("NJT", "PATH")
        hoboken = [
            tp
            for tp in transfers
            if "HB" in (tp.station_a, tp.station_b)
            and "PHO" in (tp.station_a, tp.station_b)
        ]
        tp = hoboken[0]

        # Now orient PATH -> NJT
        alight, alight_sys, board, board_sys = _orient_transfer(
            tp, from_systems={"PATH"}, to_systems={"NJT"}
        )
        assert alight_sys == "PATH"
        assert board_sys == "NJT"
        assert alight == "PHO"
        assert board == "HB"


class TestEmptyResponse:
    """Test empty response construction."""

    def test_basic_empty_response(self):
        resp = _empty_response("NP", "PWC", "no_systems")
        assert resp.trips == []
        assert resp.metadata["count"] == 0
        assert resp.metadata["search_type"] == "no_systems"
        assert resp.metadata["from_station"]["code"] == "NP"
        assert resp.metadata["to_station"]["code"] == "PWC"

    def test_direct_no_trains_reason(self):
        resp = _empty_response("NY", "TR", "direct_no_trains")
        assert resp.metadata["search_type"] == "direct_no_trains"


class TestTripOptionModel:
    """Test TripOption model construction and serialization."""

    def test_direct_trip_serialization(self):
        now = datetime.now(ET)
        trip = TripOption(
            legs=[
                TripLeg(
                    train_id="3456",
                    journey_date=now.date(),
                    line=LineInfo(
                        code="NE", name="Northeast Corridor", color="#000000"
                    ),
                    data_source="NJT",
                    destination="New York Penn Station",
                    boarding=_make_station_info(
                        code="NP", name="Newark Penn Station", scheduled=now
                    ),
                    alighting=_make_station_info(
                        code="NY",
                        name="New York Penn Station",
                        scheduled=now + timedelta(minutes=30),
                    ),
                )
            ],
            transfers=[],
            departure_time=now,
            arrival_time=now + timedelta(minutes=30),
            total_duration_minutes=30,
            is_direct=True,
        )
        data = trip.model_dump()
        assert data["is_direct"] is True
        assert data["total_duration_minutes"] == 30
        assert len(data["legs"]) == 1
        assert len(data["transfers"]) == 0

    def test_transfer_trip_serialization(self):
        now = datetime.now(ET)
        trip = TripOption(
            legs=[
                TripLeg(
                    train_id="3456",
                    journey_date=now.date(),
                    line=LineInfo(
                        code="NE", name="Northeast Corridor", color="#000000"
                    ),
                    data_source="NJT",
                    destination="Hoboken",
                    boarding=_make_station_info(
                        code="NP", name="Newark Penn Station", scheduled=now
                    ),
                    alighting=_make_station_info(
                        code="HB", name="Hoboken", scheduled=now + timedelta(minutes=20)
                    ),
                ),
                TripLeg(
                    train_id="HOB-WTC-001",
                    journey_date=now.date(),
                    line=LineInfo(
                        code="HOB-WTC", name="Hoboken - WTC", color="#65c100"
                    ),
                    data_source="PATH",
                    destination="World Trade Center",
                    boarding=_make_station_info(
                        code="PHO",
                        name="Hoboken PATH",
                        scheduled=now + timedelta(minutes=28),
                    ),
                    alighting=_make_station_info(
                        code="PWC",
                        name="World Trade Center",
                        scheduled=now + timedelta(minutes=42),
                    ),
                ),
            ],
            transfers=[
                TransferInfo(
                    from_station=SimpleStationInfo(code="HB", name="Hoboken"),
                    to_station=SimpleStationInfo(code="PHO", name="Hoboken PATH"),
                    walk_minutes=5,
                    same_station=False,
                ),
            ],
            departure_time=now,
            arrival_time=now + timedelta(minutes=42),
            total_duration_minutes=42,
            is_direct=False,
        )
        data = trip.model_dump()
        assert data["is_direct"] is False
        assert data["total_duration_minutes"] == 42
        assert len(data["legs"]) == 2
        assert len(data["transfers"]) == 1
        assert data["transfers"][0]["walk_minutes"] == 5
        assert data["transfers"][0]["same_station"] is False
        assert data["legs"][0]["data_source"] == "NJT"
        assert data["legs"][1]["data_source"] == "PATH"


class TestDataSourcesFiltering:
    """Test that data_sources correctly restricts transfer search systems.

    Newark Penn Station (NP) is served by NJT and AMTRAK.
    Newark PATH (PNK) is served by PATH.
    These are linked via a station equivalence group but have separate system sets.
    The user's data_sources filter should exclude systems from the search.
    """

    def test_filtering_excludes_njt_when_only_path_subway(self):
        """NP is served by NJT+AMTRAK. When only PATH+SUBWAY are allowed,
        NP's systems should be empty after filtering — preventing NJT routes.
        """
        all_systems = get_systems_serving_station("NP")
        assert "NJT" in all_systems, "NP should be served by NJT"
        assert "AMTRAK" in all_systems, "NP should be served by AMTRAK"

        allowed = {"PATH", "SUBWAY"}
        filtered = all_systems & allowed
        assert (
            len(filtered) == 0
        ), "NP should have no allowed systems with PATH+SUBWAY only"

    def test_pnk_kept_when_path_allowed(self):
        """PNK (Newark PATH) should survive filtering when PATH is allowed."""
        all_systems = get_systems_serving_station("PNK")
        assert "PATH" in all_systems, "PNK should be served by PATH"

        allowed = {"PATH", "SUBWAY"}
        filtered = all_systems & allowed
        assert "PATH" in filtered

    def test_filtered_systems_produce_no_njt_transfers(self):
        """With only PATH+SUBWAY enabled, transfer search from PNK to a subway
        station should not include any NJT legs.
        """
        allowed = {"PATH", "SUBWAY"}
        from_systems = get_systems_serving_station("PNK") & allowed
        # WTC PATH station connects to subway
        to_systems = get_systems_serving_station("SA24") & allowed

        assert len(from_systems) > 0, "PNK should have PATH in allowed systems"
        assert len(to_systems) > 0, "SA24 should have SUBWAY in allowed systems"

        transfers = _find_relevant_transfer_points(from_systems, to_systems)
        for tp in transfers:
            assert tp.system_a != "NJT", f"NJT should not appear: {tp}"
            assert tp.system_b != "NJT", f"NJT should not appear: {tp}"
            assert tp.system_a != "AMTRAK", f"AMTRAK should not appear: {tp}"
            assert tp.system_b != "AMTRAK", f"AMTRAK should not appear: {tp}"

    def test_no_filter_includes_all_systems(self):
        """When data_sources is None (no filter), all systems remain."""
        all_systems = get_systems_serving_station("NP")
        assert "NJT" in all_systems
        assert "AMTRAK" in all_systems


class TestIntraSubwayTransferPoints:
    """Test finding intra-subway transfer points for line changes."""

    def test_metropolitan_av_to_wall_st_finds_transfers(self):
        """G/L at Metropolitan Av → 4/5 at Wall St should find transfer points."""
        transfers = _find_relevant_transfer_points(
            {"SUBWAY"}, {"SUBWAY"}, from_station="SG29", to_station="S419"
        )
        assert (
            len(transfers) > 0
        ), "Should find transfer points for Metropolitan Av (G/L) → Wall St (4/5)"
        # Union Sq (SL03 <-> S635) should be among them
        station_pairs = {frozenset({tp.station_a, tp.station_b}) for tp in transfers}
        assert (
            frozenset({"SL03", "S635"}) in station_pairs
        ), "Union Sq (L <-> 4/5/6) should be a transfer point for this route"

    def test_pure_same_line_returns_empty(self):
        """Stations on ONLY the same line (no equivalences) should find no transfers."""
        # SG35 and SG34 are both purely G-line, no station complex equivalences
        transfers = _find_relevant_transfer_points(
            {"SUBWAY"}, {"SUBWAY"}, from_station="SG35", to_station="SG34"
        )
        assert (
            len(transfers) == 0
        ), "Pure same-line (G→G) should not produce intra-subway transfers"

    def test_overlapping_lines_still_finds_transfers(self):
        """Stations sharing a line but having other lines should find transfers for non-shared lines.

        SG29 (Metropolitan Av) has lines {G, L} via equivalence with SL10.
        SG22 (Court Sq) has lines {G, 7, E, ...} via equivalence with S719/SF09.
        They share G, but transfers connecting L to 7/E/M should still be found.
        """
        transfers = _find_relevant_transfer_points(
            {"SUBWAY"}, {"SUBWAY"}, from_station="SG29", to_station="SG22"
        )
        assert (
            len(transfers) > 0
        ), "Overlapping lines with other non-shared lines should find transfers"

    def test_without_station_codes_returns_empty(self):
        """Intra-subway needs station codes to determine lines; without them, no results."""
        transfers = _find_relevant_transfer_points({"SUBWAY"}, {"SUBWAY"})
        assert len(transfers) == 0

    def test_cross_system_still_works(self):
        """Cross-system transfers should still work alongside intra-subway."""
        transfers = _find_relevant_transfer_points(
            {"NJT"}, {"PATH"}, from_station="NP", to_station="PWC"
        )
        assert len(transfers) > 0, "Cross-system NJT→PATH should still work"

    def test_no_duplicate_transfer_points(self):
        """No duplicates in intra-subway results."""
        transfers = _find_relevant_transfer_points(
            {"SUBWAY"}, {"SUBWAY"}, from_station="SG29", to_station="S419"
        )
        keys = [
            frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            for tp in transfers
        ]
        assert len(keys) == len(set(keys)), "Duplicate transfers found"


class TestIntraSubwayOrientTransfer:
    """Test transfer point orientation for intra-subway routing."""

    def test_orient_l_to_4_5_at_union_sq(self):
        """For G/L origin → 4/5 dest, L side should be alight, 4/5 side should be board."""
        from trackrat.config.transfer_points import get_intra_subway_transfers

        # Find Union Sq L <-> 4/5/6 transfer
        union_sq = None
        for tp in get_intra_subway_transfers():
            if {tp.station_a, tp.station_b} == {"SL03", "S635"}:
                union_sq = tp
                break
        assert union_sq is not None, "Union Sq L<->4/5/6 transfer not found"

        alight, alight_sys, board, board_sys = _orient_transfer(
            union_sq,
            from_systems={"SUBWAY"},
            to_systems={"SUBWAY"},
            from_station="SG29",  # Metropolitan Av (G/L)
            to_station="S419",  # Wall St (4/5)
        )
        # SG29 is equivalent to SL10 (L line), so origin has L line
        # Alight at L platform (SL03), board at 4/5/6 platform (S635)
        assert alight == "SL03", f"Should alight at L platform SL03, got {alight}"
        assert board == "S635", f"Should board at 4/5 platform S635, got {board}"
        assert alight_sys == "SUBWAY"
        assert board_sys == "SUBWAY"

    def test_orient_reverse_direction(self):
        """For 4/5 origin → L dest, orientation should reverse."""
        from trackrat.config.transfer_points import get_intra_subway_transfers

        union_sq = None
        for tp in get_intra_subway_transfers():
            if {tp.station_a, tp.station_b} == {"SL03", "S635"}:
                union_sq = tp
                break
        assert union_sq is not None

        alight, alight_sys, board, board_sys = _orient_transfer(
            union_sq,
            from_systems={"SUBWAY"},
            to_systems={"SUBWAY"},
            from_station="S419",  # Wall St (4/5) as origin
            to_station="SG29",  # Metropolitan Av (G/L) as dest
        )
        # Origin has 4/5 lines, so alight at 4/5/6 platform (S635)
        assert alight == "S635", f"Should alight at 4/5 platform S635, got {alight}"
        assert board == "SL03", f"Should board at L platform SL03, got {board}"


def _make_trip_option(
    departure_offset_min: int = 0,
    duration_min: int = 30,
) -> TripOption:
    """Helper to build a TripOption with specified departure offset and duration."""
    now = datetime.now(ET)
    dep_time = now + timedelta(minutes=departure_offset_min)
    arr_time = dep_time + timedelta(minutes=duration_min)
    leg = TripLeg(
        train_id="9999",
        journey_date=now.date(),
        line=LineInfo(code="NE", name="Northeast Corridor", color="#000000"),
        destination="Test",
        boarding=_make_station_info(code="A", name="A", scheduled=dep_time),
        alighting=_make_station_info(code="B", name="B", scheduled=arr_time),
        data_source="NJT",
        observation_type="OBSERVED",
        is_cancelled=False,
        train_position=TrainPosition(),
    )
    return TripOption(
        legs=[leg],
        transfers=[],
        departure_time=dep_time,
        arrival_time=arr_time,
        total_duration_minutes=duration_min,
        is_direct=False,
    )


class TestFilterUnreasonableDurations:
    """Test duration-relative filtering of transfer trips."""

    def test_empty_list_returns_empty(self):
        assert _filter_unreasonable_durations([]) == []

    def test_single_trip_always_kept(self):
        trips = [_make_trip_option(duration_min=60)]
        result = _filter_unreasonable_durations(trips)
        assert len(result) == 1

    def test_similar_durations_all_kept(self):
        """Trips within reasonable range of fastest should all be kept."""
        trips = [
            _make_trip_option(departure_offset_min=0, duration_min=25),
            _make_trip_option(departure_offset_min=5, duration_min=30),
            _make_trip_option(departure_offset_min=10, duration_min=35),
        ]
        result = _filter_unreasonable_durations(trips)
        assert len(result) == 3, f"Expected all 3 trips kept, got {len(result)}"

    def test_much_longer_trip_filtered(self):
        """A trip taking 2x+ and +20min+ longer than the fastest should be excluded."""
        trips = [
            _make_trip_option(departure_offset_min=0, duration_min=25),  # fastest
            _make_trip_option(departure_offset_min=5, duration_min=30),  # OK
            _make_trip_option(
                departure_offset_min=10, duration_min=55
            ),  # 55 > max(50, 45) = 50 → filtered
        ]
        result = _filter_unreasonable_durations(trips)
        durations = [t.total_duration_minutes for t in result]
        assert 25 in durations, f"Fastest trip (25 min) should be kept, got {durations}"
        assert 30 in durations, f"30-min trip should be kept, got {durations}"
        assert 55 not in durations, f"55-min trip should be filtered, got {durations}"

    def test_20min_floor_prevents_aggressive_filter_on_short_trips(self):
        """For a 10-min fastest trip, 2x=20 but +20=30 is more generous, so 25-min kept."""
        trips = [
            _make_trip_option(duration_min=10),  # fastest
            _make_trip_option(duration_min=25),  # 25 <= max(20, 30) = 30 → kept
        ]
        result = _filter_unreasonable_durations(trips)
        assert len(result) == 2, (
            f"25-min trip should survive +20 floor (max_reasonable=30), got "
            f"{[t.total_duration_minutes for t in result]}"
        )

    def test_2x_rule_dominates_for_long_trips(self):
        """For a 40-min fastest trip, 2x=80 > +20=60, so 2x rule applies."""
        trips = [
            _make_trip_option(duration_min=40),  # fastest
            _make_trip_option(duration_min=75),  # 75 <= 80 → kept
            _make_trip_option(duration_min=85),  # 85 > 80 → filtered
        ]
        result = _filter_unreasonable_durations(trips)
        durations = [t.total_duration_minutes for t in result]
        assert 40 in durations
        assert 75 in durations, f"75-min trip should be kept (2x=80), got {durations}"
        assert (
            85 not in durations
        ), f"85-min trip should be filtered (>80), got {durations}"

    def test_boundary_exactly_at_threshold_kept(self):
        """A trip exactly at the threshold should be kept (<=, not <)."""
        trips = [
            _make_trip_option(
                duration_min=25
            ),  # fastest, max_reasonable = max(50, 45) = 50
            _make_trip_option(duration_min=50),  # exactly at threshold
        ]
        result = _filter_unreasonable_durations(trips)
        assert len(result) == 2, (
            f"Trip at exact threshold (50) should be kept, got "
            f"{[t.total_duration_minutes for t in result]}"
        )


class TestLeg2TimeWindowFromLeg1Arrivals:
    """Test the logic for computing leg 2 time_from based on leg 1 arrival times.

    Bug context: When leg 1 is long (e.g. MNR 55 min, Amtrak 3h), leg 2 queried
    with time_from=None returned the next 20 departures from "now", which were all
    BEFORE leg 1 arrives.  The fix sets time_from to earliest_leg1_arrival +
    walk_minutes + CONNECTION_BUFFER_MINUTES so the departure service returns
    trains starting at the connection window.
    """

    def test_earliest_arrival_from_multiple_departures(self):
        """Should find the earliest arrival across multiple leg 1 departures."""
        now = datetime.now(ET)
        dep1 = _make_departure(
            train_id="1001",
            dep_time=now + timedelta(minutes=5),
            arr_time=now + timedelta(minutes=60),
        )
        dep2 = _make_departure(
            train_id="1002",
            dep_time=now + timedelta(minutes=15),
            arr_time=now + timedelta(minutes=45),  # arrives earlier
        )
        dep3 = _make_departure(
            train_id="1003",
            dep_time=now + timedelta(minutes=25),
            arr_time=now + timedelta(minutes=80),
        )
        departures = [dep1, dep2, dep3]

        # Extract earliest arrival (same logic as in search_trips Phase 2)
        earliest_arrival = None
        for dep in departures:
            if dep.is_cancelled or not dep.arrival:
                continue
            arr_time = _get_best_time(dep.arrival)
            if arr_time and (earliest_arrival is None or arr_time < earliest_arrival):
                earliest_arrival = arr_time

        assert earliest_arrival == now + timedelta(
            minutes=45
        ), f"Expected earliest arrival at +45 min, got {earliest_arrival}"

        # With 5 min walk + 2 min buffer, leg 2 should start at +52
        from trackrat.services.trip_search import CONNECTION_BUFFER_MINUTES

        walk_minutes = 5
        leg2_time_from = earliest_arrival + timedelta(
            minutes=walk_minutes + CONNECTION_BUFFER_MINUTES
        )
        expected = now + timedelta(minutes=45 + 5 + CONNECTION_BUFFER_MINUTES)
        assert leg2_time_from == expected, (
            f"Leg 2 time_from should be earliest_arrival + walk + buffer, "
            f"got {leg2_time_from}, expected {expected}"
        )

    def test_cancelled_departures_skipped(self):
        """Cancelled departures should not affect earliest arrival calculation."""
        now = datetime.now(ET)
        cancelled = _make_departure(
            train_id="C1",
            dep_time=now + timedelta(minutes=5),
            arr_time=now + timedelta(minutes=20),  # earliest but cancelled
            is_cancelled=True,
        )
        running = _make_departure(
            train_id="R1",
            dep_time=now + timedelta(minutes=15),
            arr_time=now + timedelta(minutes=50),
        )
        departures = [cancelled, running]

        earliest_arrival = None
        for dep in departures:
            if dep.is_cancelled or not dep.arrival:
                continue
            arr_time = _get_best_time(dep.arrival)
            if arr_time and (earliest_arrival is None or arr_time < earliest_arrival):
                earliest_arrival = arr_time

        assert earliest_arrival == now + timedelta(minutes=50), (
            f"Cancelled dep (arriving +20min) should be skipped; "
            f"expected +50min, got {earliest_arrival}"
        )

    def test_departure_without_arrival_skipped(self):
        """Departures missing arrival info should be skipped."""
        now = datetime.now(ET)
        no_arrival = _make_departure(
            train_id="N1",
            dep_time=now + timedelta(minutes=5),
            arr_time=now + timedelta(minutes=20),
        )
        no_arrival.arrival = None  # Remove arrival info

        with_arrival = _make_departure(
            train_id="W1",
            dep_time=now + timedelta(minutes=15),
            arr_time=now + timedelta(minutes=40),
        )
        departures = [no_arrival, with_arrival]

        earliest_arrival = None
        for dep in departures:
            if dep.is_cancelled or not dep.arrival:
                continue
            arr_time = _get_best_time(dep.arrival)
            if arr_time and (earliest_arrival is None or arr_time < earliest_arrival):
                earliest_arrival = arr_time

        assert earliest_arrival == now + timedelta(minutes=40), (
            f"Departure without arrival should be skipped; "
            f"expected +40min, got {earliest_arrival}"
        )

    def test_no_valid_arrivals_returns_none(self):
        """When all departures are cancelled or lack arrivals, earliest_arrival is None."""
        now = datetime.now(ET)
        cancelled = _make_departure(
            train_id="C1",
            dep_time=now,
            arr_time=now + timedelta(minutes=20),
            is_cancelled=True,
        )
        departures = [cancelled]

        earliest_arrival = None
        for dep in departures:
            if dep.is_cancelled or not dep.arrival:
                continue
            arr_time = _get_best_time(dep.arrival)
            if arr_time and (earliest_arrival is None or arr_time < earliest_arrival):
                earliest_arrival = arr_time

        assert (
            earliest_arrival is None
        ), f"No valid arrivals should yield None, got {earliest_arrival}"

    def test_long_leg1_produces_far_future_leg2_window(self):
        """For a 3-hour leg 1 (like Amtrak WS→NY), leg 2 time_from should be ~3h out.

        This is the exact scenario that caused the original bug: Amtrak WS→NY
        arrives at ~12:30 PM, but leg 2 (LIRR NY→JAM) only returned the next
        20 departures from ~9:30 AM, all before 12:30.
        """
        now = datetime.now(ET)
        amtrak_dep = _make_departure(
            train_id="AMTK_123",
            from_code="WS",
            from_name="Washington",
            to_code="NY",
            to_name="New York Penn Station",
            dep_time=now + timedelta(minutes=10),
            arr_time=now + timedelta(hours=3, minutes=10),  # 3h trip
            data_source="AMTRAK",
        )

        from trackrat.services.trip_search import CONNECTION_BUFFER_MINUTES

        earliest_arrival = _get_best_time(amtrak_dep.arrival)
        walk_minutes = 5  # typical NY Penn transfer
        leg2_time_from = earliest_arrival + timedelta(
            minutes=walk_minutes + CONNECTION_BUFFER_MINUTES
        )

        # Leg 2 should start 3h10m + 7min = 3h17m from now
        expected_offset = timedelta(hours=3, minutes=10 + 5 + CONNECTION_BUFFER_MINUTES)
        assert leg2_time_from == now + expected_offset, (
            f"3-hour Amtrak leg 1 should push leg 2 window to +{expected_offset}, "
            f"got {leg2_time_from - now}"
        )


class TestDirectTripFallthroughBehavior:
    """Regression test for issue #921: search_trips must fall through to
    transfer search when direct departures exist but produce no usable trips.

    The bug: `search_trips` checked `if direct_response.departures:` and
    returned early even when all departures failed `_make_direct_trip`
    (returned None due to missing times). The fix: check whether any
    *converted* trips exist before returning.
    """

    def test_make_direct_trip_returns_none_for_all_none_times(self):
        """_make_direct_trip must return None when departure has no times.

        This is the precondition for the fallthrough bug: if all departures
        in a response produce None from _make_direct_trip, the search must
        not return an empty trips list — it should fall through to transfers.
        """
        dep = _make_departure()
        # Set departure info with no times at all
        dep.departure = _make_station_info(code="NP", name="Newark Penn Station")
        trip = _make_direct_trip(dep)
        assert trip is None, (
            "_make_direct_trip should return None when departure has no "
            "actual_time, updated_time, or scheduled_time"
        )

    def test_search_trips_checks_converted_trips_not_raw_departures(self):
        """Verify that search_trips guards on converted trips, not raw departures.

        Inspects the source of search_trips to ensure the early return is
        conditional on `direct_trips` (the list of successfully converted
        TripOption objects), NOT on `direct_response.departures` (the raw
        list from the departure service).
        """
        import ast
        import inspect
        import textwrap

        from trackrat.services import trip_search as module

        source = inspect.getsource(module)
        source = textwrap.dedent(source)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != "search_trips":
                continue

            # Find all `if` guards that lead to a return with search_type="direct"
            for child in ast.walk(node):
                if not isinstance(child, ast.If):
                    continue
                # Check if this if-block contains a return with "direct" in it
                block_source = ast.get_source_segment(source, child)
                if block_source and '"direct"' in block_source:
                    # The guard condition should reference direct_trips (or similar),
                    # NOT direct_response.departures
                    cond_source = ast.get_source_segment(source, child.test)
                    assert cond_source is not None
                    assert "direct_response.departures" not in cond_source, (
                        f"search_trips still guards on direct_response.departures "
                        f"instead of the converted trips list. "
                        f"Guard condition: {cond_source}. "
                        f"This causes empty results when departures exist but "
                        f"produce no usable trips (issue #921)."
                    )
                    break
            break


class TestRankTransferPoints:
    """Test transfer point ranking for deterministic, direction-symmetric truncation."""

    def _make_tp(
        self,
        station_a: str = "NY",
        system_a: str = "NJT",
        station_b: str = "PWC",
        system_b: str = "PATH",
        walk_minutes: int = 5,
        same_station: bool = False,
    ) -> TransferPoint:
        return TransferPoint(
            station_a=station_a,
            system_a=system_a,
            station_b=station_b,
            system_b=system_b,
            walk_meters=walk_minutes * 80.0,
            walk_minutes=walk_minutes,
            same_station=same_station,
        )

    def test_same_station_preferred_over_walk(self):
        """same_station transfers should rank before walk transfers."""
        walk = self._make_tp(station_a="HB", station_b="PHO", walk_minutes=5, same_station=False)
        same = self._make_tp(station_a="NP", station_b="PNK", walk_minutes=5, same_station=True)
        ranked = _rank_transfer_points(
            [walk, same], "TR", "PWC", {"NJT"}, {"PATH"}
        )
        assert ranked[0].same_station is True
        assert ranked[1].same_station is False

    def test_shorter_walk_preferred(self):
        """Shorter walk_minutes should rank before longer."""
        long_walk = self._make_tp(station_a="AA", station_b="BB", walk_minutes=10, same_station=False)
        short_walk = self._make_tp(station_a="CC", station_b="DD", walk_minutes=3, same_station=False)
        ranked = _rank_transfer_points(
            [long_walk, short_walk], "TR", "PWC", {"NJT"}, {"PATH"}
        )
        assert ranked[0].walk_minutes == 3
        assert ranked[1].walk_minutes == 10

    def test_direction_symmetric_ordering(self):
        """Ranking must produce identical order regardless of search direction.

        This is the core property that fixes issue #1062: reversing from/to
        stations and their system sets must not change which TPs survive truncation.
        """
        tp1 = self._make_tp(station_a="NP", system_a="NJT", station_b="PNK", system_b="PATH",
                            walk_minutes=5, same_station=True)
        tp2 = self._make_tp(station_a="HB", system_a="NJT", station_b="PHO", system_b="PATH",
                            walk_minutes=7, same_station=False)
        tp3 = self._make_tp(station_a="NY", system_a="NJT", station_b="S128", system_b="SUBWAY",
                            walk_minutes=5, same_station=False)

        forward = _rank_transfer_points(
            [tp1, tp2, tp3], "TR", "PWC", {"NJT", "AMTRAK"}, {"PATH", "SUBWAY"}
        )
        reverse = _rank_transfer_points(
            [tp1, tp2, tp3], "PWC", "TR", {"PATH", "SUBWAY"}, {"NJT", "AMTRAK"}
        )
        # Exact same ordering regardless of direction
        assert [tp.station_a for tp in forward] == [tp.station_a for tp in reverse]
        assert [tp.station_b for tp in forward] == [tp.station_b for tp in reverse]

    def test_stable_tiebreaker_on_station_codes(self):
        """When same_station and walk_minutes are equal, sort by canonical station/system codes."""
        tp_a = self._make_tp(station_a="BB", system_a="X", station_b="AA", system_b="Y",
                             walk_minutes=5, same_station=False)
        tp_b = self._make_tp(station_a="AA", system_a="X", station_b="CC", system_b="Y",
                             walk_minutes=5, same_station=False)
        ranked = _rank_transfer_points(
            [tp_a, tp_b], "Z1", "Z2", {"X"}, {"Y"}
        )
        # Canonical order: tp_a has sorted pair (AA,Y),(BB,X); tp_b has (AA,X),(CC,Y)
        # (AA,X) < (AA,Y) so tp_b comes first
        assert ranked[0] is tp_b
        assert ranked[1] is tp_a

    def test_empty_input(self):
        """Ranking an empty list should return an empty list."""
        assert _rank_transfer_points([], "A", "B", {"NJT"}, {"PATH"}) == []

    def test_single_element(self):
        """Single-element list is returned unchanged."""
        tp = self._make_tp()
        result = _rank_transfer_points([tp], "A", "B", {"NJT"}, {"PATH"})
        assert len(result) == 1
        assert result[0] is tp


class TestMaxTransferQueriesIncreased:
    """Verify MAX_TRANSFER_QUERIES is large enough to avoid aggressive truncation."""

    def test_max_transfer_queries_at_least_12(self):
        """Issue #1062: cap of 6 (3 TPs) was too aggressive. Must be >= 12."""
        assert MAX_TRANSFER_QUERIES >= 12

    def test_max_transfer_points_at_least_6(self):
        """With MAX_TRANSFER_QUERIES=12, at least 6 transfer points are evaluated."""
        assert MAX_TRANSFER_QUERIES // 2 >= 6


class TestTransferPointSymmetryIntegration:
    """Integration test using real transfer point data to verify direction symmetry.

    Uses the actual route topology to confirm that _find_relevant_transfer_points
    followed by _rank_transfer_points produces the same ranked list regardless
    of which direction the search runs.
    """

    @pytest.mark.parametrize(
        "station_a,station_b",
        [
            ("TR", "PWC"),   # NJT → PATH (Trenton to World Trade Center)
            ("HB", "P33"),   # NJT/PATH hub → PATH (Hoboken area)
            ("NP", "PHO"),   # NJT Newark → PATH Hoboken
        ],
        ids=["trenton-to-wtc", "hoboken-to-33rd", "newark-to-hoboken-path"],
    )
    def test_ranked_transfer_points_are_direction_symmetric(self, station_a: str, station_b: str):
        """Forward and reverse searches must produce identically ranked TPs.

        This catches the root cause of issue #1062: set iteration order in
        _find_relevant_transfer_points changes with direction, but after ranking
        the order must be identical.
        """
        from trackrat.config.transfer_points import get_systems_serving_station

        sys_a = get_systems_serving_station(station_a)
        sys_b = get_systems_serving_station(station_b)

        if not sys_a or not sys_b:
            pytest.skip(f"No systems found for {station_a} or {station_b}")

        fwd_tps = _find_relevant_transfer_points(sys_a, sys_b, station_a, station_b)
        rev_tps = _find_relevant_transfer_points(sys_b, sys_a, station_b, station_a)

        fwd_ranked = _rank_transfer_points(fwd_tps, station_a, station_b, sys_a, sys_b)
        rev_ranked = _rank_transfer_points(rev_tps, station_b, station_a, sys_b, sys_a)

        # Both directions should find the same transfer points (possibly in different
        # initial order), and after ranking they must be in identical order.
        fwd_keys = [
            frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            for tp in fwd_ranked
        ]
        rev_keys = [
            frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            for tp in rev_ranked
        ]
        assert fwd_keys == rev_keys, (
            f"Direction-dependent ordering detected for {station_a}↔{station_b}.\n"
            f"Forward:  {[(tp.station_a, tp.system_a, tp.station_b, tp.system_b) for tp in fwd_ranked]}\n"
            f"Reverse:  {[(tp.station_a, tp.system_a, tp.station_b, tp.system_b) for tp in rev_ranked]}"
        )
