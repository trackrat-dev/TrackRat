"""Data processing utilities for TrackCast."""

import csv
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from trackcast.exceptions import DataProcessingError
from trackcast.utils import parse_njtransit_datetime, save_json

logger = logging.getLogger(__name__)


class NJTransitDataProcessor:
    """Processor for NJ Transit API data."""

    def __init__(self, data_dir: str = "data"):
        """Initialize the processor.

        Args:
            data_dir: Directory to store processed data
        """
        self.data_dir = data_dir
        self.raw_data_dir = os.path.join(data_dir, "raw")
        self.processed_data_dir = os.path.join(data_dir, "processed")

        # Create directories if they don't exist
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)

    def save_raw_data(self, data: Dict[str, Any], timestamp: Optional[datetime] = None) -> str:
        """Save raw API data to a JSON file.

        Args:
            data: Raw API data
            timestamp: Timestamp to use in filename (default: current time)

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now()

        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"njtransit_raw_{timestamp_str}.json"
        filepath = os.path.join(self.raw_data_dir, filename)

        data_with_meta = {
            "timestamp": timestamp.isoformat(),
            "source": "NJ Transit API",
            "data": data,
        }

        save_json(data_with_meta, filepath)
        logger.info(f"Saved raw data to {filepath}")
        return filepath

    def process_raw_data(
        self, data: Dict[str, Any], timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Process raw API data into structured train records.

        Args:
            data: Raw API data
            timestamp: Collection timestamp (default: current time)

        Returns:
            List of processed train records
        """
        if timestamp is None:
            timestamp = datetime.now()

        try:
            train_items = data.get("ITEMS", [])
            processed_items = []

            for item in train_items:
                train_id = item.get("TRAIN_ID", "")
                line = item.get("LINE", "")
                destination = item.get("DESTINATION", "")
                status = item.get("STATUS", "").strip()
                track = item.get("TRACK", "").strip()

                # Parse departure time
                departure_time_str = item.get("SCHED_DEP_DATE", "")
                if not departure_time_str:
                    logger.warning(f"Missing departure time for train {train_id}, skipping")
                    continue

                try:
                    departure_time = parse_njtransit_datetime(departure_time_str)
                except ValueError as e:
                    logger.warning(f"Invalid departure time format for train {train_id}: {str(e)}")
                    continue

                processed_items.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "train_id": train_id,
                        "line": line,
                        "destination": destination,
                        "departure_time": departure_time.isoformat(),
                        "status": status,
                        "track": track,
                        "raw_data": item,
                    }
                )

            return processed_items
        except (KeyError, TypeError) as e:
            logger.error(f"Error processing raw data: {str(e)}")
            raise DataProcessingError(f"Failed to process raw data: {str(e)}")

    def save_processed_data(
        self, processed_items: List[Dict[str, Any]], timestamp: Optional[datetime] = None
    ) -> str:
        """Save processed train records to a CSV file.

        Args:
            processed_items: List of processed train records
            timestamp: Timestamp to use in filename (default: current time)

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now()

        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"njtransit_processed_{timestamp_str}.csv"
        filepath = os.path.join(self.processed_data_dir, filename)

        if not processed_items:
            logger.warning("No processed items to save")
            return ""

        fieldnames = [
            "timestamp",
            "train_id",
            "line",
            "destination",
            "departure_time",
            "status",
            "track",
        ]

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in processed_items:
                # Filter out raw_data field and include only the specified fields
                row = {field: item.get(field, "") for field in fieldnames}
                writer.writerow(row)

        logger.info(f"Saved {len(processed_items)} processed records to {filepath}")
        return filepath
