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

from datetime import date, datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from trackrat.config.transfer_points import get_transfer_points
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
    TripSearchResponse,
)
from trackrat.config.transfer_points import get_systems_serving_station
from trackrat.services.trip_search import (
    _departure_to_leg,
    _empty_response,
    _find_relevant_transfer_points,
    _get_best_time,
    _make_direct_trip,
    _orient_transfer,
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
