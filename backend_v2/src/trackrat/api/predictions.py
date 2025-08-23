"""
Machine Learning platform prediction API endpoints.

Provides ML-based platform predictions for supported stations.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.station_configs import (
    STATION_ML_CONFIGS,
    get_platform_for_track,
    get_station_config,
    get_tracks_for_station,
    station_has_ml_predictions,
)
from trackrat.db.engine import get_db
from trackrat.services.ml_features import TrackPredictionFeatures
from trackrat.services.ml_predictor import track_predictor

logger = get_logger()

router = APIRouter(prefix="/api/v2/predictions", tags=["predictions"])


class TrackPredictionResponse(BaseModel):
    """Response model for platform predictions."""

    platform_probabilities: dict[str, float]
    primary_prediction: str
    confidence: float
    top_3: list[str]
    model_version: str
    station_code: str
    train_id: str
    features_used: dict[str, Any] | None = None


class StationMLSupport(BaseModel):
    """Information about ML prediction support for a station."""

    code: str
    name: str
    ml_predictions_available: bool
    track_count: int | None = None


class SupportedStationsResponse(BaseModel):
    """Response model for supported stations endpoint."""

    stations: list[StationMLSupport]
    total_ml_enabled: int


@router.get("/track", response_model=TrackPredictionResponse)
@handle_errors
async def predict_track(
    station_code: str = Query(..., description="Station code (e.g., 'NY')"),
    train_id: str = Query(..., description="Train ID (e.g., '3123' or 'A2301')"),
    journey_date: date = Query(..., description="Date of journey (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> TrackPredictionResponse:
    """
    Get ML-based platform prediction for a train at a station.

    Supports all stations with ML predictions enabled.
    Falls back to uniform distribution if model is unavailable.

    Args:
        station_code: Station code (e.g., 'NY', 'NP', 'TR')
        train_id: Train identifier
        journey_date: Date of the journey

    Returns:
        Platform prediction with probabilities and confidence
    """

    logger.info(
        "track_prediction_request_start",
        station_code=station_code,
        train_id=train_id,
        journey_date=journey_date,
    )

    # Check if station supports ML predictions
    if not station_has_ml_predictions(station_code):
        raise HTTPException(
            status_code=400,
            detail=f"Platform predictions not available for station {station_code}",
        )

    # Extract features
    feature_extractor = TrackPredictionFeatures()
    features = await feature_extractor.extract_features(
        db, station_code, train_id, journey_date
    )

    if not features:
        raise HTTPException(
            status_code=404,
            detail=f"Train {train_id} not found for date {journey_date}",
        )

    # Generate prediction with timing
    import time

    prediction_start = time.time()
    prediction = await track_predictor.predict(db, station_code, features)
    prediction_duration = time.time() - prediction_start

    logger.info(
        "ml_prediction_timing",
        station_code=station_code,
        train_id=train_id,
        prediction_duration_ms=round(prediction_duration * 1000, 2),
    )

    if not prediction:
        # Fallback: return uniform distribution
        logger.warning(
            "prediction_fallback_used",
            station_code=station_code,
            train_id=train_id,
            reason="ml_model_failed",
        )

        # Get station-specific default platforms
        config = get_station_config(station_code)
        tracks = config.get("tracks", [])

        # Convert tracks to platforms
        default_platforms = []
        seen_platforms = set()
        for track in tracks:
            platform = get_platform_for_track(station_code, track)
            if platform not in seen_platforms:
                default_platforms.append(platform)
                seen_platforms.add(platform)

        if not default_platforms:
            # Shouldn't happen but fallback to single platform
            default_platforms = ["1"]

        uniform_prob = 1.0 / len(default_platforms)

        logger.info(
            "fallback_prediction_returned",
            station_code=station_code,
            train_id=train_id,
            fallback_confidence=uniform_prob,
            platforms_count=len(default_platforms),
        )

        # Pick reasonable defaults for top 3
        top_3 = (
            default_platforms[:3] if len(default_platforms) >= 3 else default_platforms
        )

        return TrackPredictionResponse(
            platform_probabilities={
                platform: uniform_prob for platform in default_platforms
            },
            primary_prediction=default_platforms[0],
            confidence=uniform_prob,
            top_3=top_3,
            model_version="fallback",
            station_code=station_code,
            train_id=train_id,
            features_used=None,
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
        prediction_distribution={
            platform: round(prob, 3)
            for platform, prob in sorted(
                prediction["platform_probabilities"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
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
    """
    Get list of stations that support ML track predictions.

    Returns information about which stations have ML predictions available,
    allowing clients to show/hide prediction features appropriately.
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
        "JA": "Jamaica",
    }

    stations = []
    ml_enabled_count = 0

    for code, config in STATION_ML_CONFIGS.items():
        if code == "_default":
            continue

        ml_enabled = config.get("ml_enabled", False)
        if ml_enabled:
            ml_enabled_count += 1

        stations.append(
            StationMLSupport(
                code=code,
                name=STATION_NAMES.get(code, code),
                ml_predictions_available=ml_enabled,
                track_count=len(get_tracks_for_station(code)) if ml_enabled else None,
            )
        )

    # Sort by station code
    stations.sort(key=lambda x: x.code)

    logger.info(
        "supported_stations_requested",
        total_stations=len(stations),
        ml_enabled=ml_enabled_count,
    )

    return SupportedStationsResponse(
        stations=stations, total_ml_enabled=ml_enabled_count
    )
