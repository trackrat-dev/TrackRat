"""
Pipeline for track prediction using PyTorch neural networks.
"""

import logging
import os
import pickle
import json
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.preprocessing import StandardScaler

from ..constants import MODEL_SAVE_PATH

logger = logging.getLogger(__name__)


class TrackPredictor(nn.Module):
    """Feed-forward neural network for track prediction."""
    
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(TrackPredictor, self).__init__()
        self.features = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
        self.temperature = nn.Parameter(torch.ones(1) * 1.0)
    
    def forward(self, x, apply_softmax=True, apply_temperature=False):
        """Forward pass with options for temperature scaling and softmax"""
        logits = self.features(x)
        
        if apply_temperature:
            logits = logits / self.temperature
            
        if apply_softmax:
            return F.softmax(logits, dim=1)
        else:
            return logits
    
    def calibrate(self, val_loader, criterion, device='cpu'):
        """
        Tune the temperature parameter on validation data to improve probability calibration.
        This is done after the main training is complete.
        """
        import torch.optim as optim
        
        self.eval()  # Set to evaluation mode
        
        # Create a temperature optimization criterion and optimizer
        # We optimize only the temperature parameter
        optimizer = optim.LBFGS([self.temperature], lr=0.01, max_iter=50)
        
        # Define the temperature scaling loss
        def eval_fn():
            optimizer.zero_grad()
            loss = 0
            batch_count = 0
            
            # We need gradients for temperature but not for model parameters
            for inputs, targets in val_loader:
                inputs = inputs.to(device)
                targets = targets.to(device)
                
                # Get raw logits (no softmax) - no gradient needed for logits
                with torch.no_grad():
                    logits = self.features(inputs)
                
                # Apply temperature scaling - WITH gradient for temperature
                scaled_logits = logits / self.temperature
                
                # Calculate loss
                batch_loss = criterion(scaled_logits, targets)
                loss += batch_loss * inputs.size(0)
                batch_count += inputs.size(0)
            
            loss = loss / batch_count
            loss.backward()
            return loss
        
        # Optimize the temperature parameter
        optimizer.step(eval_fn)
        
        # Make sure temperature is positive
        self.temperature.data.clamp_(min=0.01)
        
        logger.info(f"Temperature scaling parameter: {self.temperature.item():.4f}")
        return self.temperature.item()


class TrackPredictionPipeline:
    """
    Pipeline for predicting train tracks using PyTorch neural networks.
    """

    def __init__(self, model_version=None):
        """Initialize the pipeline."""
        logger.info("Initializing track prediction pipeline")
        self.model_version = model_version
        self.model = None
        self.metadata = None
        self.scaler = None
        self.track_to_idx = {}
        self.idx_to_track = {}
        self.feature_columns = []

    @classmethod
    def find_latest_model(cls, station_code: Optional[str] = None):
        """
        Find the latest trained model files.
        
        Args:
            station_code: Optional station code to find station-specific model
            
        Returns:
            Dict with model file paths and metadata, or None if no model found
        """
        if station_code:
            logger.info(f"Looking for latest trained model for station {station_code}")
        else:
            logger.info("Looking for latest trained model")
        
        # Look in both MODEL_SAVE_PATH and main models directory
        search_dirs = [
            Path(MODEL_SAVE_PATH),
            Path("models"),
            Path("models/saved")
        ]
        
        latest_model = None
        latest_time = 0
        
        for model_dir in search_dirs:
            if not model_dir.exists():
                continue
                
            # Look for PyTorch model files (*.pt)
            if station_code:
                # Station-specific model pattern: track_pred_model_VERSION_STATIONCODE_TIMESTAMP.pt
                model_files = list(model_dir.glob(f"track_pred_model_*_{station_code}_*.pt"))
            else:
                # Legacy combined model pattern (no station code)
                model_files = []
                for f in model_dir.glob("track_pred_model_*.pt"):
                    # Exclude station-specific models when looking for combined model
                    stem = f.stem
                    parts = stem.split('_')
                    # Check if this looks like a station-specific model
                    if len(parts) >= 6 and parts[4].isupper() and len(parts[4]) <= 3:
                        continue  # Skip station-specific models
                    model_files.append(f)
            
            for model_file in model_files:
                mtime = model_file.stat().st_mtime
                if mtime > latest_time:
                    latest_time = mtime
                    latest_model = model_file
        
        if not latest_model:
            if station_code:
                logger.info(f"No PyTorch model files found for station {station_code}")
            else:
                logger.info("No PyTorch model files found")
            return None
        
        # Extract version and timestamp from filename
        stem = latest_model.stem  # removes .pt extension
        parts = stem.split('_')
        
        if station_code and len(parts) >= 6:
            # Station-specific format: track_pred_model_VERSION_STATIONCODE_TIMESTAMP.pt
            version = parts[3]
            timestamp = parts[5] if len(parts) > 5 else "unknown"
            version_key = f"{version}_{station_code}"
        elif len(parts) >= 5:
            # Legacy format: track_pred_model_VERSION_TIMESTAMP.pt
            version = parts[3]
            timestamp = parts[4]
            version_key = version
        else:
            version = "1.0.0"
            timestamp = "unknown"
            version_key = version
        
        # Build paths for associated files
        model_dir = latest_model.parent
        metadata_path = model_dir / f"metadata_{version_key}_{timestamp}.json"
        scaler_path = model_dir / f"scaler_{version_key}_{timestamp}.pkl"
        
        # Check if metadata exists
        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            return None
        
        model_info = {
            "model_path": str(latest_model),
            "metadata_path": str(metadata_path),
            "scaler_path": str(scaler_path) if scaler_path.exists() else None,
            "timestamp": timestamp,
            "version": version_key if station_code else version,
            "station_code": station_code
        }
        
        logger.info(f"Found latest model: {latest_model}")
        return model_info

    def load(self, model_path: str, metadata_path: str = None, scaler_path: str = None) -> None:
        """
        Load the PyTorch model and associated files.
        
        Args:
            model_path: Path to the PyTorch model file (.pt)
            metadata_path: Path to the metadata file
            scaler_path: Path to the scaler file
        """
        logger.info(f"Loading PyTorch model from {model_path}")
        
        # Load metadata first to get model architecture
        if metadata_path and os.path.exists(metadata_path):
            logger.info(f"Loading metadata from {metadata_path}")
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
                self.model_version = self.metadata.get("model_version", "1.0.0")
                self.track_to_idx = self.metadata.get("track_to_idx", {})
                self.idx_to_track = self.metadata.get("idx_to_track", {})
                self.feature_columns = self.metadata.get("feature_columns", [])
        else:
            logger.error(f"Metadata file required but not found: {metadata_path}")
            raise FileNotFoundError(f"Metadata file required: {metadata_path}")
        
        # Get model architecture from metadata
        input_dim = self.metadata.get("input_dim", 182)
        hidden_dims = self.metadata.get("hidden_dims", [128, 64, 32])
        output_dim = self.metadata.get("output_dim", 17)
        
        # For now, use the first hidden dimension (compatible with original model.py)
        hidden_dim = hidden_dims[0] if hidden_dims else 64
        
        # Create model instance with correct architecture
        self.model = TrackPredictor(input_dim, hidden_dim, output_dim)
        
        # Load the model state
        try:
            state_dict = torch.load(model_path, map_location='cpu')
            self.model.load_state_dict(state_dict)
            self.model.eval()  # Set to evaluation mode
            logger.info("PyTorch model loaded successfully")
            
            # Load temperature parameter if available in metadata
            if self.metadata and "temperature" in self.metadata:
                temperature_value = self.metadata["temperature"]
                self.model.temperature.data = torch.tensor([temperature_value])
                logger.info(f"Loaded temperature parameter: {temperature_value}")
            
        except Exception as e:
            logger.error(f"Error loading PyTorch model: {e}")
            raise
        
        # Load scaler if provided
        if scaler_path and os.path.exists(scaler_path):
            logger.info(f"Loading scaler from {scaler_path}")
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
        else:
            logger.warning("No scaler found - predictions may be inaccurate")
        
        logger.info("Model pipeline loaded successfully")

    def _prepare_features(self, features) -> np.ndarray:
        """
        Prepare features for model input.
        
        Args:
            features: Dict of feature values or numpy array
            
        Returns:
            Scaled numpy array ready for model input
        """
        if isinstance(features, dict):
            # Convert dict to array using feature column order
            if not self.feature_columns:
                logger.error("Feature columns not available from metadata")
                raise ValueError("Feature columns not available")
            
            feature_array = np.array([
                features.get(col, 0.0) for col in self.feature_columns
            ]).reshape(1, -1)
        elif hasattr(features, 'to_dict'):
            # Handle ModelData objects directly
            features_dict = features.to_dict()
            if not self.feature_columns:
                logger.error("Feature columns not available from metadata")
                raise ValueError("Feature columns not available")
            
            feature_array = np.array([
                features_dict.get(col, 0.0) for col in self.feature_columns
            ]).reshape(1, -1)
        else:
            # Assume it's already a numpy array or list
            feature_array = np.array(features)
            if feature_array.ndim == 1:
                feature_array = feature_array.reshape(1, -1)
        
        # Apply scaling if scaler is available
        if self.scaler:
            feature_array = self.scaler.transform(feature_array)
        
        return feature_array

    def predict(self, features):
        """
        Make track predictions based on input features.
        
        Args:
            features: Dict of feature values for single prediction, or list of dicts for batch
            
        Returns:
            Dict mapping track names to probabilities (single), or list of such dicts (batch)
        """
        if not self.model:
            logger.error("Model not loaded. Call load() first.")
            raise RuntimeError("Model not loaded")
        
        logger.debug("Making track prediction with PyTorch model")
        
        # Handle batch prediction
        if isinstance(features, list):
            logger.info(f"Making batch predictions for {len(features)} samples")
            return [self.predict(f) for f in features]
        
        # Prepare features
        try:
            feature_array = self._prepare_features(features)
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            # Return uniform distribution as fallback
            uniform_prob = 1.0 / len(self.track_to_idx) if self.track_to_idx else 0.25
            return {track: uniform_prob for track in self.track_to_idx.keys()} or {"1": 0.25, "2": 0.25, "3": 0.25, "4": 0.25}
        
        # Convert to torch tensor
        feature_tensor = torch.tensor(feature_array, dtype=torch.float32)
        
        # Make prediction
        with torch.no_grad():
            # Use temperature scaling and softmax for final predictions
            probabilities = self.model(feature_tensor, apply_softmax=True, apply_temperature=True)
            probs_array = probabilities.numpy()[0]  # Get first (and only) sample
        
        # Map probabilities to track names
        track_probs = {}
        for idx_str, track in self.idx_to_track.items():
            idx = int(idx_str)
            if idx < len(probs_array):
                track_probs[track] = float(probs_array[idx])
        
        return track_probs

    def get_prediction_factors(self, features: Dict[str, Any], use_perturbation=True) -> List[Dict[str, Any]]:
        """
        Generate explanation factors for predictions using feature importance analysis.
        
        Args:
            features: Dict of feature values
            use_perturbation: If True, use perturbation-based feature importance like model.py
            
        Returns:
            List of dicts containing explanation factors
        """
        logger.debug("Generating prediction explanation factors")
        
        if not self.model or not use_perturbation:
            # Fallback to simple heuristic approach
            return self._get_heuristic_factors()
        
        try:
            # Prepare features for model input
            feature_array = self._prepare_features(features)
            feature_tensor = torch.tensor(feature_array, dtype=torch.float32)
            
            # Get baseline prediction
            with torch.no_grad():
                baseline_pred = self.model(feature_tensor, apply_softmax=True, apply_temperature=True)
                baseline_probs = baseline_pred.numpy()[0]
                predicted_track_idx = np.argmax(baseline_probs)
            
            # Calculate feature importance using perturbation (like model.py)
            num_features = feature_array.shape[1]
            feature_importances = np.zeros(num_features)
            baseline_prob = baseline_probs[predicted_track_idx]
            
            for feat_idx in range(num_features):
                # Create perturbed sample
                perturbed_sample = feature_array[0].copy()
                perturbed_sample[feat_idx] = 0  # Set feature to zero (perturbation)
                
                # Get prediction with perturbed feature
                perturbed_tensor = torch.tensor(perturbed_sample.reshape(1, -1), dtype=torch.float32)
                with torch.no_grad():
                    perturbed_pred = self.model(perturbed_tensor, apply_softmax=True, apply_temperature=True)
                    perturbed_prob = perturbed_pred.numpy()[0, predicted_track_idx]
                
                # Calculate importance as difference in prediction probability
                feature_importances[feat_idx] = baseline_prob - perturbed_prob
            
            # Get top important features
            if hasattr(self, 'feature_columns') and self.feature_columns:
                feature_names = self.feature_columns
            else:
                feature_names = [f"feature_{i}" for i in range(num_features)]
            
            # Pair features with importance and sort by absolute importance
            factor_pairs = [(feature_names[i], feature_importances[i]) for i in range(len(feature_names))]
            sorted_factors = sorted(factor_pairs, key=lambda x: abs(x[1]), reverse=True)
            
            # Convert to explanation format (top 10 factors)
            factors = []
            for i, (feature_name, importance) in enumerate(sorted_factors[:10]):
                if abs(importance) < 1e-6:  # Skip very small importances
                    continue
                    
                factors.append({
                    "feature": self._get_friendly_feature_name(feature_name),
                    "importance": float(abs(importance)),
                    "direction": "positive" if importance > 0 else "negative",
                    "explanation": self._get_factor_explanation(feature_name, importance, predicted_track_idx)
                })
            
            return factors
            
        except Exception as e:
            logger.warning(f"Perturbation-based feature importance failed: {e}")
            # Fallback to heuristic approach
            return self._get_heuristic_factors()
    
    def _get_heuristic_factors(self) -> List[Dict[str, Any]]:
        """Fallback heuristic-based explanation factors."""
        factors = []
        
        if not hasattr(self, 'feature_columns') or not self.feature_columns:
            return factors
        
        # Time-based features
        time_features = [col for col in self.feature_columns if any(x in col.lower() for x in ['hour', 'day', 'weekend', 'rush'])]
        if time_features:
            factors.append({
                "feature": "time_patterns",
                "importance": 0.4,
                "direction": "positive",
                "explanation": "Time of day and day of week patterns influence track assignment"
            })
        
        # Line features
        line_features = [col for col in self.feature_columns if col.startswith('Line_')]
        if line_features:
            factors.append({
                "feature": "train_line",
                "importance": 0.3,
                "direction": "positive", 
                "explanation": "Train line strongly correlates with specific track assignments"
            })
        
        # Destination features
        dest_features = [col for col in self.feature_columns if col.startswith('Destination_')]
        if dest_features:
            factors.append({
                "feature": "destination",
                "importance": 0.2,
                "direction": "positive",
                "explanation": "Train destination affects track selection patterns"
            })
        
        # Track utilization features
        util_features = [col for col in self.feature_columns if 'Utilization' in col or 'Occupied' in col]
        if util_features:
            factors.append({
                "feature": "track_utilization",
                "importance": 0.1,
                "direction": "negative",
                "explanation": "Current track usage affects availability for assignment"
            })
        
        return factors
    
    def _get_friendly_feature_name(self, feature_name: str) -> str:
        """Convert technical feature name to user-friendly name."""
        # Handle common patterns
        if 'hour' in feature_name.lower():
            return "departure_time"
        elif 'day' in feature_name.lower():
            return "day_of_week"
        elif 'weekend' in feature_name.lower():
            return "weekend_schedule"
        elif 'rush' in feature_name.lower():
            return "rush_hour"
        elif feature_name.startswith('Line_'):
            return f"train_line_{feature_name.replace('Line_', '')}"
        elif feature_name.startswith('Destination_'):
            return f"destination_{feature_name.replace('Destination_', '')}"
        elif 'TrainID' in feature_name:
            return "train_id_history"
        elif 'Track_' in feature_name and '_Last_Used' in feature_name:
            track = feature_name.split('_')[1]
            return f"track_{track}_availability"
        elif 'Utilization' in feature_name:
            return "track_utilization"
        else:
            return feature_name.lower().replace('_', ' ')
    
    def _get_factor_explanation(self, feature_name: str, importance: float, predicted_track_idx: int) -> str:
        """Generate explanation text for a feature's importance."""
        direction = "increases" if importance > 0 else "decreases"
        
        if 'hour' in feature_name.lower() or 'time' in feature_name.lower():
            return f"Departure time {direction} likelihood of track assignment"
        elif 'Line_' in feature_name:
            line_name = feature_name.replace('Line_', '')
            return f"Being on the {line_name} line {direction} track assignment probability"
        elif 'Destination_' in feature_name:
            dest_name = feature_name.replace('Destination_', '')
            return f"Destination to {dest_name} {direction} track assignment likelihood"
        elif 'TrainID' in feature_name:
            return f"Historical pattern for this train ID {direction} track assignment probability"
        elif 'Track_' in feature_name and '_Last_Used' in feature_name:
            return f"Track availability {direction} assignment probability"
        elif 'Utilization' in feature_name:
            return f"Track utilization patterns {direction} assignment likelihood"
        else:
            return f"This feature {direction} the prediction confidence"

    def save(self, model_path: str = None):
        """
        Public method to save the trained model.
        
        Args:
            model_path: Optional path to save the model. If provided, extracts version and timestamp from path.
        """
        if model_path:
            # Extract version and timestamp from provided path for consistency
            path = Path(model_path)
            stem = path.stem
            parts = stem.split('_')
            
            # Try to extract version and timestamp from filename
            encoders = None
            target_encoder = None
            tracks = None
            
            # Call _save_pytorch_model with custom path info
            return self._save_pytorch_model(
                encoders=encoders, 
                target_encoder=target_encoder, 
                tracks=tracks,
                custom_path=model_path
            )
        else:
            # Use default save behavior
            return self._save_pytorch_model()
    
    def _save_pytorch_model(self, encoders=None, target_encoder=None, tracks=None, custom_path=None):
        """Save the trained PyTorch model to disk."""
        if self.model is None:
            logger.warning("No model to save")
            return
        
        if custom_path:
            # Use provided custom path
            model_path = Path(custom_path)
            model_dir = model_path.parent
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract version and timestamp from filename
            stem = model_path.stem
            parts = stem.split('_')
            
            # Handle station-specific format: track_pred_model_VERSION_STATIONCODE_TIMESTAMP.pt
            if len(parts) >= 6 and parts[4].isupper() and len(parts[4]) <= 3:
                version = f"{parts[3]}_{parts[4]}"  # Include station code in version
                station_code = parts[4]
                timestamp = parts[5]
            # Handle legacy format: track_pred_model_VERSION_TIMESTAMP.pt
            elif len(parts) >= 5:
                version = parts[3]
                station_code = None
                timestamp = parts[4]
            else:
                version = self.model_version or "1.0.0"
                station_code = None
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        else:
            # Generate default path
            model_dir = Path("models")
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp and version
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            version = self.model_version or "1.0.0"
            station_code = None
            
            # Extract station code from version if present (e.g., "1.0.0_NY")
            if '_' in version:
                parts = version.split('_')
                if len(parts) == 2 and parts[1].isupper() and len(parts[1]) <= 3:
                    base_version = parts[0]
                    station_code = parts[1]
                    model_path = model_dir / f"track_pred_model_{base_version}_{station_code}_{timestamp}.pt"
                else:
                    model_path = model_dir / f"track_pred_model_{version}_{timestamp}.pt"
            else:
                model_path = model_dir / f"track_pred_model_{version}_{timestamp}.pt"
        
        # Save PyTorch model
        torch.save(self.model.state_dict(), model_path)
        
        # Create metadata
        metadata = {
            "model_version": version,
            "timestamp": timestamp,
            "input_dim": self.model.features[0].in_features,  # Get input dim from first layer
            "hidden_dims": [self.model.features[0].out_features],  # Simplified - just first hidden layer
            "output_dim": self.model.features[3].out_features,  # Get output dim from last layer
            "track_to_idx": self.track_to_idx,
            "idx_to_track": self.idx_to_track,
            "feature_columns": getattr(self, 'feature_columns', []),
            "temperature": float(self.model.temperature.item()) if hasattr(self.model, 'temperature') else 1.0
        }
        
        # Save metadata
        metadata_path = model_dir / f"metadata_{version}_{timestamp}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save scaler
        if self.scaler:
            scaler_path = model_dir / f"scaler_{version}_{timestamp}.pkl"
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"Scaler saved to {scaler_path}")
        
        # Save encoders if provided
        if encoders:
            encoders_path = model_dir / f"encoders_{version}_{timestamp}.pkl"
            with open(encoders_path, 'wb') as f:
                pickle.dump(encoders, f)
            logger.info(f"Encoders saved to {encoders_path}")
        
        # Save target encoder if provided
        if target_encoder:
            target_encoder_path = model_dir / f"target_encoder_{version}_{timestamp}.pkl"
            with open(target_encoder_path, 'wb') as f:
                pickle.dump(target_encoder, f)
            logger.info(f"Target encoder saved to {target_encoder_path}")
        
        # Save tracks if provided
        if tracks:
            tracks_path = model_dir / f"tracks_{version}_{timestamp}.pkl"
            with open(tracks_path, 'wb') as f:
                pickle.dump(tracks, f)
            logger.info(f"Tracks saved to {tracks_path}")
        
        # Save feature names
        if hasattr(self, 'feature_columns') and self.feature_columns:
            feature_names_path = model_dir / f"feature_names_{version}_{timestamp}.txt"
            with open(feature_names_path, 'w') as f:
                f.write('\n'.join(self.feature_columns))
            logger.info(f"Feature names saved to {feature_names_path}")
        
        logger.info(f"PyTorch model saved to {model_path}")
        logger.info(f"Metadata saved to {metadata_path}")
        
        return {
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
            "scaler_path": str(scaler_path) if self.scaler else None,
            "timestamp": timestamp,
            "version": version
        }

    def train(self, train_data, train_tracks, val_data=None, val_tracks=None, csv_mode=False):
        """
        Train the PyTorch model using the provided data.
        
        Args:
            train_data: List of ModelData objects for training OR path to CSV directory if csv_mode=True
            train_tracks: List of track labels for training OR None if csv_mode=True
            val_data: List of ModelData objects for validation (optional) OR None if csv_mode=True
            val_tracks: List of track labels for validation (optional) OR None if csv_mode=True
            csv_mode: If True, load data from CSV files like model.py
            
        Returns:
            Dict containing training statistics
        """
        try:
            # Import necessary modules for training
            from sklearn.preprocessing import StandardScaler, LabelEncoder
            from sklearn.model_selection import train_test_split
            from torch.utils.data import Dataset, DataLoader
            import torch.optim as optim
            
            if csv_mode:
                # CSV mode: Load and process data like model.py
                logger.info(f"Training in CSV mode from directory: {train_data}")
                from ..features.engineering import (
                    load_track_data_from_csv, 
                    add_historical_features, 
                    add_track_percentage_features,
                    prepare_model_data_from_csv
                )
                
                # Load data from CSV files
                df, tracks, train_lines, feature_cols = load_track_data_from_csv(train_data)
                
                # Add historical features
                df = add_historical_features(df)
                
                # Add track percentage features
                df = add_track_percentage_features(df, tracks)
                
                # Prepare model data
                X_train, X_test, y_train, y_test, input_dim, output_dim, feature_names, class_weights, scaler = prepare_model_data_from_csv(
                    df, tracks, feature_cols
                )
                
                # Store pipeline artifacts
                self.scaler = scaler
                self.feature_columns = feature_names
                
                # Extract unique tracks for label mapping
                unique_tracks = tracks
                
                # Create label mappings
                self.track_to_idx = {track: i for i, track in enumerate(unique_tracks)}
                self.idx_to_track = {str(i): track for i, track in enumerate(unique_tracks)}
                
                logger.info(f"CSV mode: Loaded {X_train.shape[0]} training and {X_test.shape[0]} test samples")
                
            else:
                # ModelData mode: Process ModelData objects
                logger.info(f"Training PyTorch model with {len(train_data)} training samples")
                
                # Convert ModelData objects to feature arrays
                X_train = []
                feature_names = None
                for model_data in train_data:
                    # ModelData has a to_dict() method to extract features
                    features_dict = model_data.to_dict()
                    if features_dict:
                        if feature_names is None:
                            # Store feature names from first sample for consistent ordering
                            feature_names = sorted(features_dict.keys())
                            self.feature_columns = feature_names
                        # Convert to array using consistent feature ordering
                        feature_array = [features_dict.get(name, 0.0) for name in feature_names]
                        X_train.append(feature_array)
                    else:
                        logger.error("ModelData object returned empty features")
                        raise ValueError("ModelData object returned empty features")
                
                X_train = np.array(X_train)
                y_train = np.array(train_tracks)
                
                # Handle validation data for ModelData mode
                X_test = None
                y_test = None
                if val_data and val_tracks:
                    X_val = []
                    for model_data in val_data:
                        features_dict = model_data.to_dict()
                        if features_dict and feature_names:
                            # Use same feature ordering as training data
                            feature_array = [features_dict.get(name, 0.0) for name in feature_names]
                            X_val.append(feature_array)
                        else:
                            logger.error("Validation ModelData object returned empty features")
                            raise ValueError("Validation ModelData object returned empty features")
                    X_test = np.array(X_val)
                    y_test = np.array(val_tracks)
                
                logger.info(f"ModelData mode: Feature matrix shape: {X_train.shape}")
                
                # Prepare label encoding for ModelData mode
                label_encoder = LabelEncoder()
                y_train_encoded = label_encoder.fit_transform(y_train)
                unique_tracks = label_encoder.classes_
                
                if X_test is not None:
                    y_test_encoded = label_encoder.transform(y_test)
                else:
                    # Split training data for validation
                    X_train, X_test, y_train_encoded, y_test_encoded = train_test_split(
                        X_train, y_train_encoded, test_size=0.2, random_state=42, stratify=y_train_encoded
                    )
                
                # One-hot encode targets for multi-class classification
                n_classes = len(unique_tracks)
                y_train = np.eye(n_classes)[y_train_encoded]
                y_test = np.eye(n_classes)[y_test_encoded]
                
                # Scale features
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X_train)
                X_test = scaler.transform(X_test)
                
                # Store scaler and label mappings for later use
                self.scaler = scaler
                self.track_to_idx = {track: i for i, track in enumerate(unique_tracks)}
                self.idx_to_track = {str(i): track for i, track in enumerate(unique_tracks)}
            
            # Now both CSV and ModelData modes have X_train, X_test, y_train, y_test ready
            # Convert to the variable names expected by the rest of the method
            X_train_scaled = X_train
            X_val_scaled = X_test
            y_train_onehot = y_train
            y_val_onehot = y_test if X_test is not None else None
            
            # Create PyTorch datasets
            class TrackDataset(Dataset):
                def __init__(self, features, targets):
                    self.features = torch.tensor(features, dtype=torch.float32)
                    self.targets = torch.tensor(targets, dtype=torch.float32)
                
                def __len__(self):
                    return len(self.features)
                
                def __getitem__(self, idx):
                    return self.features[idx], self.targets[idx]
            
            train_dataset = TrackDataset(X_train_scaled, y_train_onehot)
            train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
            
            val_loader = None
            if X_val_scaled is not None and y_val_onehot is not None:
                val_dataset = TrackDataset(X_val_scaled, y_val_onehot)
                val_loader = DataLoader(val_dataset, batch_size=32)
            
            # Initialize model
            input_dim = X_train_scaled.shape[1]
            hidden_dim = 128
            output_dim = n_classes
            
            self.model = TrackPredictor(input_dim, hidden_dim, output_dim)
            
            # Training setup
            criterion = nn.CrossEntropyLoss()
            optimizer = optim.Adam(self.model.parameters(), lr=0.001, weight_decay=1e-5)
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=20)
            
            # Training loop
            num_epochs = 300
            train_losses = []
            val_losses = []
            val_accuracies = []
            best_val_acc = 0
            best_state_dict = None
            
            for epoch in range(num_epochs):
                # Training phase
                self.model.train()
                train_loss = 0.0
                for inputs, targets in train_loader:
                    logits = self.model(inputs, apply_softmax=False)
                    loss = criterion(logits, targets)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    train_loss += loss.item()
                
                avg_train_loss = train_loss / len(train_loader)
                train_losses.append(avg_train_loss)
                
                # Validation phase
                if val_loader is not None:
                    self.model.eval()
                    val_loss = 0.0
                    correct = 0
                    total = 0
                    
                    with torch.no_grad():
                        for inputs, targets in val_loader:
                            logits = self.model(inputs, apply_softmax=False)
                            loss = criterion(logits, targets)
                            val_loss += loss.item()
                            
                            # Calculate accuracy
                            predictions = self.model(inputs, apply_softmax=True)
                            predicted = torch.argmax(predictions, dim=1)
                            actual = torch.argmax(targets, dim=1)
                            total += targets.size(0)
                            correct += (predicted == actual).sum().item()
                    
                    avg_val_loss = val_loss / len(val_loader)
                    val_accuracy = correct / total
                    
                    val_losses.append(avg_val_loss)
                    val_accuracies.append(val_accuracy)
                    
                    scheduler.step(avg_val_loss)
                    
                    # Save best model
                    if val_accuracy > best_val_acc:
                        best_val_acc = val_accuracy
                        best_state_dict = self.model.state_dict().copy()
                    
                    if (epoch + 1) % 20 == 0:
                        logger.info(f"Epoch {epoch+1}/{num_epochs}: Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}, Val Acc: {val_accuracy:.4f}")
                else:
                    if (epoch + 1) % 20 == 0:
                        logger.info(f"Epoch {epoch+1}/{num_epochs}: Train Loss: {avg_train_loss:.4f}")
            
            # Load best model if validation was used
            if best_state_dict is not None:
                self.model.load_state_dict(best_state_dict)
                logger.info(f"Using best model with validation accuracy {best_val_acc:.4f}")
            
            # Calibrate model with temperature scaling if validation data exists
            if val_loader is not None:
                logger.info("Calibrating model with temperature scaling...")
                # Create calibration dataset from half of validation data
                val_size = len(val_dataset)
                cal_size = int(0.5 * val_size)
                cal_indices = np.random.choice(val_size, cal_size, replace=False)
                
                # Create calibration loader
                cal_inputs = torch.stack([val_dataset[i][0] for i in cal_indices])
                cal_targets = torch.stack([val_dataset[i][1] for i in cal_indices])
                cal_dataset = torch.utils.data.TensorDataset(cal_inputs, cal_targets)
                cal_loader = DataLoader(cal_dataset, batch_size=32)
                
                # Calibrate temperature
                cal_criterion = nn.CrossEntropyLoss()
                try:
                    temperature = self.model.calibrate(cal_loader, cal_criterion)
                    logger.info(f"Temperature calibration completed. Final temperature: {temperature:.4f}")
                except Exception as e:
                    logger.warning(f"Temperature calibration failed: {e}")
            
            # Save the trained model with all artifacts
            unique_tracks_list = list(unique_tracks)
            self._save_pytorch_model(
                encoders={"label_encoder": label_encoder},
                target_encoder=label_encoder,
                tracks=unique_tracks_list
            )
            
            return {
                "train_samples": len(train_data) if not csv_mode else X_train_scaled.shape[0],
                "val_samples": len(val_data) if val_data and not csv_mode else (X_val_scaled.shape[0] if X_val_scaled is not None else 0),
                "epochs": num_epochs,
                "final_train_loss": train_losses[-1] if train_losses else None,
                "final_val_loss": val_losses[-1] if val_losses else None,
                "best_val_accuracy": best_val_acc if val_loader is not None else None,
                "train_losses": train_losses,
                "val_losses": val_losses,
                "val_accuracies": val_accuracies
            }
            
        except Exception as e:
            logger.error(f"Error during training: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def explain(self, features: Dict[str, Any], detailed=True) -> Dict[str, Any]:
        """
        Provide comprehensive explanation of the prediction.
        
        Args:
            features: Dict of feature values
            detailed: If True, include detailed analysis
            
        Returns:
            Dict containing comprehensive explanation
        """
        try:
            # Get prediction probabilities
            track_probs = self.predict(features)
            
            # Get prediction factors
            factors = self.get_prediction_factors(features, use_perturbation=detailed)
            
            # Find predicted track
            predicted_track = max(track_probs.keys(), key=lambda k: track_probs[k])
            predicted_prob = track_probs[predicted_track]
            
            explanation = {
                "predicted_track": predicted_track,
                "confidence": float(predicted_prob),
                "prediction_factors": factors,
                "all_probabilities": track_probs
            }
            
            if detailed:
                # Add confidence assessment
                explanation["confidence_level"] = self._assess_confidence(predicted_prob)
                
                # Add alternative tracks
                sorted_tracks = sorted(track_probs.items(), key=lambda x: x[1], reverse=True)
                explanation["alternative_tracks"] = [
                    {"track": track, "probability": float(prob)} 
                    for track, prob in sorted_tracks[1:4]  # Top 3 alternatives
                ]
                
                # Add prediction summary
                explanation["summary"] = self._generate_prediction_summary(
                    predicted_track, predicted_prob, factors[:3]  # Top 3 factors
                )
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return {
                "predicted_track": "unknown",
                "confidence": 0.0,
                "prediction_factors": [],
                "error": str(e)
            }
    
    def _assess_confidence(self, probability: float) -> str:
        """Assess confidence level based on prediction probability."""
        if probability >= 0.8:
            return "very_high"
        elif probability >= 0.6:
            return "high"
        elif probability >= 0.4:
            return "medium"
        elif probability >= 0.2:
            return "low"
        else:
            return "very_low"
    
    def _generate_prediction_summary(self, predicted_track: str, confidence: float, 
                                   top_factors: List[Dict[str, Any]]) -> str:
        """Generate a human-readable summary of the prediction."""
        confidence_level = self._assess_confidence(confidence)
        
        summary = f"Track {predicted_track} is predicted with {confidence_level} confidence ({confidence:.1%})"
        
        if top_factors:
            key_factor = top_factors[0]
            summary += f". The main contributing factor is {key_factor['feature']}"
            
            if len(top_factors) > 1:
                summary += f", along with {top_factors[1]['feature']}"
                
            if len(top_factors) > 2:
                summary += f" and {top_factors[2]['feature']}"
        
        summary += "."
        return summary
    
    def analyze_prediction_batch(self, features_list: List[Dict[str, Any]], 
                               include_explanations=True) -> Dict[str, Any]:
        """
        Analyze a batch of predictions for comprehensive insights.
        
        Args:
            features_list: List of feature dictionaries
            include_explanations: Whether to include explanations for each prediction
            
        Returns:
            Dict containing batch analysis results
        """
        logger.info(f"Analyzing batch of {len(features_list)} predictions")
        
        predictions = []
        track_distribution = {}
        confidence_levels = []
        
        for i, features in enumerate(features_list):
            try:
                # Get prediction
                track_probs = self.predict(features)
                predicted_track = max(track_probs.keys(), key=lambda k: track_probs[k])
                confidence = track_probs[predicted_track]
                
                prediction = {
                    "index": i,
                    "predicted_track": predicted_track,
                    "confidence": float(confidence),
                    "probabilities": track_probs
                }
                
                # Add explanation if requested
                if include_explanations:
                    explanation = self.explain(features, detailed=False)
                    prediction["explanation"] = explanation
                
                predictions.append(prediction)
                
                # Update distribution tracking
                track_distribution[predicted_track] = track_distribution.get(predicted_track, 0) + 1
                confidence_levels.append(confidence)
                
            except Exception as e:
                logger.error(f"Error predicting sample {i}: {e}")
                predictions.append({
                    "index": i,
                    "predicted_track": "error",
                    "confidence": 0.0,
                    "error": str(e)
                })
        
        # Calculate batch statistics
        avg_confidence = np.mean(confidence_levels) if confidence_levels else 0.0
        confidence_std = np.std(confidence_levels) if confidence_levels else 0.0
        
        # Track distribution percentages
        total_predictions = len([p for p in predictions if p["predicted_track"] != "error"])
        track_percentages = {
            track: (count / total_predictions * 100) if total_predictions > 0 else 0
            for track, count in track_distribution.items()
        }
        
        return {
            "total_predictions": len(features_list),
            "successful_predictions": total_predictions,
            "failed_predictions": len(features_list) - total_predictions,
            "average_confidence": float(avg_confidence),
            "confidence_std": float(confidence_std),
            "track_distribution": track_distribution,
            "track_percentages": track_percentages,
            "predictions": predictions,
            "summary": self._generate_batch_summary(
                total_predictions, avg_confidence, track_distribution
            )
        }
    
    def _generate_batch_summary(self, total: int, avg_confidence: float, 
                              distribution: Dict[str, int]) -> str:
        """Generate summary for batch prediction analysis."""
        if total == 0:
            return "No successful predictions were made."
        
        # Find most common track
        most_common_track = max(distribution.keys(), key=lambda k: distribution[k])
        most_common_count = distribution[most_common_track]
        
        summary = f"Analyzed {total} predictions with average confidence of {avg_confidence:.1%}. "
        summary += f"Track {most_common_track} was predicted most frequently ({most_common_count} times, "
        summary += f"{most_common_count/total:.1%} of predictions)."
        
        return summary
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the loaded model.
        
        Returns:
            Dict containing model statistics and metadata
        """
        stats = {
            "model_loaded": self.model is not None,
            "model_version": self.model_version,
            "scaler_loaded": self.scaler is not None,
            "feature_count": len(self.feature_columns) if self.feature_columns else 0,
            "track_count": len(self.track_to_idx) if self.track_to_idx else 0,
            "supported_tracks": list(self.track_to_idx.keys()) if self.track_to_idx else [],
            "feature_columns": self.feature_columns if self.feature_columns else []
        }
        
        if self.model:
            # Get model architecture info
            stats["model_architecture"] = {
                "input_dim": self.model.features[0].in_features,
                "hidden_dim": self.model.features[0].out_features,
                "output_dim": self.model.features[3].out_features,
                "temperature": float(self.model.temperature.item()) if hasattr(self.model, 'temperature') else 1.0
            }
            
            # Count parameters
            total_params = sum(p.numel() for p in self.model.parameters())
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            stats["parameters"] = {
                "total": total_params,
                "trainable": trainable_params
            }
        
        if self.metadata:
            stats["metadata"] = self.metadata
            
        return stats
    
    def validate_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that features are compatible with the loaded model.
        
        Args:
            features: Dict of feature values
            
        Returns:
            Dict containing validation results
        """
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "feature_info": {}
        }
        
        if not self.feature_columns:
            validation["errors"].append("No feature columns available from model metadata")
            validation["valid"] = False
            return validation
        
        # Check for missing features
        missing_features = []
        for col in self.feature_columns:
            if col not in features:
                missing_features.append(col)
        
        if missing_features:
            validation["warnings"].append(f"Missing {len(missing_features)} features: {missing_features[:5]}...")
        
        # Check for extra features
        extra_features = []
        for feature in features:
            if feature not in self.feature_columns:
                extra_features.append(feature)
        
        if extra_features:
            validation["warnings"].append(f"Extra {len(extra_features)} features will be ignored: {extra_features[:5]}...")
        
        # Validate feature types and ranges
        for col in self.feature_columns:
            if col in features:
                value = features[col]
                feature_info = {"value": value, "type": type(value).__name__}
                
                # Check for problematic values
                if value is None:
                    feature_info["warning"] = "None value will be replaced with 0"
                elif isinstance(value, (int, float)) and np.isnan(value):
                    feature_info["warning"] = "NaN value will be replaced with 0"
                elif isinstance(value, (int, float)) and np.isinf(value):
                    feature_info["warning"] = "Infinite value will be clipped"
                
                validation["feature_info"][col] = feature_info
        
        if validation["errors"]:
            validation["valid"] = False
        
        return validation