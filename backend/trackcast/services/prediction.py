"""
Prediction service for TrackCast.

This module provides the service that generates track predictions
for upcoming trains using the trained machine learning model.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy.orm import Session

from trackcast.db.models import PredictionData, Train
from trackcast.db.repository import PredictionDataRepository, TrainRepository
from trackcast.models.pipeline import TrackPredictionPipeline

logger = logging.getLogger(__name__)


# Define Prometheus metrics
MODEL_PREDICTION_ACCURACY = Gauge(
    "model_prediction_accuracy",
    "Prediction accuracy of the model by station",
    ["station"],
)
MODEL_INFERENCE_TIME = Histogram(
    "model_inference_time_seconds",
    "Inference time for model predictions by station",
    ["station"],
)
TRAINS_PROCESSED_TOTAL = Counter("trains_processed_total", "Total number of trains processed")
TRACK_PREDICTION_CONFIDENCE = Histogram(
    "track_prediction_confidence_ratio",
    "Distribution of track prediction confidence scores",
    ["station"],
)


class PredictionService:
    """Service that generates track predictions for upcoming trains."""

    def __init__(self, db_session: Session):
        """
        Initialize the prediction service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.session = db_session
        self.train_repo = TrainRepository(db_session)
        self.prediction_repo = PredictionDataRepository(db_session)
        # Station-specific model cache
        self.models = {}  # {station_code: model}
        self.model_infos = {}  # {station_code: model_info}

    def _load_model_for_station(self, station_code: str) -> bool:
        """
        Load the latest trained model for a specific station.

        Args:
            station_code: Station code to load model for

        Returns:
            True if model loaded successfully, False otherwise
        """
        try:
            # Find the latest model files for this station
            model_info = TrackPredictionPipeline.find_latest_model(station_code=station_code)
            if not model_info:
                logger.warning(
                    f"No trained model found for station {station_code}. Train a model first using: trackcast train-model --station {station_code}"
                )
                return False

            # If the model is already loaded for this station, check if it's the same version
            if (
                station_code in self.models
                and station_code in self.model_infos
                and self.model_infos[station_code]["version"] == model_info["version"]
                and self.model_infos[station_code]["timestamp"] == model_info["timestamp"]
            ):
                logger.debug(
                    f"Model already loaded for station {station_code} (version: {model_info['version']})"
                )
                return True

            # Load the model
            logger.info(
                f"Loading model for station {station_code}, version {model_info['version']} from {model_info['model_path']}"
            )
            model = TrackPredictionPipeline()
            model.load(
                model_path=model_info["model_path"],
                metadata_path=model_info["metadata_path"],
                scaler_path=model_info["scaler_path"],
            )

            # Store in cache
            self.models[station_code] = model
            self.model_infos[station_code] = model_info

            logger.info(
                f"Model loaded successfully for station {station_code} (version: {model_info['version']})"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading model for station {station_code}: {str(e)}")
            # Remove from cache if loading failed
            self.models.pop(station_code, None)
            self.model_infos.pop(station_code, None)
            return False

    def run_prediction(
        self,
        train_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        future_only: bool = False,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run a prediction cycle for trains needing predictions with optional filtering.

        Args:
            train_id: Filter to a specific train ID
            time_range: Filter to trains within a time range (start_time, end_time)
            future_only: If True, only predict for trains with future departure times

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        stats: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "model_version": None,
            "trains_processed": 0,
            "trains_predicted": 0,
            "trains_skipped": 0,
            "trains_failed": 0,
            "duration_ms": 0,
            "filters": {
                "train_id": train_id,
                "time_range": [t.isoformat() for t in time_range] if time_range else None,
                "future_only": future_only,
            },
        }
        # Type assertions for mypy to understand these are integers
        trains_processed = 0
        trains_predicted = 0
        trains_skipped = 0
        trains_failed = 0

        try:
            # Get trains that need predictions with filters
            logger.info(
                f"Retrieving trains that need predictions with filters: train_id={train_id}, time_range={time_range}, future_only={future_only}"
            )
            trains = self.train_repo.get_trains_needing_predictions(
                train_id=train_id, time_range=time_range, future_only=future_only
            )

            if not trains:
                logger.info("No trains found needing predictions")
                stats["duration_ms"] = int((time.time() - start_time) * 1000)
                return True, stats

            logger.info(f"Generating predictions for {len(trains)} trains")
            trains_processed = len(trains)
            TRAINS_PROCESSED_TOTAL.inc(len(trains))

            # Group trains by station for efficient model loading
            trains_by_station = {}
            for train in trains:
                station_code = train.origin_station_code
                if station_code not in trains_by_station:
                    trains_by_station[station_code] = []
                trains_by_station[station_code].append(train)

            # Process trains by station
            station_models_loaded = []
            for station_code, station_trains in trains_by_station.items():
                logger.info(f"Processing {len(station_trains)} trains for station {station_code}")

                # Load model for this station if not already loaded
                if not self._load_model_for_station(station_code):
                    logger.warning(
                        f"No model found for station {station_code}, skipping {len(station_trains)} trains. Train a model for this station first."
                    )
                    trains_skipped += len(station_trains)
                    continue

                station_models_loaded.append(station_code)

                # Process each train for this station
                for train in station_trains:
                    try:
                        # Skip trains without features
                        if not train.model_data:
                            logger.warning(f"Skipping train {train.train_id}: missing features")
                            trains_skipped += 1
                            continue

                        # Skip trains with existing predictions
                        if train.prediction_data:
                            logger.debug(
                                f"Skipping train {train.train_id}: already has predictions"
                            )
                            trains_skipped += 1
                            continue

                        # Generate prediction using station-specific model
                        prediction_result = self._predict_train(train)
                        if prediction_result:
                            trains_predicted += 1
                        else:
                            trains_failed += 1

                    except Exception as e:
                        logger.error(f"Error predicting train {train.train_id}: {str(e)}")
                        trains_failed += 1

            # Set model versions in stats (comma-separated list)
            model_versions = []
            for station_code in station_models_loaded:
                if station_code in self.model_infos:
                    model_versions.append(
                        f"{station_code}:{self.model_infos[station_code]['version']}"
                    )
            stats["model_versions"] = ", ".join(model_versions)

            # Update stats with final counts
            stats["trains_processed"] = trains_processed
            stats["trains_predicted"] = trains_predicted
            stats["trains_skipped"] = trains_skipped
            stats["trains_failed"] = trains_failed

            # Calculate duration
            stats["duration_ms"] = int((time.time() - start_time) * 1000)

            logger.info(
                f"Prediction cycle completed: {trains_predicted} predicted, "
                f"{trains_skipped} skipped, {trains_failed} failed "
                f"in {stats['duration_ms']}ms"
            )

            return trains_predicted > 0, stats

        except Exception as e:
            logger.error(f"Error in prediction cycle: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def predict_train_with_context(
        self, train_id: str, boarding_station_code: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate a prediction for a specific train using the boarding station's model.

        Args:
            train_id: Train ID to predict
            boarding_station_code: Station code for the boarding station (context)

        Returns:
            Tuple containing success status and result dictionary
        """
        start_time = time.time()
        result = {
            "timestamp": datetime.now().isoformat(),
            "train_id": train_id,
            "boarding_station_code": boarding_station_code,
            "success": False,
            "track_probabilities": None,
            "prediction_factors": None,
            "duration_ms": 0,
        }

        try:
            # Get train
            train = self.train_repo.get_train_by_id(train_id)

            if not train:
                logger.error(f"Train not found with ID {train_id}")
                result["error"] = f"Train not found with ID {train_id}"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Check if train already has a track assigned
            if train.track:
                logger.info(f"Train {train_id} already has track {train.track} assigned")
                result["success"] = True
                result["info"] = f"Train already has track {train.track} assigned"
                result["track"] = train.track
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return True, result

            # Check if train has features
            if not train.model_data:
                logger.error(f"Train {train_id} has no features. Process features first.")
                result["error"] = "Train has no features. Process features first."
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Load model for boarding station instead of origin station
            station_code = boarding_station_code
            if not self._load_model_for_station(station_code):
                result["error"] = f"Failed to load model for boarding station {station_code}"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Generate prediction using the boarding station model
            prediction_result = self._predict_train_with_station(train, station_code)

            if not prediction_result:
                result["error"] = "Context prediction failed"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Get the actual prediction data
            track_probs = prediction_result.track_probabilities
            prediction_factors = prediction_result.prediction_factors

            result["success"] = True
            result["track_probabilities"] = track_probs
            result["prediction_factors"] = prediction_factors
            result["prediction_data"] = prediction_result

            # Get the top predicted track
            if track_probs:
                top_track = max(track_probs.items(), key=lambda x: x[1])
                result["top_track"] = top_track[0]
                result["top_probability"] = float(top_track[1])

            result["model_version"] = self.model_infos[station_code]["version"]
            result["prediction_id"] = prediction_result.id
            result["duration_ms"] = int((time.time() - start_time) * 1000)

            return True, result

        except Exception as e:
            logger.error(
                f"Error predicting train {train_id} with context {boarding_station_code}: {str(e)}"
            )
            result["error"] = str(e)
            result["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, result

    def predict_train(self, train_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate a prediction for a specific train by ID.

        Args:
            train_id: Train ID to predict

        Returns:
            Tuple containing success status and result dictionary
        """
        start_time = time.time()
        result = {
            "timestamp": datetime.now().isoformat(),
            "train_id": train_id,
            "success": False,
            "track_probabilities": None,
            "prediction_factors": None,
            "duration_ms": 0,
        }

        try:
            # Get train
            train = self.train_repo.get_train_by_id(train_id)

            if not train:
                logger.error(f"Train not found with ID {train_id}")
                result["error"] = f"Train not found with ID {train_id}"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Check if train already has a track assigned
            if train.track:
                logger.info(f"Train {train_id} already has track {train.track} assigned")
                result["success"] = True
                result["info"] = f"Train already has track {train.track} assigned"
                result["track"] = train.track
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return True, result

            # Check if train has features
            if not train.model_data:
                logger.error(f"Train {train_id} has no features. Process features first.")
                result["error"] = "Train has no features. Process features first."
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Load model for train's origin station
            station_code = train.origin_station_code
            if not self._load_model_for_station(station_code):  # type: ignore[arg-type]
                result["error"] = f"Failed to load model for station {station_code}"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Generate prediction
            prediction_result = self._predict_train(train)

            if not prediction_result:
                result["error"] = "Prediction failed"
                result["duration_ms"] = int((time.time() - start_time) * 1000)
                return False, result

            # Get the actual prediction data
            track_probs = prediction_result.track_probabilities
            prediction_factors = prediction_result.prediction_factors

            result["success"] = True
            result["track_probabilities"] = track_probs
            result["prediction_factors"] = prediction_factors

            # Get the top predicted track
            if track_probs:
                top_track = max(track_probs.items(), key=lambda x: x[1])
                result["top_track"] = top_track[0]
                result["top_probability"] = float(top_track[1])

            result["model_version"] = self.model_infos[station_code]["version"]
            result["prediction_id"] = prediction_result.id
            result["duration_ms"] = int((time.time() - start_time) * 1000)

            return True, result

        except Exception as e:
            logger.error(f"Error predicting train {train_id}: {str(e)}")
            result["error"] = str(e)
            result["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, result

    def _predict_train(self, train: Train) -> Optional[PredictionData]:
        """
        Generate a prediction for a train and save to database.

        Args:
            train: Train object to predict

        Returns:
            PredictionData object if successful, None otherwise
        """
        try:
            # Get the model for this train's origin station
            station_code = train.origin_station_code
            if station_code not in self.models:
                logger.error(f"No model loaded for station {station_code}")
                return None

            model = self.models[station_code]
            model_info = self.model_infos[station_code]

            # Generate prediction
            inference_start_time = time.time()
            predictions = model.predict([train.model_data])
            inference_duration_seconds = time.time() - inference_start_time
            MODEL_INFERENCE_TIME.labels(station=station_code).observe(inference_duration_seconds)
            # TODO: Implement accuracy metric - requires comparing with actual track after departure
            # MODEL_PREDICTION_ACCURACY.labels(station=station_code).set(accuracy_value)

            if not predictions:
                logger.error(f"Model returned no predictions for train {train.train_id}")
                return None

            # Get the prediction for this train
            track_probabilities = predictions[0]

            # Check for empty predictions
            if not track_probabilities:
                logger.error(f"Model returned empty track probabilities for train {train.train_id}")
                return None

            # Log top predictions
            top_tracks = sorted(track_probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_tracks:
                TRACK_PREDICTION_CONFIDENCE.labels(station=station_code).observe(
                    top_tracks[0][1]  # Observe confidence of the top predicted track
                )
            logger.info(
                f"Top 3 predicted tracks for train {train.train_id} from {station_code}: {top_tracks}"
            )

            # Generate explanation factors
            try:
                prediction_factors = model.get_prediction_factors(train.model_data)
            except Exception as factor_error:
                logger.error(
                    f"Error generating prediction factors for train {train.train_id}: {str(factor_error)}"
                )
                prediction_factors = [
                    {
                        "feature": "error",
                        "importance": 0.0,
                        "direction": "neutral",
                        "explanation": f"Failed to generate explanation: {str(factor_error)}",
                    }
                ]

            # Create prediction data
            prediction_data = {
                "model_data_id": train.model_data_id,
                "track_probabilities": track_probabilities,
                "prediction_factors": prediction_factors,
                "model_version": model_info["version"],
            }

            # Save to database
            prediction = self.prediction_repo.create_prediction(prediction_data)

            # Associate with train
            train.prediction_data_id = prediction.id
            self.session.commit()

            logger.info(f"Created prediction for train {train.train_id}")
            return prediction

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error generating prediction for train {train.train_id}: {str(e)}")
            return None

    def _predict_train_with_station(
        self, train: Train, station_code: str
    ) -> Optional[PredictionData]:
        """
        Generate a prediction for a train using a specific station's model.

        Args:
            train: Train object to predict
            station_code: Station code for the model to use

        Returns:
            PredictionData object if successful, None otherwise
        """
        try:
            # Get the model for the specified station
            if station_code not in self.models:
                logger.error(f"No model loaded for station {station_code}")
                return None

            model = self.models[station_code]
            model_info = self.model_infos[station_code]

            # Generate prediction
            inference_start_time = time.time()
            predictions = model.predict([train.model_data])
            inference_duration_seconds = time.time() - inference_start_time
            MODEL_INFERENCE_TIME.labels(station=station_code).observe(inference_duration_seconds)
            # TODO: Implement accuracy metric - requires comparing with actual track after departure
            # MODEL_PREDICTION_ACCURACY.labels(station=station_code).set(accuracy_value)

            if not predictions:
                logger.error(f"Model returned no predictions for train {train.train_id}")
                return None

            # Get the prediction for this train
            track_probabilities = predictions[0]

            # Check for empty predictions
            if not track_probabilities:
                logger.error(f"Model returned empty track probabilities for train {train.train_id}")
                return None

            # Log top predictions
            top_tracks = sorted(track_probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_tracks:
                TRACK_PREDICTION_CONFIDENCE.labels(station=station_code).observe(
                    top_tracks[0][1]  # Observe confidence of the top predicted track
                )
            logger.info(
                f"Top 3 predicted tracks for train {train.train_id} using {station_code} model: {top_tracks}"
            )

            # Generate explanation factors
            try:
                prediction_factors = model.get_prediction_factors(train.model_data)
            except Exception as factor_error:
                logger.error(
                    f"Error generating prediction factors for train {train.train_id}: {str(factor_error)}"
                )
                prediction_factors = [
                    {
                        "feature": "error",
                        "importance": 0.0,
                        "direction": "neutral",
                        "explanation": f"Failed to generate explanation: {str(factor_error)}",
                    }
                ]

            # Create prediction data (don't save to database for context predictions)
            prediction_data = PredictionData(
                model_data_id=train.model_data_id,
                track_probabilities=track_probabilities,
                prediction_factors=prediction_factors,
                model_version=f"{model_info['version']}_{station_code}",
                created_at=datetime.now(),
            )

            logger.info(
                f"Generated context prediction for train {train.train_id} using {station_code} model"
            )
            return prediction_data

        except Exception as e:
            logger.error(
                f"Error generating context prediction for train {train.train_id} with station {station_code}: {str(e)}"
            )
            return None

    def run_prediction_with_regeneration(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run a prediction cycle for all trains needing predictions,
        first clearing any existing predictions for future trains to ensure regeneration.

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        now = datetime.now()
        end_time = now + timedelta(hours=24)  # Regenerate predictions for next 24 hours

        stats = {
            "timestamp": datetime.now().isoformat(),
            "model_versions": {},  # Changed to support multiple station models
            "regeneration": True,
            "predictions_cleared": 0,
            "trains_processed": 0,
            "trains_predicted": 0,
            "trains_skipped": 0,
            "trains_failed": 0,
            "duration_ms": 0,
        }

        try:
            # Clear predictions for future trains
            logger.info(
                f"Clearing predictions for trains from {now} to {end_time} for regeneration"
            )
            clear_stats = self.train_repo.clear_predictions_for_time_range(now, end_time)
            stats["predictions_cleared"] = clear_stats["predictions_deleted"]
            stats["trains_cleared"] = clear_stats["trains_cleared"]

            # Now run the normal prediction process which will include the trains we just cleared
            logger.info("Running normal prediction process to regenerate predictions")
            success, predict_stats = self.run_prediction()

            # Update stats with prediction results
            stats.update(
                {
                    "trains_processed": predict_stats.get("trains_processed", 0),
                    "trains_predicted": predict_stats.get("trains_predicted", 0),
                    "trains_skipped": predict_stats.get("trains_skipped", 0),
                    "trains_failed": predict_stats.get("trains_failed", 0),
                    "model_versions": predict_stats.get("model_versions", {}),
                    "duration_ms": int((time.time() - start_time) * 1000),
                }
            )

            if "error" in predict_stats:
                stats["error"] = predict_stats["error"]

            logger.info(
                f"Prediction regeneration completed: cleared {stats['predictions_cleared']} predictions, "
                f"regenerated {stats['trains_predicted']} in {stats['duration_ms']}ms"
            )

            return success, stats

        except Exception as e:
            logger.error(f"Error in prediction regeneration: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def clear_all_predictions(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Clear all predictions from the database.

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        stats = {
            "timestamp": datetime.now().isoformat(),
            "duration_ms": 0,
        }

        try:
            logger.info("Clearing all predictions from the database")
            clear_stats = self.train_repo.clear_all_predictions()

            # Update stats with clearing results
            stats.update(clear_stats)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)

            logger.info(
                f"Prediction clearing completed: {clear_stats['predictions_deleted']} predictions deleted "
                f"from {clear_stats['trains_cleared']} trains in {stats['duration_ms']}ms"
            )

            return True, stats

        except Exception as e:
            logger.error(f"Error clearing predictions: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def clear_predictions(
        self,
        train_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        future_only: bool = False,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Clear predictions with optional filtering.

        Args:
            train_id: Clear predictions for a specific train ID
            time_range: Clear predictions for trains within a time range
            future_only: If True, only clear predictions for future trains

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        stats = {
            "timestamp": datetime.now().isoformat(),
            "duration_ms": 0,
            "filters": {
                "train_id": train_id,
                "time_range": [t.isoformat() for t in time_range] if time_range else None,
                "future_only": future_only,
            },
        }

        try:
            # Determine which clearing method to use based on filters
            if train_id:
                logger.info(f"Clearing predictions for train {train_id}")
                clear_stats = self.train_repo.clear_predictions_for_train(train_id)
            elif time_range:
                start_time_range, end_time_range = time_range
                logger.info(
                    f"Clearing predictions for trains from {start_time_range} to {end_time_range}"
                )
                clear_stats = self.train_repo.clear_predictions_for_time_range(
                    start_time_range, end_time_range
                )
            elif future_only:
                logger.info("Clearing predictions for future trains")
                clear_stats = self.train_repo.clear_predictions_for_future_trains()
            else:
                logger.info("Clearing all predictions")
                clear_stats = self.train_repo.clear_all_predictions()

            # Update stats with clearing results
            stats.update(clear_stats)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)

            logger.info(
                f"Prediction clearing completed: {clear_stats.get('predictions_deleted', 0)} predictions deleted "
                f"from {clear_stats.get('trains_cleared', 0)} trains in {stats['duration_ms']}ms"
            )

            return True, stats

        except Exception as e:
            logger.error(f"Error clearing predictions: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def evaluate_performance(self, days: int = 7) -> Dict[str, Any]:
        """
        Evaluate prediction performance on recent data.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with evaluation metrics
        """
        from trackcast.models.training import evaluate_model_performance

        try:
            # Delegate to the training module's evaluation function
            return evaluate_model_performance(self.session, days)

        except Exception as e:
            logger.error(f"Error evaluating prediction performance: {str(e)}")
            return {"status": "error", "timestamp": datetime.now().isoformat(), "message": str(e)}
