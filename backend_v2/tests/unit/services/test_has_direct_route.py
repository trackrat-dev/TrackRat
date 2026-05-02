"""Tests for _has_direct_route helper in departure service."""

import pytest

from trackrat.services.departure import _has_direct_route


class TestHasDirectRoute:
    """Test the _has_direct_route function which checks if any data source
    has a route containing both the origin and destination stations."""

    def test_same_njt_route(self):
        """NY and TR are both on the NJT Northeast Corridor — should be True."""
        assert _has_direct_route("NY", "TR", ["NJT"]) is True

    def test_same_path_route(self):
        """PNK and PWC are both on the PATH Newark-WTC line — should be True."""
        assert _has_direct_route("PNK", "PWC", ["PATH"]) is True

    def test_cross_system_no_match(self):
        """PWC (PATH WTC) and TR (NJT Trenton) — no single PATH route contains both."""
        assert _has_direct_route("PWC", "TR", ["PATH"]) is False

    def test_cross_system_with_both_sources(self):
        """PHO (PATH Hoboken) and BTA (LIRR Babylon) — no route spans them."""
        assert _has_direct_route("PHO", "BTA", ["PATH", "LIRR"]) is False

    def test_all_sources_still_false_for_impossible_pair(self):
        """PATH-only station to an LIRR-only station has no direct route on any system."""
        all_sources = ["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]
        # P33 (33rd Street PATH) to BTA (Babylon LIRR) — no system connects them
        assert _has_direct_route("P33", "BTA", all_sources) is False

    def test_amtrak_route(self):
        """NY (Penn Station) and PH (30th St) are on Amtrak NEC — should be True."""
        assert _has_direct_route("NY", "PH", ["AMTRAK"]) is True

    def test_subway_same_line(self):
        """Two stations on the same subway line — should be True."""
        # A train: Far Rockaway to Howard Beach (both on A line)
        assert _has_direct_route("SH04", "SH12", ["SUBWAY"]) is True

    def test_subway_different_lines(self):
        """Stations on different subway lines with no shared route — should be False."""
        # SH04 is on A/C line, S726 is on the 7 line — no shared route
        assert _has_direct_route("SH04", "S726", ["SUBWAY"]) is False

    def test_no_to_station_not_called(self):
        """This function should only be called when to_station is provided.
        But if called with stations on the same line, it should work."""
        assert _has_direct_route("NY", "NP", ["NJT"]) is True

    def test_nonexistent_station(self):
        """Non-existent station codes should return False."""
        assert _has_direct_route("XXXXXX", "YYYYYY", ["NJT"]) is False

    def test_empty_data_sources(self):
        """Empty data sources list should return False (no sources to check)."""
        assert _has_direct_route("NY", "TR", []) is False

    def test_station_equivalences_amtrak(self):
        """Station equivalences should be considered.
        E.g., Amtrak NRO and MNR MNRC are the same physical station (New Rochelle).
        A search using one code should find routes containing the equivalent code."""
        # NRO is Amtrak's code for New Rochelle, which is on Amtrak NEC
        assert _has_direct_route("NY", "NRO", ["AMTRAK"]) is True

    def test_station_equivalences_cross_system(self):
        """PNK (PATH Newark) is equivalent to NP (NJT Newark Penn).
        Searching PNK to TR on NJT should find NJT NEC via the NP equivalence."""
        assert _has_direct_route("PNK", "TR", ["NJT"]) is True

    def test_penn_subway_equivalence_finds_njt_route(self):
        """34 St-Penn subway platforms should resolve to NY for NJT routes."""
        assert _has_direct_route("TR", "S128", ["NJT"]) is True
        assert _has_direct_route("TR", "SA28", ["NJT"]) is True

    def test_grand_central_subway_equivalence_finds_mnr_route(self):
        """Grand Central subway platforms should resolve to GCT for MNR routes."""
        assert _has_direct_route("MSTM", "S631", ["MNR"]) is True
        assert _has_direct_route("MSTM", "S723", ["MNR"]) is True

    def test_union_square_is_not_grand_central_equivalent(self):
        """S635 is 14 St-Union Sq, not Grand Central."""
        assert _has_direct_route("MSTM", "S635", ["MNR"]) is False

    def test_lirr_route(self):
        """JAM (Jamaica) and BTA (Babylon) are on the LIRR Babylon branch."""
        assert _has_direct_route("JAM", "BTA", ["LIRR"]) is True

    def test_mnr_route(self):
        """GCT (Grand Central) and MPOK (Mt Pleasant) on MNR Hudson line."""
        # Using a known MNR route pair
        assert _has_direct_route("GCT", "MPOK", ["MNR"]) is True

    def test_found_on_second_source(self):
        """Route exists on AMTRAK but not NJT — should be True when both checked."""
        # PH (30th Street Philadelphia) is on Amtrak NEC, not on any NJT route from NY
        assert _has_direct_route("NY", "PH", ["NJT"]) is False
        assert _has_direct_route("NY", "PH", ["NJT", "AMTRAK"]) is True
