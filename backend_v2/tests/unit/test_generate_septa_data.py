"""Unit tests for scripts/generate_septa_data.py.

Covers the two pure helpers behind issue #1632: bidirectional route-sequence
generation and deterministic station ordering. The generator's own IO
(downloading and parsing the SEPTA feed) is not exercised here — these tests
drive the logic with route_stops rows shaped exactly like SEPTA's, so they run
without network access and pin behaviour the generated artifact depends on.
"""

import os
import sys

# Add scripts directory to path so we can import the generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))

from generate_septa_data import (  # noqa: E402
    build_route_sequences,
    sort_station_names,
)


def _rs(route_id: str, direction_id: str, order: int, stop_id: str) -> dict[str, str]:
    """One route_stops.txt row, in SEPTA's column shape (all values strings)."""
    return {
        "route_id": route_id,
        "direction_id": direction_id,
        "stop_id": stop_id,
        "route_stop_sort_order": str(order),
    }


class TestBuildRouteSequences:
    """Ordered per-direction station sequences from route_stops.txt rows."""

    # Baltimore Av & 42nd St: 20876 is the outbound curb, 20879 the inbound one.
    # This is the real pair named in the #1573 normalizer comment.
    STOP_TO_CODE = {
        "20876": "SEPM20876",
        "20881": "SEPM20881",
        "20879": "SEPM20879",
        "20884": "SEPM20884",
    }

    ROWS = [
        _rs("T2", "0", 1, "20876"),
        _rs("T2", "0", 2, "20881"),
        _rs("T2", "1", 1, "20884"),
        _rs("T2", "1", 2, "20879"),
    ]

    def test_outbound_sequence_is_direction_zero_in_sort_order(self):
        seqs = build_route_sequences(self.ROWS, {"T2"}, self.STOP_TO_CODE, "0")
        assert seqs == {"T2": ["SEPM20876", "SEPM20881"]}

    def test_inbound_sequence_is_direction_one_in_sort_order(self):
        """The whole point of #1632: direction 1 produces its own sequence.

        Before the fix this direction was filtered out entirely, so its codes
        appeared in no route tuple anywhere in the topology.
        """
        seqs = build_route_sequences(self.ROWS, {"T2"}, self.STOP_TO_CODE, "1")
        assert seqs == {"T2": ["SEPM20884", "SEPM20879"]}

    def test_inbound_is_not_the_outbound_sequence_reversed(self):
        """Inbound visits different station codes, not the same ones backwards.

        Each trolley curb stop is its own code, so treating the reverse
        direction as `reversed(outbound)` would silently keep 271 real
        station codes out of the topology.
        """
        out = build_route_sequences(self.ROWS, {"T2"}, self.STOP_TO_CODE, "0")["T2"]
        inb = build_route_sequences(self.ROWS, {"T2"}, self.STOP_TO_CODE, "1")["T2"]
        assert inb != list(reversed(out))
        assert not set(out) & set(inb)

    def test_rows_are_ordered_by_sort_order_not_file_order(self):
        rows = [
            _rs("T2", "0", 3, "20879"),
            _rs("T2", "0", 1, "20876"),
            _rs("T2", "0", 2, "20881"),
        ]
        seqs = build_route_sequences(rows, {"T2"}, self.STOP_TO_CODE, "0")
        assert seqs == {"T2": ["SEPM20876", "SEPM20881", "SEPM20879"]}

    def test_consecutive_duplicate_codes_are_collapsed(self):
        """Grouped subway platforms can map two adjacent stop_ids to one code."""
        stop_to_code = {"a1": "SEPM1", "a2": "SEPM1", "b1": "SEPM2"}
        rows = [
            _rs("B1", "0", 1, "a1"),
            _rs("B1", "0", 2, "a2"),
            _rs("B1", "0", 3, "b1"),
        ]
        seqs = build_route_sequences(rows, {"B1"}, stop_to_code, "0")
        assert seqs == {"B1": ["SEPM1", "SEPM2"]}

    def test_non_adjacent_repeat_is_kept(self):
        """Only *consecutive* duplicates collapse; a genuine revisit stays."""
        stop_to_code = {"a": "SEPM1", "b": "SEPM2"}
        rows = [
            _rs("T1", "0", 1, "a"),
            _rs("T1", "0", 2, "b"),
            _rs("T1", "0", 3, "a"),
        ]
        seqs = build_route_sequences(rows, {"T1"}, stop_to_code, "0")
        assert seqs == {"T1": ["SEPM1", "SEPM2", "SEPM1"]}

    def test_routes_outside_the_requested_set_are_skipped(self):
        """The bus network shares route_stops.txt with Metro."""
        rows = self.ROWS + [_rs("17", "0", 1, "20876")]
        seqs = build_route_sequences(rows, {"T2"}, self.STOP_TO_CODE, "0")
        assert set(seqs) == {"T2"}

    def test_stops_with_no_internal_code_are_dropped(self):
        """A route_stops row for a stop no trip ever served has no code."""
        rows = [_rs("T2", "0", 1, "20876"), _rs("T2", "0", 2, "99999")]
        seqs = build_route_sequences(rows, {"T2"}, self.STOP_TO_CODE, "0")
        assert seqs == {"T2": ["SEPM20876"]}

    def test_route_ids_may_be_a_dict(self):
        """Callers pass the `metro_routes` dict directly; membership is by key."""
        seqs = build_route_sequences(
            self.ROWS, {"T2": {"route_type": "0"}}, self.STOP_TO_CODE, "0"
        )
        assert seqs == {"T2": ["SEPM20876", "SEPM20881"]}

    def test_absent_direction_yields_no_entry(self):
        rows = [_rs("T2", "0", 1, "20876")]
        assert build_route_sequences(rows, {"T2"}, self.STOP_TO_CODE, "1") == {}


class TestSortStationNames:
    """Deterministic ordering of the generated station-name block."""

    def test_sorted_by_display_name(self):
        assert sort_station_names({"SEPM2": "Bravo", "SEPM1": "Alpha"}) == [
            ("SEPM1", "Alpha"),
            ("SEPM2", "Bravo"),
        ]

    def test_duplicate_names_break_ties_on_code(self):
        """SEPTA Metro has many stations sharing one display name.

        Sorting on the name alone leaves these in `dict` insertion order,
        which derives from set iteration and so varies with PYTHONHASHSEED.
        """
        names = {
            "SEPM31140": "15th St/City Hall",
            "SEPM1392": "15th St/City Hall",
            "SEPM20659": "15th St/City Hall",
        }
        assert [c for c, _ in sort_station_names(names)] == [
            "SEPM1392",
            "SEPM20659",
            "SEPM31140",
        ]

    def test_result_is_independent_of_insertion_order(self):
        """The regression itself: same data, different insertion order, same output."""
        pairs = [
            ("SEPM1392", "15th St/City Hall"),
            ("SEPM20659", "15th St/City Hall"),
            ("SEPM416", "69th St Transit Center"),
            ("SEPM31140", "15th St/City Hall"),
        ]
        assert sort_station_names(dict(pairs)) == sort_station_names(
            dict(reversed(pairs))
        )
