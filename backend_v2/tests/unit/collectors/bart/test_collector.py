"""
Unit tests for BARTCollector.

Tests train ID generation, journey discovery, and the unified collection loop.
"""

import pytest

from trackrat.collectors.bart.collector import _generate_train_id
from trackrat.config.stations.bart import (
    BART_GTFS_STOP_TO_INTERNAL_MAP,
    BART_ROUTES,
    BART_STATION_COORDINATES,
    BART_STATION_NAMES,
    INTERNAL_TO_BART_GTFS_STOP_MAP,
    get_bart_route_info,
    map_bart_gtfs_stop,
)


class TestGenerateTrainId:
    """Tests for _generate_train_id."""

    def test_simple_numeric_trip_id(self):
        """BART trip_ids are plain integers."""
        assert _generate_train_id("1842090") == "B1842090"

    def test_another_trip_id(self):
        """Test another trip_id."""
        assert _generate_train_id("999") == "B999"

    def test_empty_trip_id(self):
        """Edge case: empty trip_id."""
        assert _generate_train_id("") == "B"


class TestBartStationConfig:
    """Tests for BART station configuration completeness and consistency."""

    def test_all_stations_have_names(self):
        """Every station code in the names dict should be non-empty."""
        for code, name in BART_STATION_NAMES.items():
            assert code.startswith("BART_"), f"Station {code} missing BART_ prefix"
            assert len(name) > 0, f"Station {code} has empty name"

    def test_station_count(self):
        """BART should have ~50 stations."""
        count = len(BART_STATION_NAMES)
        assert 48 <= count <= 55, f"Expected ~50 BART stations, got {count}"

    def test_all_stations_have_coordinates(self):
        """Every station in BART_STATION_NAMES should have coordinates."""
        for code in BART_STATION_NAMES:
            assert code in BART_STATION_COORDINATES, (
                f"Station {code} missing from BART_STATION_COORDINATES"
            )
            lat, lon = BART_STATION_COORDINATES[code]
            # BART is in the San Francisco Bay Area
            assert 37.0 <= lat <= 39.0, f"Station {code} lat {lat} out of range"
            assert -123.0 <= lon <= -121.0, f"Station {code} lon {lon} out of range"

    def test_gtfs_stop_mapping_covers_all_stations(self):
        """Every BART station should be reachable via at least one GTFS stop_id."""
        mapped_internal_codes = set(BART_GTFS_STOP_TO_INTERNAL_MAP.values())
        for code in BART_STATION_NAMES:
            assert code in mapped_internal_codes, (
                f"Station {code} has no GTFS stop_id mapping"
            )

    def test_reverse_mapping_has_parent_codes_only(self):
        """Reverse mapping should only contain 4-letter parent station codes."""
        for internal_code, gtfs_id in INTERNAL_TO_BART_GTFS_STOP_MAP.items():
            assert internal_code.startswith("BART_"), (
                f"Reverse mapping key {internal_code} missing BART_ prefix"
            )
            assert "-" not in gtfs_id, (
                f"Reverse mapping value {gtfs_id} should be a parent code, not platform"
            )
            assert len(gtfs_id) <= 4, (
                f"Reverse mapping value {gtfs_id} too long for parent station code"
            )

    def test_no_duplicate_internal_codes_in_names(self):
        """Station codes should be unique."""
        codes = list(BART_STATION_NAMES.keys())
        assert len(codes) == len(set(codes)), "Duplicate station codes found"

    def test_platform_stop_ids_map_to_parent(self):
        """Platform-level stop_ids (e.g., A40-2) should map to same station as parent."""
        # Embarcadero: M16-1, M16-2, and parent EMBR should all map to BART_EMBR
        assert map_bart_gtfs_stop("M16-1") == "BART_EMBR"
        assert map_bart_gtfs_stop("M16-2") == "BART_EMBR"
        assert map_bart_gtfs_stop("EMBR") == "BART_EMBR"

        # MacArthur has 4 platforms
        assert map_bart_gtfs_stop("K30-1") == "BART_MCAR"
        assert map_bart_gtfs_stop("K30-2") == "BART_MCAR"
        assert map_bart_gtfs_stop("K30-3") == "BART_MCAR"
        assert map_bart_gtfs_stop("K30-4") == "BART_MCAR"
        assert map_bart_gtfs_stop("MCAR") == "BART_MCAR"


class TestBartRoutes:
    """Tests for BART route definitions."""

    def test_all_routes_defined(self):
        """BART should have routes for all 6 lines (12 directional route_ids)."""
        assert len(BART_ROUTES) == 12

    def test_directional_routes_share_line_code(self):
        """Paired directional routes should map to the same line."""
        pairs = [("1", "2"), ("3", "4"), ("5", "6"), ("7", "8"), ("11", "12"), ("19", "20")]
        for fwd, rev in pairs:
            assert BART_ROUTES[fwd][0] == BART_ROUTES[rev][0], (
                f"Routes {fwd} and {rev} should share line code"
            )

    def test_route_colors_are_hex(self):
        """All route colors should be valid hex color strings."""
        for route_id, (_, _, color) in BART_ROUTES.items():
            assert color.startswith("#"), f"Route {route_id} color {color} not hex"
            assert len(color) == 7, f"Route {route_id} color {color} not 7 chars"

    def test_get_bart_route_info(self):
        """Test route info helper function."""
        info = get_bart_route_info("1")
        assert info is not None
        line_code, name, color = info
        assert line_code == "BART-YEL"
        assert "Antioch" in name
        assert color == "#FFFF33"

        assert get_bart_route_info("999") is None

    def test_map_bart_gtfs_stop(self):
        """Test stop mapping helper function."""
        assert map_bart_gtfs_stop("EMBR") == "BART_EMBR"
        assert map_bart_gtfs_stop("M16-1") == "BART_EMBR"
        assert map_bart_gtfs_stop("INVALID") is None
