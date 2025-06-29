"""
Service for calculating and updating estimated arrival times for train stops.

This service extends the real-time arrival time estimates beyond just the next stop
to include all future stops based on current delays.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainRepository
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)


class EstimatedArrivalService:
    """Service for calculating and updating estimated arrival times."""

    def __init__(self, session: Session):
        """Initialize the service with a database session."""
        self.session = session
        self.train_repo = TrainRepository(session)

    def update_estimated_arrivals_for_train(self, train: Train) -> int:
        """
        Calculate and update estimated arrival times for all future stops of a train.

        Args:
            train: The train to update estimated arrivals for

        Returns:
            Number of stops updated with estimated arrival times
        """
        if not train.stops:
            logger.debug(f"Train {train.train_id} has no stops to update")
            return 0

        # Find the last departed stop and get its delay
        last_departed_stop = None
        delay_minutes = 0

        # Sort stops by scheduled arrival time to ensure proper order
        sorted_stops = sorted(
            [stop for stop in train.stops if stop.scheduled_arrival],
            key=lambda s: s.scheduled_arrival,
        )

        # Find the most recent departed stop
        for stop in sorted_stops:
            if stop.departed and stop.actual_departure and stop.scheduled_departure:
                # Calculate delay for this stop
                delay = int((stop.actual_departure - stop.scheduled_departure).total_seconds() / 60)
                last_departed_stop = stop
                delay_minutes = delay

        if not last_departed_stop or delay_minutes <= 0:
            logger.debug(f"Train {train.train_id} has no delay to propagate")
            return 0

        logger.info(
            f"Train {train.train_id}: Propagating {delay_minutes} minute delay from {last_departed_stop.station_name}"
        )

        # Update estimated arrival times for all future stops
        updates_count = 0
        for stop in sorted_stops:
            # Skip stops that have already departed
            if stop.departed:
                continue

            # Skip stops without scheduled arrival times
            if not stop.scheduled_arrival:
                continue

            # Calculate estimated arrival time
            estimated_arrival = stop.scheduled_arrival + timedelta(minutes=delay_minutes)

            # Only update if the estimated time is different or if no estimate exists
            if stop.estimated_arrival != estimated_arrival:
                stop.estimated_arrival = estimated_arrival
                updates_count += 1
                logger.debug(
                    f"Updated estimated arrival for {stop.station_name}: {estimated_arrival}"
                )

        if updates_count > 0:
            self.session.commit()
            logger.info(
                f"Updated {updates_count} stops with estimated arrival times for train {train.train_id}"
            )

        return updates_count

    def update_estimated_arrivals_for_active_trains(self, limit: Optional[int] = None) -> int:
        """
        Update estimated arrival times for all active trains with delays.

        Args:
            limit: Optional limit on number of trains to process

        Returns:
            Total number of stops updated
        """
        logger.info("Starting estimated arrival time updates for active trains")

        # Get active trains that might have delays
        # Focus on trains that are en route or boarding (not completed journeys)
        trains = self.train_repo.get_active_trains_with_stops(
            statuses=["BOARDING", "DEPARTED", "EN_ROUTE"], limit=limit
        )

        total_updates = 0
        processed_trains = 0

        for train in trains:
            try:
                updates = self.update_estimated_arrivals_for_train(train)
                total_updates += updates
                processed_trains += 1
            except Exception as e:
                logger.error(f"Error updating estimated arrivals for train {train.train_id}: {e}")
                continue

        logger.info(
            f"Processed {processed_trains} trains, updated {total_updates} stops with estimated arrival times"
        )
        return total_updates

    def clear_outdated_estimates(self, hours_old: int = 6) -> int:
        """
        Clear estimated arrival times for trains that are old or no longer active.

        Args:
            hours_old: Clear estimates for trains older than this many hours

        Returns:
            Number of stops cleared
        """
        cutoff_time = get_eastern_now() - timedelta(hours=hours_old)

        # Clear estimated arrivals for old trains
        cleared_count = (
            self.session.query(TrainStop)
            .join(Train)
            .filter(Train.departure_time < cutoff_time)
            .filter(TrainStop.estimated_arrival.isnot(None))
            .update({TrainStop.estimated_arrival: None}, synchronize_session=False)
        )

        if cleared_count > 0:
            self.session.commit()
            logger.info(f"Cleared {cleared_count} outdated estimated arrival times")

        return cleared_count

    def get_trains_with_estimated_arrivals(self, limit: int = 10) -> List[Train]:
        """
        Get trains that have estimated arrival times set.

        Args:
            limit: Maximum number of trains to return

        Returns:
            List of trains with estimated arrival data
        """
        return (
            self.session.query(Train)
            .join(TrainStop)
            .filter(TrainStop.estimated_arrival.isnot(None))
            .distinct()
            .limit(limit)
            .all()
        )
