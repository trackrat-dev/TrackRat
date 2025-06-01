import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import settings
from ..db.connection import SessionContext
from ..db.models import ModelData, PredictionData, Train
from .pytorch_model import PyTorchTrackPredictor
from .xgboost_model import XGBoostTrackPredictor

logger = logging.getLogger(__name__)


class ModelInference:
    """
    Handles model loading and inference for track predictions
    """

    def __init__(
        self,
        models_dir: Optional[str] = None,
        model_type: Optional[str] = None,
        model_version: Optional[str] = None,
    ):
        """
        Initialize the inference engine

        Args:
            models_dir: Directory where model files are stored
            model_type: Type of model to use ('pytorch' or 'xgboost')
            model_version: Specific model version to load
        """
        self.models_dir = models_dir or settings.get("model.save_path", "models/")
        self.model_type = model_type or settings.get("model.type", "pytorch")
        self.model_version = model_version or settings.get("model.version", "1.0.0")
        self.model = None

    def initialize(self) -> bool:
        """
        Load the latest model for inference

        Returns:
            True if model was successfully loaded, False otherwise
        """
        # Initialize the appropriate model type
        if self.model_type.lower() == "pytorch":
            self.model = PyTorchTrackPredictor(model_version=self.model_version)
        elif self.model_type.lower() == "xgboost":
            self.model = XGBoostTrackPredictor(model_version=self.model_version)
        else:
            logger.error(f"Unsupported model type: {self.model_type}")
            return False

        # Find the latest model of the requested version
        model_files = self.model.find_latest_model(self.models_dir, self.model_version)

        if not model_files:
            logger.error(
                f"No model files found for version {self.model_version} in {self.models_dir}"
            )
            return False

        try:
            # Load the model
            self.model.load_model(
                model_files["model_path"], model_files["metadata_path"], model_files["scaler_path"]
            )
            logger.info(f"Successfully loaded {self.model_type} model version {self.model_version}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

    def predict_tracks(self, model_data_list: List[ModelData]) -> List[Dict[str, Any]]:
        """
        Generate track predictions for a list of model data objects

        Args:
            model_data_list: List of ModelData objects to generate predictions for

        Returns:
            List of dictionaries containing track probabilities and prediction factors
        """
        if not self.model:
            raise ValueError("Model not initialized. Call initialize() first.")

        if not model_data_list:
            logger.warning("No model data provided for prediction")
            return []

        # Generate track probabilities
        try:
            track_probabilities = self.model.predict(model_data_list)

            # Generate prediction factors for each train
            results = []
            for i, model_data in enumerate(model_data_list):
                # Get prediction factors for this specific train
                prediction_factors = self.model.get_prediction_factors(model_data)

                results.append(
                    {
                        "model_data_id": model_data.id,
                        "track_probabilities": track_probabilities[i],
                        "prediction_factors": prediction_factors,
                        "model_version": self.model_version,
                        "model_type": self.model_type,
                    }
                )

            return results
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}")
            return []

    def generate_and_store_predictions(self, session, trains: List[Train]) -> Dict[str, Any]:
        """
        Generate predictions for a list of trains and store them in the database

        Args:
            session: Database session
            trains: List of Train objects to generate predictions for

        Returns:
            Dictionary containing prediction stats
        """
        if not self.model:
            raise ValueError("Model not initialized. Call initialize() first.")

        stats = {"total_trains": len(trains), "predictions_generated": 0, "errors": 0}

        # Collect model_data for each train
        train_model_data = []
        for train in trains:
            if train.model_data_id and train.model_data:
                train_model_data.append((train, train.model_data))
            else:
                logger.warning(f"Train {train.id} has no model data")
                stats["errors"] += 1

        # Generate predictions
        for train, model_data in train_model_data:
            try:
                # Generate prediction
                result = self.predict_tracks([model_data])[0]

                # Create a new PredictionData object
                prediction = PredictionData(
                    train_id=train.id,
                    model_data_id=model_data.id,
                    track_probabilities=result["track_probabilities"],
                    prediction_factors=result["prediction_factors"],
                    model_version=self.model_version,
                    created_at=datetime.now(),
                )

                # Add to database
                session.add(prediction)
                session.flush()  # To get the prediction ID

                # Update the train record
                train.prediction_data_id = prediction.id

                stats["predictions_generated"] += 1

            except Exception as e:
                logger.error(f"Error generating prediction for train {train.id}: {str(e)}")
                stats["errors"] += 1

        # Commit the session
        session.commit()

        logger.info(
            f"Generated {stats['predictions_generated']} predictions with {stats['errors']} errors"
        )
        return stats

    def generate_predictions_for_pending_trains(self) -> Dict[str, Any]:
        """
        Generate predictions for all trains that have model data but no predictions

        Returns:
            Dictionary containing prediction stats
        """
        with SessionContext() as session:
            # Find trains with model data but no predictions
            pending_trains = (
                session.query(Train)
                .filter(
                    Train.model_data_id.isnot(None),
                    Train.prediction_data_id.is_(None),
                    Train.track.is_(None),  # Only predict for trains without assigned tracks
                )
                .all()
            )

            logger.info(f"Found {len(pending_trains)} trains pending prediction")

            if not pending_trains:
                return {"total_trains": 0, "predictions_generated": 0, "errors": 0}

            return self.generate_and_store_predictions(session, pending_trains)

    def regenerate_all_predictions(self) -> Dict[str, Any]:
        """
        Regenerate predictions for all trains that have model data

        This is useful when updating the model version or type

        Returns:
            Dictionary containing prediction stats
        """
        with SessionContext() as session:
            # Find all trains with model data
            trains = session.query(Train).filter(Train.model_data_id.isnot(None)).all()

            logger.info(f"Found {len(trains)} trains for prediction regeneration")

            if not trains:
                return {"total_trains": 0, "predictions_generated": 0, "errors": 0}

            # Delete existing predictions for these trains
            train_ids = [train.id for train in trains]
            session.query(PredictionData).filter(PredictionData.train_id.in_(train_ids)).delete(
                synchronize_session=False
            )

            # Reset prediction_data_id in Train records
            for train in trains:
                train.prediction_data_id = None

            session.commit()

            return self.generate_and_store_predictions(session, trains)
