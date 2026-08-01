"""
Unit tests for occupied-track filtering in HistoricalTrackPredictor.predict_track.

Issue #1676: a rider reported currently-occupied tracks appearing heavily
weighted in NY Penn track predictions. Beyond the occupancy-window fix in
TrackOccupancyService (see test_track_occupancy.py), the predictor itself
had two holes:

1. The static fallback distribution skipped occupancy filtering entirely —
   the API contract ("Occupied tracks are automatically excluded") was false
   exactly when it mattered most.
2. When every historical track was occupied, the predictor swapped to the
   provider-wide static table (also unfiltered) instead of keeping the
   train-specific distribution.

These tests pin the corrected behavior: filtering and renormalization apply
at every level including the static fallback, and an all-occupied
distribution is served unfiltered rather than replaced.

The filtering/renormalization branch logic is pinned with the same mocked
distribution pattern as test_track_predictor_hierarchy.py; the final test
runs the full predict_track path end-to-end against the real Postgres test
database with the real TrackOccupancyService, so an integration break in
the SQL or service wiring cannot stay green.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.api import OccupiedTracksResponse
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.historical_track_predictor import (
    MIN_TRAIN_ID_RECORDS,
    HistoricalTrackPredictor,
)
from trackrat.services.track_occupancy import TrackOccupancyService
from trackrat.utils.time import now_et


class FakeOccupancyService:
    """Occupancy service stub returning a fixed set of occupied tracks."""

    def __init__(self, occupied: list[str]) -> None:
        self.occupied = occupied

    async def get_occupied_tracks(self, station_code: str) -> OccupiedTracksResponse:
        return OccupiedTracksResponse(
            station_code=station_code,
            station_name=station_code,
            occupied_tracks=self.occupied,
            last_updated=datetime.now(UTC),
            cache_expires_at=datetime.now(UTC),
        )


def _make_predictor(
    occupied: list[str],
    train_id_dist: dict | None,
) -> HistoricalTrackPredictor:
    """Predictor with mocked distribution queries and a fixed occupied set.

    train_id_dist is returned for the train_id level; all lower levels
    return None so a None train_id_dist exercises the static fallback.
    """
    predictor = HistoricalTrackPredictor()
    predictor._occupancy_service = FakeOccupancyService(occupied)
    predictor._get_train_id_distribution = AsyncMock(  # type: ignore[method-assign]
        return_value=train_id_dist
    )
    predictor._get_time_line_distribution = AsyncMock(return_value=None)  # type: ignore[method-assign]
    predictor._get_line_code_distribution = AsyncMock(return_value=None)  # type: ignore[method-assign]
    predictor._get_service_distribution = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return predictor


async def _predict(
    predictor: HistoricalTrackPredictor,
    station_code: str = "NP",
    data_source: str = "NJT",
) -> dict | None:
    return await predictor.predict_track(
        station_code=station_code,
        train_id="3927",
        line_code=None,
        data_source=data_source,
        scheduled_departure=datetime(2026, 7, 28, 8, 0, tzinfo=UTC),
        db=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_occupied_track_removed_and_renormalized():
    """An occupied track is dropped and the rest renormalize to 1.0.

    NP has no platform mappings, so tracks pass through unchanged and the
    track-level math is directly observable."""
    predictor = _make_predictor(
        occupied=["1"],
        train_id_dist={
            "track_probabilities": {"1": 0.5, "2": 0.3, "3": 0.2},
            "total_records": MIN_TRAIN_ID_RECORDS,
        },
    )
    result = await _predict(predictor)

    assert result is not None
    print("platform_probabilities:", result["platform_probabilities"])
    assert result["platform_probabilities"] == {
        "2": pytest.approx(0.6),
        "3": pytest.approx(0.4),
    }
    assert result["features_used"]["occupied_tracks_removed"] == 1
    assert result["features_used"]["occupied_tracks"] == ["1"]
    assert result["primary_prediction"] == "2"


@pytest.mark.asyncio
async def test_all_occupied_serves_distribution_unfiltered():
    """When every candidate track is occupied, keep the train-specific
    distribution unfiltered instead of swapping to the static table."""
    dist = {
        "track_probabilities": {"1": 0.7, "2": 0.3},
        "total_records": MIN_TRAIN_ID_RECORDS,
    }
    predictor = _make_predictor(occupied=["1", "2"], train_id_dist=dist)
    result = await _predict(predictor)

    assert result is not None
    print("platform_probabilities:", result["platform_probabilities"])
    assert result["features_used"]["prediction_level"] == "train_id"
    assert result["platform_probabilities"] == {
        "1": pytest.approx(0.7),
        "2": pytest.approx(0.3),
    }
    assert result["features_used"]["occupied_tracks_removed"] == 0


@pytest.mark.asyncio
async def test_static_fallback_filters_occupied_tracks():
    """Regression (#1676): the static fallback must exclude occupied tracks.

    Occupying tracks 5 and 6 at NY Penn must remove the '5 & 6' platform
    from the static Amtrak distribution and renormalize the rest."""
    predictor = _make_predictor(occupied=["5", "6"], train_id_dist=None)
    result = await _predict(predictor, station_code="NY", data_source="AMTRAK")

    assert result is not None
    print("platform_probabilities:", result["platform_probabilities"])
    assert result["features_used"]["prediction_level"] == "static_fallback"
    assert "5 & 6" not in result["platform_probabilities"]
    assert sum(result["platform_probabilities"].values()) == pytest.approx(1.0)
    assert result["features_used"]["occupied_tracks_removed"] == 2


@pytest.mark.asyncio
async def test_static_fallback_unfiltered_when_unoccupied():
    """Baseline: static fallback with no occupancy serves the full table."""
    predictor = _make_predictor(occupied=[], train_id_dist=None)
    result = await _predict(predictor, station_code="NY", data_source="AMTRAK")

    assert result is not None
    assert result["features_used"]["prediction_level"] == "static_fallback"
    assert "5 & 6" in result["platform_probabilities"]
    assert sum(result["platform_probabilities"].values()) == pytest.approx(1.0)
    assert result["features_used"]["occupied_tracks_removed"] == 0


@pytest.mark.asyncio
async def test_unconfigured_station_returns_none():
    """No historical data and no static table for the station -> no
    prediction (endpoint 404s)."""
    predictor = _make_predictor(occupied=[], train_id_dist=None)
    result = await _predict(predictor, station_code="HB", data_source="NJT")

    assert result is None


async def _seed_np_journey(
    db: AsyncSession,
    train_id: str,
    journey_date: datetime,
    track: str,
    scheduled_departure: datetime,
) -> None:
    """Seed a journey with a tracked stop at Newark Penn (NP)."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date.date(),
        line_code="NE",
        destination="Test Destination",
        origin_station_code="NP",
        terminal_station_code="NY",
        data_source="NJT",
        scheduled_departure=scheduled_departure,
    )
    db.add(journey)
    await db.flush()
    db.add(
        JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_departure=scheduled_departure,
            track=track,
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_end_to_end_occupancy_filtering_real_db(db_session: AsyncSession):
    """Full predict_track path against real Postgres with the real
    TrackOccupancyService: historical distribution comes from seeded
    journeys, the occupied set from a currently-boarding train, and the
    occupied track must be excluded and renormalized away.

    NP has no platform mappings, so tracks pass through 1:1 and the math
    is directly observable end to end."""
    now = now_et()

    # Historical runs of train 9001 at NP: 6 on track 1, 4 on track 2 —
    # journey_dates older than the occupancy service's 2-day bound so only
    # the boarding train below contributes to the occupied set.
    for i in range(MIN_TRAIN_ID_RECORDS):
        day = now - timedelta(days=3 + i)
        await _seed_np_journey(
            db_session,
            "9001",
            journey_date=day,
            track="1" if i < 6 else "2",
            scheduled_departure=day,
        )

    # A different train boarding on track 1 right now.
    await _seed_np_journey(
        db_session,
        "9002",
        journey_date=now,
        track="1",
        scheduled_departure=now + timedelta(minutes=10),
    )

    predictor = HistoricalTrackPredictor()
    # Real occupancy service — fresh instance so its 60s TTL cache cannot
    # carry state across tests.
    predictor._occupancy_service = TrackOccupancyService()

    result = await predictor.predict_track(
        station_code="NP",
        train_id="9001",
        line_code="NE",
        data_source="NJT",
        scheduled_departure=now + timedelta(minutes=30),
        db=db_session,
    )

    assert result is not None
    print("end-to-end result:", result)
    assert result["features_used"]["prediction_level"] == "train_id"
    assert result["features_used"]["occupied_tracks"] == ["1"]
    assert result["features_used"]["occupied_tracks_removed"] == 1
    assert result["platform_probabilities"] == {"2": pytest.approx(1.0)}
    assert result["primary_prediction"] == "2"
