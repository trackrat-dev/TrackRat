"""The scheduler's sync NJT refresh path must advance the freshness clock when
NJT has no stop list for a train (issue #1748).

``SchedulerService._collect_single_njt_journey_safe`` is the implementation
``schedule_periodic_updates`` actually dispatches to, and it is a *separate*
implementation from ``JourneyCollector.collect_journey_details`` — it writes
through a synchronous session rather than the request's async one. Both had the
same defect, so both need their own regression test; a fix to one does not
protect the other.

The bug: the ``NJTransitNullDataError`` arm returned without opening a session
at all, while the ``TrainNotFoundError`` arm immediately below it wrote
``last_updated_at``. Since the periodic batch is selected with
``ORDER BY last_updated_at ASC LIMIT batch_size``, a journey that never stamps
sorts first on every subsequent tick and is re-selected forever.

These tests run against real Postgres through the real sync engine the
production code builds for itself — only the NJT API is stubbed, at the
``njt_client`` boundary, since the whole point is what happens when upstream
answers with nulls.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from trackrat.collectors.njt.client import NJTransitNullDataError, TrainNotFoundError
from trackrat.models.database import TrainJourney
from trackrat.services.scheduler import SchedulerService
from trackrat.utils.time import now_et


class _NullDataNJTClient:
    """Upstream NJT answering with all key fields null, as it does nightly for
    the same ~116 train numbers."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_train_stop_list(self, train_id: str) -> None:
        self.calls.append(train_id)
        raise NJTransitNullDataError(f"Train {train_id} - API returned null data")


class _TrainNotFoundNJTClient:
    """Upstream NJT with no record of the train at all — a genuine strike."""

    async def get_train_stop_list(self, train_id: str) -> None:
        raise TrainNotFoundError(f"Train {train_id} not found")


async def _persist_journey(
    db_session,
    *,
    train_id: str,
    last_updated_at,
    api_error_count: int = 0,
) -> TrainJourney:
    """Commit a journey so the scheduler's separate sync connection can see it."""
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
    # last_updated_at has a server default, so it must be set after the insert
    # is materialized to survive.
    journey.last_updated_at = last_updated_at
    await db_session.commit()
    return journey


async def _reload(db_session, train_id: str) -> TrainJourney:
    """Re-read from Postgres so we see what the sync session actually wrote."""
    db_session.expire_all()
    result = await db_session.execute(
        select(TrainJourney).where(TrainJourney.train_id == train_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_null_data_stamps_last_updated_at(db_session, test_settings):
    """The freshness clock advances even though nothing was collected."""
    stale_stamp = now_et() - timedelta(hours=2)
    await _persist_journey(db_session, train_id="744", last_updated_at=stale_stamp)

    service = SchedulerService(test_settings)
    service.njt_client = _NullDataNJTClient()

    before = now_et()
    result = await service._collect_single_njt_journey_safe("744", now_et().date())

    journey = await _reload(db_session, "744")
    assert journey.last_updated_at is not None
    assert journey.last_updated_at >= before, (
        f"last_updated_at is still {journey.last_updated_at} (was seeded at "
        f"{stale_stamp}); the journey stays pinned to the head of the "
        "oldest-first batch and is re-selected on every tick"
    )
    assert result is not None
    assert result["success"] is False


@pytest.mark.asyncio
async def test_null_data_does_not_record_a_strike(db_session, test_settings):
    """Stamping the clock must not also count the train as failing.

    ``last_updated_at`` answers "when did we last ask", ``api_error_count``
    answers "is this train failing". #1725 established that null data is NJT's
    missing coverage, so it is the first and never the second — expiring these
    would erase live journeys wholesale.
    """
    await _persist_journey(
        db_session,
        train_id="738",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=2,
    )

    service = SchedulerService(test_settings)
    service.njt_client = _NullDataNJTClient()

    # Three cycles: more than enough to trip the 3-strike threshold if the
    # freshness stamp had been wired to the error counter.
    for _ in range(3):
        await service._collect_single_njt_journey_safe("738", now_et().date())

    journey = await _reload(db_session, "738")
    assert journey.api_error_count == 2, (
        f"api_error_count moved to {journey.api_error_count}; null data must "
        "never advance the strike counter"
    )
    assert journey.is_expired is False, (
        "the train was expired by repeated null data — it is very likely still "
        "running and on the departure boards"
    )


@pytest.mark.asyncio
async def test_null_data_is_reported_as_skipped_not_an_error(db_session, test_settings):
    """The returned dict must classify as `skipped` for the batch collector.

    ``collect_njt_journeys_batch`` branches success → skipped → else-error. The
    old return carried only ``error: "Transient null data"``, so every null-data
    train landed in the error branch — the ~20%-nightly / 80%-on-2026-08-01
    "failure" rate #1725 set out to stop counting as ours.
    """
    await _persist_journey(
        db_session, train_id="1122", last_updated_at=now_et() - timedelta(hours=2)
    )

    service = SchedulerService(test_settings)
    service.njt_client = _NullDataNJTClient()

    result = await service._collect_single_njt_journey_safe("1122", now_et().date())

    assert result is not None
    assert result["skipped"] is True, (
        "without a truthy `skipped` key this falls through to the generic error "
        "branch of collect_njt_journeys_batch"
    )
    assert result["reason"] == "no_upstream_data"
    assert result["expired"] is False
    assert "transient" not in str(result).lower(), (
        "null data is persistent — the same train numbers return null night "
        "after night (see NJTransitNullDataError)"
    )


@pytest.mark.asyncio
async def test_genuinely_missing_train_still_strikes_and_expires(
    db_session, test_settings
):
    """The sibling branch must keep working — this fix must not blunt expiry.

    Both branches now write ``last_updated_at``, so the only thing separating
    them is the strike. A train NJT has no record of at all still accrues one
    and still expires on the third.
    """
    await _persist_journey(
        db_session,
        train_id="9001",
        last_updated_at=now_et() - timedelta(hours=2),
        api_error_count=2,
    )

    service = SchedulerService(test_settings)
    service.njt_client = _TrainNotFoundNJTClient()

    result = await service._collect_single_njt_journey_safe("9001", now_et().date())

    journey = await _reload(db_session, "9001")
    assert journey.api_error_count == 3
    assert journey.is_expired is True, (
        "the third TrainNotFoundError must still expire the journey; null-data "
        "handling shares this code path and must not have softened it"
    )
    assert result is not None
    assert result["expired"] is True
    assert not result.get("skipped"), (
        "a genuine not-found is a real outcome with a strike attached, not a "
        "benign skip"
    )
