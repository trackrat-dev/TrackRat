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
    FALLBACK_TRANSIT_MINUTES,
    MAX_TRANSFER_QUERIES,
    _cross_modal_hub_direct_trips,
    _departure_to_leg,
    _empty_response,
    _filter_cross_system_direct_trips,
    _filter_unreasonable_durations,
    _find_relevant_transfer_points,
    _get_best_time,
    _get_station_lines_expanded,
    _has_shared_line,
    _make_direct_trip,
    _orient_transfer,
    _rank_transfer_points,
    _resolve_arrival_time,
    _synthesize_alighting,
    _systems_for_station,
    search_trips,
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

    def test_njt_pascack_to_nec_finds_secaucus_junction(self):
        """Regression #1296: Pascack Valley (NH) -> NEC (NY) must surface the
        Secaucus (SE) intra-NJT junction. Before the fix, the junction only
        carried the first-generated line-pair ({NE}<->{NC}), which doesn't
        connect Pascack Valley, so this returned nothing."""
        transfers = _find_relevant_transfer_points(
            {"NJT"}, {"NJT"}, from_station="NH", to_station="NY"
        )
        assert any(
            tp.station_a == "SE" and tp.station_b == "SE" and tp.system_a == "NJT"
            for tp in transfers
        ), "Expected a Secaucus intra-NJT junction transfer for NH->NY"

    def test_njt_morris_essex_to_nec_finds_secaucus_junction(self):
        """Regression #1296: Madison (M&E) -> Trenton (NEC) also routes via SE."""
        transfers = _find_relevant_transfer_points(
            {"NJT"}, {"NJT"}, from_station="MA", to_station="TR"
        )
        assert any(
            tp.station_a == "SE" and tp.station_b == "SE" for tp in transfers
        ), "Expected a Secaucus junction transfer for Madison->Trenton"

    def test_lirr_branch_to_branch_finds_jamaica_junction(self):
        """Regression #1296: Ronkonkoma (RON) -> Long Beach (LBH) must surface
        the Jamaica (JAM) junction. Only the first branch-pair survived before
        the fix, so most LIRR inter-branch transfers were dropped."""
        transfers = _find_relevant_transfer_points(
            {"LIRR"}, {"LIRR"}, from_station="RON", to_station="LBH"
        )
        assert any(
            tp.station_a == "JAM" and tp.station_b == "JAM" for tp in transfers
        ), "Expected a Jamaica junction transfer for Ronkonkoma->Long Beach"


class TestStationLinesExpanded:
    """Test line lookup across physical station equivalences."""

    def test_penn_station_subway_platforms_expand_to_all_lines(self):
        # S128 (1/2/3) and SA28 (A/C/E) are equivalent subway platforms at Penn
        # Station; the rail code NY is a transfer, not an equivalence (#1355).
        lines = _get_station_lines_expanded("S128", "SUBWAY")
        assert {"1", "2", "3", "A", "C", "E"} <= set(lines)

    def test_grand_central_subway_platforms_expand_to_all_lines(self):
        # S631 (4/5/6), S723 (7), and S901 (GS shuttle) are equivalent subway
        # platforms at Grand Central; GCT is a transfer, not an equivalence (#1355).
        lines = _get_station_lines_expanded("S631", "SUBWAY")
        assert {"4", "5", "6", "7", "GS"} <= set(lines)

    def test_penn_station_rail_code_no_longer_expands_to_subway_lines(self):
        # NY (rail) and the subway platforms are a transfer, not an
        # equivalence, so the rail code alone yields no subway lines.
        lines = _get_station_lines_expanded("NY", "SUBWAY")
        assert lines == frozenset()


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
        walk = self._make_tp(
            station_a="HB", station_b="PHO", walk_minutes=5, same_station=False
        )
        same = self._make_tp(
            station_a="NP", station_b="PNK", walk_minutes=5, same_station=True
        )
        ranked = _rank_transfer_points([walk, same], "TR", "PWC", {"NJT"}, {"PATH"})
        assert ranked[0].same_station is True
        assert ranked[1].same_station is False

    def test_shorter_walk_preferred(self):
        """Shorter walk_minutes should rank before longer."""
        long_walk = self._make_tp(
            station_a="AA", station_b="BB", walk_minutes=10, same_station=False
        )
        short_walk = self._make_tp(
            station_a="CC", station_b="DD", walk_minutes=3, same_station=False
        )
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
        tp1 = self._make_tp(
            station_a="NP",
            system_a="NJT",
            station_b="PNK",
            system_b="PATH",
            walk_minutes=5,
            same_station=True,
        )
        tp2 = self._make_tp(
            station_a="HB",
            system_a="NJT",
            station_b="PHO",
            system_b="PATH",
            walk_minutes=7,
            same_station=False,
        )
        tp3 = self._make_tp(
            station_a="NY",
            system_a="NJT",
            station_b="S128",
            system_b="SUBWAY",
            walk_minutes=5,
            same_station=False,
        )

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
        tp_a = self._make_tp(
            station_a="BB",
            system_a="X",
            station_b="AA",
            system_b="Y",
            walk_minutes=5,
            same_station=False,
        )
        tp_b = self._make_tp(
            station_a="AA",
            system_a="X",
            station_b="CC",
            system_b="Y",
            walk_minutes=5,
            same_station=False,
        )
        ranked = _rank_transfer_points([tp_a, tp_b], "Z1", "Z2", {"X"}, {"Y"})
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

    def test_intra_system_ranked_before_cross_system(self):
        """Regression #1296: a relevance-verified intra-system junction must
        rank ahead of speculative cross-system transfers, even when the
        cross-system points sort earlier by station code. Otherwise the only
        useful transfer gets crowded out of the MAX_TRANSFER_QUERIES budget."""
        intra = self._make_tp(
            station_a="SE",
            system_a="NJT",
            station_b="SE",
            system_b="NJT",
            walk_minutes=5,
            same_station=True,
        )
        # Cross-system same-station transfers whose codes sort before "SE".
        cross = [
            self._make_tp(
                station_a=code,
                system_a="NJT",
                station_b=code,
                system_b="AMTRAK",
                walk_minutes=5,
                same_station=True,
            )
            for code in ("MP", "NB", "NP", "NY", "PH", "PJ")
        ]
        ranked = _rank_transfer_points(
            cross + [intra], "NH", "NY", {"NJT"}, {"NJT", "AMTRAK"}
        )
        assert ranked[0] is intra, "Intra-system junction must rank first"


class TestSecaucusJunctionBudget:
    """End-to-end transfer-selection regression for issue #1296.

    Combines the real route topology, _find_relevant_transfer_points, and
    _rank_transfer_points to confirm the Secaucus junction is actually queried
    for the reported New Bridge Landing -> NY Penn search in both the
    single-system and default multi-system cases.
    """

    def _secaucus_in_budget(self, from_systems: set[str], to_systems: set[str]) -> bool:
        transfers = _find_relevant_transfer_points(
            from_systems, to_systems, from_station="NH", to_station="NY"
        )
        ranked = _rank_transfer_points(transfers, "NH", "NY", from_systems, to_systems)
        budget = MAX_TRANSFER_QUERIES // 2
        return any(
            tp.station_a == "SE" and tp.station_b == "SE" and tp.system_a == "NJT"
            for tp in ranked[:budget]
        )

    def test_njt_only(self):
        """With data_sources=NJT, the Secaucus junction is selected."""
        assert self._secaucus_in_budget({"NJT"}, {"NJT"})

    def test_multi_source_not_crowded_out(self):
        """With no filter (NJT+AMTRAK+LIRR), Amtrak-shared stations must not
        crowd Secaucus out of the queried budget."""
        assert self._secaucus_in_budget({"NJT"}, {"NJT", "AMTRAK", "LIRR"})


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
            ("TR", "PWC"),  # NJT → PATH (Trenton to World Trade Center)
            ("HB", "P33"),  # NJT/PATH hub → PATH (Hoboken area)
            ("NP", "PHO"),  # NJT Newark → PATH Hoboken
        ],
        ids=["trenton-to-wtc", "hoboken-to-33rd", "newark-to-hoboken-path"],
    )
    def test_ranked_transfer_points_are_direction_symmetric(
        self, station_a: str, station_b: str
    ):
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


class TestSystemsForStation:
    """Verify _systems_for_station's hybrid lookup behavior.

    Native codes (codes that appear in a route topology) must return only
    their native systems — expanding cross-modal equivalence groups would
    defeat the cross-system direct-trip filter (#1121).  Alias-only codes
    (codes that are not in any route topology) fall back to expansion so
    they still resolve to the canonical station's systems.
    """

    def test_native_code_returns_native_systems_only(self):
        """S128 (subway) is in subway routes, so it stays SUBWAY-only.

        S128's equivalence group is now subway-only ({S128, SA28}); the Penn
        commuter-rail code (NY) is a cross-modal transfer, not an equivalence
        sibling (#1355), so no rail system leaks into the subway code's set.
        """
        assert _systems_for_station("S128") == {"SUBWAY"}

    def test_native_code_with_cross_modal_equivalence_unaffected(self):
        """NY (Penn) is shared by NJT/AMTRAK/LIRR; expansion would add SUBWAY.

        We want exactly the systems whose routes call at NY, not the systems
        of the equivalent subway codes (S128, SA28).
        """
        assert _systems_for_station("NY") == {"NJT", "AMTRAK", "LIRR"}

    def test_non_subway_code_includes_sibling_rail_systems(self):
        """NP (Newark Penn Station) is served natively by NJT/AMTRAK; its
        equivalent PNK is served by PATH at the same physical building.

        For non-subway station codes we include sibling systems from the
        equivalence group so a search NP→PWC surfaces direct PATH trains
        (issue #1172).  SUBWAY is still excluded from the cross-modal
        expansion of non-subway codes (preserves the #1121 filter).
        """
        assert _systems_for_station("NP") == {"NJT", "AMTRAK", "PATH"}
        # And symmetrically: PNK should see NJT/AMTRAK from its NP equivalent.
        assert _systems_for_station("PNK") == {"NJT", "AMTRAK", "PATH"}

    def test_alias_only_code_falls_back_to_expansion(self):
        """TS (Secaucus Lower Level) is alias-only and must resolve to NJT via SE."""
        # Precondition: TS is genuinely alias-only.
        assert get_systems_serving_station("TS") == set()
        # Fallback expansion picks up SE → NJT.
        assert "NJT" in _systems_for_station("TS")

    def test_unknown_code_returns_empty(self):
        """A completely unknown code returns empty (no native, no expansion)."""
        assert _systems_for_station("ZZZZ_NOT_A_STATION") == set()

    def test_amtrak_mnr_shared_station_includes_both(self):
        """Stations shared between Amtrak and Metro-North (e.g. New Rochelle)
        should surface both systems regardless of which code the user picks.
        """
        assert _systems_for_station("NRO") == {"AMTRAK", "MNR"}
        assert _systems_for_station("MNRC") == {"AMTRAK", "MNR"}

    def test_np_pwc_direct_filter_keeps_path_trips(self):
        """End-to-end check for issue #1172: a PATH train NP→PWC must survive
        _filter_cross_system_direct_trips so the user sees direct PATH service
        from Newark Penn Station to World Trade Center / Grove Street.
        """
        from_sys = _systems_for_station("NP")
        to_sys = _systems_for_station("PWC")
        valid = from_sys & to_sys
        assert "PATH" in valid, (
            f"PATH should be a valid direct system for NP→PWC. "
            f"from_systems={from_sys}, to_systems={to_sys}"
        )


class TestFilterCrossSystemDirectTrips:
    """Test filtering of direct trips that matched only via station equivalence expansion.

    When the departure service expands station codes across equivalence groups,
    it can return trains from systems that don't natively serve both endpoints.
    Any train whose data_source isn't in ``from_systems & to_systems`` is not a
    genuine direct trip and is filtered so the transfer search can propose the
    correct multi-leg trip. Cross-modal hub pairs (e.g. TR->S127) always have an
    empty intersection and so are fully filtered here (#1355).
    """

    def _make_trip_with_source(self, data_source: str) -> TripOption:
        """Helper to build a TripOption with a specific data_source."""
        now = datetime.now(ET)
        dep_time = now + timedelta(minutes=10)
        arr_time = dep_time + timedelta(minutes=30)
        leg = TripLeg(
            train_id="9999",
            journey_date=now.date(),
            line=LineInfo(code="NE", name="Test Line", color="#000000"),
            destination="Test",
            boarding=_make_station_info(code="A", name="A", scheduled=dep_time),
            alighting=_make_station_info(code="B", name="B", scheduled=arr_time),
            data_source=data_source,
            observation_type="OBSERVED",
            is_cancelled=False,
            train_position=TrainPosition(),
        )
        return TripOption(
            legs=[leg],
            transfers=[],
            departure_time=dep_time,
            arrival_time=arr_time,
            total_duration_minutes=30,
            is_direct=True,
        )

    def test_empty_list_returns_empty(self):
        result = _filter_cross_system_direct_trips([], {"NJT"}, {"NJT"})
        assert result == []

    def test_same_system_keeps_all(self):
        """When from and to are both served by NJT, NJT trips pass through."""
        trips = [self._make_trip_with_source("NJT")]
        result = _filter_cross_system_direct_trips(trips, {"NJT", "AMTRAK"}, {"NJT"})
        assert len(result) == 1
        assert result[0].legs[0].data_source == "NJT"

    def test_cross_system_filtered_out(self):
        """Rail trips are filtered when to_station is subway-only.

        Cross-modal case from=TR (NJT, AMTRAK) to=S128 (SUBWAY): rail trains
        that matched only via the departure service's equivalence expansion have
        no shared system with the subway destination, so none survive as direct.
        """
        trips = [
            self._make_trip_with_source("AMTRAK"),
            self._make_trip_with_source("NJT"),
        ]
        # TR is served by NJT+AMTRAK, S128 is served by SUBWAY only
        result = _filter_cross_system_direct_trips(
            trips,
            from_systems={"NJT", "AMTRAK"},
            to_systems={"SUBWAY"},
        )
        assert len(result) == 0, (
            f"Cross-system trips should be filtered when from and to have "
            f"no common system. Got: {[t.legs[0].data_source for t in result]}"
        )

    def test_disjoint_systems_returns_empty(self):
        """When no system serves both endpoints, all direct trips are filtered."""
        trips = [self._make_trip_with_source("AMTRAK")]
        result = _filter_cross_system_direct_trips(
            trips, from_systems={"AMTRAK"}, to_systems={"SUBWAY"}
        )
        assert len(result) == 0

    def test_shared_system_kept_different_system_filtered(self):
        """When from=NY (NJT,AMTRAK,LIRR) and to=TR (NJT,AMTRAK),
        NJT and AMTRAK trips pass but LIRR trips would be filtered.
        """
        trips = [
            self._make_trip_with_source("NJT"),
            self._make_trip_with_source("AMTRAK"),
            self._make_trip_with_source("LIRR"),
        ]
        result = _filter_cross_system_direct_trips(
            trips,
            from_systems={"NJT", "AMTRAK", "LIRR"},
            to_systems={"NJT", "AMTRAK"},
        )
        sources = [t.legs[0].data_source for t in result]
        assert "NJT" in sources, f"NJT should be kept, got {sources}"
        assert "AMTRAK" in sources, f"AMTRAK should be kept, got {sources}"
        assert "LIRR" not in sources, f"LIRR should be filtered, got {sources}"

    def test_subway_to_subway_direct(self):
        """Intra-subway trips should pass (both endpoints are SUBWAY)."""
        trips = [self._make_trip_with_source("SUBWAY")]
        result = _filter_cross_system_direct_trips(
            trips, from_systems={"SUBWAY"}, to_systems={"SUBWAY"}
        )
        assert len(result) == 1

    def test_penn_station_subway_to_trenton_filtered(self):
        """Reverse direction: from=S128 (SUBWAY) to=TR (NJT,AMTRAK).
        NJT trains from NY (matched via equivalence) should be filtered.
        """
        trips = [self._make_trip_with_source("NJT")]
        result = _filter_cross_system_direct_trips(
            trips,
            from_systems={"SUBWAY"},
            to_systems={"NJT", "AMTRAK"},
        )
        assert len(result) == 0, (
            f"NJT trip from equivalence-expanded S128→NY should not be "
            f"'direct'. Got: {[t.legs[0].data_source for t in result]}"
        )

    def test_grand_central_mnr_to_subway_filtered(self):
        """from=GCT (MNR) to=S631 (SUBWAY): MNR trips should be filtered."""
        trips = [self._make_trip_with_source("MNR")]
        result = _filter_cross_system_direct_trips(
            trips, from_systems={"MNR"}, to_systems={"SUBWAY"}
        )
        assert len(result) == 0

    def test_wtc_path_to_subway_filtered(self):
        """from=PWC (PATH) to=S138 (SUBWAY): PATH trips should be filtered."""
        trips = [self._make_trip_with_source("PATH")]
        result = _filter_cross_system_direct_trips(
            trips, from_systems={"PATH"}, to_systems={"SUBWAY"}
        )
        assert len(result) == 0

    def test_uses_real_station_systems(self):
        """Integration test with real get_systems_serving_station data.

        Verifies the fix for the exact scenario reported in issue #1121:
        from=TR to=S128 should have no valid direct systems.
        """
        from_sys = get_systems_serving_station("TR")
        to_sys = get_systems_serving_station("S128")
        assert (
            from_sys & to_sys == set()
        ), f"TR ({from_sys}) and S128 ({to_sys}) should have no common systems"

        trips = [
            self._make_trip_with_source("AMTRAK"),
            self._make_trip_with_source("NJT"),
        ]
        result = _filter_cross_system_direct_trips(trips, from_sys, to_sys)
        assert len(result) == 0, (
            f"All trips from TR to S128 should be filtered as cross-system. "
            f"from_systems={from_sys}, to_systems={to_sys}, "
            f"remaining: {[t.legs[0].data_source for t in result]}"
        )

    def test_alias_code_resolves_via_equivalence_expansion(self):
        """Alias-only codes (TS, SC) should resolve systems via expansion.

        TS (Secaucus Lower Level) is not in any route topology, so
        get_systems_serving_station("TS") returns empty. But expanding
        TS → {TS, SC, SE} and unioning their systems yields {"NJT"} via SE.
        Without expansion, from_systems would be empty and all direct trips
        from TS would be incorrectly filtered.
        """
        from trackrat.config.stations import expand_station_codes

        # Direct lookup returns empty for alias codes
        assert get_systems_serving_station("TS") == set()
        assert get_systems_serving_station("SC") == set()

        # But expansion resolves via SE
        expanded_systems: set[str] = set()
        for code in expand_station_codes("TS"):
            expanded_systems |= get_systems_serving_station(code)
        assert (
            "NJT" in expanded_systems
        ), f"TS should resolve to NJT via SE expansion, got {expanded_systems}"

        # NJT trip from TS to TR should be kept when using expanded systems
        trips = [self._make_trip_with_source("NJT")]
        to_sys = get_systems_serving_station("TR")
        result = _filter_cross_system_direct_trips(trips, expanded_systems, to_sys)
        assert len(result) == 1, (
            f"NJT trip from TS (expanded) to TR should be kept. "
            f"from_systems={expanded_systems}, to_systems={to_sys}"
        )

    def test_ny_to_trenton_keeps_njt_amtrak(self):
        """Sanity check: NY→TR is a normal direct route, nothing should be filtered."""
        from_sys = get_systems_serving_station("NY")
        to_sys = get_systems_serving_station("TR")
        valid = from_sys & to_sys
        assert "NJT" in valid, f"NJT should serve both NY and TR, got {valid}"
        assert "AMTRAK" in valid, f"AMTRAK should serve both NY and TR, got {valid}"

        trips = [
            self._make_trip_with_source("NJT"),
            self._make_trip_with_source("AMTRAK"),
        ]
        result = _filter_cross_system_direct_trips(trips, from_sys, to_sys)
        assert len(result) == 2, (
            f"Both NJT and AMTRAK should be kept for NY→TR, got "
            f"{[t.legs[0].data_source for t in result]}"
        )


class TestResolveArrivalTime:
    """Bug C from #1231: subway GTFS-RT often omits intermediate-stop arrivals,
    so the leg-matching loop must fall back to ``departure + estimate`` instead
    of dropping the candidate connection.
    """

    def test_fallback_constant_is_reasonable(self):
        """The estimate is a heuristic; sanity-check it sits in a sensible range."""
        assert 5 <= FALLBACK_TRANSIT_MINUTES <= 30, (
            f"FALLBACK_TRANSIT_MINUTES={FALLBACK_TRANSIT_MINUTES} is outside the "
            "5–30 minute range that makes sense for in-city subway / commuter hops."
        )

    def test_returns_real_arrival_when_present(self):
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, arr_time=now + timedelta(minutes=22))
        assert _resolve_arrival_time(dep) == now + timedelta(minutes=22)

    def test_returns_updated_arrival_when_no_actual(self):
        now = datetime.now(ET)
        dep = _make_departure()
        dep.arrival = _make_station_info(
            code="X", name="X", updated=now + timedelta(minutes=18)
        )
        assert _resolve_arrival_time(dep) == now + timedelta(minutes=18)

    def test_falls_back_to_departure_plus_estimate_when_arrival_missing(self):
        """Subway intermediate-stop case: arrival is None entirely."""
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, data_source="SUBWAY")
        dep.arrival = None
        expected = now + timedelta(minutes=FALLBACK_TRANSIT_MINUTES)
        assert _resolve_arrival_time(dep) == expected, (
            f"With no arrival info, should fall back to departure + "
            f"FALLBACK_TRANSIT_MINUTES ({FALLBACK_TRANSIT_MINUTES}min). "
            f"Expected {expected}, got {_resolve_arrival_time(dep)}"
        )

    def test_falls_back_when_arrival_station_info_has_no_times(self):
        """Arrival StationInfo exists but every time field is None."""
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, data_source="SUBWAY")
        dep.arrival = _make_station_info(code="X", name="X")  # all times None
        expected = now + timedelta(minutes=FALLBACK_TRANSIT_MINUTES)
        assert _resolve_arrival_time(dep) == expected

    def test_missing_arrival_does_not_fallback_for_non_subway(self):
        """Do not invent commuter/regional arrival times from a subway heuristic."""
        now = datetime.now(ET)
        dep = _make_departure(dep_time=now, data_source="NJT")
        dep.arrival = None
        assert _resolve_arrival_time(dep) is None

    def test_returns_none_when_both_arrival_and_departure_missing(self):
        """No data at all — cannot synthesize an arrival."""
        dep = _make_departure(data_source="SUBWAY")
        dep.arrival = None
        dep.departure = _make_station_info(code="X", name="X")  # all times None
        assert _resolve_arrival_time(dep) is None


class TestCrossModalHubsRouteAsTransfer:
    """Cross-modal mega-hubs (Penn, GCT, WTC) are modeled as transfers, not
    same-station equivalences (see CROSS_MODAL_HUBS). A rail<->subway pair must
    therefore share NO system, giving an empty direct-filter intersection so
    trip search falls through to transfer search (#1355).
    """

    def test_hub_subway_codes_stay_subway_only(self):
        """The subway platform codes at Penn/GCT/WTC keep only SUBWAY — the
        adjacent rail/PATH code is no longer an equivalence sibling."""
        assert _systems_for_station("S128") == {"SUBWAY"}  # Penn 1/2/3
        assert _systems_for_station("SA28") == {"SUBWAY"}  # Penn A/C/E
        assert _systems_for_station("S631") == {"SUBWAY"}  # GCT 4/5/6
        assert _systems_for_station("S138") == {"SUBWAY"}  # WTC

    def test_hub_rail_codes_carry_no_subway(self):
        """NY/GCT/PWC carry only their rail/PATH systems — no SUBWAY leaks in."""
        assert _systems_for_station("NY") == {"NJT", "AMTRAK", "LIRR"}
        assert "SUBWAY" not in _systems_for_station("GCT")
        assert "SUBWAY" not in _systems_for_station("PWC")
        assert "PATH" in _systems_for_station("PWC")

    def test_cross_modal_pairs_share_no_system(self):
        """Rail/PATH <-> subway hub pairs have an empty intersection, so the
        direct search produces nothing and transfer search takes over."""
        for a, b in [
            ("TR", "S127"),  # NJT Trenton <-> Times Sq (subway)
            ("S127", "TR"),
            ("MSTM", "S635"),  # MNR Stamford <-> Union Sq (subway)
            ("PWC", "S635"),  # PATH WTC <-> Union Sq (subway)
        ]:
            shared = _systems_for_station(a) & _systems_for_station(b)
            assert not shared, (
                f"{a}->{b} is cross-modal and must share no system "
                f"(routes as a transfer), got {shared}"
            )

    def test_pure_subway_pair_stays_strict(self):
        """Pure-subway stations stay SUBWAY-only (unchanged)."""
        assert _systems_for_station("SR01") == {"SUBWAY"}
        assert _systems_for_station("S701") == {"SUBWAY"}

    def test_same_station_cross_system_rail_still_direct(self):
        """Genuine same-station cross-system pairs are unchanged: NP<->PWC still
        share PATH via the NP/PNK equivalence, so they stay direct. Only the
        cross-MODAL (rail<->subway) hubs were reclassified as transfers.
        """
        valid = _systems_for_station("NP") & _systems_for_station("PWC")
        assert (
            "PATH" in valid
        ), f"NP<->PWC must keep PATH as a direct system, got {valid}"


class TestHasSharedLine:
    """Bug A/D from #1231: when origin and destination already share a line,
    transfer search has nothing useful to add (intra-system junctions don't
    connect a line to itself) and we should report ``no_direct_trains``
    instead of the misleading ``no_transfer_points``.
    """

    def test_same_subway_line_returns_true(self):
        """Two 7-line stations should be detected as sharing a line."""
        # S701 (Flushing 7) and S726 (Hudson Yards 7) are both pure 7.
        assert _has_shared_line(
            "S701", "S726", {"SUBWAY"}, {"SUBWAY"}
        ), "S701 and S726 are both 7-line stations and must report shared line"

    def test_overlapping_subway_complex_returns_true(self):
        """S635 (Union Sq 4/5/6 family) and S419 (Wall St 4/5) share 4 & 5."""
        assert _has_shared_line(
            "S635", "S419", {"SUBWAY"}, {"SUBWAY"}
        ), "Union Sq 4/5 and Wall St 4/5 share lines and must report shared line"

    def test_disjoint_subway_lines_returns_false(self):
        """G/L origin and 4/5 destination share no line → return False."""
        # SG29 (Metropolitan Av) = G/L; S419 (Wall St) = 4/5. Disjoint.
        assert not _has_shared_line(
            "SG29", "S419", {"SUBWAY"}, {"SUBWAY"}
        ), "G/L and 4/5 don't share a line — transfer search is legitimate"

    def test_no_common_system_returns_false(self):
        """NJT origin vs PATH destination — no common system at all."""
        assert not _has_shared_line("TR", "PWC", {"NJT", "AMTRAK"}, {"PATH"})

    def test_njt_north_jersey_coast_to_northeast_corridor_shared(self):
        """Sanity check on rail systems: NP (NEC) ↔ NY (NEC) share Northeast Corridor."""
        assert _has_shared_line("NP", "NY", {"NJT", "AMTRAK"}, {"NJT", "AMTRAK"})


class TestFilterCrossModalDirectTrips:
    """End-to-end check for #1355: ``search_trips`` builds the direct-filter
    intersection from ``_systems_for_station``. Cross-modal hub pairs share no
    system, so any rail train that only matched via the departure service's
    equivalence expansion is dropped and the trip routes as a transfer.
    """

    def _make_trip(self, data_source: str) -> TripOption:
        now = datetime.now(ET)
        dep_time = now + timedelta(minutes=10)
        arr_time = dep_time + timedelta(minutes=30)
        leg = TripLeg(
            train_id="TEST",
            journey_date=now.date(),
            line=LineInfo(code="NE", name="Test", color="#000000"),
            destination="Test",
            boarding=_make_station_info(code="A", name="A", scheduled=dep_time),
            alighting=_make_station_info(code="B", name="B", scheduled=arr_time),
            data_source=data_source,
            observation_type="OBSERVED",
            is_cancelled=False,
            train_position=TrainPosition(),
        )
        return TripOption(
            legs=[leg],
            transfers=[],
            departure_time=dep_time,
            arrival_time=arr_time,
            total_duration_minutes=30,
            is_direct=True,
        )

    def test_cross_modal_pair_drops_rail_direct_trips(self):
        """TR<->S127 is cross-modal (no shared system), so rail trains that
        matched only via equivalence expansion must NOT survive as direct."""
        for from_code, to_code in [("TR", "S127"), ("S127", "TR")]:
            from_systems = _systems_for_station(from_code)
            to_systems = _systems_for_station(to_code)
            trips = [self._make_trip("NJT"), self._make_trip("AMTRAK")]
            result = _filter_cross_system_direct_trips(trips, from_systems, to_systems)
            sources = [t.legs[0].data_source for t in result]
            assert sources == [], (
                f"{from_code}->{to_code} is cross-modal; rail trains must not "
                f"survive the direct filter (route as transfer), got {sources}"
            )

    def test_pure_subway_pair_excludes_unrelated_rail(self):
        """Subway-only pair without shared rail equivalents must drop NJT/MNR."""
        # SR01 (N) and S701 (7) have no equivalence groups.
        from_systems = _systems_for_station("SR01")
        to_systems = _systems_for_station("S701")
        trips = [
            self._make_trip("SUBWAY"),
            self._make_trip("NJT"),  # would be wrong to keep
            self._make_trip("MNR"),  # would be wrong to keep
        ]
        result = _filter_cross_system_direct_trips(trips, from_systems, to_systems)
        sources = [t.legs[0].data_source for t in result]
        assert sources == [
            "SUBWAY"
        ], f"Pure subway pair must filter out rail trains, got {sources}"


class TestSynthesizeAlighting:
    """PR #1235 codex P1: when ``dep.arrival`` is missing, the synthesized
    alighting StationInfo must carry the resolved fallback time so leg-level
    times don't disagree with trip-level ``arrival_time``.
    """

    def test_synthesizes_station_info_with_scheduled_time(self):
        when = datetime(2026, 5, 24, 14, 30, tzinfo=ET)
        info = _synthesize_alighting("S128", when)
        assert info.code == "S128"
        assert info.scheduled_time == when
        assert info.updated_time is None
        assert info.actual_time is None

    def test_get_best_time_returns_synthesized_value(self):
        """The trip-level arrival_time uses ``_resolve_arrival_time`` which
        ultimately reads the leg's alighting via ``_get_best_time``.  Both
        must end up at the same datetime — otherwise the leg breakdown
        contradicts the trip header.
        """
        when = datetime(2026, 5, 24, 14, 30, tzinfo=ET)
        info = _synthesize_alighting("S128", when)
        assert _get_best_time(info) == when

    def test_name_is_resolved_from_known_code(self):
        """Real station codes (e.g. S128 = 34St-Penn Station 7) get a name,
        not the bare code.  Clients render this name; a bare code would
        leak through to UI as e.g. "S128" with no station label.
        """
        info = _synthesize_alighting("S128", datetime.now(ET))
        # Don't hard-code the exact name string (it can change), just
        # confirm it isn't the raw code or an empty string.
        assert info.name and info.name != "S128"


class TestDepartureToLegAlightingOverride:
    """PR #1235 codex P1: ``_departure_to_leg`` must accept an override so
    callers can patch in a synthesized alighting StationInfo when
    ``dep.arrival`` is missing but a fallback arrival time was used at the
    trip level.  Without this, the leg-level times silently fall back to
    the boarding station's data and disagree with the trip header.
    """

    def test_override_replaces_alighting_when_arrival_present(self):
        """Override wins over real arrival — callers opt in deliberately."""
        dep = _make_departure(to_code="NY", to_name="New York Penn Station")
        override = _make_station_info(
            code="OTHER",
            name="Override Station",
            scheduled=datetime(2026, 5, 24, 14, 30, tzinfo=ET),
        )
        leg = _departure_to_leg(dep, alighting_override=override)
        assert leg.alighting.code == "OTHER"
        assert leg.alighting.scheduled_time == override.scheduled_time

    def test_override_used_when_arrival_missing(self):
        """Real fix scenario: dep.arrival is None and caller wants to surface
        the synthesized fallback time at the leg level too.
        """
        dep = _make_departure()
        dep.arrival = None
        when = datetime(2026, 5, 24, 14, 30, tzinfo=ET)
        override = _synthesize_alighting("S726", when)
        leg = _departure_to_leg(dep, alighting_override=override)
        assert leg.alighting.code == "S726"
        assert _get_best_time(leg.alighting) == when

    def test_no_override_falls_back_to_departure_when_arrival_missing(self):
        """Backward compat: callers that don't supply override keep the old
        fallback behavior (alighting copies dep.departure).  This is the
        legacy code path other call sites still rely on.
        """
        dep = _make_departure()
        dep.arrival = None
        leg = _departure_to_leg(dep)
        # Fallback path: alighting carries the departure's station data
        assert leg.alighting.code == dep.departure.code

    def test_no_override_uses_real_arrival(self):
        """Backward compat: callers that don't supply override and have a real
        arrival keep using it.  No regression for the common case.
        """
        dep = _make_departure(to_code="NY", to_name="New York Penn Station")
        leg = _departure_to_leg(dep)
        assert leg.alighting.code == "NY"


class TestSharedLineShortcutRespectsDataSources:
    """PR #1235 codex P2: the shared-line shortcut must run *after* the
    ``data_sources`` filter, so an excluded-system overlap can't short-
    circuit a search that should still try transfer routing through the
    user's enabled systems.

    These are unit tests against ``_has_shared_line`` using the same
    filtered system sets that ``search_trips`` now computes; an end-to-end
    integration test is in TestSharedLineEndToEnd below.
    """

    def test_njt_amtrak_overlap_invisible_when_user_only_enabled_subway(self):
        """NP (Newark Penn) and NY share NJT + AMTRAK on the NEC.  If the user
        only enabled SUBWAY, that rail overlap must NOT trigger the shortcut.
        """
        # Mirror what search_trips computes: from_systems/to_systems after
        # the data_sources filter has been applied.
        from_systems_filtered = {"NJT", "AMTRAK"} & {"SUBWAY"}  # = {}
        to_systems_filtered = {"NJT", "AMTRAK"} & {"SUBWAY"}  # = {}
        assert from_systems_filtered == set()
        # _has_shared_line with empty intersection returns False because the
        # loop body never executes — confirms the shortcut is dormant when
        # no common enabled system remains.
        assert not _has_shared_line(
            "NP", "NY", from_systems_filtered, to_systems_filtered
        )

    def test_njt_amtrak_overlap_still_triggers_when_user_enabled_them(self):
        """Sanity check: when the user kept NJT/AMTRAK enabled, the shortcut
        should still fire for shared-NEC pairs — that's the whole point of
        Bug A/D (#1231).
        """
        from_systems_filtered = {"NJT", "AMTRAK"} & {"NJT", "AMTRAK"}
        to_systems_filtered = {"NJT", "AMTRAK"} & {"NJT", "AMTRAK"}
        assert _has_shared_line("NP", "NY", from_systems_filtered, to_systems_filtered)

    def test_subway_overlap_invisible_when_user_only_enabled_rail(self):
        """Inverse: two subway-line-sharing stations, but user only enabled
        NJT/AMTRAK — the SUBWAY overlap must NOT trigger the shortcut, so
        the search proceeds to try rail transfers.
        """
        from_systems_filtered = {"SUBWAY"} & {"NJT", "AMTRAK"}  # = {}
        to_systems_filtered = {"SUBWAY"} & {"NJT", "AMTRAK"}  # = {}
        assert not _has_shared_line(
            "S701", "S726", from_systems_filtered, to_systems_filtered
        )


class TestSharedLineEndToEnd:
    """PR #1235 codex P2: end-to-end ``search_trips`` must not short-circuit
    to ``no_direct_trains`` when the shared line lives in a system the user
    filtered out via ``data_sources``.

    Patches ``DepartureService`` at module level so the test is hermetic
    (no DB).  Each stub call records its kwargs and returns an empty
    departures response.
    """

    class _StubResponse:
        def __init__(self, deps: list[TrainDeparture]):
            self.departures = deps

    class _StubDepartureService:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def get_departures(self, **kwargs):  # noqa: ANN003 - test stub
            self.calls.append(kwargs)
            return TestSharedLineEndToEnd._StubResponse([])

    @pytest.mark.asyncio
    async def test_shortcut_skipped_when_shared_line_system_is_excluded(
        self, monkeypatch
    ):
        """User enables only SUBWAY for an NP→NY search.  Direct (subway)
        returns nothing; rail overlap on NEC must NOT short-circuit to
        ``no_direct_trains`` — instead the search should land in
        ``no_systems`` because filtering NP/NY by SUBWAY removes the only
        common systems.
        """
        from trackrat.services import trip_search as ts_mod

        stub = self._StubDepartureService()
        monkeypatch.setattr(ts_mod, "DepartureService", lambda: stub)

        result = await search_trips(
            db=None,  # type: ignore[arg-type]  # stub doesn't read db
            from_station="NP",
            to_station="NY",
            data_sources=["SUBWAY"],
        )
        assert result.metadata["search_type"] != "no_direct_trains", (
            "Shared-line shortcut fired on a system the user filtered out — "
            f"should have proceeded past it. metadata={result.metadata}"
        )
        assert result.metadata["search_type"] == "no_systems", (
            f"Filtered NP/NY by SUBWAY should leave no enabled systems, "
            f"got metadata={result.metadata}"
        )

    @pytest.mark.asyncio
    async def test_shortcut_still_fires_when_user_enabled_shared_system(
        self, monkeypatch
    ):
        """Sanity check: when the user kept NJT enabled, NP→NY returns
        ``no_direct_trains`` (the legitimate shortcut path from #1231 A/D).
        Without this assertion the reorder fix could silently regress the
        Bug A/D behavior the original PR delivered.
        """
        from trackrat.services import trip_search as ts_mod

        stub = self._StubDepartureService()
        monkeypatch.setattr(ts_mod, "DepartureService", lambda: stub)

        result = await search_trips(
            db=None,  # type: ignore[arg-type]
            from_station="NP",
            to_station="NY",
            data_sources=["NJT"],
        )
        assert result.metadata["search_type"] == "no_direct_trains", (
            "NJT-enabled NP→NY with no real-time results should report "
            f"no_direct_trains, got {result.metadata}"
        )


class TestCrossModalHubEndpoint:
    """Issue #1587: a cross-modal hub (PWC/NY/GCT) as a trip *endpoint* must
    resolve the subway portion as a single direct SUBWAY leg, instead of the
    degenerate ``HUB -> HUB`` [PATH] leg that produced 0 trips in both directions.

    ``PWC`` (WTC / Oculus) is paired with subway complex codes including ``SR25``
    (WTC-Cortlandt, R/W). The real onward ride to 14 St-Union Sq (``S635``) is a
    single R/W subway leg; the PATH<->subway walk is the implicit transfer.
    """

    class _StubResponse:
        def __init__(self, deps: list[TrainDeparture]):
            self.departures = deps

    class _StubSession:
        """Async context manager standing in for ``get_session()`` (no DB)."""

        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    class _StubDepartureService:
        """Returns an R/W subway departure only for the S635<->SR25 pair."""

        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def get_departures(self, **kwargs):  # noqa: ANN003 - test stub
            self.calls.append(kwargs)
            frm = kwargs.get("from_station")
            to = kwargs.get("to_station")
            if {frm, to} == {"S635", "SR25"}:
                return TestCrossModalHubEndpoint._StubResponse(
                    [
                        _make_departure(
                            train_id="R100",
                            from_code=frm,
                            from_name="from",
                            to_code=to,
                            to_name="to",
                            data_source="SUBWAY",
                            line_code="R",
                        )
                    ]
                )
            return TestCrossModalHubEndpoint._StubResponse([])

    def _patch(self, monkeypatch, stub):
        from trackrat.services import trip_search as ts_mod

        monkeypatch.setattr(ts_mod, "DepartureService", lambda: stub)
        monkeypatch.setattr(ts_mod, "get_session", lambda: self._StubSession())

    @pytest.mark.asyncio
    async def test_hub_to_subway_returns_cross_modal_trip(self, monkeypatch):
        """``PWC -> S635`` yields a single-leg SUBWAY trip (was 0 trips)."""
        stub = self._StubDepartureService()
        self._patch(monkeypatch, stub)

        result = await search_trips(
            db=None,  # type: ignore[arg-type]
            from_station="PWC",
            to_station="S635",
        )

        assert result.metadata["search_type"] == "cross_modal", result.metadata
        assert len(result.trips) == 1
        leg = result.trips[0].legs[0]
        assert leg.data_source == "SUBWAY"
        assert leg.boarding.code == "SR25"  # WTC subway platform, not PWC
        assert result.trips[0].is_direct is True

    @pytest.mark.asyncio
    async def test_subway_to_hub_returns_cross_modal_trip(self, monkeypatch):
        """Reverse direction ``S635 -> PWC`` is symmetric (was 0 trips)."""
        stub = self._StubDepartureService()
        self._patch(monkeypatch, stub)

        result = await search_trips(
            db=None,  # type: ignore[arg-type]
            from_station="S635",
            to_station="PWC",
        )

        assert result.metadata["search_type"] == "cross_modal", result.metadata
        assert len(result.trips) == 1
        leg = result.trips[0].legs[0]
        assert leg.data_source == "SUBWAY"
        assert leg.boarding.code == "S635"
        assert leg.alighting.code == "SR25"

    @pytest.mark.asyncio
    async def test_helper_noop_when_neither_endpoint_is_hub(self):
        """Non-hub pairs return [] without issuing any departure query."""
        stub = self._StubDepartureService()
        trips = await _cross_modal_hub_direct_trips(
            stub, "S635", "SR20", None, None, None, False, None, 10
        )
        assert trips == []
        assert stub.calls == []  # short-circuits before querying

    @pytest.mark.asyncio
    async def test_helper_noop_when_subway_disabled(self):
        """A hub endpoint with SUBWAY filtered out returns [] and never queries."""
        stub = self._StubDepartureService()
        trips = await _cross_modal_hub_direct_trips(
            stub, "PWC", "S635", None, None, None, False, ["PATH"], 10
        )
        assert trips == []
        assert stub.calls == []

    @pytest.mark.asyncio
    async def test_helper_falls_through_when_no_subway_service(self, monkeypatch):
        """A hub paired with an unreachable subway stop yields no trip, so the
        caller falls through to transfer search rather than getting a false hit."""
        from trackrat.services import trip_search as ts_mod

        stub = self._StubDepartureService()  # only serves S635<->SR25
        monkeypatch.setattr(ts_mod, "get_session", lambda: self._StubSession())

        trips = await _cross_modal_hub_direct_trips(
            stub, "PWC", "S601", None, None, None, False, None, 10
        )
        assert trips == []
        # It did attempt subway queries (one per PWC subway code), all empty.
        assert stub.calls and all(c["data_sources"] == ["SUBWAY"] for c in stub.calls)
