"""
Data collection service for TrackCast.

This module provides the service that collects train data from the NJ Transit API,
processes it, and stores it in the database.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.data.collectors import AmtrakCollector, NJTransitCollector
from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.exceptions import APIError
from trackcast.utils import clean_destination, get_eastern_now

logger = logging.getLogger(__name__)


class DataCollectorService:
    """Service that collects train data from NJ Transit API and updates the database."""

    def __init__(self, db_session: Session):
        """
        Initialize the data collector service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.session = db_session
        self.train_repo = TrainRepository(db_session)
        self.stop_repo = TrainStopRepository(db_session)

        # Create collectors for each enabled station
        self.station_collectors = []

        # Check if njtransit_api settings exist and have stations
        if (
            hasattr(settings, "njtransit_api")
            and settings.njtransit_api
            and hasattr(settings.njtransit_api, "stations")
        ):
            for station in settings.njtransit_api.stations:
                if station.enabled:
                    collector = NJTransitCollector(
                        base_url_or_config=settings.njtransit_api.base_url,
                        station_code=station.code,
                        station_name=station.name,
                        retry_attempts=settings.njtransit_api.retry_attempts,
                        timeout=settings.njtransit_api.timeout_seconds,
                    )
                    self.station_collectors.append(
                        {
                            "station_code": station.code,
                            "station_name": station.name,
                            "collector": collector,
                            "collector_type": "njtransit",
                        }
                    )
                    logger.info(
                        f"Initialized NJ Transit collector for station: {station.name} ({station.code})"
                    )

        # Create Amtrak collector if enabled
        if getattr(settings, "amtrak_api", None) and getattr(settings.amtrak_api, "enabled", False):
            try:
                amtrak_collector = AmtrakCollector(
                    base_url=settings.amtrak_api.base_url,
                    retry_attempts=settings.amtrak_api.retry_attempts,
                    timeout=settings.amtrak_api.timeout_seconds,
                    debug_mode=settings.amtrak_api.debug_mode,
                )
                self.station_collectors.append(
                    {
                        "station_code": "AMTRAK",
                        "station_name": "Amtrak Network",
                        "collector": amtrak_collector,
                        "collector_type": "amtrak",
                    }
                )
                logger.info("Initialized Amtrak collector for all Amtrak routes")
            except Exception as e:
                logger.error(f"Failed to initialize Amtrak collector: {str(e)}")

    def run_collection(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run a single collection cycle for all stations.

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = time.time()
        stats = {
            "collection_timestamp": get_eastern_now().isoformat(),
            "stations_processed": 0,
            "stations_failed": 0,
            "trains_total": 0,
            "trains_new": 0,
            "trains_updated": 0,
            "trains_departed": 0,
            "duration_ms": 0,
            "station_details": {},
        }

        all_success = True

        # Collect data from each station
        for station_info in self.station_collectors:
            station_code = station_info["station_code"]
            station_name = station_info["station_name"]
            collector = station_info["collector"]
            collector_type = station_info["collector_type"]

            station_stats = {
                "trains_total": 0,
                "trains_new": 0,
                "trains_updated": 0,
                "success": False,
                "error": None,
            }

            try:
                logger.info(
                    f"Starting data collection for station: {station_name} ({station_code})"
                )
                data, collector_stats = collector.run()

                # Process collected data differently based on collector type
                if collector_type == "amtrak":
                    station_success, processing_stats = self._process_amtrak_data(data)
                else:
                    station_success, processing_stats = self._process_train_data_for_station(
                        data, station_code, station_name
                    )

                if station_success:
                    station_stats["success"] = True
                    station_stats["trains_total"] = len(data)
                    station_stats["trains_new"] = processing_stats.get("trains_new", 0)
                    station_stats["trains_updated"] = processing_stats.get("trains_updated", 0)

                    # Update overall stats
                    stats["stations_processed"] += 1
                    stats["trains_total"] += station_stats["trains_total"]
                    stats["trains_new"] += station_stats["trains_new"]
                    stats["trains_updated"] += station_stats["trains_updated"]
                else:
                    station_stats["error"] = "Failed to process train data"
                    stats["stations_failed"] += 1
                    all_success = False
                    logger.error(f"Failed to process train data for station {station_name}")

            except APIError as e:
                station_stats["error"] = f"API error: {str(e)}"
                stats["stations_failed"] += 1
                all_success = False
                logger.error(f"API error for station {station_name}: {str(e)}")

            except Exception as e:
                station_stats["error"] = f"Error: {str(e)}"
                stats["stations_failed"] += 1
                all_success = False
                logger.error(f"Error collecting data for station {station_name}: {str(e)}")

            # Add station details to stats
            stats["station_details"][station_code] = station_stats

        # Journey validation is handled by CLI after data collection
        stats["journeys_validated"] = 0

        # Final statistics
        stats["duration_ms"] = int((time.time() - start_time) * 1000)

        logger.info(
            f"Data collection completed: {stats['stations_processed']} stations processed, "
            f"{stats['stations_failed']} failed, {stats['trains_total']} total trains in {stats['duration_ms']}ms"
        )

        return all_success, stats

    def _process_train_data_for_station(
        self, train_data: List[Dict[str, Any]], station_code: str, station_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process collected train data for a specific station and update the database.

        Args:
            train_data: List of train data dictionaries from the collector
            station_code: Code of the origin station
            station_name: Name of the origin station

        Returns:
            Tuple of (success status, statistics dictionary)
        """
        try:
            from trackcast.services.station_mapping import StationMapper

            station_mapper = StationMapper()

            trains_new = 0
            trains_updated = 0
            trains_departed = 0
            current_time = get_eastern_now()

            # Get a set of train IDs in this batch for later comparison
            current_train_ids = {
                (train.get("train_id"), train.get("departure_time")) for train in train_data
            }

            # Process each train record
            for train_record in train_data:
                # Convert string departure time to datetime if needed
                departure_time = train_record.get("departure_time")
                if isinstance(departure_time, str):
                    try:
                        # Parse time string as-is, preserving original precision
                        departure_time = datetime.fromisoformat(departure_time)
                    except ValueError:
                        # Try parsing as original string
                        try:
                            departure_time = datetime.fromisoformat(departure_time)
                        except ValueError:
                            logger.warning(f"Invalid departure time format: {departure_time}")
                            departure_time = None

                if not departure_time:
                    logger.warning(f"Skipping train with missing departure time: {train_record}")
                    continue

                # Check if train already exists (now including origin station)
                existing_train = self.train_repo.get_train_by_id_time_and_station(
                    train_record.get("train_id"), departure_time, station_code
                )

                if existing_train:
                    # Update existing train
                    update_data = {
                        "track": train_record.get("track"),
                        "line": train_record.get("line"),
                        "destination": train_record.get(
                            "destination"
                        ),  # Already cleaned in collector
                        "line_code": train_record.get("line_code"),
                    }

                    # Only update status if it's not BOARDING for Amtrak trains
                    # (BOARDING status is misleading as trains show this even when at different locations)
                    new_status = train_record.get("status")
                    data_source = train_record.get("data_source", "njtransit")
                    if not (data_source == "amtrak" and new_status == "BOARDING"):
                        update_data["status"] = new_status
                    else:
                        logger.debug(
                            f"Skipping BOARDING status update for Amtrak train {train_record.get('train_id')}"
                        )

                    self.train_repo.update_train(existing_train, update_data, current_time)
                    trains_updated += 1

                    # Check if the train has departed
                    if train_record.get("status") == "DEPARTED":
                        trains_departed += 1
                else:
                    # Create new train record
                    new_train = {
                        "train_id": train_record.get("train_id"),
                        "origin_station_code": station_code,
                        "origin_station_name": station_name,
                        "line": train_record.get("line"),
                        "line_code": train_record.get("line_code"),
                        "destination": train_record.get(
                            "destination"
                        ),  # Already cleaned in collector
                        "departure_time": departure_time,
                        "track": train_record.get("track"),
                        "status": train_record.get("status"),
                        "data_source": train_record.get("data_source", "njtransit"),
                        "delay_minutes": train_record.get("delay_minutes"),
                    }

                    # Set track_assigned_at if track is already known
                    if train_record.get("track"):
                        new_train["track_assigned_at"] = current_time

                    # Create train in database
                    created_train = self.train_repo.create_train(new_train, current_time)
                    trains_new += 1

                # Process stops for both new and existing trains
                if "stops" in train_record and train_record["stops"]:
                    try:
                        # Pass stop times as-is, fuzzy matching handles consolidation
                        self.stop_repo.upsert_train_stops(
                            train_record.get("train_id"),
                            departure_time,
                            train_record["stops"],  # Use original stops without normalization
                            train_record.get("data_source", "njtransit"),
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to process stops for train {train_record.get('train_id')}: {str(e)}"
                        )

            # Check for trains that have departed but aren't in the API response
            departed_count = self._check_departed_trains(current_train_ids, station_code)
            trains_departed += departed_count

            # Log results
            logger.info(
                f"Processed {len(train_data)} trains for {station_name}: "
                f"{trains_new} new, {trains_updated} updated, {trains_departed} departed"
            )

            return True, {
                "trains_new": trains_new,
                "trains_updated": trains_updated,
                "trains_departed": trains_departed,
            }

        except Exception as e:
            logger.error(f"Error processing train data for {station_name}: {str(e)}")
            self.session.rollback()
            return False, {}

    def _check_departed_trains(self, current_train_ids: set, station_code: str) -> int:
        """
        Check for trains that have departed but are no longer in the API response.

        Args:
            current_train_ids: Set of (train_id, departure_time) tuples from current API response
            station_code: Station code to filter trains

        Returns:
            Number of trains marked as departed
        """
        try:
            # Look for trains with departure times before current time and status of BOARDING
            # that are also not in the current API response
            current_time = get_eastern_now()

            logger.info(
                f"Running departed train check at {current_time}, current API has {len(current_train_ids)} train records"
            )

            query = self.session.query(Train).filter(
                Train.departure_time <= current_time,
                Train.status == "BOARDING",
                Train.origin_station_code == station_code,
            )

            potential_departed = query.all()
            logger.info(
                f"Found {len(potential_departed)} boarding trains with departure times in the past"
            )

            departed_count = 0

            for train in potential_departed:
                # Check if this train is in the current API response
                train_key = (train.train_id, train.departure_time)
                if train_key not in current_train_ids:
                    # Train is no longer in API but hasn't been marked as departed
                    logger.info(
                        f"Train {train.train_id} to {train.destination} scheduled for {train.departure_time} "
                        f"on track {train.track} is no longer in API - marking as DEPARTED"
                    )

                    # Set both status and track_released_at to ensure delay calculation happens
                    update_data = {
                        "status": "DEPARTED",
                        "track_released_at": current_time,
                    }

                    # Delay calculation will happen automatically in update_train
                    # since we're setting track_released_at and the train doesn't have delay_minutes yet
                    self.train_repo.update_train(train, update_data, current_time)
                    departed_count += 1
                else:
                    logger.info(
                        f"Train {train.train_id} to {train.destination} scheduled for {train.departure_time} "
                        f"is still in API despite being past departure time"
                    )

            if departed_count > 0:
                logger.info(
                    f"Marked {departed_count} trains as departed that were no longer in API response"
                )
            else:
                logger.info("No trains needed to be marked as departed in this collection cycle")

            return departed_count

        except Exception as e:
            logger.error(f"Error checking for departed trains: {str(e)}")
            # Don't fail the entire collection process for this
            return 0

    def _process_amtrak_data(self, train_data: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Process collected Amtrak train data and update the database.

        Args:
            train_data: List of processed Amtrak train data dictionaries

        Returns:
            Tuple of (success status, statistics dictionary)
        """
        try:
            from trackcast.services.station_mapping import StationMapper

            station_mapper = StationMapper()

            trains_new = 0
            trains_updated = 0
            trains_departed = 0
            current_time = get_eastern_now()

            # Get a set of train IDs in this batch for later comparison
            current_train_ids = {
                (
                    train.get("train_id"),
                    train.get("departure_time"),
                    train.get("origin_station_code"),
                )
                for train in train_data
            }

            # Process each train record
            for train_record in train_data:
                # Normalize Amtrak data for better consolidation
                normalized_train = self._normalize_amtrak_train_data(train_record, station_mapper)

                # Convert string departure time to datetime if needed
                departure_time = normalized_train.get("departure_time")
                if isinstance(departure_time, str):
                    try:
                        departure_time = datetime.fromisoformat(departure_time)
                    except ValueError:
                        logger.warning(f"Invalid departure time format: {departure_time}")
                        departure_time = None

                if not departure_time:
                    logger.warning(
                        f"Skipping Amtrak train with missing departure time: {normalized_train}"
                    )
                    continue

                origin_station_code = normalized_train.get("origin_station_code")
                if not origin_station_code:
                    logger.warning(
                        f"Skipping Amtrak train with missing origin station: {normalized_train}"
                    )
                    continue

                # Check if train already exists (including data source)
                existing_train = self.train_repo.get_train_by_id_time_and_station_source(
                    normalized_train.get("train_id"), departure_time, origin_station_code, "amtrak"
                )

                if existing_train:
                    # Update existing train
                    update_data = {
                        "track": normalized_train.get("track"),
                        "status": normalized_train.get("status"),
                        "line": normalized_train.get("line"),
                        "destination": normalized_train.get("destination"),
                        "line_code": normalized_train.get("line_code"),
                        "delay_minutes": normalized_train.get("delay_minutes"),
                    }

                    self.train_repo.update_train(existing_train, update_data, current_time)
                    trains_updated += 1

                    # Check if the train has departed
                    if normalized_train.get("status") == "DEPARTED":
                        trains_departed += 1
                else:
                    # Create new train record
                    new_train = {
                        "train_id": normalized_train.get("train_id"),
                        "origin_station_code": origin_station_code,
                        "origin_station_name": normalized_train.get("origin_station_name"),
                        "line": normalized_train.get("line"),
                        "line_code": normalized_train.get("line_code"),
                        "destination": normalized_train.get("destination"),
                        "departure_time": departure_time,
                        "track": normalized_train.get("track"),
                        "status": normalized_train.get("status"),
                        "data_source": "amtrak",
                        "delay_minutes": normalized_train.get("delay_minutes"),
                    }

                    # Set track_assigned_at if track is already known
                    if normalized_train.get("track"):
                        new_train["track_assigned_at"] = current_time

                    # Create train in database
                    created_train = self.train_repo.create_train(new_train, current_time)
                    trains_new += 1

                # Process stops for both new and existing trains
                if "stops" in normalized_train and normalized_train["stops"]:
                    try:
                        self.stop_repo.upsert_train_stops(
                            normalized_train.get("train_id"),
                            departure_time,
                            normalized_train["stops"],
                            "amtrak",
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to process stops for Amtrak train {normalized_train.get('train_id')}: {str(e)}"
                        )

            # Log results
            logger.info(
                f"Processed {len(train_data)} Amtrak trains: "
                f"{trains_new} new, {trains_updated} updated, {trains_departed} departed"
            )

            return True, {
                "trains_new": trains_new,
                "trains_updated": trains_updated,
                "trains_departed": trains_departed,
            }

        except Exception as e:
            logger.error(f"Error processing Amtrak train data: {str(e)}")
            self.session.rollback()
            return False, {}

    def _normalize_amtrak_train_data(
        self, train_record: Dict[str, Any], station_mapper
    ) -> Dict[str, Any]:
        """
        Normalize Amtrak train data to match NJ Transit format for better consolidation.

        Args:
            train_record: Original Amtrak train data
            station_mapper: StationMapper instance

        Returns:
            Normalized train record
        """
        try:
            normalized = train_record.copy()

            # Check if this train should be aligned with NJ Transit departure time
            train_id = train_record.get("train_id")
            departure_time = train_record.get("departure_time")

            if departure_time:
                # Preserve original time precision, fuzzy matching handles consolidation
                normalized["departure_time"] = departure_time

            # Normalize origin station
            origin_code = train_record.get("origin_station_code")
            origin_name = train_record.get("origin_station_name")
            if origin_code or origin_name:
                normalized_station = station_mapper.normalize_amtrak_station(
                    origin_code, origin_name
                )
                if (
                    normalized_station["code"] != origin_code
                    or normalized_station["name"] != origin_name
                ):
                    normalized["origin_station_code"] = normalized_station["code"]
                    normalized["origin_station_name"] = normalized_station["name"]
                    logger.debug(
                        f"Normalized origin station: {origin_code}/{origin_name} -> {normalized_station['code']}/{normalized_station['name']}"
                    )

            # Normalize stops
            if "stops" in normalized and normalized["stops"]:
                normalized_stops = []
                for i, stop in enumerate(normalized["stops"]):
                    normalized_stop = stop.copy()

                    # Normalize station code and name
                    stop_code = stop.get("station_code")
                    stop_name = stop.get("station_name")
                    if stop_code or stop_name:
                        normalized_station = station_mapper.normalize_amtrak_station(
                            stop_code, stop_name
                        )
                        normalized_stop["station_code"] = normalized_station["code"]
                        normalized_stop["station_name"] = normalized_station["name"]

                    # Normalize times
                    # Preserve original time precision in stop data
                    # Fuzzy matching handles time differences during consolidation

                    normalized_stops.append(normalized_stop)

                normalized["stops"] = normalized_stops

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing Amtrak train data: {str(e)}")
            # Return original data if normalization fails
            return train_record
