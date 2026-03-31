"""
Prediction API endpoints.

Provides track predictions and delay forecasts for supported stations.
"""

from datetime import UTC, date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.station_configs import (
    STATION_PREDICTION_CONFIGS,
    get_tracks_for_station,
    station_has_predictions,
)
from trackrat.db.engine import get_db
from trackrat.models.api import DelayBreakdownProbabilities, DelayForecastResponse
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.delay_forecaster import delay_forecaster
from trackrat.services.historical_track_predictor import historical_track_predictor

logger = get_logger()

router = APIRouter(prefix="/api/v2/predictions", tags=["predictions"])


class TrackPredictionResponse(BaseModel):
    """Response model for track predictions."""

    platform_probabilities: dict[str, float]
    primary_prediction: str
    confidence: float
    top_3: list[str]
    model_version: str
    station_code: str
    train_id: str
    features_used: dict[str, Any] | None = None


class StationPredictionSupport(BaseModel):
    """Information about prediction support for a station."""

    code: str
    name: str
    predictions_available: bool
    track_count: int | None = None


class SupportedStationsResponse(BaseModel):
    """Response model for supported stations endpoint."""

    stations: list[StationPredictionSupport]
    total_predictions_enabled: int


@router.get("/track", response_model=TrackPredictionResponse)
@handle_errors
async def predict_track(
    station_code: str = Query(..., description="Station code (e.g., 'NY')"),
    train_id: str = Query(..., description="Train ID (e.g., '3123' or 'A2301')"),
    journey_date: date = Query(..., description="Date of journey (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> TrackPredictionResponse:
    """Get track prediction for a train at a station.

    Returns probability distribution across tracks with a primary prediction and
    confidence score. Occupied tracks are automatically excluded and probabilities
    renormalized. Returns 400 for unsupported stations, 404 for insufficient data.
    """

    logger.info(
        "track_prediction_request_start",
        station_code=station_code,
        train_id=train_id,
        journey_date=journey_date,
    )

    # Check if station supports predictions (for now, keep this check)
    if not station_has_predictions(station_code):
        raise HTTPException(
            status_code=400,
            detail=f"Track predictions not available for station {station_code}",
        )

    # Look up the train to get line code and data source
    from sqlalchemy import and_, select

    query = (
        select(TrainJourney)
        .where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
            )
        )
        .limit(1)
    )

    result = await db.execute(query)
    train_journey = result.scalar_one_or_none()

    if not train_journey:
        # Try to find any journey for this train ID to get metadata
        query = select(TrainJourney).where(TrainJourney.train_id == train_id).limit(1)

        result = await db.execute(query)
        train_journey = result.scalar_one_or_none()

        if not train_journey:
            raise HTTPException(
                status_code=404,
                detail=f"Train {train_id} not found",
            )

    # Generate prediction with timing
    import time
    from datetime import datetime

    prediction_start = time.time()

    # Look up stop-level departure at the target station for better time-of-day matching.
    # Falls back to journey-level scheduled_departure (origin time) if stop not found.
    stop_query = (
        select(JourneyStop.scheduled_departure)
        .where(
            and_(
                JourneyStop.journey_id == train_journey.id,
                JourneyStop.station_code == station_code,
                JourneyStop.scheduled_departure.is_not(None),
            )
        )
        .limit(1)
    )
    stop_result = await db.execute(stop_query)
    stop_departure = stop_result.scalar_one_or_none()

    scheduled_departure = (
        stop_departure or train_journey.scheduled_departure or datetime.now(UTC)
    )

    # data_source is non-nullable in database but MyPy doesn't know this
    data_source = train_journey.data_source or "NJT"  # fallback to NJT as default

    prediction = await historical_track_predictor.predict_track(
        station_code=station_code,
        train_id=train_id,
        line_code=train_journey.line_code,
        data_source=data_source,
        scheduled_departure=scheduled_departure,
        db=db,
    )

    prediction_duration = time.time() - prediction_start

    logger.info(
        "historical_prediction_timing",
        station_code=station_code,
        train_id=train_id,
        prediction_duration_ms=round(prediction_duration * 1000, 2),
    )

    # If no prediction available (insufficient historical data), return 404
    if prediction is None:
        logger.info(
            "track_prediction_unavailable",
            station_code=station_code,
            train_id=train_id,
            reason="insufficient_data",
        )
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data to predict track for train {train_id} at station {station_code}",
        )

    # Log successful prediction details
    logger.info(
        "track_prediction_success",
        station_code=station_code,
        train_id=train_id,
        primary_prediction=prediction["primary_prediction"],
        confidence=prediction["confidence"],
        top_3_platforms=prediction["top_3"],
        model_version=prediction["model_version"],
        features_count=len(prediction.get("features_used", {})),
        prediction_level=prediction.get("features_used", {}).get("prediction_level"),
        historical_records=prediction.get("features_used", {}).get(
            "historical_records"
        ),
        prediction_distribution={
            platform: round(prob, 3)
            for platform, prob in sorted(
                prediction["platform_probabilities"].items(),
                key=lambda x: x[1],
                reverse=True,
            )[
                :5
            ]  # Only log top 5 for brevity
        },
    )

    # Return prediction
    return TrackPredictionResponse(
        platform_probabilities=prediction["platform_probabilities"],
        primary_prediction=prediction["primary_prediction"],
        confidence=prediction["confidence"],
        top_3=prediction["top_3"],
        model_version=prediction["model_version"],
        station_code=station_code,
        train_id=train_id,
        features_used=prediction.get("features_used"),
    )


@router.get("/supported-stations", response_model=SupportedStationsResponse)
@handle_errors
async def get_supported_stations() -> SupportedStationsResponse:
    """Get list of stations that support track predictions.

    Returns each station's prediction availability and track count, allowing
    clients to show or hide prediction features appropriately.
    """

    # Station name mappings
    STATION_NAMES = {
        "NY": "New York Penn",
        "NP": "Newark Penn",
        "ND": "Newark Broad",
        "HB": "Hoboken",
        "MP": "Metropark",
        "ST": "Secaucus",
        "TR": "Trenton",
        "PH": "Philadelphia",
        "DV": "Dover",
        "DN": "Denville",
        "PL": "Plainfield",
        "LB": "Long Branch",
        "JA": "Jersey Avenue",
        "JAM": "Jamaica",
        "GCT": "Grand Central",
    }

    stations = []
    predictions_enabled_count = 0

    for code, config in STATION_PREDICTION_CONFIGS.items():
        if code == "_default":
            continue

        enabled = config.get("predictions_enabled", False)
        if enabled:
            predictions_enabled_count += 1

        stations.append(
            StationPredictionSupport(
                code=code,
                name=STATION_NAMES.get(code, code),
                predictions_available=enabled,
                track_count=len(get_tracks_for_station(code)) if enabled else None,
            )
        )

    # Sort by station code
    stations.sort(key=lambda x: x.code)

    logger.info(
        "supported_stations_requested",
        total_stations=len(stations),
        predictions_enabled=predictions_enabled_count,
    )

    return SupportedStationsResponse(
        stations=stations, total_predictions_enabled=predictions_enabled_count
    )


@router.get("/delay", response_model=DelayForecastResponse)
@handle_errors
async def predict_delay(
    train_id: str = Query(..., description="Train ID (e.g., '3123' or 'A2301')"),
    station_code: str = Query(
        ..., description="Station code (e.g., 'NY', 'NP', 'JAM')"
    ),
    journey_date: date = Query(..., description="Date of journey (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> DelayForecastResponse:
    """Get delay and cancellation forecast for a train at a boarding station.

    Returns probability distribution across delay categories (on-time, slight,
    significant, major), cancellation probability, and expected delay minutes.
    Predictions are station-specific when the boarding station differs from the
    train's origin. Adjusts for time-of-day patterns and live congestion.
    """
    import time

    logger.info(
        "delay_forecast_request_start",
        train_id=train_id,
        station_code=station_code,
        journey_date=journey_date,
    )

    # Look up the train to get line code and data source
    from sqlalchemy import and_, select

    query = (
        select(TrainJourney)
        .where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
            )
        )
        .limit(1)
    )

    result = await db.execute(query)
    train_journey = result.scalar_one_or_none()

    if not train_journey:
        # Try to find any journey for this train ID to get metadata
        query = select(TrainJourney).where(TrainJourney.train_id == train_id).limit(1)
        result = await db.execute(query)
        train_journey = result.scalar_one_or_none()

        if not train_journey:
            raise HTTPException(
                status_code=404,
                detail=f"Train {train_id} not found",
            )

    # Generate forecast
    prediction_start = time.time()

    from trackrat.utils.time import now_et

    scheduled_departure = train_journey.scheduled_departure or now_et()
    data_source = train_journey.data_source or "NJT"

    forecast = await delay_forecaster.forecast(
        train_id=train_id,
        station_code=station_code,
        origin_station_code=train_journey.origin_station_code or station_code,
        line_code=train_journey.line_code,
        data_source=data_source,
        journey_date=journey_date,
        scheduled_departure=scheduled_departure,
        db=db,
    )

    prediction_duration = time.time() - prediction_start

    logger.info(
        "delay_forecast_timing",
        train_id=train_id,
        prediction_duration_ms=round(prediction_duration * 1000, 2),
    )

    return DelayForecastResponse(
        train_id=train_id,
        station_code=station_code,
        journey_date=journey_date,
        cancellation_probability=forecast.cancellation_probability,
        delay_probabilities=DelayBreakdownProbabilities(
            on_time=forecast.on_time_probability,
            slight=forecast.slight_delay_probability,
            significant=forecast.significant_delay_probability,
            major=forecast.major_delay_probability,
        ),
        expected_delay_minutes=forecast.expected_delay_minutes,
        confidence=forecast.confidence,
        sample_count=forecast.sample_count,
        factors=forecast.factors,
    )
