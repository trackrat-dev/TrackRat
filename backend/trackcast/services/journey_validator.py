"""
Service for validating completed train journeys.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_

from trackcast.config import settings
from trackcast.data.collectors import NJTransitCollector
from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.services.train_stop_updater import TrainStopUpdater
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)


class JourneyValidator:
    """Service for validating and tracking completed train journeys."""

    def __init__(self, train_repo: TrainRepository, stop_repo: TrainStopRepository):
        self.train_repo = train_repo
        self.stop_repo = stop_repo
        self.settings = settings

    def validate_completed_journeys(self, batch_size: int = 10) -> List[Train]:
        """
        Find and validate trains that should have completed their journeys using batch processing.

        Args:
            batch_size: Maximum number of trains to validate in one batch

        Returns:
            List of validated trains
        """
        logger.info("Starting journey validation check")

        # Find candidates for validation
        candidates = self._find_validation_candidates(batch_size)
        validated_trains = []

        # Group trains by train_id for batch processing
        trains_by_id = {}
        for train in candidates:
            if train.train_id not in trains_by_id:
                trains_by_id[train.train_id] = []
            trains_by_id[train.train_id].append(train)

        # Process each group with batch validation
        for train_id, train_group in trains_by_id.items():
            try:
                validated_group = self._validate_train_group(train_group)
                validated_trains.extend(validated_group)
            except Exception as e:
                logger.error(f"Error validating train group {train_id}: {e}")
                # Mark all trains in group for retry later
                for train in train_group:
                    train.next_validation_check = get_eastern_now() + timedelta(hours=1)
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
        now = get_eastern_now()

        # Query for trains that:
        # - Are NJ Transit
        # - Journey not yet validated or need re-check
        # - Within last 24 hours (includes future/active trains)
        query = (
            self.train_repo.session.query(Train)
            .filter(
                Train.data_source == "njtransit",
                Train.departure_time > now - timedelta(hours=24),
                or_(
                    # Trains never validated
                    Train.journey_completion_status == None,
                    # In-progress trains that are due for re-check
                    and_(
                        Train.journey_completion_status == "in_progress",
                        or_(
                            Train.next_validation_check == None,
                            Train.next_validation_check < now,
                        ),
                    ),
                ),
            )
            .order_by(Train.train_id)
            .limit(limit)
        )

        return query.all()

    def _validate_train_group(self, trains: List[Train]) -> List[Train]:
        """
        Validate a group of trains with the same train_id using batch processing.
        Handles trains from different origin stations by grouping them by station.

        Args:
            trains: List of trains to validate (must all have same train_id)

        Returns:
            List of successfully validated trains
        """
        if not trains:
            return []

        train_id = trains[0].train_id
        logger.debug(f"Validating {len(trains)} trains for train_id {train_id}")

        # Group trains by origin station since each station needs its own API call
        trains_by_station = {}
        for train in trains:
            station_code = train.origin_station_code
            if station_code not in trains_by_station:
                trains_by_station[station_code] = []
            trains_by_station[station_code].append(train)

        validated_trains = []

        # Process each station group
        for station_code, station_trains in trains_by_station.items():
            try:
                # Create appropriate NJ Transit collector
                station_config = next(
                    (s for s in self.settings.njtransit_api.stations if s.code == station_code),
                    None,
                )

                if not station_config:
                    logger.warning(f"No station config found for {station_code}")
                    continue

                # Create updater and collector
                updater = TrainStopUpdater(self.train_repo, self.stop_repo)
                nj_collector = NJTransitCollector(
                    station_code=station_config.code, station_name=station_config.name
                )
                updater.nj_collector = nj_collector

                # Update stops for all trains from this station with single API call
                completion_results = updater.update_multiple_trains_stops(station_trains)

                # Process completion results for each train
                for train in station_trains:
                    train_db_id = str(train.id)
                    is_complete = completion_results.get(train_db_id, False)

                    if is_complete:
                        train.journey_completion_status = "completed"
                        train.journey_validated_at = get_eastern_now()
                        train.next_validation_check = None
                        logger.info(f"Train {train.train_id} (DB ID: {train.id}) journey completed")
                    else:
                        # Estimate when to check again
                        train.journey_completion_status = "in_progress"
                        train.next_validation_check = self._estimate_next_check(train)
                        logger.debug(
                            f"Train {train.train_id} (DB ID: {train.id}) still in progress, "
                            f"next check at {train.next_validation_check}"
                        )

                    self.train_repo.update(train)
                    validated_trains.append(train)

                logger.info(
                    f"Batch validated {len(station_trains)} trains for train_id {train_id} from {station_code}"
                )

            except Exception as e:
                logger.error(f"Failed to validate trains for {train_id} from {station_code}: {e}")
                continue

        logger.info(f"Total batch validated {len(validated_trains)} trains for train_id {train_id}")
        return validated_trains

    def _validate_train_journey(self, train: Train) -> bool:
        """
        Validate a single train's journey (legacy method - kept for backward compatibility).

        Note: The main validation now uses _validate_train_group for batch processing.

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
                train.journey_validated_at = get_eastern_now()
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
            Next check datetime (always in the future)
        """
        now = get_eastern_now()

        # Get the last scheduled stop
        stops = self.stop_repo.get_stops_for_train(train.train_id, train.departure_time)

        if stops:
            # Find latest scheduled stop
            last_stop = max(stops, key=lambda s: s.scheduled_time or datetime.min)
            if last_stop.scheduled_time:
                # Check 30 minutes after last scheduled stop
                estimated_check = last_stop.scheduled_time + timedelta(minutes=30)
                # Ensure it's in the future - if not, default to 2 hours from now
                if estimated_check > now:
                    return estimated_check

        # Default: check again in 2 hours from now
        return now + timedelta(hours=2)
