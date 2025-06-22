"""
Service for updating train stop data from NJ Transit API.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from trackcast.data.collectors import NJTransitCollector
from trackcast.db.models import Train, TrainStop
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.exceptions import APIError
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)


class TrainStopUpdater:
    """Service for fetching and updating train stop data."""

    def __init__(
        self,
        train_repo: TrainRepository,
        stop_repo: TrainStopRepository,
        nj_collector: Optional[NJTransitCollector] = None,
    ):
        self.train_repo = train_repo
        self.stop_repo = stop_repo
        self.nj_collector = nj_collector

    def update_multiple_trains_stops(self, trains: List[Train]) -> Dict[str, bool]:
        """
        Update train stops for multiple trains with the same train_id using a single NJ Transit API call.

        Args:
            trains: List of trains to update (must all have same train_id and be NJ Transit)

        Returns:
            Dict mapping train database ID to completion status

        Raises:
            APIError: If the API request fails
        """
        if not trains:
            return {}

        if not self.nj_collector:
            raise ValueError("NJTransitCollector not provided")

        # Validate all trains have same train_id and are NJ Transit
        train_id = trains[0].train_id
        non_nj_trains = [t for t in trains if t.data_source != "njtransit"]
        if non_nj_trains:
            logger.warning(f"Skipping {len(non_nj_trains)} non-NJ Transit trains")

        different_id_trains = [t for t in trains if t.train_id != train_id]
        if different_id_trains:
            raise ValueError(
                f"All trains must have same train_id, found multiple: {set(t.train_id for t in trains)}"
            )

        # Filter to only NJ Transit trains
        nj_trains = [t for t in trains if t.data_source == "njtransit"]
        if not nj_trains:
            logger.warning(f"No NJ Transit trains to update for train_id {train_id}")
            return {}

        try:
            # Fetch stop data from API once for the train_id
            stop_data = self.nj_collector.get_train_stops(train_id)

            if not stop_data or "STOPS" not in stop_data:
                logger.warning(f"No stop data returned for train {train_id}")
                return {str(train.id): False for train in nj_trains}

            # Process and update stops for each train
            results = {}
            for train in nj_trains:
                try:
                    journey_complete = self._process_stop_updates(train, stop_data["STOPS"])

                    # Update the stops_last_updated timestamp
                    train.stops_last_updated = get_eastern_now()
                    self.train_repo.update(train)

                    results[str(train.id)] = journey_complete
                    logger.debug(
                        f"Updated stops for train {train.train_id} (DB ID: {train.id}), complete: {journey_complete}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error updating stops for train {train.train_id} (DB ID: {train.id}): {e}"
                    )
                    results[str(train.id)] = False

            logger.info(f"Updated stops for {len(results)} trains with train_id {train_id}")
            return results

        except APIError as e:
            logger.error(f"API error updating stops for train {train_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating stops for train {train_id}: {e}")
            raise

    def update_train_stops(self, train: Train) -> bool:
        """
        Update train stops using NJ Transit getTrainStopList API.

        Args:
            train: The train to update stops for

        Returns:
            True if journey is complete, False otherwise

        Raises:
            APIError: If the API request fails
        """
        if not self.nj_collector:
            raise ValueError("NJTransitCollector not provided")

        if train.data_source != "njtransit":
            logger.warning(f"Train {train.train_id} is not an NJ Transit train")
            return False

        try:
            # Fetch stop data from API
            stop_data = self.nj_collector.get_train_stops(train.train_id)

            if not stop_data or "STOPS" not in stop_data:
                logger.warning(f"No stop data returned for train {train.train_id}")
                return False

            # Process and update stops
            journey_complete = self._process_stop_updates(train, stop_data["STOPS"])

            # Update the stops_last_updated timestamp
            train.stops_last_updated = get_eastern_now()
            self.train_repo.update(train)

            return journey_complete

        except APIError as e:
            logger.error(f"API error updating stops for train {train.train_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating stops for train {train.train_id}: {e}")
            raise

    def _process_stop_updates(self, train: Train, stops_data: list) -> bool:
        """
        Process stop updates from API response.

        Args:
            train: The train being updated
            stops_data: List of stop data from API

        Returns:
            True if all stops have departed (journey complete)
        """
        journey_complete = True

        for stop_data in stops_data:
            # Find matching TrainStop record
            existing_stop = self.stop_repo.get_stop_by_train_and_station(
                train_id=train.train_id,
                train_departure_time=train.departure_time,
                station_name=stop_data.get("STATIONNAME", ""),
                data_source=train.data_source,
            )

            if not existing_stop:
                # Log but continue - stop might not be in our database
                logger.debug(
                    f"Stop not found for train {train.train_id} at "
                    f"{stop_data.get('STATIONNAME', 'Unknown')}"
                )
                continue

            # Update actual times - NEVER modify scheduled_time!
            if stop_data.get("TIME"):  # Actual arrival time
                existing_stop.actual_arrival_time = self._parse_nj_datetime(stop_data["TIME"])

            if stop_data.get("DEP_TIME"):  # Actual departure time
                existing_stop.departure_time = self._parse_nj_datetime(stop_data["DEP_TIME"])

            # Update status fields
            existing_stop.departed = stop_data.get("DEPARTED") == "YES"
            existing_stop.stop_status = stop_data.get("STOP_STATUS", "")
            existing_stop.last_seen_at = get_eastern_now()

            # Check if this stop is still pending
            if not existing_stop.departed:
                journey_complete = False

            # Save the updated stop
            self.stop_repo.update(existing_stop)

        return journey_complete

    def _parse_nj_datetime(self, datetime_str: str) -> Optional[datetime]:
        """
        Parse NJ Transit datetime format.

        Args:
            datetime_str: Datetime string in format "30-May-2024 10:52:30 AM"

        Returns:
            Parsed datetime or None if invalid
        """
        if not datetime_str:
            return None

        try:
            return datetime.strptime(datetime_str, "%d-%b-%Y %I:%M:%S %p")
        except ValueError:
            logger.warning(f"Invalid datetime format: {datetime_str}")
            return None

    def should_refresh_stops(self, train: Train) -> bool:
        """
        Determine if train stop data should be refreshed.

        Args:
            train: The train to check

        Returns:
            True if stops should be refreshed
        """
        # Only refresh NJ Transit trains
        if train.data_source != "njtransit":
            return False

        # Allow refresh for all train statuses

        # Never fetched stop data
        if not train.stops_last_updated:
            return True

        # Journey already complete, no need to refresh
        if train.journey_completion_status == "completed":
            return False

        # Check if data is stale (>5 minutes old)
        if train.stops_last_updated is None:
            return True

        try:
            minutes_since_update = (
                get_eastern_now() - train.stops_last_updated
            ).total_seconds() / 60
            return minutes_since_update > 5
        except (TypeError, AttributeError):
            # Handle case where stops_last_updated is not a datetime (e.g., in tests with mocks)
            return True
