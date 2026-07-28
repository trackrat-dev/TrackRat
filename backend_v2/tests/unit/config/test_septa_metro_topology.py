"""SEPTA Metro bidirectional route topology (issue #1632).

Before this, route topology was generated from ``direction_id=0`` only. Each
trolley curb stop is its own station code, so a route's inbound path is a
largely disjoint set of codes — 271 of the 633 configured Metro stations
appeared in no route tuple at all. Every consumer that asks "is this station on
a route" therefore answered no for them: direct-route detection, transfer
search, station-pair alert derivation, and segment validation.

These tests pin the completeness invariant and each of those consumer paths.
"""

import pytest

from trackrat.config.route_topology import (
    ALL_ROUTES,
    find_route_for_segment,
    get_routes_for_data_source,
)
from trackrat.config.stations.septa_metro import (
    SEPTA_METRO_ROUTE_STATIONS,
    SEPTA_METRO_ROUTE_STATIONS_INBOUND,
    SEPTA_METRO_ROUTES,
    SEPTA_METRO_STATION_NAMES,
)
from trackrat.config.stations.septa_rr import SEPTA_RR_STATION_NAMES
from trackrat.config.transfer_points import (
    get_station_lines,
    get_systems_serving_station,
)

# Baltimore Av & 42nd St on the Route 34 trolley (T2): SEPM20876 is the
# outbound curb, SEPM20879 the inbound one. The pair the #1573 normalizer
# comment cites as the canonical example of the defect.
OUTBOUND_CURB = "SEPM20876"
INBOUND_CURB = "SEPM20879"
# Baltimore Av & 44th St, inbound curb — also inbound-only, same line.
INBOUND_CURB_NEXT = "SEPM20881"


def _metro_routes():
    return get_routes_for_data_source("SEPTA_METRO")


class TestTopologyCompleteness:
    """Acceptance criterion: every Metro stop is in a route."""

    def test_every_configured_station_is_on_a_route(self):
        covered: set[str] = set()
        for route in _metro_routes():
            covered.update(route.all_stations)
        missing = sorted(set(SEPTA_METRO_STATION_NAMES) - covered)
        assert not missing, (
            f"{len(missing)} SEPTA Metro station codes are in no route tuple, "
            f"so they are invisible to routing, transfers, and alerts: "
            f"{missing[:10]}"
        )

    def test_inbound_direction_adds_the_missing_stops(self):
        """The outbound tuples alone do not cover the network.

        This is the measurement from the issue, asserted rather than assumed:
        if it ever passes trivially (because outbound already covered
        everything) the completeness test above has stopped being meaningful.
        """
        outbound = {c for seq in SEPTA_METRO_ROUTE_STATIONS.values() for c in seq}
        inbound = {
            c for seq in SEPTA_METRO_ROUTE_STATIONS_INBOUND.values() for c in seq
        }
        assert outbound < set(SEPTA_METRO_STATION_NAMES)
        assert outbound | inbound == set(SEPTA_METRO_STATION_NAMES)

    def test_every_route_has_both_directions(self):
        for route_id in SEPTA_METRO_ROUTES:
            assert SEPTA_METRO_ROUTE_STATIONS.get(route_id), route_id
            assert SEPTA_METRO_ROUTE_STATIONS_INBOUND.get(route_id), route_id

    def test_inbound_sequence_is_not_the_outbound_one_reversed(self):
        """At least one trolley route must genuinely differ between directions.

        Subway routes share one code per station, so their two sequences are
        near-mirrors; the trolleys are where per-curb codes make the paths
        disjoint. If this stopped holding, the generator has silently gone
        back to deriving one direction from the other.
        """
        differing = [
            rid
            for rid, seq in SEPTA_METRO_ROUTE_STATIONS.items()
            if set(SEPTA_METRO_ROUTE_STATIONS_INBOUND[rid]) - set(seq)
        ]
        assert differing, "no route has any inbound-only stop"

    def test_regional_rail_is_unaffected(self):
        """RR stops are 1:1 with stations, so it needs no inbound sequence."""
        covered: set[str] = set()
        for route in get_routes_for_data_source("SEPTA_RR"):
            assert route.reverse_stations == ()
            covered.update(route.all_stations)
        assert not set(SEPTA_RR_STATION_NAMES) - covered

    def test_no_other_system_gained_a_reverse_sequence(self):
        """`reverse_stations` must stay empty everywhere but SEPTA Metro."""
        offenders = sorted(
            route.id
            for route in ALL_ROUTES
            if route.reverse_stations and route.data_source != "SEPTA_METRO"
        )
        assert not offenders


class TestRouteContainment:
    """Both stop variants resolve through `Route`."""

    def test_outbound_and_inbound_curb_are_on_the_same_route(self):
        route = find_route_for_segment("SEPTA_METRO", OUTBOUND_CURB, INBOUND_CURB)
        assert route is not None
        assert route.line_codes == frozenset({"SEPTA-T2"})

    def test_two_inbound_only_codes_resolve(self):
        """Fails if `_station_set` is built from the outbound tuple alone."""
        route = find_route_for_segment("SEPTA_METRO", INBOUND_CURB, INBOUND_CURB_NEXT)
        assert route is not None

    def test_unknown_code_still_resolves_to_nothing(self):
        assert find_route_for_segment("SEPTA_METRO", INBOUND_CURB, "SEPM99999") is None

    def test_all_stations_has_no_duplicates(self):
        for route in _metro_routes():
            codes = route.all_stations
            assert len(codes) == len(set(codes)), route.id

    def test_all_stations_starts_with_the_outbound_sequence(self):
        for route in _metro_routes():
            assert route.all_stations[: len(route.stations)] == route.stations

    def test_intermediate_stations_stay_within_one_direction(self):
        """Expansion must not stitch a path across the two directions.

        Each direction is its own sequence; a pair with one code from each
        has no single physical path, so `get_intermediate_stations` returns
        None rather than inventing one.
        """
        route = find_route_for_segment("SEPTA_METRO", INBOUND_CURB, INBOUND_CURB_NEXT)
        assert route is not None

        path = route.get_intermediate_stations(INBOUND_CURB, INBOUND_CURB_NEXT)
        assert path is not None
        assert path[0] == INBOUND_CURB and path[-1] == INBOUND_CURB_NEXT
        # Every stop on the path comes from the inbound sequence, none from the
        # outbound one — the two are never spliced together.
        assert set(path) <= set(route.reverse_stations)

        # One code from each direction has no single physical path.
        assert route.get_intermediate_stations(OUTBOUND_CURB, INBOUND_CURB) is None


class TestDirectRouteDetection:
    """`_has_direct_route` answers for inbound codes (departure service)."""

    def test_inbound_pair_has_a_direct_route(self):
        from trackrat.services.departure import _has_direct_route

        assert (
            _has_direct_route(INBOUND_CURB, INBOUND_CURB_NEXT, ["SEPTA_METRO"]) is True
        )

    def test_unrelated_pair_still_has_none(self):
        from trackrat.services.departure import _has_direct_route

        # Fern Rock TC is on the Broad Street Line, not the Route 34 trolley.
        assert _has_direct_route(INBOUND_CURB, "SEPM20965", ["SEPTA_METRO"]) is False


class TestDirectionFilter:
    """`_filter_by_direction` must resolve the sequence before indexing.

    `_station_set` is the union of both directions, so a journey between two
    inbound-only codes passes the membership guard. Indexing the outbound
    `route.stations` for it raises ValueError — and `evaluate_route_alerts`
    has no per-subscription handler, so one such subscription would abort the
    entire alert run for every user.
    """

    class _Journey:
        """Minimal stand-in: `_filter_by_direction` reads only these two fields."""

        def __init__(self, origin: str, terminal: str):
            self.origin_station_code = origin
            self.terminal_station_code = terminal

    def _t2(self):
        route = next(r for r in _metro_routes() if r.id == "septa-metro-t2")
        assert route.reverse_stations, "T2 must have an inbound sequence"
        return route

    def test_inbound_journey_does_not_raise(self):
        from trackrat.services.alert_evaluator import _filter_by_direction

        route = self._t2()
        journey = self._Journey(route.reverse_stations[0], route.reverse_stations[-1])
        # Direction given as the *outbound* terminus, which is what a
        # subscription created from the outbound station list would carry.
        _filter_by_direction([journey], route, route.stations[-1])

    def test_inbound_journey_matches_its_own_terminus(self):
        from trackrat.services.alert_evaluator import _filter_by_direction

        route = self._t2()
        journey = self._Journey(route.reverse_stations[0], route.reverse_stations[-1])
        kept = _filter_by_direction([journey], route, route.reverse_stations[-1])
        assert kept == [journey]

    def test_inbound_journey_is_dropped_for_the_opposite_terminus(self):
        from trackrat.services.alert_evaluator import _filter_by_direction

        route = self._t2()
        journey = self._Journey(route.reverse_stations[-1], route.reverse_stations[0])
        assert _filter_by_direction([journey], route, route.reverse_stations[-1]) == []

    def test_outbound_journey_still_filters_normally(self):
        from trackrat.services.alert_evaluator import _filter_by_direction

        route = self._t2()
        forward = self._Journey(route.stations[0], route.stations[-1])
        backward = self._Journey(route.stations[-1], route.stations[0])
        kept = _filter_by_direction([forward, backward], route, route.stations[-1])
        assert kept == [forward]

    def test_njt_route_is_unaffected(self):
        """Single-sequence routes behave exactly as before."""
        from trackrat.config.route_topology import get_route_by_line_code
        from trackrat.services.alert_evaluator import _filter_by_direction

        route = get_route_by_line_code("NJT", "NE")
        assert route is not None and route.reverse_stations == ()
        forward = self._Journey(route.stations[0], route.stations[-1])
        backward = self._Journey(route.stations[-1], route.stations[0])
        assert _filter_by_direction([forward, backward], route, route.stations[-1]) == [
            forward
        ]

    def test_sequence_containing_requires_one_shared_sequence(self):
        route = self._t2()
        inbound_only = next(
            c for c in route.reverse_stations if c not in route.stations
        )
        outbound_only = next(
            c for c in route.stations if c not in route.reverse_stations
        )
        assert route.sequence_containing(inbound_only) == route.reverse_stations
        assert route.sequence_containing(outbound_only) == route.stations
        # One code from each direction shares no sequence.
        assert route.sequence_containing(inbound_only, outbound_only) is None
        assert route.sequence_containing("SEPM99999") is None


class TestTransferPointIndexes:
    """`transfer_points` builds its indexes by iterating route stations."""

    def test_inbound_station_is_served_by_septa_metro(self):
        """This is the hardest failure of the old behaviour.

        An inbound curb belonged to no system at all, so trip search reported
        `no_transfer_points` for what is a single trolley ride.
        """
        assert "SEPTA_METRO" in get_systems_serving_station(INBOUND_CURB)

    def test_septa_metro_line_index_is_not_built(self):
        """Documents a pre-existing limit this change deliberately leaves alone.

        `_SYSTEM_STATION_LINES` is only built for `_INTRA_TRANSFER_SYSTEMS`,
        which has never included SEPTA. So `get_station_lines` is empty for
        Metro in *both* directions — unchanged by #1632, and not a directional
        defect. Adding SEPTA there would generate intra-Metro transfer points
        at every shared curb, which is a separate decision.
        """
        assert get_station_lines(OUTBOUND_CURB, "SEPTA_METRO") == frozenset()
        assert get_station_lines(INBOUND_CURB, "SEPTA_METRO") == frozenset()

    def test_every_metro_station_belongs_to_a_system(self):
        missing = sorted(
            code
            for code in SEPTA_METRO_STATION_NAMES
            if "SEPTA_METRO" not in get_systems_serving_station(code)
        )
        assert not missing, f"{len(missing)} codes serve no system: {missing[:10]}"


class TestStationPairAlertDerivation:
    """Station-pair alert subscriptions derive their route in both directions.

    Asserted at `_route_contains_station_pair`, which is the half #1632 owns:
    given a station pair, does any route claim it. Translating the matched
    route's `line_codes` into alert route ids is `_line_codes_to_gtfs_ids`,
    which has no SEPTA branch on `main` — that is issue #1631. Both halves are
    needed for a SEPTA subscription to deliver; this one is fixed here.
    """

    @pytest.mark.parametrize(
        "from_code,to_code",
        [
            pytest.param(OUTBOUND_CURB, "SEPM20884", id="outbound-pair"),
            pytest.param(INBOUND_CURB, INBOUND_CURB_NEXT, id="inbound-pair"),
            pytest.param(INBOUND_CURB_NEXT, INBOUND_CURB, id="inbound-pair-reversed"),
        ],
    )
    def test_pair_is_derived_to_the_trolley_line(self, from_code, to_code):
        from trackrat.services.alert_evaluator import _route_contains_station_pair

        matched = {
            code
            for route in ALL_ROUTES
            if route.data_source == "SEPTA_METRO"
            and _route_contains_station_pair(route, from_code, to_code)
            for code in route.line_codes
        }
        assert "SEPTA-T2" in matched

    def test_cross_line_pair_still_derives_nothing(self):
        from trackrat.services.alert_evaluator import _route_contains_station_pair

        matched = [
            route.id
            for route in ALL_ROUTES
            if route.data_source == "SEPTA_METRO"
            and _route_contains_station_pair(route, INBOUND_CURB, "SEPM20965")
        ]
        assert matched == []
