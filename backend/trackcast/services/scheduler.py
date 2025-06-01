"""
Scheduler service for TrackCast.

This module provides the service that coordinates the periodic execution
of data collection, feature engineering, and prediction tasks.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Tuple

import schedule
from sqlalchemy import text
from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.db.connection import db_session
from trackcast.services.data_collector import DataCollectorService
from trackcast.services.feature_engineering import FeatureEngineeringService
from trackcast.services.prediction import PredictionService

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service that schedules and coordinates the periodic execution of all TrackCast components.

    The scheduler handles:
    1. Data collection from the NJ Transit API
    2. Feature engineering for new train data
    3. Track predictions for upcoming trains

    Each task runs on its own schedule, as defined in the configuration.
    """

    def __init__(self):
        """Initialize the scheduler service."""
        self.running = False
        self.thread = None
        self._setup_schedules()

    def _setup_schedules(self) -> None:
        """Set up the scheduled tasks based on configuration."""
        # Clear any existing schedules
        schedule.clear()

        # Data collection interval
        collection_interval = getattr(settings.scheduler, "collection_interval_minutes", 1)
        schedule.every(collection_interval).minutes.do(self._run_data_collection)
        logger.info(f"Scheduled data collection every {collection_interval} minutes")

        # Feature engineering interval
        feature_interval = getattr(settings.scheduler, "feature_engineering_interval_minutes", 5)
        schedule.every(feature_interval).minutes.do(self._run_feature_engineering)
        logger.info(f"Scheduled feature engineering every {feature_interval} minutes")

        # Prediction interval
        prediction_interval = getattr(settings.scheduler, "prediction_interval_minutes", 2)
        schedule.every(prediction_interval).minutes.do(self._run_prediction)
        logger.info(f"Scheduled prediction every {prediction_interval} minutes")

        # Schedule health check to verify all components are running
        schedule.every(15).minutes.do(self._health_check)
        logger.info("Scheduled health check every 15 minutes")

    def start(self) -> None:
        """Start the scheduler in a separate thread."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True
        self.thread.start()

        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        self.running = False

        if self.thread:
            # Wait for the thread to finish, but with a timeout
            self.thread.join(timeout=5)

        logger.info("Scheduler stopped")

    def _run_scheduler(self) -> None:
        """Run the scheduler loop."""
        # Run all tasks immediately on startup
        self._run_data_collection()
        self._run_feature_engineering()
        self._run_prediction()

        while self.running:
            try:
                # Run pending scheduled tasks
                schedule.run_pending()

                # Sleep for a short time
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                # Don't let an error stop the scheduler
                time.sleep(5)

    def _run_with_session(
        self, task_func: Callable[[Session], Tuple[bool, Dict[str, Any]]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run a task function with a database session.

        Args:
            task_func: Function that takes a session and returns (success, stats)

        Returns:
            Tuple of (success, stats)
        """
        with db_session() as session:
            try:
                return task_func(session)
            except Exception as e:
                logger.error(f"Error running task: {str(e)}")
                return False, {"error": str(e)}

    def _run_data_collection(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run the data collection process.

        Returns:
            Tuple of (success, stats)
        """
        logger.info("Running scheduled data collection")

        def task(session: Session) -> Tuple[bool, Dict[str, Any]]:
            service = DataCollectorService(session)
            return service.run_collection()

        return self._run_with_session(task)

    def _run_feature_engineering(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run the feature engineering process, regenerating features for future trains.

        Returns:
            Tuple of (success, stats)
        """
        logger.info("Running scheduled feature engineering with regeneration")

        def task(session: Session) -> Tuple[bool, Dict[str, Any]]:
            service = FeatureEngineeringService(session)
            # Use regeneration method to ensure future trains have fresh features
            return service.process_future_trains_with_regeneration()

        return self._run_with_session(task)

    def _run_prediction(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run the prediction process, regenerating predictions for future trains.

        Returns:
            Tuple of (success, stats)
        """
        logger.info("Running scheduled prediction with regeneration")

        def task(session: Session) -> Tuple[bool, Dict[str, Any]]:
            service = PredictionService(session)
            # Use regeneration method to ensure future trains have fresh predictions
            return service.run_prediction_with_regeneration()

        return self._run_with_session(task)

    def _health_check(self) -> None:
        """
        Run a health check to verify all components are operational.

        This function logs warnings if any component is not functioning.
        """
        logger.info("Running scheduler health check")

        # Check database connection
        try:
            with db_session() as session:
                session.execute(text("SELECT 1"))
            logger.info("Database connection: OK")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")

        # Check data collection
        try:
            with db_session() as session:
                # Check for recent train data (last 30 minutes)
                cutoff_time = datetime.now() - timedelta(minutes=30)

                from trackcast.db.models import Train

                recent_trains = (
                    session.query(Train.id).filter(Train.created_at >= cutoff_time).count()
                )

                if recent_trains > 0:
                    logger.info(f"Data collection: OK ({recent_trains} trains in last 30 minutes)")
                else:
                    logger.warning("Data collection may be failing: No recent train data")
        except Exception as e:
            logger.error(f"Data collection health check failed: {str(e)}")

        # Check feature engineering
        try:
            with db_session() as session:
                # Check for unprocessed trains
                from trackcast.db.models import Train

                unprocessed = (
                    session.query(Train.id)
                    .filter(Train.model_data_id is None, Train.departure_time >= datetime.now())
                    .count()
                )

                if unprocessed <= 5:
                    logger.info(f"Feature engineering: OK ({unprocessed} unprocessed trains)")
                else:
                    logger.warning(
                        f"Feature engineering may be delayed: {unprocessed} unprocessed trains"
                    )
        except Exception as e:
            logger.error(f"Feature engineering health check failed: {str(e)}")

        # Check prediction
        try:
            with db_session() as session:
                # Check for trains with features but no predictions
                from trackcast.db.models import Train

                unpredicted = (
                    session.query(Train.id)
                    .filter(
                        Train.model_data_id is not None,
                        Train.prediction_data_id is None,
                        Train.departure_time >= datetime.now(),
                        Train.track is None,
                    )
                    .count()
                )

                if unpredicted <= 5:
                    logger.info(f"Prediction: OK ({unpredicted} unpredicted trains)")
                else:
                    logger.warning(f"Prediction may be delayed: {unpredicted} unpredicted trains")
        except Exception as e:
            logger.error(f"Prediction health check failed: {str(e)}")

        logger.info("Health check completed")

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the scheduler.

        Returns:
            Dictionary with scheduler status
        """
        return {
            "running": self.running,
            "timestamp": datetime.now().isoformat(),
            "schedules": {
                "data_collection": getattr(settings.scheduler, "collection_interval_minutes", 1),
                "feature_engineering": getattr(
                    settings.scheduler, "feature_engineering_interval_minutes", 5
                ),
                "prediction": getattr(settings.scheduler, "prediction_interval_minutes", 2),
            },
        }
