"""
Feature engineering service for TrackCast.

This module provides the service that extracts features from train data
for use in machine learning prediction models.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository
from trackcast.features.pipelines import FeaturePipeline

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """Service that processes train data to generate features for the prediction model."""

    def __init__(self, db_session: Session):
        """
        Initialize the feature engineering service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.session = db_session
        self.train_repo = TrainRepository(db_session)
        self.feature_pipeline = FeaturePipeline(
            session=db_session, feature_version=settings.model.version
        )

    def clear_features(
        self, train_id=None, start_time=None, end_time=None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Clear features based on parameters.

        Args:
            train_id: Specific train ID to clear features for
            start_time: Start of time range to clear features
            end_time: End of time range to clear features

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_process_time = time.time()

        try:
            stats = {"timestamp": datetime.now().isoformat()}

            # Clear for specific train
            if train_id:
                result = self.train_repo.clear_features_for_train(train_id)
                stats.update(result)
                stats["scope"] = f"train_id={train_id}"
                success = result["trains_cleared"] > 0

            # Clear for time range
            elif start_time and end_time:
                result = self.train_repo.clear_features_for_time_range(start_time, end_time)
                stats.update(result)
                stats["scope"] = f"time_range={start_time} to {end_time}"
                success = result["trains_cleared"] > 0

            # Clear all (default)
            else:
                result = self.train_repo.clear_all_features()
                stats.update(result)
                stats["scope"] = "all"
                success = True

            # Calculate duration
            stats["duration_ms"] = int((time.time() - start_process_time) * 1000)

            return success, stats

        except Exception as e:
            logger.error(f"Error clearing features: {str(e)}")
            stats = {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "duration_ms": int((time.time() - start_process_time) * 1000),
            }
            return False, stats

    def process_pending_trains(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Process all trains that need features.

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        stats = {
            "timestamp": datetime.now().isoformat(),
            "trains_processed": 0,
            "trains_succeeded": 0,
            "trains_failed": 0,
            "duration_ms": 0,
        }

        try:
            # Get trains without features
            logger.info("Retrieving trains that need feature engineering")
            trains = self.train_repo.get_trains_needing_features()

            if not trains:
                logger.info("No trains found needing feature engineering")
                stats["duration_ms"] = int((time.time() - start_time) * 1000)
                return True, stats

            logger.info(f"Processing features for {len(trains)} trains")
            stats["trains_processed"] = len(trains)

            # Process trains through the feature pipeline
            # Each train will use its own departure time as reference to prevent self-conflicts
            success_count, failure_count, errors = self.feature_pipeline.process_trains(trains)

            stats["trains_succeeded"] = success_count
            stats["trains_failed"] = failure_count

            if errors:
                stats["errors"] = errors[:5]  # Store first 5 errors
                if len(errors) > 5:
                    stats["errors"].append(f"... and {len(errors) - 5} more errors")

            # Calculate duration
            stats["duration_ms"] = int((time.time() - start_time) * 1000)

            logger.info(
                f"Feature engineering completed: {success_count} succeeded, "
                f"{failure_count} failed in {stats['duration_ms']}ms"
            )

            return success_count > 0, stats

        except Exception as e:
            logger.error(f"Error in feature engineering: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def process_train_range(
        self, start_time: datetime, end_time: datetime
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process all trains within a specific time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Tuple containing success status and statistics dictionary
        """
        timer_start = time.time()
        stats = {
            "timestamp": datetime.now().isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "trains_processed": 0,
            "trains_succeeded": 0,
            "trains_failed": 0,
            "duration_ms": 0,
        }

        try:
            # Get trains within time range without features
            logger.info(
                f"Retrieving trains in range {start_time} to {end_time} that need feature engineering"
            )
            trains = (
                self.session.query(Train)
                .filter(
                    Train.departure_time >= start_time,
                    Train.departure_time <= end_time,
                    Train.model_data_id == None,
                )
                .all()
            )

            if not trains:
                logger.info("No trains found in range needing feature engineering")
                stats["duration_ms"] = int((time.time() - timer_start) * 1000)
                return True, stats

            logger.info(f"Processing features for {len(trains)} trains in range")
            stats["trains_processed"] = len(trains)

            # Process trains through the feature pipeline
            # Each train will use its own departure time as reference to prevent self-conflicts
            success_count, failure_count, errors = self.feature_pipeline.process_trains(trains)

            stats["trains_succeeded"] = success_count
            stats["trains_failed"] = failure_count

            if errors:
                stats["errors"] = errors[:5]  # Store first 5 errors
                if len(errors) > 5:
                    stats["errors"].append(f"... and {len(errors) - 5} more errors")

            # Calculate duration
            stats["duration_ms"] = int((time.time() - timer_start) * 1000)

            logger.info(
                f"Feature engineering for time range completed: {success_count} succeeded, "
                f"{failure_count} failed in {stats['duration_ms']}ms"
            )

            return success_count > 0, stats

        except Exception as e:
            logger.error(f"Error in feature engineering for time range: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - timer_start) * 1000)
            return False, stats

    def process_future_trains(self, hours_ahead: int = 6) -> Tuple[bool, Dict[str, Any]]:
        """
        Process all future trains departing within a specified time window.

        Args:
            hours_ahead: Number of hours ahead to process

        Returns:
            Tuple containing success status and statistics dictionary
        """
        now = datetime.now()
        end_time = now + timedelta(hours=hours_ahead)
        return self.process_train_range(now, end_time)

    def process_future_trains_with_regeneration(
        self, hours_ahead: int = 24
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process all future trains departing within a specified time window,
        clearing any existing features first to ensure regeneration.

        Args:
            hours_ahead: Number of hours ahead to process and regenerate features for

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        now = datetime.now()
        end_time = now + timedelta(hours=hours_ahead)

        stats = {
            "timestamp": datetime.now().isoformat(),
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "regeneration": True,
            "trains_processed": 0,
            "trains_succeeded": 0,
            "trains_failed": 0,
            "duration_ms": 0,
        }

        try:
            # First, clear all features for future trains in the time window
            logger.info(f"Clearing features for trains from {now} to {end_time} for regeneration")
            clear_stats = self.train_repo.clear_features_for_time_range(now, end_time)
            stats["features_cleared"] = clear_stats["trains_cleared"]

            # Then proceed with normal feature processing which will now include
            # the trains we just cleared features for
            logger.info(f"Processing features for all trains needing features")
            success, process_stats = self.process_pending_trains()

            # Update stats with processing results
            stats.update(
                {
                    "trains_processed": process_stats.get("trains_processed", 0),
                    "trains_succeeded": process_stats.get("trains_succeeded", 0),
                    "trains_failed": process_stats.get("trains_failed", 0),
                    "duration_ms": int((time.time() - start_time) * 1000),
                }
            )

            if "errors" in process_stats:
                stats["errors"] = process_stats["errors"]

            logger.info(
                f"Feature regeneration completed: cleared {stats['features_cleared']} feature sets, "
                f"regenerated {stats['trains_succeeded']} in {stats['duration_ms']}ms"
            )

            return success, stats

        except Exception as e:
            logger.error(f"Error in feature regeneration: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - start_time) * 1000)
            return False, stats

    def process_specific_train(self, train_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a specific train by ID.

        Args:
            train_id: Train ID to process

        Returns:
            Tuple containing success status and statistics dictionary
        """
        timer_start = time.time()
        stats = {
            "timestamp": datetime.now().isoformat(),
            "train_id": train_id,
            "success": False,
            "duration_ms": 0,
        }

        try:
            # Get the train
            train = self.train_repo.get_train_by_id(train_id)

            if not train:
                logger.error(f"Train not found with ID {train_id}")
                stats["error"] = f"Train not found with ID {train_id}"
                stats["duration_ms"] = int((time.time() - timer_start) * 1000)
                return False, stats

            if train.model_data_id:
                logger.info(f"Train {train_id} already has features")
                stats["info"] = "Train already has features"
                stats["model_data_id"] = train.model_data_id
                stats["duration_ms"] = int((time.time() - timer_start) * 1000)
                return True, stats

            # Process the train
            result = self.feature_pipeline.process_train(train)
            if result:
                logger.info(f"Successfully processed features for train {train_id}")
                stats["success"] = True
                stats["model_data_id"] = result.id
            else:
                logger.error(f"Failed to process features for train {train_id}")
                stats["error"] = "Feature processing failed"

            stats["duration_ms"] = int((time.time() - timer_start) * 1000)
            return stats["success"], stats

        except Exception as e:
            logger.error(f"Error in feature engineering for train {train_id}: {str(e)}")
            stats["error"] = str(e)
            stats["duration_ms"] = int((time.time() - timer_start) * 1000)
            return False, stats
