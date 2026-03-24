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
    TRANSFER_POINTS,
    WALK_THRESHOLD_METERS,
    TransferPoint,
    _haversine_meters,
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


class TestTransferPointGeneration:
    """Test that known transfer points are discovered."""

    def test_total_count_reasonable(self):
        """Should find a meaningful number of transfers (not 0, not thousands)."""
        assert (
            30 < len(TRANSFER_POINTS) < 200
        ), f"Expected 30-200 transfer points, got {len(TRANSFER_POINTS)}"

    def test_all_transfers_are_cross_system(self):
        """Every transfer must connect different systems."""
        for tp in TRANSFER_POINTS:
            assert tp.system_a != tp.system_b, (
                f"Same-system transfer found: {tp.station_a}/{tp.system_a} "
                f"<-> {tp.station_b}/{tp.system_b}"
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
