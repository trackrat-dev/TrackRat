"""
Unit tests for scripts/generate_route_shapes.py (issue #1559).

Amtrak shipped with near-zero shape coverage because the generator processed
only the first 200 trips per feed — and the Amtrak feed leads with hundreds of
Thruway connecting-bus trips, so the budget was spent before any rail route
was reached. These tests cover the fixes: the rail route_type filter, per-route
trip sampling, polyline-projection anchoring, topology-pair slicing, and
cross-provider key deduplication (a Swift dictionary literal with duplicate
keys is a runtime crash).

The iOS-file parsers are tested against the real RouteTopology.swift and
StationCoordinates.swift so regex drift against those files fails loudly.
"""

import os
import sys

# Add scripts directory to path so we can import the generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))

from generate_route_shapes import (
    MAX_PATTERNS_PER_ROUTE,
    MAX_STATION_TO_SHAPE_M,
    ShapePoint,
    extract_segment_shapes,
    find_nearest_shape_position,
    merge_provider_shapes,
    parse_ios_station_coordinates,
    parse_ios_topology,
    rail_trip_filter,
    resolve_station_coords,
    slice_topology_pairs,
    topology_adjacent_pairs,
)


def _points(coords):
    """Build ShapePoints from (lat, lon) tuples with sequential sequence."""
    return [
        ShapePoint(lat=lat, lon=lon, sequence=i) for i, (lat, lon) in enumerate(coords)
    ]


class TestRailTripFilter:
    """Bus trips (route_type 3) must not consume the trip sampling budget."""

    ROUTES = [
        {"route_id": "rail", "route_type": "2"},
        {"route_id": "subway", "route_type": "1"},
        {"route_id": "trolley", "route_type": "0"},
        {"route_id": "thruway-bus", "route_type": "3"},
    ]

    def test_drops_bus_trips_keeps_rail(self):
        trips = [
            {"trip_id": "t1", "route_id": "rail"},
            {"trip_id": "t2", "route_id": "thruway-bus"},
            {"trip_id": "t3", "route_id": "subway"},
            {"trip_id": "t4", "route_id": "trolley"},
        ]
        kept = rail_trip_filter(trips, self.ROUTES)
        kept_ids = [t["trip_id"] for t in kept]
        assert kept_ids == [
            "t1",
            "t3",
            "t4",
        ], f"expected the Thruway bus trip filtered out, got {kept_ids}"

    def test_unknown_route_id_dropped(self):
        trips = [{"trip_id": "t1", "route_id": "not-in-routes-txt"}]
        assert rail_trip_filter(trips, self.ROUTES) == []

    def test_missing_routes_txt_passes_everything(self):
        trips = [{"trip_id": "t1", "route_id": "anything"}]
        assert rail_trip_filter(trips, []) == trips

    def test_routes_without_route_type_pass_everything(self):
        routes = [{"route_id": "r1"}, {"route_id": "r2", "route_type": ""}]
        trips = [{"trip_id": "t1", "route_id": "r1"}]
        assert rail_trip_filter(trips, routes) == trips


class TestPerRouteSampling:
    """A busy route must not starve other routes of shape extraction.

    This is the exact regression that left Amtrak with near-zero coverage:
    a global trip cap was exhausted by the first routes in stop_times order.
    """

    def _synthetic_feed(self, busy_trip_count, distinct_patterns=False):
        # Straight north-south line through three real Amtrak stops whose GTFS
        # stop_ids map to internal codes via the real backend mapping
        # (NYP -> NY, PHL -> PH, WIL -> WI). No mocks — real code mapping.
        shape_a = _points([(40.75, -74.0), (40.0, -74.5), (39.95, -75.18)])
        shape_b = _points([(39.95, -75.18), (39.8, -75.3), (39.74, -75.55)])
        shapes = {"shape_a": shape_a, "shape_b": shape_b}

        stops = [
            {
                "stop_id": "NYP",
                "stop_name": "New York Penn",
                "stop_lat": "40.75",
                "stop_lon": "-74.0",
            },
            {
                "stop_id": "PHL",
                "stop_name": "Philadelphia",
                "stop_lat": "39.95",
                "stop_lon": "-75.18",
            },
            {
                "stop_id": "WIL",
                "stop_name": "Wilmington",
                "stop_lat": "39.74",
                "stop_lon": "-75.55",
            },
        ]

        trips = []
        stop_times = []
        # Busy route: many trips NYP -> PHL. With distinct_patterns each trip
        # gets its own copy of the shape, making every (shape, stops) pattern
        # unique so each one consumes budget.
        for i in range(busy_trip_count):
            trip_id = f"busy-{i}"
            shape_id = "shape_a"
            if distinct_patterns:
                shape_id = f"shape_a_{i}"
                shapes[shape_id] = shape_a
            trips.append({"trip_id": trip_id, "route_id": "busy", "shape_id": shape_id})
            stop_times.append(
                {"trip_id": trip_id, "stop_sequence": "1", "stop_id": "NYP"}
            )
            stop_times.append(
                {"trip_id": trip_id, "stop_sequence": "2", "stop_id": "PHL"}
            )
        # Quiet route: a single trip PHL -> WIL on shape_b, listed last
        trips.append({"trip_id": "quiet-0", "route_id": "quiet", "shape_id": "shape_b"})
        stop_times.append(
            {"trip_id": "quiet-0", "stop_sequence": "1", "stop_id": "PHL"}
        )
        stop_times.append(
            {"trip_id": "quiet-0", "stop_sequence": "2", "stop_id": "WIL"}
        )

        return shapes, trips, stop_times, stops

    def test_quiet_route_survives_budget_exhausting_busy_route(self):
        # Busy route burns through more distinct patterns than its budget —
        # the quiet route must still be processed (per-route, not global, cap)
        shapes, trips, stop_times, stops = self._synthetic_feed(
            busy_trip_count=MAX_PATTERNS_PER_ROUTE + 25, distinct_patterns=True
        )
        segments = extract_segment_shapes("AMTRAK", shapes, trips, stop_times, stops)
        assert "NY-PH" in segments, f"busy route pair missing: {sorted(segments)}"
        assert "PH-WI" in segments, (
            "quiet route was starved by the busy route — per-route sampling "
            f"is broken. Got keys: {sorted(segments)}"
        )

    def test_duplicate_patterns_do_not_consume_budget(self):
        # Identical trips collapse to one pattern; even far more of them than
        # the budget must leave the quiet route unaffected
        shapes, trips, stop_times, stops = self._synthetic_feed(
            busy_trip_count=MAX_PATTERNS_PER_ROUTE * 2
        )
        segments = extract_segment_shapes("AMTRAK", shapes, trips, stop_times, stops)
        assert (
            "NY-PH" in segments and "PH-WI" in segments
        ), f"expected both pairs, got: {sorted(segments)}"

    def test_segment_points_run_in_canonical_order(self):
        shapes, trips, stop_times, stops = self._synthetic_feed(busy_trip_count=1)
        segments = extract_segment_shapes("AMTRAK", shapes, trips, stop_times, stops)
        # Key "NY-PH": points must run from NY (40.75) toward PH (39.95)
        points = segments["NY-PH"]
        assert (
            points[0][0] > points[-1][0]
        ), f"expected points to run NY -> PH (north to south), got {points}"


class TestFindNearestShapePosition:
    """Projection onto the polyline, not just nearest vertex.

    Long-distance shapes space vertices kilometers apart; Syracuse sits ~0 m
    from the Empire Corridor track but 3.5 km from the nearest vertex.
    """

    def test_station_between_sparse_vertices_projects_onto_line(self):
        # Two vertices ~22 km apart on a line of constant latitude
        shape = _points([(43.0, -76.3), (43.0, -76.03)])
        # Station on the line, halfway between the vertices
        dist, seg_idx, t, proj_lat, proj_lon = find_nearest_shape_position(
            shape, 43.0, -76.165
        )
        assert dist < 50, f"expected ~0 m to the line, got {dist:.0f} m"
        assert seg_idx == 0
        assert 0.4 < t < 0.6, f"expected projection near the middle, got t={t}"
        assert abs(proj_lat - 43.0) < 1e-9
        assert abs(proj_lon - (-76.165)) < 0.01

    def test_station_beyond_endpoint_clamps(self):
        shape = _points([(40.0, -74.0), (40.1, -74.0)])
        dist, seg_idx, t, proj_lat, proj_lon = find_nearest_shape_position(
            shape, 39.9, -74.0
        )
        assert t == 0.0 and seg_idx == 0
        assert (proj_lat, proj_lon) == (40.0, -74.0)
        assert 10_000 < dist < 12_500  # ~11.1 km per 0.1 degree latitude


class TestSliceTopologyPairs:
    """Coarse express hops must be cut from full-trip shapes."""

    # A shape through three "stations" A (index 0), mid vertex, B (index 2),
    # far vertex C (index 4)
    SHAPE = {
        "s1": _points(
            [
                (40.00, -74.00),
                (40.05, -74.02),
                (40.10, -74.00),
                (40.15, -73.98),
                (40.20, -74.00),
            ]
        )
    }
    COORDS = {
        "AA": {"lat": 40.00, "lon": -74.00},
        "CC": {"lat": 40.20, "lon": -74.00},
        "ZZ": {"lat": 45.00, "lon": -70.00},  # nowhere near the shape
    }

    def test_slices_between_stations_and_keeps_interior_vertices(self):
        result = slice_topology_pairs(self.SHAPE, {("AA", "CC")}, set(), self.COORDS)
        assert "AA-CC" in result, f"expected a slice, got {result}"
        points = result["AA-CC"]
        # Full span: endpoints at the stations, interior vertices preserved
        assert points[0] == (40.00, -74.00)
        assert points[-1] == (40.20, -74.00)
        assert (40.10, -74.00) in points, f"interior vertex lost: {points}"

    def test_direction_matches_canonical_key(self):
        # Same pair, canonical order reversed relative to travel direction:
        # key "AA-CC" must run from AA regardless of shape direction
        reversed_shape = {"s1": list(reversed(self.SHAPE["s1"]))}
        result = slice_topology_pairs(
            reversed_shape, {("AA", "CC")}, set(), self.COORDS
        )
        points = result["AA-CC"]
        assert points[0] == (
            40.00,
            -74.00,
        ), f"points must start at AA (canonical first), got {points[:2]}"

    def test_station_too_far_from_shape_is_skipped(self):
        result = slice_topology_pairs(self.SHAPE, {("AA", "ZZ")}, set(), self.COORDS)
        assert result == {}, (
            f"ZZ is ~500 km from the shape (> {MAX_STATION_TO_SHAPE_M} m) "
            f"but produced {result}"
        )

    def test_existing_keys_not_overwritten(self):
        result = slice_topology_pairs(
            self.SHAPE, {("AA", "CC")}, {"AA-CC"}, self.COORDS
        )
        assert result == {}, "trip-pass segments must win over topology slices"

    def test_missing_coordinates_skipped(self):
        result = slice_topology_pairs(self.SHAPE, {("AA", "XX")}, set(), self.COORDS)
        assert result == {}


class TestMergeProviderShapes:
    """Duplicate keys across providers crash a Swift dictionary literal."""

    def test_duplicate_key_emitted_once_most_points_wins(self):
        all_shapes = {
            "NJT": {"NP-NY": [(40.73, -74.16), (40.74, -74.1), (40.75, -74.0)]},
            "AMTRAK": {"NP-NY": [(40.73, -74.16), (40.75, -74.0)]},
        }
        merged = merge_provider_shapes(all_shapes)
        emitted = [
            (provider, key) for provider, shapes in merged.items() for key in shapes
        ]
        assert emitted == [
            ("NJT", "NP-NY")
        ], f"expected single emission under NJT (3 points beats 2), got {emitted}"

    def test_tie_goes_to_first_provider_alphabetically(self):
        pts = [(40.0, -74.0), (40.1, -74.0)]
        merged = merge_provider_shapes({"NJT": {"K-L": pts}, "AMTRAK": {"K-L": pts}})
        assert "K-L" in merged["AMTRAK"] and "K-L" not in merged["NJT"]

    def test_unique_keys_all_retained(self):
        all_shapes = {
            "NJT": {"A-B": [(1.0, 2.0), (1.1, 2.0)]},
            "AMTRAK": {"C-D": [(3.0, 4.0), (3.1, 4.0)]},
        }
        merged = merge_provider_shapes(all_shapes)
        assert merged["NJT"] == all_shapes["NJT"]
        assert merged["AMTRAK"] == all_shapes["AMTRAK"]


class TestIOSFileParsers:
    """Parse the real iOS files — regex drift must fail loudly, not silently
    produce an empty base-layer key set."""

    def test_parses_real_route_topology(self):
        topology = parse_ios_topology()
        assert "AMTRAK" in topology, f"providers found: {sorted(topology)}"
        assert (
            len(topology["AMTRAK"]) >= 15
        ), f"expected the ~20 iOS Amtrak routes, got {len(topology['AMTRAK'])}"
        nec = next(
            (codes for codes in topology["AMTRAK"] if "BOS" in codes and "WS" in codes),
            None,
        )
        assert nec is not None, "iOS Northeast Corridor route not parsed"

    def test_adjacent_pairs_include_coarse_express_hops(self):
        topology = parse_ios_topology()
        pairs = topology_adjacent_pairs("AMTRAK", topology)
        # OMA-DEN: iOS California Zephyr hop that no trip serves as
        # consecutive stops — the whole reason the topology pass exists
        assert ("DEN", "OMA") in pairs, "coarse Zephyr hop missing from pairs"
        for a, b in pairs:
            assert a < b, f"pair not canonically ordered: {(a, b)}"

    def test_parses_real_station_coordinates(self):
        coords = parse_ios_station_coordinates()
        assert len(coords) > 2000, f"expected ~2700 stations, got {len(coords)}"
        # GRB (Greensboro) is missing from the backend table and the current
        # Amtrak feed — iOS coordinates are its only anchor
        assert "GRB" in coords
        assert 35 < coords["GRB"]["lat"] < 37


class TestResolveStationCoords:
    def test_priority_feed_then_backend_then_ios(self):
        feed = {"NY": {"lat": 1.0, "lon": 1.0}}
        ios = {"NY": {"lat": 3.0, "lon": 3.0}, "GRB": {"lat": 36.07, "lon": -79.79}}
        resolved = resolve_station_coords({("GRB", "NY")}, feed, ios)
        assert resolved["NY"] == {"lat": 1.0, "lon": 1.0}, "feed coords must win"
        assert resolved["GRB"] == ios["GRB"], "iOS coords must backfill feed gaps"

    def test_backend_coords_beat_ios(self):
        # PH (Philadelphia 30th St) exists in the backend table
        ios = {"PH": {"lat": 0.0, "lon": 0.0}}
        resolved = resolve_station_coords({("NY", "PH")}, {}, ios)
        assert resolved["PH"]["lat"] != 0.0, "backend coords must beat iOS"

    def test_unresolvable_station_omitted(self):
        resolved = resolve_station_coords({("QQ", "QX")}, {}, {})
        assert resolved == {}
