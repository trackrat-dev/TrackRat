"""A bare ``NJTransitAPIError`` must advance the freshness clock, at every site
that refreshes an NJT journey (issue #1827).

#1748 established the invariant: the periodic batch is selected with
``ORDER BY last_updated_at ASC LIMIT journey_update_batch_size``, so a journey
that returns from a refresh without stamping sorts first on every subsequent
tick and is re-selected forever. That fix covered ``NJTransitNullDataError``
and ``TrainNotFoundError``. It did not cover their **parent** class, which is
what NJT's client raises for any HTTP error, timeout, or non-JSON body — so
every transient upstream failure became permanent.

The cost is not hypothetical. NJ Transit sent a quota warning on 2026-09-20:
``getTrainStopList`` went from 6,836 calls/day to 85,663 (214% of the
40,000/day limit) over 2026-09-17..09-20, 64% of them errors, with no deploy in
that window. ``NJTransitAPIError`` was 172,616 of the 199,619 lifetime errors.

The three sites are *separate implementations* of the same refresh, so each
needs its own regression test — fixing one does not protect the others:

* ``JourneyCollector.collect_journey_details`` — async session, the shared
  write path.
* ``SchedulerService._collect_single_njt_journey_safe`` — synchronous session,
  what ``schedule_periodic_updates`` actually dispatches to.
* ``DepartureService`` JIT station-board refresh — async, and the one that
  ``rollback()``\\s, which is how it managed to *undo* a stamp the collector had
  already written.

These run against real Postgres. Only the NJT API is stubbed, at the client
boundary, since the whole point is what happens when upstream breaks.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from trackrat.collectors.njt.client import (
    NJTransitAPIError,
    NJTransitNullDataError,
    TrainNotFoundError,
)
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.collectors.njt.refresh_outcome import NJT_EXPIRY_THRESHOLD
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.services.scheduler import SchedulerService
from trackrat.utils.time import now_et


class _UpstreamErrorNJTClient:
    """NJT answering with an HTTP error, a timeout, or an HTML error page — all
    of which the client surfaces as a bare ``NJTransitAPIError``."""

    def __init__(self, message: str = "NJT API returned 503") -> None:
        self.message = message
        self.calls: list[str] = []

    async def get_train_stop_list(self, train_id: str) -> None:
        self.calls.append(train_id)
        raise NJTransitAPIError(self.message)

    async def close(self) -> None:
        return None


class _NullDataNJTClient:
    async def get_train_stop_list(self, train_id: str) -> None:
        raise NJTransitNullDataError(f"Train {train_id} - API returned null data")

    async def close(self) -> None:
        return None


class _TrainNotFoundNJTClient:
    async def get_train_stop_list(self, train_id: str) -> None:
        raise TrainNotFoundError(f"Train {train_id} not found")

    async def close(self) -> None:
        return None


async def _persist_journey(
    db_session,
    *,
    train_id: str,
    last_updated_at,
    api_error_count: int = 0,
    with_stop_at: str | None = None,
) -> TrainJourney:
    """Commit a journey (and optionally one stop) so a separate connection sees it."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        data_source="NJT",
        observation_type="OBSERVED",
        scheduled_departure=now_et() - timedelta(minutes=40),
        has_complete_journey=True,
        api_error_count=api_error_count,
        is_expired=False,
        stops_count=6,
    )
    db_session.add(journey)
    await db_session.flush()

    if with_stop_at:
        db_session.add(
            JourneyStop(
                journey=journey,
                station_code=with_stop_at,
                station_name="Newark Penn Station",
                stop_sequence=2,
                scheduled_departure=now_et() - timedelta(minutes=20),
            )
        )

    # last_updated_at has a server default, so it must be set after the insert
    # is materialized to survive.
    journey.last_updated_at = last_updated_at
    await db_session.commit()
    return journey


async def _reload(db_session, train_id: str) -> TrainJourney:
    """Re-read from Postgres so we see what was actually committed."""
    db_session.expire_all()
    result = await db_session.execute(
        select(TrainJourney).where(TrainJourney.train_id == train_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Site 1: the scheduler's synchronous periodic-update path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_upstream_error_stamps_last_updated_at(
    db_session, test_settings
):
    """The freshness clock advances even though NJT gave us nothing usable.

    Without this the journey stays pinned to the head of the oldest-first
    batch and is re-selected on every 5-minute tick: 100 journeys x 288 ticks
    = 28,800 wasted calls/day against a 40,000/day quota.
    """
    stale_stamp = now_et() - timedelta(hours=2)
    await _persist_journey(db_session, train_id="3901", last_updated_at=stale_stamp)

    service = SchedulerService(test_settings)
    service.njt_client = _UpstreamErrorNJTClient()

    before = now_et()
    result = await service._collect_single_njt_journey_safe("3901", now_et().date())

    journey = await _reload(db_session, "3901")
    assert journey.last_updated_at is not None
    assert journey.last_updated_at >= before, (
        f"last_updated_at is still {journey.last_updated_at} (seeded at "
        f"{stale_stamp}); the journey never leaves the head of the oldest-first "
        "batch and is re-asked on every tick for the rest of its in-flight window"
    )
    assert result is not None
    assert result["success"] is False
    assert result.get("skipped") is not True, (
        "an upstream failure is a real outcome with a strike attached, not a "
        "benign skip like the null-data case"
    )


@pytest.mark.asyncio
async def test_scheduler_upstream_error_records_a_strike(db_session, test_settings):
    """The strike counter advances, so a sustained outage stops re-asking.

    Expiry is reversible here: NJT discovery re-activates an expired train the
    moment it reappears, so this degrades the board to the timetable rather
    than losing the day's journeys.
    """
    await _persist_journey(
        db_session,
        train_id="3902",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
    )

    service = SchedulerService(test_settings)
    service.njt_client = _UpstreamErrorNJTClient()

    result = await service._collect_single_njt_journey_safe("3902", now_et().date())

    journey = await _reload(db_session, "3902")
    assert journey.api_error_count == NJT_EXPIRY_THRESHOLD
    assert journey.is_expired is True, (
        "the threshold-th consecutive upstream failure must take the journey "
        "out of the candidate set; otherwise a sustained NJT outage holds the "
        "system at max call rate indefinitely"
    )
    assert result is not None
    assert result["expired"] is True


@pytest.mark.asyncio
async def test_scheduler_subclass_handlers_still_win(db_session, test_settings):
    """Handler ordering is load-bearing: both specific arms must come first.

    ``TrainNotFoundError`` and ``NJTransitNullDataError`` both inherit from
    ``NJTransitAPIError``. If the new base-class arm were placed above them it
    would swallow both, and null data — which is NJT's missing coverage, not a
    failing train (#1725) — would start expiring live journeys wholesale.
    """
    await _persist_journey(
        db_session,
        train_id="3903",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
    )

    service = SchedulerService(test_settings)
    service.njt_client = _NullDataNJTClient()

    result = await service._collect_single_njt_journey_safe("3903", now_et().date())

    journey = await _reload(db_session, "3903")
    assert journey.api_error_count == NJT_EXPIRY_THRESHOLD - 1, (
        f"api_error_count moved to {journey.api_error_count}; null data reached "
        "the base-class handler instead of its own, and now carries a strike"
    )
    assert journey.is_expired is False, (
        "a train with no NJT stop-list coverage was expired — it is very likely "
        "still running and on the departure boards"
    )
    assert result is not None
    assert result["reason"] == "no_upstream_data"

    # And the other subclass keeps its own semantics too.
    await _persist_journey(
        db_session,
        train_id="3904",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
    )
    service.njt_client = _TrainNotFoundNJTClient()

    not_found = await service._collect_single_njt_journey_safe("3904", now_et().date())

    assert not_found is not None
    assert not_found["error"] == "Train not found", (
        "a genuine not-found was reported as a generic upstream error; the "
        "specific handler no longer runs"
    )


# ---------------------------------------------------------------------------
# Site 2: the shared async collector path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_upstream_error_stamps_and_strikes(db_session):
    """``collect_journey_details`` handles the bare error instead of raising.

    Before the fix this propagated out of the collector entirely, which is what
    let the JIT caller roll the stamp back.
    """
    stale_stamp = now_et() - timedelta(hours=2)
    journey = await _persist_journey(
        db_session, train_id="3905", last_updated_at=stale_stamp
    )

    collector = JourneyCollector(_UpstreamErrorNJTClient())

    before = now_et()
    # Must not raise — the outcome is recorded, not escalated.
    await collector.collect_journey_details(db_session, journey)
    await db_session.commit()

    refreshed = await _reload(db_session, "3905")
    assert refreshed.last_updated_at is not None
    assert refreshed.last_updated_at >= before
    assert refreshed.api_error_count == 1
    assert refreshed.is_expired is False, (
        "one upstream failure must not expire a running train; only "
        f"{NJT_EXPIRY_THRESHOLD} consecutive ones do"
    )


@pytest.mark.asyncio
async def test_collector_upstream_error_expires_at_threshold(db_session):
    """Consecutive failures reach the existing 3-strike expiry.

    Unlike ``TrainNotFoundError``, no last-chance completion is attempted: an
    HTTP error says nothing about whether the train finished its run, so
    claiming completion would be inventing a fact.
    """
    journey = await _persist_journey(
        db_session,
        train_id="3906",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
    )

    collector = JourneyCollector(_UpstreamErrorNJTClient())
    await collector.collect_journey_details(db_session, journey)
    await db_session.commit()

    refreshed = await _reload(db_session, "3906")
    assert refreshed.api_error_count == NJT_EXPIRY_THRESHOLD
    assert refreshed.is_expired is True
    assert refreshed.is_completed is not True, (
        "an upstream HTTP failure was recorded as the train completing its "
        "journey; that is a fabricated arrival"
    )


@pytest.mark.asyncio
async def test_collector_null_data_still_takes_no_strike(db_session):
    """Ordering check on the collector's arms, mirroring the scheduler's."""
    journey = await _persist_journey(
        db_session,
        train_id="3907",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
    )

    collector = JourneyCollector(_NullDataNJTClient())
    await collector.collect_journey_details(db_session, journey)
    await db_session.commit()

    refreshed = await _reload(db_session, "3907")
    assert refreshed.api_error_count == NJT_EXPIRY_THRESHOLD - 1
    assert refreshed.is_expired is False


# ---------------------------------------------------------------------------
# Site 3: the JIT station-board refresh, which rolls back
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jit_stamp_survives_the_rollback(db_session):
    """The JIT path must not undo the record that we asked NJT.

    This site is uncapped and driven by user traffic: the second pass selects
    on ``last_updated_at < now - 60s``, so a journey whose stamp is rolled back
    is re-attempted by the *next* station-board view — every page load and
    every 30-second web poll — which matches the observed bursty, rush-hour
    weighted call profile.

    The failure is injected *after* the collector has done its bookkeeping, so
    this asserts the recovery path specifically rather than re-testing the
    collector's own handler.
    """
    stale_stamp = now_et() - timedelta(hours=2)
    await _persist_journey(
        db_session,
        train_id="3908",
        last_updated_at=stale_stamp,
        with_stop_at="NP",
    )

    service = DepartureService()

    async def _explode(*args, **kwargs):
        raise RuntimeError("write failed after the collector stamped the journey")

    before = now_et()
    with (
        patch(
            "trackrat.services.departure.NJTJourneyCollector.collect_journey_details",
            new=AsyncMock(side_effect=_explode),
        ),
        patch(
            "trackrat.services.departure.NJTransitClient.get_train_schedule_with_stops",
            new=AsyncMock(return_value={"ITEMS": []}),
        ),
    ):
        await service._ensure_fresh_station_data(db_session, "NP", now_et().date())

    journey = await _reload(db_session, "3908")
    assert journey.last_updated_at is not None
    assert journey.last_updated_at >= before, (
        f"last_updated_at is still {journey.last_updated_at} (seeded at "
        f"{stale_stamp}); the rollback discarded the stamp, so the very next "
        "station-board view re-attempts this same doomed refresh — uncapped, "
        "because user traffic drives it"
    )


@pytest.mark.asyncio
async def test_jit_stamp_after_rollback_takes_no_strike(db_session):
    """A local failure must not push a live train toward expiry.

    Anything reaching the JIT handler may be our own fault — a deadlock, a bad
    row — rather than something NJT said. NJT-attributable strikes are applied
    inside ``collect_journey_details`` before it ever returns here, so counting
    another one would double-count the real ones and invent strikes for the
    rest.
    """
    await _persist_journey(
        db_session,
        train_id="3909",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=NJT_EXPIRY_THRESHOLD - 1,
        with_stop_at="NP",
    )

    service = DepartureService()

    async def _explode(*args, **kwargs):
        raise RuntimeError("deadlock detected")

    with (
        patch(
            "trackrat.services.departure.NJTJourneyCollector.collect_journey_details",
            new=AsyncMock(side_effect=_explode),
        ),
        patch(
            "trackrat.services.departure.NJTransitClient.get_train_schedule_with_stops",
            new=AsyncMock(return_value={"ITEMS": []}),
        ),
    ):
        await service._ensure_fresh_station_data(db_session, "NP", now_et().date())

    journey = await _reload(db_session, "3909")
    assert journey.api_error_count == NJT_EXPIRY_THRESHOLD - 1, (
        f"api_error_count moved to {journey.api_error_count}; a local fault was "
        "charged to the train and pushed it toward expiry"
    )
    assert journey.is_expired is False


# ---------------------------------------------------------------------------
# The regression this is all for
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeatedly_failing_journey_leaves_the_oldest_first_batch(
    db_session, test_settings
):
    """The end-to-end property: a failing journey stops monopolising the queue.

    Two journeys, both stale, one older. The older one fails upstream. After
    that failure it must no longer be the oldest — otherwise the next tick
    picks it again and the second journey is never refreshed at all. This is
    the starvation half of #1827: real in-flight trains go stale behind a
    journey NJT will not answer for.
    """
    older = now_et() - timedelta(hours=3)
    newer = now_et() - timedelta(hours=2)
    await _persist_journey(db_session, train_id="3910", last_updated_at=older)
    await _persist_journey(db_session, train_id="3911", last_updated_at=newer)

    service = SchedulerService(test_settings)
    service.njt_client = _UpstreamErrorNJTClient()

    await service._collect_single_njt_journey_safe("3910", now_et().date())

    db_session.expire_all()
    rows = (
        (
            await db_session.execute(
                select(TrainJourney).where(TrainJourney.train_id.in_(["3910", "3911"]))
            )
        )
        .scalars()
        .all()
    )
    by_id = {j.train_id: j for j in rows}
    failing = by_id["3910"]
    waiting = by_id["3911"]

    assert failing.last_updated_at > waiting.last_updated_at, (
        "the failing journey is still the oldest, so "
        "`ORDER BY last_updated_at ASC` re-selects it on the next tick and "
        f"train {waiting.train_id} — a real in-flight train — keeps waiting"
    )
