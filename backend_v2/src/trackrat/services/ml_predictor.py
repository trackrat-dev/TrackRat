"""
ML model loading and prediction service for platform predictions.

Handles loading trained models and generating platform predictions.
"""

import pickle
from pathlib import Path
from typing import Any, Union

import numpy as np
from structlog import get_logger

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
            self.platform_classes: dict[str, list[str]] = {}
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

        # Model file paths
        base_path = Path("ml/models")

        # Map station codes to model file prefixes
        model_prefix = {"NY": "ny"}.get(station_code)

        if not model_prefix:
            logger.warning("no_model_for_station", station_code=station_code)
            return False

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

            # Load platform classes
            classes_path = base_path / f"{model_prefix}_track_classes.pkl"
            if not classes_path.exists():
                logger.error("classes_file_not_found", path=str(classes_path))
                return False

            with open(classes_path, "rb") as f:
                self.platform_classes[station_code] = pickle.load(f)

            logger.info(
                "model_loaded",
                station_code=station_code,
                n_platforms=len(self.platform_classes[station_code]),
            )

            return True

        except Exception as e:
            logger.error("model_load_error", station_code=station_code, error=str(e))
            return False

    def predict(
        self, station_code: str, features: dict[str, Any]
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
            platform_classes = self.platform_classes[station_code]

            # Encode categorical features
            line_code = features.get("line_code", "UNKNOWN")
            destination = features.get("destination", "UNKNOWN")

            # Handle unknown values
            if line_code not in encoders["line_code"].classes_:
                line_code_encoded = -1  # Unknown line
            else:
                line_code_encoded = encoders["line_code"].transform([line_code])[0]

            if destination not in encoders["destination"].classes_:
                destination_encoded = -1  # Unknown destination
            else:
                destination_encoded = encoders["destination"].transform([destination])[
                    0
                ]

            # Get track usage times
            track_times = features.get("minutes_since_track_used", {})
            platform_times = features.get("minutes_since_platform_used", {})

            # For now, use average time since any track was used
            # In the future, we could use track-specific times
            if track_times:
                avg_track_time = np.mean(list(track_times.values()))
            else:
                avg_track_time = -1  # Unknown

            if platform_times:
                avg_platform_time = np.mean(list(platform_times.values()))
            else:
                avg_platform_time = -1  # Unknown

            # Prepare feature vector
            feature_vector = np.array(
                [
                    [
                        features["hour_of_day"],
                        features["day_of_week"],
                        features["is_amtrak"],
                        line_code_encoded,
                        destination_encoded,
                        avg_track_time,
                        avg_platform_time,
                    ]
                ]
            )

            # Get predictions
            probabilities = model.predict_proba(feature_vector)[0]

            # Create platform probability dictionary
            platform_probs = {}
            for i, platform in enumerate(platform_classes):
                platform_probs[platform] = float(probabilities[i])

            # Sort by probability
            sorted_platforms = sorted(
                platform_probs.items(), key=lambda x: x[1], reverse=True
            )

            # Get top predictions
            primary_prediction = sorted_platforms[0][0]
            confidence = sorted_platforms[0][1]
            top_3 = [platform for platform, _ in sorted_platforms[:3]]

            # Prepare response
            result = {
                "platform_probabilities": platform_probs,
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
                    "avg_minutes_since_platform_used": avg_platform_time,
                },
            }

            logger.info(
                "prediction_generated",
                station_code=station_code,
                primary_prediction=primary_prediction,
                confidence=confidence,
            )

            return result

        except Exception as e:
            logger.error("prediction_error", station_code=station_code, error=str(e))
            return None


# Global instance
track_predictor = TrackPredictor()
