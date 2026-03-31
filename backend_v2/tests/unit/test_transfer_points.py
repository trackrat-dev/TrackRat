"""
Unit tests for transfer point generation and lookup.
"""

import pytest

from trackrat.config.transfer_points import (
    TRANSFER_POINTS,
    TransferPoint,
    _estimate_walk_minutes,
    _haversine_meters,
    get_systems_serving_station,
    get_transfer_points,
    get_transfers_from_station,
    MIN_TRANSFER_MINUTES,
    WALK_THRESHOLD_METERS,
)


class TestHaversine:
    """Test haversine distance calculation."""

    def test_same_point_is_zero(self):
        assert _haversine_meters(40.7128, -74.0060, 40.7128, -74.0060) == 0.0

    def test_known_distance(self):
        """Penn Station to WTC is ~2.5km — verify rough accuracy."""
        penn = (40.7505, -73.9935)
        wtc = (40.7127, -74.0134)
        dist = _haversine_meters(*penn, *wtc)
        assert 4000 < dist < 5000, f"Expected ~4.3km, got {dist:.0f}m"

    def test_short_distance(self):
        """Two nearby points should be within expected range."""
        # ~100m apart
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
    """Test that transfer points are generated correctly."""

    def test_transfer_points_not_empty(self):
        """Transfer points should be auto-generated from station data."""
        assert len(TRANSFER_POINTS) > 0, "No transfer points were generated"

    def test_cross_system_transfers_exist(self):
        """Cross-system transfer points must exist."""
        cross = [tp for tp in TRANSFER_POINTS if tp.system_a != tp.system_b]
        assert len(cross) > 0, "No cross-system transfers found"

    def test_intra_subway_transfers_have_line_metadata(self):
        """Intra-subway transfers must have lines_a and lines_b populated."""
        intra = [
            tp for tp in TRANSFER_POINTS
            if tp.system_a == tp.system_b == "SUBWAY"
        ]
        assert len(intra) > 0, "No intra-subway transfers found"
        for tp in intra:
            assert tp.lines_a, f"{tp.station_a} missing lines_a"
            assert tp.lines_b, f"{tp.station_b} missing lines_b"
            assert tp.lines_a != tp.lines_b

    def test_same_station_transfers_have_zero_walk_meters(self):
        """Same-station transfers should have 0 walk distance."""
        same_station = [tp for tp in TRANSFER_POINTS if tp.same_station]
        for tp in same_station:
            assert tp.walk_meters == 0.0, (
                f"Same-station transfer {tp.station_a}({tp.system_a}) <-> "
                f"{tp.station_b}({tp.system_b}) has walk_meters={tp.walk_meters}"
            )

    def test_walking_transfers_within_threshold(self):
        """Walking transfers should be within WALK_THRESHOLD_METERS."""
        walking = [tp for tp in TRANSFER_POINTS if not tp.same_station]
        for tp in walking:
            assert tp.walk_meters <= WALK_THRESHOLD_METERS, (
                f"Transfer {tp.station_a} <-> {tp.station_b} has "
                f"walk_meters={tp.walk_meters} > {WALK_THRESHOLD_METERS}"
            )

    def test_shared_station_ny_generates_transfers(self):
        """NY Penn Station (shared by NJT, AMTRAK, LIRR) should generate transfers."""
        ny_transfers = [
            tp for tp in TRANSFER_POINTS if tp.station_a == "NY" or tp.station_b == "NY"
        ]
        assert (
            len(ny_transfers) >= 2
        ), f"Expected at least 2 transfer points for NY, got {len(ny_transfers)}"
        # Check that NJT-AMTRAK pair exists
        systems = set()
        for tp in ny_transfers:
            systems.add(tp.system_a)
            systems.add(tp.system_b)
        assert "NJT" in systems, "NY should be served by NJT"
        assert "AMTRAK" in systems, "NY should be served by AMTRAK"

    def test_no_duplicate_transfer_points(self):
        """No duplicate transfer points (same station pair and systems)."""
        seen = set()
        for tp in TRANSFER_POINTS:
            key = frozenset({(tp.station_a, tp.system_a), (tp.station_b, tp.system_b)})
            assert key not in seen, (
                f"Duplicate transfer: {tp.station_a}({tp.system_a}) <-> "
                f"{tp.station_b}({tp.system_b})"
            )
            seen.add(key)

    def test_walk_minutes_always_positive(self):
        """Walk minutes should always be at least MIN_TRANSFER_MINUTES."""
        for tp in TRANSFER_POINTS:
            assert tp.walk_minutes >= MIN_TRANSFER_MINUTES, (
                f"Transfer {tp.station_a} <-> {tp.station_b} has "
                f"walk_minutes={tp.walk_minutes} < {MIN_TRANSFER_MINUTES}"
            )


class TestTransferPointLookup:
    """Test transfer point lookup functions."""

    def test_get_transfer_points_njt_path(self):
        """NJT <-> PATH should have transfer points (e.g., at NP/Newark)."""
        tps = get_transfer_points("NJT", "PATH")
        assert len(tps) > 0, "Expected NJT <-> PATH transfer points"

    def test_get_transfer_points_bidirectional(self):
        """get_transfer_points should work in both directions."""
        ab = get_transfer_points("NJT", "AMTRAK")
        ba = get_transfer_points("AMTRAK", "NJT")
        assert len(ab) == len(ba), "Bidirectional lookup should return same count"

    def test_get_transfer_points_same_non_subway_system_empty(self):
        """Same non-subway system should return no transfer points."""
        assert get_transfer_points("NJT", "NJT") == []

    def test_get_transfer_points_subway_subway_has_results(self):
        """SUBWAY <-> SUBWAY should return intra-subway transfer points."""
        tps = get_transfer_points("SUBWAY", "SUBWAY")
        assert len(tps) > 0, "Expected SUBWAY intra-transfers"

    def test_get_transfers_from_station_ny(self):
        """NY Penn should have transfers to multiple systems."""
        tps = get_transfers_from_station("NY")
        assert len(tps) > 0, "NY should have transfer points"

    def test_get_transfers_from_unknown_station(self):
        """Unknown station should return empty list."""
        assert get_transfers_from_station("ZZZZZ") == []


class TestGetSystemsServingStation:
    """Test get_systems_serving_station function."""

    def test_ny_served_by_multiple_systems(self):
        """NY Penn is served by NJT, AMTRAK, and LIRR."""
        systems = get_systems_serving_station("NY")
        assert "NJT" in systems, "NY should be served by NJT"
        assert "AMTRAK" in systems, "NY should be served by AMTRAK"

    def test_unknown_station_returns_empty(self):
        """Unknown station returns empty set."""
        assert get_systems_serving_station("ZZZZZ") == set()

    def test_path_only_station(self):
        """PATH-only stations (like PNK) should only return PATH."""
        systems = get_systems_serving_station("PNK")
        assert systems == {"PATH"}, f"PNK should be served by PATH only, got {systems}"
