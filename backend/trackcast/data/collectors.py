"""
Data collection modules for TrackCast.
"""

import abc
import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from trackcast.config import settings
from trackcast.exceptions import APIError
from trackcast.utils import clean_destination, parse_iso_datetime_to_eastern

logger = logging.getLogger(__name__)


class BaseCollector(abc.ABC):
    """Base abstract class for data collectors."""

    @abc.abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Collect data from source."""
        pass

    @abc.abstractmethod
    def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process collected data."""
        pass

    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Run collection and processing pipeline.

        Returns:
            Tuple containing:
            - List of processed train records
            - Statistics about the collection run
        """
        start_time = time.time()
        stats = {
            "collected_at": datetime.now().isoformat(),
            "record_count": 0,
            "new_records": 0,
            "updated_records": 0,
            "processing_time_ms": 0,
        }

        try:
            # Collect raw data
            data = self.collect()

            # Process data into structured format
            processed_data = self.process(data)

            # Update statistics
            stats["record_count"] = len(processed_data)
            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)

            return processed_data, stats
        except Exception as e:
            logger.error(f"Error in data collection: {str(e)}")
            stats["error"] = str(e)
            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)
            raise


class NJTransitCollector(BaseCollector):
    """Collector for NJ Transit API data."""

    # API endpoint constants
    TOKEN_ENDPOINT = "getToken"
    TRAIN_SCHEDULE_ENDPOINT = "getTrainSchedule"

    def __init__(
        self,
        base_url_or_config: Optional[Union[str, Dict[str, Any]]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        station_code: Optional[str] = None,
        station_name: Optional[str] = None,
        retry_attempts: Optional[int] = None,
        timeout: Optional[int] = None,
        data_dir: Optional[str] = None,
        token_file: Optional[str] = None,
        debug_mode: Optional[bool] = None,
    ):
        """
        Initialize NJ Transit API collector.

        Args:
            base_url_or_config: Base API URL (defaults to config value) or config dict
            username: NJ Transit API username (from config or env var)
            password: NJ Transit API password (from config or env var)
            station_code: Station code to fetch data for
            station_name: Human-readable station name
            retry_attempts: Number of retry attempts for API calls
            timeout: Timeout in seconds for API calls
            data_dir: Directory to store raw and processed data
            token_file: Path to token cache file (if None, uses data_dir/token.json)
            debug_mode: Whether to save all raw API responses for debugging
        """
        # Handle config dict case (for tests)
        if isinstance(base_url_or_config, dict):
            # Extract values from config dict, but still allow parameter overrides
            config = base_url_or_config
            base_url = config.get('njtransit', {}).get('api_url')
            if username is None:
                username = config.get('njtransit', {}).get('username')
            if password is None:
                password = config.get('njtransit', {}).get('password')
            if station_code is None:
                station_code = config.get('njtransit', {}).get('station_code', 'NY')
            if station_name is None:
                station_name = config.get('njtransit', {}).get('station_name', 'New York Penn')
        else:
            base_url = base_url_or_config

        self.base_url = base_url or (settings.njtransit_api and settings.njtransit_api.base_url)
        self.username = (
            username or (settings.njtransit_api and settings.njtransit_api.username) or os.environ.get("NJT_USERNAME")
        )
        self.password = (
            password or (settings.njtransit_api and settings.njtransit_api.password) or os.environ.get("NJT_PASSWORD")
        )
        self.station_code = station_code  # Must be provided explicitly
        self.station_name = station_name  # Must be provided explicitly
        if not self.station_code:
            raise ValueError("Station code is required")
        if not self.station_name:
            raise ValueError("Station name is required")

        self.retry_attempts = retry_attempts or (settings.njtransit_api and settings.njtransit_api.retry_attempts) or 3
        self.timeout = timeout or (settings.njtransit_api and settings.njtransit_api.timeout_seconds) or 10
        self.debug_mode = debug_mode or (settings.njtransit_api and settings.njtransit_api.debug_mode) or False

        # Set up data directories
        self.data_dir = Path(data_dir or "data")
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.debug_dir = self.data_dir / "debug"

        # Create directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        if self.debug_mode:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Token management
        self.token_file = token_file or str(self.data_dir / "token.json")
        self.token = self._load_token_from_file()

        if not self.base_url:
            raise ValueError("NJ Transit API base URL is required")

    def _load_token_from_file(self) -> Optional[str]:
        """
        Load authentication token from a file.

        Returns:
            Valid auth token or None if file doesn't exist or token is invalid
        """
        if not os.path.exists(self.token_file):
            logger.debug(f"Token file {self.token_file} not found")
            return None

        try:
            with open(self.token_file, "r") as file:
                data = json.load(file)
                if data.get("Authenticated") == "True" and "UserToken" in data:
                    logger.info("Loaded authentication token from file")
                    return data.get("UserToken")
                else:
                    logger.warning("Invalid token file format")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading token file: {str(e)}")

        return None

    def _save_token_to_file(self, token_data: Dict[str, Any]) -> None:
        """
        Save token data to a file for reuse.

        Args:
            token_data: The full token response from the API
        """
        try:
            with open(self.token_file, "w") as file:
                json.dump(token_data, file, indent=2)
                logger.debug(f"Saved token to {self.token_file}")
        except IOError as e:
            logger.warning(f"Failed to save token: {str(e)}")

    def _get_token(self) -> str:
        """
        Authenticate and get a token from the NJ Transit API.

        Returns:
            Authentication token string

        Raises:
            APIError: If authentication fails or API is unavailable
        """
        url = f"{self.base_url}/{self.TOKEN_ENDPOINT}"
        files = {"username": (None, self.username), "password": (None, self.password)}

        try:
            logger.debug(f"Authenticating with NJ Transit API at {url}")
            response = requests.post(url, files=files, timeout=self.timeout)
            response.raise_for_status()

            # Archive raw response if debug mode is enabled
            if self.debug_mode:
                self._archive_response(response, "getToken")

            data = response.json()
            if data.get("Authenticated") == "True":
                # Save token for future use
                self._save_token_to_file(data)
                logger.info("Successfully authenticated with NJ Transit API")
                return data.get("UserToken")
            elif "errorMessage" in data:
                error_msg = f"API authentication error: {data['errorMessage']}"
                logger.error(error_msg)
                raise APIError(error_msg)
            else:
                error_msg = "Authentication failed. Check credentials."
                logger.error(error_msg)
                raise APIError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Request error during authentication: {str(e)}"
            logger.error(error_msg)
            raise APIError(error_msg)
        except json.JSONDecodeError:
            error_msg = "Invalid response format from the API during authentication"
            logger.error(error_msg)
            raise APIError(error_msg)

    def _archive_response(
        self, response: Union[requests.Response, Dict[str, Any]], endpoint_name: str
    ) -> None:
        """
        Archive raw API response to a file for debugging purposes.

        Args:
            response: API response or data dictionary
            endpoint_name: Name of the API endpoint for the filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.debug_dir / f"{endpoint_name}_{timestamp}.json"

        try:
            with open(filename, "w") as file:
                if isinstance(response, requests.Response):
                    json.dump(response.json(), file, indent=2)
                else:
                    json.dump(response, file, indent=2)
            logger.debug(f"Archived response to {filename}")
        except Exception as e:
            logger.warning(f"Failed to archive response: {str(e)}")

    def collect(self) -> Dict[str, Any]:
        """
        Collect data from NJ Transit API.

        Returns:
            Dict containing the API response data and collection timestamp

        Raises:
            APIError: If the API request fails after all retry attempts
        """
        collection_time = datetime.now()

        # Ensure we have a valid token
        if not self.token:
            self.token = self._get_token()
            if not self.token:
                raise APIError("Failed to obtain authentication token")

        # Now fetch train schedule data
        attempts = 0
        last_error = None

        while attempts < self.retry_attempts:
            try:
                url = f"{self.base_url}/{self.TRAIN_SCHEDULE_ENDPOINT}"
                files = {"token": (None, self.token), "station": (None, self.station_code)}

                logger.debug(
                    f"Fetching train schedule from {url} (attempt {attempts+1}/{self.retry_attempts})"
                )
                response = requests.post(url, files=files, timeout=self.timeout)
                response.raise_for_status()

                # Archive raw response if debug mode is enabled
                if self.debug_mode:
                    self._archive_response(
                        response, f"{self.TRAIN_SCHEDULE_ENDPOINT}_{self.station_code}"
                    )

                # Parse JSON response
                raw_data = response.json()

                # Save raw data to file for audit purposes
                timestamp = collection_time.strftime("%Y%m%d%H%M%S")
                raw_file = self.raw_dir / f"njtransit_{timestamp}.json"

                with open(raw_file, "w") as f:
                    json.dump(raw_data, f, indent=2)
                    logger.debug(f"Saved raw data to {raw_file}")

                return {"data": raw_data, "timestamp": collection_time.isoformat()}

            except requests.RequestException as e:
                attempts += 1
                last_error = e
                logger.warning(
                    f"API request failed, attempt {attempts}/{self.retry_attempts}: {str(e)}"
                )

                # If token may be expired, try to get a new one
                if attempts == 1 and (
                    (hasattr(e, "response") and e.response and e.response.status_code == 401)
                    or "Unauthorized" in str(e)
                ):
                    logger.info("Token may be expired, attempting to refresh")
                    try:
                        self.token = self._get_token()
                    except APIError as auth_error:
                        logger.error(f"Failed to refresh token: {str(auth_error)}")

                if attempts < self.retry_attempts:
                    time.sleep(2)  # Wait before retry

        # If we reach here, all attempts failed
        error_msg = f"Failed to collect data after {self.retry_attempts} attempts"
        if last_error:
            error_msg += f": {str(last_error)}"

        logger.error(error_msg)
        raise APIError(error_msg)

    def process(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process NJ Transit API data into structured format.

        Args:
            raw_data: Dictionary containing the raw API response

        Returns:
            List of processed train records

        Raises:
            ValueError: If the data format is invalid or cannot be processed
        """
        processed_data = []
        try:
            timestamp = raw_data["timestamp"]
            items = raw_data["data"]["ITEMS"]

            logger.info(f"Processing {len(items)} train records")

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

                # Process stop information
                stops = []
                if "STOPS" in item and isinstance(item["STOPS"], list):
                    for stop in item["STOPS"]:
                        if isinstance(stop, dict):
                            # Parse stop times
                            stop_time = None
                            dep_time = None

                            stop_time_str = stop.get("TIME", "")
                            if stop_time_str:
                                try:
                                    stop_time = datetime.strptime(
                                        stop_time_str, "%d-%b-%Y %I:%M:%S %p"
                                    ).isoformat()
                                except ValueError:
                                    logger.warning(f"Invalid stop time format: {stop_time_str}")

                            dep_time_str = stop.get("DEP_TIME", "")
                            if dep_time_str:
                                try:
                                    dep_time = datetime.strptime(
                                        dep_time_str, "%d-%b-%Y %I:%M:%S %p"
                                    ).isoformat()
                                except ValueError:
                                    logger.warning(f"Invalid departure time format: {dep_time_str}")

                            # Safely handle potentially None values
                            pickup_val = stop.get("PICKUP", "") or ""
                            dropoff_val = stop.get("DROPOFF", "") or ""
                            departed_val = stop.get("DEPARTED", "") or ""
                            status_val = stop.get("STOP_STATUS", "") or ""

                            # Handle station code - can be None/null from API
                            station_code = stop.get("STATION_2CHAR")
                            if station_code == "":
                                station_code = None

                            stops.append(
                                {
                                    "station_code": station_code,
                                    "station_name": stop.get("STATIONNAME", ""),
                                    "scheduled_time": stop_time,
                                    "departure_time": dep_time,
                                    "pickup_only": pickup_val.strip() == "Pick Up Only",
                                    "dropoff_only": dropoff_val.strip() == "Drop Off Only",
                                    "departed": departed_val.strip() == "YES",
                                    "stop_status": status_val.strip(),
                                }
                            )

                # Extract train record
                processed_data.append(
                    {
                        "timestamp": timestamp,
                        "train_id": item.get("TRAIN_ID", ""),
                        "origin_station_code": self.station_code,
                        "origin_station_name": self.station_name,
                        "destination": clean_destination(item.get("DESTINATION", "")),
                        "track": item.get("TRACK", ""),
                        "departure_time": departure_time,
                        "status": item.get("STATUS", "").strip(),
                        "line": item.get("LINE", ""),
                        "line_code": item.get("LINECODE", ""),
                        "last_modified": item.get("LAST_MODIFIED", ""),
                        "stops": stops,
                    }
                )

            # Save processed data to CSV for easy inspection
            self._save_to_csv(processed_data, timestamp)

            logger.info(f"Processed {len(processed_data)} train records successfully")
            return processed_data

        except (KeyError, TypeError) as e:
            error_msg = f"Invalid data format: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _save_to_csv(self, data: List[Dict[str, Any]], timestamp: str) -> None:
        """
        Save processed data to CSV file.

        Args:
            data: List of processed train records
            timestamp: Collection timestamp
        """
        # Format timestamp for filename
        file_timestamp = timestamp.replace(":", "-").replace(".", "-")
        filename = self.processed_dir / f"trains_{file_timestamp}.csv"

        fieldnames = [
            "Timestamp",
            "Train_ID",
            "Origin_Station_Code",
            "Origin_Station_Name",
            "Destination",
            "Track",
            "Departure_Time",
            "Status",
            "Line",
            "Line_Code",
            "Last_Modified",
        ]

        with open(filename, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in data:
                writer.writerow(
                    {
                        "Timestamp": item["timestamp"],
                        "Train_ID": item["train_id"],
                        "Origin_Station_Code": item["origin_station_code"],
                        "Origin_Station_Name": item["origin_station_name"],
                        "Destination": item["destination"],
                        "Track": item["track"],
                        "Departure_Time": item["departure_time"],
                        "Status": item["status"],
                        "Line": item["line"],
                        "Line_Code": item["line_code"],
                        "Last_Modified": item["last_modified"],
                    }
                )

            logger.debug(f"Saved processed data to {filename}")


class AmtrakCollector(BaseCollector):
    """Collector for Amtrak real-time train tracking API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        retry_attempts: Optional[int] = None,
        timeout: Optional[int] = None,
        data_dir: Optional[str] = None,
        debug_mode: Optional[bool] = None,
    ):
        """
        Initialize Amtrak API collector.

        Args:
            base_url: Base API URL (defaults to config value)
            retry_attempts: Number of retry attempts for API calls
            timeout: Timeout in seconds for API calls
            data_dir: Directory to store raw and processed data
            debug_mode: Whether to save all raw API responses for debugging
        """
        self.base_url = base_url or settings.amtrak_api.base_url
        self.retry_attempts = retry_attempts or settings.amtrak_api.retry_attempts or 3
        self.timeout = timeout or settings.amtrak_api.timeout_seconds or 15
        self.debug_mode = debug_mode or settings.amtrak_api.debug_mode or False

        # Set up data directories
        self.data_dir = Path(data_dir or "data")
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.debug_dir = self.data_dir / "debug"

        # Create directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        if self.debug_mode:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        if not self.base_url:
            raise ValueError("Amtrak API base URL is required")

    def _archive_response(self, response: requests.Response, endpoint_name: str) -> None:
        """
        Archive raw API response to a file for debugging purposes.

        Args:
            response: API response
            endpoint_name: Name of the API endpoint for the filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.debug_dir / f"{endpoint_name}_{timestamp}.json"

        try:
            with open(filename, "w") as file:
                json.dump(response.json(), file, indent=2)
            logger.debug(f"Archived response to {filename}")
        except Exception as e:
            logger.warning(f"Failed to archive response: {str(e)}")

    def collect(self) -> Dict[str, Any]:
        """
        Collect data from Amtrak API.

        Returns:
            Dict containing the API response data and collection timestamp

        Raises:
            APIError: If the API request fails after all retry attempts
        """
        collection_time = datetime.now()
        attempts = 0
        last_error = None

        while attempts < self.retry_attempts:
            try:
                logger.debug(
                    f"Fetching Amtrak train data from {self.base_url} (attempt {attempts+1}/{self.retry_attempts})"
                )
                response = requests.get(self.base_url, timeout=self.timeout)
                response.raise_for_status()

                # Archive raw response if debug mode is enabled
                if self.debug_mode:
                    self._archive_response(response, "amtrak_trains")

                # Parse JSON response
                raw_data = response.json()

                # Save raw data to file for audit purposes
                timestamp = collection_time.strftime("%Y%m%d%H%M%S")
                raw_file = self.raw_dir / f"amtrak_{timestamp}.json"

                with open(raw_file, "w") as f:
                    json.dump(raw_data, f, indent=2)
                    logger.debug(f"Saved raw Amtrak data to {raw_file}")

                return {"data": raw_data, "timestamp": collection_time.isoformat()}

            except requests.RequestException as e:
                attempts += 1
                last_error = e
                logger.warning(
                    f"Amtrak API request failed, attempt {attempts}/{self.retry_attempts}: {str(e)}"
                )

                if attempts < self.retry_attempts:
                    time.sleep(2)  # Wait before retry

        # If we reach here, all attempts failed
        error_msg = f"Failed to collect Amtrak data after {self.retry_attempts} attempts"
        if last_error:
            error_msg += f": {str(last_error)}"

        logger.error(error_msg)
        raise APIError(error_msg)

    def process(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process Amtrak API data into structured format compatible with Train model.

        Args:
            raw_data: Dictionary containing the raw API response

        Returns:
            List of processed train records

        Raises:
            ValueError: If the data format is invalid or cannot be processed
        """
        processed_data = []

        try:
            timestamp = raw_data["timestamp"]
            trains_data = raw_data["data"]

            # Debug: Log data structure
            logger.info(f"Raw data keys: {list(raw_data.keys())}")
            logger.info(f"Data type: {type(trains_data)}")

            # Amtrak API returns {trainNumber: [trainData]} structure, not [trainData]
            all_trains = []
            if isinstance(trains_data, dict):
                logger.info(f"Found {len(trains_data)} train numbers in response")
                for train_num, train_list in trains_data.items():
                    if isinstance(train_list, list) and len(train_list) > 0:
                        # Each train number has a list, usually with one train object
                        all_trains.extend(train_list)
                    else:
                        logger.warning(
                            f"Unexpected structure for train {train_num}: {type(train_list)}"
                        )
            else:
                logger.error(f"Expected dict structure but got {type(trains_data)}")
                return []

            logger.info(f"Processing {len(all_trains)} Amtrak train records")

            # Debug: Log the first train structure
            if all_trains and len(all_trains) > 0:
                sample_train = all_trains[0]
                logger.info(
                    f"Sample train structure: trainNum={sample_train.get('trainNum')}, "
                    f"stations_count={len(sample_train.get('stations', []))}"
                )

            for train in all_trains:
                # Skip if train is not a dictionary
                if not isinstance(train, dict):
                    logger.warning(f"Skipping non-dict train record: {type(train)}")
                    continue

                # Skip trains that don't have stations data
                if not train.get("stations") or not isinstance(train["stations"], list):
                    continue

                # Find the origin station from the stations array (first station)
                origin_station = None
                stations_with_platform = []

                for station in train["stations"]:
                    # Skip if station is not a dictionary
                    if not isinstance(station, dict):
                        logger.warning(f"Skipping non-dict station record: {type(station)}")
                        continue
                    if origin_station is None:
                        origin_station = station

                    # Map station info to NJ Transit format
                    mapped_code, mapped_name = self._map_station_info(
                        station.get("code", ""), station.get("name", "")
                    )

                    # Extract timing for TrainStop records
                    stop_data = {
                        "station_code": mapped_code,
                        "station_name": mapped_name,
                        "scheduled_time": self._parse_datetime(station.get("schArr"))
                        or self._parse_datetime(station.get("schDep")),
                        "departure_time": self._parse_datetime(station.get("dep")),
                        "pickup_only": False,  # Amtrak doesn't distinguish pickup/dropoff
                        "dropoff_only": False,
                        "departed": station.get("status") == "Departed",
                        "stop_status": station.get("status", ""),
                    }
                    stations_with_platform.append(stop_data)

                if not origin_station:
                    logger.warning(
                        f"Skipping train {train.get('trainNum')} - no origin station found"
                    )
                    continue

                # Calculate departure time from origin station
                departure_time = self._parse_datetime(origin_station.get("schDep"))
                if not departure_time:
                    logger.warning(
                        f"Skipping train {train.get('trainNum')} - no valid departure time"
                    )
                    continue

                # Map train status from Amtrak to our format
                train_state = train.get("trainState", "")
                status = self._map_train_status(train_state)

                # Get track/platform from origin station
                track = origin_station.get("platform")

                # Map origin station info to NJ Transit format
                origin_code, origin_name = self._map_station_info(
                    origin_station.get("code", ""), origin_station.get("name", "")
                )

                # Map destination to NJ Transit format
                dest_code, dest_name = self._map_station_info(
                    train.get("destCode", ""), train.get("destName", "")
                )

                # Calculate delay if available
                scheduled_dep = self._parse_datetime(origin_station.get("schDep"))
                actual_dep = self._parse_datetime(origin_station.get("dep"))
                delay_minutes = None
                if scheduled_dep and actual_dep:
                    delay_seconds = (actual_dep - scheduled_dep).total_seconds()
                    delay_minutes = int(delay_seconds / 60) if delay_seconds > 0 else 0

                # Extract train record
                train_num = train.get("trainNum", "")
                train_id = f"A{train_num}" if train_num else ""
                logger.debug(f"Amtrak train {train_num} mapped to ID: {train_id}")

                processed_data.append(
                    {
                        "timestamp": timestamp,
                        "train_id": train_id,
                        "origin_station_code": origin_code,
                        "origin_station_name": origin_name,
                        "destination": clean_destination(dest_name),
                        "track": track,
                        "departure_time": departure_time.isoformat() if departure_time else None,
                        "status": status,
                        "line": train.get("routeName", ""),
                        "line_code": train.get("routeCode", ""),
                        "data_source": "amtrak",
                        "delay_minutes": delay_minutes,
                        "stops": stations_with_platform,
                    }
                )

            # Save processed data to CSV for easy inspection
            self._save_to_csv(processed_data, timestamp)

            logger.info(f"Processed {len(processed_data)} Amtrak train records successfully")
            return processed_data

        except (KeyError, TypeError) as e:
            error_msg = f"Invalid Amtrak data format: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string from Amtrak API format and convert to Eastern time.

        Args:
            datetime_str: ISO format datetime string from API (usually UTC)

        Returns:
            Parsed datetime object in Eastern timezone (naive), or None if invalid
        """
        if not datetime_str:
            return None

        # Use the new timezone-aware parsing utility
        return parse_iso_datetime_to_eastern(datetime_str)

    def _map_train_status(self, train_state: str) -> str:
        """
        Map Amtrak trainState to TrackCast status format.

        Args:
            train_state: Amtrak train state

        Returns:
            Mapped status string
        """
        status_mapping = {
            "Active": "EN ROUTE",
            "Predeparture": "BOARDING",
            "Station": "BOARDING",
            "Terminated": "DEPARTED",
        }
        return status_mapping.get(train_state, "UNKNOWN")

    def _map_station_info(self, amtrak_code: str, amtrak_name: str) -> tuple[str, str]:
        """
        Map Amtrak station codes and names to NJ Transit equivalents.

        Args:
            amtrak_code: Amtrak station code
            amtrak_name: Amtrak station name

        Returns:
            Tuple of (mapped_code, mapped_name)
        """
        # Station code mappings
        code_mapping = {
            "NYP": "NY",
            "NYK": "NY",  # Sometimes Amtrak uses NYK for NY Penn
            "TRE": "TR",
            "PJC": "PJ",
            "MET": "MP",
            "NWK": "NP",
            "EWR": "EWR",  # Newark Airport - keep same
        }

        # Station name mappings (partial matching for flexibility)
        name_mapping = {
            "New York Penn": "New York Penn Station",
            "New York": "New York Penn Station",
            "Penn Station": "New York Penn Station",
            "Trenton": "Trenton Transit Center",
            "Princeton Junction": "Princeton Junction",
            "Metropark": "Metropark",
            "Newark Penn": "Newark Penn Station",
            "Newark": "Newark Penn Station",
        }

        # Map station code
        mapped_code = code_mapping.get(amtrak_code, amtrak_code)

        # Map station name - check for partial matches
        mapped_name = amtrak_name
        for amtrak_pattern, nj_name in name_mapping.items():
            if amtrak_pattern.lower() in amtrak_name.lower():
                mapped_name = nj_name
                break

        return mapped_code, mapped_name

    def _save_to_csv(self, data: List[Dict[str, Any]], timestamp: str) -> None:
        """
        Save processed Amtrak data to CSV file.

        Args:
            data: List of processed train records
            timestamp: Collection timestamp
        """
        # Format timestamp for filename
        file_timestamp = timestamp.replace(":", "-").replace(".", "-")
        filename = self.processed_dir / f"amtrak_trains_{file_timestamp}.csv"

        fieldnames = [
            "Timestamp",
            "Train_ID",
            "Origin_Station_Code",
            "Origin_Station_Name",
            "Destination",
            "Track",
            "Departure_Time",
            "Status",
            "Line",
            "Line_Code",
            "Data_Source",
            "Delay_Minutes",
        ]

        with open(filename, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in data:
                writer.writerow(
                    {
                        "Timestamp": item["timestamp"],
                        "Train_ID": item["train_id"],
                        "Origin_Station_Code": item["origin_station_code"],
                        "Origin_Station_Name": item["origin_station_name"],
                        "Destination": item["destination"],
                        "Track": item["track"],
                        "Departure_Time": item["departure_time"],
                        "Status": item["status"],
                        "Line": item["line"],
                        "Line_Code": item["line_code"],
                        "Data_Source": item["data_source"],
                        "Delay_Minutes": item["delay_minutes"],
                    }
                )

        logger.debug(f"Saved processed Amtrak data to {filename}")
