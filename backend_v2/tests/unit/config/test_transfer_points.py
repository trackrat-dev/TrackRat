"""
Unit tests for transfer point auto-generation.

Tests that the transfer map correctly discovers:
1. Shared station codes across systems
2. Station equivalence group transfers
3. Coordinate-proximity transfers
4. Lookup indexes for system pairs and individual stations
"""

import pytest

from trackrat.config.transfer_points import (
    MIN_TRANSFER_MINUTES,
    TRANSFER_POINTS,
    WALK_THRESHOLD_METERS,
    TransferPoint,
    _estimate_walk_minutes,
    _haversine_meters,
    get_intra_subway_transfers,
    get_subway_lines_at_station,
    get_systems_serving_station,
    get_transfer_points,
    get_transfers_from_station,
)


class TestHaversine:
    """Test haversine distance calculation."""

    def test_same_point_is_zero(self):
        assert _haversine_meters(40.75, -73.99, 40.75, -73.99) == 0.0

    def test_known_distance(self):
        # NY Penn (40.750046, -73.992358) to PATH 33rd St (40.7491, -73.9882)
        dist = _haversine_meters(40.750046, -73.992358, 40.7491, -73.9882)
        # Should be roughly 350-400m
        assert 300 < dist < 500, f"Expected ~350-400m, got {dist:.0f}m"

    def test_far_apart(self):
        # NY Penn to Newark Penn — should be many km
        dist = _haversine_meters(40.750046, -73.992358, 40.734221, -74.164554)
        assert dist > 10_000, f"Expected >10km, got {dist:.0f}m"

    def test_short_distance(self):
        """Two nearby points (~100m apart) should be within expected range."""
        lat, lon = 40.7128, -74.0060
        dist = _haversine_meters(lat, lon, lat + 0.0009, lon)
        assert 90 < dist < 110, f"Expected ~100m, got {dist:.0f}m"


class TestEstimateWalkMinutes:
    """Test walk time estimation."""

    def test_zero_meters_gives_minimum(self):
        assert _estimate_walk_minutes(0) == MIN_TRANSFER_MINUTES

    def test_short_distance_gives_minimum(self):
        """100m at 80m/min is ~1.25min, but floor is MIN_TRANSFER_MINUTES."""
        assert _estimate_walk_minutes(100) == MIN_TRANSFER_MINUTES

    def test_long_distance(self):
        """400m at 80m/min = 5min."""
        assert _estimate_walk_minutes(400) == MIN_TRANSFER_MINUTES

    def test_very_long_distance(self):
        """800m at 80m/min = 10min."""
        assert _estimate_walk_minutes(800) == 10


class TestTransferPointGeneration:
    """Test that known transfer points are discovered."""

    def test_total_count_reasonable(self):
        """Should find a meaningful number of transfers (not 0, not thousands)."""
        assert (
            30 < len(TRANSFER_POINTS) < 500
        ), f"Expected 30-500 transfer points, got {len(TRANSFER_POINTS)}"

    def test_cross_system_transfers_exist(self):
        """Cross-system transfers must exist."""
        cross = [tp for tp in TRANSFER_POINTS if tp.system_a != tp.system_b]
        assert len(cross) > 0, "No cross-system transfers found"

    def test_intra_subway_transfers_exist(self):
        """Intra-subway transfers must exist at station complexes."""
        intra = [
            tp
            for tp in TRANSFER_POINTS
            if tp.system_a == "SUBWAY" and tp.system_b == "SUBWAY"
        ]
        assert len(intra) > 0, "No intra-subway transfers found"
        # All intra-subway should be same-station (within a complex)
        for tp in intra:
            assert tp.same_station, (
                f"Intra-subway transfer {tp.station_a} <-> {tp.station_b} "
                f"should be same_station"
            )
            assert tp.lines_a, f"Intra-subway {tp.station_a} missing lines_a"
            assert tp.lines_b, f"Intra-subway {tp.station_b} missing lines_b"
            assert tp.lines_a != tp.lines_b, (
                f"Intra-subway {tp.station_a} <-> {tp.station_b} "
                f"should connect different line groups"
            )

    def test_walk_minutes_at_least_minimum(self):
        """Walk time should always be at least MIN_TRANSFER_MINUTES."""
        for tp in TRANSFER_POINTS:
            assert (
                tp.walk_minutes >= 5
            ), f"Walk time too low: {tp.station_a} <-> {tp.station_b} = {tp.walk_minutes}min"

    def test_walk_meters_within_threshold(self):
        """All proximity-based transfers should be within the threshold."""
        for tp in TRANSFER_POINTS:
            if not tp.same_station:
                assert (
                    tp.walk_meters <= WALK_THRESHOLD_METERS
                ), f"Transfer too far: {tp.station_a} <-> {tp.station_b} = {tp.walk_meters:.0f}m"

    def test_same_station_has_zero_walk_meters(self):
        """Same-station transfers should have 0 walk distance."""
        for tp in TRANSFER_POINTS:
            if tp.same_station:
                assert tp.walk_meters == 0.0, (
                    f"Same-station transfer has non-zero distance: "
                    f"{tp.station_a} <-> {tp.station_b} = {tp.walk_meters:.0f}m"
                )

    def test_no_duplicate_transfers(self):
        """No duplicate transfer pairs."""
        seen: set[frozenset[tuple[str, str]]] = set()
        for tp in TRANSFER_POINTS:
            key = frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            assert (
                key not in seen
            ), f"Duplicate transfer: {tp.station_a}/{tp.system_a} <-> {tp.station_b}/{tp.system_b}"
            seen.add(key)


class TestSharedStationCodes:
    """Test discovery of shared station codes across systems."""

    def test_ny_penn_shared_by_three_systems(self):
        """NY Penn Station code is used by NJT, Amtrak, and LIRR."""
        systems = get_systems_serving_station("NY")
        assert "NJT" in systems, "NJT should serve NY"
        assert "AMTRAK" in systems, "AMTRAK should serve NY"
        assert "LIRR" in systems, "LIRR should serve NY"

    def test_ny_penn_has_transfers_between_all_pairs(self):
        """NY should generate transfers: NJT<->AMTRAK, NJT<->LIRR, AMTRAK<->LIRR."""
        ny_transfers = [
            tp
            for tp in get_transfers_from_station("NY")
            if tp.same_station and tp.station_a == "NY" and tp.station_b == "NY"
        ]
        system_pairs = {frozenset({tp.system_a, tp.system_b}) for tp in ny_transfers}
        assert frozenset({"NJT", "AMTRAK"}) in system_pairs
        assert frozenset({"NJT", "LIRR"}) in system_pairs
        assert frozenset({"AMTRAK", "LIRR"}) in system_pairs

    def test_gct_shared_by_lirr_and_mnr(self):
        """Grand Central Terminal is shared by LIRR and MNR."""
        systems = get_systems_serving_station("GCT")
        assert "LIRR" in systems
        assert "MNR" in systems
        gct_transfers = [
            tp
            for tp in get_transfers_from_station("GCT")
            if tp.same_station and "GCT" in (tp.station_a, tp.station_b)
        ]
        assert len(gct_transfers) >= 1

    def test_newark_penn_shared_by_njt_and_amtrak(self):
        """Newark Penn (NP) is shared by NJT and Amtrak."""
        systems = get_systems_serving_station("NP")
        assert "NJT" in systems
        assert "AMTRAK" in systems


class TestEquivalenceGroupTransfers:
    """Test transfers from STATION_EQUIVALENCE_GROUPS."""

    @pytest.mark.parametrize(
        "amtrak_code,mnr_code,station_name",
        [
            ("STM", "MSTM", "Stamford"),
            ("NHV", "MNHV", "New Haven"),
            # NRO and CRT are in equivalence groups but not in any Amtrak route
            # in ALL_ROUTES, so they won't generate transfers.
            # BRP and POU are also valid Amtrak/MNR pairs:
            ("BRP", "MBGP", "Bridgeport"),
        ],
    )
    def test_amtrak_mnr_equivalence(self, amtrak_code, mnr_code, station_name):
        """Amtrak/MNR shared stations should be found as same-station transfers."""
        transfers = get_transfers_from_station(amtrak_code)
        matching = [
            tp
            for tp in transfers
            if tp.same_station and mnr_code in (tp.station_a, tp.station_b)
        ]
        assert (
            len(matching) >= 1
        ), f"No transfer found for {station_name}: {amtrak_code} <-> {mnr_code}"


class TestProximityTransfers:
    """Test coordinate-proximity-based transfer discovery."""

    def test_hoboken_njt_path(self):
        """NJT Hoboken (HB) should connect to PATH Hoboken (PHO)."""
        transfers = get_transfer_points("NJT", "PATH")
        hoboken = [
            tp
            for tp in transfers
            if "HB" in (tp.station_a, tp.station_b)
            and "PHO" in (tp.station_a, tp.station_b)
        ]
        assert len(hoboken) == 1, f"Expected 1 Hoboken transfer, got {len(hoboken)}"
        assert not hoboken[0].same_station  # Different codes = proximity-based
        assert hoboken[0].walk_meters < 200  # Very close

    def test_newark_njt_path(self):
        """NJT/Amtrak Newark (NP) should connect to PATH Newark (PNK)."""
        transfers = get_transfer_points("NJT", "PATH")
        newark = [
            tp
            for tp in transfers
            if "NP" in (tp.station_a, tp.station_b)
            and "PNK" in (tp.station_a, tp.station_b)
        ]
        assert len(newark) == 1
        assert newark[0].walk_meters < 200

    def test_lindenwold_njt_patco(self):
        """NJT Lindenwold (LW) should connect to PATCO Lindenwold (LND)."""
        transfers = get_transfer_points("NJT", "PATCO")
        lindenwold = [
            tp
            for tp in transfers
            if "LW" in (tp.station_a, tp.station_b)
            and "LND" in (tp.station_a, tp.station_b)
        ]
        assert len(lindenwold) == 1
        assert lindenwold[0].walk_meters < 100  # Adjacent stations

    def test_path_33rd_near_ny_penn(self):
        """PATH 33rd St (P33) should be a transfer to NY Penn (NJT/AMTRAK/LIRR)."""
        transfers = get_transfers_from_station("P33")
        penn_transfers = [
            tp for tp in transfers if "NY" in (tp.station_a, tp.station_b)
        ]
        assert len(penn_transfers) >= 1, "PATH 33rd St should connect to NY Penn"
        # Should be within walking distance but not same station
        for tp in penn_transfers:
            assert not tp.same_station
            assert tp.walk_meters < WALK_THRESHOLD_METERS


class TestLookupIndexes:
    """Test lookup functions."""

    def test_get_transfer_points_both_orderings(self):
        """get_transfer_points(A, B) and get_transfer_points(B, A) return same results."""
        njt_path = get_transfer_points("NJT", "PATH")
        path_njt = get_transfer_points("PATH", "NJT")
        assert len(njt_path) == len(path_njt)
        assert len(njt_path) > 0

    def test_get_transfer_points_no_results(self):
        """Non-connected systems return empty list."""
        result = get_transfer_points("PATCO", "LIRR")
        assert result == []

    def test_get_transfer_points_same_non_branching_system_empty(self):
        """Systems not in _INTRA_TRANSFER_SYSTEMS return no same-system transfers."""
        assert get_transfer_points("AMTRAK", "AMTRAK") == []
        assert get_transfer_points("PATCO", "PATCO") == []
        assert get_transfer_points("WMATA", "WMATA") == []

    def test_get_transfer_points_njt_njt_has_junction_transfers(self):
        """NJT intra-system should return junction transfers (e.g., NE/NC at Newark Penn)."""
        tps = get_transfer_points("NJT", "NJT")
        assert len(tps) > 0, "Expected NJT intra-system junction transfers"
        # All should be same-station, same-system with different line groups
        for tp in tps:
            assert tp.system_a == "NJT" and tp.system_b == "NJT"
            assert (
                tp.station_a == tp.station_b
            ), f"Intra-system junction should be same station, got {tp.station_a} != {tp.station_b}"
            assert tp.same_station is True
            assert (
                tp.lines_a != tp.lines_b
            ), f"Junction should connect different line groups at {tp.station_a}"

    def test_get_transfer_points_subway_subway_has_results(self):
        """SUBWAY <-> SUBWAY should return intra-subway transfer points."""
        tps = get_transfer_points("SUBWAY", "SUBWAY")
        assert len(tps) > 0, "Expected SUBWAY intra-transfers"

    def test_get_transfers_from_station_returns_list(self):
        """Known transfer station should return transfers."""
        result = get_transfers_from_station("NY")
        assert len(result) > 0

    def test_get_transfers_from_unknown_station(self):
        """Unknown station code returns empty list."""
        result = get_transfers_from_station("ZZZZZ")
        assert result == []

    def test_get_systems_serving_station(self):
        """Returns correct system set."""
        assert get_systems_serving_station("NY") == {"NJT", "AMTRAK", "LIRR"}

    def test_get_systems_serving_unknown_station(self):
        """Unknown station returns empty set."""
        assert get_systems_serving_station("ZZZZZ") == set()

    def test_path_only_station(self):
        """PATH-only stations (like PNK) should only return PATH."""
        systems = get_systems_serving_station("PNK")
        assert systems == {"PATH"}, f"PNK should be served by PATH only, got {systems}"


class TestTransferPointProperties:
    """Test TransferPoint dataclass properties."""

    def test_station_names(self):
        """station_a_name and station_b_name return human-readable names."""
        tp = TransferPoint(
            station_a="NY",
            system_a="NJT",
            station_b="P33",
            system_b="PATH",
            walk_meters=366.0,
            walk_minutes=5,
            same_station=False,
        )
        assert tp.station_a_name == "New York Penn Station"
        assert tp.station_b_name == "33rd Street"

    def test_lines_default_empty(self):
        """lines_a and lines_b default to empty frozensets."""
        tp = TransferPoint(
            station_a="NY",
            system_a="NJT",
            station_b="P33",
            system_b="PATH",
            walk_meters=0.0,
            walk_minutes=5,
            same_station=False,
        )
        assert tp.lines_a == frozenset()
        assert tp.lines_b == frozenset()


class TestIntraSubwayTransfers:
    """Test intra-subway transfer point generation and lookup."""

    def test_union_sq_transfer_exists(self):
        """Union Sq should have L <-> 4/5/6 transfer."""
        intra = get_intra_subway_transfers()
        union_sq = [
            tp for tp in intra if {"SL03", "S635"} <= {tp.station_a, tp.station_b}
        ]
        assert (
            len(union_sq) == 1
        ), f"Expected 1 Union Sq L<->4/5/6 transfer, got {len(union_sq)}"
        tp = union_sq[0]
        # One side should have L, other should have 4/5
        all_lines = tp.lines_a | tp.lines_b
        assert "L" in all_lines, "Union Sq transfer should include L line"
        assert "4" in all_lines, "Union Sq transfer should include 4 line"

    def test_times_sq_transfer_exists(self):
        """Times Sq should have transfers between its many line groups."""
        intra = get_intra_subway_transfers()
        # Times Sq complex: S127, S725, SA27, SR16, S902
        times_sq_codes = {"S127", "S725", "SA27", "SR16", "S902"}
        times_sq = [
            tp
            for tp in intra
            if tp.station_a in times_sq_codes and tp.station_b in times_sq_codes
        ]
        assert len(times_sq) > 0, "Times Sq should have intra-subway transfers"

    def test_fulton_st_transfer_exists(self):
        """Fulton St should have transfers across its complex (2/3 + 4/5 + A/C + J/Z)."""
        intra = get_intra_subway_transfers()
        fulton_codes = {"S229", "S418", "SA38", "SM22"}
        fulton = [
            tp
            for tp in intra
            if tp.station_a in fulton_codes and tp.station_b in fulton_codes
        ]
        assert len(fulton) > 0, "Fulton St should have intra-subway transfers"

    def test_no_same_line_transfers(self):
        """Intra-subway transfers should never connect the same line group."""
        intra = get_intra_subway_transfers()
        for tp in intra:
            assert tp.lines_a != tp.lines_b, (
                f"Same-line transfer found: {tp.station_a} ({tp.lines_a}) "
                f"<-> {tp.station_b} ({tp.lines_b})"
            )

    def test_intra_subway_indexed_correctly(self):
        """get_intra_subway_transfers should return same-system SUBWAY pairs."""
        intra = get_intra_subway_transfers()
        for tp in intra:
            assert tp.system_a == "SUBWAY"
            assert tp.system_b == "SUBWAY"

    def test_no_duplicates_in_intra_subway(self):
        """No duplicate pairs in intra-subway transfers."""
        intra = get_intra_subway_transfers()
        seen: set[frozenset[str]] = set()
        for tp in intra:
            key = frozenset({tp.station_a, tp.station_b})
            assert (
                key not in seen
            ), f"Duplicate intra-subway: {tp.station_a} <-> {tp.station_b}"
            seen.add(key)


class TestGetSubwayLinesAtStation:
    """Test subway line lookup with equivalence expansion."""

    def test_metropolitan_av_has_g_and_l(self):
        """Metropolitan Av (SG29) is in complex with Lorimer St (SL10) on L."""
        lines = get_subway_lines_at_station("SG29")
        assert "G" in lines, "SG29 should be on G line"
        assert "L" in lines, "SG29 equivalent SL10 should bring in L line"

    def test_wall_st_4_5(self):
        """Wall St (S419) should be on the 4 and 5 lines."""
        lines = get_subway_lines_at_station("S419")
        assert "4" in lines
        assert "5" in lines

    def test_union_sq_all_lines(self):
        """14 St-Union Sq (S635) should include 4/5/6 + L + N/Q/R/W via equivalences."""
        lines = get_subway_lines_at_station("S635")
        assert "4" in lines
        assert "L" in lines, "S635 is equivalent to SL03 which is on L"
        assert "N" in lines, "S635 is equivalent to SR20 which is on N/Q/R/W"

    def test_penn_station_subway_lines_from_rail_code(self):
        """NY should include 34 St-Penn subway lines through station equivalence."""
        lines = get_subway_lines_at_station("NY")
        assert {"1", "2", "3", "A", "C", "E"} <= set(lines)

    def test_grand_central_subway_lines_from_rail_code(self):
        """GCT should include Grand Central-42 St subway lines through equivalence."""
        lines = get_subway_lines_at_station("GCT")
        assert {"4", "5", "6", "7", "GS"} <= set(lines)

    def test_unknown_station_returns_empty(self):
        """Unknown station returns empty frozenset."""
        lines = get_subway_lines_at_station("ZZZZZ")
        assert lines == frozenset()

    def test_non_subway_station_returns_empty(self):
        """Non-subway station (NJT) returns empty frozenset."""
        lines = get_subway_lines_at_station("TR")
        assert lines == frozenset()
