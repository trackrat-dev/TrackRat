import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from ..config import settings
from ..db.models import ModelData
from .base import BaseTrackPredictor

logger = logging.getLogger(__name__)


class XGBoostTrackPredictor(BaseTrackPredictor):
    """XGBoost implementation for track prediction"""

    def __init__(
        self,
        learning_rate: Optional[float] = None,
        max_depth: Optional[int] = None,
        n_estimators: Optional[int] = None,
        subsample: Optional[float] = None,
        colsample_bytree: Optional[float] = None,
        model_version: Optional[str] = None,
    ):
        # Get hyperparameters from config or use defaults
        learning_rate = learning_rate or settings.get("model.hyperparameters.learning_rate", 0.1)
        max_depth = max_depth or settings.get("model.hyperparameters.max_depth", 6)
        n_estimators = n_estimators or settings.get("model.hyperparameters.n_estimators", 100)
        subsample = subsample or settings.get("model.hyperparameters.subsample", 0.8)
        colsample_bytree = colsample_bytree or settings.get(
            "model.hyperparameters.colsample_bytree", 0.8
        )
        model_version = model_version or settings.get("model.version", "1.0.0")

        # Initialize model parameters
        self.xgb_params = {
            "objective": "multi:softprob",
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "n_estimators": n_estimators,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "tree_method": "hist",  # For faster training
            "verbosity": 1,
            "eval_metric": ["mlogloss", "merror"],
        }

        # Model state
        self.model = None
        self.model_version = model_version
        self.scaler = None
        self.feature_columns = None
        self.track_to_idx = None
        self.idx_to_track = None

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
        logger.info(f"Feature matrix shape: {X.shape} with {len(column_names)} named features")
        logger.info(f"Feature names: {column_names}")

        # Create track mapping if not exists
        if self.track_to_idx is None:
            unique_tracks = sorted(list(set(tracks)))
            self.track_to_idx = {track: i for i, track in enumerate(unique_tracks)}
            self.idx_to_track = {i: track for track, i in self.track_to_idx.items()}
            # Set the num_class parameter for XGBoost
            self.xgb_params["num_class"] = len(unique_tracks)
            logger.info(f"Created track mapping with {len(unique_tracks)} unique tracks")

        # Convert tracks to indices
        y = np.array([self.track_to_idx.get(t, 0) for t in tracks])

        # Initialize and fit scaler if not exists
        if self.scaler is None:
            logger.info("Initializing and fitting new StandardScaler")
            self.scaler = StandardScaler()
            X = self.scaler.fit_transform(X)
        else:
            logger.info(f"Using existing scaler expecting {self.scaler.n_features_in_} features, got {X.shape[1]}")
            if self.scaler.n_features_in_ != X.shape[1]:
                # Log detailed feature mismatch information
                logger.error(f"Feature dimension mismatch: X has {X.shape[1]} features, scaler expects {self.scaler.n_features_in_}")

                # Save feature information for debugging
                if not hasattr(self, 'feature_snapshots'):
                    self.feature_snapshots = []

                # Add current snapshot
                snapshot = {
                    'timestamp': datetime.now().isoformat(),
                    'feature_count': len(self.feature_columns),
                    'features': self.feature_columns
                }
                self.feature_snapshots.append(snapshot)

                # Detailed comparison if we have previous snapshots
                if hasattr(self, 'previous_feature_columns') and self.previous_feature_columns:
                    prev_features = self.previous_feature_columns
                    curr_features = self.feature_columns

                    # Compare features by position
                    logger.error(f"Detailed feature comparison between previous ({len(prev_features)}) and current ({len(curr_features)}):")

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

                        comparison_lines.append(f"{i:5d} | {prev_feat:30s} | {curr_feat:30s} | {status}")

                    # Log the comparison 10 lines at a time to avoid log truncation
                    chunk_size = 10
                    for i in range(0, len(comparison_lines), chunk_size):
                        chunk = comparison_lines[i:i+chunk_size]
                        logger.error("\n".join(chunk))

                    # Set comparison (summarized)
                    prev_set = set(prev_features)
                    curr_set = set(curr_features)

                    missing = prev_set - curr_set
                    new = curr_set - prev_set

                    if missing:
                        logger.error(f"Missing features that were in previous data: {missing}")
                    if new:
                        logger.error(f"New features not seen in previous data: {new}")

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

        # Create DMatrix for training
        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=self.feature_columns)

        # Validation data if provided
        eval_list = [(dtrain, "train")]
        if val_model_data and val_tracks:
            X_val, y_val = self._prepare_data(val_model_data, val_tracks)
            dval = xgb.DMatrix(X_val, label=y_val, feature_names=self.feature_columns)
            eval_list.append((dval, "validation"))

        # Train the model
        logger.info(f"Starting XGBoost training with {len(train_model_data)} samples")

        # Early stopping parameters
        early_stopping_rounds = 10 if len(eval_list) > 1 else None

        # Training with cv
        self.model = xgb.train(
            self.xgb_params,
            dtrain,
            num_boost_round=self.xgb_params["n_estimators"],
            evals=eval_list,
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=10,
        )

        # Get training results
        results = {
            "feature_importance": dict(
                sorted(
                    self.model.get_score(importance_type="gain").items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ),
            "model_version": self.model_version,
        }

        # Add validation metrics if available
        if len(eval_list) > 1:
            results["best_iteration"] = self.model.best_iteration
            results["best_score"] = self.model.best_score

        # Save the model
        self._save_model()

        return results

    def predict(self, model_data: List[ModelData]) -> List[Dict[str, float]]:
        """Generate track probabilities for new data"""
        if self.model is None:
            raise ValueError("Model must be trained or loaded before prediction")

        # Create dummy targets (won't be used)
        dummy_tracks = ["1"] * len(model_data)

        # Debug log for prediction data
        logger.info(f"Preparing prediction features for {len(model_data)} samples")
        if model_data and hasattr(model_data[0], 'id'):
            logger.info(f"Model data IDs for prediction: {[md.id for md in model_data[:5]]}...")

        # Prepare features
        X, _ = self._prepare_data(model_data, dummy_tracks)

        # Create DMatrix for prediction
        dtest = xgb.DMatrix(X, feature_names=self.feature_columns)

        # Generate predictions
        probabilities = self.model.predict(dtest)

        # Convert to dictionary format
        results = []
        for probs in probabilities:
            track_probs = {}
            for idx, prob in enumerate(probs):
                if idx in self.idx_to_track:
                    track = self.idx_to_track[idx]
                    track_probs[track] = float(prob)
            results.append(track_probs)

        return results

    def get_prediction_factors(self, model_data: ModelData) -> List[Dict[str, Any]]:
        """Generate SHAP values to explain predictions"""
        if self.model is None:
            raise ValueError("Model must be trained or loaded before generating explanations")

        # Create a single-element batch
        dummy_tracks = ["1"]
        X, _ = self._prepare_data([model_data], dummy_tracks)

        # Create explainer
        explainer = shap.TreeExplainer(self.model)

        # Get SHAP values
        dmatrix = xgb.DMatrix(X, feature_names=self.feature_columns)
        shap_values = explainer.shap_values(dmatrix)

        # Get the predicted class
        probs = self.predict([model_data])[0]
        predicted_track = max(probs.items(), key=lambda x: x[1])[0]
        predicted_idx = self.track_to_idx[predicted_track]

        # Get SHAP values for the predicted class
        class_shap_values = shap_values[predicted_idx][0]

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
        model_path = models_dir / f"track_pred_model_{self.model_version}_{timestamp}.xgb"
        scaler_path = models_dir / f"scaler_{self.model_version}_{timestamp}.pkl"
        metadata_path = models_dir / f"metadata_{self.model_version}_{timestamp}.json"

        # Save XGBoost model
        self.model.save_model(str(model_path))

        # Save scaler
        with open(scaler_path, "wb") as f:
            pickle.dump(self.scaler, f)

        # Save metadata (track mappings, feature columns, etc.)
        metadata = {
            "model_version": self.model_version,
            "timestamp": timestamp,
            "track_to_idx": self.track_to_idx,
            "idx_to_track": self.idx_to_track,
            "feature_columns": self.feature_columns,
            "xgb_params": self.xgb_params,
        }

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path}")
        return str(model_path)

    def load_model(
        self, model_path: str, metadata_path: str, scaler_path: Optional[str] = None
    ) -> None:
        """Load a trained model and its metadata"""
        # Load metadata first
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Set model parameters from metadata
        self.track_to_idx = metadata["track_to_idx"]
        self.idx_to_track = metadata["idx_to_track"]
        self.feature_columns = metadata["feature_columns"]
        self.model_version = metadata["model_version"]

        # Update XGBoost parameters if available
        if "xgb_params" in metadata:
            self.xgb_params = metadata["xgb_params"]

        # Load XGBoost model
        self.model = xgb.Booster()
        self.model.load_model(model_path)

        # Load scaler if provided
        if scaler_path and os.path.exists(scaler_path):
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)

        logger.info(f"Model loaded from {model_path}")
