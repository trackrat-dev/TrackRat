"""
Unit tests for station mapping functionality.

Tests station code conversions between Amtrak and internal codes.
"""

import pytest

from trackrat.config.stations import (
    AMTRAK_TO_INTERNAL_STATION_MAP,
    map_amtrak_station_code,
    get_station_name,
)


class TestStationMapping:
    """Test suite for station code mapping."""

    def test_amtrak_to_internal_mapping_constants(self):
        """Test that the mapping dictionary contains expected values."""
        # Test key mappings we know should exist
        assert AMTRAK_TO_INTERNAL_STATION_MAP["NYP"] == "NY"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["NWK"] == "NP"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["TRE"] == "TR"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["PJC"] == "PJ"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["MET"] == "MP"

    def test_map_amtrak_station_code_valid_codes(self):
        """Test mapping valid Amtrak station codes."""
        assert map_amtrak_station_code("NYP") == "NY"
        assert map_amtrak_station_code("NWK") == "NP"
        assert map_amtrak_station_code("TRE") == "TR"
        assert map_amtrak_station_code("PJC") == "PJ"
        assert map_amtrak_station_code("MET") == "MP"

    def test_map_amtrak_station_code_invalid_codes(self):
        """Test mapping invalid/unmapped Amtrak station codes."""
        assert map_amtrak_station_code("INVALID") is None
        assert map_amtrak_station_code("XYZ") is None
        assert map_amtrak_station_code("") is None
        assert map_amtrak_station_code("123") is None

    def test_map_amtrak_station_code_case_sensitivity(self):
        """Test that mapping is case sensitive."""
        # Valid uppercase
        assert map_amtrak_station_code("NYP") == "NY"

        # Invalid lowercase should return None
        assert map_amtrak_station_code("nyp") is None
        assert map_amtrak_station_code("Nyp") is None

    def test_get_station_name_valid_codes(self):
        """Test getting station names for valid internal codes."""
        # Test that the function exists and works for known codes
        ny_name = get_station_name("NY")
        assert isinstance(ny_name, str)
        assert len(ny_name) > 0

        np_name = get_station_name("NP")
        assert isinstance(np_name, str)
        assert len(np_name) > 0

    def test_get_station_name_invalid_codes(self):
        """Test getting station names for invalid codes."""
        # Should handle invalid codes gracefully
        result = get_station_name("INVALID")
        # Function should either return the code itself or a default
        assert result is not None

    def test_mapping_completeness(self):
        """Test that all expected NJ stations are mapped."""
        expected_internal_codes = ["NY", "NP", "TR", "PJ", "MP"]
        mapped_internal_codes = set(AMTRAK_TO_INTERNAL_STATION_MAP.values())

        for code in expected_internal_codes:
            assert (
                code in mapped_internal_codes
            ), f"Internal code {code} missing from mapping"

    def test_multiple_amtrak_codes_to_same_internal(self):
        """Test that multiple Amtrak codes can map to the same internal code."""
        # Expected: NWK (Newark Penn) and EWR (Newark Airport) both map to NP
        assert AMTRAK_TO_INTERNAL_STATION_MAP["NWK"] == "NP"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["EWR"] == "NP"

        # This is correct behavior - both Newark stations map to Newark Penn internally

    def test_mapping_keys_format(self):
        """Test that all Amtrak station codes follow expected format."""
        for amtrak_code in AMTRAK_TO_INTERNAL_STATION_MAP.keys():
            # Should be uppercase letters, typically 3 characters
            assert amtrak_code.isupper(), f"Amtrak code {amtrak_code} not uppercase"
            assert (
                amtrak_code.isalpha()
            ), f"Amtrak code {amtrak_code} contains non-letters"
            assert (
                2 <= len(amtrak_code) <= 4
            ), f"Amtrak code {amtrak_code} unexpected length"

    def test_mapping_values_format(self):
        """Test that all internal codes follow expected format."""
        for internal_code in AMTRAK_TO_INTERNAL_STATION_MAP.values():
            # Should be uppercase letters, typically 2 characters
            assert (
                internal_code.isupper()
            ), f"Internal code {internal_code} not uppercase"
            assert (
                internal_code.isalpha()
            ), f"Internal code {internal_code} contains non-letters"
            assert (
                1 <= len(internal_code) <= 3
            ), f"Internal code {internal_code} unexpected length"

    @pytest.mark.parametrize(
        "amtrak_code,expected_internal",
        [
            ("NYP", "NY"),
            ("NWK", "NP"),
            ("TRE", "TR"),
            ("PJC", "PJ"),
            ("MET", "MP"),
        ],
    )
    def test_known_mappings_parametrized(self, amtrak_code, expected_internal):
        """Test known mappings using parametrization."""
        result = map_amtrak_station_code(amtrak_code)
        assert result == expected_internal

    def test_integration_with_amtrak_data(self):
        """Test that mapping works with realistic Amtrak station data."""
        # Simulate common Amtrak codes we'd see in real data
        common_amtrak_codes = ["NYP", "NWK", "TRE", "PHL", "BOS", "WAS"]

        for code in common_amtrak_codes:
            result = map_amtrak_station_code(code)
            # Should either map to something or return None
            if result is not None:
                assert isinstance(result, str)
                assert len(result) > 0
