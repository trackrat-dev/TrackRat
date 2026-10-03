"""
Unit tests for NJT schedule collector line code parsing.

The NJT schedule API returns full line names (e.g., "Northeast Corridor")
while the real-time discovery API returns short codes (e.g., "NEC").
The parse_njt_line_code function handles both formats.
"""

import pytest

from trackrat.collectors.njt.schedule import parse_njt_line_code


class TestParseNjtLineCode:
    """Tests for parse_njt_line_code function."""

    # --- Full line names from the NJT schedule API ---

    def test_northeast_corridor(self):
        """NJT schedule API returns 'Northeast Corridor' for NEC trains."""
        assert parse_njt_line_code("Northeast Corridor") == "NE"

    def test_northeast_corridor_line(self):
        """Alternate form with 'Line' suffix."""
        assert parse_njt_line_code("Northeast Corridor Line") == "NE"

    def test_north_jersey_coast(self):
        """NJT schedule API returns 'North Jersey Coast Line' for NJCL trains."""
        assert parse_njt_line_code("North Jersey Coast Line") == "NC"

    def test_north_jersey_coast_no_suffix(self):
        assert parse_njt_line_code("North Jersey Coast") == "NC"

    def test_raritan_valley(self):
        assert parse_njt_line_code("Raritan Valley Line") == "RV"

    def test_morris_and_essex(self):
        assert parse_njt_line_code("Morris and Essex Line") == "ME"

    def test_morris_ampersand_essex(self):
        assert parse_njt_line_code("Morris & Essex Line") == "ME"

    def test_montclair_boonton(self):
        assert parse_njt_line_code("Montclair-Boonton Line") == "MO"

    def test_gladstone_branch(self):
        assert parse_njt_line_code("Gladstone Branch") == "GL"

    def test_main_line(self):
        assert parse_njt_line_code("Main Line") == "MA"

    def test_bergen_county_line(self):
        assert parse_njt_line_code("Bergen County Line") == "BE"

    def test_pascack_valley(self):
        assert parse_njt_line_code("Pascack Valley Line") == "PV"

    def test_atlantic_city(self):
        assert parse_njt_line_code("Atlantic City Rail Line") == "AC"

    def test_atlantic_city_unsuffixed(self):
        assert parse_njt_line_code("Atlantic City Line") == "AC"

    def test_atl_city_abbreviation(self):
        """The literal string NJT's schedule API sends (issue #1796).

        Not a synthesised variant: this is the exact `line` value from the
        production `unknown_njt_line_name` log, which fired ~200x per sample.
        """
        assert parse_njt_line_code("Atl. City Line") == "AC"

    def test_port_jervis(self):
        """Port Jervis had no prefix entry at all (issue #1796)."""
        assert parse_njt_line_code("Port Jervis Line") == "PJ"

    def test_princeton_shuttle(self):
        assert parse_njt_line_code("Princeton Shuttle") == "PR"

    # --- Short codes from the NJT real-time discovery API ---

    def test_short_code_nec(self):
        """Real-time API returns 'NEC' — truncated to 'NE'."""
        assert parse_njt_line_code("NEC") == "NE"

    def test_short_code_ne(self):
        """Real-time API may return 'NE' directly."""
        assert parse_njt_line_code("NE") == "NE"

    def test_short_code_nc(self):
        assert parse_njt_line_code("NC") == "NC"

    def test_short_code_mo(self):
        assert parse_njt_line_code("Mo") == "Mo"

    def test_short_code_ra(self):
        assert parse_njt_line_code("Ra") == "Ra"

    # --- Edge cases ---

    def test_empty_string(self):
        assert parse_njt_line_code("") == ""

    def test_single_char(self):
        """Single char should be returned as-is ([:2] of 1-char string)."""
        assert parse_njt_line_code("X") == "X"

    def test_unknown_long_name_falls_back_to_truncation(self):
        """Unknown full names fall back to [:2] with a warning log."""
        result = parse_njt_line_code("Some Unknown Line Name")
        assert result == "So"

    def test_case_insensitive_matching(self):
        """Full name matching should be case-insensitive."""
        assert parse_njt_line_code("NORTHEAST CORRIDOR") == "NE"
        assert parse_njt_line_code("northeast corridor") == "NE"

    # --- Verify the old bug is fixed ---

    def test_no_longer_produces_no_for_nec(self):
        """The old line[:2] truncation produced 'No' for 'Northeast Corridor'.
        This was the root cause of duplicate trains (e.g., 3719/3243)."""
        result = parse_njt_line_code("Northeast Corridor")
        assert result != "No"
        assert result == "NE"

    def test_no_longer_produces_no_for_njcl(self):
        """The old line[:2] truncation produced 'No' for 'North Jersey Coast Line'.
        This collided with NEC's 'No', corrupting line code data."""
        result = parse_njt_line_code("North Jersey Coast Line")
        assert result != "No"
        assert result == "NC"

    def test_no_longer_produces_at_for_atl_city(self):
        """'Atl. City Line' truncated to 'At' (issue #1796).

        'At' is Atlantic City's own pre-2026-03 legacy alias, so topology
        lookups still resolved and nothing looked broken — while SCHEDULED
        rows carried 'At' and OBSERVED rows carried 'AC' for the same line,
        and a client filtering `lines=AC` silently dropped the scheduled ones.
        """
        result = parse_njt_line_code("Atl. City Line")
        assert result != "At"
        assert result == "AC"

    def test_no_longer_produces_po_for_port_jervis(self):
        """'Port Jervis Line' truncated to 'Po' (issue #1796).

        Strictly worse than the Atlantic City case that was reported: no NJT
        route carries 'Po', so unlike 'At' it resolved to no route at all.
        """
        result = parse_njt_line_code("Port Jervis Line")
        assert result != "Po"
        assert result == "PJ"
