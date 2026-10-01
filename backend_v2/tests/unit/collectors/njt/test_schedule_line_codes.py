"""
Unit tests for NJT schedule collector line code parsing.

The NJT schedule API returns full line names (e.g., "Northeast Corridor")
while the real-time discovery API returns short codes (e.g., "NEC").
The parse_njt_line_code function handles both formats.
"""

import pytest

from trackrat.utils.train import parse_njt_line_code


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

    # --- Abbreviated names from the NJT real-time discovery API (issue #1839) ---

    def test_realtime_no_jersey_coast(self):
        """Real-time discovery sends 'No Jersey Coast' for NJCL trains. Before
        #1839 this fell through to truncation ('No'), so the OBSERVED row never
        shared a line code with the schedule API's 'NC' row for the same train
        and both showed on the board (one as 'Train TBD')."""
        result = parse_njt_line_code("No Jersey Coast")
        assert result == "NC", f"'No Jersey Coast' -> {result!r}, expected 'NC'"
        assert result == parse_njt_line_code("North Jersey Coast Line")

    def test_realtime_atl_city_line(self):
        """Real-time discovery sends 'Atl. City Line' for ACL trains; must match
        the schedule API's 'Atlantic City Rail Line'."""
        result = parse_njt_line_code("Atl. City Line")
        assert result == "AC", f"'Atl. City Line' -> {result!r}, expected 'AC'"
        assert result == parse_njt_line_code("Atlantic City Rail Line")

    # --- NJT's own LINECODE values (getTrainStopList, issue #1839) ---

    @pytest.mark.parametrize(
        ("linecode", "expected"),
        [("ML", "MA"), ("BC", "BE"), ("GS", "GL"), ("MC", "MO")],
    )
    def test_njt_linecode_aliases(self, linecode: str, expected: str):
        """Journey collection used to store these raw, so an OBSERVED Main
        Line row ('ML') never shared a line code with its schedule twin ('MA')."""
        result = parse_njt_line_code(linecode)
        assert result == expected, f"{linecode!r} -> {result!r}, expected {expected!r}"

    @pytest.mark.parametrize("linecode", ["NE", "NC", "RV", "PV", "ME", "AC"])
    def test_njt_linecodes_already_canonical(self, linecode: str):
        """Codes NJT and TrackRat agree on pass through unchanged."""
        assert parse_njt_line_code(linecode) == linecode
