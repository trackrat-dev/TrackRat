import abc
import logging
import os
from typing import Any, Dict, List, Optional

from ..db.models import ModelData

logger = logging.getLogger(__name__)


class BaseTrackPredictor(abc.ABC):
    """Abstract base class for track prediction models"""

    @abc.abstractmethod
    def train(
        self,
        train_model_data: List[ModelData],
        train_tracks: List[str],
        val_model_data: Optional[List[ModelData]] = None,
        val_tracks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Train the model on prepared feature data.

        Args:
            train_model_data: List of ModelData objects for training set
            train_tracks: List of track values corresponding to train_model_data
            val_model_data: Optional list of ModelData objects for validation set
            val_tracks: Optional list of track values corresponding to val_model_data

        Returns:
            Dict containing training statistics and metrics
        """
        pass

    @abc.abstractmethod
    def predict(self, model_data: List[ModelData]) -> List[Dict[str, float]]:
        """
        Generate track probabilities for new data.

        Args:
            model_data: List of ModelData objects to generate predictions for

        Returns:
            List of dictionaries mapping track IDs to their probabilities
        """
        pass

    @abc.abstractmethod
    def get_prediction_factors(self, model_data: ModelData) -> List[Dict[str, Any]]:
        """
        Generate explanation factors for a prediction.

        Args:
            model_data: ModelData object to explain prediction for

        Returns:
            List of dictionaries containing feature importance details
        """
        pass

    @abc.abstractmethod
    def _save_model(self) -> str:
        """
        Save the model to disk.

        Returns:
            Path to the saved model
        """
        pass

    @abc.abstractmethod
    def load_model(
        self, model_path: str, metadata_path: str, scaler_path: Optional[str] = None
    ) -> None:
        """
        Load a trained model from disk.

        Args:
            model_path: Path to the saved model file
            metadata_path: Path to the model metadata file
            scaler_path: Optional path to the feature scaler
        """
        pass

    def find_latest_model(
        self, models_dir: str, version: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Find the latest saved model in the models directory.

        Args:
            models_dir: Directory containing model files
            version: Optional version string to filter models

        Returns:
            Dictionary with paths to model, metadata, and scaler files,
            or None if no model is found
        """
        if not os.path.exists(models_dir):
            logger.warning(f"Models directory {models_dir} does not exist")
            return None

        # Look for model files matching pattern
        model_files = [f for f in os.listdir(models_dir) if f.startswith("track_pred_model_")]

        # Filter by version if specified
        if version:
            model_files = [f for f in model_files if version in f]

        if not model_files:
            logger.warning(f"No model files found in {models_dir}")
            return None

        # Sort by timestamp (assuming filename format includes timestamp)
        model_files.sort(reverse=True)
        latest_model = model_files[0]

        # Construct corresponding metadata and scaler paths
        model_base = latest_model.replace("track_pred_model_", "")
        metadata_file = f"metadata_{model_base}"
        scaler_file = f"scaler_{model_base}"

        # Check if files exist
        metadata_path = os.path.join(models_dir, metadata_file)
        scaler_path = os.path.join(models_dir, scaler_file)
        model_path = os.path.join(models_dir, latest_model)

        if not os.path.exists(metadata_path):
            logger.warning(f"Metadata file {metadata_path} not found")
            return None

        return {
            "model_path": model_path,
            "metadata_path": metadata_path,
            "scaler_path": scaler_path if os.path.exists(scaler_path) else None,
        }
