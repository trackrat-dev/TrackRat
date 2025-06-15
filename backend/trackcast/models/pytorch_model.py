import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Optional SHAP import for model explanation
try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from ..config import settings
from ..db.models import ModelData

logger = logging.getLogger(__name__)


class TrackPredictionNN(nn.Module):
    """PyTorch neural network for track prediction"""

    def __init__(
        self, input_dim: int, hidden_dims: List[int], output_dim: int, dropout_rate: float = 0.3
    ):
        super(TrackPredictionNN, self).__init__()

        layers = []
        # Input layer
        layers.append(nn.Linear(input_dim, hidden_dims[0]))
        layers.append(nn.ReLU())
        layers.append(nn.Dropout(dropout_rate))

        # Hidden layers
        for i in range(len(hidden_dims) - 1):
            layers.append(nn.Linear(hidden_dims[i], hidden_dims[i + 1]))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout_rate))

        # Output layer - removed softmax to output raw logits
        layers.append(nn.Linear(hidden_dims[-1], output_dim))
        # Removed Softmax layer - will apply softmax explicitly during prediction

        self.model = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


class PyTorchTrackPredictor:
    """PyTorch model trainer and predictor for track prediction"""

    def __init__(
        self,
        input_dim: Optional[int] = None,
        hidden_dims: Optional[List[int]] = None,
        output_dim: int = 21,  # Number of track options
        learning_rate: Optional[float] = None,
        batch_size: Optional[int] = None,
        num_epochs: Optional[int] = None,
        model_version: Optional[str] = None,
    ):
        # Get configuration
        hidden_dims = hidden_dims or settings.get(
            "model.hyperparameters.hidden_layers", [128, 64, 32]
        )
        learning_rate = learning_rate or settings.get("model.hyperparameters.learning_rate", 0.001)
        dropout_rate = settings.get("model.hyperparameters.dropout_rate", 0.3)
        batch_size = batch_size or settings.get("model.hyperparameters.batch_size", 64)
        num_epochs = num_epochs or settings.get("model.hyperparameters.num_epochs", 100)
        model_version = model_version or settings.get("model.version", "1.0.0")

        # Ensure num_epochs is never None
        if num_epochs is None:
            num_epochs = 100
            logger.warning(f"num_epochs was None, using default value of {num_epochs}")

        # Set up device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")

        # Initialize model
        self.input_dim = input_dim  # Will be set during feature preparation if None
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims
        self.dropout_rate = dropout_rate

        # Will initialize the model once input_dim is known
        self.model = None

        # Training parameters
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.num_epochs = num_epochs  # This should now never be None
        self.model_version = model_version

        # Log initialization parameters for debugging
        logger.info(
            f"Initialized PyTorchTrackPredictor with: learning_rate={self.learning_rate}, batch_size={self.batch_size}, num_epochs={self.num_epochs}"
        )

        # Feature processing
        self.scaler = None
        self.feature_columns = None

        # Track mapping
        self.track_to_idx = None
        self.idx_to_track = None

    def _initialize_model(self):
        """Initialize the PyTorch model"""
        if self.input_dim is None:
            raise ValueError("input_dim must be set before initializing model")

        self.model = TrackPredictionNN(
            self.input_dim, self.hidden_dims, self.output_dim, self.dropout_rate
        ).to(self.device)

        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        self.criterion = nn.CrossEntropyLoss()

    def _prepare_data(
        self, model_data_list: List[ModelData], tracks: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert ModelData objects to feature matrix and target vector"""
        from sklearn.preprocessing import StandardScaler

        # Convert ModelData to DataFrame for easier processing
        data = []
        for md in model_data_list:
            row = {
                "train_id": md.train.train_id if md.train else "unknown",
                "hour_sin": md.hour_sin,
                "hour_cos": md.hour_cos,
                "day_of_week_sin": md.day_of_week_sin,
                "day_of_week_cos": md.day_of_week_cos,
                "is_weekend": int(md.is_weekend),
                "is_morning_rush": int(md.is_morning_rush),
                "is_evening_rush": int(md.is_evening_rush),
                "line_features": md.line_features,
                "destination_features": md.destination_features,
                "track_usage_features": md.track_usage_features,
                "historical_features": md.historical_features,
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Process numeric features
        numeric_cols = [
            "hour_sin",
            "hour_cos",
            "day_of_week_sin",
            "day_of_week_cos",
            "is_weekend",
            "is_morning_rush",
            "is_evening_rush",
        ]
        X_numeric = df[numeric_cols].values

        # Process JSON columns to create feature vectors
        # We'll build these as we go to handle dynamic features
        all_features = []
        column_names = numeric_cols.copy()

        # Process line features
        if len(df) > 0:
            # Process line features
            line_features = df["line_features"].iloc[0]
            if line_features is not None:
                if isinstance(line_features, str):
                    line_features = json.loads(line_features)
                if line_features:  # Check if not empty
                    line_cols = sorted(line_features.keys())
                    column_names.extend(line_cols)

                    line_matrix = np.zeros((len(df), len(line_cols)))
                    for i, row in enumerate(df["line_features"]):
                        if row is None:
                            continue
                        if isinstance(row, str):
                            row = json.loads(row)
                        for j, col in enumerate(line_cols):
                            line_matrix[i, j] = row.get(col, 0)

                    all_features.append(line_matrix)

            # Destination features
            dest_features = df["destination_features"].iloc[0]
            if dest_features is not None:
                if isinstance(dest_features, str):
                    dest_features = json.loads(dest_features)
                if dest_features:  # Check if not empty
                    dest_cols = sorted(dest_features.keys())
                    column_names.extend(dest_cols)

                    dest_matrix = np.zeros((len(df), len(dest_cols)))
                    for i, row in enumerate(df["destination_features"]):
                        if row is None:
                            continue
                        if isinstance(row, str):
                            row = json.loads(row)
                        for j, col in enumerate(dest_cols):
                            dest_matrix[i, j] = row.get(col, 0)

                    all_features.append(dest_matrix)

            # Track usage features
            track_features = df["track_usage_features"].iloc[0]
            if track_features is not None:
                if isinstance(track_features, str):
                    track_features = json.loads(track_features)
                if track_features:  # Check if not empty
                    track_cols = sorted(track_features.keys())
                    column_names.extend(track_cols)

                    track_matrix = np.zeros((len(df), len(track_cols)))
                    for i, row in enumerate(df["track_usage_features"]):
                        if row is None:
                            continue
                        if isinstance(row, str):
                            row = json.loads(row)
                        for j, col in enumerate(track_cols):
                            track_matrix[i, j] = row.get(col, 0)

                    all_features.append(track_matrix)

            # Historical features
            hist_features = df["historical_features"].iloc[0]
            if hist_features is not None:
                if isinstance(hist_features, str):
                    hist_features = json.loads(hist_features)
                if hist_features:  # Check if not empty
                    hist_cols = sorted(hist_features.keys())
                    column_names.extend(hist_cols)

                    hist_matrix = np.zeros((len(df), len(hist_cols)))
                    for i, row in enumerate(df["historical_features"]):
                        if row is None:
                            continue
                        if isinstance(row, str):
                            row = json.loads(row)
                        for j, col in enumerate(hist_cols):
                            hist_matrix[i, j] = row.get(col, 0)

                    all_features.append(hist_matrix)

        # Combine all features
        features = [X_numeric]
        features.extend(all_features)
        X = np.hstack(features) if all_features else X_numeric

        # Store feature column names for later use
        self.feature_columns = column_names

        # Debug: Log feature dimensions
        feature_count = len(column_names)
        logger.info(f"Feature matrix shape: {X.shape} with {feature_count} named features")
        logger.info(f"Feature names: {column_names}")

        # Check if feature count exceeds limit
        MAX_FEATURE_COUNT = 1000
        if feature_count > MAX_FEATURE_COUNT:
            error_msg = (
                f"Feature count ({feature_count}) exceeds maximum allowed ({MAX_FEATURE_COUNT})"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Set input_dim if not already set
        if self.input_dim is None:
            self.input_dim = X.shape[1]
            logger.info(f"Setting initial input_dim to {self.input_dim}")
            self._initialize_model()

        # Create track mapping if not exists
        if self.track_to_idx is None:
            # Filter out None values from tracks
            valid_tracks = [t for t in tracks if t is not None]
            if len(valid_tracks) < len(tracks):
                logger.warning(f"Filtered out {len(tracks) - len(valid_tracks)} None tracks")

            unique_tracks = sorted(list(set(valid_tracks)))
            self.track_to_idx = {track: i for i, track in enumerate(unique_tracks)}
            self.idx_to_track = {i: track for track, i in self.track_to_idx.items()}
            logger.info(f"Created track mapping with {len(unique_tracks)} unique tracks")

        # Convert tracks to indices with safety check for None values
        y = np.array([self.track_to_idx.get(t, 0) if t is not None else 0 for t in tracks])

        # Initialize and fit scaler if not exists
        if self.scaler is None:
            logger.info("Initializing and fitting new StandardScaler")
            self.scaler = StandardScaler()
            X = self.scaler.fit_transform(X)
        else:
            logger.info(
                f"Using existing scaler expecting {self.scaler.n_features_in_} features, got {X.shape[1]}"
            )
            if self.scaler.n_features_in_ != X.shape[1]:
                # Log detailed feature mismatch information
                logger.error(
                    f"Feature dimension mismatch: X has {X.shape[1]} features, scaler expects {self.scaler.n_features_in_}"
                )

                # Save feature information for debugging
                if not hasattr(self, "feature_snapshots"):
                    self.feature_snapshots = []

                # Add current snapshot
                snapshot = {
                    "timestamp": datetime.now().isoformat(),
                    "feature_count": len(self.feature_columns),
                    "features": self.feature_columns,
                }
                self.feature_snapshots.append(snapshot)

                # Detailed comparison if we have previous snapshots
                if hasattr(self, "previous_feature_columns") and self.previous_feature_columns:
                    prev_features = self.previous_feature_columns
                    curr_features = self.feature_columns

                    # Compare features by position
                    logger.error(
                        f"Detailed feature comparison between previous ({len(prev_features)}) and current ({len(curr_features)}):"
                    )

                    # Print full detailed side-by-side comparison
                    max_len = max(len(prev_features), len(curr_features))
                    comparison_lines = []
                    comparison_lines.append("Index | Previous Feature | Current Feature | Status")
                    comparison_lines.append("-" * 70)

                    for i in range(max_len):
                        prev_feat = prev_features[i] if i < len(prev_features) else "N/A"
                        curr_feat = curr_features[i] if i < len(curr_features) else "N/A"

                        # Mark differences
                        if i >= len(prev_features):
                            status = "NEW"
                        elif i >= len(curr_features):
                            status = "REMOVED"
                        elif prev_feat != curr_feat:
                            status = "CHANGED"
                        else:
                            status = "SAME"

                        comparison_lines.append(
                            f"{i:5d} | {prev_feat:30s} | {curr_feat:30s} | {status}"
                        )

                    # Log the comparison 10 lines at a time to avoid log truncation
                    chunk_size = 10
                    for i in range(0, len(comparison_lines), chunk_size):
                        chunk = comparison_lines[i : i + chunk_size]
                        logger.error("\n".join(chunk))

                    # Access scaler features if available
                    scaler_feature_names = []
                    if hasattr(self.scaler, "feature_names_in_"):
                        scaler_feature_names = list(self.scaler.feature_names_in_)
                    else:
                        logger.error(
                            "Scaler doesn't have feature_names_in_ attribute - using previous_feature_columns as fallback"
                        )
                        scaler_feature_names = prev_features

                    # Better comparison against what the scaler expects
                    scaler_set = set(scaler_feature_names)
                    curr_set = set(curr_features)

                    true_missing = (
                        scaler_set - curr_set
                    )  # Features the scaler expects but aren't present
                    extra = curr_set - scaler_set  # Features present that the scaler doesn't expect

                    # Check for discrepancy between feature counts and array dimensions
                    expected_dimension = self.scaler.n_features_in_
                    received_dimension = X.shape[1]
                    dimension_mismatch = expected_dimension != received_dimension

                    logger.error(f"FEATURE DIMENSION ANALYSIS:")
                    logger.error(f"  - Scaler expects: {expected_dimension} features")
                    logger.error(f"  - Current data has: {received_dimension} features")
                    logger.error(f"  - Named features in scaler: {len(scaler_feature_names)}")
                    logger.error(f"  - Named features in current data: {len(curr_features)}")

                    if dimension_mismatch and len(true_missing) == 0 and len(extra) == 0:
                        logger.error(
                            f"CRITICAL: Dimension mismatch despite identical feature names!"
                        )
                        logger.error(
                            f"This suggests the model was trained with {expected_dimension} features, but current data has only {received_dimension} features."
                        )

                        # Look for Matching_TrainID_Track_* features which may be missing
                        trainid_pattern = "Matching_TrainID_Track_"
                        trainid_features = [f for f in scaler_feature_names if trainid_pattern in f]
                        curr_trainid_features = [f for f in curr_features if trainid_pattern in f]

                        if len(trainid_features) != len(curr_trainid_features):
                            logger.error(
                                f"Detected {len(trainid_features)} {trainid_pattern}* features in scaler, but only {len(curr_trainid_features)} in current data"
                            )
                            missing_trainid = set(trainid_features) - set(curr_trainid_features)
                            if missing_trainid:
                                logger.error(f"Missing TrainID features ({len(missing_trainid)}):")
                                for f in sorted(missing_trainid):
                                    logger.error(f"  - {f}")

                    # Standard set comparison
                    if true_missing:
                        logger.error(
                            f"MISSING {len(true_missing)} FEATURES (expected by scaler but not found):"
                        )
                        for i, feature in enumerate(sorted(true_missing)):
                            logger.error(f"  Missing feature {i + 1}: {feature}")
                    if extra:
                        logger.error(
                            f"EXTRA {len(extra)} FEATURES (found but not expected by scaler):"
                        )
                        for i, feature in enumerate(sorted(extra)):
                            logger.error(f"  Extra feature {i + 1}: {feature}")

                    # Compare with previous feature set too
                    prev_set = set(prev_features)
                    regression_missing = prev_set - curr_set
                    regression_new = curr_set - prev_set

                    if regression_missing:
                        logger.error(
                            f"REGRESSION: {len(regression_missing)} features present in previous data but missing now:"
                        )
                        for i, feature in enumerate(sorted(regression_missing)):
                            logger.error(f"  Regression missing {i + 1}: {feature}")
                    if regression_new:
                        logger.error(
                            f"NEW SINCE LAST RUN: {len(regression_new)} features new since last execution:"
                        )
                        for i, feature in enumerate(sorted(regression_new)):
                            logger.error(f"  New feature {i + 1}: {feature}")

                    # Print clear summary showing the dimension mismatch
                    logger.error(
                        f"FEATURE COUNT SUMMARY: Expected {expected_dimension} features, got {received_dimension} features"
                    )
                    logger.error(f"  - Missing features count (by name): {len(true_missing)}")
                    logger.error(f"  - Extra features count (by name): {len(extra)}")
                    logger.error(
                        f"  - Dimension difference: {expected_dimension - received_dimension} features"
                    )

                # Store current feature columns for future comparison
                self.previous_feature_columns = self.feature_columns.copy()

            X = self.scaler.transform(X)

        return X, y

    def train(
        self,
        train_model_data: List[ModelData],
        train_tracks: List[str],
        val_model_data: Optional[List[ModelData]] = None,
        val_tracks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train the model on prepared feature data"""
        # Prepare data
        X_train, y_train = self._prepare_data(train_model_data, train_tracks)

        # Initialize model if not already done
        if self.model is None:
            self.input_dim = X_train.shape[1]
            self._initialize_model()

        # Convert to PyTorch tensors
        X_train_tensor = torch.FloatTensor(X_train).to(self.device)
        y_train_tensor = torch.LongTensor(y_train).to(self.device)

        # Create data loader for training
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)

        # Validation data if provided
        val_loader = None
        if (
            val_model_data is not None
            and val_tracks is not None
            and len(val_model_data) > 0
            and len(val_tracks) > 0
        ):
            try:
                logger.info(f"Preparing validation data: {len(val_model_data)} samples")
                X_val, y_val = self._prepare_data(val_model_data, val_tracks)
                X_val_tensor = torch.FloatTensor(X_val).to(self.device)
                y_val_tensor = torch.LongTensor(y_val).to(self.device)
                val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
                val_loader = DataLoader(val_dataset, batch_size=self.batch_size, shuffle=False)
                logger.info(f"Created validation loader with {len(val_dataset)} samples")
            except Exception as e:
                logger.error(f"Error preparing validation data: {str(e)}")
                # Continue without validation if there's an error
                val_loader = None

        # Training loop
        best_val_loss = float("inf")
        patience = 10
        patience_counter = 0
        train_losses = []
        val_losses = []
        val_accuracies = []

        logger.info(f"Starting training with {len(train_model_data)} samples")

        # Safety check for num_epochs
        if self.num_epochs is None:
            logger.error("num_epochs is None, using default value of 100")
            self.num_epochs = 100

        logger.info(f"Training for {self.num_epochs} epochs")

        for epoch in range(self.num_epochs):
            # Training
            self.model.train()
            train_loss = 0.0

            for batch_X, batch_y in train_loader:
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                train_loss += loss.item()

            avg_train_loss = train_loss / len(train_loader)
            train_losses.append(avg_train_loss)

            # Validation
            if val_loader:
                self.model.eval()
                val_loss = 0.0
                val_correct = 0
                val_total = 0

                with torch.no_grad():
                    for batch_X, batch_y in val_loader:
                        outputs = self.model(batch_X)
                        loss = self.criterion(outputs, batch_y)
                        val_loss += loss.item()

                        _, predicted = torch.max(outputs.data, 1)
                        val_total += batch_y.size(0)
                        val_correct += (predicted == batch_y).sum().item()

                avg_val_loss = val_loss / len(val_loader)
                val_accuracy = val_correct / val_total

                val_losses.append(avg_val_loss)
                val_accuracies.append(val_accuracy)

                logger.info(
                    f"Epoch {epoch + 1}/{self.num_epochs} - "
                    f"Train Loss: {avg_train_loss:.4f}, "
                    f"Val Loss: {avg_val_loss:.4f}, "
                    f"Val Accuracy: {val_accuracy:.4f}"
                )

                # Early stopping
                if avg_val_loss < best_val_loss:
                    best_val_loss = avg_val_loss
                    patience_counter = 0
                    self._save_model()
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        logger.info(f"Early stopping after {epoch + 1} epochs")
                        break
            else:
                logger.info(
                    f"Epoch {epoch + 1}/{self.num_epochs} - " f"Train Loss: {avg_train_loss:.4f}"
                )
                # Save model periodically if no validation
                if (epoch + 1) % 10 == 0:
                    self._save_model()

        # Final save
        self._save_model()

        # Return training stats
        return {
            "train_losses": train_losses,
            "val_losses": val_losses if val_loader else [],
            "val_accuracies": val_accuracies if val_loader else [],
            "epochs_trained": epoch + 1,
            "early_stopped": patience_counter >= patience if val_loader else False,
            "best_val_loss": best_val_loss if val_loader else None,
            "final_train_loss": train_losses[-1],
            "model_version": self.model_version,
        }

    def predict(self, model_data: List[ModelData]) -> List[Dict[str, float]]:
        """Generate track probabilities for new data"""
        if self.model is None:
            raise ValueError("Model must be trained or loaded before prediction")

        try:
            # Check if there's any data to predict
            if not model_data:
                logger.warning("No model data provided for prediction")
                return [{}]

            self.model.eval()

            # Create dummy targets (won't be used)
            dummy_tracks = ["1"] * len(model_data)

            # Debug log for prediction data
            logger.info(f"Preparing prediction features for {len(model_data)} samples")
            if model_data and hasattr(model_data[0], "id"):
                logger.info(f"Model data IDs for prediction: {[md.id for md in model_data[:5]]}...")

            # Prepare features
            X, _ = self._prepare_data(model_data, dummy_tracks)
            X_tensor = torch.FloatTensor(X).to(self.device)

            # Generate predictions
            with torch.no_grad():
                outputs = self.model(X_tensor)
                # Explicitly apply softmax to convert logits to probabilities
                probabilities = torch.softmax(outputs, dim=1).cpu().numpy()

            # Debug track mapping
            logger.info(f"Model has {len(self.idx_to_track)} track mappings: {self.idx_to_track}")

            # Convert to dictionary format
            results = []
            for i, probs in enumerate(probabilities):
                track_probs = {}
                mapped_indices = 0
                unmapped_indices = []

                for idx, prob in enumerate(probs):
                    if idx in self.idx_to_track:
                        track = self.idx_to_track[idx]
                        track_probs[track] = float(prob)
                        mapped_indices += 1
                    elif prob > 0.01:  # Only log significant unmapped probabilities
                        unmapped_indices.append((idx, float(prob)))

                results.append(track_probs)

                # Detailed debug information
                if mapped_indices == 0:
                    logger.warning(
                        f"Sample {i}: No valid track mappings found! Model predicted probabilities for indices: "
                        f"{[idx for idx, prob in enumerate(probs) if prob > 0.01]}"
                    )
                    if unmapped_indices:
                        logger.warning(
                            f"Unmapped tracks with significant probabilities: {unmapped_indices}"
                        )
                elif len(track_probs) < sum(1 for p in probs if p > 0.01):
                    logger.warning(
                        f"Sample {i}: Some tracks couldn't be mapped. Mapped {mapped_indices} tracks, "
                        f"but model predicted {sum(1 for p in probs if p > 0.01)} tracks with p>0.01"
                    )

            # If all results are empty, provide a fallback
            if all(not r for r in results):
                logger.error(
                    "ALL prediction results are empty due to track mapping issues. Using fallback track mapping."
                )

                # Create a fallback mapping for the top predicted tracks
                for i, probs in enumerate(probabilities):
                    # Find top 3 indices by probability
                    top_indices = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)[
                        :3
                    ]
                    track_probs = {}

                    # Map them to track numbers directly
                    for idx in top_indices:
                        if probs[idx] > 0.01:  # Only include significant probabilities
                            track = str(idx + 1)  # Convert to 1-based track numbers
                            track_probs[track] = float(probs[idx])

                    # Replace the empty result
                    if track_probs:
                        logger.info(f"Using fallback mapping for sample {i}: {track_probs}")
                        results[i] = track_probs

            return results
        except Exception as e:
            logger.error(f"Error in prediction: {str(e)}")
            # Return empty predictions in case of error
            return [{}] * len(model_data)

    def get_prediction_factors(self, model_data: ModelData) -> List[Dict[str, Any]]:
        """Generate SHAP values to explain predictions"""
        if self.model is None:
            raise ValueError("Model must be trained or loaded before generating explanations")

        # Check if SHAP is available
        if not SHAP_AVAILABLE:
            logger.warning("SHAP not available - cannot generate detailed prediction factors")
            return [
                {
                    "feature": "model_prediction",
                    "importance": 1.0,
                    "direction": "positive",
                    "explanation": "SHAP explanations not available in inference-only mode",
                }
            ]

        # Create a single-element batch
        dummy_tracks = ["1"]
        X, _ = self._prepare_data([model_data], dummy_tracks)

        # Create background data for SHAP (simplified)
        background = np.zeros((1, X.shape[1]))

        # Define a PyTorch model wrapper for SHAP
        class ModelWrapper:
            def __init__(self, model, device):
                self.model = model
                self.device = device

            def __call__(self, x):
                x_tensor = torch.FloatTensor(x).to(self.device)
                self.model.eval()
                with torch.no_grad():
                    outputs = self.model(x_tensor)
                    # Explicitly apply softmax to convert logits to probabilities
                    return torch.softmax(outputs, dim=1).cpu().numpy()

        # Create explainer
        explainer = shap.Explainer(ModelWrapper(self.model, self.device), background)
        shap_values = explainer(X)

        # Get the predicted class
        probs = self.predict([model_data])[0]

        # Handle empty or invalid predictions
        if not probs:
            logger.warning("No valid track predictions found, cannot generate prediction factors")
            return [
                {
                    "feature": "unknown",
                    "importance": 0.0,
                    "direction": "neutral",
                    "explanation": "No valid predictions were generated",
                }
            ]

        try:
            # Find the track with the highest probability
            if not probs.items():
                logger.warning("Empty track probability dictionary")
                return [
                    {
                        "feature": "unknown",
                        "importance": 0.0,
                        "direction": "neutral",
                        "explanation": "Empty track probabilities",
                    }
                ]

            predicted_track = max(probs.items(), key=lambda x: x[1])[0]
            predicted_idx = self.track_to_idx.get(predicted_track)

            if predicted_idx is None:
                logger.warning(f"Track {predicted_track} not found in track_to_idx mapping")
                return [
                    {
                        "feature": "unknown",
                        "importance": 0.0,
                        "direction": "neutral",
                        "explanation": f"Track {predicted_track} not in model mapping",
                    }
                ]
        except Exception as e:
            logger.error(f"Error determining predicted track: {str(e)}")
            return [
                {
                    "feature": "error",
                    "importance": 0.0,
                    "direction": "neutral",
                    "explanation": f"Error in prediction analysis: {str(e)}",
                }
            ]

        # Get SHAP values for the predicted class
        class_shap_values = shap_values[:, :, predicted_idx][0]

        # Sort features by importance (absolute SHAP value)
        feature_importance = [
            (col, abs(val)) for col, val in zip(self.feature_columns, class_shap_values)
        ]
        feature_importance.sort(key=lambda x: x[1], reverse=True)

        # Generate human-readable explanations for top features
        factors = []
        for feature, importance in feature_importance[:5]:  # Top 5 features
            direction = (
                "positive"
                if class_shap_values[self.feature_columns.index(feature)] > 0
                else "negative"
            )
            explanation = self._generate_explanation(feature, direction, predicted_track)

            factors.append(
                {
                    "feature": feature,
                    "importance": float(importance),
                    "direction": direction,
                    "explanation": explanation,
                }
            )

        return factors

    def _generate_explanation(self, feature: str, direction: str, predicted_track: str) -> str:
        """Generate a human-readable explanation for a feature's influence"""
        # This could be more sophisticated with templates based on feature types
        if "Line_" in feature:
            line = feature.replace("Line_", "").replace("_", " ")
            return f"{line} trains {'often' if direction == 'positive' else 'rarely'} use Track {predicted_track}"
        elif "Destination_" in feature:
            dest = feature.replace("Destination_", "").replace("_", " ")
            return f"Trains to {dest} {'typically' if direction == 'positive' else 'rarely'} use Track {predicted_track}"
        elif "Track_" in feature and "Last_Used" in feature:
            track = feature.split("_")[1]
            return f"Track {track} was {'recently' if direction == 'negative' else 'not recently'} used"
        elif "hour_sin" in feature or "hour_cos" in feature:
            return "Time of day influences track assignment"
        elif "is_weekend" in feature:
            return f"{'Weekend' if direction == 'positive' else 'Weekday'} patterns favor Track {predicted_track}"
        elif "is_morning_rush" in feature or "is_evening_rush" in feature:
            rush = "Morning" if "morning" in feature else "Evening"
            return f"{rush} rush hour {'increases' if direction == 'positive' else 'decreases'} likelihood of Track {predicted_track}"
        else:
            return f"This feature {'increases' if direction == 'positive' else 'decreases'} likelihood of Track {predicted_track}"

    def _save_model(self) -> str:
        """Save the trained model and metadata"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Create models directory if it doesn't exist
        models_dir = Path(settings.get("model.save_path", "models/"))
        models_dir.mkdir(parents=True, exist_ok=True)

        # Paths for model artifacts
        model_path = models_dir / f"track_pred_model_{self.model_version}_{timestamp}.pt"
        scaler_path = models_dir / f"scaler_{self.model_version}_{timestamp}.pkl"
        metadata_path = models_dir / f"metadata_{self.model_version}_{timestamp}.json"

        # Save PyTorch model
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
            },
            model_path,
        )

        # Save scaler
        with open(scaler_path, "wb") as f:
            pickle.dump(self.scaler, f)

        # Save metadata (track mappings, feature columns, etc.)
        metadata = {
            "model_version": self.model_version,
            "timestamp": timestamp,
            "input_dim": self.input_dim,
            "hidden_dims": self.hidden_dims,
            "output_dim": self.output_dim,
            "track_to_idx": self.track_to_idx,
            "idx_to_track": self.idx_to_track,
            "feature_columns": self.feature_columns,
        }

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path}")
        return str(model_path)

    def load_model(self, model_path: str, metadata_path: str, scaler_path: str) -> None:
        """Load a trained model and its metadata"""
        # Load metadata first
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Set model parameters from metadata
        self.input_dim = metadata["input_dim"]
        self.hidden_dims = metadata["hidden_dims"]
        self.output_dim = metadata["output_dim"]

        # Load track mappings with better error handling
        try:
            self.track_to_idx = metadata["track_to_idx"]
            # Convert string keys back to correct types if needed
            if all(not isinstance(k, int) for k in self.track_to_idx.values()):
                logger.warning("Converting track_to_idx values from strings to integers")
                self.track_to_idx = {k: int(v) for k, v in self.track_to_idx.items()}

            # For idx_to_track, keys must be integers
            self.idx_to_track = metadata["idx_to_track"]
            # Convert keys from strings to integers if needed (JSON serialization converts int keys to strings)
            if all(not isinstance(k, int) for k in self.idx_to_track.keys()):
                logger.warning("Converting idx_to_track keys from strings to integers")
                self.idx_to_track = {int(k): v for k, v in self.idx_to_track.items()}

            logger.info(f"Loaded track mappings: {len(self.track_to_idx)} tracks")
            logger.info(f"Track to idx mapping: {self.track_to_idx}")
            logger.info(f"Idx to track mapping: {self.idx_to_track}")

            # Sanity check for number of tracks
            if len(self.track_to_idx) < 10 or len(self.idx_to_track) < 10:
                logger.warning(
                    f"Suspiciously low number of track mappings: {len(self.track_to_idx)}"
                )

        except Exception as e:
            logger.error(f"Error loading track mappings, using defaults: {str(e)}")
            # Create default mappings for tracks 1-21
            default_tracks = [str(i) for i in range(1, 22)]
            self.track_to_idx = {track: i for i, track in enumerate(default_tracks)}
            self.idx_to_track = {i: track for i, track in enumerate(default_tracks)}
        self.feature_columns = metadata["feature_columns"]
        self.model_version = metadata["model_version"]

        # Initialize model architecture
        self._initialize_model()

        # Load model weights
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

        # Load scaler
        with open(scaler_path, "rb") as f:
            self.scaler = pickle.load(f)

        logger.info(f"Model loaded from {model_path}")
