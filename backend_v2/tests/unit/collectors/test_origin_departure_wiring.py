"""A journey's ``actual_departure`` belongs to its origin stop — in every
GTFS-RT collector, not just SUBWAY (issue #1750).

GTFS-RT prunes stops a trip has already passed, so the earliest stop still in
the feed is not the trip's origin. Assigning that stop's time to
``journey.actual_departure`` pairs an *origin* ``scheduled_departure`` with a
*downstream* actual, and every consumer that subtracts the two reads the
running time already covered as departure delay. ``alert_evaluator.
_is_significantly_delayed`` subtracts exactly those two fields, so an on-time
train is pushed to subscribers as delayed — and because the whole in-flight
cohort drifts together, the system-wide "N% of trains delayed" alert fires too.

``mta_common.origin_actual_departure`` was written to fix this and was adopted
by SUBWAY only; the other seven collectors kept the raw substitution at three
sites each. ``test_mta_common.TestOriginActualDeparture`` already covers the
helper itself, so these tests cover the *wiring*: that each collector reaches
the helper, and that a trip first seen mid-route ends up with an unknown
departure rather than a fabricated one.
"""

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from trackrat.collectors.bart.client import BartArrival, BARTClient
from trackrat.collectors.bart.collector import BARTCollector
from trackrat.collectors.lirr.client import LirrArrival, LIRRClient
from trackrat.collectors.lirr.collector import LIRRCollector
from trackrat.collectors.mbta.client import MbtaArrival, MBTAClient
from trackrat.collectors.mbta.collector import MBTACollector
from trackrat.collectors.metra.client import MetraArrival, MetraClient
from trackrat.collectors.metra.collector import MetraCollector
from trackrat.collectors.mnr.client import MnrArrival, MNRClient
from trackrat.collectors.mnr.collector import MNRCollector
from trackrat.collectors.septa_metro.client import SeptaMetroArrival, SeptaMetroClient
from trackrat.collectors.septa_metro.collector import SeptaMetroCollector
from trackrat.collectors.septa_rr.client import (
    SeptaRailClient,
    SeptaRailStopUpdate,
    SeptaRailTripUpdate,
)
from trackrat.collectors.septa_rr.collector import SeptaRailCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.alert_evaluator import (
    DELAY_THRESHOLD_MINUTES,
    _is_significantly_delayed,
)
from trackrat.utils.time import now_et

# The seven collectors that share mta_common and carried the raw substitution,
# plus subway, which is the reference implementation the others now match.
GTFS_RT_COLLECTORS = [
    "lirr",
    "mnr",
    "mbta",
    "metra",
    "bart",
    "septa_metro",
    "septa_rr",
    "subway",
]

COLLECTORS_DIR = Path(__file__).resolve().parents[3] / "src" / "trackrat" / "collectors"


# =============================================================================
# SOURCE-LEVEL CONTRACT
# =============================================================================


class TestNoCollectorSubstitutesTheFirstVisibleStop:
    """The substitution must not reappear anywhere under ``collectors/``.

    This is the issue's own acceptance criterion, kept as a test because the
    defect's history is that it was fixed in one collector and left in seven.
    A behavioural test only guards the collector it names; this guards the ones
    nobody has written a test for yet, including any added later.
    """

    # `journey.actual_departure = <arrival>.arrival_time` in the update/JIT
    # branches, and `actual_departure=<arrival>.arrival_time` inside the
    # TrainJourney(...) constructor. The constructor form is the one the
    # original report's grep missed — a keyword argument, not an assignment.
    RAW_SUBSTITUTION = re.compile(
        r"actual_departure\s*=\s*"
        r"(first_arrival|first_stop|arrivals\[0\]|best_trip\[0\])\s*\.\s*arrival_time"
    )
    # The inlined `min(...)` form used by septa_rr and septa_metro.
    RAW_MIN_SUBSTITUTION = re.compile(
        r"journey\.actual_departure\s*=\s*min\(", re.MULTILINE
    )

    @pytest.mark.parametrize("collector_name", GTFS_RT_COLLECTORS)
    def test_no_raw_first_visible_arrival_substitution(self, collector_name):
        source = (COLLECTORS_DIR / collector_name / "collector.py").read_text()

        offenders = [
            line.strip()
            for line in source.splitlines()
            if self.RAW_SUBSTITUTION.search(line)
        ]
        assert not offenders, (
            f"{collector_name}/collector.py assigns the first feed-visible "
            "stop to actual_departure. GTFS-RT prunes passed stops, so that "
            "stop is not the origin and the value reads as departure delay. "
            f"Use origin_actual_departure(stops) instead. Offending: {offenders}"
        )

    @pytest.mark.parametrize("collector_name", GTFS_RT_COLLECTORS)
    def test_no_inlined_min_substitution(self, collector_name):
        source = (COLLECTORS_DIR / collector_name / "collector.py").read_text()

        assert not self.RAW_MIN_SUBSTITUTION.search(source), (
            f"{collector_name}/collector.py derives actual_departure from a "
            "min() over feed arrivals. The earliest *visible* stop is not the "
            "origin — use origin_actual_departure(stops), which reads the "
            "min-stop_sequence stop and returns None for a backfilled origin."
        )

    @pytest.mark.parametrize("collector_name", GTFS_RT_COLLECTORS)
    def test_collector_uses_the_shared_helper(self, collector_name):
        source = (COLLECTORS_DIR / collector_name / "collector.py").read_text()

        assert "origin_actual_departure" in source, (
            f"{collector_name}/collector.py does not use "
            "origin_actual_departure; it cannot be honouring the origin rule."
        )
        # Discovery, the update branch, and the JIT refresh. Missing one means
        # the next collection cycle reinstates whatever the other two fixed.
        call_count = source.count("journey.actual_departure = origin_actual_departure")
        assert call_count == 3, (
            f"{collector_name}/collector.py sets actual_departure from the "
            f"origin at {call_count} site(s); expected 3 (discovery, update, "
            "JIT). A branch left out silently restores the fabricated delay."
        )

    @pytest.mark.parametrize("collector_name", GTFS_RT_COLLECTORS)
    def test_constructor_defers_the_departure(self, collector_name):
        """The `TrainJourney(...)` constructor must not stamp a departure.

        Discovery creates the row before the stops exist, so there is nothing
        to read an origin from yet. Every collector passes None and sets the
        real value once the stops are built.
        """
        source = (COLLECTORS_DIR / collector_name / "collector.py").read_text()

        assert "actual_departure=None," in source, (
            f"{collector_name}/collector.py does not pass "
            "actual_departure=None into TrainJourney(...). If it passes a "
            "feed arrival there, the row is created with a fabricated "
            "departure that no later branch necessarily overwrites."
        )


# =============================================================================
# BEHAVIOURAL HARNESS
# =============================================================================


def _mid_route_schedule(now: datetime) -> dict:
    """A three-stop trip whose origin the feed has already pruned.

    ORIGIN departed 20 minutes ago and is gone from the feed; the train is
    running on time to MID and TERM. This is what every collector sees on
    restart for every train currently in flight, so it is the common case.
    """
    return {
        "origin_scheduled": now - timedelta(minutes=20),
        "mid": now + timedelta(minutes=5),
        "terminal": now + timedelta(minutes=20),
    }


def _static_stops(times: dict) -> list[dict]:
    return [
        {
            "station_code": "ORIGIN",
            "stop_sequence": 1,
            "arrival_time": times["origin_scheduled"],
            "departure_time": times["origin_scheduled"],
        },
        {
            "station_code": "MID",
            "stop_sequence": 2,
            "arrival_time": times["mid"],
            "departure_time": times["mid"],
        },
        {
            "station_code": "TERM",
            "stop_sequence": 3,
            "arrival_time": times["terminal"],
            "departure_time": times["terminal"],
        },
    ]


def _arrival(arrival_cls, station_code: str, when: datetime, **extra):
    """Build one RT arrival, tolerating the small per-provider field diffs."""
    fields = {
        "station_code": station_code,
        "gtfs_stop_id": f"gtfs-{station_code}",
        "trip_id": "TRIP-1",
        "route_id": "1",
        "direction_id": 0,
        "headsign": "Terminal",
        "arrival_time": when,
        "departure_time": when + timedelta(seconds=30),
        "delay_seconds": 0,
        "track": None,
    }
    fields.update(extra)
    # BartArrival has no headsign; SeptaRailArrival has neither headsign nor
    # gtfs_stop_id. Drop whatever this provider's model does not declare.
    declared = set(arrival_cls.model_fields)
    return arrival_cls(**{k: v for k, v in fields.items() if k in declared})


def _visible_arrivals(arrival_cls, times: dict) -> list:
    """Only MID and TERM — ORIGIN has been pruned from the feed."""
    return [
        _arrival(arrival_cls, "MID", times["mid"]),
        _arrival(arrival_cls, "TERM", times["terminal"]),
    ]


def _mock_session(existing_journey=None):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_journey
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _added_stops(session) -> list[JourneyStop]:
    return [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], JourneyStop)
    ]


def _make_lirr():
    return LIRRCollector(client=AsyncMock(spec=LIRRClient))


def _make_mnr():
    return MNRCollector(client=AsyncMock(spec=MNRClient))


def _make_mbta():
    return MBTACollector(client=AsyncMock(spec=MBTAClient))


def _make_metra():
    return MetraCollector(client=AsyncMock(spec=MetraClient))


def _make_bart():
    return BARTCollector(client=AsyncMock(spec=BARTClient))


def _make_septa_metro():
    return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))


def _make_septa_rr():
    return SeptaRailCollector(client=AsyncMock(spec=SeptaRailClient))


async def _run_standard(collector, session, arrival_cls, times):
    """The six collectors whose _process_trip fetches its own static stops."""
    collector._gtfs_service = MagicMock()
    collector._gtfs_service.get_static_stop_times = AsyncMock(
        return_value=_static_stops(times)
    )
    return await collector._process_trip(
        session, "TRIP-1", _visible_arrivals(arrival_cls, times)
    )


async def _run_septa_metro(collector, session, arrival_cls, times):
    collector._gtfs_service = MagicMock()
    collector._gtfs_service.get_static_stop_times = AsyncMock(
        return_value=_static_stops(times)
    )
    return await collector._process_trip(
        session,
        "TRIP-1",
        _visible_arrivals(arrival_cls, times),
        times["mid"].date(),
    )


async def _run_septa_rr(collector, session, arrival_cls, times):
    """SEPTA RR is delay-based: the caller resolves the static schedule and
    ``resolve_arrivals`` reconstructs absolute times from per-stop delays.
    Delay 0 on the two visible stops = the on-time train described above.
    """
    trip = SeptaRailTripUpdate(
        trip_id="CHW8312_20260718_SID189411",
        route_id="CHW",
        direction_id=0,
        vehicle_label="805",
        stop_updates=[
            SeptaRailStopUpdate(stop_sequence=2, arrival_delay=0, departure_delay=0),
        ],
    )
    return await collector._process_trip(
        session, trip, times["mid"].date(), _static_stops(times)
    )


# (id, collector factory, arrival class, runner, delay_first)
COLLECTOR_CASES = [
    ("lirr", _make_lirr, LirrArrival, _run_standard, True),
    ("mnr", _make_mnr, MnrArrival, _run_standard, True),
    ("mbta", _make_mbta, MbtaArrival, _run_standard, True),
    ("metra", _make_metra, MetraArrival, _run_standard, True),
    ("septa_rr", _make_septa_rr, None, _run_septa_rr, True),
    ("bart", _make_bart, BartArrival, _run_standard, False),
    ("septa_metro", _make_septa_metro, SeptaMetroArrival, _run_septa_metro, False),
]

CASE_IDS = [case[0] for case in COLLECTOR_CASES]


class TestMidRouteDiscoveryLeavesTheDepartureUnknown:
    """Discovery: the row must be created with no departure, not a fake one."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,make_collector,arrival_cls,runner,delay_first",
        COLLECTOR_CASES,
        ids=CASE_IDS,
    )
    async def test_backfilled_origin_yields_no_actual_departure(
        self, name, make_collector, arrival_cls, runner, delay_first
    ):
        now = now_et()
        times = _mid_route_schedule(now)
        collector = make_collector()
        session = _mock_session(existing_journey=None)

        result, journey = await runner(collector, session, arrival_cls, times)

        assert (
            result == "discovered"
        ), f"{name}: expected the trip to be discovered, got {result!r}"

        stops = _added_stops(session)
        origin = min(stops, key=lambda s: s.stop_sequence)
        assert origin.station_code == "ORIGIN", (
            f"{name}: static backfill should restore the pruned origin; "
            f"got stops {[s.station_code for s in stops]}"
        )
        assert origin.actual_arrival is None and origin.actual_departure is None, (
            f"{name}: the origin is a static backfill — the feed never "
            "observed it, so it must carry no actual times"
        )

        # The scheduled side is the restored origin's. That pairing is exactly
        # what makes substituting a downstream actual read as delay.
        assert journey.scheduled_departure == times["origin_scheduled"]

        fabricated = (times["mid"] - times["origin_scheduled"]).total_seconds() / 60
        assert journey.actual_departure is None, (
            f"{name}: ORIGIN was never observed, so the departure is unknown. "
            "Using the first visible stop instead would report this on-time "
            f"train as {fabricated:.0f} minutes late."
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,make_collector,arrival_cls,runner,delay_first",
        COLLECTOR_CASES,
        ids=CASE_IDS,
    )
    async def test_update_cycle_keeps_the_departure_unknown(
        self, name, make_collector, arrival_cls, runner, delay_first
    ):
        """Fixing discovery alone would last one collection cycle.

        ``_process_trip`` re-runs against the existing row every 4 minutes and
        the update branch set the same first-visible value — so the fabricated
        delay would be reinstated on the next tick, and would then grow as the
        feed window advanced further past the origin.
        """
        now = now_et()
        times = _mid_route_schedule(now)
        collector = make_collector()

        discovery_session = _mock_session(existing_journey=None)
        _, journey = await runner(collector, discovery_session, arrival_cls, times)
        journey.stops = _added_stops(discovery_session)

        update_session = _mock_session(existing_journey=journey)
        result, updated = await runner(collector, update_session, arrival_cls, times)

        assert (
            result == "updated"
        ), f"{name}: expected the second pass to update, got {result!r}"
        assert updated.actual_departure is None, (
            f"{name}: the update branch must derive the departure from the "
            "origin stop too, or the next collection cycle reinstates the "
            "fabricated delay"
        )


class TestObservedOriginStillRecordsItsDeparture:
    """The rule must not simply blank the field.

    A collector that always returned None would pass every test above while
    losing a real signal. When the feed *does* include the origin, the journey
    must record when it actually left.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,make_collector,arrival_cls,runner,delay_first",
        [c for c in COLLECTOR_CASES if c[0] != "septa_rr"],
        ids=[c[0] for c in COLLECTOR_CASES if c[0] != "septa_rr"],
    )
    async def test_origin_in_feed_sets_actual_departure(
        self, name, make_collector, arrival_cls, runner, delay_first
    ):
        now = now_et()
        times = _mid_route_schedule(now)
        collector = make_collector()
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(
            return_value=_static_stops(times)
        )
        session = _mock_session(existing_journey=None)

        origin_departure = times["origin_scheduled"] + timedelta(seconds=30)
        arrivals = [
            _arrival(arrival_cls, "ORIGIN", times["origin_scheduled"]),
            _arrival(arrival_cls, "MID", times["mid"]),
            _arrival(arrival_cls, "TERM", times["terminal"]),
        ]

        if name == "septa_metro":
            _, journey = await collector._process_trip(
                session, "TRIP-1", arrivals, times["mid"].date()
            )
        else:
            _, journey = await collector._process_trip(session, "TRIP-1", arrivals)

        assert journey.actual_departure == origin_departure, (
            f"{name}: the origin was observed, so its own actual_departure "
            "is the journey's departure and must be recorded"
        )


# =============================================================================
# THE CONSUMER THIS PROTECTS
# =============================================================================


class TestAlertEvaluatorIsNotFooledByAMidRouteDiscovery:
    """``_is_significantly_delayed`` is why this bug reached users."""

    def _journey(self, scheduled_departure, actual_departure):
        return TrainJourney(
            train_id="T1",
            journey_date=date(2026, 8, 8),
            data_source="LIRR",
            observation_type="OBSERVED",
            line_code="1",
            line_name="Babylon",
            destination="Babylon",
            origin_station_code="ORIGIN",
            terminal_station_code="TERM",
            scheduled_departure=scheduled_departure,
            actual_departure=actual_departure,
            has_complete_journey=True,
        )

    def test_unknown_departure_is_not_a_delay(self):
        """The fixed shape: an on-time train discovered mid-route."""
        now = now_et()
        journey = self._journey(
            scheduled_departure=now - timedelta(minutes=25),
            actual_departure=None,
        )

        assert _is_significantly_delayed(journey) is False, (
            "A journey whose origin was never observed has an unknown "
            "departure. It must not be reported as delayed."
        )

    def test_substituted_mid_route_arrival_would_have_alerted(self):
        """The broken shape, kept as the control.

        This asserts the *old* value really did trip the threshold — without
        it, the test above would pass just as happily against a threshold that
        no realistic delay could ever reach, and would prove nothing.
        """
        now = now_et()
        scheduled = now - timedelta(minutes=25)
        # What the raw substitution produced: the first stop still in the feed.
        substituted = scheduled + timedelta(minutes=DELAY_THRESHOLD_MINUTES + 10)
        journey = self._journey(
            scheduled_departure=scheduled, actual_departure=substituted
        )

        assert _is_significantly_delayed(journey) is True, (
            "Sanity check on the threshold: substituting a stop "
            f"{DELAY_THRESHOLD_MINUTES + 10} minutes into the run is what "
            "pushed a delay alert for an on-time train."
        )

    def test_genuinely_late_origin_still_alerts(self):
        """The rule must not suppress real delays.

        When the origin *was* observed and the train really did leave late,
        the alert must still fire — otherwise the fix trades false positives
        for false negatives.
        """
        now = now_et()
        scheduled = now - timedelta(minutes=40)
        journey = self._journey(
            scheduled_departure=scheduled,
            actual_departure=scheduled + timedelta(minutes=DELAY_THRESHOLD_MINUTES + 5),
        )

        assert _is_significantly_delayed(journey) is True, (
            "A train observed leaving its origin late is genuinely delayed "
            "and must still alert."
        )
