"""Integration tests for issue #1723: PATH short-headway train matching.

Runs the real PATH collector against a live PostgreSQL session.

The defect: both matching passes resolved each RidePATH arrival independently
against a +/-5 minute window. On JSQ-33 (2-4 minute headways) consecutive trains
share line, origin and destination, so every train in a run fell inside that
window of the one journey already on record. Discovery kept "finding" the same
journey and creating nothing, quantizing the line to roughly one journey per
five minutes, and the update pass wrote a single arrival onto the stops of every
journey it fitted.

The window itself cannot shrink: RidePATH reports whole-minute countdowns and
the origin departure is back-calculated from GTFS segment times, so the same
train seen at two stations lands minutes apart. What changed is that both passes
now claim their pairs one-to-one, closest first.

JSQ-33 (route 861, orange #ff9900) is the line under test:
    PJS -> PGR -> PNP -> PCH -> P9S -> P14 -> P23 -> P33
With no GTFS segment times loaded every hop is DEFAULT_MINUTES_PER_SEGMENT
(3 minutes), so PJS -> PGR is 3 minutes and PJS -> PNP is 6.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import normalize_to_et, now_et

JSQ_33_COLOR = "FF9900"


def _arrival(station_code: str, minutes_away: int, base: datetime) -> PathArrival:
    """A RidePATH prediction for a 33rd Street-bound JSQ-33 train."""
    return PathArrival(
        station_code=station_code,
        headsign="33rd Street",
        direction="ToNY",
        minutes_away=minutes_away,
        arrival_time=base + timedelta(minutes=minutes_away),
        line_color=JSQ_33_COLOR,
        last_updated=None,
    )


async def _path_journeys(db_session: AsyncSession) -> list[TrainJourney]:
    """Every PATH journey on record, earliest scheduled departure first."""
    result = await db_session.scalars(
        select(TrainJourney)
        .where(TrainJourney.data_source == "PATH")
        .order_by(TrainJourney.scheduled_departure)
    )
    return list(result.all())


async def _stop_at(
    db_session: AsyncSession, journey: TrainJourney, station_code: str
) -> JourneyStop:
    """The journey's stop at a station."""
    stop = await db_session.scalar(
        select(JourneyStop).where(
            JourneyStop.journey_id == journey.id,
            JourneyStop.station_code == station_code,
        )
    )
    assert stop is not None, f"{journey.train_id} has no stop at {station_code}"
    return stop


@pytest.mark.asyncio
class TestDiscoveryDoesNotSwallowConsecutiveTrains:
    """Discovery: N distinct trains in one cycle must yield N journeys."""

    async def test_three_trains_inside_one_window_create_three_journeys(
        self, db_session: AsyncSession
    ):
        """Three JSQ-33 trains 1, 4 and 6 minutes out all sit inside +/-5 min.

        This is the reported symptom: RidePATH lists a train due in the next few
        minutes and TrackRat has no corresponding record, because the second and
        third trains were absorbed into the first one's journey.
        """
        base = now_et()
        arrivals = [_arrival("PJS", minutes, base) for minutes in (1, 4, 6)]

        collector = PathCollector()
        stats = await collector._discover_trains(db_session, arrivals, {})
        await db_session.commit()

        assert stats["new_journeys"] == 3, "each train needs its own journey"

        journeys = await _path_journeys(db_session)
        assert len(journeys) == 3
        assert len({journey.train_id for journey in journeys}) == 3

        # Journeys are minutes apart, in the order the trains were listed.
        departures = [
            normalize_to_et(journey.scheduled_departure) for journey in journeys
        ]
        offsets = [
            round((departure - normalize_to_et(base)).total_seconds() / 60)
            for departure in departures
        ]
        assert offsets == [1, 4, 6]

    async def test_same_train_seen_at_two_stations_creates_one_journey(
        self, db_session: AsyncSession
    ):
        """The case the wide window exists for must still collapse to one row.

        One train that departed PJS at ``base`` reaches PGR 3 minutes later and
        PNP 6 minutes later. Both sightings back-calculate to the same origin
        departure, so they are one train — not two.
        """
        base = now_et()
        arrivals = [_arrival("PGR", 3, base), _arrival("PNP", 6, base)]

        collector = PathCollector()
        stats = await collector._discover_trains(db_session, arrivals, {})
        await db_session.commit()

        assert stats["new_journeys"] == 1
        journeys = await _path_journeys(db_session)
        assert len(journeys) == 1
        assert journeys[0].origin_station_code == "PJS"

        # The sighting closest to the origin wins, so PGR (3 min of
        # back-calculation) supplies the journey rather than PNP (6 min).
        pgr_stop = await _stop_at(db_session, journeys[0], "PGR")
        assert pgr_stop.has_departed_station is not True

    async def test_mixed_sightings_resolve_to_the_right_train_count(
        self, db_session: AsyncSession
    ):
        """Two trains, one of them seen twice, must produce exactly two journeys.

        Train A departed PJS at ``base`` (seen at PGR and PNP); train B departs
        PJS 4 minutes later (seen at PJS). Every sighting is within the +/-5 min
        window of every other, so only one-to-one matching separates them.
        """
        base = now_et()
        arrivals = [
            _arrival("PGR", 3, base),  # train A, origin == base
            _arrival("PNP", 6, base),  # train A again, origin == base
            _arrival("PJS", 4, base),  # train B, origin == base + 4
        ]

        collector = PathCollector()
        stats = await collector._discover_trains(db_session, arrivals, {})
        await db_session.commit()

        assert stats["new_journeys"] == 2
        journeys = await _path_journeys(db_session)
        offsets = [
            round(
                (
                    normalize_to_et(journey.scheduled_departure) - normalize_to_et(base)
                ).total_seconds()
                / 60
            )
            for journey in journeys
        ]
        assert offsets == [0, 4]

    async def test_second_cycle_matches_existing_journeys_one_to_one(
        self, db_session: AsyncSession
    ):
        """A later cycle updates the run it already has instead of duplicating it.

        Each train has drifted 30 seconds since the first cycle, which keeps
        every sighting inside +/-5 min of every existing journey. Nearest-first
        claiming has to pair them up rather than let the earliest journey absorb
        the closest sighting of a later train.
        """
        base = now_et()
        collector = PathCollector()

        await collector._discover_trains(
            db_session, [_arrival("PJS", minutes, base) for minutes in (1, 4, 6)], {}
        )
        await db_session.commit()
        first_cycle = await _path_journeys(db_session)
        assert len(first_cycle) == 3

        drifted = base + timedelta(seconds=30)
        stats = await collector._discover_trains(
            db_session, [_arrival("PJS", minutes, drifted) for minutes in (1, 4, 6)], {}
        )
        await db_session.commit()

        assert stats["new_journeys"] == 0, "the same three trains, 30s later"
        assert [journey.train_id for journey in await _path_journeys(db_session)] == [
            journey.train_id for journey in first_cycle
        ]

    async def test_a_shared_delay_does_not_duplicate_the_second_train(
        self, db_session: AsyncSession
    ):
        """Both trains slipping keeps them both matched, not one duplicated.

        Journeys on record leave PJS at base and base+4; next cycle the same two
        trains are listed at base+3 and base+8. The single closest pair is
        base+3 to the base+4 journey, and taking it strands base+8 outside the
        window of the base journey — a duplicate for a train already tracked.
        """
        base = now_et()
        collector = PathCollector()

        await collector._discover_trains(
            db_session, [_arrival("PJS", minutes, base) for minutes in (0, 4)], {}
        )
        await db_session.commit()
        first_cycle = await _path_journeys(db_session)
        assert len(first_cycle) == 2

        stats = await collector._discover_trains(
            db_session, [_arrival("PJS", minutes, base) for minutes in (3, 8)], {}
        )
        await db_session.commit()

        assert stats["new_journeys"] == 0, "both trains were already on record"
        assert [journey.train_id for journey in await _path_journeys(db_session)] == [
            journey.train_id for journey in first_cycle
        ]


@pytest.mark.asyncio
class TestUpdatesDoNotShareOneArrivalBetweenTrains:
    """Updates: an arrival belongs to exactly one journey."""

    async def test_arrival_is_claimed_by_the_journey_it_belongs_to(
        self, db_session: AsyncSession
    ):
        """Two consecutive trains, one arrival, one winner.

        Train A left PJS at ``base`` and reaches PGR at base+3; train B left at
        base+4 and reaches PGR at base+7. Only B is still listed at PGR. Its
        arrival is 4 minutes from A's PGR stop — inside the window — so before
        the fix both journeys recorded it and A's position jumped to a train it
        was not.
        """
        base = now_et()
        collector = PathCollector()

        await collector._discover_trains(
            db_session,
            [_arrival("PJS", 0, base), _arrival("PJS", 4, base)],
            {},
        )
        await db_session.commit()

        train_a, train_b = await _path_journeys(db_session)

        await collector._update_journeys(db_session, [_arrival("PGR", 7, base)], {})
        await db_session.commit()

        a_stop = await _stop_at(db_session, train_a, "PGR")
        b_stop = await _stop_at(db_session, train_b, "PGR")

        assert b_stop.arrival_source == "api_observed"
        assert normalize_to_et(b_stop.actual_arrival) == normalize_to_et(
            base + timedelta(minutes=7)
        )
        assert (
            a_stop.arrival_source != "api_observed"
        ), "train A must not record train B's arrival"
