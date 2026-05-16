"""
Unit tests for the historical lookback bound on track-distribution queries.

Issue #1168: The four distribution methods used to scan the full retention
window (120 days), which on staging exhausted Postgres /dev/shm and surfaced
as DiskFullError on /predictions/track. We now cap each query at the
HISTORICAL_LOOKBACK_DAYS window via `TrainJourney.journey_date >= cutoff`.

These tests verify the filter is present on the compiled SQL for every
distribution method, so future regressions (e.g., copying a query without
the bound) are caught at unit-test time rather than via /dev/shm pressure
in production.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from trackrat.services.historical_track_predictor import (
    HISTORICAL_LOOKBACK_DAYS,
    HistoricalTrackPredictor,
)


def _empty_result() -> AsyncMock:
    """Mock execute() return value that yields no rows."""
    result = AsyncMock()
    result.all = lambda: []
    return result


async def _capture_query(predictor: HistoricalTrackPredictor, coro):
    """Invoke a distribution method and return the compiled SQL it issued."""
    captured: dict[str, object] = {}

    async def fake_execute(stmt):
        captured["stmt"] = stmt
        return _empty_result()

    db = AsyncMock()
    db.execute = fake_execute
    await coro(db)

    stmt = captured["stmt"]
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_historical_lookback_days_is_positive():
    """The lookback constant must be a sensible positive value."""
    assert HISTORICAL_LOOKBACK_DAYS > 0
    # Anything beyond the default retention (120 days) would be a no-op cap.
    assert HISTORICAL_LOOKBACK_DAYS <= 120


@pytest.mark.asyncio
async def test_train_id_distribution_bounds_by_journey_date():
    """_get_train_id_distribution must filter by TrainJourney.journey_date."""
    predictor = HistoricalTrackPredictor()
    sql = await _capture_query(
        predictor,
        lambda db: predictor._get_train_id_distribution(db, "NY", "3927"),
    )
    assert "train_journeys.journey_date >=" in sql, sql


@pytest.mark.asyncio
async def test_time_line_distribution_bounds_by_journey_date():
    """_get_time_line_distribution must filter by TrainJourney.journey_date."""
    predictor = HistoricalTrackPredictor()
    scheduled = datetime(2026, 5, 11, 8, 30, tzinfo=UTC)
    sql = await _capture_query(
        predictor,
        lambda db: predictor._get_time_line_distribution(db, "NY", "NE", scheduled),
    )
    assert "train_journeys.journey_date >=" in sql, sql


@pytest.mark.asyncio
async def test_line_code_distribution_bounds_by_journey_date():
    """_get_line_code_distribution must filter by TrainJourney.journey_date."""
    predictor = HistoricalTrackPredictor()
    sql = await _capture_query(
        predictor,
        lambda db: predictor._get_line_code_distribution(db, "NY", "NE"),
    )
    assert "train_journeys.journey_date >=" in sql, sql


@pytest.mark.asyncio
async def test_service_distribution_bounds_by_journey_date():
    """_get_service_distribution must filter by TrainJourney.journey_date."""
    predictor = HistoricalTrackPredictor()
    sql = await _capture_query(
        predictor,
        lambda db: predictor._get_service_distribution(db, "NY", "NJT"),
    )
    assert "train_journeys.journey_date >=" in sql, sql


@pytest.mark.asyncio
async def test_cutoff_matches_configured_lookback():
    """The compiled cutoff value must equal today() - HISTORICAL_LOOKBACK_DAYS.

    We use the train_id query as a representative; all four methods compute
    the cutoff identically via now_et().date() - timedelta(days=...).
    """
    from trackrat.utils.time import now_et

    predictor = HistoricalTrackPredictor()
    sql = await _capture_query(
        predictor,
        lambda db: predictor._get_train_id_distribution(db, "NY", "3927"),
    )

    expected_cutoff = (
        now_et().date() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    ).isoformat()
    assert expected_cutoff in sql, sql
