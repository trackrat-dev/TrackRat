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

    Currently only supports NY Penn Station (station_code='NY').
    Falls back to uniform distribution if model is unavailable.

    Args:
        station_code: Station code (currently only 'NY' supported)
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

    # Currently only support NY Penn Station
    if station_code != "NY":
        raise HTTPException(
            status_code=400,
            detail=f"Platform predictions not available for station {station_code}. Only 'NY' is currently supported.",
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

        # Default platforms for NY Penn
        default_platforms = [
            "1 & 2",
            "3 & 4",
            "5 & 6",
            "7 & 8",
            "9 & 10",
            "11 & 12",
            "13 & 14",
            "15 & 16",
            "17",
            "18 & 19",
            "20 & 21",
        ]
        uniform_prob = 1.0 / len(default_platforms)

        logger.info(
            "fallback_prediction_returned",
            station_code=station_code,
            train_id=train_id,
            fallback_confidence=uniform_prob,
            platforms_count=len(default_platforms),
        )

        return TrackPredictionResponse(
            platform_probabilities={
                platform: uniform_prob for platform in default_platforms
            },
            primary_prediction="7 & 8",  # Most common platform
            confidence=uniform_prob,
            top_3=["7 & 8", "9 & 10", "11 & 12"],
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
