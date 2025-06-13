import abc
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class FeatureExtractor(abc.ABC):
    """Base abstract class for feature extractors."""

    @property
    def feature_names(self) -> List[str]:
        """Get the names of features this extractor produces."""
        return []

    @abc.abstractmethod
    def extract(self, *args, **kwargs) -> Dict[str, Any]:
        """Extract features from the provided data."""
        pass


class TimeFeatureExtractor(FeatureExtractor):
    """Extract time-based features from train data"""

    def extract(self, train, reference_time=None) -> Dict[str, Any]:
        """Extract time features from train data"""
        # Convert Train object to dictionary if needed
        train_data = train.__dict__ if hasattr(train, "__dict__") else train
        departure_time = train_data["departure_time"]
        if isinstance(departure_time, str):
            departure_time = datetime.fromisoformat(departure_time.replace(" ", "T"))

        # Hour features (cyclical encoding)
        hour = departure_time.hour + departure_time.minute / 60
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)

        # Day of week features (cyclical encoding)
        # Assuming Monday is 0 and Sunday is 6
        day_of_week = departure_time.weekday()
        day_of_week_sin = np.sin(2 * np.pi * day_of_week / 7)
        day_of_week_cos = np.cos(2 * np.pi * day_of_week / 7)

        # Weekend indicator
        is_weekend = 1 if day_of_week >= 5 else 0

        # Rush hour indicators
        is_morning_rush = 1 if (not is_weekend and 6 <= hour < 10) else 0

        is_evening_rush = 1 if (not is_weekend and 16 <= hour < 20) else 0

        return {
            "hour_sin": float(hour_sin),
            "hour_cos": float(hour_cos),
            "day_of_week_sin": float(day_of_week_sin),
            "day_of_week_cos": float(day_of_week_cos),
            "is_weekend": bool(is_weekend),
            "is_morning_rush": bool(is_morning_rush),
            "is_evening_rush": bool(is_evening_rush),
        }


class CategoricalFeatureExtractor(FeatureExtractor):
    """Extract categorical features from train data"""

    def __init__(
        self, all_lines: Optional[List[str]] = None, all_destinations: Optional[List[str]] = None
    ):
        """Initialize with known categorical values"""
        self.all_lines = all_lines or []
        self.all_destinations = all_destinations or []

    def extract(self, train, reference_time=None) -> Dict[str, Dict[str, int]]:
        """Extract categorical features from train data"""
        # Convert Train object to dictionary if needed
        train_data = train.__dict__ if hasattr(train, "__dict__") else train

        # Ensure we get string values for line and destination
        if isinstance(train_data, dict):
            line = str(train_data.get("line", ""))
            destination = str(train_data.get("destination", ""))
        else:
            # If train is an ORM object, access attributes directly
            line = str(getattr(train, "line", ""))
            destination = str(getattr(train, "destination", ""))

        # One-hot encode lines
        line_features = {}
        for line_name in self.all_lines:
            safe_name = str(line_name).replace(" ", "_")
            line_features[f"Line_{safe_name}"] = 1 if str(line_name) == line else 0

        # One-hot encode destinations
        destination_features = {}
        for d in self.all_destinations:
            safe_name = str(d).replace(" ", "_")
            destination_features[f"Destination_{safe_name}"] = 1 if str(d) == destination else 0

        return {"line_features": line_features, "destination_features": destination_features}


class TrackUsageFeatureExtractor(FeatureExtractor):
    """Extract track usage features"""

    def __init__(self, session, max_lookback_hours: int = 24):
        self.session = session
        self.max_lookback_hours = max_lookback_hours
        self.historical_data = None
        self.track_usage_timeline = {}  # Track timeline of usage {track: [sorted departure_times]}
        self.all_tracks = [str(i) for i in range(1, 22)]  # Tracks 1-21

    def precompute_historical_data(self, reference_time=None):
        """Precompute historical track usage data for all tracks"""
        import logging
        from collections import defaultdict

        from trackcast.db.models import Train

        logger = logging.getLogger(__name__)

        try:
            logger.info("Precomputing track usage timeline")

            # Get all historical trains with track assignments
            query = self.session.query(Train).filter(Train.track != None)
            if reference_time:
                query = query.filter(Train.departure_time < reference_time)

            # Order by departure time for efficiency in later calculations
            historical_trains = query.order_by(Train.departure_time).all()

            logger.info(
                f"Retrieved {len(historical_trains)} historical trains with track assignments"
            )

            # Convert to dictionaries for easier processing
            self.historical_data = [
                {
                    "train_id": train.train_id,
                    "track": train.track,
                    "departure_time": train.departure_time,
                    "line": train.line,
                    "destination": train.destination,
                    "origin_station_code": train.origin_station_code,
                    "internal_id": train.id,  # Include database primary key
                }
                for train in historical_trains
            ]

            # Build track usage timeline (sorted list of train entries for each track)
            self.track_usage_timeline = defaultdict(list)
            for train in self.historical_data:
                track = train["track"]
                if track:
                    # Store complete train metadata instead of just timestamp
                    train_entry = {
                        "time": train["departure_time"],
                        "train_id": train["train_id"],
                        "origin": train.get("origin_station_code", "NY"),
                        "internal_id": train.get("internal_id"),
                        "line": train.get("line"),
                        "destination": train.get("destination"),
                    }
                    self.track_usage_timeline[track].append(train_entry)

            # Ensure each timeline is sorted by departure time
            for track in self.track_usage_timeline:
                self.track_usage_timeline[track].sort(key=lambda x: x["time"])

            # Initialize any missing tracks with empty lists
            for track in self.all_tracks:
                if track not in self.track_usage_timeline:
                    self.track_usage_timeline[track] = []

            logger.info("Track usage timeline precomputation completed")

        except Exception as e:
            logger.error(f"Error precomputing track usage data: {str(e)}")
            # Initialize with empty data
            self.historical_data = []
            self.track_usage_timeline = {track: [] for track in self.all_tracks}

    def _is_same_train(self, timeline_entry: Dict, target_train) -> bool:
        """
        Determine if a timeline entry represents the same train as the target train.
        Uses multiple identifiers to ensure robust matching and prevent self-conflicts.
        """
        return (
            timeline_entry["train_id"] == target_train.train_id
            and timeline_entry["time"] == target_train.departure_time
            and timeline_entry["origin"] == target_train.origin_station_code
            and timeline_entry["internal_id"] == target_train.id
        )

    def extract(self, train, reference_time=None) -> Dict[str, Any]:
        """Extract track usage features for a train"""
        import bisect
        import logging

        logger = logging.getLogger(__name__)

        # Use provided reference time or train's departure time
        if reference_time:
            train_time = reference_time
            logger.debug(f"Using reference_time: {train_time}")
        elif hasattr(train, "departure_time"):
            train_time = train.departure_time
            logger.debug(
                f"Using train.departure_time: {train_time} for train {getattr(train, 'id', 'unknown')}"
            )
        else:
            train_time = train.get("departure_time")
            logger.debug(
                f"Using train dict departure_time: {train_time} for train {train.get('id', 'unknown')}"
            )

        # Initialize result dictionary
        result = {}

        # If we don't have precomputed data, try to populate it
        # This is a fallback in case extract() is called without precomputation
        if self.historical_data is None:
            logger.warning(
                "No precomputed data available in TrackUsageFeatureExtractor. Precomputing now..."
            )
            self.precompute_historical_data(reference_time=train_time)

        # For each track, calculate:
        # 1. Minutes since last use
        # 2. Is currently occupied
        # 3. Utilization in last 24h
        for track in self.all_tracks:
            # Get track usage timeline (now contains train metadata, not just times)
            track_timeline = self.track_usage_timeline.get(track, [])

            # Extract times for binary search operations
            track_times = [entry["time"] for entry in track_timeline]

            # Find last usage before this train's departure time using binary search
            # Find index where we would insert train_time to maintain sorting
            index = bisect.bisect_left(track_times, train_time)

            # If index > 0, there's at least one usage before this train
            if index > 0 and track_times:
                last_used_time = track_times[index - 1]
                time_diff = (train_time - last_used_time).total_seconds() / 60
                # Cap at max lookback
                minutes_since_last_use = min(time_diff, self.max_lookback_hours * 60)
            else:
                # If never used in our data before this train, set to max
                minutes_since_last_use = self.max_lookback_hours * 60

            # Calculate if track is currently active (has trains boarding or about to depart)
            # Check for trains that are actively using this track at the time of this train's departure
            # Look for trains within a small window (2 minutes before to 2 minutes after)
            # to catch trains that are boarding or about to board
            active_window_before = pd.Timedelta(minutes=2)
            active_window_after = pd.Timedelta(minutes=2)

            # Find trains that would be actively using the track
            active_start_time = train_time - active_window_before
            active_end_time = train_time + active_window_after

            # Check each train in the timeline to see if it's in the active window
            # and exclude the target train using robust identification
            active_trains = []
            for train_entry in track_timeline:
                entry_time = train_entry["time"]
                # Check if this train is in the active window
                if active_start_time <= entry_time <= active_end_time:
                    # Use robust train identification to exclude the target train
                    if not self._is_same_train(train_entry, train):
                        active_trains.append(train_entry)

            is_occupied = 1 if active_trains else 0

            # Defensive validation: Check for self-conflicts (should never happen now)
            target_train_in_window = any(
                self._is_same_train(entry, train) for entry in active_trains
            )
            if target_train_in_window:
                logger.warning(
                    f"Self-conflict detected for train {train.train_id} on track {track} - "
                    f"this should not happen with the new exclusion logic!"
                )

            # Debug logging for the first few tracks to verify exclusion is working
            if track in ["1", "2", "3", "4"] and active_trains:
                train_id = getattr(train, "train_id", "unknown")
                conflicting_trains = [
                    f"{entry['train_id']}@{entry['time']}" for entry in active_trains
                ]
                logger.debug(
                    f"Train {train_id} Track_{track}: {len(active_trains)} conflicting trains: "
                    f"{', '.join(conflicting_trains)}"
                )

            # Calculate 24h utilization for this track
            day_ago = train_time - pd.Timedelta(hours=24)
            day_ago_index = bisect.bisect_left(track_times, day_ago)

            # Count trains in past 24h for this track
            track_day_count = index - day_ago_index if day_ago_index <= index else 0

            # Calculate total trains in past 24h across all tracks
            total_day_count = 0
            for t in self.all_tracks:
                track_timeline_t = self.track_usage_timeline.get(t, [])
                if track_timeline_t:
                    # Extract times for binary search
                    times_t = [entry["time"] for entry in track_timeline_t]
                    t_day_ago_index = bisect.bisect_left(times_t, day_ago)
                    t_now_index = bisect.bisect_left(times_t, train_time)
                    total_day_count += (
                        (t_now_index - t_day_ago_index) if t_day_ago_index <= t_now_index else 0
                    )

            # Calculate utilization percentage
            utilization_24h = track_day_count / total_day_count if total_day_count > 0 else 0.0

            # Store results with train ID tag for debugging
            result[f"Track_{track}_Last_Used"] = float(minutes_since_last_use)
            result[f"Is_Track_{track}_Occupied"] = bool(is_occupied)
            result[f"Track_{track}_Utilization_24h"] = float(utilization_24h)

            # Add debug log for first three tracks to verify they differ between trains
            if track in ["1", "2", "3"]:
                train_id = getattr(train, "train_id", getattr(train, "id", "unknown"))
                logger.debug(
                    f"Train {train_id} Track_{track}_Last_Used = {minutes_since_last_use:.2f} min at time {train_time}"
                )

        # Return with top-level key to match the expected field name in the model
        return {"track_usage_features": result}


class HistoricalTrackFeatureExtractor(FeatureExtractor):
    """Extract historical track usage patterns"""

    def __init__(self, session):
        self.session = session
        self.historical_data = None
        self.train_id_stats = {}
        self.line_stats = {}
        self.destination_stats = {}
        self.all_tracks = [str(i) for i in range(1, 22)]  # Tracks 1-21

    def precompute_historical_data(self, reference_time=None):
        """Precompute historical track usage patterns for quick lookup"""
        import logging
        from collections import defaultdict

        from trackcast.db.models import Train

        logger = logging.getLogger(__name__)

        try:
            logger.info("Precomputing historical track patterns")

            # Get all historical trains with track assignments
            query = self.session.query(Train).filter(Train.track != None)
            if reference_time:
                query = query.filter(Train.departure_time < reference_time)

            historical_trains = query.all()

            logger.info(
                f"Retrieved {len(historical_trains)} historical trains with track assignments for pattern analysis"
            )

            # Convert to dictionaries for easier processing
            self.historical_data = [
                {
                    "train_id": train.train_id,
                    "track": train.track,
                    "line": train.line,
                    "destination": train.destination,
                }
                for train in historical_trains
            ]

            # Precompute train_id statistics
            train_id_counter = defaultdict(int)
            train_id_track_counter = defaultdict(lambda: defaultdict(int))

            # Precompute line statistics
            line_counter = defaultdict(int)
            line_track_counter = defaultdict(lambda: defaultdict(int))

            # Precompute destination statistics
            dest_counter = defaultdict(int)
            dest_track_counter = defaultdict(lambda: defaultdict(int))

            # Process all historical data
            for train in self.historical_data:
                train_id = train["train_id"]
                line = train["line"]
                destination = train["destination"]
                track = train["track"]

                # Skip if missing data
                if not train_id or not line or not destination or not track:
                    continue

                # Count by train_id
                train_id_counter[train_id] += 1
                train_id_track_counter[train_id][track] += 1

                # Count by line
                line_counter[line] += 1
                line_track_counter[line][track] += 1

                # Count by destination
                dest_counter[destination] += 1
                dest_track_counter[destination][track] += 1

            # Build train_id statistics with precomputed percentages
            self.train_id_stats = {}
            for train_id, count in train_id_counter.items():
                track_counts = train_id_track_counter[train_id]
                track_percentages = {}

                for track in self.all_tracks:
                    if track in track_counts:
                        track_percentages[track] = track_counts[track] / count
                    else:
                        track_percentages[track] = 0.0

                self.train_id_stats[train_id] = {
                    "count": count,
                    "track_counts": dict(track_counts),
                    "track_percentages": track_percentages,
                }

            # Build line statistics with precomputed percentages
            self.line_stats = {}
            for line, count in line_counter.items():
                track_counts = line_track_counter[line]
                track_percentages = {}

                for track in self.all_tracks:
                    if track in track_counts:
                        track_percentages[track] = track_counts[track] / count
                    else:
                        track_percentages[track] = 0.0

                self.line_stats[line] = {
                    "count": count,
                    "track_counts": dict(track_counts),
                    "track_percentages": track_percentages,
                }

            # Build destination statistics with precomputed percentages
            self.destination_stats = {}
            for dest, count in dest_counter.items():
                track_counts = dest_track_counter[dest]
                track_percentages = {}

                for track in self.all_tracks:
                    if track in track_counts:
                        track_percentages[track] = track_counts[track] / count
                    else:
                        track_percentages[track] = 0.0

                self.destination_stats[dest] = {
                    "count": count,
                    "track_counts": dict(track_counts),
                    "track_percentages": track_percentages,
                }

            logger.info(
                f"Precomputed stats for {len(self.train_id_stats)} train IDs, {len(self.line_stats)} lines, and {len(self.destination_stats)} destinations"
            )

        except Exception as e:
            logger.error(f"Error precomputing historical track patterns: {str(e)}")
            # Initialize with empty data
            self.historical_data = []
            self.train_id_stats = {}
            self.line_stats = {}
            self.destination_stats = {}

    def extract(self, train, reference_time=None) -> Dict[str, Any]:
        """Extract historical features based on past patterns"""
        # Convert Train object to dictionary if needed
        train_data = train.__dict__ if hasattr(train, "__dict__") else train

        # If we don't have precomputed data, try to populate it
        # This is a fallback in case extract() is called without precomputation
        if self.historical_data is None:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "No precomputed data available in HistoricalTrackFeatureExtractor. Precomputing now..."
            )
            self.precompute_historical_data(reference_time)

        # Extract train attributes
        train_id = train_data.get("train_id", "")
        line = train_data.get("line", "")
        destination = train_data.get("destination", "")

        # Initialize result
        result = {
            "Matching_TrainID_Count": 0,
            "Matching_Line_Count": 0,
            "Matching_Dest_Count": 0,
        }

        # Get train_id stats from precomputed data
        train_id_info = self.train_id_stats.get(train_id, {})

        # Always initialize all TrainID track percentage features, even if no data
        # This ensures consistent feature dimensions
        result["Matching_TrainID_Count"] = train_id_info.get("count", 0)
        for track in self.all_tracks:
            # Default to 0.0 if no data or track not present
            if train_id_info and "track_percentages" in train_id_info:
                result[f"Matching_TrainID_Track_{track}_Pct"] = train_id_info[
                    "track_percentages"
                ].get(track, 0.0)
            else:
                result[f"Matching_TrainID_Track_{track}_Pct"] = 0.0

        # Get line stats from precomputed data
        line_info = self.line_stats.get(line, {})
        if line_info:
            result["Matching_Line_Count"] = line_info["count"]
            # Add percentages for each track
            for track in self.all_tracks:
                result[f"Matching_Line_Track_{track}_Pct"] = line_info["track_percentages"].get(
                    track, 0.0
                )

        # Get destination stats from precomputed data
        dest_info = self.destination_stats.get(destination, {})
        if dest_info:
            result["Matching_Dest_Count"] = dest_info["count"]
            # Add percentages for each track
            for track in self.all_tracks:
                result[f"Matching_Dest_Track_{track}_Pct"] = dest_info["track_percentages"].get(
                    track, 0.0
                )

        # Return with top-level key to match the expected field name in the model
        return {"historical_features": result}
