"""
Data import service for TrackCast.

This module provides functionality to import train data from CSV files or JSON files
into the database, preserving train state transitions and track timing information.
"""

import csv
import glob
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session

from trackcast.config import settings
from trackcast.db.models import Train
from trackcast.db.repository import TrainRepository
from trackcast.utils import clean_destination

logger = logging.getLogger(__name__)


class DataImportService:
    """Service that imports train data from files into the database."""

    def __init__(self, db_session: Session):
        """
        Initialize the data import service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.session = db_session
        self.train_repo = TrainRepository(db_session)
        # Initialize train ID sets for departed train detection
        self.current_train_ids = set()

    def clear_data(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Clear all train data from the database.

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = datetime.now()

        try:
            stats = {
                "clear_timestamp": start_time.isoformat(),
            }

            # Clear all train data
            result = self.train_repo.clear_all_train_data()
            stats.update(result)

            # Calculate duration
            time_elapsed = (datetime.now() - start_time).total_seconds()
            stats["duration_seconds"] = time_elapsed

            logger.info(f"Database cleared: {stats['trains_deleted']} trains removed in {time_elapsed:.2f}s")
            return True, stats

        except Exception as e:
            error_msg = f"Error clearing database: {str(e)}"
            logger.error(error_msg)

            time_elapsed = (datetime.now() - start_time).total_seconds()
            stats = {
                "clear_timestamp": start_time.isoformat(),
                "duration_seconds": time_elapsed,
                "error": error_msg,
            }

            return False, stats

    def import_data(
        self, source_dir: str, file_pattern: str = None, file_format: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Import data from files in the specified directory.

        Args:
            source_dir: Directory containing data files
            file_pattern: Pattern to match filenames (default: all files)
            file_format: Format of data files ('csv' or 'json')

        Returns:
            Tuple containing success status and statistics dictionary
        """
        start_time = datetime.now()
        stats = {
            "import_timestamp": start_time.isoformat(),
            "files_processed": 0,
            "records_processed": 0,
            "trains_new": 0,
            "trains_updated": 0,
            "errors": [],
        }

        try:
            # Validate source directory
            source_path = Path(source_dir)
            if not source_path.exists() or not source_path.is_dir():
                error_msg = f"Source directory does not exist or is not a directory: {source_dir}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                return False, stats

            # Get list of files matching pattern
            if file_pattern:
                file_paths = sorted(list(source_path.glob(file_pattern)))
            else:
                # Default patterns based on format
                if file_format == "csv":
                    file_paths = sorted(list(source_path.glob("*.csv")))
                elif file_format == "json":
                    file_paths = sorted(list(source_path.glob("*.json")))
                else:
                    # Try both formats if not specified
                    file_paths = sorted(list(source_path.glob("*.csv")) + list(source_path.glob("*.json")))

            if not file_paths:
                error_msg = f"No matching files found in {source_dir}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                return False, stats

            logger.info(f"Found {len(file_paths)} files to process")

            # Sort files alphabetically by name to maintain chronological order
            # Since filenames include timestamps in format YYYYMMDD_HHMMSS, alphabetical sort will be chronological
            file_paths = self._sort_files_by_name(file_paths)

            # Process each file
            for file_path in file_paths:
                try:
                    file_format_detected = file_format or self._detect_file_format(file_path)
                    
                    if file_format_detected == "csv":
                        success, file_stats = self._import_csv_file(file_path)
                    elif file_format_detected == "json":
                        success, file_stats = self._import_json_file(file_path)
                    else:
                        logger.warning(f"Unsupported file format for {file_path}, skipping")
                        continue

                    # Update stats
                    stats["files_processed"] += 1
                    stats["records_processed"] += file_stats.get("records_processed", 0)
                    stats["trains_new"] += file_stats.get("trains_new", 0)
                    stats["trains_updated"] += file_stats.get("trains_updated", 0)
                    
                    if not success:
                        stats["errors"].extend(file_stats.get("errors", []))
                
                except Exception as e:
                    error_msg = f"Error processing file {file_path}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Calculate time elapsed
            time_elapsed = (datetime.now() - start_time).total_seconds()
            stats["duration_seconds"] = time_elapsed

            if stats["errors"]:
                logger.warning(f"Import completed with {len(stats['errors'])} errors")
                return False, stats
            else:
                logger.info(
                    f"Import completed: {stats['files_processed']} files, "
                    f"{stats['records_processed']} records, "
                    f"{stats['trains_new']} new trains, "
                    f"{stats['trains_updated']} updated trains"
                )
                return True, stats

        except Exception as e:
            error_msg = f"Error in data import: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return False, stats

    def _detect_file_format(self, file_path: Path) -> str:
        """
        Detect file format based on extension and contents.

        Args:
            file_path: Path to the file

        Returns:
            String indicating the file format ('csv', 'json', or 'unknown')
        """
        extension = file_path.suffix.lower()
        
        if extension == ".csv":
            return "csv"
        elif extension == ".json":
            return "json"
        
        # Try to detect format by reading the first few bytes
        try:
            with open(file_path, "r") as f:
                start = f.read(20).strip()
                if start.startswith("{") or start.startswith("["):
                    return "json"
                elif "," in start or ";" in start:
                    return "csv"
        except Exception:
            pass
            
        return "unknown"

    def _sort_files_by_name(self, file_paths: List[Path]) -> List[Path]:
        """
        Sort files alphabetically by filename.

        Since filenames follow the format getTrainSchedule19Rec_NY_YYYYMMDD_HHMMSS.json,
        alphabetical sorting will naturally order files chronologically.

        Args:
            file_paths: List of file paths

        Returns:
            Sorted list of file paths
        """
        return sorted(file_paths, key=lambda p: str(p.name))

    def _parse_timestamp_from_filename(self, file_path: Path) -> Optional[datetime]:
        """
        Extract timestamp from filename.

        Expected formats include:
        - getTrainSchedule19Rec_NY_YYYYMMDD_HHMMSS.json
        - trains_YYYYMMDD_HHMMSS.csv

        Args:
            file_path: Path to the file

        Returns:
            Extracted datetime or None if not found
        """
        try:
            filename = file_path.name

            # Match dates in format YYYYMMDD_HHMMSS
            match = re.search(r'(\d{8})_(\d{6})', filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS

                if len(date_str) == 8 and len(time_str) == 6:
                    year = int(date_str[0:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    hour = int(time_str[0:2])
                    minute = int(time_str[2:4])
                    second = int(time_str[4:6])

                    return datetime(year, month, day, hour, minute, second)

            # If no match, fall back to file modification time
            return datetime.fromtimestamp(file_path.stat().st_mtime)

        except Exception as e:
            logger.warning(f"Could not extract timestamp from filename {file_path.name}: {str(e)}")
            return None

    def _check_departed_trains(self, current_train_ids: Set[Tuple[str, datetime]], max_import_time: datetime) -> int:
        """
        Check for trains that have departed but are no longer in the imported data.

        Args:
            current_train_ids: Set of (train_id, departure_time) tuples in current import batch
            max_import_time: Maximum departure time in the current import batch

        Returns:
            Number of trains marked as departed
        """
        try:
            logger.info(f"Running departed train check for import data at {max_import_time}")
            logger.info(f"Current import batch has {len(current_train_ids)} train records")

            # Query for trains with departure times before the max import time
            # and with status of BOARDING
            query = self.session.query(Train).filter(
                Train.departure_time <= max_import_time,
                Train.status == "BOARDING",
            )

            # Log the SQL query being executed
            query_sql = str(query.statement.compile(
                compile_kwargs={"literal_binds": True}
            ))
            logger.info(f"Executing SQL query: {query_sql}")

            potential_departed = query.all()
            logger.info(f"Found {len(potential_departed)} boarding trains with departure times in the past")

            departed_count = 0

            for train in potential_departed:
                # Check if this train is in the current import batch
                train_key = (train.train_id, train.departure_time)
                if train_key not in current_train_ids:
                    # Train is not in current import but hasn't been marked as departed
                    logger.info(
                        f"Train {train.train_id} to {train.destination} scheduled for {train.departure_time} "
                        f"on track {train.track} is not in import data - marking as DEPARTED"
                    )
                    update_data = {
                        "status": "DEPARTED",
                    }
                    self.train_repo.update_train(train, update_data, max_import_time)
                    departed_count += 1
                else:
                    logger.info(
                        f"Train {train.train_id} to {train.destination} scheduled for {train.departure_time} "
                        f"is still present in import data despite being past departure time"
                    )

            if departed_count > 0:
                logger.info(
                    f"Marked {departed_count} trains as departed that were not in import data"
                )
            else:
                logger.info("No trains needed to be marked as departed in this import batch")

            return departed_count

        except Exception as e:
            logger.error(f"Error checking for departed trains: {str(e)}")
            # Don't fail the entire import process for this
            return 0

    def _import_csv_file(self, file_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """
        Import data from a CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            Tuple containing success status and statistics dictionary
        """
        stats = {
            "file": str(file_path),
            "records_processed": 0,
            "trains_new": 0,
            "trains_updated": 0,
            "trains_departed": 0,
            "errors": [],
        }

        try:
            # Read CSV file
            with open(file_path, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)

                logger.info(f"Processing {len(rows)} records from {file_path}")

                # Track current time for track state management
                # Try to get timestamp from filename first
                file_timestamp = self._parse_timestamp_from_filename(file_path)
                current_time = file_timestamp if file_timestamp else datetime.now()

                # Initialize a set to collect train IDs for departed train detection
                current_train_ids = set()
                max_departure_time = current_time

                # Process each row
                for row in rows:
                    try:
                        # Standardize field names (handle variations in CSV exports)
                        train_data = self._standardize_csv_record(row)

                        # Skip if required fields are missing
                        if not train_data.get("train_id") or not train_data.get("departure_time"):
                            logger.warning(f"Skipping record due to missing train_id or departure_time: {row}")
                            continue

                        # Import the train record
                        new_train, updated = self._import_train_record(train_data, current_time)

                        # Track train ID and departure time for departed train detection
                        train_id = train_data.get("train_id")
                        departure_time = train_data.get("departure_time")
                        if train_id and departure_time:
                            current_train_ids.add((train_id, departure_time))

                            # Track max departure time for departed train detection
                            if departure_time > max_departure_time:
                                max_departure_time = departure_time

                        # Update stats
                        stats["records_processed"] += 1
                        if new_train:
                            stats["trains_new"] += 1
                        elif updated:
                            stats["trains_updated"] += 1

                    except Exception as e:
                        error_msg = f"Error processing CSV row: {str(e)}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

                # Check for departed trains
                if current_train_ids:
                    departed_count = self._check_departed_trains(current_train_ids, max_departure_time)
                    stats["trains_departed"] = departed_count

                return len(stats["errors"]) == 0, stats

        except Exception as e:
            error_msg = f"Error reading CSV file {file_path}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return False, stats

    def _import_json_file(self, file_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """
        Import data from a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Tuple containing success status and statistics dictionary
        """
        stats = {
            "file": str(file_path),
            "records_processed": 0,
            "trains_new": 0,
            "trains_updated": 0,
            "trains_departed": 0,
            "errors": [],
        }

        try:
            # Read JSON file
            with open(file_path, "r") as jsonfile:
                json_data = json.load(jsonfile)

            # Try to extract timestamp from filename
            file_timestamp = self._parse_timestamp_from_filename(file_path)

            # Track current time for track state management
            current_time = file_timestamp if file_timestamp else datetime.now()

            # Initialize a set to collect train IDs for departed train detection
            current_train_ids = set()
            max_departure_time = current_time

            # Handle different JSON structures
            train_records = []

            # If it's a raw API response format with "data" wrapper
            if "data" in json_data and "ITEMS" in json_data.get("data", {}):
                # This is the raw NJ Transit API format with data wrapper
                items = json_data["data"]["ITEMS"]
                timestamp = json_data.get("timestamp", current_time)

                # Process each train using same logic as collector
                for item in items:
                    # Parse departure time
                    departure_time_str = item.get("SCHED_DEP_DATE", "")
                    try:
                        departure_time = (
                            datetime.strptime(departure_time_str, "%d-%b-%Y %I:%M:%S %p").isoformat()
                            if departure_time_str
                            else None
                        )
                    except ValueError:
                        logger.warning(f"Invalid date format: {departure_time_str}")
                        departure_time = None

                    if not departure_time:
                        logger.warning(f"Skipping train with missing departure time: {item}")
                        continue

                    # Extract train record
                    train_record = {
                        "timestamp": timestamp,
                        "train_id": item.get("TRAIN_ID", ""),
                        "destination": item.get("DESTINATION", ""),
                        "track": item.get("TRACK", ""),
                        "departure_time": departure_time,
                        "status": item.get("STATUS", "").strip(),
                        "line": item.get("LINE", ""),
                        "line_code": item.get("LINECODE", ""),
                    }
                    train_records.append(train_record)

            # If it's a raw API response format without "data" wrapper (direct ITEMS)
            elif "ITEMS" in json_data and isinstance(json_data.get("ITEMS"), list):
                # This is the raw NJ Transit API format without data wrapper
                items = json_data["ITEMS"]

                # Extract file timestamp from filename if available
                timestamp = None
                if file_timestamp:
                    timestamp = file_timestamp.isoformat()
                else:
                    # Try older approach for backward compatibility
                    if hasattr(file_path, 'name'):
                        # Try to extract timestamp from filename (format: getTrainSchedule19Rec_NY_YYYYMMDD_HHMMSS.json)
                        try:
                            filename = file_path.name
                            date_parts = filename.split('_')
                            if len(date_parts) >= 4:
                                date_str = date_parts[2]  # YYYYMMDD
                                time_str = date_parts[3].split('.')[0]  # HHMMSS
                                if len(date_str) == 8 and len(time_str) == 6:
                                    year = date_str[0:4]
                                    month = date_str[4:6]
                                    day = date_str[6:8]
                                    hour = time_str[0:2]
                                    minute = time_str[2:4]
                                    second = time_str[4:6]
                                    timestamp = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
                        except Exception:
                            pass

                # If timestamp couldn't be extracted from filename, use current time
                if not timestamp:
                    timestamp = datetime.now().isoformat()

                # Process each train
                for item in items:
                    # Parse departure time
                    departure_time_str = item.get("SCHED_DEP_DATE", "")
                    try:
                        departure_time = (
                            datetime.strptime(departure_time_str, "%d-%b-%Y %I:%M:%S %p").isoformat()
                            if departure_time_str
                            else None
                        )
                    except ValueError:
                        logger.warning(f"Invalid date format: {departure_time_str}")
                        departure_time = None

                    if not departure_time:
                        logger.warning(f"Skipping train with missing departure time: {item}")
                        continue

                    # Extract train record
                    train_record = {
                        "timestamp": timestamp,
                        "train_id": item.get("TRAIN_ID", ""),
                        "destination": item.get("DESTINATION", ""),
                        "track": item.get("TRACK", ""),
                        "departure_time": departure_time,
                        "status": item.get("STATUS", "").strip(),
                        "line": item.get("LINE", ""),
                        "line_code": item.get("LINECODE", ""),
                    }
                    train_records.append(train_record)

            # If no valid format was detected
            else:
                error_msg = f"Unsupported JSON format in file {file_path}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                return False, stats

            # Process each train record
            logger.info(f"Processing {len(train_records)} records from {file_path}")

            for train_record in train_records:
                try:
                    # Standardize the record
                    train_data = self._standardize_json_record(train_record)

                    # Skip if required fields are missing
                    if not train_data.get("train_id") or not train_data.get("departure_time"):
                        logger.warning(f"Skipping record due to missing train_id or departure_time: {train_record}")
                        continue

                    # Import the train record
                    new_train, updated = self._import_train_record(train_data,
                                                                 train_data.get("timestamp", current_time))

                    # Track train ID and departure time for departed train detection
                    train_id = train_data.get("train_id")
                    departure_time = train_data.get("departure_time")
                    if train_id and departure_time:
                        current_train_ids.add((train_id, departure_time))

                        # Track max departure time for departed train detection
                        if departure_time > max_departure_time:
                            max_departure_time = departure_time

                    # Update stats
                    stats["records_processed"] += 1
                    if new_train:
                        stats["trains_new"] += 1
                    elif updated:
                        stats["trains_updated"] += 1

                except Exception as e:
                    error_msg = f"Error processing JSON record: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Check for departed trains
            if current_train_ids:
                departed_count = self._check_departed_trains(current_train_ids, max_departure_time)
                stats["trains_departed"] = departed_count

            return len(stats["errors"]) == 0, stats

        except Exception as e:
            error_msg = f"Error reading JSON file {file_path}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return False, stats

    def _standardize_csv_record(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        Standardize field names and values from CSV record.

        Args:
            row: CSV row as dictionary

        Returns:
            Standardized train data dictionary
        """
        # Create a mapping of possible CSV column names to standardized field names
        field_mapping = {
            "Train_ID": "train_id",
            "TRAIN_ID": "train_id",
            "train_id": "train_id",

            "Destination": "destination",
            "DESTINATION": "destination",
            "destination": "destination",

            "Track": "track",
            "TRACK": "track",
            "track": "track",

            "Departure_Time": "departure_time",
            "DEPARTURE_TIME": "departure_time",
            "departure_time": "departure_time",

            "Status": "status",
            "STATUS": "status",
            "status": "status",

            "Line": "line",
            "LINE": "line",
            "line": "line",

            "Line_Code": "line_code",
            "LINE_CODE": "line_code",
            "LINECODE": "line_code",
            "line_code": "line_code",

            "Timestamp": "timestamp",
            "TIMESTAMP": "timestamp",
            "timestamp": "timestamp",
        }

        # Create standardized record
        train_data = {}

        # Map fields using the mapping
        for csv_field, value in row.items():
            if csv_field in field_mapping:
                std_field = field_mapping[csv_field]
                train_data[std_field] = value

        # Clean destination field if present
        if "destination" in train_data:
            train_data["destination"] = clean_destination(train_data["destination"])

        # Handle departure time conversion
        if "departure_time" in train_data and train_data["departure_time"]:
            # Try to parse the departure time if it's a string
            if isinstance(train_data["departure_time"], str):
                try:
                    # Try ISO format first
                    train_data["departure_time"] = datetime.fromisoformat(train_data["departure_time"])
                except ValueError:
                    try:
                        # Try other common formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%d-%b-%Y %I:%M:%S %p"]:
                            try:
                                train_data["departure_time"] = datetime.strptime(
                                    train_data["departure_time"], fmt
                                )
                                break
                            except ValueError:
                                continue
                    except Exception:
                        logger.warning(f"Could not parse departure time: {train_data['departure_time']}")

        return train_data

    def _standardize_json_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize field names and values from JSON record.

        Args:
            record: JSON record as dictionary

        Returns:
            Standardized train data dictionary
        """
        # Create standardized record
        train_data = {
            "train_id": record.get("train_id", ""),
            "destination": clean_destination(record.get("destination", "")),
            "track": record.get("track", ""),
            "status": record.get("status", ""),
            "line": record.get("line", ""),
            "line_code": record.get("line_code", ""),
            "timestamp": record.get("timestamp", ""),
        }

        # Handle departure time
        departure_time = record.get("departure_time")
        if departure_time:
            if isinstance(departure_time, str):
                try:
                    train_data["departure_time"] = datetime.fromisoformat(departure_time)
                except ValueError:
                    try:
                        # Try other common formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%d-%b-%Y %I:%M:%S %p"]:
                            try:
                                train_data["departure_time"] = datetime.strptime(departure_time, fmt)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        logger.warning(f"Could not parse departure time: {departure_time}")
            else:
                train_data["departure_time"] = departure_time

        return train_data

    def _import_train_record(
        self, train_data: Dict[str, Any], timestamp
    ) -> Tuple[bool, bool]:
        """
        Import a single train record into the database.

        Args:
            train_data: Train data dictionary

        Returns:
            Tuple containing:
            - Whether a new train was created
            - Whether an existing train was updated
        """
        try:
            # Check if train exists in database
            existing_train = self.train_repo.get_train_by_id_and_time(
                train_data["train_id"], train_data["departure_time"]
            )
            if existing_train:
                # Update existing train
                update_data = {
                    "track": train_data.get("track"),
                    "status": train_data.get("status"),
                    "line": train_data.get("line"),
                    "destination": train_data.get("destination"),
                    "line_code": train_data.get("line_code"),
                }
                
                # Update train in database - using the repository will properly handle
                # track_assigned_at and track_released_at fields
                self.train_repo.update_train(existing_train, update_data, timestamp)
                logger.debug(f"Updated train {existing_train.train_id}")
                return False, True
            
            else:
                # Create new train record
                new_train = {
                    "train_id": train_data["train_id"],
                    "line": train_data.get("line", ""),
                    "line_code": train_data.get("line_code", ""),
                    "destination": train_data.get("destination", ""),
                    "departure_time": train_data["departure_time"],
                    "track": train_data.get("track", ""),
                    "status": train_data.get("status", ""),
                }
                
                # Set track_assigned_at if track is already known
                if train_data.get("track"):
                    new_train["track_assigned_at"] = timestamp
                
                # Create train in database
                self.train_repo.create_train(new_train, timestamp)
                logger.debug(f"Created new train {new_train['train_id']}")
                return True, False
                
        except Exception as e:
            logger.error(f"Error importing train record: {str(e)}")
            raise
