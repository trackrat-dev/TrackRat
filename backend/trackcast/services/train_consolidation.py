"""
Train consolidation service for merging duplicate train records from multiple sources.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from trackcast.db.models import Train, TrainStop
from trackcast.exceptions import TrackCastError

logger = logging.getLogger(__name__)


class TrainConsolidationService:
    """Service for consolidating train records from multiple sources."""

    def __init__(self):
        """Initialize the consolidation service."""
        self.time_tolerance = timedelta(minutes=5)  # For matching stop times

    def consolidate_trains(self, trains: List[Train], from_station_code: str = None) -> List[Dict]:
        """
        Consolidate multiple train records into unified journey representations.

        Args:
            trains: List of Train objects to consolidate
            from_station_code: Optional station code for user context

        Returns:
            List of consolidated train dictionaries
        """
        if not trains:
            return []

        # Group trains by potential journeys
        journey_groups = self._group_trains_by_journey(trains)

        # Consolidate each journey group
        consolidated_trains = []
        for journey_id, train_group in journey_groups.items():
            consolidated = self._consolidate_journey_group(train_group, from_station_code)
            consolidated_trains.append(consolidated)

        return consolidated_trains

    def _group_trains_by_journey(self, trains: List[Train]) -> Dict[str, List[Train]]:
        """
        Group trains that represent the same physical journey.

        Returns:
            Dictionary mapping journey IDs to lists of related trains
        """
        logger.debug(f"Grouping {len(trains)} trains by journey")
        journey_groups = defaultdict(list)
        processed = set()

        for i, train1 in enumerate(trains):
            if i in processed:
                continue

            # Start a new journey group with this train
            journey_trains = [train1]
            processed.add(i)
            logger.debug(
                f"Starting new journey group with train {train1.train_id} from {train1.origin_station_code}"
            )

            # Find all other trains that match this journey
            for j, train2 in enumerate(trains):
                if j <= i or j in processed:
                    continue

                logger.debug(
                    f"Testing if train {train1.train_id} ({train1.origin_station_code}) matches {train2.train_id} ({train2.origin_station_code})"
                )
                if self._trains_match(train1, train2):
                    logger.debug(
                        f"✓ Trains match: {train1.train_id} ({train1.origin_station_code}) + {train2.train_id} ({train2.origin_station_code})"
                    )
                    journey_trains.append(train2)
                    processed.add(j)
                else:
                    logger.debug(
                        f"✗ Trains don't match: {train1.train_id} ({train1.origin_station_code}) vs {train2.train_id} ({train2.origin_station_code})"
                    )

            # Generate journey ID and store group
            journey_id = self._get_journey_id(journey_trains)
            journey_groups[journey_id] = journey_trains
            logger.debug(f"Created journey group '{journey_id}' with {len(journey_trains)} trains")

        return dict(journey_groups)

    def _trains_match(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains represent the same physical journey.

        Args:
            train1: First train to compare
            train2: Second train to compare

        Returns:
            True if trains are the same journey, False otherwise
        """
        # Primary match: Same train ID
        if train1.train_id != train2.train_id:
            logger.debug(f"Train IDs don't match: {train1.train_id} vs {train2.train_id}")
            return False

        logger.debug(f"Train IDs match: {train1.train_id}")

        # Check if trains share the same journey by comparing stop times
        if not self._same_journey(train1, train2):
            logger.debug(f"Journeys don't match for {train1.train_id}")
            return False

        logger.debug(f"Journeys match for {train1.train_id}")

        # Route validation: Check if they share the same route pattern
        # For trains with very strong journey matching (≥80% stations match),
        # we can be more lenient about route ordering differences
        if not self._same_route_pattern(train1, train2):
            # Calculate journey match strength
            if not hasattr(train1, "stops") or not hasattr(train2, "stops"):
                logger.debug(f"Route patterns don't match for {train1.train_id} (no stops data)")
                return False

            # Get common stations count from journey matching
            from trackcast.services.station_mapping import StationMapper

            station_mapper = StationMapper()

            train1_schedule = {}
            train2_schedule = {}

            for stop in train1.stops:
                if stop.station_code and stop.scheduled_time:
                    normalized = station_mapper.normalize_amtrak_station(
                        stop.station_code, stop.station_name
                    )
                    station_code = normalized["code"] if normalized["code"] else stop.station_code
                    train1_schedule[station_code] = stop.scheduled_time

            for stop in train2.stops:
                if stop.station_code and stop.scheduled_time:
                    normalized = station_mapper.normalize_amtrak_station(
                        stop.station_code, stop.station_name
                    )
                    station_code = normalized["code"] if normalized["code"] else stop.station_code
                    train2_schedule[station_code] = stop.scheduled_time

            common_stations = set(train1_schedule.keys()) & set(train2_schedule.keys())

            # Use the same matching logic as _same_journey: count how many common stations have matching times
            matching_stations = 0
            for station in common_stations:
                time1 = train1_schedule[station]
                time2 = train2_schedule[station]
                time_diff = abs(time1 - time2)

                if time_diff <= self.time_tolerance:
                    matching_stations += 1

            # Use the same threshold as _same_journey: at least 50% of common stations must match
            min_required_matches = max(2, len(common_stations) // 2)
            journey_match_strength = (
                matching_stations / len(common_stations) if common_stations else 0
            )

            if (
                matching_stations >= min_required_matches and journey_match_strength >= 0.8
            ):  # 80% or more common stations match
                logger.info(
                    f"Route patterns don't match for {train1.train_id}, but journey match strength is {journey_match_strength:.1%} ({matching_stations}/{len(common_stations)} common stations) - allowing consolidation"
                )
                return True
            else:
                logger.info(
                    f"Route patterns don't match for {train1.train_id}, journey match strength only {journey_match_strength:.1%} ({matching_stations}/{len(common_stations)} common stations) - rejecting"
                )
                return False

        logger.debug(f"Route patterns match for {train1.train_id}")
        return True

    def _same_journey(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains are part of the same journey by comparing their stops.
        Since departure_time is relative to origin_station_code, we need to find
        a common reference point in their stop schedules.
        """
        # Check if stops are loaded
        if not hasattr(train1, "stops") or not hasattr(train2, "stops"):
            logger.warning(f"Trains {train1.train_id} and {train2.train_id} missing stop data")
            return False

        if not train1.stops or not train2.stops:
            return False

        # Build station-to-time mappings for both trains (only include stops with scheduled times)
        # Apply normalization to handle Amtrak station codes
        from trackcast.services.station_mapping import StationMapper

        station_mapper = StationMapper()

        train1_schedule = {}
        train2_schedule = {}

        for stop in train1.stops:
            if stop.station_code and stop.scheduled_time:
                # Normalize station code in case it's from Amtrak
                normalized = station_mapper.normalize_amtrak_station(
                    stop.station_code, stop.station_name
                )
                station_code = normalized["code"] if normalized["code"] else stop.station_code
                if stop.station_code != station_code:
                    logger.debug(
                        f"Normalized station {stop.station_code} -> {station_code} for train1"
                    )
                train1_schedule[station_code] = stop.scheduled_time

        for stop in train2.stops:
            if stop.station_code and stop.scheduled_time:
                # Normalize station code in case it's from Amtrak
                normalized = station_mapper.normalize_amtrak_station(
                    stop.station_code, stop.station_name
                )
                station_code = normalized["code"] if normalized["code"] else stop.station_code
                if stop.station_code != station_code:
                    logger.debug(
                        f"Normalized station {stop.station_code} -> {station_code} for train2"
                    )
                train2_schedule[station_code] = stop.scheduled_time

        # Find common stations
        common_stations = set(train1_schedule.keys()) & set(train2_schedule.keys())

        if len(common_stations) < 2:
            logger.debug(
                f"Trains {train1.train_id} and {train2.train_id} have fewer than 2 common stations"
            )
            return False

        # Count stations with matching times (within tolerance)
        matching_stations = 0
        for station in common_stations:
            time1 = train1_schedule[station]
            time2 = train2_schedule[station]
            time_diff = abs(time1 - time2)

            if time_diff <= self.time_tolerance:
                matching_stations += 1
                logger.debug(f"Station {station} matches: {time1} vs {time2} (diff: {time_diff})")
            else:
                logger.debug(
                    f"Station {station} time mismatch: {time1} vs {time2} (diff: {time_diff})"
                )

        # Require at least 2 matching stations AND at least 50% of common stations to match
        min_required_matches = max(2, len(common_stations) // 2)

        logger.debug(
            f"Journey comparison for {train1.train_id}: {matching_stations}/{len(common_stations)} stations match (need {min_required_matches})"
        )

        return matching_stations >= min_required_matches

    def _same_route_pattern(self, train1: Train, train2: Train) -> bool:
        """
        Check if two trains follow the same route pattern.

        Args:
            train1: First train to compare
            train2: Second train to compare

        Returns:
            True if routes match, False otherwise
        """
        if not hasattr(train1, "stops") or not hasattr(train2, "stops"):
            return False

        # Apply station normalization for Amtrak codes (same as in _same_journey)
        from trackcast.services.station_mapping import StationMapper

        station_mapper = StationMapper()

        # Extract ordered station codes with normalization
        route1 = []
        for stop in train1.stops:
            if stop.station_code:
                normalized = station_mapper.normalize_amtrak_station(
                    stop.station_code, stop.station_name
                )
                station_code = normalized["code"] if normalized["code"] else stop.station_code
                route1.append(station_code)

        route2 = []
        for stop in train2.stops:
            if stop.station_code:
                normalized = station_mapper.normalize_amtrak_station(
                    stop.station_code, stop.station_name
                )
                station_code = normalized["code"] if normalized["code"] else stop.station_code
                route2.append(station_code)

        logger.debug(f"Route pattern comparison for {train1.train_id} vs {train2.train_id}:")
        logger.debug(f"  Route1 ({train1.origin_station_code}): {route1}")
        logger.debug(f"  Route2 ({train2.origin_station_code}): {route2}")

        # Find common stations and check order
        common_stations = []
        for station in route1:
            if station in route2:
                common_stations.append(station)

        logger.debug(f"  Common stations: {common_stations} (need at least 2)")

        # Need at least 2 common stations
        if len(common_stations) < 2:
            logger.debug(
                f"  Route pattern check failed: only {len(common_stations)} common stations"
            )
            return False

        # Check if common stations appear in the same order in both routes
        idx1 = 0
        idx2 = 0
        for station in common_stations:
            # Find station in route1
            while idx1 < len(route1) and route1[idx1] != station:
                idx1 += 1
            # Find station in route2
            while idx2 < len(route2) and route2[idx2] != station:
                idx2 += 1

            if idx1 >= len(route1) or idx2 >= len(route2):
                logger.debug(f"  Route pattern check failed: station {station} ordering issue")
                return False

        logger.debug(f"  Route pattern check passed: {len(common_stations)} stations in same order")
        return True

    def _get_journey_id(self, trains: List[Train]) -> str:
        """
        Generate a unique journey identifier based on train_id and the earliest stop time.
        This helps group trains from different origins into the same journey.
        """
        if not trains:
            raise ValueError("Cannot generate journey ID for empty train list")

        train_id = trains[0].train_id

        # Find the earliest scheduled stop across all trains
        earliest_time = None
        for train in trains:
            if hasattr(train, "stops") and train.stops:
                for stop in train.stops:
                    if stop.scheduled_time:
                        if earliest_time is None or stop.scheduled_time < earliest_time:
                            earliest_time = stop.scheduled_time

        # If no stops found, use the earliest departure time
        if earliest_time is None:
            earliest_time = min(train.departure_time for train in trains)

        journey_date = earliest_time.date()
        return f"{train_id}_{journey_date.isoformat()}"

    def _consolidate_journey_group(
        self, trains: List[Train], from_station_code: str = None
    ) -> Dict:
        """
        Consolidate a group of trains representing the same journey.

        Args:
            trains: List of trains on the same journey
            from_station_code: Optional station code for user context

        Returns:
            Consolidated train dictionary
        """
        if not trains:
            raise ValueError("Cannot consolidate empty train list")

        # Sort trains by their origin departure time
        trains.sort(key=lambda t: t.departure_time)

        # Use the earliest train as the base
        base_train = trains[0]

        # Merge data from all sources
        consolidated = {
            "train_id": base_train.train_id,
            "consolidated_id": self._get_journey_id(trains),
            "origin_station": {
                "code": base_train.origin_station_code,
                "name": base_train.origin_station_name,
                "departure_time": base_train.departure_time.isoformat(),
            },
            "destination": base_train.destination,
            "line": base_train.line,
            "line_code": base_train.line_code,
            # Data sources information
            "data_sources": self._build_data_sources(trains),
            # Merged fields using priority rules
            "track_assignment": self._merge_track_assignment(trains),
            "status_summary": self._merge_status(trains, from_station_code),
            # Merged stops with departure status from all sources (must come first)
            "stops": self._merge_stops(trains),
        }

        # Add position tracking using the merged stops
        consolidated["current_position"] = self._calculate_current_position_from_stops(
            consolidated["stops"]
        )

        # Add metadata
        consolidated["consolidation_metadata"] = {
            "source_count": len(trains),
            "last_update": max(t.updated_at for t in trains).isoformat(),
            "confidence_score": self._calculate_confidence_score(trains),
        }

        # Add prediction data if available
        prediction_data = self._get_best_prediction(trains)
        if prediction_data:
            consolidated["prediction_data"] = prediction_data

        # Add new enhanced status and progress fields
        consolidated["status_v2"] = self._compute_status_v2(trains, consolidated)
        consolidated["progress"] = self._compute_progress(trains, consolidated)

        return consolidated

    def _build_data_sources(self, trains: List[Train]) -> List[Dict]:
        """Build list of data sources contributing to this consolidated train."""
        sources = []
        for train in trains:
            source_info = {
                "origin": train.origin_station_code,
                "data_source": train.data_source,
                "last_update": train.updated_at.isoformat(),
                "status": train.status,
                "track": train.track,
                "delay_minutes": train.delay_minutes,
                "db_id": train.id,
            }
            sources.append(source_info)
        return sources

    def _merge_track_assignment(self, trains: List[Train]) -> Dict:
        """
        Merge track assignment data using priority rules.
        Priority: True origin station > Most recent > NJ Transit > Amtrak

        The "true origin" is the station where the journey actually starts
        (earliest stop in the route), not just the first train in our list.
        """
        track_info = {"track": None, "assigned_at": None, "assigned_by": None, "source": None}

        # Find the true origin station (where the journey actually starts)
        true_origin = self._find_true_origin_station(trains)

        # Priority 1: Check if true origin station has a track assignment
        true_origin_train = None
        for train in trains:
            if train.origin_station_code == true_origin:
                true_origin_train = train
                break

        # If true origin exists and has a track (even empty), use it and stop
        if true_origin_train is not None:
            if true_origin_train.track and true_origin_train.track.strip():
                track_info["track"] = true_origin_train.track
                track_info["assigned_at"] = (
                    true_origin_train.track_assigned_at.isoformat()
                    if true_origin_train.track_assigned_at
                    else None
                )
                track_info["assigned_by"] = true_origin_train.origin_station_code
                track_info["source"] = true_origin_train.data_source
            # If true origin exists but has no track, leave track_info empty (don't fallback)
            return track_info

        # Priority 2: If no track from true origin, use most recent assignment
        if not track_info["track"]:
            candidate_trains = [t for t in trains if t.track and t.track.strip()]
            if candidate_trains:
                # Sort by track assignment time (most recent first)
                recent_train = max(
                    candidate_trains,
                    key=lambda t: t.track_assigned_at if t.track_assigned_at else t.updated_at,
                )
                track_info["track"] = recent_train.track
                track_info["assigned_at"] = (
                    recent_train.track_assigned_at.isoformat()
                    if recent_train.track_assigned_at
                    else None
                )
                track_info["assigned_by"] = recent_train.origin_station_code
                track_info["source"] = recent_train.data_source

        return track_info

    def _find_true_origin_station(self, trains: List[Train]) -> Optional[str]:
        """
        Find the true origin station where the journey actually starts.
        This is the station with the earliest scheduled stop time across all trains.
        """
        earliest_station = None
        earliest_time = None

        for train in trains:
            if hasattr(train, "stops") and train.stops:
                for stop in train.stops:
                    if stop.scheduled_time:
                        if earliest_time is None or stop.scheduled_time < earliest_time:
                            earliest_time = stop.scheduled_time
                            earliest_station = stop.station_code

        return earliest_station

    def _merge_status(self, trains: List[Train], from_station_code: str = None) -> Dict:
        """
        Merge status information from all sources.
        Priority: Most recent update > Most progressed > Amtrak > NJ Transit
        """
        # Get the most recent status
        latest_train = max(trains, key=lambda t: t.updated_at)

        # Calculate maximum delay (conservative approach)
        max_delay = 0
        for train in trains:
            if train.delay_minutes is not None and train.delay_minutes > max_delay:
                max_delay = train.delay_minutes

        # Determine current status
        current_status = latest_train.status
        if any(t.status == "DEPARTED" for t in trains):
            current_status = "In Transit"
        elif any(t.status == "BOARDING" for t in trains):
            # If user specified a boarding station, only show "Boarding" if it's boarding at that station
            if from_station_code:
                user_station_boarding = any(
                    t.status == "BOARDING" and t.origin_station_code == from_station_code
                    for t in trains
                )
                if user_station_boarding:
                    # Only show "Boarding" if there's also a track assignment (for this station)
                    user_station_has_track = any(
                        t.status == "BOARDING"
                        and t.origin_station_code == from_station_code
                        and t.track
                        and t.track.strip()
                        for t in trains
                    )
                    if user_station_has_track:
                        current_status = "Boarding"
                    # If boarding at user's station but no track yet, keep latest status
                else:
                    # Train is boarding somewhere else, not at user's station
                    # Don't show "BOARDING" status - use a more appropriate status
                    current_status = (
                        "Scheduled"  # or "En Route" - train is not boarding for this user
                    )
            else:
                # No user context - show "Boarding" if any train is boarding with track assignment
                if any(t.status == "BOARDING" and t.track and t.track.strip() for t in trains):
                    current_status = "Boarding"

        return {
            "current_status": current_status,
            "delay_minutes": max_delay,
            "on_time_performance": "Delayed" if max_delay > 5 else "On Time",
        }

    def _calculate_current_position(self, trains: List[Train]) -> Optional[Dict]:
        """Calculate the train's current position based on departed flags."""
        # Collect all stops with their departed status
        all_stops = []
        for train in trains:
            if hasattr(train, "stops") and train.stops:
                all_stops.extend(train.stops)

        if not all_stops:
            return None

        # Build consolidated stop status
        stop_status = {}
        for stop in all_stops:
            # Skip stops with missing station codes
            if not stop.station_code:
                continue

            if stop.station_code not in stop_status:
                stop_status[stop.station_code] = {
                    "station_name": stop.station_name,
                    "scheduled_time": stop.scheduled_time,
                    "departed": False,
                }
            # If any source says departed, mark as departed
            if stop.departed:
                stop_status[stop.station_code]["departed"] = True

        # Find last departed and next station
        if not stop_status:
            return None

        # Use a very early datetime for None values to sort them first
        min_datetime = datetime(1900, 1, 1)
        sorted_stops = sorted(
            stop_status.items(), key=lambda x: x[1]["scheduled_time"] or min_datetime
        )
        last_departed = None
        next_station = None

        for i, (code, info) in enumerate(sorted_stops):
            if info["departed"]:
                last_departed = (code, info)
            elif last_departed and not next_station:
                next_station = (code, info)
                break

        if not last_departed:
            # Train hasn't departed yet
            return {
                "status": "Not yet departed",
                "next_station": (
                    {
                        "code": sorted_stops[0][0],
                        "name": sorted_stops[0][1]["station_name"],
                        "scheduled_arrival": (
                            sorted_stops[0][1]["scheduled_time"].isoformat()
                            if sorted_stops[0][1]["scheduled_time"]
                            else None
                        ),
                    }
                    if sorted_stops
                    else None
                ),
            }

        position = {
            "last_departed_station": {
                "code": last_departed[0],
                "name": last_departed[1]["station_name"],
                "scheduled_departure": (
                    last_departed[1]["scheduled_time"].isoformat()
                    if last_departed[1]["scheduled_time"]
                    else None
                ),
            }
        }

        if next_station:
            position["next_station"] = {
                "code": next_station[0],
                "name": next_station[1]["station_name"],
                "scheduled_arrival": (
                    next_station[1]["scheduled_time"].isoformat()
                    if next_station[1]["scheduled_time"]
                    else None
                ),
            }
            # Could calculate segment progress here if we had real-time position data

        return position

    def _calculate_current_position_from_stops(self, merged_stops: List[Dict]) -> Optional[Dict]:
        """
        Calculate the train's current position from already-merged stop data.

        Args:
            merged_stops: List of stop dictionaries from _merge_stops()

        Returns:
            Current position dictionary or None
        """
        if not merged_stops:
            return None

        # Find last departed and next station from merged stops
        last_departed = None
        next_station = None

        for i, stop in enumerate(merged_stops):
            if stop.get("departed"):
                last_departed = stop
            elif last_departed and not next_station:
                next_station = stop
                break

        if not last_departed:
            # Train hasn't departed yet
            return {
                "status": "Not yet departed",
                "next_station": (
                    {
                        "code": merged_stops[0]["station_code"],
                        "name": merged_stops[0]["station_name"],
                        "scheduled_arrival": merged_stops[0]["scheduled_time"],
                    }
                    if merged_stops
                    else None
                ),
            }

        position = {
            "last_departed_station": {
                "code": last_departed["station_code"],
                "name": last_departed["station_name"],
                "scheduled_departure": last_departed["scheduled_time"],
            }
        }

        if next_station:
            position["next_station"] = {
                "code": next_station["station_code"],
                "name": next_station["station_name"],
                "scheduled_arrival": next_station["scheduled_time"],
            }

        return position

    def _merge_stops(self, trains: List[Train]) -> List[Dict]:
        """
        Merge stop information from all sources using 'most recently updated train wins' logic.

        When trains have conflicting departure status for the same station, the train with
        the most recent updated_at timestamp takes precedence.
        """
        # Collect all stops with their source train metadata
        stop_map = {}

        for train in trains:
            if not hasattr(train, "stops") or not train.stops:
                continue

            for stop in train.stops:
                # Skip stops with missing station codes
                if not stop.station_code:
                    continue

                key = stop.station_code
                if key not in stop_map:
                    stop_map[key] = {
                        "station_code": stop.station_code,
                        "station_name": stop.station_name,
                        "scheduled_time": (
                            stop.scheduled_time.isoformat() if stop.scheduled_time else None
                        ),
                        "departure_time": (
                            stop.departure_time.isoformat() if stop.departure_time else None
                        ),
                        "pickup_only": stop.pickup_only,
                        "dropoff_only": stop.dropoff_only,
                        "departed": stop.departed,
                        "departed_confirmed_by": [],
                        "stop_status": stop.stop_status,
                        # Track which train/timestamp determined the departed status
                        "_departed_source_train": train if stop.departed else None,
                        "_departed_source_timestamp": train.updated_at if stop.departed else None,
                    }
                    # Add to confirmed_by if this source says departed
                    if stop.departed:
                        stop_map[key]["departed_confirmed_by"].append(train.origin_station_code)
                else:
                    # Station already exists - resolve conflicts using most recent train wins
                    existing_departed = stop_map[key]["departed"]
                    current_departed = stop.departed

                    # Always add this source to confirmed_by if it says departed
                    if current_departed:
                        if train.origin_station_code not in stop_map[key]["departed_confirmed_by"]:
                            stop_map[key]["departed_confirmed_by"].append(train.origin_station_code)

                    # If there's a conflict about departure status, use most recent train
                    if existing_departed != current_departed:
                        existing_timestamp = stop_map[key]["_departed_source_timestamp"]
                        current_timestamp = train.updated_at

                        # If current train is more recent, use its departure status
                        if existing_timestamp is None or current_timestamp > existing_timestamp:
                            logger.debug(
                                f"Station {key}: Using more recent departure status from {train.origin_station_code} "
                                f"({current_departed}) over previous status ({existing_departed})"
                            )
                            stop_map[key]["departed"] = current_departed
                            stop_map[key]["_departed_source_train"] = train
                            stop_map[key]["_departed_source_timestamp"] = current_timestamp
                        else:
                            logger.debug(
                                f"Station {key}: Keeping existing departure status ({existing_departed}) "
                                f"from more recent source over {train.origin_station_code} ({current_departed})"
                            )

                    # Update actual times if available (take first non-None value)
                    if stop.departure_time and not stop_map[key]["departure_time"]:
                        stop_map[key]["departure_time"] = stop.departure_time.isoformat()

        # Clean up internal tracking fields before returning
        for stop_data in stop_map.values():
            stop_data.pop("_departed_source_train", None)
            stop_data.pop("_departed_source_timestamp", None)

        # Sort stops by scheduled time
        # Use datetime.min for None values to ensure proper sorting
        sorted_stops = sorted(
            stop_map.values(),
            key=lambda s: (
                datetime.fromisoformat(s["scheduled_time"]) if s["scheduled_time"] else datetime.min
            ),
        )
        return sorted_stops

    def _get_best_prediction(self, trains: List[Train]) -> Optional[Dict]:
        """Get the best prediction data from available sources."""
        # Find trains with predictions
        trains_with_predictions = [t for t in trains if t.prediction_data]

        if not trains_with_predictions:
            return None

        # Use prediction from origin station if available
        for train in trains_with_predictions:
            if train.origin_station_code == trains[0].origin_station_code:
                return self._serialize_prediction(train.prediction_data)

        # Otherwise use most recent prediction
        latest = max(trains_with_predictions, key=lambda t: t.updated_at)
        return self._serialize_prediction(latest.prediction_data)

    def _serialize_prediction(self, prediction_data) -> Dict:
        """Serialize prediction data object to dictionary."""
        if not prediction_data:
            return None

        return {
            "track_probabilities": prediction_data.track_probabilities,
            "prediction_factors": prediction_data.prediction_factors,
            "model_version": prediction_data.model_version,
            "created_at": prediction_data.created_at.isoformat(),
        }

    def _calculate_confidence_score(self, trains: List[Train]) -> float:
        """
        Calculate confidence score for the consolidation.
        Higher score means more confident in the consolidation accuracy.
        """
        score = 1.0

        # More sources = higher confidence
        score = min(1.0, 0.5 + (len(trains) * 0.1))

        # Consistent data = higher confidence
        statuses = set(t.status for t in trains if t.status)
        if len(statuses) > 1:
            score *= 0.9  # Small penalty for inconsistent statuses

        tracks = set(t.track for t in trains if t.track)
        if len(tracks) > 1:
            score *= 0.8  # Larger penalty for inconsistent tracks

        return round(score, 2)

    def _compute_status_v2(self, trains: List[Train], consolidated: Dict) -> Dict:
        """
        Compute the enhanced unified status based on all data sources.

        Args:
            trains: List of trains being consolidated
            consolidated: The consolidated train data so far

        Returns:
            StatusV2 dictionary with enhanced status information
        """
        # Determine the most reliable current status
        status = "UNKNOWN"
        location = "Unknown location"
        source = "unknown"

        # Check for DEPARTED status first (highest priority)
        departed_trains = [t for t in trains if t.status == "DEPARTED"]
        if departed_trains:
            # Find which station we departed from
            latest_departed = max(departed_trains, key=lambda t: t.updated_at)
            source = f"{latest_departed.origin_station_code}_{latest_departed.data_source}"

            # Use current_position to determine location
            if consolidated.get("current_position"):
                pos = consolidated["current_position"]
                if pos.get("next_station"):
                    status = "EN_ROUTE"
                    location = f"between {pos.get('last_departed_station', {}).get('name', 'Unknown')} and {pos['next_station']['name']}"
                else:
                    # No next station means we're at the final destination
                    status = "ARRIVED"
                    location = f"at {consolidated['destination']}"
            else:
                status = "EN_ROUTE"
                location = f"departed from {latest_departed.origin_station_name}"

        # Check for BOARDING status (only if not departed)
        elif any(t.status == "BOARDING" and t.track for t in trains):
            boarding_trains = [t for t in trains if t.status == "BOARDING" and t.track]
            latest_boarding = max(boarding_trains, key=lambda t: t.updated_at)
            status = "BOARDING"
            location = f"at {latest_boarding.origin_station_name}"
            source = f"{latest_boarding.origin_station_code}_{latest_boarding.data_source}"

        # Check for ALL ABOARD status
        elif any(t.status == "ALL ABOARD" for t in trains):
            all_aboard_trains = [t for t in trains if t.status == "ALL ABOARD"]
            latest = max(all_aboard_trains, key=lambda t: t.updated_at)
            status = "ALL ABOARD"
            location = f"at {latest.origin_station_name}"
            source = f"{latest.origin_station_code}_{latest.data_source}"

        # Check for DELAYED status
        elif any(t.status == "DELAYED" for t in trains):
            delayed_trains = [t for t in trains if t.status == "DELAYED"]
            latest = max(delayed_trains, key=lambda t: t.updated_at)
            status = "DELAYED"
            location = f"at {latest.origin_station_name}"
            source = f"{latest.origin_station_code}_{latest.data_source}"

        # Check for CANCELLED status
        elif any(t.status == "CANCELLED" for t in trains):
            cancelled_trains = [t for t in trains if t.status == "CANCELLED"]
            latest = max(cancelled_trains, key=lambda t: t.updated_at)
            status = "CANCELLED"
            location = f"at {latest.origin_station_name}"
            source = f"{latest.origin_station_code}_{latest.data_source}"

        # Default case - train is scheduled but not yet boarding
        else:
            # Use the train with the most recent update
            latest_train = max(trains, key=lambda t: t.updated_at)
            status = "SCHEDULED"
            location = f"scheduled from {latest_train.origin_station_name}"
            source = f"{latest_train.origin_station_code}_{latest_train.data_source}"

        # Calculate confidence based on data consistency
        confidence = "high"
        statuses = set(t.status for t in trains if t.status)
        if len(statuses) > 1:
            # If we have conflicting statuses, reduce confidence
            if "DEPARTED" in statuses and "BOARDING" in statuses:
                # Common case where NJ Transit says BOARDING but train has actually departed
                confidence = "medium"
            elif len(statuses) > 2:
                confidence = "low"

        # Determine update time
        updated_at = max(t.updated_at for t in trains).isoformat()

        return {
            "current": status,
            "location": location,
            "updated_at": updated_at,
            "confidence": confidence,
            "source": source,
        }

    def _compute_progress(self, trains: List[Train], consolidated: Dict) -> Dict:
        """
        Compute journey progress tracking information.

        Args:
            trains: List of trains being consolidated
            consolidated: The consolidated train data so far

        Returns:
            Progress dictionary with journey tracking information
        """
        progress = {
            "last_departed": None,
            "next_arrival": None,
            "journey_percent": 0,
            "stops_completed": 0,
            "total_stops": 0,
        }

        # Get all stops from consolidated data
        stops = consolidated.get("stops", [])
        if not stops:
            return progress

        progress["total_stops"] = len(stops)

        # Count completed stops and find last departed/next arrival
        now = datetime.now()
        last_departed_stop = None
        next_arrival_stop = None

        for i, stop in enumerate(stops):
            if stop.get("departed"):
                progress["stops_completed"] += 1
                last_departed_stop = (i, stop)
            elif last_departed_stop and not next_arrival_stop:
                next_arrival_stop = (i, stop)

        # Set last departed station info
        if last_departed_stop:
            idx, stop = last_departed_stop
            # Find actual departure time and delay
            departure_time = None
            delay_minutes = 0

            if stop.get("departure_time"):
                departure_time = stop["departure_time"]
            elif stop.get("scheduled_time"):
                departure_time = stop["scheduled_time"]

            # Calculate delay if we have both scheduled and actual times
            if stop.get("departure_time") and stop.get("scheduled_time"):
                scheduled = datetime.fromisoformat(stop["scheduled_time"])
                actual = datetime.fromisoformat(stop["departure_time"])
                delay_minutes = int((actual - scheduled).total_seconds() / 60)

            progress["last_departed"] = {
                "station_code": stop["station_code"],
                "departed_at": departure_time,
                "delay_minutes": delay_minutes,
            }

        # Set next arrival info
        if next_arrival_stop:
            idx, stop = next_arrival_stop
            scheduled_time = stop.get("scheduled_time")

            # Estimate arrival time based on delay pattern
            estimated_time = scheduled_time
            if (
                scheduled_time
                and progress["last_departed"]
                and progress["last_departed"]["delay_minutes"] > 0
            ):
                # Apply the delay to the scheduled time
                scheduled_dt = datetime.fromisoformat(scheduled_time)
                estimated_dt = scheduled_dt + timedelta(
                    minutes=progress["last_departed"]["delay_minutes"]
                )
                estimated_time = estimated_dt.isoformat()

            # Calculate minutes to arrival
            minutes_away = 0
            if estimated_time:
                try:
                    estimated_dt = datetime.fromisoformat(estimated_time)
                    minutes_away = max(0, int((estimated_dt - now).total_seconds() / 60))
                except (ValueError, TypeError):
                    pass

            progress["next_arrival"] = {
                "station_code": stop["station_code"],
                "scheduled_time": scheduled_time or "",
                "estimated_time": estimated_time or scheduled_time or "",
                "minutes_away": minutes_away,
            }

        # Calculate journey completion percentage
        if progress["total_stops"] > 0:
            progress["journey_percent"] = int(
                (progress["stops_completed"] / progress["total_stops"]) * 100
            )

        return progress
