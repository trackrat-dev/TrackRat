"""
Unit tests for scripts/generate_subway_data.py station name generation.

Tests the route suffix formatting and name collision resolution logic
to prevent regressions where station codes (e.g., 'SA63') end up as
display labels instead of route letters (e.g., 'A').
"""

import sys
import os

import pytest

# Add scripts directory to path so we can import the generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))

from generate_subway_data import (
    _format_route_suffix,
    resolve_backend_name_collisions,
    resolve_name_collisions,
    strip_route_suffix,
)


class TestFormatRouteSuffix:
    """Tests for _format_route_suffix helper."""

    def test_single_letter_route(self):
        assert _format_route_suffix({"A"}) == "A"

    def test_single_number_route(self):
        assert _format_route_suffix({"1"}) == "1"

    def test_multiple_number_routes_sorted(self):
        assert _format_route_suffix({"3", "1", "2"}) == "1/2/3"

    def test_multiple_letter_routes_sorted(self):
        assert _format_route_suffix({"C", "A", "E"}) == "A/C/E"

    def test_mixed_numbers_and_letters(self):
        """Numbers should come before letters."""
        assert _format_route_suffix({"A", "1", "C", "2"}) == "1/2/A/C"

    def test_express_variants_filtered_out(self):
        """Express variants (6X, 7X, FX) should be excluded."""
        assert _format_route_suffix({"6", "6X"}) == "6"
        assert _format_route_suffix({"7", "7X"}) == "7"
        assert _format_route_suffix({"F", "FX"}) == "F"

    def test_express_only_returns_none(self):
        """If only express variants remain, return None."""
        assert _format_route_suffix({"6X"}) is None

    def test_empty_set_returns_none(self):
        assert _format_route_suffix(set()) is None

    def test_shuttle_routes_included(self):
        """Shuttle routes (GS, FS, H) should NOT be filtered out."""
        result = _format_route_suffix({"GS", "4", "5", "6"})
        assert "GS" in result
        assert result == "4/5/6/GS"

    def test_real_world_example_irt_local(self):
        """96 St on the 1/2/3 line."""
        assert _format_route_suffix({"1", "2", "3"}) == "1/2/3"

    def test_real_world_example_8th_ave(self):
        """59 St-Columbus Circle on A/B/C/D."""
        assert _format_route_suffix({"A", "B", "C", "D"}) == "A/B/C/D"


class TestResolveBackendNameCollisions:
    """Tests for resolve_backend_name_collisions on flat station lists."""

    def test_no_collision_leaves_names_unchanged(self):
        """Stations with unique names should not be modified."""
        stations = [
            {"code": "S101", "name": "Van Cortlandt Park-242 St"},
            {"code": "S102", "name": "238 St"},
        ]
        station_routes = {
            "S101": {"1"},
            "S102": {"1"},
        }
        resolve_backend_name_collisions(stations, station_routes)
        assert stations[0]["name"] == "Van Cortlandt Park-242 St"
        assert stations[1]["name"] == "238 St"

    def test_collision_resolved_with_route_labels(self):
        """Stations sharing a name get route suffixes."""
        stations = [
            {"code": "SA63", "name": "104 St"},
            {"code": "SJ14", "name": "104 St"},
        ]
        station_routes = {
            "SA63": {"A"},
            "SJ14": {"J", "Z"},
        }
        resolve_backend_name_collisions(stations, station_routes)
        assert stations[0]["name"] == "104 St (A)"
        assert stations[1]["name"] == "104 St (J/Z)"

    def test_collision_with_three_stations(self):
        """Three-way collision (like 111 St: 7, A, J lines)."""
        stations = [
            {"code": "S705", "name": "111 St"},
            {"code": "SA64", "name": "111 St"},
            {"code": "SJ13", "name": "111 St"},
        ]
        station_routes = {
            "S705": {"7"},
            "SA64": {"A"},
            "SJ13": {"J"},
        }
        resolve_backend_name_collisions(stations, station_routes)
        assert stations[0]["name"] == "111 St (7)"
        assert stations[1]["name"] == "111 St (A)"
        assert stations[2]["name"] == "111 St (J)"

    def test_collision_falls_back_to_station_code_when_no_routes(self):
        """If no route info exists, use station code as fallback."""
        stations = [
            {"code": "SX01", "name": "Mystery St"},
            {"code": "SX02", "name": "Mystery St"},
        ]
        station_routes = {}
        resolve_backend_name_collisions(stations, station_routes)
        assert stations[0]["name"] == "Mystery St (SX01)"
        assert stations[1]["name"] == "Mystery St (SX02)"

    def test_express_variants_excluded_from_labels(self):
        """Express variants should not appear in collision labels."""
        stations = [
            {"code": "SA01", "name": "Test St"},
            {"code": "SB01", "name": "Test St"},
        ]
        station_routes = {
            "SA01": {"6", "6X"},
            "SB01": {"A", "FX"},
        }
        resolve_backend_name_collisions(stations, station_routes)
        assert stations[0]["name"] == "Test St (6)"
        assert stations[1]["name"] == "Test St (A)"

    def test_already_unique_names_not_modified(self):
        """Names that are already different should be left alone,
        even if they share a base name like '96 St'."""
        stations = [
            {"code": "S120", "name": "96 St (1/2/3)"},
            {"code": "SA19", "name": "96 St (A/B/C)"},
        ]
        station_routes = {
            "S120": {"1", "2", "3"},
            "SA19": {"A", "B", "C"},
        }
        resolve_backend_name_collisions(stations, station_routes)
        # Names already unique — no change
        assert stations[0]["name"] == "96 St (1/2/3)"
        assert stations[1]["name"] == "96 St (A/B/C)"


class TestResolveNameCollisions:
    """Tests for resolve_name_collisions on consolidated station lists."""

    def test_consolidated_collision_uses_all_codes_for_routes(self):
        """Consolidated entries collect routes from all codes in the complex."""
        consolidated = [
            {"name": "Test St", "canonical_code": "SA01", "all_codes": {"SA01", "SB01"}},
            {"name": "Test St", "canonical_code": "SC01", "all_codes": {"SC01"}},
        ]
        station_routes = {
            "SA01": {"A", "C"},
            "SB01": {"E"},
            "SC01": {"1", "2"},
        }
        resolve_name_collisions(consolidated, station_routes)
        assert consolidated[0]["name"] == "Test St (A/C/E)"
        assert consolidated[1]["name"] == "Test St (1/2)"

    def test_single_entry_not_modified(self):
        """Names with no collision should not be changed."""
        consolidated = [
            {"name": "Unique Station", "canonical_code": "S001", "all_codes": {"S001"}},
        ]
        station_routes = {"S001": {"1"}}
        resolve_name_collisions(consolidated, station_routes)
        assert consolidated[0]["name"] == "Unique Station"


class TestStripRouteSuffix:
    """Tests for strip_route_suffix helper."""

    def test_strips_parenthetical_suffix(self):
        assert strip_route_suffix("96 St (1/2/3)") == "96 St"

    def test_strips_single_route_suffix(self):
        assert strip_route_suffix("103 St (1)") == "103 St"

    def test_strips_dash_suffix(self):
        assert strip_route_suffix("Cathedral Pkwy (110 St) - 1") == "Cathedral Pkwy (110 St)"

    def test_strips_station_code_suffix(self):
        assert strip_route_suffix("104 St (SA63)") == "104 St"

    def test_no_suffix_unchanged(self):
        assert strip_route_suffix("Times Sq-42 St") == "Times Sq-42 St"

    def test_empty_string(self):
        assert strip_route_suffix("") == ""
