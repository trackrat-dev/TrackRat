"""
ML model loading and prediction service for platform predictions.

Handles loading trained models and generating platform predictions.
"""

import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.station_configs import (
    get_platform_for_track,
    get_station_config,
    station_has_ml_predictions,
)

logger = get_logger()


class TrackPredictor:
    """Singleton service for platform predictions."""

    _instance: Union["TrackPredictor", None] = None

    def __new__(cls) -> "TrackPredictor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the predictor (only runs once due to singleton)."""
        if not hasattr(self, "initialized") or not self.initialized:
            self.models: dict[str, Any] = {}
            self.encoders: dict[str, Any] = {}
            self.track_classes: dict[str, list[str]] = {}
            self.initialized: bool = True

            # Pre-load NY Penn model
            self.load_model("NY")

    def load_model(self, station_code: str) -> bool:
        """
        Load model for a specific station.

        Args:
            station_code: Station code (e.g., 'NY')

        Returns:
            True if model loaded successfully, False otherwise
        """

        # Check if station has ML enabled
        if not station_has_ml_predictions(station_code):
            logger.info("ml_not_enabled_for_station", station_code=station_code)
            return False

        # Model file paths
        base_path = Path("ml/models")

        # Use lowercase station code for file names
        model_prefix = station_code.lower()

        try:
            # Load model
            model_path = base_path / f"{model_prefix}_track_predictor.pkl"
            if not model_path.exists():
                logger.error("model_file_not_found", path=str(model_path))
                return False

            with open(model_path, "rb") as f:
                self.models[station_code] = pickle.load(f)

            # Load encoders
            encoders_path = base_path / f"{model_prefix}_label_encoders.pkl"
            if not encoders_path.exists():
                logger.error("encoders_file_not_found", path=str(encoders_path))
                return False

            with open(encoders_path, "rb") as f:
                self.encoders[station_code] = pickle.load(f)

            # Load track classes
            classes_path = base_path / f"{model_prefix}_track_classes.pkl"
            if not classes_path.exists():
                logger.error("classes_file_not_found", path=str(classes_path))
                return False

            with open(classes_path, "rb") as f:
                self.track_classes[station_code] = pickle.load(f)

            logger.info(
                "model_loaded",
                station_code=station_code,
                n_tracks=len(self.track_classes[station_code]),
            )

            return True

        except Exception as e:
            logger.error("model_load_error", station_code=station_code, error=str(e))
            return False

    async def predict(
        self, db: AsyncSession, station_code: str, features: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Generate platform prediction from features.

        Args:
            station_code: Station code (e.g., 'NY')
            features: Dictionary of features from TrackPredictionFeatures

        Returns:
            Dictionary with:
            - platform_probabilities: Dict mapping platform -> probability
            - primary_prediction: Most likely platform
            - confidence: Confidence score (0-1)
            - top_3: List of top 3 most likely platforms
            - features_used: Features that were used (for debugging)
        """

        # Check if model is loaded
        if station_code not in self.models:
            if not self.load_model(station_code):
                logger.error("model_not_available", station_code=station_code)
                return None

        try:
            # Get model and encoders
            model = self.models[station_code]
            encoders = self.encoders[station_code]
            track_classes = self.track_classes[station_code]

            # Encode categorical features
            line_code = features.get("line_code", "UNKNOWN")
            destination = features.get("destination", "UNKNOWN")

            # Handle unknown values with logging
            if line_code not in encoders["line_code"].classes_:
                line_code_encoded = -1  # Unknown line
                logger.info(
                    "unknown_line_code_encountered",
                    station_code=station_code,
                    line_code=line_code,
                    known_lines=list(encoders["line_code"].classes_)[
                        :5
                    ],  # First 5 for brevity
                )
            else:
                line_code_encoded = encoders["line_code"].transform([line_code])[0]

            if destination not in encoders["destination"].classes_:
                destination_encoded = -1  # Unknown destination
                logger.info(
                    "unknown_destination_encountered",
                    station_code=station_code,
                    destination=destination,
                    known_destinations_count=len(encoders["destination"].classes_),
                )
            else:
                destination_encoded = encoders["destination"].transform([destination])[
                    0
                ]

            # Get track usage times for averaging
            track_times = features.get("minutes_since_track_used", {})

            if track_times:
                avg_track_time = np.mean(list(track_times.values()))
            else:
                avg_track_time = -1  # Unknown

            # Prepare feature vector with 6 features only
            feature_list = [
                features["hour_of_day"],
                features["day_of_week"],
                features["is_amtrak"],
                line_code_encoded,
                destination_encoded,
                avg_track_time,
            ]

            feature_vector = np.array([feature_list])

            # Get raw ML predictions (now predicting tracks)
            probabilities = model.predict_proba(feature_vector)[0]
            track_classes = self.track_classes[station_code]  # Now contains tracks

            # Create track probability dictionary
            raw_track_probs = {}
            for i, track in enumerate(track_classes):
                raw_track_probs[track] = float(probabilities[i])

            # Filter occupied tracks and aggregate to platforms
            scheduled_departure = features["scheduled_departure"]
            final_platform_probs = await self._predict_with_track_filtering(
                db, raw_track_probs, station_code, scheduled_departure
            )

            # Sort by probability
            sorted_platforms = sorted(
                final_platform_probs.items(), key=lambda x: x[1], reverse=True
            )

            # Get top predictions
            primary_prediction = sorted_platforms[0][0]
            confidence = sorted_platforms[0][1]
            top_3 = [platform for platform, _ in sorted_platforms[:3]]

            # Prepare response
            result = {
                "platform_probabilities": final_platform_probs,
                "primary_prediction": primary_prediction,
                "confidence": confidence,
                "top_3": top_3,
                "model_version": "1.0.0",
                "features_used": {
                    "hour_of_day": features["hour_of_day"],
                    "day_of_week": features["day_of_week"],
                    "is_amtrak": features["is_amtrak"],
                    "line_code": line_code,
                    "destination": destination,
                    "avg_minutes_since_track_used": avg_track_time,
                    "track_data_points": len(track_times),
                },
            }

            # Enhanced logging for prediction performance
            logger.info(
                "prediction_generated",
                station_code=station_code,
                primary_prediction=primary_prediction,
                confidence=confidence,
                top_3_platforms=top_3,
                platform_probabilities=final_platform_probs,
                model_version="1.0.0",
            )

            # Log confidence level category
            if confidence >= 0.8:
                confidence_level = "high"
            elif confidence >= 0.5:
                confidence_level = "medium"
            else:
                confidence_level = "low"

            logger.info(
                "prediction_confidence_assessment",
                station_code=station_code,
                confidence_level=confidence_level,
                confidence_score=confidence,
                margin_to_second=(
                    confidence - sorted_platforms[1][1]
                    if len(sorted_platforms) > 1
                    else 0
                ),
            )

            return result

        except Exception as e:
            logger.error("prediction_error", station_code=station_code, error=str(e))
            return None

    async def _predict_with_track_filtering(
        self,
        db: AsyncSession,
        raw_track_probs: dict[str, float],
        station_code: str,
        scheduled_departure: datetime,
    ) -> dict[str, float]:
        """
        Filter occupied tracks and aggregate remaining tracks to platforms.

        Args:
            db: Database session
            raw_track_probs: ML predictions for individual tracks
            station_code: Station code (e.g., 'NY')
            scheduled_departure: Scheduled departure time for occupancy check

        Returns:
            Platform probabilities after filtering and aggregation
        """
        # Get occupied tracks
        occupied_tracks = await self._get_occupied_tracks(
            db, station_code, scheduled_departure
        )

        # Filter out occupied tracks (convert track to string for comparison)
        available_track_probs = {}
        for track, probability in raw_track_probs.items():
            track_str = str(track)
            if track_str not in occupied_tracks:
                available_track_probs[track] = probability

        # Renormalize track probabilities to sum to 100%
        total_track_prob = sum(available_track_probs.values())
        if total_track_prob > 0:
            available_track_probs = {
                t: prob / total_track_prob for t, prob in available_track_probs.items()
            }
        else:
            # All tracks occupied - return uniform distribution of available tracks
            track_count = len(raw_track_probs)
            available_track_probs = {t: 1.0 / track_count for t in raw_track_probs}
            logger.warning(
                "all_tracks_occupied_fallback",
                station_code=station_code,
                scheduled_departure=scheduled_departure,
                occupied_tracks=list(occupied_tracks),
            )

        # Aggregate tracks to platforms
        platform_probs = self._aggregate_tracks_to_platforms(
            available_track_probs, station_code
        )

        # Log filtering and aggregation results
        filtered_count = len(raw_track_probs) - len(available_track_probs)
        logger.info(
            "track_filtering_and_aggregation",
            station_code=station_code,
            original_tracks=len(raw_track_probs),
            filtered_tracks=filtered_count,
            available_tracks=len(available_track_probs),
            final_platforms=len(platform_probs),
            occupied_tracks=sorted(occupied_tracks),
        )

        return platform_probs

    def _aggregate_tracks_to_platforms(
        self, track_probs: dict[str, float], station_code: str
    ) -> dict[str, float]:
        """
        Aggregate individual track probabilities into platform probabilities.

        Args:
            track_probs: Dictionary of track -> probability
            station_code: Station code (e.g., 'NY')

        Returns:
            Dictionary of platform -> aggregated probability
        """
        platform_probs = {}

        for track, probability in track_probs.items():
            # Get platform for this track (convert track to string)
            track_str = str(track)
            platform = self._get_platform_for_track(station_code, track_str)

            # Add probability to platform total
            if platform not in platform_probs:
                platform_probs[platform] = 0.0
            platform_probs[platform] += probability

        return platform_probs

    async def _get_occupied_tracks(
        self, db: AsyncSession, station_code: str, scheduled_departure: datetime
    ) -> set[str]:
        """Get set of occupied track numbers."""
        from datetime import timedelta

        from sqlalchemy import and_, select

        from trackrat.models.database import JourneyStop, TrainJourney

        # Use same 12-minute window as before
        window_start = scheduled_departure - timedelta(minutes=10)
        window_end = scheduled_departure + timedelta(minutes=2)

        stmt = (
            select(JourneyStop.track)
            .join(TrainJourney)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    JourneyStop.track.isnot(None),
                    JourneyStop.track != "",
                    JourneyStop.scheduled_departure >= window_start,
                    JourneyStop.scheduled_departure <= window_end,
                    TrainJourney.is_expired == False,  # noqa: E712
                    TrainJourney.is_cancelled == False,  # noqa: E712
                )
            )
        )

        result = await db.execute(stmt)
        return {row.track for row in result}

    def _get_platform_for_track(self, station_code: str, track: str) -> str:
        """Get platform name for a given track number."""
        # Use centralized configuration
        return get_platform_for_track(station_code, track)

    def _get_tracks_for_platform(self, station_code: str, platform: str) -> list[str]:
        """Get track numbers for a given platform."""
        config = get_station_config(station_code)

        if config["platform_mappings"]:
            # Station has platform mappings - find tracks for this platform
            tracks = []
            for track, plat in config["platform_mappings"].items():
                if plat == platform:
                    tracks.append(track)
            return tracks if tracks else [platform]
        else:
            # No platform mappings - platform is a single track
            return [platform]


# Global instance
track_predictor = TrackPredictor()
