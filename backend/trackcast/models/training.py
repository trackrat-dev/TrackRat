"""
Model training and evaluation functions for TrackCast.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.db.models import ModelData, Train
from trackcast.models.pipeline import TrackPredictionPipeline

logger = logging.getLogger(__name__)


def train_models_for_all_stations(db_session: Session) -> Tuple[bool, Dict[str, Any]]:
    """
    Train separate models for each station.

    Args:
        db_session: SQLAlchemy database session

    Returns:
        Tuple containing success status and statistics dictionary
    """
    logger.info("Starting station-specific model training process")
    overall_stats = {
        "start_time": datetime.now().isoformat(),
        "stations": {},
        "total_success": 0,
        "total_failed": 0,
    }

    try:
        # Get unique station codes from the database
        station_codes = (
            db_session.query(Train.origin_station_code)
            .distinct()
            .filter(Train.origin_station_code.isnot(None))
            .all()
        )
        station_codes = [code[0] for code in station_codes]

        logger.info(f"Found {len(station_codes)} unique station codes: {station_codes}")

        for station_code in station_codes:
            logger.info(f"Training model for station: {station_code}")
            success, stats = train_model_for_station(db_session, station_code)

            overall_stats["stations"][station_code] = stats

            if success:
                overall_stats["total_success"] += 1
            else:
                overall_stats["total_failed"] += 1

        overall_stats["end_time"] = datetime.now().isoformat()

        return overall_stats["total_failed"] == 0, overall_stats

    except Exception as e:
        logger.error(f"Error in multi-station training: {str(e)}")
        overall_stats["error"] = str(e)
        return False, overall_stats


def train_model_for_station(db_session: Session, station_code: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Train a model for a specific station.

    Args:
        db_session: SQLAlchemy database session
        station_code: Station code to train model for

    Returns:
        Tuple containing success status and statistics dictionary
    """
    logger.info(f"Starting model training for station {station_code}")
    stats = {
        "start_time": datetime.now().isoformat(),
        "station_code": station_code,
        "data_points": 0,
        "train_size": 0,
        "validation_size": 0,
        "test_size": 0,
        "accuracy": None,
        "f1_score": None,
    }

    try:
        # Create output directories
        models_dir = Path(settings.model.save_path or "models")
        artifacts_dir = Path("training_artifacts") / station_code
        models_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Load data for this station only
        query = (
            db_session.query(Train, ModelData)
            .join(ModelData, Train.model_data_id == ModelData.id)
            .filter(
                Train.origin_station_code == station_code,
                Train.track != "",
                Train.track.isnot(None),
                Train.track_assigned_at.isnot(None),
            )
            .order_by(Train.departure_time)
        )

        results = query.all()
        logger.info(f"Loaded {len(results)} training samples for station {station_code}")

        if len(results) < 50:  # Lower threshold for station-specific models
            logger.error(
                f"Insufficient data for training station {station_code} (found {len(results)}, need at least 50)"
            )
            stats["error_message"] = "Insufficient training data"
            return False, stats

        # Rest of the training logic remains similar but with station-specific naming
        # Extract data
        model_data_list = []
        tracks = []

        for train, model_data in results:
            model_data_list.append(model_data)
            tracks.append(train.track)

        stats["data_points"] = len(model_data_list)

        # Split data
        train_ratio = 0.7
        val_ratio = 0.15
        test_ratio = 0.15

        train_size = int(len(model_data_list) * train_ratio)
        val_size = int(len(model_data_list) * val_ratio)

        train_data = model_data_list[:train_size]
        train_tracks = tracks[:train_size]

        val_data = model_data_list[train_size : train_size + val_size]
        val_tracks = tracks[train_size : train_size + val_size]

        test_data = model_data_list[train_size + val_size :]
        test_tracks = tracks[train_size + val_size :]

        stats["train_size"] = len(train_data)
        stats["validation_size"] = len(val_data)
        stats["test_size"] = len(test_data)

        # Initialize model with station-specific version
        model = TrackPredictionPipeline(model_version=f"{settings.model.version}_{station_code}")

        # Train the model
        if len(val_data) == 0:
            val_data = None
            val_tracks = None

        training_stats = model.train(train_data, train_tracks, val_data, val_tracks)

        # Save model with station-specific filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        model_filename = f"track_pred_model_{settings.model.version}_{station_code}_{timestamp}.pt"
        model_path = models_dir / model_filename

        model.save(str(model_path))
        logger.info(f"Saved model for station {station_code} to {model_path}")

        # Evaluate on test set
        if test_data and test_tracks:
            test_predictions = model.predict(test_data)
            predicted_tracks = [
                max(pred.items(), key=lambda x: x[1])[0] if pred else None
                for pred in test_predictions
            ]

            stats["accuracy"] = accuracy_score(test_tracks, predicted_tracks)
            stats["f1_score"] = f1_score(test_tracks, predicted_tracks, average="weighted")

            logger.info(
                f"Station {station_code} - Test accuracy: {stats['accuracy']:.3f}, F1 score: {stats['f1_score']:.3f}"
            )

        stats["model_path"] = str(model_path)
        stats["end_time"] = datetime.now().isoformat()

        return True, stats

    except Exception as e:
        logger.error(f"Error training model for station {station_code}: {str(e)}")
        stats["error_message"] = str(e)
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False, stats


def train_new_model(db_session: Session) -> Tuple[bool, Dict[str, Any]]:
    """
    Train a new model using historical data.

    Args:
        db_session: SQLAlchemy database session

    Returns:
        Tuple containing success status and statistics dictionary
    """
    logger.info("Starting model training process")
    stats = {
        "start_time": datetime.now().isoformat(),
        "data_points": 0,
        "train_size": 0,
        "validation_size": 0,
        "test_size": 0,
        "accuracy": None,
        "f1_score": None,
    }

    try:
        # Create output directories
        models_dir = Path(settings.model.save_path or "models")
        artifacts_dir = Path("training_artifacts")
        models_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Load data - We only want trains that have both features and a track assignment
        # that was made after the features were generated
        logger.info("Building query to retrieve trains with track assignments and features")

        # First, get the count of all trains
        all_trains_count = db_session.query(Train).count()
        logger.info(f"Total trains in database: {all_trains_count}")

        # Count trains with model data
        trains_with_model_data = (
            db_session.query(Train).filter(Train.model_data_id.isnot(None)).count()
        )
        logger.info(f"Trains with model data: {trains_with_model_data}")

        # Count trains with tracks
        trains_with_tracks = (
            db_session.query(Train).filter(Train.track != "", Train.track.isnot(None)).count()
        )
        logger.info(f"Trains with track assignments: {trains_with_tracks}")

        # Count trains with track assignment times
        trains_with_track_times = (
            db_session.query(Train).filter(Train.track_assigned_at.isnot(None)).count()
        )
        logger.info(f"Trains with track assignment times: {trains_with_track_times}")

        query = (
            db_session.query(Train, ModelData)
            .join(ModelData, Train.model_data_id == ModelData.id)
            .filter(
                Train.track != "",  # Has a track assignment
                Train.track.isnot(None),  # Proper SQLAlchemy syntax for IS NOT NULL
                Train.track_assigned_at.isnot(None),  # Proper SQLAlchemy syntax for IS NOT NULL
            )
            .order_by(Train.departure_time)
        )  # Time-based ordering

        # Execute query
        results = query.all()
        logger.info(f"Loaded {len(results)} training samples")

        if len(results) < 100:
            logger.error(
                f"Insufficient data for training (found {len(results)}, need at least 100)"
            )
            stats["error_message"] = "Insufficient training data"
            return False, stats

        # Extract data
        model_data_list = []
        tracks = []

        for train, model_data in results:
            model_data_list.append(model_data)
            tracks.append(train.track)

        stats["data_points"] = len(model_data_list)

        # Split data into train/val/test sets
        # Use time-based splitting since this is time series data
        train_ratio = 0.7
        val_ratio = 0.15
        test_ratio = 0.15

        train_size = int(len(model_data_list) * train_ratio)
        val_size = int(len(model_data_list) * val_ratio)

        train_data = model_data_list[:train_size]
        train_tracks = tracks[:train_size]

        val_data = model_data_list[train_size : train_size + val_size]
        val_tracks = tracks[train_size : train_size + val_size]

        test_data = model_data_list[train_size + val_size :]
        test_tracks = tracks[train_size + val_size :]

        stats["train_size"] = len(train_data)
        stats["validation_size"] = len(val_data)
        stats["test_size"] = len(test_data)

        logger.info(
            f"Split data: Train {len(train_data)}, Validation {len(val_data)}, Test {len(test_data)}"
        )

        # Update the train_split column for each train record
        logger.info("Updating train_split column for all train records...")

        # First, clear existing split info
        db_session.query(Train).update({Train.train_split: None})

        # Assign train set
        for i in range(train_size):
            train_record = results[i][0]  # Get Train object from (Train, ModelData) pair
            train_record.train_split = "train"

        # Assign validation set
        for i in range(train_size, train_size + val_size):
            train_record = results[i][0]
            train_record.train_split = "validation"

        # Assign test set
        for i in range(train_size + val_size, len(results)):
            train_record = results[i][0]
            train_record.train_split = "test"

        # Commit changes to DB
        db_session.commit()
        logger.info("Updated train_split column for all train records")

        # Initialize model
        model = TrackPredictionPipeline(model_version=settings.model.version)

        # Check for valid validation data
        if len(val_data) == 0 or len(val_tracks) == 0:
            logger.warning("No validation data available - training without validation")
            val_data = None
            val_tracks = None

        # Check that all test data is valid
        if len(test_data) == 0 or len(test_tracks) == 0:
            logger.warning("No test data available - will skip evaluation")
            test_data = []
            test_tracks = []

        # Log data shapes for debugging
        logger.info(
            f"Final data shapes - Train: {len(train_data)}/{len(train_tracks)}, Val: {len(val_data) if val_data else 0}/{len(val_tracks) if val_tracks else 0}, Test: {len(test_data)}/{len(test_tracks)}"
        )

        try:
            training_stats = model.train(train_data, train_tracks, val_data, val_tracks)
        except Exception as e:
            logger.error(f"Error in model training: {str(e)}")
            stats["error_message"] = f"Error in model training: {str(e)}"
            # Provide more detailed error information
            import traceback

            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False, stats

        # Evaluate on test set
        if test_data and test_tracks:
            logger.info("Evaluating model on test set")

            # Make predictions
            test_predictions = model.predict(test_data)
            predicted_tracks = [
                max(pred.items(), key=lambda x: x[1])[0] if pred else None
                for pred in test_predictions
            ]

            # Calculate metrics
            accuracy = accuracy_score(test_tracks, predicted_tracks)
            f1 = f1_score(test_tracks, predicted_tracks, average="weighted")

            stats["accuracy"] = float(accuracy)
            stats["f1_score"] = float(f1)

            logger.info(f"Test accuracy: {accuracy:.4f}, F1 score: {f1:.4f}")

            # Make predictions with probabilities for evaluation
            test_predictions_proba = model.predict(test_data)

            # Get timestamps for evaluation metrics
            test_timestamps = []
            test_lines = []
            test_destinations = []
            for i, (train, _) in enumerate(results[train_size + val_size :]):
                test_timestamps.append(train.departure_time)
                test_lines.append(train.line)
                test_destinations.append(train.destination)

            # Generate model timestamp for consistent file naming
            model_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

            # Visualization removed - keeping core training functionality only
            logger.info("Training artifacts generation skipped (visualization module removed)")

            # Still generate the classification report for backward compatibility
            report = classification_report(test_tracks, predicted_tracks)
            with open(artifacts_dir / "classification_report.txt", "w") as f:
                f.write(report)

        end_time = datetime.now()
        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = (
            end_time - datetime.fromisoformat(stats["start_time"])
        ).total_seconds()
        stats["training_stats"] = training_stats

        logger.info("Model training completed successfully")
        return True, stats

    except Exception as e:
        end_time = datetime.now()
        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = (
            end_time - datetime.fromisoformat(stats["start_time"])
        ).total_seconds()
        stats["error_message"] = str(e)
        logger.error(f"Error in model training: {str(e)}")
        return False, stats


def evaluate_model_performance(db_session: Session, days: int = 7) -> Dict[str, Any]:
    """
    Evaluate the current model's performance on recent data.

    Args:
        db_session: SQLAlchemy database session
        days: Number of days of history to evaluate (default: 7)

    Returns:
        Dictionary with evaluation metrics
    """
    logger.info(f"Evaluating model performance over the last {days} days")

    try:
        # Create output directory
        artifacts_dir = Path("training_artifacts")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Get cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Find tracks that were assigned after feature generation
        query = (
            db_session.query(Train, ModelData)
            .join(ModelData, Train.model_data_id == ModelData.id)
            .filter(
                Train.track != "",  # Has a track assignment
                Train.track.isnot(None),  # Non-null track
                Train.track_assigned_at.isnot(None),  # Has track assignment time
                Train.departure_time >= cutoff_date,  # Within time range
            )
            .order_by(Train.departure_time)
        )

        results = query.all()
        logger.info(f"Found {len(results)} trains for evaluation")

        if len(results) < 10:
            return {
                "status": "error",
                "message": f"Insufficient data for evaluation (found {len(results)}, need at least 10)",
                "timestamp": datetime.now().isoformat(),
            }

        # Extract data
        model_data_list = []
        tracks = []
        train_ids = []
        lines = []
        destinations = []

        for train, model_data in results:
            model_data_list.append(model_data)
            tracks.append(train.track)
            train_ids.append(train.train_id)
            lines.append(train.line)
            destinations.append(train.destination)

        # Load model
        model_info = TrackPredictionPipeline.find_latest_model()
        if not model_info:
            return {
                "status": "error",
                "message": "No trained model found",
                "timestamp": datetime.now().isoformat(),
            }

        # Create and load model
        model = TrackPredictionPipeline()
        model.load(
            model_info["model_path"],
            model_info["metadata_path"],
            model_info["scaler_path"],
        )

        # Generate predictions
        predictions = model.predict(model_data_list)
        predicted_tracks = [
            max(pred.items(), key=lambda x: x[1])[0] if pred else None for pred in predictions
        ]

        # Calculate metrics
        accuracy = accuracy_score(tracks, predicted_tracks)
        f1 = f1_score(tracks, predicted_tracks, average="weighted")

        # Get timestamps for time-based visualizations
        timestamps = [train.departure_time for train, _ in results]

        # Generate model timestamp for consistent file naming
        eval_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Create evaluation subdirectory
        eval_dir = artifacts_dir / f"eval_{days}days_{eval_timestamp}"
        eval_dir.mkdir(exist_ok=True, parents=True)

        # Visualization removed - evaluation metrics only
        logger.info("Evaluation visualization skipped (visualization module removed)")

        # For backward compatibility, generate text-based evaluation only
        eval_file = artifacts_dir / f"eval_report_{days}days.txt"

        # Generate classification report
        report = classification_report(tracks, predicted_tracks)
        with open(artifacts_dir / f"eval_report_{days}days.txt", "w") as f:
            f.write(report)

        # Calculate metrics by line
        line_metrics = {}
        for line_name in set(lines):
            line_indices = [i for i, l in enumerate(lines) if l == line_name]
            if len(line_indices) <= 1:
                continue

            line_tracks = [tracks[i] for i in line_indices]
            line_preds = [predicted_tracks[i] for i in line_indices]

            line_accuracy = accuracy_score(line_tracks, line_preds)
            line_metrics[line_name] = {
                "count": len(line_indices),
                "accuracy": float(line_accuracy),
            }

        # Calculate metrics by destination
        dest_metrics = {}
        for dest_name in set(destinations):
            dest_indices = [i for i, d in enumerate(destinations) if d == dest_name]
            if len(dest_indices) <= 1:
                continue

            dest_tracks = [tracks[i] for i in dest_indices]
            dest_preds = [predicted_tracks[i] for i in dest_indices]

            dest_accuracy = accuracy_score(dest_tracks, dest_preds)
            dest_metrics[dest_name] = {
                "count": len(dest_indices),
                "accuracy": float(dest_accuracy),
            }

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "days": days,
            "total_samples": len(tracks),
            "accuracy": float(accuracy),
            "f1_score": float(f1),
            "evaluation_report_file": str(eval_file),
            "line_metrics": line_metrics,
            "destination_metrics": dest_metrics,
            "model_version": getattr(settings.model, "version", "1.0.0"),
        }

    except Exception as e:
        logger.error(f"Error evaluating model performance: {str(e)}")
        return {"status": "error", "timestamp": datetime.now().isoformat(), "message": str(e)}


def find_latest_model() -> Optional[Dict[str, str]]:
    """
    Find the latest trained model files.

    Returns:
        Dictionary with model file paths or None if no model found
    """
    return TrackPredictionPipeline.find_latest_model()
