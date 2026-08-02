"""Integration tests for issue #1701: PATH departed stops carrying future stamps.

Runs the real PATH discovery path against a live PostgreSQL session, then reads
the persisted rows back through the same ``hide_departed`` SQL the departures
board uses.

The invariant under test:

    No PATH journey stop may be persisted with ``has_departed_station=True``
    and an effective departure — ``coalesce(actual_departure,
    scheduled_departure)`` — in the future.

That coalesce is not incidental: it is literally the second branch of
``DepartureService``'s ``hide_departed`` filter, kept so a train dwelling at its
origin terminal stays boardable (issue #1422). Any row matching it while flagged
departed is simultaneously "already passed" and "boardable", which corrupts the
train's reported position (``_derive_at_station_code`` skips departed stops, so
the app reports the wrong next station) and freezes a fabricated future time
into ``actual_departure``, which ``_recompute_stop_times`` then refuses to
refine because the stop looks departed.

Scope note: this does not claim mid-route discovery produces a *correct* origin
schedule. Back-computing from a RidePATH prediction can still put a journey's
scheduled origin departure in the future, and such a row is served either way —
as an undeparted upcoming departure now, instead of a departed-but-upcoming one
before. What changes here is that the collector no longer asserts the train
passed a station it has not reached.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import normalize_to_et, now_et

# NWK-WTC route: PNK(1) -> PHR(2) -> PJS(3) -> PGR(4) -> PEX(5) -> PWC(6)
# GTFS default segment time is 3 minutes, so PNK -> PGR is 9 minutes.
NWK_WTC_COLOR = "D93A30"


def _grove_street_arrival(minutes_away: int) -> PathArrival:
    """A RidePATH prediction for a WTC-bound train approaching Grove Street."""
    return PathArrival(
        station_code="PGR",
        headsign="World Trade Center",
        direction="ToNY",
        minutes_away=minutes_away,
        arrival_time=now_et() + timedelta(minutes=minutes_away),
        line_color=NWK_WTC_COLOR,
        last_updated=None,
    )


async def _persisted_stops(
    db_session: AsyncSession, train_id: str
) -> dict[str, JourneyStop]:
    result = await db_session.scalars(
        select(JourneyStop)
        .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
        .where(TrainJourney.train_id == train_id)
    )
    return {stop.station_code: stop for stop in result.all()}


async def _discover(db_session: AsyncSession, arrival: PathArrival) -> TrainJourney:
    collector = PathCollector()
    created = await collector._process_arrival_for_discovery(db_session, arrival, {})
    assert created, "discovery should have created a journey for this arrival"
    await db_session.commit()

    journey = await db_session.scalar(
        select(TrainJourney).where(TrainJourney.data_source == "PATH")
    )
    assert journey is not None
    return journey


@pytest.mark.asyncio
class TestPathDepartedStopsNeverFuture:
    """The persisted invariant, exercised through real discovery + real SQL."""

    async def test_mid_route_discovery_persists_no_future_departed_stop(
        self, db_session: AsyncSession
    ):
        """The #1701 reproduction, end to end.

        A WTC-bound train is predicted to reach Grove Street in 5 minutes.
        Working backwards over 9 minutes of cumulative segment time puts the
        origin departure at now-4, so PNK (now-4) and PHR (now-1) are genuinely
        passed — but PJS lands at now+2, two minutes before the train gets
        there. Marking PJS departed wrote a future ``actual_departure``, the one
        shape ``hide_departed``'s upcoming branch resurrects.
        """
        journey = await _discover(db_session, _grove_street_arrival(minutes_away=5))
        stops = await _persisted_stops(db_session, journey.train_id)
        now = now_et()

        assert set(stops) == {"PNK", "PHR", "PJS", "PGR", "PEX", "PWC"}

        violations = [
            (
                code,
                stop.actual_departure or stop.scheduled_departure,
            )
            for code, stop in stops.items()
            if stop.has_departed_station
            and (stop.actual_departure or stop.scheduled_departure) is not None
            and normalize_to_et(stop.actual_departure or stop.scheduled_departure)
            > normalize_to_et(now)
        ]
        assert not violations, (
            "stops flagged departed with a future effective departure survive "
            f"hide_departed's upcoming branch and read as boardable: {violations}"
        )

        # The genuinely-passed run-up is still backfilled — the guard must not
        # cost us the legitimate inference.
        assert stops["PNK"].has_departed_station is True
        assert stops["PHR"].has_departed_station is True
        assert stops["PNK"].departure_source == "inferred_from_discovery"

        # PJS is two minutes out; it stays an ordinary upcoming prediction.
        assert stops["PJS"].has_departed_station is False
        assert stops["PJS"].actual_departure is None
        assert stops["PJS"].scheduled_arrival is not None

        # Nothing at or beyond the discovery station is ever departed.
        for code in ("PGR", "PEX", "PWC"):
            assert stops[code].has_departed_station is False

    async def test_upcoming_stop_is_served_as_undeparted_not_via_the_1422_branch(
        self, db_session: AsyncSession
    ):
        """PJS is still boardable — but because it hasn't departed, truthfully.

        Before the fix this row reached the board through the #1422 escape hatch
        (flagged departed, kept because its time was upcoming). The rider sees a
        Journal Square departure either way; what changes is that the train's
        position is no longer reported one station further along than it is.
        """
        journey = await _discover(db_session, _grove_street_arrival(minutes_away=5))
        now = now_et()

        service = DepartureService()
        response = await service.get_departures(
            db=db_session,
            from_station="PJS",
            to_station="PWC",
            time_from=now,
            time_to=now + timedelta(hours=3),
            hide_departed=True,
            data_sources=["PATH"],
        )

        train_ids = {d.train_id for d in response.departures}
        assert journey.train_id in train_ids, (
            "a train two minutes from Journal Square must still be boardable there. "
            f"Returned: {train_ids}"
        )

        stops = await _persisted_stops(db_session, journey.train_id)
        assert stops["PJS"].has_departed_station is False, (
            "the row must be served because it has not departed, not because "
            "hide_departed's upcoming branch rescued a departed-flagged stop"
        )

    async def test_train_at_discovery_station_hides_its_passed_origin(
        self, db_session: AsyncSession
    ):
        """The guard must not over-decline: a real run-up still gets hidden.

        With the train AT Grove Street, the whole back-computed run-up is in the
        past. Newark is genuinely 9 minutes behind it, so a Newark board with
        ``hide_departed`` must not advertise this train.
        """
        journey = await _discover(db_session, _grove_street_arrival(minutes_away=0))
        stops = await _persisted_stops(db_session, journey.train_id)
        now = now_et()

        for code in ("PNK", "PHR", "PJS"):
            assert (
                stops[code].has_departed_station is True
            ), f"{code} is behind the train and must be marked departed"
            assert normalize_to_et(stops[code].actual_departure) < normalize_to_et(now)

        service = DepartureService()
        response = await service.get_departures(
            db=db_session,
            from_station="PNK",
            to_station="PWC",
            time_from=now - timedelta(hours=1),
            time_to=now + timedelta(hours=3),
            hide_departed=True,
            data_sources=["PATH"],
        )

        train_ids = {d.train_id for d in response.departures}
        assert journey.train_id not in train_ids, (
            "a train that left Newark 9 minutes ago must not be advertised as a "
            f"Newark departure. Returned: {train_ids}"
        )
