"""Validate the NYCT trip_id origin-time encoding against a captured feed sample.

Issue #1704. `synthetic_origin_departure` guards origin inference purely on
time — it accepts an inferred origin only when the synthesized departure lands
in the past. Two different situations land there:

  * GTFS-RT dropped stops the train already passed (inference is correct), and
  * a short-turn trip first seen less than `ORIGIN_TRAVEL_BUFFER` before its
    real, mid-route first stop (inference invents a terminal the train never
    calls at, stamped in the past).

`nyct_trip_begins_at_first_stop` separates them using the origin departure
encoded in the NYCT real-time trip_id. That encoding is an MTA-internal
convention nothing else in the repo relies on, so gating on it unvalidated
could decline legitimate origins across the whole subway feed. These tests are
the validation: they run the production feed parser over raw protobuf captured
from all 8 feeds (see `tests/fixtures/subway_gtfs_rt/README.md`) and check the
encoding against the feeds' own stop times before anything gates on it.

Every trip is evaluated at its own feed's header timestamp, so the sample is
fully deterministic.
"""

import asyncio
import gzip
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.mta_common import (
    infer_subway_origin,
    nyct_trip_begins_at_first_stop,
    synthetic_origin_departure,
)
from trackrat.collectors.subway.client import (
    SubwayArrival,
    SubwayClient,
    parse_nyct_service_date,
    parse_nyct_trip_origin_time,
)
from trackrat.config.route_topology import get_route_by_line_code
from trackrat.config.stations import SUBWAY_ROUTES

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "subway_gtfs_rt"
EXPECTED_FEEDS = {"1234567S", "ACE", "BDFM", "G", "JZ", "L", "NQRW", "SIR"}


def _feed_key(path: Path) -> str:
    """Feed-group key from a fixture filename (`ACE.pb.gz` -> `ACE`)."""
    return path.name.removesuffix(".pb.gz")


class Trip:
    """One trip's feed-visible extent, as the collector sees it."""

    def __init__(self, feed: str, now: datetime, arrivals: list[SubwayArrival]):
        arrivals = sorted(arrivals, key=lambda a: a.arrival_time)
        self.feed = feed
        self.now = now
        self.trip_id = arrivals[0].trip_id
        self.route_id = arrivals[0].route_id
        self.first = arrivals[0]
        self.last = arrivals[-1]
        self.stop_count = len(arrivals)
        route_info = SUBWAY_ROUTES.get(self.route_id)
        self.line_code = route_info[0] if route_info else f"SUBWAY-{self.route_id}"
        self.route = get_route_by_line_code("SUBWAY", self.line_code)

    @property
    def origin_lead(self) -> timedelta | None:
        """How far the encoded origin precedes the first visible stop."""
        if self.first.trip_origin_time is None:
            return None
        return self.first.arrival_time - self.first.trip_origin_time

    @property
    def first_stop_is_topology_terminal(self) -> bool:
        return bool(self.route) and self.first.station_code in (
            self.route.stations[0],
            self.route.stations[-1],
        )

    @property
    def stops_from_nearest_terminal(self) -> int | None:
        """Position of the first visible stop, counted from the nearer end.

        0 means it is a terminal, 1 means one stop out. None means the stop is
        not on the route's topology at all (branches, interlined shuttles).
        """
        if not self.route or self.first.station_code not in self.route.stations:
            return None
        i = self.route.stations.index(self.first.station_code)
        return min(i, len(self.route.stations) - 1 - i)

    def __repr__(self) -> str:
        lead = self.origin_lead
        lead_text = (
            "no-encoding"
            if lead is None
            else f"lead={lead.total_seconds() / 60:.2f}min"
        )
        return (
            f"<{self.trip_id} feed={self.feed} route={self.route_id} "
            f"first={self.first.station_code} stops={self.stop_count} {lead_text}>"
        )


def _parse_fixture_feeds() -> list[Trip]:
    """Run the production feed parser over every captured feed.

    Uses `SubwayClient._fetch_feed` rather than a bespoke protobuf walk so the
    trip_origin_time under test is the one production actually produces —
    including the stop mapping and arrival/departure fallbacks that decide
    which stop counts as "first".
    """
    client = SubwayClient()
    trips: list[Trip] = []

    for path in sorted(FIXTURE_DIR.glob("*.pb.gz")):
        payload = gzip.decompress(path.read_bytes())
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(payload)
        now = datetime.fromtimestamp(feed.header.timestamp, tz=UTC)

        response = MagicMock()
        response.content = payload
        response.raise_for_status = MagicMock()
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=response)
        client.clear_cache()

        arrivals = asyncio.run(client._fetch_feed(_feed_key(path), "https://fixture"))

        by_trip: dict[str, list[SubwayArrival]] = defaultdict(list)
        for arrival in arrivals:
            by_trip[arrival.trip_id].append(arrival)
        trips.extend(
            Trip(_feed_key(path), now, group) for group in by_trip.values() if group
        )

    return trips


@pytest.fixture(scope="module")
def trips() -> list[Trip]:
    return _parse_fixture_feeds()


class TestFixtureCoverage:
    """The sample has to be broad enough for the validation to mean anything."""

    def test_all_eight_feeds_are_present(self):
        captured = {_feed_key(p) for p in FIXTURE_DIR.glob("*.pb.gz")}
        assert captured == EXPECTED_FEEDS, (
            "The encoding is gated for every subway route, so it must be "
            f"validated against every feed. Missing: {EXPECTED_FEEDS - captured}, "
            f"unexpected: {captured - EXPECTED_FEEDS}"
        )

    def test_sample_spans_many_routes_and_trips(self, trips):
        routes = {t.route_id for t in trips}
        assert len(trips) >= 400, f"Only {len(trips)} trips in the sample"
        assert len(routes) >= 20, f"Only {len(routes)} routes in the sample: {routes}"

    def test_every_trip_carries_a_decodable_origin_time(self, trips):
        undecoded = [t for t in trips if t.first.trip_origin_time is None]
        assert not undecoded, (
            "The gate falls back to the temporal guard alone when the id can't "
            f"be decoded; {len(undecoded)}/{len(trips)} failed to decode. "
            f"Examples: {undecoded[:5]}"
        )


class TestEncodingMatchesObservedOriginStops:
    """The core claim: when a trip's own origin stop is still in the feed, the
    trip_id decodes to that stop's time.

    The cohort is trips whose first visible stop is one of the route's topology
    terminals — for those, nothing upstream was dropped, so the first visible
    stop *is* the origin. If the encoding did not hold here, it could not be
    used to detect the opposite case.
    """

    TOLERANCE = timedelta(minutes=1)

    @staticmethod
    def _cohort(trips):
        return [
            t
            for t in trips
            if t.route
            and t.stop_count >= 2
            and t.first_stop_is_topology_terminal
            and t.origin_lead is not None
        ]

    def test_cohort_is_large_enough_to_be_evidence(self, trips):
        cohort = self._cohort(trips)
        assert len(cohort) >= 100, (
            f"Only {len(cohort)} trips still show their own origin stop — too "
            "few to validate the encoding against"
        )

    def test_encoded_origin_matches_the_visible_origin_stop(self, trips):
        cohort = self._cohort(trips)
        mismatched = [t for t in cohort if abs(t.origin_lead) > self.TOLERANCE]
        detail = "\n".join(
            f"    {t!r} first_stop={t.first.arrival_time.isoformat()} "
            f"encoded={t.first.trip_origin_time.isoformat()}"
            for t in mismatched
        )
        assert len(mismatched) / len(cohort) <= 0.05, (
            f"{len(mismatched)}/{len(cohort)} trips whose origin stop is still "
            "in the feed decoded to a different time — the trip_id encoding "
            f"does not hold and must not gate origin inference:\n{detail}"
        )

    def test_the_match_is_exact_not_merely_within_tolerance(self, trips):
        """A loose tolerance could pass by accident. The encoding is exact."""
        cohort = self._cohort(trips)
        exact = [t for t in cohort if t.origin_lead == timedelta(0)]
        assert len(exact) / len(cohort) >= 0.90, (
            f"Only {len(exact)}/{len(cohort)} matched to the second. The gate's "
            "1-minute tolerance is slack, not the signal — if the encoding is "
            "merely approximate, the separation it relies on is not real."
        )


class TestGateSeparatesShortTurnsFromDroppedOrigins:
    """What the gate does to the sample's actual inference candidates.

    A trip whose origin was genuinely dropped has just left a terminal, so its
    first visible stop is near one. A short-turn trip starts deep in the route.
    That is an independent signal from the trip_id, so it can be used to check
    the gate's verdicts rather than restate them.
    """

    @staticmethod
    def _candidates(trips):
        """Trips that reach origin inference at all (the collector's path)."""
        out = []
        for t in trips:
            if not t.route:
                continue
            candidate = infer_subway_origin(
                t.line_code, t.last.station_code, t.first.station_code
            )
            if candidate:
                out.append((t, candidate))
        return out

    def test_declined_trips_are_never_near_a_terminal(self, trips):
        """Nothing the gate declines looks like a train that just left one."""
        declined = [
            (t, c)
            for t, c in self._candidates(trips)
            if nyct_trip_begins_at_first_stop(
                t.first.trip_origin_time, t.first.arrival_time
            )
        ]
        assert declined, "The gate declined nothing — it cannot be doing any work"

        too_close = [
            (t, c, t.stops_from_nearest_terminal)
            for t, c in declined
            if t.stops_from_nearest_terminal is not None
            and t.stops_from_nearest_terminal < 2
        ]
        distances = Counter(t.stops_from_nearest_terminal for t, _ in declined)
        assert not too_close, (
            "The gate declined a trip whose first visible stop is adjacent to a "
            "topology terminal — that looks like a legitimately dropped origin, "
            f"so the gate is over-declining: {too_close}\n"
            f"    distance histogram: {dict(distances)}"
        )

    def test_accepted_trips_lead_their_first_stop_by_real_travel_time(self, trips):
        """The accepted population is the one inference exists for: the encoded
        origin sits meaningfully earlier than the first visible stop, which is
        what an already-travelled segment looks like."""
        accepted = [
            t
            for t, _ in self._candidates(trips)
            if not nyct_trip_begins_at_first_stop(
                t.first.trip_origin_time, t.first.arrival_time
            )
        ]
        assert accepted, "The gate accepted nothing — legitimate inference is broken"

        leads = sorted(t.origin_lead for t in accepted if t.origin_lead is not None)
        assert leads[0] > timedelta(minutes=1), (
            "An accepted trip led its first stop by only "
            f"{leads[0].total_seconds() / 60:.2f} minutes, which is inside the "
            "band the declined population occupies — the two are not separable"
        )

    def test_gate_changes_the_outcome_for_real_short_turn_trips(self, trips):
        """The #1704 population: the temporal guard accepts these and stamps a
        fabricated origin in the past. This is the fix doing its job, measured
        on captured data rather than a constructed scenario."""
        changed = []
        for t, candidate in self._candidates(trips):
            temporal_accepts = (
                synthetic_origin_departure(t.first.arrival_time, t.now) is not None
            )
            if temporal_accepts and nyct_trip_begins_at_first_stop(
                t.first.trip_origin_time, t.first.arrival_time
            ):
                changed.append((t, candidate))

        detail = "\n".join(
            f"    {t.trip_id} route={t.route_id} first={t.first.station_code} "
            f"({t.stops_from_nearest_terminal} stops from a terminal) would have "
            f"invented {c}, first stop "
            f"{(t.first.arrival_time - t.now).total_seconds() / 60:.1f} min out"
            for t, c in changed
        )
        assert changed, (
            "No trip in the sample changed verdict, so this fixture cannot "
            "demonstrate the fix — re-capture during a service change"
        )
        print(f"\n{len(changed)} trips no longer get a fabricated origin:\n{detail}")


class TestParseNyctTripOriginTime:
    """Unit-level behaviour of the decoder, including the shapes the sample
    contains and the malformed ones it cannot."""

    def test_decodes_hundredths_of_a_minute_past_midnight(self):
        result = parse_nyct_trip_origin_time("091150_1..N03R", "20260802")
        assert result is not None
        assert (result.hour, result.minute, result.second) == (15, 11, 30), (
            "091150 is 911.5 minutes past midnight = 15:11:30 ET; got "
            f"{result.isoformat()}"
        )
        assert result.date().isoformat() == "2026-08-02"

    def test_decodes_the_single_dot_shuttle_form(self):
        """Shuttles use a 2-character route, so the id reads `077400_GS.S04R`
        rather than `..`. Both appear in the captured sample."""
        result = parse_nyct_trip_origin_time("077400_GS.S04R", "20260802")
        assert result is not None
        assert (result.hour, result.minute) == (12, 54), result.isoformat()

    def test_after_midnight_service_day_stays_on_the_service_day(self):
        """NYCT counts past 1440 minutes for trips after midnight; the result
        must roll into the next calendar day, not wrap to the morning."""
        result = parse_nyct_trip_origin_time("148000_A..S55R", "20260802")
        assert result is not None
        assert result.date().isoformat() == "2026-08-03"
        assert (result.hour, result.minute) == (0, 40), result.isoformat()

    def test_negative_origin_time_precedes_the_service_day(self):
        result = parse_nyct_trip_origin_time("-00300_1..N03R", "20260802")
        assert result is not None
        assert result.date().isoformat() == "2026-08-01"
        assert (result.hour, result.minute) == (23, 57), result.isoformat()

    def test_missing_start_date_returns_none(self):
        assert parse_nyct_trip_origin_time("091150_1..N03R", None) is None

    def test_service_date_is_parsed_separately_from_overnight_origin(self):
        service_date = parse_nyct_service_date("20260802")
        origin = parse_nyct_trip_origin_time("148000_A..S55R", "20260802")

        assert service_date == date(2026, 8, 2)
        assert origin is not None
        assert origin.date() == date(2026, 8, 3)

    @pytest.mark.parametrize("value", [None, "", "not-a-date", "202681", "20261340"])
    def test_invalid_service_date_returns_none(self, value):
        assert parse_nyct_service_date(value) is None

    def test_malformed_start_date_returns_none(self):
        assert parse_nyct_trip_origin_time("091150_1..N03R", "not-a-date") is None

    def test_trip_id_without_the_encoding_returns_none(self):
        assert parse_nyct_trip_origin_time("SIR-FA2017-SI-Weekday", "20260802") is None
        assert parse_nyct_trip_origin_time("", "20260802") is None

    @pytest.mark.parametrize(
        "prefix",
        ["9" * 30, "-" + "9" * 30, "9" * 400],
        ids=["overflows-c-int", "negative-overflow", "overflows-float"],
    )
    def test_absurd_origin_value_returns_none_rather_than_raising(self, prefix):
        """An oversized numeric prefix overflows the timedelta/float conversion
        with OverflowError, which is not a ValueError. The only handler above
        this wraps an entire feed, so an escape would discard every other trip
        in that feed and serve stale data for it."""
        assert parse_nyct_trip_origin_time(f"{prefix}_1..N03R", "20260802") is None

    def test_result_is_eastern_time(self):
        result = parse_nyct_trip_origin_time("091150_1..N03R", "20260802")
        assert result is not None and result.tzinfo is not None
        assert result.utcoffset() == timedelta(hours=-4), (
            "August is EDT; a naive or UTC result would shift every comparison "
            "by four hours"
        )
