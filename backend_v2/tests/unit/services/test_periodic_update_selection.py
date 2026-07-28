"""Regression tests for NJT periodic-update candidate selection (issue #1670).

Train 3918 was cancelled mid-journey on 2026-07-28 and TrackRat did not notice
for 65 minutes — it received no real-time collection at all between the nightly
schedule build and a user-triggered JIT refresh. The cause was in
``SchedulerService.schedule_periodic_updates``:

- The candidate query matched on lifecycle flags only, which is satisfied by
  *every* NJT train of the day (the nightly schedule collector sets
  ``has_complete_journey=True`` on all of them) plus every earlier journey that
  never reached a terminal stop. Production logged the batch saturated at its
  cap on every 5-minute tick around the clock, including 4am.
- ``LIMIT`` was applied before the staleness filter (which ran in Python) with
  no ``ORDER BY``, so which trains were refreshed came down to Postgres'
  physical row order — a given running train could be passed over indefinitely.

These tests pin both properties: the candidate set is restricted to trains that
can plausibly be in flight, and within it the stalest trains are served first.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest

import trackrat.services.scheduler as scheduler_module
from trackrat.models.database import TrainJourney
from trackrat.services.scheduler import (
    ACTIVE_JOURNEY_LOOKBACK_HOURS,
    SchedulerService,
)
from trackrat.settings import Settings
from trackrat.utils.time import now_et


def _make_scheduler(batch_size: int) -> SchedulerService:
    """A SchedulerService whose add_job/get_job are inert but observable."""
    settings = Settings(
        njt_api_token="test_token",
        journey_update_interval_minutes=15,
        hot_train_window_minutes=15,
        journey_update_batch_size=batch_size,
        environment="testing",
    )
    return SchedulerService(settings=settings)


def _scheduled_train_ids(service: SchedulerService) -> list[str]:
    """Train IDs the service queued for collection, in the order it queued them."""
    return [job.args[0] for job in service.scheduler.get_jobs()]


async def _add_journey(
    db,
    *,
    train_id: str,
    scheduled_departure,
    last_updated_at,
    is_cancelled: bool = False,
    is_completed: bool = False,
    is_expired: bool = False,
    has_complete_journey: bool = True,
    data_source: str = "NJT",
) -> TrainJourney:
    journey = TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=scheduled_departure,
        has_complete_journey=has_complete_journey,
        is_cancelled=is_cancelled,
        is_completed=is_completed,
        is_expired=is_expired,
        stops_count=6,
    )
    db.add(journey)
    await db.flush()
    # last_updated_at has a server default, so it must be set after the insert
    # is materialized to survive.
    journey.last_updated_at = last_updated_at
    await db.flush()
    return journey


@pytest.mark.asyncio
async def test_stalest_in_flight_train_is_never_starved_by_the_batch_limit(db_session):
    """The exact 3918 failure: an in-flight train stale for over an hour must be
    picked up even when the batch limit is smaller than the candidate pool.

    Before the fix the LIMIT ran before the staleness filter with no ORDER BY,
    so this train's presence in the batch depended on Postgres' row order — and
    in production it lost that lottery for 12 consecutive ticks.
    """
    now = now_et()
    batch_size = 5
    service = _make_scheduler(batch_size)

    # A pool of in-flight trains, all stale, far larger than one batch.
    for i in range(20):
        await _add_journey(
            db_session,
            train_id=f"filler{i}",
            scheduled_departure=now - timedelta(minutes=20),
            last_updated_at=now - timedelta(minutes=16),
        )

    # 3918: departed its origin 65 min ago, last touched 78 min ago.
    await _add_journey(
        db_session,
        train_id="3918",
        scheduled_departure=now - timedelta(minutes=65),
        last_updated_at=now - timedelta(minutes=78),
    )

    await service.schedule_periodic_updates(db_session)

    scheduled = _scheduled_train_ids(service)
    assert len(scheduled) == batch_size
    assert "3918" in scheduled, (
        "the stalest in-flight train must be in the batch; it was starved by an "
        "unordered LIMIT before issue #1670"
    )


@pytest.mark.asyncio
async def test_batch_is_ordered_stalest_first(db_session):
    """Oldest-updated trains are served first, so per-train staleness is bounded
    by pool_size / batch_size ticks rather than being unbounded."""
    now = now_et()
    service = _make_scheduler(batch_size=3)

    # Insert newest-updated first so insertion order is the opposite of the
    # expected selection order — an unordered query would likely return these
    # in heap (insertion) order and fail.
    for minutes_stale in (16, 30, 45, 60, 75):
        await _add_journey(
            db_session,
            train_id=f"stale{minutes_stale}",
            scheduled_departure=now - timedelta(minutes=30),
            last_updated_at=now - timedelta(minutes=minutes_stale),
        )

    await service.schedule_periodic_updates(db_session)

    assert _scheduled_train_ids(service) == ["stale75", "stale60", "stale45"]


@pytest.mark.asyncio
async def test_trains_that_cannot_be_in_flight_are_not_candidates(db_session):
    """Journeys matching every lifecycle flag but not plausibly running are
    excluded.

    This is what saturated the batch: the nightly schedule collector marks every
    one of the day's trains ``has_complete_journey=True``, and journeys that
    never reach a terminal keep ``is_completed=False`` until the next day's
    expiry sweep. Selecting on flags alone burns the whole budget on trains that
    finished hours ago or have not left yet.
    """
    now = now_et()
    service = _make_scheduler(batch_size=50)

    # Ran and finished long ago (never marked completed).
    await _add_journey(
        db_session,
        train_id="ranHoursAgo",
        scheduled_departure=now
        - timedelta(hours=ACTIVE_JOURNEY_LOOKBACK_HOURS, minutes=30),
        last_updated_at=now - timedelta(hours=4),
    )
    # Tonight's train, built by the nightly schedule job, not due for hours.
    await _add_journey(
        db_session,
        train_id="departsTonight",
        scheduled_departure=now + timedelta(hours=6),
        last_updated_at=now - timedelta(hours=5),
    )
    # About to depart: schedule_departure_collections owns the pre-departure
    # window on a much faster cadence, so this path leaves it alone rather than
    # queueing a second collection for the same train.
    await _add_journey(
        db_session,
        train_id="departsShortly",
        scheduled_departure=now + timedelta(minutes=10),
        last_updated_at=now - timedelta(hours=5),
    )
    # Actually in flight.
    await _add_journey(
        db_session,
        train_id="running",
        scheduled_departure=now - timedelta(minutes=25),
        last_updated_at=now - timedelta(minutes=20),
    )

    await service.schedule_periodic_updates(db_session)

    assert _scheduled_train_ids(service) == ["running"]


@pytest.mark.asyncio
async def test_fresh_and_finished_journeys_are_excluded(db_session):
    """Staleness and the lifecycle flags are still honoured — now in SQL."""
    now = now_et()
    service = _make_scheduler(batch_size=50)

    in_flight = {
        "scheduled_departure": now - timedelta(minutes=20),
        "last_updated_at": now - timedelta(minutes=20),
    }
    await _add_journey(
        db_session,
        train_id="fresh",
        scheduled_departure=now - timedelta(minutes=20),
        last_updated_at=now - timedelta(minutes=2),
    )
    await _add_journey(db_session, train_id="cancelled", is_cancelled=True, **in_flight)
    await _add_journey(db_session, train_id="completed", is_completed=True, **in_flight)
    await _add_journey(db_session, train_id="expired", is_expired=True, **in_flight)
    await _add_journey(
        db_session, train_id="noStops", has_complete_journey=False, **in_flight
    )
    await _add_journey(db_session, train_id="notNJT", data_source="AMTRAK", **in_flight)
    await _add_journey(db_session, train_id="stale", **in_flight)

    await service.schedule_periodic_updates(db_session)

    assert _scheduled_train_ids(service) == ["stale"]


@pytest.mark.asyncio
async def test_backlog_is_logged_so_a_saturated_batch_is_visible(db_session):
    """The old log reported the post-limit list length as `total_active_trains`,
    which is clamped by the limit and so could never reveal that trains were
    being left behind — production emitted `count=50 total_active_trains=50` on
    every tick for months while running trains went unrefreshed."""
    now = now_et()
    service = _make_scheduler(batch_size=2)

    for i in range(7):
        await _add_journey(
            db_session,
            train_id=f"train{i}",
            scheduled_departure=now - timedelta(minutes=20),
            last_updated_at=now - timedelta(minutes=20 + i),
        )

    with patch.object(scheduler_module.logger, "info") as mock_log:
        await service.schedule_periodic_updates(db_session)

    summaries = [
        call.kwargs
        for call in mock_log.call_args_list
        if call.args and call.args[0] == "scheduler.periodic.scheduled"
    ]
    assert summaries, "expected a batch summary log line"
    assert summaries[-1]["count"] == 2
    assert summaries[-1]["eligible_count"] == 7
    assert summaries[-1]["backlog"] == 5
