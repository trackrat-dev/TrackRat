"""
Service for validating completed train journeys.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import or_

from trackcast.config import settings
from trackcast.data.collectors import NJTransitCollector
from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.services.train_stop_updater import TrainStopUpdater

logger = logging.getLogger(__name__)


class JourneyValidator:
    """Service for validating and tracking completed train journeys."""

    def __init__(self, train_repo: TrainRepository, stop_repo: TrainStopRepository):
        self.train_repo = train_repo
        self.stop_repo = stop_repo
        self.settings = settings

    def validate_completed_journeys(self, batch_size: int = 10) -> List[Train]:
        """
        Find and validate trains that should have completed their journeys.

        Args:
            batch_size: Maximum number of trains to validate in one batch

        Returns:
            List of validated trains
        """
        logger.info("Starting journey validation check")

        # Find candidates for validation
        candidates = self._find_validation_candidates(batch_size)
        validated_trains = []

        for train in candidates:
            try:
                if self._validate_train_journey(train):
                    validated_trains.append(train)
            except Exception as e:
                logger.error(f"Error validating train {train.train_id}: {e}")
                # Mark for retry later
                train.next_validation_check = datetime.utcnow() + timedelta(hours=1)
                self.train_repo.update(train)

        logger.info(f"Validated {len(validated_trains)} train journeys")
        return validated_trains

    def _find_validation_candidates(self, limit: int) -> List[Train]:
        """
        Find NJ Transit trains that need journey validation.

        Args:
            limit: Maximum number of trains to return

        Returns:
            List of trains needing validation
        """
        now = datetime.utcnow()

        # Query for trains that:
        # - Are NJ Transit
        # - Have DEPARTED status
        # - Journey not yet validated or need re-check
        # - Departed at least 1 hour ago
        query = (
            self.train_repo.session.query(Train)
            .filter(
                Train.data_source == "njtransit",
                Train.status == "DEPARTED",
                Train.departure_time > now - timedelta(hours=24),
                Train.departure_time < now - timedelta(hours=1),
                or_(
                    Train.journey_completion_status == None,
                    Train.journey_completion_status == "in_progress",
                    Train.next_validation_check < now,
                ),
            )
            .limit(limit)
        )

        return query.all()

    def _validate_train_journey(self, train: Train) -> bool:
        """
        Validate a single train's journey.

        Args:
            train: Train to validate

        Returns:
            True if successfully validated
        """
        logger.debug(f"Validating journey for train {train.train_id}")

        # Create appropriate NJ Transit collector
        station_config = next(
            (
                s
                for s in self.settings.njtransit_api.stations
                if s.code == train.origin_station_code
            ),
            None,
        )

        if not station_config:
            logger.warning(f"No station config found for {train.origin_station_code}")
            return False

        # Create updater and collector
        updater = TrainStopUpdater(self.train_repo, self.stop_repo)
        nj_collector = NJTransitCollector(
            station_code=station_config.code, station_name=station_config.name
        )
        updater.nj_collector = nj_collector

        try:
            # Update stops and check if journey is complete
            is_complete = updater.update_train_stops(train)

            if is_complete:
                train.journey_completion_status = "completed"
                train.journey_validated_at = datetime.utcnow()
                train.next_validation_check = None
                logger.info(f"Train {train.train_id} journey completed")
            else:
                # Estimate when to check again
                train.journey_completion_status = "in_progress"
                train.next_validation_check = self._estimate_next_check(train)
                logger.debug(
                    f"Train {train.train_id} still in progress, "
                    f"next check at {train.next_validation_check}"
                )

            self.train_repo.update(train)
            return True

        except Exception as e:
            logger.error(f"Failed to validate train {train.train_id}: {e}")
            return False

    def _estimate_next_check(self, train: Train) -> datetime:
        """
        Estimate when to next check a train's journey.

        Args:
            train: Train to estimate for

        Returns:
            Next check datetime
        """
        # Get the last scheduled stop
        stops = self.stop_repo.get_stops_for_train(train.train_id, train.departure_time)

        if stops:
            # Find latest scheduled stop
            last_stop = max(stops, key=lambda s: s.scheduled_time or datetime.min)
            if last_stop.scheduled_time:
                # Check 30 minutes after last scheduled stop
                return last_stop.scheduled_time + timedelta(minutes=30)

        # Default: check again in 2 hours
        return datetime.utcnow() + timedelta(hours=2)
