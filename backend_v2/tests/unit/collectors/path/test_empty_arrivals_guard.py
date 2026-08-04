"""Tests for the PATH empty-arrivals guard in ``PathCollector.collect``.

Issue #1746. ``RidePathClient.get_all_arrivals`` converts an HTTP 200 with an
empty body into ``[]`` rather than raising. Before the guard, ``collect()``
short-circuited only on an *exception*, so an empty-but-successful response ran
the full update phase against zero arrivals: nothing matched any journey, so
every in-flight journey took a strike, and three such cycles expired the entire
PATH fleet (``path_journey_expired_no_arrivals``). Expired journeys are filtered
out of ``/api/v2/trains/departures``.

These tests drive the real ``_update_journeys`` strike path against real journey
rows. The only thing faked is the HTTP boundary (``get_all_arrivals``), which is
the upstream API itself — the collector, the assignment logic and the database
are all genuine, because the defect lives in the interaction between them.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

# Journeys are only struck once their origin departure has passed — a train that
# has not left yet legitimately matches nothing. Every journey below therefore
# departed its origin in the past; otherwise these tests would pass for the
# wrong reason.
DEPARTED_MINUTES_AGO = 10

# Remaining stops must stay in the *future*. A stop whose scheduled time is
# more than the grace period in the past is inferred as departed, and once the
# terminal stop is departed the journey is marked complete and drops out of
# _update_journeys' candidate query — so a journey built entirely in the past
# can only ever take one strike, no matter how many cycles run.
NWK_WTC_STOPS = {"PGR": 3, "PEX": 6}
JSQ_33_STOPS = {"PCH": 8, "P14": 11}


async def _make_journey(
    session: AsyncSession,
    *,
    train_id: str,
    line_code: str,
    line_color: str,
    origin_station_code: str,
    destination: str,
    terminal_station_code: str,
    stop_minutes_from_now: dict[str, int],
    api_error_count: int = 0,
) -> TrainJourney:
    """Insert a mid-journey PATH train: origin departed, stops still ahead.

    Args:
        session: Test database session
        train_id: Unique train identifier
        line_code: PATH line code
        line_color: Line color, matched against arrival colors
        origin_station_code: Station the train started from
        destination: Headsign, matched against arrival headsigns
        terminal_station_code: Terminal station for the journey
        stop_minutes_from_now: Station code -> minutes until scheduled arrival
        api_error_count: Starting strike count

    Returns:
        The persisted journey
    """
    now = now_et()
    today = now.date()

    journey = TrainJourney(
        train_id=train_id,
        journey_date=today,
        line_code=line_code,
        line_name=line_code,
        line_color=line_color,
        destination=destination,
        origin_station_code=origin_station_code,
        terminal_station_code=terminal_station_code,
        data_source="PATH",
        observation_type="OBSERVED",
        scheduled_departure=now - timedelta(minutes=DEPARTED_MINUTES_AGO),
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
        api_error_count=api_error_count,
    )
    session.add(journey)
    await session.flush()

    for sequence, (station_code, minutes) in enumerate(
        stop_minutes_from_now.items(), start=1
    ):
        session.add(
            JourneyStop(
                journey_id=journey.id,
                journey_date=today,
                station_code=station_code,
                station_name=station_code,
                stop_sequence=sequence,
                scheduled_arrival=now + timedelta(minutes=minutes),
                scheduled_departure=now + timedelta(minutes=minutes),
            )
        )

    await session.flush()
    return journey


async def _make_wtc_journey(
    session: AsyncSession, *, train_id: str, api_error_count: int = 0
) -> TrainJourney:
    """Insert a Newark -> World Trade Center journey.

    Args:
        session: Test database session
        train_id: Unique train identifier
        api_error_count: Starting strike count

    Returns:
        The persisted journey
    """
    return await _make_journey(
        session,
        train_id=train_id,
        line_code="NWK-WTC",
        line_color="#D93A30",
        origin_station_code="PNK",
        destination="World Trade Center",
        terminal_station_code="PWC",
        stop_minutes_from_now=NWK_WTC_STOPS,
        api_error_count=api_error_count,
    )


async def _make_33rd_journey(
    session: AsyncSession, *, train_id: str, api_error_count: int = 0
) -> TrainJourney:
    """Insert a Journal Square -> 33rd Street journey.

    Args:
        session: Test database session
        train_id: Unique train identifier
        api_error_count: Starting strike count

    Returns:
        The persisted journey
    """
    return await _make_journey(
        session,
        train_id=train_id,
        line_code="JSQ-33",
        line_color="#FF9900",
        origin_station_code="PJS",
        destination="33rd Street",
        terminal_station_code="P33",
        stop_minutes_from_now=JSQ_33_STOPS,
        api_error_count=api_error_count,
    )


def _wtc_feed() -> list[PathArrival]:
    """Build a populated feed covering the WTC run only.

    Returns:
        Arrivals matching the stops of a WTC-bound journey
    """
    return [
        _arrival(station_code, "World Trade Center", minutes)
        for station_code, minutes in NWK_WTC_STOPS.items()
    ]


def _arrival(station_code: str, headsign: str, minutes_away: int) -> PathArrival:
    """Build a RidePATH arrival prediction.

    Args:
        station_code: Internal PATH station code
        headsign: Destination headsign as RidePATH reports it
        minutes_away: Countdown in whole minutes, as RidePATH reports it

    Returns:
        A single arrival prediction
    """
    now = now_et()
    return PathArrival(
        station_code=station_code,
        headsign=headsign,
        direction="ToNY",
        minutes_away=minutes_away,
        arrival_time=now + timedelta(minutes=minutes_away),
        line_color="D93A30",
        last_updated=now,
    )


def _collector_returning(arrivals_per_cycle: list[list[PathArrival]]) -> PathCollector:
    """Build a collector whose upstream API returns the given cycles in order.

    Args:
        arrivals_per_cycle: One arrival list per ``collect()`` call

    Returns:
        A collector wired to a fake RidePATH client
    """
    client = AsyncMock()
    client.close = AsyncMock()
    client.get_all_arrivals = AsyncMock(side_effect=arrivals_per_cycle)
    return PathCollector(client=client)


class TestEmptyArrivalsGuard:
    """An empty-but-successful RidePATH response must be a no-op cycle."""

    @pytest.mark.asyncio
    async def test_empty_arrivals_do_not_strike_any_journey(
        self, db_session: AsyncSession
    ):
        """A single empty response leaves every strike counter untouched.

        This is the case that mattered most in production: a journey already
        sitting at 2 strikes for legitimate reasons was expired outright by one
        empty body, without ever reaching three genuine no-show cycles.
        """
        fresh = await _make_wtc_journey(db_session, train_id="PATH_PNK_wtc_fresh")
        nearly_expired = await _make_33rd_journey(
            db_session, train_id="PATH_PJS_33s_nearly_expired", api_error_count=2
        )

        collector = _collector_returning([[]])
        result = await collector.collect(db_session)

        assert result["arrivals_fetched"] == 0, (
            "An empty cycle must report zero arrivals fetched, "
            f"got {result['arrivals_fetched']}"
        )
        assert result["updated"] == 0, (
            "An empty cycle must not update journeys, "
            f"got updated={result['updated']}"
        )

        await db_session.refresh(fresh)
        await db_session.refresh(nearly_expired)

        assert fresh.api_error_count == 0, (
            "A journey with no strikes must not gain one from an empty body, "
            f"got api_error_count={fresh.api_error_count}"
        )
        assert nearly_expired.api_error_count == 2, (
            "A journey at 2 strikes must stay at 2 after an empty body, "
            f"got api_error_count={nearly_expired.api_error_count}"
        )
        assert nearly_expired.is_expired is False, (
            "An empty body must never be the third strike that expires a "
            "journey that was one short of the threshold"
        )

    @pytest.mark.asyncio
    async def test_repeated_empty_arrivals_never_expire_the_fleet(
        self, db_session: AsyncSession
    ):
        """Four consecutive empty cycles expire nothing.

        Four is one more than the three-strike expiry threshold, so this fails
        loudly against the pre-fix behaviour: by cycle 3 every journey below
        would have had ``is_expired=True`` and dropped off the departure board.
        """
        journeys = [
            await _make_wtc_journey(db_session, train_id=f"PATH_PNK_wtc_{index}")
            for index in range(3)
        ]

        collector = _collector_returning([[], [], [], []])
        for cycle in range(4):
            result = await collector.collect(db_session)
            assert result["arrivals_fetched"] == 0, (
                f"Cycle {cycle + 1} should have fetched no arrivals, "
                f"got {result['arrivals_fetched']}"
            )

        for journey in journeys:
            await db_session.refresh(journey)
            assert journey.api_error_count == 0, (
                f"{journey.train_id} advanced to "
                f"api_error_count={journey.api_error_count} across 4 empty "
                "cycles; empty cycles carry no evidence about any train"
            )
            assert journey.is_expired is False, (
                f"{journey.train_id} was expired by empty cycles alone, which "
                "would remove it from /api/v2/trains/departures while running"
            )

        still_active = (
            await db_session.scalars(
                select(TrainJourney).where(
                    TrainJourney.data_source == "PATH",
                    TrainJourney.journey_date == now_et().date(),
                    TrainJourney.is_expired == False,  # noqa: E712
                )
            )
        ).all()
        assert len(still_active) == 3, (
            "All 3 journeys must remain servable after the empty cycles, "
            f"got {len(still_active)}"
        )

    @pytest.mark.asyncio
    async def test_empty_arrivals_skip_discovery_too(self, db_session: AsyncSession):
        """No arrivals means nothing to discover, so no journeys are created."""
        collector = _collector_returning([[]])
        result = await collector.collect(db_session)

        assert result["new_journeys"] == 0, (
            f"An empty cycle created {result['new_journeys']} journeys; "
            "there is nothing to discover from zero arrivals"
        )

        created = (
            await db_session.scalars(
                select(TrainJourney).where(TrainJourney.data_source == "PATH")
            )
        ).all()
        assert (
            created == []
        ), f"An empty cycle wrote {len(created)} PATH journeys to the database"

    @pytest.mark.asyncio
    async def test_empty_arrivals_return_the_documented_shape(
        self, db_session: AsyncSession
    ):
        """The skip result carries the same keys the scheduler reads.

        ``SchedulerService.run_path_collection`` logs
        ``arrivals_fetched``/``new_journeys``/``updated``/``completed`` off this
        dict, so a short-circuit that omitted them would silently log zeros for
        a different reason than it appears.
        """
        collector = _collector_returning([[]])
        result = await collector.collect(db_session)

        assert result == {
            "data_source": "PATH",
            "arrivals_fetched": 0,
            "new_journeys": 0,
            "updated": 0,
            "completed": 0,
        }, f"Unexpected skip result shape: {result}"


class TestGenuineNoShowStillStrikes:
    """The guard must not blunt the mechanism it is protecting."""

    @pytest.mark.asyncio
    async def test_train_missing_from_a_non_empty_feed_still_takes_its_strike(
        self, db_session: AsyncSession
    ):
        """A populated feed that omits one train strikes only that train.

        This is the case the strike counter exists for: we had data, and this
        particular train was not in it. Guarding on ``arrivals`` at the top of
        ``collect()`` must leave this path exactly as it was.
        """
        served = await _make_wtc_journey(db_session, train_id="PATH_PNK_wtc_served")
        omitted = await _make_33rd_journey(db_session, train_id="PATH_PJS_33s_omitted")

        # The feed covers the WTC run only; nothing on the 33rd Street run.
        collector = _collector_returning([_wtc_feed()])
        result = await collector.collect(db_session)

        assert result["arrivals_fetched"] == len(
            NWK_WTC_STOPS
        ), f"Expected the populated feed to be processed, got {result}"

        await db_session.refresh(served)
        await db_session.refresh(omitted)

        assert served.api_error_count == 0, (
            "A train present in the feed must have its strike count reset, "
            f"got api_error_count={served.api_error_count}"
        )
        assert omitted.api_error_count == 1, (
            "A train absent from a populated feed must take a strike, "
            f"got api_error_count={omitted.api_error_count}"
        )
        assert (
            omitted.is_expired is False
        ), "One strike is below the 3-strike threshold and must not expire"

    @pytest.mark.asyncio
    async def test_three_non_empty_cycles_omitting_a_train_expire_it(
        self, db_session: AsyncSession
    ):
        """Three genuine no-show cycles still reach expiry."""
        omitted = await _make_33rd_journey(db_session, train_id="PATH_PJS_33s_vanished")

        collector = _collector_returning([_wtc_feed() for _ in range(3)])

        for cycle in range(3):
            await collector.collect(db_session)
            await db_session.refresh(omitted)
            assert omitted.api_error_count == cycle + 1, (
                f"After {cycle + 1} populated cycles omitting this train, "
                f"expected {cycle + 1} strikes, got {omitted.api_error_count}"
            )

        assert omitted.is_expired is True, (
            "Three consecutive populated cycles without this train must expire "
            "it; the guard must not have disabled the strike path"
        )

    @pytest.mark.asyncio
    async def test_empty_cycles_between_real_ones_do_not_advance_the_count(
        self, db_session: AsyncSession
    ):
        """Empty cycles interleaved with real ones neither strike nor reset.

        The counter should measure "cycles in which we had data and still did
        not see this train". An empty cycle is not evidence either way, so it
        must leave the count exactly where the previous real cycle left it.
        """
        omitted = await _make_33rd_journey(
            db_session, train_id="PATH_PJS_33s_interleaved"
        )

        collector = _collector_returning(
            [_wtc_feed(), [], _wtc_feed(), [], _wtc_feed()]
        )

        expected_after_each = [1, 1, 2, 2, 3]
        for cycle, expected in enumerate(expected_after_each):
            await collector.collect(db_session)
            await db_session.refresh(omitted)
            assert omitted.api_error_count == expected, (
                f"After cycle {cycle + 1} expected api_error_count={expected}, "
                f"got {omitted.api_error_count}"
            )

        assert omitted.is_expired is True, (
            "Three genuine no-show cycles must still expire the journey even "
            "when empty cycles are interleaved between them"
        )
