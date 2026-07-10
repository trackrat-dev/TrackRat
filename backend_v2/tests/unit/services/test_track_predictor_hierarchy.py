"""
Unit tests for the lazy hierarchy walk in HistoricalTrackPredictor.predict_track.

Issue #1368: predict_track used to query all four distribution levels
(train_id, time+line, line_code, service_provider) on every request even
when the train_id level already had enough records to satisfy the
hierarchy. These tests assert that each level is only queried when the
higher-priority levels didn't already meet their MIN_*_RECORDS threshold,
and that the selected prediction level is unchanged from the original
eager-evaluation behavior.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from trackrat.models.api import OccupiedTracksResponse
from trackrat.services.historical_track_predictor import (
    MIN_LINE_CODE_RECORDS,
    MIN_SERVICE_PROVIDER_RECORDS,
    MIN_TIME_LINE_RECORDS,
    MIN_TRAIN_ID_RECORDS,
    HistoricalTrackPredictor,
)


def _dist(total_records: int, track: str = "1") -> dict:
    return {"track_probabilities": {track: 1.0}, "total_records": total_records}


class FakeOccupancyService:
    """No tracks occupied, so the selected distribution passes through untouched."""

    async def get_occupied_tracks(self, station_code: str) -> OccupiedTracksResponse:
        return OccupiedTracksResponse(
            station_code=station_code,
            station_name=station_code,
            occupied_tracks=[],
            last_updated=datetime.now(UTC),
            cache_expires_at=datetime.now(UTC),
        )


def _make_predictor(
    train_id_records: int | None,
    time_line_records: int | None,
    line_code_records: int | None,
    service_records: int | None,
) -> HistoricalTrackPredictor:
    """Build a predictor whose four distribution queries are mocked to return
    the given record counts (None means "no historical data at all")."""
    predictor = HistoricalTrackPredictor()
    predictor._occupancy_service = FakeOccupancyService()

    predictor._get_train_id_distribution = AsyncMock(  # type: ignore[method-assign]
        return_value=_dist(train_id_records) if train_id_records is not None else None
    )
    predictor._get_time_line_distribution = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            _dist(time_line_records) if time_line_records is not None else None
        )
    )
    predictor._get_line_code_distribution = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            _dist(line_code_records) if line_code_records is not None else None
        )
    )
    predictor._get_service_distribution = AsyncMock(  # type: ignore[method-assign]
        return_value=_dist(service_records) if service_records is not None else None
    )
    return predictor


@pytest.mark.asyncio
async def test_train_id_hit_skips_lower_levels():
    """When train_id has enough records, the other three levels must not be queried."""
    predictor = _make_predictor(
        train_id_records=MIN_TRAIN_ID_RECORDS,
        time_line_records=MIN_TIME_LINE_RECORDS,
        line_code_records=MIN_LINE_CODE_RECORDS,
        service_records=MIN_SERVICE_PROVIDER_RECORDS,
    )

    result = await predictor.predict_track(
        station_code="NY",
        train_id="3927",
        line_code="NE",
        data_source="NJT",
        scheduled_departure=datetime(2026, 7, 4, 8, 0, tzinfo=UTC),
        db=AsyncMock(),
    )

    assert result is not None
    assert result["features_used"]["prediction_level"] == "train_id"
    predictor._get_train_id_distribution.assert_awaited_once()
    predictor._get_time_line_distribution.assert_not_called()
    predictor._get_line_code_distribution.assert_not_called()
    predictor._get_service_distribution.assert_not_called()


@pytest.mark.asyncio
async def test_falls_through_to_line_code_when_higher_levels_insufficient():
    """train_id and time_line below threshold -> line_code queried and selected;
    service_provider (the most expensive query) must not be queried."""
    predictor = _make_predictor(
        train_id_records=MIN_TRAIN_ID_RECORDS - 1,
        time_line_records=MIN_TIME_LINE_RECORDS - 1,
        line_code_records=MIN_LINE_CODE_RECORDS,
        service_records=MIN_SERVICE_PROVIDER_RECORDS,
    )

    result = await predictor.predict_track(
        station_code="NY",
        train_id="3927",
        line_code="NE",
        data_source="NJT",
        scheduled_departure=datetime(2026, 7, 4, 8, 0, tzinfo=UTC),
        db=AsyncMock(),
    )

    assert result is not None
    assert result["features_used"]["prediction_level"] == "line_code"
    predictor._get_train_id_distribution.assert_awaited_once()
    predictor._get_time_line_distribution.assert_awaited_once()
    predictor._get_line_code_distribution.assert_awaited_once()
    predictor._get_service_distribution.assert_not_called()


@pytest.mark.asyncio
async def test_falls_through_to_service_provider_when_no_line_code():
    """Without a line_code, time_line and line_code levels are skipped
    entirely and the hierarchy goes straight from train_id to service."""
    predictor = _make_predictor(
        train_id_records=MIN_TRAIN_ID_RECORDS - 1,
        time_line_records=None,
        line_code_records=None,
        service_records=MIN_SERVICE_PROVIDER_RECORDS,
    )

    result = await predictor.predict_track(
        station_code="NY",
        train_id="3927",
        line_code=None,
        data_source="NJT",
        scheduled_departure=datetime(2026, 7, 4, 8, 0, tzinfo=UTC),
        db=AsyncMock(),
    )

    assert result is not None
    assert result["features_used"]["prediction_level"] == "service_provider"
    predictor._get_train_id_distribution.assert_awaited_once()
    predictor._get_time_line_distribution.assert_not_called()
    predictor._get_line_code_distribution.assert_not_called()
    predictor._get_service_distribution.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_levels_insufficient_falls_back_to_static():
    """When every level is below threshold, all four are queried (there's
    nothing left to skip) and the static fallback distribution is used."""
    predictor = _make_predictor(
        train_id_records=MIN_TRAIN_ID_RECORDS - 1,
        time_line_records=MIN_TIME_LINE_RECORDS - 1,
        line_code_records=MIN_LINE_CODE_RECORDS - 1,
        service_records=MIN_SERVICE_PROVIDER_RECORDS - 1,
    )

    result = await predictor.predict_track(
        station_code="NY",
        train_id="3927",
        line_code="NE",
        data_source="NJT",
        scheduled_departure=datetime(2026, 7, 4, 8, 0, tzinfo=UTC),
        db=AsyncMock(),
    )

    assert result is not None
    assert result["features_used"]["prediction_level"] == "static_fallback"
    predictor._get_train_id_distribution.assert_awaited_once()
    predictor._get_time_line_distribution.assert_awaited_once()
    predictor._get_line_code_distribution.assert_awaited_once()
    predictor._get_service_distribution.assert_awaited_once()
