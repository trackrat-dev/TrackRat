"""Unit tests for `expects_real_time_departures`.

This predicate exists because "is this source real-time?" is the wrong question
for SEPTA Metro, and answering it at source granularity gets Metro exactly
backwards. Metro is deliberately absent from `REAL_TIME_DATA_SOURCES` — it is
served schedule-first so that Broad St and Market-Frankford, which SEPTA does
not feed live at all, are not hidden near departure by the stale-SCHEDULED
filter. But SEPTA *does* feed NHSL and the trolleys, and whether those reach
OBSERVED is the only external evidence that Metro's real-time ingest works
(issue #1634).

Without a per-line answer the two states below are indistinguishable from a
departure board, because both produce a full set of plausible times:

  - the collector is ingesting GTFS-RT and upgrading trips to OBSERVED
  - the collector is ingesting nothing and every row came off the timetable
"""

import pytest

from trackrat.config.route_topology import get_routes_for_data_source
from trackrat.config.stations import (
    SEPTA_METRO_ROUTES,
    SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES,
    SEPTA_METRO_SCHEDULE_ONLY_ROUTES,
)
from trackrat.services.departure import (
    REAL_TIME_DATA_SOURCES,
    expects_real_time_departures,
)


class TestSourceLevelSources:
    """For every system whose lines are uniform, source membership is the
    whole answer and the line codes are irrelevant."""

    @pytest.mark.parametrize("source", ["NJT", "AMTRAK", "PATH", "SUBWAY", "SEPTA_RR"])
    def test_real_time_sources_expect_observed(self, source: str):
        assert expects_real_time_departures(source, frozenset({"ANY"})) is True

    def test_patco_is_schedule_only(self):
        """PATCO has no real-time API at all — times are scheduled only. If this
        ever reported True the sweep would alarm on PATCO every single run."""
        assert expects_real_time_departures("PATCO", frozenset({"PATCO-1"})) is False

    def test_line_codes_do_not_change_a_non_metro_verdict(self):
        """Only SEPTA Metro splits by line. Passing Metro's schedule-only codes
        to another source must not make it schedule-only by accident."""
        assert (
            expects_real_time_departures("NJT", SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES)
            is True
        )

    def test_unknown_source_is_not_assumed_live(self):
        assert expects_real_time_departures("NOT_A_SOURCE", frozenset({"X"})) is False


class TestSeptaMetroSplitsByLine:
    """The case the predicate was written for."""

    def test_broad_street_is_schedule_only(self):
        assert (
            expects_real_time_departures("SEPTA_METRO", frozenset({"SEPTA-B1"}))
            is False
        )

    def test_market_frankford_is_schedule_only(self):
        assert (
            expects_real_time_departures("SEPTA_METRO", frozenset({"SEPTA-L1"}))
            is False
        )

    def test_norristown_high_speed_line_expects_observed(self):
        assert (
            expects_real_time_departures("SEPTA_METRO", frozenset({"SEPTA-M1"})) is True
        )

    def test_trolleys_expect_observed(self):
        for code in ("SEPTA-T1", "SEPTA-T2", "SEPTA-D1", "SEPTA-G1"):
            assert (
                expects_real_time_departures("SEPTA_METRO", frozenset({code})) is True
            ), f"{code} is fed in real time and must be expected to reach OBSERVED"

    def test_source_membership_alone_would_get_metro_wrong(self):
        """Pins the actual defect, not just the fixed behaviour.

        A reader who "simplifies" this predicate back to a
        `data_source in REAL_TIME_DATA_SOURCES` check gets False for NHSL, and
        the gate silently stops testing anything: Metro would be excused from
        ever producing an OBSERVED row, which is the exact failure the check
        was added to catch.
        """
        assert "SEPTA_METRO" not in REAL_TIME_DATA_SOURCES
        assert expects_real_time_departures("SEPTA_METRO", frozenset({"SEPTA-M1"})) is (
            not ("SEPTA_METRO" in REAL_TIME_DATA_SOURCES)
        )

    def test_a_route_carrying_any_live_line_expects_observed(self):
        """Mixed sets resolve to live: one live line on the route is enough for
        an all-SCHEDULED result to be suspicious."""
        assert (
            expects_real_time_departures(
                "SEPTA_METRO", frozenset({"SEPTA-B1", "SEPTA-M1"})
            )
            is True
        )

    def test_untagged_route_makes_no_claim(self):
        """Routes with no line_codes exist (LIRR terminal variants are resolved
        geometrically). Defaulting them to "expected live" would produce a
        finding with no evidence behind it."""
        assert expects_real_time_departures("SEPTA_METRO", frozenset()) is False
        assert expects_real_time_departures("SEPTA_METRO") is False


class TestScheduleOnlyConfigIntegrity:
    """The line-code set is derived, so these guard the derivation rather than
    restating it — a stale route_id in the source set would otherwise silently
    drop a line out of the schedule-only list and make the sweep alarm on it."""

    def test_every_schedule_only_route_id_resolves_to_a_line_code(self):
        assert len(SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES) == len(
            SEPTA_METRO_SCHEDULE_ONLY_ROUTES
        )
        for route_id in SEPTA_METRO_SCHEDULE_ONLY_ROUTES:
            assert route_id in SEPTA_METRO_ROUTES, (
                f"{route_id} is listed as schedule-only but is not a known "
                "SEPTA Metro route_id"
            )
            assert (
                SEPTA_METRO_ROUTES[route_id][0] in SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES
            )

    def test_every_schedule_only_line_code_is_served_by_a_real_route(self):
        """Catches the set drifting away from the topology the sweep iterates.

        A code in the schedule-only set that no route carries would exempt
        nothing, while a route the set was meant to cover would start being
        asserted on.
        """
        topology_codes = {
            code
            for route in get_routes_for_data_source("SEPTA_METRO")
            for code in route.line_codes
        }
        missing = SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES - topology_codes
        assert not missing, f"schedule-only codes absent from the topology: {missing}"

    def test_every_metro_route_in_the_topology_gets_a_verdict(self):
        """The sweep calls this for every SEPTA_METRO route it probes; none may
        raise or fall through to an unusable answer."""
        routes = get_routes_for_data_source("SEPTA_METRO")
        assert routes, "topology defines no SEPTA_METRO routes"
        for route in routes:
            verdict = expects_real_time_departures("SEPTA_METRO", route.line_codes)
            assert isinstance(verdict, bool)
            expected = bool(route.line_codes - SEPTA_METRO_SCHEDULE_ONLY_LINE_CODES)
            assert verdict is expected, f"{route.id} classified inconsistently"
