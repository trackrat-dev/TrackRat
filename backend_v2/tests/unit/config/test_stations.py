"""
Unit tests for station mapping functionality.

Tests station code conversions between Amtrak and internal codes,
NJT GTFS stop mappings, and station coordinate validity.
"""

import pytest

from trackrat.config.stations import (
    AMTRAK_TO_INTERNAL_STATION_MAP,
    INTERNAL_TO_MNR_GTFS_STOP_MAP,
    INTERNAL_TO_SUBWAY_GTFS_STOP_MAP,
    MNR_GTFS_STOP_TO_INTERNAL_MAP,
    MNR_STATION_NAMES,
    NJT_GTFS_STOP_TO_INTERNAL_MAP,
    STATION_COORDINATES,
    STATION_EQUIVALENCE_GROUPS,
    STATION_EQUIVALENTS,
    STATION_NAMES,
    SUBWAY_GTFS_STOP_TO_INTERNAL_MAP,
    SUBWAY_STATION_COMPLEXES,
    SUBWAY_STATION_NAMES,
    canonical_station_code,
    expand_station_codes,
    get_station_name,
    map_amtrak_station_code,
    map_gtfs_stop_to_station_code,
    map_subway_gtfs_stop,
    get_path_stops_by_origin_destination,
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
        assert AMTRAK_TO_INTERNAL_STATION_MAP["PHL"] == "PH"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["WIL"] == "WI"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["BAL"] == "BL"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["BWI"] == "BA"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["BOS"] == "BOS"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["BBY"] == "BBY"
        assert AMTRAK_TO_INTERNAL_STATION_MAP["WAS"] == "WS"

    def test_map_amtrak_station_code_valid_codes(self):
        """Test mapping valid Amtrak station codes."""
        assert map_amtrak_station_code("NYP") == "NY"
        assert map_amtrak_station_code("NWK") == "NP"
        assert map_amtrak_station_code("TRE") == "TR"
        assert map_amtrak_station_code("PJC") == "PJ"
        assert map_amtrak_station_code("MET") == "MP"
        assert map_amtrak_station_code("PHL") == "PH"
        assert map_amtrak_station_code("WIL") == "WI"
        assert map_amtrak_station_code("BAL") == "BL"
        assert map_amtrak_station_code("BWI") == "BA"
        assert map_amtrak_station_code("BOS") == "BOS"
        assert map_amtrak_station_code("BBY") == "BBY"
        assert map_amtrak_station_code("WAS") == "WS"

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
        """Test that all expected stations are mapped."""
        expected_internal_codes = [
            "NY",
            "NP",
            "TR",
            "PJ",
            "MP",
            "PH",
            "WI",
            "BL",
            "BA",
            "BOS",
            "BBY",
            "WS",
        ]
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
            ("PHL", "PH"),
            ("WIL", "WI"),
            ("BAL", "BL"),
            ("BWI", "BA"),
            ("BOS", "BOS"),
            ("BBY", "BBY"),
            ("WAS", "WS"),
        ],
    )
    def test_known_mappings_parametrized(self, amtrak_code, expected_internal):
        """Test known mappings using parametrization."""
        result = map_amtrak_station_code(amtrak_code)
        assert result == expected_internal

    def test_integration_with_amtrak_data(self):
        """Test that mapping works with realistic Amtrak station data."""
        # Simulate common Amtrak codes we'd see in real data
        common_amtrak_codes = ["NYP", "NWK", "TRE", "PHL", "BOS", "WAS", "BAL", "BWI"]

        for code in common_amtrak_codes:
            result = map_amtrak_station_code(code)
            # Should either map to something or return None
            if result is not None:
                assert isinstance(result, str)
                assert len(result) > 0


class TestPathStopsByOriginDestination:
    """Tests for the PATH route stop lookup function."""

    def test_hoboken_to_33rd(self):
        """Test Hoboken to 33rd Street route (HOB-33 line)."""
        stops = get_path_stops_by_origin_destination("PHO", "P33")
        assert stops is not None
        assert stops[0] == "PHO"  # Origin
        assert stops[-1] == "P33"  # Destination
        # HOB-33 line: PHO -> PCH -> P9S -> P14 -> P23 -> P33
        assert len(stops) == 6
        assert "PCH" in stops
        assert "P9S" in stops

    def test_33rd_to_hoboken(self):
        """Test 33rd Street to Hoboken (reverse direction)."""
        stops = get_path_stops_by_origin_destination("P33", "PHO")
        assert stops is not None
        assert stops[0] == "P33"  # Origin
        assert stops[-1] == "PHO"  # Destination
        assert len(stops) == 6

    def test_newark_to_wtc(self):
        """Test Newark to World Trade Center route (NWK-WTC line)."""
        stops = get_path_stops_by_origin_destination("PNK", "PWC")
        assert stops is not None
        assert stops[0] == "PNK"  # Origin
        assert stops[-1] == "PWC"  # Destination
        # NWK-WTC line: PNK -> PHR -> PJS -> PGR -> PEX -> PWC
        assert len(stops) == 6
        assert "PJS" in stops
        assert "PEX" in stops

    def test_wtc_to_newark(self):
        """Test World Trade Center to Newark (reverse direction)."""
        stops = get_path_stops_by_origin_destination("PWC", "PNK")
        assert stops is not None
        assert stops[0] == "PWC"  # Origin
        assert stops[-1] == "PNK"  # Destination

    def test_hoboken_to_wtc(self):
        """Test Hoboken to World Trade Center route (HOB-WTC line)."""
        stops = get_path_stops_by_origin_destination("PHO", "PWC")
        assert stops is not None
        assert stops[0] == "PHO"
        assert stops[-1] == "PWC"
        # HOB-WTC line: PHO -> PNP -> PEX -> PWC
        assert len(stops) == 4

    def test_partial_route(self):
        """Test getting stops for a partial route (mid-route origin)."""
        # From Journal Square to World Trade Center (part of NWK-WTC line)
        stops = get_path_stops_by_origin_destination("PJS", "PWC")
        assert stops is not None
        assert stops[0] == "PJS"
        assert stops[-1] == "PWC"
        # Should be: PJS -> PGR -> PEX -> PWC
        assert len(stops) == 4

    def test_no_matching_route(self):
        """Test that None is returned when no route connects the stations."""
        # Harrison to 33rd Street - no direct route in PATH network
        # (Newark and 33rd are on different branches)
        stops = get_path_stops_by_origin_destination("PHR", "P33")
        # Should be None since Harrison is not on any route to 33rd
        assert stops is None

    def test_same_station(self):
        """Test that same station for origin and destination returns single stop."""
        # Same station - should find a route containing it
        stops = get_path_stops_by_origin_destination("PJS", "PJS")
        # Should return single station since origin == destination
        assert stops is not None
        assert stops == ["PJS"]

    def test_invalid_station_code(self):
        """Test that invalid station codes return None."""
        stops = get_path_stops_by_origin_destination("INVALID", "P33")
        assert stops is None

        stops = get_path_stops_by_origin_destination("PHO", "INVALID")
        assert stops is None


class TestNJTGTFSStopMapping:
    """Tests for NJT GTFS stop_id to internal station code mapping.

    NJT GTFS uses numeric stop_ids and uppercase abbreviated names like
    "PRINCETON JCT." which don't always match our station names exactly.
    The explicit mapping handles these cases.
    """

    def test_princeton_junction_mapping(self):
        """Test Princeton Junction maps correctly (was broken before fix)."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("125", "PRINCETON JCT.", "NJT")
        assert result == "PJ", f"Expected PJ, got {result}"

    def test_trenton_transit_center_mapping(self):
        """Test Trenton Transit Center maps correctly."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("148", "TRENTON TRANSIT CENTER", "NJT")
        assert result == "TR", f"Expected TR, got {result}"

    def test_edison_station_mapping(self):
        """Test Edison Station maps correctly."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("38", "EDISON STATION", "NJT")
        assert result == "ED", f"Expected ED, got {result}"

    def test_philadelphia_mapping(self):
        """Test 30th St Philadelphia maps correctly."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("1", "30TH ST. PHL.", "NJT")
        assert result == "PH", f"Expected PH, got {result}"

    def test_ny_penn_still_works(self):
        """Test NY Penn Station still maps via name matching."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("105", "NEW YORK PENN STATION", "NJT")
        assert result == "NY", f"Expected NY, got {result}"

    def test_hamilton_still_works(self):
        """Test Hamilton still maps via name matching."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("32905", "HAMILTON", "NJT")
        assert result == "HL", f"Expected HL, got {result}"

    def test_explicit_mapping_takes_precedence(self):
        """Test that explicit stop_id mapping is checked before name matching."""
        # Verify explicit mapping exists
        assert "125" in NJT_GTFS_STOP_TO_INTERNAL_MAP
        assert NJT_GTFS_STOP_TO_INTERNAL_MAP["125"] == "PJ"

        # Verify it's used even with a different name
        result = map_gtfs_stop_to_station_code("125", "SOME OTHER NAME", "NJT")
        assert result == "PJ", "Explicit mapping should take precedence over name"

    @pytest.mark.parametrize(
        "gtfs_stop_id,gtfs_name,expected_code",
        [
            # Stations that previously collided with Amtrak/PATCO codes
            ("35", "DOVER", "DO"),  # Was mapping to Amtrak DOV (Dover, NH)
            ("145", "SUMMIT", "ST"),  # Was mapping to Amtrak SMT (Summit, IL)
            ("77", "MADISON", "MA"),  # Was mapping to Amtrak MDS (Madison, CT)
            ("124", "PRINCETON", "PR"),  # Was mapping to Amtrak PCT (Princeton, IL)
            ("158", "WOODBRIDGE", "WB"),  # Was mapping to Amtrak WDB (Woodbridge, VA)
            ("25", "BROADWAY", "BF"),  # Was mapping to PATCO BWY (Broadway, Camden)
            ("71", "LINDENWOLD", "LW"),  # Was mapping to PATCO LND
        ],
    )
    def test_njt_name_collision_stations(self, gtfs_stop_id, gtfs_name, expected_code):
        """Test NJT stations whose names collide with Amtrak/PATCO codes.

        These stations previously mapped to wrong codes because the fuzzy
        name matcher returned Amtrak/PATCO station codes instead of NJT codes.
        The explicit stop_id mapping now prevents this.
        """
        result = map_gtfs_stop_to_station_code(gtfs_stop_id, gtfs_name, "NJT")
        assert result == expected_code, (
            f"GTFS stop '{gtfs_name}' (id={gtfs_stop_id}) mapped to "
            f"'{result}' ({STATION_NAMES.get(result, '???')}), "
            f"expected '{expected_code}' ({STATION_NAMES.get(expected_code, '???')})"
        )

    @pytest.mark.parametrize(
        "gtfs_stop_id,gtfs_name,expected_code",
        [
            ("38174", "FRANK R LAUTENBERG SECAUCUS LOWER LEVEL", "TS"),
            ("38187", "FRANK R LAUTENBERG SECAUCUS UPPER LEVEL", "SE"),
            ("32906", "JERSEY AVE.", "JA"),
            ("38081", "MSU", "UV"),
            ("43298", "PENNSAUKEN TRANSIT CENTER", "PN"),
            ("39635", "WAYNE/ROUTE 23 TRANSIT CENTER [RR]", "23"),
        ],
    )
    def test_previously_unmapped_stations(self, gtfs_stop_id, gtfs_name, expected_code):
        """Test NJT stations that were previously unmapped (returned None).

        These stations had names too different from our internal names
        for the fuzzy matcher to find them. They now have explicit mappings.
        """
        result = map_gtfs_stop_to_station_code(gtfs_stop_id, gtfs_name, "NJT")
        assert result == expected_code, (
            f"GTFS stop '{gtfs_name}' (id={gtfs_stop_id}) mapped to "
            f"'{result}', expected '{expected_code}' ({STATION_NAMES.get(expected_code, '???')})"
        )


class TestNJTStationCoordinates:
    """Tests for NJT station coordinate validity.

    Verifies that all NJT station coordinates fall within the expected
    geographic bounds (NJ/NY/PA/CT region) and that known-problematic
    stations have correct coordinates from GTFS.
    """

    # NJ-area bounds for NJT-only stations (2-char codes)
    NJ_MIN_LAT = 39.3  # South NJ (Atlantic City area)
    NJ_MAX_LAT = 41.5  # North NJ/lower NY (Port Jervis line)
    NJ_MIN_LON = -75.2  # West NJ (Philadelphia area)
    NJ_MAX_LON = -73.9  # East NJ (coastal)

    def test_all_coordinates_are_valid(self):
        """All station coordinates should have reasonable lat/lon values."""
        for code, coords in STATION_COORDINATES.items():
            lat, lon = coords["lat"], coords["lon"]
            assert -90 <= lat <= 90, (
                f"[{code}] {STATION_NAMES.get(code, '???')}: "
                f"lat {lat} is not a valid latitude"
            )
            assert -180 <= lon <= 180, (
                f"[{code}] {STATION_NAMES.get(code, '???')}: "
                f"lon {lon} is not a valid longitude"
            )

    def test_njt_stations_within_nj_bounds(self):
        """NJT stations (2-char codes) should fall within NJ/NY service area.

        Excludes known Amtrak-only stations that share the NJ Transit
        station list but are outside the NJ area (e.g., WI, BA, BL, WS).
        """
        # Codes for stations outside NJ area (Amtrak intercity + LIRR)
        non_nj_codes = {
            "BA",
            "BL",
            "WS",
            "WI",
            "NF",  # DC corridor
            "PH",  # Philadelphia
            "CI",  # LIRR - Central Islip (Long Island)
        }
        for code, coords in STATION_COORDINATES.items():
            if len(code) > 2:  # Skip 3-char Amtrak/PATH/PATCO codes
                continue
            if code in non_nj_codes:
                continue
            lat, lon = coords["lat"], coords["lon"]
            assert self.NJ_MIN_LAT <= lat <= self.NJ_MAX_LAT, (
                f"[{code}] {STATION_NAMES.get(code, '???')}: "
                f"lat {lat} out of NJ bounds [{self.NJ_MIN_LAT}, {self.NJ_MAX_LAT}]"
            )
            assert self.NJ_MIN_LON <= lon <= self.NJ_MAX_LON, (
                f"[{code}] {STATION_NAMES.get(code, '???')}: "
                f"lon {lon} out of NJ bounds [{self.NJ_MIN_LON}, {self.NJ_MAX_LON}]"
            )

    def test_no_duplicate_coordinates(self):
        """No two distinct stations should share identical coordinates.

        Exception: Secaucus variants (SE/SC/TS) share the same location.
        """
        secaucus_codes = {"SE", "SC", "TS"}
        coord_to_codes: dict[tuple[float, float], list[str]] = {}
        for code, coords in STATION_COORDINATES.items():
            key = (coords["lat"], coords["lon"])
            if key not in coord_to_codes:
                coord_to_codes[key] = []
            coord_to_codes[key].append(code)

        for coord, codes in coord_to_codes.items():
            if len(codes) > 1:
                # Allow Secaucus variants to share coordinates
                non_secaucus = [c for c in codes if c not in secaucus_codes]
                # Allow subway stations to share coordinates (multiple complexes
                # at the same physical location, e.g., Queensboro Plaza)
                non_secaucus_non_subway = [
                    c for c in non_secaucus if not c.startswith("S") or len(c) <= 2
                ]
                assert len(non_secaucus_non_subway) <= 1, (
                    f"Stations {codes} share coordinates {coord}: "
                    f"{[STATION_NAMES.get(c, '???') for c in codes]}"
                )

    @pytest.mark.parametrize(
        "code,expected_lat,expected_lon,description",
        [
            # Previously had Mountain Station coords at Mount Tabor location (~35km off)
            ("MT", 40.755365, -74.253024, "Mountain Station was 35km off"),
            # Previously had Hackettstown in New York state (~17km off)
            ("HQ", 40.851444, -74.835352, "Hackettstown was 17km north in NY"),
            # Previously had Metuchen at same coords as Metropark
            ("MU", 40.540736, -74.360671, "Metuchen had Metropark's coords"),
            ("MP", 40.56864, -74.329394, "Metropark (distinct from Metuchen)"),
            # Previously had Jersey Avenue at wrong location (~46km off)
            ("JA", 40.476912, -74.467363, "Jersey Avenue was 46km off"),
            # Previously had Murray Hill ~12km off
            ("MH", 40.695068, -74.403134, "Murray Hill was 12km off"),
        ],
    )
    def test_previously_wrong_coordinates(
        self, code, expected_lat, expected_lon, description
    ):
        """Verify previously-wrong coordinates are now correct (from GTFS)."""
        assert (
            code in STATION_COORDINATES
        ), f"[{code}] {STATION_NAMES.get(code, '???')} missing from STATION_COORDINATES"
        actual_lat = STATION_COORDINATES[code]["lat"]
        actual_lon = STATION_COORDINATES[code]["lon"]
        assert actual_lat == pytest.approx(
            expected_lat, abs=0.001
        ), f"[{code}] lat mismatch: {actual_lat} != {expected_lat} ({description})"
        assert actual_lon == pytest.approx(
            expected_lon, abs=0.001
        ), f"[{code}] lon mismatch: {actual_lon} != {expected_lon} ({description})"

    def test_njt_explicit_mapping_completeness(self):
        """Every NJT GTFS explicit mapping should point to a valid station code."""
        for stop_id, code in NJT_GTFS_STOP_TO_INTERNAL_MAP.items():
            assert code in STATION_NAMES, (
                f"GTFS stop_id {stop_id} maps to '{code}' "
                f"which is not in STATION_NAMES"
            )


class TestStationEquivalences:
    """Tests for station code equivalence mapping.

    Shared stations between Amtrak and Metro-North use different internal codes.
    The equivalence mapping ensures queries match trains from both systems.
    """

    # All expected equivalence pairs (Amtrak code, MNR code, station name)
    EXPECTED_PAIRS = [
        ("NRO", "MNRC", "New Rochelle"),
        ("YNY", "MYON", "Yonkers"),
        ("CRT", "MCRH", "Croton-Harmon"),
        ("POU", "MPOK", "Poughkeepsie"),
        ("STM", "MSTM", "Stamford"),
        ("BRP", "MBGP", "Bridgeport"),
        ("NHV", "MNHV", "New Haven"),
    ]

    def test_expand_station_codes_with_equivalent(self):
        """expand_station_codes returns all codes for shared stations."""
        for amtrak_code, mnr_code, name in self.EXPECTED_PAIRS:
            # Amtrak code expands to include MNR code
            result = expand_station_codes(amtrak_code)
            assert (
                amtrak_code in result
            ), f"{name}: Amtrak code {amtrak_code} missing from its own expansion"
            assert (
                mnr_code in result
            ), f"{name}: MNR code {mnr_code} missing from expansion of {amtrak_code}"

            # MNR code expands to include Amtrak code
            result = expand_station_codes(mnr_code)
            assert (
                mnr_code in result
            ), f"{name}: MNR code {mnr_code} missing from its own expansion"
            assert (
                amtrak_code in result
            ), f"{name}: Amtrak code {amtrak_code} missing from expansion of {mnr_code}"

    def test_expand_station_codes_without_equivalent(self):
        """expand_station_codes returns single-element list for non-shared stations."""
        non_shared_codes = ["NY", "NP", "TR", "PHO", "MWPL", "JAM"]
        for code in non_shared_codes:
            result = expand_station_codes(code)
            assert result == [
                code
            ], f"Non-shared code {code} should expand to [{code}], got {result}"

    def test_expand_station_codes_original_code_first(self):
        """expand_station_codes returns the queried code as first element."""
        for amtrak_code, mnr_code, name in self.EXPECTED_PAIRS:
            result = expand_station_codes(amtrak_code)
            assert (
                result[0] == amtrak_code
            ), f"{name}: first element should be queried code {amtrak_code}, got {result[0]}"

            result = expand_station_codes(mnr_code)
            assert (
                result[0] == mnr_code
            ), f"{name}: first element should be queried code {mnr_code}, got {result[0]}"

    def test_canonical_station_code_is_deterministic(self):
        """canonical_station_code returns the same code regardless of which equivalent is passed."""
        for amtrak_code, mnr_code, name in self.EXPECTED_PAIRS:
            canonical_from_amtrak = canonical_station_code(amtrak_code)
            canonical_from_mnr = canonical_station_code(mnr_code)
            assert canonical_from_amtrak == canonical_from_mnr, (
                f"{name}: canonical({amtrak_code})={canonical_from_amtrak} != "
                f"canonical({mnr_code})={canonical_from_mnr}"
            )

    def test_canonical_station_code_non_shared(self):
        """canonical_station_code returns the code itself for non-shared stations."""
        non_shared_codes = ["NY", "NP", "TR", "PHO", "MWPL"]
        for code in non_shared_codes:
            assert (
                canonical_station_code(code) == code
            ), f"Non-shared code {code} should be its own canonical"

    def test_equivalents_are_symmetric(self):
        """Every member of an equivalence group maps to the same group."""
        for code, group in STATION_EQUIVALENTS.items():
            assert (
                code in group
            ), f"Code {code} not in its own equivalence group {group}"
            for member in group:
                assert (
                    member in STATION_EQUIVALENTS
                ), f"Code {member} (in group with {code}) has no STATION_EQUIVALENTS entry"
                assert (
                    STATION_EQUIVALENTS[member] is group
                ), f"Code {member} and {code} should share the same group object"

    def test_all_equivalent_codes_exist_in_station_names(self):
        """Every code in STATION_EQUIVALENTS should have an entry in STATION_NAMES."""
        for code in STATION_EQUIVALENTS:
            assert (
                code in STATION_NAMES
            ), f"Equivalent code {code} is missing from STATION_NAMES"

    def test_equivalent_stations_share_same_name(self):
        """Equivalent station codes should resolve to the same display name."""
        for amtrak_code, mnr_code, expected_name in self.EXPECTED_PAIRS:
            amtrak_name = get_station_name(amtrak_code)
            mnr_name = get_station_name(mnr_code)
            assert amtrak_name == expected_name, (
                f"Amtrak code {amtrak_code} resolves to '{amtrak_name}', "
                f"expected '{expected_name}'"
            )
            assert mnr_name == expected_name, (
                f"MNR code {mnr_code} resolves to '{mnr_name}', "
                f"expected '{expected_name}'"
            )

    def test_equivalence_groups_have_no_overlap(self):
        """No station code should appear in multiple equivalence groups."""
        seen: dict[str, int] = {}
        for i, group in enumerate(STATION_EQUIVALENCE_GROUPS):
            for code in group:
                assert (
                    code not in seen
                ), f"Code {code} appears in group {seen[code]} and group {i}"
                seen[code] = i

    def test_subway_complex_expansion(self):
        """Querying any platform code at a subway complex returns all platform codes."""
        # 14 St-Union Sq: S635 (4/5/6), SL03 (L), SR20 (N/Q/R/W)
        expected_14st = {"S635", "SL03", "SR20"}
        for code in expected_14st:
            result = expand_station_codes(code)
            assert set(result) == expected_14st, (
                f"expand_station_codes('{code}') returned {result}, "
                f"expected all of {sorted(expected_14st)}"
            )
            assert (
                result[0] == code
            ), f"Queried code {code} should be first, got {result[0]}"

        # Times Sq-42 St: 5-platform complex (includes S902/GS shuttle)
        expected_ts = {"S127", "S725", "SA27", "SR16", "S902"}
        for code in expected_ts:
            result = expand_station_codes(code)
            assert set(result) == expected_ts, (
                f"expand_station_codes('{code}') returned {result}, "
                f"expected all of {sorted(expected_ts)}"
            )

        # Grand Central-42 St: includes S901/GS shuttle
        expected_gc = {"S631", "S723", "S901"}
        for code in expected_gc:
            result = expand_station_codes(code)
            assert set(result) == expected_gc, (
                f"expand_station_codes('{code}') returned {result}, "
                f"expected all of {sorted(expected_gc)}"
            )

    def test_canonical_station_code_deterministic_for_subway(self):
        """canonical_station_code returns the same code for all members of a subway complex."""
        for group in SUBWAY_STATION_COMPLEXES:
            canonical_codes = {canonical_station_code(code) for code in group}
            assert (
                len(canonical_codes) == 1
            ), f"Group {sorted(group)} produced multiple canonical codes: {canonical_codes}"

    @pytest.mark.parametrize(
        "complex_codes,description",
        [
            ({"S109", "SA03"}, "Dyckman St (1 + A)"),
            ({"S111", "SA06"}, "181 St (1 + A)"),
            ({"S114", "S302", "SA12", "SD13"}, "145 St (1 + 3 + A/C + B/D)"),
            ({"S116", "S225", "S621", "SA15"}, "125 St (1 + 2/3 + 4/5/6 + A/B/C/D)"),
            ({"S118", "SA17"}, "Cathedral Pkwy 110 St (1 + A/B/C)"),
            ({"S119", "SA18"}, "103 St West Side (1 + A/B/C)"),
            ({"S120", "SA19"}, "96 St West Side (1/2/3 + A/B/C)"),
            ({"S126", "SA25"}, "50 St (1/2 + A/C/E)"),
            ({"S128", "SA28"}, "34 St-Penn Station (1/2/3 + A/C/E)"),
            (
                {"S135", "S639", "SA34", "SM20", "SQ01", "SR23"},
                "Canal St (1/2 + 4/6 + A/C/E + J/Z + Q + N/R/W)",
            ),
            (
                {"PWC", "S138", "S228", "SA36", "SE01", "SR25"},
                "WTC Cortlandt / Chambers / Cortlandt / Park Pl",
            ),
            ({"S208", "S503"}, "Gun Hill Rd (2 + 5)"),
            ({"S211", "S504"}, "Pelham Pkwy (2 + 5)"),
            ({"SA11", "SD12"}, "155 St (A/C + B/D)"),
            ({"SD25", "SF24"}, "7 Av Park Slope (B/Q + F/G)"),
        ],
    )
    def test_unified_subway_complexes(self, complex_codes, description):
        """Subway stations at the same physical location expand to each other.

        These were previously separate entries despite being connected
        in-station transfer points. The GTFS transfers.txt omitted them.
        """
        for code in complex_codes:
            result = set(expand_station_codes(code))
            assert result == complex_codes, (
                f"{description}: expand_station_codes('{code}') returned "
                f"{sorted(result)}, expected {sorted(complex_codes)}"
            )
            # Queried code should be first in the list
            result_list = expand_station_codes(code)
            assert result_list[0] == code, (
                f"{description}: queried code {code} should be first, "
                f"got {result_list[0]}"
            )

    def test_unified_complexes_in_subway_station_complexes(self):
        """All unified complexes must be present in SUBWAY_STATION_COMPLEXES."""
        expected_groups = [
            {"S109", "SA03"},  # Dyckman St
            {"S111", "SA06"},  # 181 St
            {"S114", "S302", "SA12", "SD13"},  # 145 St
            {"S116", "S225", "S621", "SA15"},  # 125 St
            {"S118", "SA17"},  # Cathedral Pkwy
            {"S119", "SA18"},  # 103 St West
            {"S120", "SA19"},  # 96 St West
            {"S126", "SA25"},  # 50 St
            {"S128", "SA28"},  # 34 St-Penn Station
            {"S135", "S639", "SA34", "SM20", "SQ01", "SR23"},  # Canal St
            {"PWC", "S138", "S228", "SA36", "SE01", "SR25"},  # WTC / Chambers
            {"S208", "S503"},  # Gun Hill Rd
            {"S211", "S504"},  # Pelham Pkwy
            {"SA11", "SD12"},  # 155 St
            {"SD25", "SF24"},  # 7 Av Park Slope
        ]
        for expected in expected_groups:
            found = False
            for group in SUBWAY_STATION_COMPLEXES:
                if expected.issubset(group):
                    found = True
                    break
            assert found, (
                f"Expected complex {sorted(expected)} not found in "
                f"SUBWAY_STATION_COMPLEXES"
            )

    def test_unified_complexes_canonical_code_deterministic(self):
        """canonical_station_code is the same for all members of unified complexes."""
        groups = [
            {"S109", "SA03"},
            {"S111", "SA06"},
            {"S114", "S302", "SA12", "SD13"},
            {"S116", "S225", "S621", "SA15"},
            {"S118", "SA17"},
            {"S119", "SA18"},
            {"S120", "SA19"},
            {"S126", "SA25"},
            {"S128", "SA28"},
            {"S135", "S639", "SA34", "SM20", "SQ01", "SR23"},
            {"S138", "S228", "SA36", "SE01", "SR25"},
            {"S208", "S503"},
            {"S211", "S504"},
            {"SA11", "SD12"},
            {"SD25", "SF24"},
        ]
        for group in groups:
            canonical_codes = {canonical_station_code(code) for code in group}
            assert (
                len(canonical_codes) == 1
            ), f"Group {sorted(group)} produced multiple canonical codes: {canonical_codes}"

    def test_non_complex_subway_station_expands_to_self(self):
        """Subway stations not in any complex expand to just themselves."""
        # S101 = Van Cortlandt Park-242 St (standalone station on 1 line)
        result = expand_station_codes("S101")
        assert result == [
            "S101"
        ], f"Standalone station S101 should expand to ['S101'], got {result}"


class TestSubwayGTFSStopMapping:
    """Tests for Subway GTFS stop_id to internal station code mapping.

    Subway GTFS uses parent station IDs (e.g., '101') with optional N/S
    directional suffixes (e.g., '101N', '101S'). Internal codes are
    S-prefixed (e.g., 'S101'). SIR stations use 'S' prefix in GTFS
    and 'SS' prefix internally (e.g., 'S31' -> 'SS31').

    Regression tests for commit 3b103d1 which fixed station code mismatches
    breaking subway departure times and train details.
    """

    @pytest.mark.parametrize(
        "gtfs_stop_id,expected_code,description",
        [
            # Regular subway stations
            ("101", "S101", "Van Cortlandt Park-242 St (1 line)"),
            ("103", "S103", "238 St (1 line)"),
            ("631", "S631", "Grand Central-42 St (4/5/6)"),
            ("A27", "SA27", "42 St-Port Authority (A/C/E)"),
            ("R16", "SR16", "Times Sq-42 St (N/Q/R/W)"),
            ("L03", "SL03", "14 St-Union Sq (L)"),
            # SIR (Staten Island Railway) - GTFS 'S' prefix -> internal 'SS' prefix
            ("S01", "SS01", "St George (SIR)"),
            ("S31", "SS31", "Tottenville (SIR)"),
            ("S09", "SS09", "Stapleton (SIR)"),
        ],
    )
    def test_subway_basic_mapping(self, gtfs_stop_id, expected_code, description):
        """Test basic GTFS stop_id to internal code mapping for subway stations."""
        result = map_gtfs_stop_to_station_code(gtfs_stop_id, "ignored", "SUBWAY")
        assert result == expected_code, (
            f"Subway station '{description}' (GTFS id={gtfs_stop_id}) mapped to "
            f"'{result}', expected '{expected_code}'"
        )

    @pytest.mark.parametrize(
        "gtfs_stop_id,expected_code,description",
        [
            ("101N", "S101", "Van Cortlandt Park northbound"),
            ("101S", "S101", "Van Cortlandt Park southbound"),
            ("631N", "S631", "Grand Central northbound"),
            ("631S", "S631", "Grand Central southbound"),
            ("A27N", "SA27", "42 St-Port Authority northbound"),
            ("A27S", "SA27", "42 St-Port Authority southbound"),
        ],
    )
    def test_subway_directional_suffix_stripping(
        self, gtfs_stop_id, expected_code, description
    ):
        """Test that N/S directional suffixes are stripped before lookup.

        GTFS-RT feeds append 'N' (northbound) or 'S' (southbound) to stop IDs.
        The mapper must strip these to find the parent station.
        """
        result = map_gtfs_stop_to_station_code(gtfs_stop_id, "ignored", "SUBWAY")
        assert result == expected_code, (
            f"Subway '{description}' (GTFS id={gtfs_stop_id}) mapped to "
            f"'{result}', expected '{expected_code}'"
        )

    def test_subway_invalid_stop_returns_none(self):
        """Test that unmapped GTFS stop IDs return None."""
        assert map_gtfs_stop_to_station_code("99999", "ignored", "SUBWAY") is None
        assert map_gtfs_stop_to_station_code("", "ignored", "SUBWAY") is None
        assert map_gtfs_stop_to_station_code("INVALID", "ignored", "SUBWAY") is None

    def test_subway_name_parameter_is_ignored(self):
        """Subway mapping uses stop_id only, not stop_name."""
        result_a = map_gtfs_stop_to_station_code("101", "Van Cortlandt", "SUBWAY")
        result_b = map_gtfs_stop_to_station_code("101", "WRONG NAME", "SUBWAY")
        assert result_a == result_b == "S101"

    def test_subway_forward_map_completeness(self):
        """Every subway GTFS mapping should point to a code in SUBWAY_STATION_NAMES."""
        for gtfs_id, internal_code in SUBWAY_GTFS_STOP_TO_INTERNAL_MAP.items():
            assert internal_code in SUBWAY_STATION_NAMES, (
                f"GTFS stop_id '{gtfs_id}' maps to '{internal_code}' "
                f"which is not in SUBWAY_STATION_NAMES"
            )

    def test_subway_reverse_map_consistency(self):
        """Reverse map should be consistent with forward map.

        For every entry in INTERNAL_TO_SUBWAY_GTFS_STOP_MAP, looking up
        the GTFS ID in the forward map should return the internal code.
        """
        for internal_code, gtfs_id in INTERNAL_TO_SUBWAY_GTFS_STOP_MAP.items():
            forward_result = SUBWAY_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_id)
            assert forward_result == internal_code, (
                f"Reverse map says '{internal_code}' -> GTFS '{gtfs_id}', "
                f"but forward map says GTFS '{gtfs_id}' -> '{forward_result}'"
            )

    def test_subway_reverse_map_covers_all_forward_entries(self):
        """Every internal code in the forward map should have a reverse mapping."""
        forward_codes = set(SUBWAY_GTFS_STOP_TO_INTERNAL_MAP.values())
        reverse_codes = set(INTERNAL_TO_SUBWAY_GTFS_STOP_MAP.keys())
        missing = forward_codes - reverse_codes
        assert (
            not missing
        ), f"Internal codes in forward map but missing from reverse map: {sorted(missing)}"

    def test_subway_round_trip_mapping(self):
        """Round-trip: GTFS -> internal -> GTFS should return the original ID."""
        sample_ids = ["101", "631", "A27", "R16", "L03", "S01", "S31"]
        for gtfs_id in sample_ids:
            internal = SUBWAY_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_id)
            assert internal is not None, f"GTFS '{gtfs_id}' not in forward map"
            back_to_gtfs = INTERNAL_TO_SUBWAY_GTFS_STOP_MAP.get(internal)
            assert (
                back_to_gtfs == gtfs_id
            ), f"Round-trip failed: GTFS '{gtfs_id}' -> '{internal}' -> '{back_to_gtfs}'"

    def test_subway_map_function_directly(self):
        """Test map_subway_gtfs_stop function directly (not through dispatch)."""
        assert map_subway_gtfs_stop("101") == "S101"
        assert map_subway_gtfs_stop("101N") == "S101"
        assert map_subway_gtfs_stop("101S") == "S101"
        assert map_subway_gtfs_stop("S31") == "SS31"
        assert map_subway_gtfs_stop("99999") is None


class TestMNRGTFSStopMapping:
    """Tests for Metro-North GTFS stop_id to internal station code mapping.

    MNR GTFS uses numeric stop_ids (e.g., '1' for Grand Central).
    Internal codes are M-prefixed (e.g., 'M125') or special (e.g., 'GCT').

    Regression tests for commit 3b103d1 which fixed station code mismatches
    breaking MNR departure times and train details.
    """

    @pytest.mark.parametrize(
        "gtfs_stop_id,expected_code,description",
        [
            # Hudson Line
            ("1", "GCT", "Grand Central Terminal"),
            ("4", "M125", "Harlem-125th Street"),
            ("622", "MEYS", "Yankees-E 153 St"),
            # Harlem Line
            ("18", "MYON", "Yonkers"),
            # New Haven Line
            ("172", "MWTB", "Waterbury"),
            ("165", "MDBY", "Danbury"),
        ],
    )
    def test_mnr_basic_mapping(self, gtfs_stop_id, expected_code, description):
        """Test basic GTFS stop_id to internal code mapping for MNR stations."""
        result = map_gtfs_stop_to_station_code(gtfs_stop_id, "ignored", "MNR")
        assert result == expected_code, (
            f"MNR station '{description}' (GTFS id={gtfs_stop_id}) mapped to "
            f"'{result}', expected '{expected_code}'"
        )

    def test_mnr_invalid_stop_returns_none(self):
        """Test that unmapped GTFS stop IDs return None."""
        assert map_gtfs_stop_to_station_code("99999", "ignored", "MNR") is None
        assert map_gtfs_stop_to_station_code("", "ignored", "MNR") is None
        assert map_gtfs_stop_to_station_code("INVALID", "ignored", "MNR") is None

    def test_mnr_name_parameter_is_ignored(self):
        """MNR mapping uses stop_id only, not stop_name."""
        result_a = map_gtfs_stop_to_station_code("1", "Grand Central", "MNR")
        result_b = map_gtfs_stop_to_station_code("1", "WRONG NAME", "MNR")
        assert result_a == result_b == "GCT"

    def test_mnr_forward_map_completeness(self):
        """Every MNR GTFS mapping should point to a code in MNR_STATION_NAMES."""
        for gtfs_id, internal_code in MNR_GTFS_STOP_TO_INTERNAL_MAP.items():
            # GCT is shared with LIRR and lives in STATION_NAMES, not MNR_STATION_NAMES
            if internal_code == "GCT":
                assert internal_code in STATION_NAMES, (
                    f"GTFS stop_id '{gtfs_id}' maps to 'GCT' "
                    f"which is not in STATION_NAMES"
                )
            else:
                assert internal_code in MNR_STATION_NAMES, (
                    f"GTFS stop_id '{gtfs_id}' maps to '{internal_code}' "
                    f"which is not in MNR_STATION_NAMES"
                )

    def test_mnr_reverse_map_consistency(self):
        """Reverse map should be consistent with forward map."""
        for internal_code, gtfs_id in INTERNAL_TO_MNR_GTFS_STOP_MAP.items():
            forward_result = MNR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_id)
            assert forward_result == internal_code, (
                f"Reverse map says '{internal_code}' -> GTFS '{gtfs_id}', "
                f"but forward map says GTFS '{gtfs_id}' -> '{forward_result}'"
            )

    def test_mnr_reverse_map_covers_all_forward_entries(self):
        """Every internal code in the forward map should have a reverse mapping."""
        forward_codes = set(MNR_GTFS_STOP_TO_INTERNAL_MAP.values())
        reverse_codes = set(INTERNAL_TO_MNR_GTFS_STOP_MAP.keys())
        missing = forward_codes - reverse_codes
        assert (
            not missing
        ), f"Internal codes in forward map but missing from reverse map: {sorted(missing)}"

    def test_mnr_round_trip_mapping(self):
        """Round-trip: GTFS -> internal -> GTFS should return the original ID."""
        sample_ids = ["1", "4", "622", "18", "172", "165"]
        for gtfs_id in sample_ids:
            internal = MNR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_id)
            assert internal is not None, f"GTFS '{gtfs_id}' not in forward map"
            back_to_gtfs = INTERNAL_TO_MNR_GTFS_STOP_MAP.get(internal)
            assert (
                back_to_gtfs == gtfs_id
            ), f"Round-trip failed: GTFS '{gtfs_id}' -> '{internal}' -> '{back_to_gtfs}'"
