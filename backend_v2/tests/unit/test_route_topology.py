"""
Unit tests for the route topology module.
"""

import pytest

from trackrat.config.route_topology import (
    ALL_ROUTES,
    LIRR_BABYLON,
    LIRR_PORT_WASHINGTON,
    LIRR_PORT_WASHINGTON_GCT,
    LIRR_RONKONKOMA,
    MNR_HUDSON,
    MNR_NEW_HAVEN,
    NJT_NORTHEAST_CORRIDOR,
    NJT_NORTH_JERSEY_COAST,
    PATH_JSQ_33,
    PATH_NWK_WTC,
    PATCO_SPEEDLINE,
    AMTRAK_NEC,
    SUBWAY_A,
    SUBWAY_A_ROCKAWAY,
    SUBWAY_H,
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
        # NY -> EZ skips SE, NP, NA, NZ
        segments = route.expand_to_canonical_segments("NY", "EZ")
        assert segments == [
            ("NY", "SE"),
            ("SE", "NP"),
            ("NP", "NA"),
            ("NA", "NZ"),
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

    def test_get_route_by_line_code_lirr(self):
        """Test LIRR route lookup by line code."""
        route = get_route_by_line_code("LIRR", "LIRR-BB")
        assert route == LIRR_BABYLON

        route = get_route_by_line_code("LIRR", "LIRR-RK")
        assert route == LIRR_RONKONKOMA

    def test_get_route_by_line_code_lirr_port_washington(self):
        """Test LIRR-PW resolves to Penn Station variant, not GCT."""
        route = get_route_by_line_code("LIRR", "LIRR-PW")
        assert route == LIRR_PORT_WASHINGTON
        assert "NY" in route.stations, "LIRR-PW should map to Penn Station terminus"

    def test_port_washington_gct_has_no_line_codes(self):
        """GCT variant should have empty line_codes (resolved via segment lookup)."""
        assert len(LIRR_PORT_WASHINGTON_GCT.line_codes) == 0

    def test_get_route_by_line_code_mnr(self):
        """Test MNR route lookup by line code."""
        route = get_route_by_line_code("MNR", "MNR-HUD")
        assert route == MNR_HUDSON

        route = get_route_by_line_code("MNR", "MNR-NH")
        assert route == MNR_NEW_HAVEN

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

        lirr_routes = get_routes_for_data_source("LIRR")
        assert len(lirr_routes) > 0
        assert all(r.data_source == "LIRR" for r in lirr_routes)

        mnr_routes = get_routes_for_data_source("MNR")
        assert len(mnr_routes) > 0
        assert all(r.data_source == "MNR" for r in mnr_routes)

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

    def test_find_route_for_lirr_segment_with_line_code(self):
        """Test finding LIRR route with line code."""
        route = find_route_for_segment("LIRR", "JAM", "BTA", line_code="LIRR-BB")
        assert route == LIRR_BABYLON

    def test_find_route_for_lirr_segment_without_line_code(self):
        """Test finding LIRR route without line code for unique segment."""
        # PWS (Port Washington) is only on the Port Washington Branch
        route = find_route_for_segment("LIRR", "NY", "PWS")
        assert route == LIRR_PORT_WASHINGTON

    def test_find_route_for_lirr_port_washington_gct(self):
        """Test finding LIRR Port Washington GCT route."""
        route = find_route_for_segment("LIRR", "GCT", "PWS")
        assert route is not None
        assert route == LIRR_PORT_WASHINGTON_GCT

    def test_find_route_for_mnr_segment(self):
        """Test finding MNR route with line code."""
        route = find_route_for_segment("MNR", "GCT", "MPOK", line_code="MNR-HUD")
        assert route == MNR_HUDSON

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
            ("NP", "NA"),
            ("NA", "NZ"),
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

    def test_canonical_lirr_adjacent(self):
        """Test LIRR adjacent segment stays as-is."""
        segments = get_canonical_segments("LIRR", "JAM", "VSM", line_code="LIRR-BB")
        assert segments == [("JAM", "VSM")]

    def test_canonical_lirr_skip_station(self):
        """Test LIRR segment expansion skipping one station."""
        # JAM -> LYN on Babylon skips VSM
        segments = get_canonical_segments("LIRR", "JAM", "LYN", line_code="LIRR-BB")
        assert segments == [("JAM", "VSM"), ("VSM", "LYN")]

    def test_canonical_lirr_trunk_expansion(self):
        """Test LIRR trunk segment expansion (NY to JAM)."""
        segments = get_canonical_segments("LIRR", "NY", "JAM", line_code="LIRR-BB")
        assert segments == [
            ("NY", "WDD"),
            ("WDD", "FHL"),
            ("FHL", "KGN"),
            ("KGN", "JAM"),
        ]

    def test_canonical_mnr_adjacent(self):
        """Test MNR adjacent segment stays as-is."""
        segments = get_canonical_segments("MNR", "GCT", "M125", line_code="MNR-HUD")
        assert segments == [("GCT", "M125")]

    def test_canonical_mnr_skip_station(self):
        """Test MNR segment expansion on Hudson Line."""
        # GCT -> MEYS skips M125
        segments = get_canonical_segments("MNR", "GCT", "MEYS", line_code="MNR-HUD")
        assert segments == [("GCT", "M125"), ("M125", "MEYS")]

    def test_canonical_mnr_branch(self):
        """Test MNR branch segment expansion."""
        # MSTM -> MTMH on New Canaan Branch skips MGLB and MSPD
        segments = get_canonical_segments("MNR", "MSTM", "MTMH", line_code="MNR-NC")
        assert segments == [
            ("MSTM", "MGLB"),
            ("MGLB", "MSPD"),
            ("MSPD", "MTMH"),
        ]

    def test_canonical_mnr_gct_to_waterbury(self):
        """Test that GCT -> MWTB expands through trunk + Waterbury branch.

        This is the core bug scenario: without trunk stations in the branch
        route, this segment could not be resolved and would pass through
        as a direct GCT -> MWTB line on the congestion map.
        """
        segments = get_canonical_segments("MNR", "GCT", "MWTB")
        # Should expand to many intermediate segments, not a direct pair
        assert len(segments) > 2, (
            f"GCT -> MWTB should expand through trunk + branch, "
            f"got only {len(segments)} segments: {segments}"
        )
        # First segment should start from GCT
        assert segments[0][0] == "GCT"
        # Last segment should end at MWTB
        assert segments[-1][1] == "MWTB"
        # Should pass through Bridgeport (MBGP), the junction station
        all_stations = [s[0] for s in segments] + [segments[-1][1]]
        assert "MBGP" in all_stations, (
            f"GCT -> MWTB expansion should pass through Bridgeport (MBGP), "
            f"stations: {all_stations}"
        )

    def test_canonical_mnr_gct_to_danbury(self):
        """Test that GCT -> MDBY expands through trunk + Danbury branch."""
        segments = get_canonical_segments("MNR", "GCT", "MDBY")
        assert len(segments) > 2
        assert segments[0][0] == "GCT"
        assert segments[-1][1] == "MDBY"
        # Should pass through South Norwalk (MSNW), the junction station
        all_stations = [s[0] for s in segments] + [segments[-1][1]]
        assert "MSNW" in all_stations

    def test_canonical_mnr_gct_to_new_canaan(self):
        """Test that GCT -> MNCA expands through trunk + New Canaan branch."""
        segments = get_canonical_segments("MNR", "GCT", "MNCA")
        assert len(segments) > 2
        assert segments[0][0] == "GCT"
        assert segments[-1][1] == "MNCA"
        # Should pass through Stamford (MSTM), the junction station
        all_stations = [s[0] for s in segments] + [segments[-1][1]]
        assert "MSTM" in all_stations

    def test_canonical_mnr_gct_to_mid_branch_station(self):
        """Test that GCT to a mid-branch station also expands correctly.

        When GTFS static backfill fails and only a few RT stops are visible,
        the synthetic GCT origin pairs with the first visible branch stop.
        """
        # GCT -> MANS (Ansonia, mid-Waterbury branch) should expand
        segments = get_canonical_segments("MNR", "GCT", "MANS")
        assert len(segments) > 2
        assert segments[0][0] == "GCT"
        assert segments[-1][1] == "MANS"


class TestAllRoutesConsistency:
    """Test that all routes are properly configured."""

    def test_all_routes_have_required_fields(self):
        """Test that all routes have required fields populated."""
        # Terminal approach routes intentionally have no line_codes
        # (trains are tagged with their destination branch's line_code)
        terminal_routes = {
            "lirr-atlantic",
            "lirr-grand-central",
            "lirr-port-washington-gct",
        }
        for route in ALL_ROUTES:
            assert route.id, f"Route missing id"
            assert route.name, f"Route {route.id} missing name"
            assert route.data_source, f"Route {route.id} missing data_source"
            if route.id not in terminal_routes:
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
        valid_sources = {"NJT", "PATH", "PATCO", "AMTRAK", "LIRR", "MNR", "SUBWAY", "WMATA"}
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

    def test_lirr_routes_count(self):
        """Test that we have expected number of LIRR routes."""
        lirr_routes = [r for r in ALL_ROUTES if r.data_source == "LIRR"]
        assert (
            len(lirr_routes) >= 13
        ), f"Expected at least 13 LIRR routes, got {len(lirr_routes)}"

    def test_mnr_routes_count(self):
        """Test that we have expected number of MNR routes."""
        mnr_routes = [r for r in ALL_ROUTES if r.data_source == "MNR"]
        assert (
            len(mnr_routes) >= 6
        ), f"Expected at least 6 MNR routes, got {len(mnr_routes)}"

    def test_lirr_routes_include_trunk(self):
        """Test that LIRR Jamaica-based routes include trunk stations."""
        trunk_stations = {"NY", "WDD", "FHL", "KGN", "JAM"}
        lirr_routes = [r for r in ALL_ROUTES if r.data_source == "LIRR"]
        for route in lirr_routes:
            if "JAM" in route.stations and route.id not in (
                "lirr-atlantic",
                "lirr-grand-central",
            ):
                assert trunk_stations.issubset(
                    set(route.stations)
                ), f"Route {route.id} missing trunk stations"

    def test_lirr_montauk_includes_babylon_stations(self):
        """Test Montauk route includes Babylon Branch stations.

        Montauk trains run via the Babylon Branch, so the Montauk route
        must include all Babylon stations for segment expansion to work.
        """
        from trackrat.config.route_topology import LIRR_MONTAUK, LIRR_BABYLON

        babylon_stations = set(LIRR_BABYLON.stations)
        montauk_stations = set(LIRR_MONTAUK.stations)
        assert babylon_stations.issubset(
            montauk_stations
        ), "Montauk route missing Babylon Branch stations"

    def test_mnr_branches_include_trunk(self):
        """Test MNR branch routes include New Haven trunk from GCT to junction.

        Branch routes must include the full trunk so that segments spanning
        the trunk and branch (e.g., GCT -> MWTB) can be resolved by a single
        route lookup.  This mirrors how LIRR routes include NY -> JAM trunk.
        """
        from trackrat.config.route_topology import (
            MNR_NEW_CANAAN,
            MNR_DANBURY,
            MNR_WATERBURY,
        )

        # All branches start from GCT
        assert MNR_NEW_CANAAN.stations[0] == "GCT"
        assert MNR_DANBURY.stations[0] == "GCT"
        assert MNR_WATERBURY.stations[0] == "GCT"

        # New Canaan includes trunk to Stamford then branch to New Canaan
        assert "MSTM" in MNR_NEW_CANAAN.stations
        assert MNR_NEW_CANAAN.stations[-1] == "MNCA"

        # Danbury includes trunk to South Norwalk then branch to Danbury
        assert "MSNW" in MNR_DANBURY.stations
        assert MNR_DANBURY.stations[-1] == "MDBY"

        # Waterbury includes trunk to Bridgeport then branch to Waterbury
        assert "MBGP" in MNR_WATERBURY.stations
        assert MNR_WATERBURY.stations[-1] == "MWTB"


class TestSubwayARockawayBranch:
    """Test the A train Rockaway Park branch route definition.

    The A train serves both the Far Rockaway branch (SH11-SH06-SH04)
    and the Rockaway Park branch (SH15-SH12-SH04) during late nights.
    SUBWAY_A_ROCKAWAY covers the latter variant.
    """

    def test_rockaway_route_exists_in_all_routes(self):
        """Test that SUBWAY_A_ROCKAWAY is registered in ALL_ROUTES."""
        assert SUBWAY_A_ROCKAWAY in ALL_ROUTES

    def test_rockaway_route_line_code(self):
        """Test that the Rockaway variant uses line code A."""
        assert "A" in SUBWAY_A_ROCKAWAY.line_codes

    def test_rockaway_route_data_source(self):
        """Test that the Rockaway variant is tagged as SUBWAY."""
        assert SUBWAY_A_ROCKAWAY.data_source == "SUBWAY"

    def test_rockaway_route_contains_rockaway_park_stations(self):
        """Test that the Rockaway variant includes SH15-SH12 (Rockaway Park branch)."""
        rockaway_park_stations = {"SH15", "SH14", "SH13", "SH12"}
        assert rockaway_park_stations.issubset(
            set(SUBWAY_A_ROCKAWAY.stations)
        ), f"Missing Rockaway Park stations: {rockaway_park_stations - set(SUBWAY_A_ROCKAWAY.stations)}"

    def test_rockaway_route_does_not_contain_far_rockaway_stations(self):
        """Test that the Rockaway variant does NOT include Far Rockaway branch stations."""
        far_rockaway_only = {"SH11", "SH10", "SH09", "SH08", "SH07", "SH06"}
        overlap = far_rockaway_only & set(SUBWAY_A_ROCKAWAY.stations)
        assert (
            len(overlap) == 0
        ), f"Rockaway Park route should not include Far Rockaway stations: {overlap}"

    def test_rockaway_route_shares_trunk_with_main_a(self):
        """Test that the Rockaway variant shares the full trunk (SH04 to SA02) with SUBWAY_A."""
        # Both routes should share everything from Broad Channel (SH04) northward
        main_a_trunk_idx = SUBWAY_A.stations.index("SH04")
        rockaway_trunk_idx = SUBWAY_A_ROCKAWAY.stations.index("SH04")

        main_trunk = SUBWAY_A.stations[main_a_trunk_idx:]
        rockaway_trunk = SUBWAY_A_ROCKAWAY.stations[rockaway_trunk_idx:]

        assert main_trunk == rockaway_trunk, (
            "Trunk stations from SH04 northward should match between "
            "SUBWAY_A and SUBWAY_A_ROCKAWAY"
        )

    def test_rockaway_route_branch_order(self):
        """Test that Rockaway Park stations are in correct geographic order."""
        stations = list(SUBWAY_A_ROCKAWAY.stations)
        # SH15 (Rockaway Park) -> SH14 -> SH13 -> SH12 -> SH04 (Broad Channel)
        sh15_idx = stations.index("SH15")
        sh14_idx = stations.index("SH14")
        sh13_idx = stations.index("SH13")
        sh12_idx = stations.index("SH12")
        sh04_idx = stations.index("SH04")
        assert (
            sh15_idx < sh14_idx < sh13_idx < sh12_idx < sh04_idx
        ), "Rockaway Park branch stations must be ordered SH15 -> SH14 -> SH13 -> SH12 -> SH04"

    def test_find_route_resolves_rockaway_segment(self):
        """Test that SH04->SH12 segment resolves to the Rockaway route.

        This is the critical bug fix: previously SH04->SH12 with line_code='A'
        could not be found because SUBWAY_A only has the Far Rockaway branch.
        """
        route = find_route_for_segment("SUBWAY", "SH04", "SH12", line_code="A")
        assert (
            route is not None
        ), "SH04->SH12 should be found in a route with line_code A"
        assert route.contains_segment("SH04", "SH12")
        assert (
            "SH15" in route._station_set
        ), "Found route should be the Rockaway Park variant"

    def test_find_route_resolves_far_rockaway_segment(self):
        """Test that SH04->SH06 segment still resolves to the main A route."""
        route = find_route_for_segment("SUBWAY", "SH04", "SH06", line_code="A")
        assert (
            route is not None
        ), "SH04->SH06 should be found in a route with line_code A"
        assert (
            "SH11" in route._station_set
        ), "Found route should be the Far Rockaway variant"

    def test_canonical_segments_rockaway_branch(self):
        """Test that skip-stop segments on Rockaway Park branch expand correctly."""
        # SH04 (Broad Channel) -> SH15 (Rockaway Park) should expand to 4 segments
        canonical = get_canonical_segments("SUBWAY", "SH04", "SH15")
        assert (
            len(canonical) == 4
        ), f"SH04->SH15 should expand to 4 canonical segments, got {len(canonical)}: {canonical}"
        expected = [
            ("SH04", "SH12"),
            ("SH12", "SH13"),
            ("SH13", "SH14"),
            ("SH14", "SH15"),
        ]
        assert canonical == expected, f"Expected {expected}, got {canonical}"

    def test_canonical_segments_cross_branch_sa28_to_sh15(self):
        """Test that the previously-broken SA28->SH15 segment now resolves correctly.

        This was the original bug: an A train with sparse GTFS-RT data had only
        SA28 (Penn Station) and SH15 (Rockaway Park) in its stop list, producing
        a phantom diagonal line across Brooklyn/Queens on the congestion map.
        """
        canonical = get_canonical_segments("SUBWAY", "SA28", "SH15")
        # Should now be expandable via SUBWAY_A_ROCKAWAY since both stations
        # are in that route
        assert len(canonical) > 1, (
            "SA28->SH15 should be expanded via SUBWAY_A_ROCKAWAY, "
            f"but got unresolved: {canonical}"
        )
        # First segment should start from SA28
        assert canonical[0][0] == "SA28"
        # Last segment should end at SH15
        assert canonical[-1][1] == "SH15"

    def test_main_a_route_still_in_line_code_lookup(self):
        """Test that the main SUBWAY_A route is still the direct line_code lookup.

        SUBWAY_A_ROCKAWAY is registered before SUBWAY_A in ALL_ROUTES, so the
        _ROUTES_BY_LINE_CODE dict should have SUBWAY_A as the direct lookup
        (it overwrites SUBWAY_A_ROCKAWAY).
        """
        route = get_route_by_line_code("SUBWAY", "A")
        assert route is not None
        # The main A route has Far Rockaway stations
        assert (
            "SH11" in route._station_set
        ), "Direct line_code lookup for 'A' should return the main Far Rockaway variant"


class TestNjtLineCodeConsistency:
    """Test that NJT line codes are consistent between collectors and topology.

    Collectors (schedule.py, gtfs.py) must produce codes that exist in
    the corresponding route's line_codes frozenset, so that
    get_route_by_line_code() can resolve them without falling back
    to brute-force segment search.
    """

    def test_schedule_collector_codes_match_topology(self):
        """Every code from parse_njt_line_code (full names) must be in some NJT route's line_codes."""
        from trackrat.collectors.njt.schedule import parse_njt_line_code

        test_names = [
            ("Northeast Corridor", "NE"),
            ("North Jersey Coast Line", "NC"),
            ("Gladstone Branch", "GL"),
            ("Montclair-Boonton Line", "MO"),
            ("Morris and Essex Line", "ME"),
            ("Raritan Valley Line", "RV"),
            ("Pascack Valley Line", "PV"),
            ("Bergen County Line", "BE"),
            ("Main Line", "MA"),
            ("Atlantic City Rail Line", "AC"),
            ("Princeton Shuttle", "PR"),
        ]
        for name, expected_code in test_names:
            code = parse_njt_line_code(name)
            assert (
                code == expected_code
            ), f"parse_njt_line_code({name!r}) = {code!r}, expected {expected_code!r}"
            route = get_route_by_line_code("NJT", code)
            assert route is not None, (
                f"Code {code!r} from parse_njt_line_code({name!r}) "
                f"not found in any NJT route's line_codes"
            )

    def test_gtfs_mapping_codes_match_topology(self):
        """Every code in NJT_LINE_CODE_MAPPING must be in some NJT route's line_codes."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        for gtfs_name, code in NJT_LINE_CODE_MAPPING.items():
            route = get_route_by_line_code("NJT", code)
            assert route is not None, (
                f"GTFS code {code!r} (from {gtfs_name!r}) "
                f"not found in any NJT route's line_codes"
            )

    def test_canonicalization_targets_match_topology(self):
        """Every target code in NJT_LINE_CANONICALIZATION must be in some NJT route's line_codes."""
        from trackrat.services.departure import NJT_LINE_CANONICALIZATION

        for old_code, canonical_code in NJT_LINE_CANONICALIZATION.items():
            route = get_route_by_line_code("NJT", canonical_code)
            assert route is not None, (
                f"Canonical code {canonical_code!r} (from {old_code!r}) "
                f"not found in any NJT route's line_codes"
            )

    def test_morris_essex_distinct_from_montclair_boonton(self):
        """Morris & Essex ('ME') and Montclair-Boonton ('MO') must resolve to different routes."""
        me_route = get_route_by_line_code("NJT", "ME")
        mo_route = get_route_by_line_code("NJT", "MO")
        assert me_route is not None
        assert mo_route is not None
        assert me_route.id != mo_route.id, (
            f"ME and MO should resolve to different routes, "
            f"both resolved to {me_route.id}"
        )

    def test_atlantic_city_line_has_full_stations(self):
        """Atlantic City Line should have all intermediate stations, not just PH-TR."""
        from trackrat.config.route_topology import NJT_ATLANTIC_CITY

        assert len(NJT_ATLANTIC_CITY.stations) >= 9, (
            f"Atlantic City Line should have at least 9 stations (PH to AC), "
            f"got {len(NJT_ATLANTIC_CITY.stations)}: {NJT_ATLANTIC_CITY.stations}"
        )
        assert NJT_ATLANTIC_CITY.stations[0] == "PH"
        assert NJT_ATLANTIC_CITY.stations[-1] == "AC"

    def test_all_njt_stations_have_names(self):
        """Every station code in NJT routes should have a name in NJT_STATION_NAMES."""
        from trackrat.config.stations.njt import NJT_STATION_NAMES
        from trackrat.config.stations.common import STATION_NAMES

        all_names = {**STATION_NAMES, **NJT_STATION_NAMES}
        njt_routes = get_routes_for_data_source("NJT")
        missing = []
        for route in njt_routes:
            for station in route.stations:
                if station not in all_names:
                    missing.append((route.id, station))
        assert missing == [], f"NJT stations missing names: {missing}"


class TestAmtrakNECIntermediateStations:
    """Test that Amtrak NEC/Keystone routes include shared NJT intermediate stations.

    Amtrak NEC and Keystone trains stop at Metropark, New Brunswick, and
    Princeton Junction between Newark Penn and Trenton. These stations must
    be in the Amtrak route topologies for segment expansion to work correctly.
    """

    def test_amtrak_nec_contains_metropark(self):
        """Metropark (MP) should be in Amtrak NEC between NP and TR."""
        assert "MP" in AMTRAK_NEC.stations, "Amtrak NEC should include Metropark (MP)"
        stations = list(AMTRAK_NEC.stations)
        assert (
            stations.index("NP") < stations.index("MP") < stations.index("TR")
        ), "MP should be between NP and TR in station order"

    def test_amtrak_nec_contains_new_brunswick(self):
        """New Brunswick (NB) should be in Amtrak NEC between NP and TR."""
        assert (
            "NB" in AMTRAK_NEC.stations
        ), "Amtrak NEC should include New Brunswick (NB)"

    def test_amtrak_nec_contains_princeton_junction(self):
        """Princeton Junction (PJ) should be in Amtrak NEC between NP and TR."""
        assert (
            "PJ" in AMTRAK_NEC.stations
        ), "Amtrak NEC should include Princeton Junction (PJ)"

    def test_amtrak_nec_contains_cornwells_heights(self):
        """Cornwells Heights (CWH) should be in Amtrak NEC between TR and PH."""
        assert (
            "CWH" in AMTRAK_NEC.stations
        ), "Amtrak NEC should include Cornwells Heights (CWH)"
        stations = list(AMTRAK_NEC.stations)
        assert (
            stations.index("TR") < stations.index("CWH") < stations.index("PH")
        ), "CWH should be between TR and PH in station order"

    def test_amtrak_nec_contains_north_philadelphia(self):
        """North Philadelphia (PHN) should be in Amtrak NEC between TR and PH."""
        assert (
            "PHN" in AMTRAK_NEC.stations
        ), "Amtrak NEC should include North Philadelphia (PHN)"

    def test_amtrak_nec_contains_new_rochelle(self):
        """New Rochelle (NRO) should be in Amtrak NEC between STM and NY."""
        assert (
            "NRO" in AMTRAK_NEC.stations
        ), "Amtrak NEC should include New Rochelle (NRO)"
        stations = list(AMTRAK_NEC.stations)
        assert (
            stations.index("STM") < stations.index("NRO") < stations.index("NY")
        ), "NRO should be between STM and NY in station order"

    def test_amtrak_nec_segment_ny_to_pj_resolves(self):
        """Segment NY→PJ should resolve to Amtrak NEC route."""
        route = find_route_for_segment("AMTRAK", "NY", "PJ")
        assert route is not None, "NY→PJ should resolve to an Amtrak route"
        assert (
            route.id == "amtrak-nec"
        ), f"NY→PJ should resolve to amtrak-nec, got {route.id}"

    def test_amtrak_nec_segment_mp_to_tr_expands(self):
        """Segment MP→TR should expand to canonical segments via Amtrak NEC."""
        segments = get_canonical_segments("AMTRAK", "MP", "TR")
        assert (
            len(segments) > 1
        ), f"MP→TR should expand to multiple segments, got: {segments}"
        assert segments[0][0] == "MP"
        assert segments[-1][1] == "TR"

    def test_amtrak_keystone_contains_shared_stations(self):
        """Keystone should include MP, NB, PJ, CWH, PHN."""
        from trackrat.config.route_topology import AMTRAK_KEYSTONE

        for code in ("MP", "NB", "PJ", "CWH", "PHN"):
            assert (
                code in AMTRAK_KEYSTONE.stations
            ), f"Amtrak Keystone should include {code}"


class TestAmtrakEmpireServiceStations:
    """Test that Amtrak Empire Service includes Hudson Valley stations."""

    def test_empire_service_contains_hudson_valley_stations(self):
        """Empire Service should include intermediate Hudson Valley stops."""
        from trackrat.config.route_topology import AMTRAK_EMPIRE_SERVICE

        hudson_valley = ["YNY", "CRT", "POU", "RHI", "HUD", "SDY"]
        for code in hudson_valley:
            assert (
                code in AMTRAK_EMPIRE_SERVICE.stations
            ), f"Empire Service should include {code}"

    def test_empire_service_station_order(self):
        """Hudson Valley stations should be in correct geographic order."""
        from trackrat.config.route_topology import AMTRAK_EMPIRE_SERVICE

        stations = list(AMTRAK_EMPIRE_SERVICE.stations)
        expected_order = ["NY", "YNY", "CRT", "POU", "RHI", "HUD", "SDY", "ALB"]
        for i in range(len(expected_order) - 1):
            a, b = expected_order[i], expected_order[i + 1]
            assert stations.index(a) < stations.index(
                b
            ), f"{a} should come before {b} in Empire Service stations"

    def test_empire_service_segment_ny_to_pou_resolves(self):
        """Segment NY→POU should resolve to Amtrak Empire Service."""
        route = find_route_for_segment("AMTRAK", "NY", "POU")
        assert route is not None, "NY→POU should resolve to an Amtrak route"
        assert (
            route.id == "amtrak-empire-service"
        ), f"NY→POU should resolve to amtrak-empire-service, got {route.id}"

    def test_empire_service_segment_ny_to_crt_expands(self):
        """Segment NY→CRT should expand through YNY."""
        segments = get_canonical_segments("AMTRAK", "NY", "CRT")
        assert (
            len(segments) == 2
        ), f"NY→CRT should expand to 2 segments, got: {segments}"
        assert segments == [("NY", "YNY"), ("YNY", "CRT")]


class TestAmtrakStationNamesConsistency:
    """Test that all Amtrak topology stations have names in the station config."""

    def test_all_amtrak_stations_have_names(self):
        """Every station code in Amtrak routes should have a name."""
        from trackrat.config.stations.amtrak import AMTRAK_STATION_NAMES
        from trackrat.config.stations.common import STATION_NAMES

        all_names = {**STATION_NAMES, **AMTRAK_STATION_NAMES}
        amtrak_routes = get_routes_for_data_source("AMTRAK")
        missing = []
        for route in amtrak_routes:
            for station in route.stations:
                if station not in all_names:
                    missing.append((route.id, station))
        assert missing == [], f"Amtrak stations missing names: {missing}"
