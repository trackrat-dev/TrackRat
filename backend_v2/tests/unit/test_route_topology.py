"""
Unit tests for the route topology module.
"""

import pytest

from trackrat.config.route_topology import (
    ALL_ROUTES,
    NJT_NORTHEAST_CORRIDOR,
    NJT_NORTH_JERSEY_COAST,
    PATH_JSQ_33,
    PATH_NWK_WTC,
    PATCO_SPEEDLINE,
    AMTRAK_NEC,
    Route,
    find_route_for_segment,
    get_canonical_segments,
    get_route_by_line_code,
    get_routes_for_data_source,
)


class TestRouteBasics:
    """Test basic Route functionality."""

    def test_route_contains_segment_valid(self):
        """Test that contains_segment returns True for valid segments."""
        route = NJT_NORTHEAST_CORRIDOR
        assert route.contains_segment("NY", "SE") is True
        assert route.contains_segment("NY", "TR") is True
        assert route.contains_segment("NP", "ED") is True

    def test_route_contains_segment_invalid(self):
        """Test that contains_segment returns False for invalid segments."""
        route = NJT_NORTHEAST_CORRIDOR
        assert route.contains_segment("NY", "XX") is False
        assert route.contains_segment("XX", "YY") is False
        # NJCL station not on NEC
        assert route.contains_segment("NY", "BH") is False

    def test_route_get_intermediate_stations_forward(self):
        """Test getting intermediate stations in forward direction."""
        route = NJT_NORTHEAST_CORRIDOR
        # NY -> NP goes through SE
        stations = route.get_intermediate_stations("NY", "NP")
        assert stations == ["NY", "SE", "NP"]

    def test_route_get_intermediate_stations_reverse(self):
        """Test getting intermediate stations in reverse direction."""
        route = NJT_NORTHEAST_CORRIDOR
        # NP -> NY goes through SE (in reverse order)
        stations = route.get_intermediate_stations("NP", "NY")
        assert stations == ["NP", "SE", "NY"]

    def test_route_get_intermediate_stations_adjacent(self):
        """Test getting intermediate stations for adjacent stops."""
        route = NJT_NORTHEAST_CORRIDOR
        stations = route.get_intermediate_stations("NY", "SE")
        assert stations == ["NY", "SE"]

    def test_route_get_intermediate_stations_invalid(self):
        """Test getting intermediate stations for invalid segment."""
        route = NJT_NORTHEAST_CORRIDOR
        stations = route.get_intermediate_stations("NY", "XX")
        assert stations is None

    def test_route_expand_canonical_segments_skip_one(self):
        """Test expanding a segment that skips one station."""
        route = NJT_NORTHEAST_CORRIDOR
        # NY -> NP skips SE
        segments = route.expand_to_canonical_segments("NY", "NP")
        assert segments == [("NY", "SE"), ("SE", "NP")]

    def test_route_expand_canonical_segments_skip_multiple(self):
        """Test expanding a segment that skips multiple stations."""
        route = NJT_NORTHEAST_CORRIDOR
        # NY -> EZ skips SE, NP, NZ
        segments = route.expand_to_canonical_segments("NY", "EZ")
        assert segments == [
            ("NY", "SE"),
            ("SE", "NP"),
            ("NP", "NZ"),
            ("NZ", "EZ"),
        ]

    def test_route_expand_canonical_segments_adjacent(self):
        """Test expanding an already-adjacent segment."""
        route = NJT_NORTHEAST_CORRIDOR
        segments = route.expand_to_canonical_segments("NY", "SE")
        assert segments == [("NY", "SE")]

    def test_route_expand_canonical_segments_reverse(self):
        """Test expanding a segment in reverse direction."""
        route = NJT_NORTHEAST_CORRIDOR
        # NP -> NY in reverse
        segments = route.expand_to_canonical_segments("NP", "NY")
        assert segments == [("NP", "SE"), ("SE", "NY")]


class TestRouteLookups:
    """Test route lookup functions."""

    def test_get_route_by_line_code_njt(self):
        """Test NJT route lookup by line code."""
        route = get_route_by_line_code("NJT", "NE")
        assert route == NJT_NORTHEAST_CORRIDOR

        route = get_route_by_line_code("NJT", "NC")
        assert route == NJT_NORTH_JERSEY_COAST

    def test_get_route_by_line_code_path(self):
        """Test PATH route lookup by line code."""
        route = get_route_by_line_code("PATH", "JSQ-33")
        assert route == PATH_JSQ_33

        route = get_route_by_line_code("PATH", "NWK-WTC")
        assert route == PATH_NWK_WTC

    def test_get_route_by_line_code_patco(self):
        """Test PATCO route lookup by line code."""
        route = get_route_by_line_code("PATCO", "PATCO")
        assert route == PATCO_SPEEDLINE

    def test_get_route_by_line_code_invalid(self):
        """Test lookup with invalid line code."""
        route = get_route_by_line_code("NJT", "INVALID")
        assert route is None

    def test_get_routes_for_data_source(self):
        """Test getting all routes for a data source."""
        njt_routes = get_routes_for_data_source("NJT")
        assert len(njt_routes) > 0
        assert all(r.data_source == "NJT" for r in njt_routes)

        path_routes = get_routes_for_data_source("PATH")
        assert len(path_routes) > 0
        assert all(r.data_source == "PATH" for r in path_routes)

    def test_get_routes_for_invalid_data_source(self):
        """Test getting routes for invalid data source."""
        routes = get_routes_for_data_source("INVALID")
        assert routes == []


class TestFindRouteForSegment:
    """Test the find_route_for_segment function."""

    def test_find_route_with_line_code(self):
        """Test finding route with specific line code."""
        route = find_route_for_segment("NJT", "NY", "SE", line_code="NE")
        assert route == NJT_NORTHEAST_CORRIDOR

    def test_find_route_without_line_code(self):
        """Test finding route without line code (searches all routes)."""
        route = find_route_for_segment("NJT", "NY", "SE")
        # Should find a route that contains this segment
        assert route is not None
        assert route.contains_segment("NY", "SE")

    def test_find_route_for_unique_segment(self):
        """Test finding route for segment unique to one line."""
        # BH (Bay Head) is only on NJCL
        route = find_route_for_segment("NJT", "PP", "BH")
        assert route == NJT_NORTH_JERSEY_COAST

    def test_find_route_for_path_segment(self):
        """Test finding route for PATH segment."""
        route = find_route_for_segment("PATH", "PNK", "PHR")
        assert route is not None
        assert route.data_source == "PATH"

    def test_find_route_for_invalid_segment(self):
        """Test finding route for invalid segment."""
        route = find_route_for_segment("NJT", "XX", "YY")
        assert route is None


class TestGetCanonicalSegments:
    """Test the get_canonical_segments function."""

    def test_canonical_adjacent_segment(self):
        """Test that adjacent segments return as-is."""
        segments = get_canonical_segments("NJT", "NY", "SE")
        assert segments == [("NY", "SE")]

    def test_canonical_skip_one_station(self):
        """Test expanding segment that skips one station."""
        segments = get_canonical_segments("NJT", "NY", "NP", line_code="NE")
        assert segments == [("NY", "SE"), ("SE", "NP")]

    def test_canonical_skip_multiple_stations(self):
        """Test expanding segment that skips multiple stations."""
        segments = get_canonical_segments("NJT", "NY", "EZ", line_code="NE")
        assert segments == [
            ("NY", "SE"),
            ("SE", "NP"),
            ("NP", "NZ"),
            ("NZ", "EZ"),
        ]

    def test_canonical_unknown_segment(self):
        """Test that unknown segments pass through as-is."""
        segments = get_canonical_segments("NJT", "XX", "YY")
        assert segments == [("XX", "YY")]

    def test_canonical_path_segment(self):
        """Test expanding PATH segment."""
        # PJS -> PNP skips PGR
        segments = get_canonical_segments("PATH", "PJS", "PNP", line_code="JSQ-33")
        assert segments == [("PJS", "PGR"), ("PGR", "PNP")]

    def test_canonical_patco_segment(self):
        """Test expanding PATCO segment."""
        # LND -> WCT skips ASD
        segments = get_canonical_segments("PATCO", "LND", "WCT", line_code="PATCO")
        assert segments == [("LND", "ASD"), ("ASD", "WCT")]


class TestAllRoutesConsistency:
    """Test that all routes are properly configured."""

    def test_all_routes_have_required_fields(self):
        """Test that all routes have required fields populated."""
        for route in ALL_ROUTES:
            assert route.id, f"Route missing id"
            assert route.name, f"Route {route.id} missing name"
            assert route.data_source, f"Route {route.id} missing data_source"
            assert len(route.line_codes) > 0, f"Route {route.id} missing line_codes"
            assert (
                len(route.stations) >= 2
            ), f"Route {route.id} has fewer than 2 stations"

    def test_all_routes_have_unique_ids(self):
        """Test that all route IDs are unique."""
        ids = [route.id for route in ALL_ROUTES]
        assert len(ids) == len(set(ids)), "Duplicate route IDs found"

    def test_data_sources_are_valid(self):
        """Test that all data sources are valid."""
        valid_sources = {"NJT", "PATH", "PATCO", "AMTRAK"}
        for route in ALL_ROUTES:
            assert (
                route.data_source in valid_sources
            ), f"Route {route.id} has invalid data_source: {route.data_source}"

    def test_njt_routes_count(self):
        """Test that we have expected number of NJT routes."""
        njt_routes = [r for r in ALL_ROUTES if r.data_source == "NJT"]
        assert (
            len(njt_routes) >= 9
        ), f"Expected at least 9 NJT routes, got {len(njt_routes)}"

    def test_path_routes_count(self):
        """Test that we have expected number of PATH routes."""
        path_routes = [r for r in ALL_ROUTES if r.data_source == "PATH"]
        assert (
            len(path_routes) >= 5
        ), f"Expected at least 5 PATH routes, got {len(path_routes)}"

    def test_amtrak_routes_count(self):
        """Test that we have expected number of AMTRAK routes."""
        amtrak_routes = [r for r in ALL_ROUTES if r.data_source == "AMTRAK"]
        assert (
            len(amtrak_routes) >= 10
        ), f"Expected at least 10 AMTRAK routes, got {len(amtrak_routes)}"
