"""Feature transformers for TrackCast."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import numpy as np

from trackcast.constants import TRACK_NUMBERS
from trackcast.exceptions import FeatureEngineeringError
from trackcast.utils import (
    encode_day_of_week,
    encode_hour_of_day,
    is_evening_rush,
    is_morning_rush,
    is_weekend,
)

logger = logging.getLogger(__name__)


class FeatureTransformer:
    """Base class for feature transformers."""

    def fit(self, data: List[Dict[str, Any]]) -> "FeatureTransformer":
        """Fit the transformer on the data.

        Args:
            data: List of train data records

        Returns:
            Self for method chaining
        """
        return self

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform the data into features.

        Args:
            data: Train data record

        Returns:
            Dictionary of features
        """
        raise NotImplementedError("Subclasses must implement transform")

    def fit_transform(
        self, data: List[Dict[str, Any]], single_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fit the transformer and transform a single record.

        Args:
            data: List of train data records for fitting
            single_record: Single train record to transform

        Returns:
            Dictionary of features
        """
        self.fit(data)
        return self.transform(single_record)


class TimeFeatureTransformer(FeatureTransformer):
    """Transformer for time-based features."""

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform time data into cyclical and flag features.

        Args:
            data: Train data record

        Returns:
            Dictionary of time features
        """
        try:
            departure_time = datetime.fromisoformat(data["departure_time"])

            # Cyclical encoding of hour and day of week
            hour_sin, hour_cos = encode_hour_of_day(departure_time)
            day_sin, day_cos = encode_day_of_week(departure_time)

            # Binary flags
            weekend = is_weekend(departure_time)
            morning_rush = is_morning_rush(departure_time)
            evening_rush = is_evening_rush(departure_time)

            return {
                "hour_sin": hour_sin,
                "hour_cos": hour_cos,
                "day_of_week_sin": day_sin,
                "day_of_week_cos": day_cos,
                "is_weekend": weekend,
                "is_morning_rush": morning_rush,
                "is_evening_rush": evening_rush,
            }
        except (KeyError, ValueError) as e:
            logger.error(f"Error extracting time features: {str(e)}")
            raise FeatureEngineeringError(f"Failed to extract time features: {str(e)}")


class CategoricalFeatureTransformer(FeatureTransformer):
    """Transformer for categorical features using one-hot encoding."""

    def __init__(self):
        """Initialize the transformer."""
        self.line_categories: Set[str] = set()
        self.destination_categories: Set[str] = set()

    def fit(self, data: List[Dict[str, Any]]) -> "CategoricalFeatureTransformer":
        """Fit the transformer by collecting all unique categories.

        Args:
            data: List of train data records

        Returns:
            Self for method chaining
        """
        for record in data:
            self.line_categories.add(record.get("line", ""))
            self.destination_categories.add(record.get("destination", ""))

        # Remove any empty strings
        self.line_categories.discard("")
        self.destination_categories.discard("")

        logger.info(
            f"Found {len(self.line_categories)} unique lines and {len(self.destination_categories)} unique destinations"
        )
        return self

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform categorical data into one-hot encoded features.

        Args:
            data: Train data record

        Returns:
            Dictionary of categorical features
        """
        try:
            line = data.get("line", "")
            destination = data.get("destination", "")

            line_features = {
                f"line_{self._clean_feature_name(line_name)}": 1 if line_name == line else 0
                for line_name in self.line_categories
            }

            destination_features = {
                f"destination_{self._clean_feature_name(d)}": 1 if d == destination else 0
                for d in self.destination_categories
            }

            return {
                "line_features": line_features,
                "destination_features": destination_features,
            }
        except Exception as e:
            logger.error(f"Error extracting categorical features: {str(e)}")
            raise FeatureEngineeringError(f"Failed to extract categorical features: {str(e)}")

    @staticmethod
    def _clean_feature_name(name: str) -> str:
        """Clean a category name for use as a feature name.

        Args:
            name: Category name

        Returns:
            Cleaned feature name
        """
        # Replace spaces, hyphens, etc. with underscores and convert to lowercase
        return "".join(c if c.isalnum() else "_" for c in name).lower().strip("_")


class TrackUsageFeatureTransformer(FeatureTransformer):
    """Transformer for track usage features."""

    def transform(
        self,
        data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Transform track usage data into features.

        Args:
            data: Train data record
            historical_data: Historical train data up to this point in time
            current_time: Current timestamp (default: departure time of the record)

        Returns:
            Dictionary of track usage features
        """
        # Support base class method signature
        history = [] if historical_data is None else historical_data
        try:
            if current_time is None:
                current_time = datetime.fromisoformat(data["departure_time"])

            # Initialize features
            track_features = {}

            # 24-hour lookback window
            lookback_time = current_time - timedelta(hours=24)

            # Dictionary to store when each track was last used
            last_used_time = {track: None for track in TRACK_NUMBERS}

            # Dictionary to store if track is currently occupied
            is_occupied = {track: False for track in TRACK_NUMBERS}

            # Dictionary to store total minutes track was occupied in last 24 hours
            track_occupied_minutes = {track: 0 for track in TRACK_NUMBERS}

            # Filter historical data to only include records from the lookback window
            relevant_history = [
                record
                for record in history
                if (
                    record.get("track")  # Has a track assignment
                    and datetime.fromisoformat(record["departure_time"])
                    <= current_time  # Before current time
                    and datetime.fromisoformat(record["departure_time"])
                    >= lookback_time  # Within lookback window
                )
            ]

            # Sort by departure time
            relevant_history.sort(key=lambda x: datetime.fromisoformat(x["departure_time"]))

            # Process each historical record to build track usage features
            for record in relevant_history:
                track = record.get("track", "")
                if not track:
                    continue

                departure_time = datetime.fromisoformat(record["departure_time"])

                # Assume a train occupies the track for 30 minutes before departure
                # If track_assigned_at is available, use that instead
                track_assigned_at = record.get("track_assigned_at")
                if track_assigned_at:
                    track_assigned_at = datetime.fromisoformat(track_assigned_at)
                else:
                    track_assigned_at = departure_time - timedelta(minutes=30)

                # Assume a train releases the track at departure time
                # If track_released_at is available, use that instead
                track_released_at = record.get("track_released_at")
                if track_released_at:
                    track_released_at = datetime.fromisoformat(track_released_at)
                else:
                    track_released_at = departure_time

                # Update last used time
                last_used_time[track] = track_released_at

                # Check if track is currently occupied
                if track_assigned_at <= current_time <= track_released_at:
                    is_occupied[track] = True

                # Calculate how long the track was occupied during the lookback window
                # Clamp to lookback window
                occupation_start = max(track_assigned_at, lookback_time)
                occupation_end = min(track_released_at, current_time)

                if occupation_end > occupation_start:
                    occupied_minutes = (occupation_end - occupation_start).total_seconds() / 60
                    track_occupied_minutes[track] += occupied_minutes

            # Calculate minutes since last used
            for track in TRACK_NUMBERS:
                if last_used_time[track]:
                    minutes_since_last_used = (
                        current_time - last_used_time[track]
                    ).total_seconds() / 60
                    # Cap at 24 hours (1440 minutes)
                    track_features[f"track_{track}_last_used"] = min(minutes_since_last_used, 1440)
                else:
                    # If track wasn't used in the lookback window, use maximum value
                    track_features[f"track_{track}_last_used"] = 1440

                track_features[f"is_track_{track}_occupied"] = 1 if is_occupied[track] else 0

                # Calculate track utilization percentage (minutes occupied / total minutes in lookback window)
                total_minutes = (current_time - lookback_time).total_seconds() / 60
                track_features[f"track_{track}_utilization_24h"] = float(
                    track_occupied_minutes[track] / total_minutes
                )

            return {"track_usage_features": track_features}
        except Exception as e:
            logger.error(f"Error extracting track usage features: {str(e)}")
            raise FeatureEngineeringError(f"Failed to extract track usage features: {str(e)}")


class HistoricalTrackFeatureTransformer(FeatureTransformer):
    """Transformer for historical track usage features."""

    def transform(
        self, data: Dict[str, Any], historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Transform historical track usage data into features.

        Args:
            data: Train data record
            historical_data: Historical train data (must be records where tracks were assigned)

        Returns:
            Dictionary of historical track features
        """
        # Support base class method signature
        history = [] if historical_data is None else historical_data
        try:
            train_id = data.get("train_id", "")
            line = data.get("line", "")
            destination = data.get("destination", "")

            # Initialize counters
            train_id_count = 0
            line_count = 0
            destination_count = 0

            # Track usage counters
            train_id_track_usage = {track: 0 for track in TRACK_NUMBERS}
            line_track_usage = {track: 0 for track in TRACK_NUMBERS}
            destination_track_usage = {track: 0 for track in TRACK_NUMBERS}

            # Filter historical data to only include records with track assignments
            relevant_history = [
                record for record in history if record.get("track")  # Has a track assignment
            ]

            # Process each historical record
            for record in relevant_history:
                record_train_id = record.get("train_id", "")
                record_line = record.get("line", "")
                record_destination = record.get("destination", "")
                record_track = record.get("track", "")

                if not record_track:
                    continue

                # Update counters for matching train ID
                if record_train_id == train_id:
                    train_id_count += 1
                    train_id_track_usage[record_track] += 1

                # Update counters for matching line
                if record_line == line:
                    line_count += 1
                    line_track_usage[record_track] += 1

                # Update counters for matching destination
                if record_destination == destination:
                    destination_count += 1
                    destination_track_usage[record_track] += 1

            # Calculate percentages
            historical_features = {
                "matching_train_id_count": train_id_count,
                "matching_line_count": line_count,
                "matching_destination_count": destination_count,
            }

            # Add track usage percentages
            for track in TRACK_NUMBERS:
                # Train ID track usage
                if train_id_count > 0:
                    historical_features[f"matching_train_id_track_{track}_pct"] = float(
                        train_id_track_usage[track] / train_id_count
                    )
                else:
                    historical_features[f"matching_train_id_track_{track}_pct"] = 0.0

                # Line track usage
                if line_count > 0:
                    historical_features[f"matching_line_track_{track}_pct"] = float(
                        line_track_usage[track] / line_count
                    )
                else:
                    historical_features[f"matching_line_track_{track}_pct"] = 0.0

                # Destination track usage
                if destination_count > 0:
                    historical_features[f"matching_destination_track_{track}_pct"] = float(
                        destination_track_usage[track] / destination_count
                    )
                else:
                    historical_features[f"matching_destination_track_{track}_pct"] = 0.0

            return {"historical_features": historical_features}
        except Exception as e:
            logger.error(f"Error extracting historical track features: {str(e)}")
            raise FeatureEngineeringError(f"Failed to extract historical track features: {str(e)}")


class FeatureNormalizer(FeatureTransformer):
    """Transformer for normalizing numerical features."""

    def __init__(self):
        """Initialize the normalizer."""
        self.feature_stats = {}

    def fit(self, data: List[Dict[str, Any]]) -> "FeatureNormalizer":
        """Fit the normalizer by calculating feature statistics.

        Args:
            data: List of feature data records

        Returns:
            Self for method chaining
        """
        # Extract numerical features from each record
        numerical_features: dict[str, list[float]] = {}

        for record in data:
            self._extract_numerical_features(record, numerical_features)

        # Calculate mean and standard deviation for each feature
        for feature, values in numerical_features.items():
            mean = np.mean(values)
            std = np.std(values) if len(values) > 1 else 1.0
            # Avoid division by zero
            std = std if std > 0 else 1.0
            self.feature_stats[feature] = {"mean": mean, "std": std}

        return self

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize numerical features in the data.

        Args:
            data: Feature data record

        Returns:
            Normalized feature data record
        """
        result = {}

        # Copy non-numerical features as-is
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._normalize_dict(value)
            else:
                result[key] = value

        return result

    def _normalize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize numerical values in a dictionary.

        Args:
            data: Dictionary containing numerical values

        Returns:
            Dictionary with normalized numerical values
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Normalize numerical values if stats are available
                if key in self.feature_stats:
                    mean = self.feature_stats[key]["mean"]
                    std = self.feature_stats[key]["std"]
                    result[key] = (value - mean) / std
                else:
                    result[key] = value
            elif isinstance(value, dict):
                # Recursively normalize nested dictionaries
                result[key] = self._normalize_dict(value)
            else:
                result[key] = value

        return result

    def _extract_numerical_features(
        self, data: Dict[str, Any], result: Dict[str, List[float]], prefix: str = ""
    ):
        """Extract numerical features from nested dictionaries.

        Args:
            data: Feature data record
            result: Dictionary to store extracted numerical features
            prefix: Prefix for feature names in nested dictionaries
        """
        for key, value in data.items():
            feature_name = f"{prefix}{key}" if prefix else key

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if feature_name not in result:
                    result[feature_name] = []
                result[feature_name].append(value)
            elif isinstance(value, dict):
                # Recursively extract from nested dictionaries
                nested_prefix = f"{feature_name}_" if feature_name else ""
                self._extract_numerical_features(value, result, nested_prefix)
