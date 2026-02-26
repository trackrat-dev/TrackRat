"""
Unit tests for NJT schedule collector line code parsing.

The NJT schedule API returns full line names (e.g., "Northeast Corridor")
while the real-time discovery API returns short codes (e.g., "NEC").
The _parse_njt_line_code function handles both formats.
"""

import pytest

from trackrat.collectors.njt.schedule import _parse_njt_line_code


class TestParseNjtLineCode:
    """Tests for _parse_njt_line_code function."""

    # --- Full line names from the NJT schedule API ---

    def test_northeast_corridor(self):
        """NJT schedule API returns 'Northeast Corridor' for NEC trains."""
        assert _parse_njt_line_code("Northeast Corridor") == "NE"

    def test_northeast_corridor_line(self):
        """Alternate form with 'Line' suffix."""
        assert _parse_njt_line_code("Northeast Corridor Line") == "NE"

    def test_north_jersey_coast(self):
        """NJT schedule API returns 'North Jersey Coast Line' for NJCL trains."""
        assert _parse_njt_line_code("North Jersey Coast Line") == "NC"

    def test_north_jersey_coast_no_suffix(self):
        assert _parse_njt_line_code("North Jersey Coast") == "NC"

    def test_raritan_valley(self):
        assert _parse_njt_line_code("Raritan Valley Line") == "Ra"

    def test_morris_and_essex(self):
        assert _parse_njt_line_code("Morris and Essex Line") == "Mo"

    def test_morris_ampersand_essex(self):
        assert _parse_njt_line_code("Morris & Essex Line") == "Mo"

    def test_montclair_boonton(self):
        assert _parse_njt_line_code("Montclair-Boonton Line") == "Mo"

    def test_gladstone_branch(self):
        assert _parse_njt_line_code("Gladstone Branch") == "Gl"

    def test_main_line(self):
        assert _parse_njt_line_code("Main Line") == "Ma"

    def test_bergen_county_line(self):
        assert _parse_njt_line_code("Bergen County Line") == "Be"

    def test_pascack_valley(self):
        assert _parse_njt_line_code("Pascack Valley Line") == "Pa"

    def test_atlantic_city(self):
        assert _parse_njt_line_code("Atlantic City Rail Line") == "At"

    def test_princeton_shuttle(self):
        assert _parse_njt_line_code("Princeton Shuttle") == "Pr"

    # --- Short codes from the NJT real-time discovery API ---

    def test_short_code_nec(self):
        """Real-time API returns 'NEC' — truncated to 'NE'."""
        assert _parse_njt_line_code("NEC") == "NE"

    def test_short_code_ne(self):
        """Real-time API may return 'NE' directly."""
        assert _parse_njt_line_code("NE") == "NE"

    def test_short_code_nc(self):
        assert _parse_njt_line_code("NC") == "NC"

    def test_short_code_mo(self):
        assert _parse_njt_line_code("Mo") == "Mo"

    def test_short_code_ra(self):
        assert _parse_njt_line_code("Ra") == "Ra"

    # --- Edge cases ---

    def test_empty_string(self):
        assert _parse_njt_line_code("") == ""

    def test_single_char(self):
        """Single char should be returned as-is ([:2] of 1-char string)."""
        assert _parse_njt_line_code("X") == "X"

    def test_unknown_long_name_falls_back_to_truncation(self):
        """Unknown full names fall back to [:2] with a warning log."""
        result = _parse_njt_line_code("Some Unknown Line Name")
        assert result == "So"

    def test_case_insensitive_matching(self):
        """Full name matching should be case-insensitive."""
        assert _parse_njt_line_code("NORTHEAST CORRIDOR") == "NE"
        assert _parse_njt_line_code("northeast corridor") == "NE"

    # --- Verify the old bug is fixed ---

    def test_no_longer_produces_no_for_nec(self):
        """The old line[:2] truncation produced 'No' for 'Northeast Corridor'.
        This was the root cause of duplicate trains (e.g., 3719/3243)."""
        result = _parse_njt_line_code("Northeast Corridor")
        assert result != "No"
        assert result == "NE"

    def test_no_longer_produces_no_for_njcl(self):
        """The old line[:2] truncation produced 'No' for 'North Jersey Coast Line'.
        This collided with NEC's 'No', corrupting line code data."""
        result = _parse_njt_line_code("North Jersey Coast Line")
        assert result != "No"
        assert result == "NC"
