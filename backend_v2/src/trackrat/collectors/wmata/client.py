"""
WMATA (Washington DC Metro) API client.

Fetches real-time train predictions, positions, and service incidents
from the official WMATA developer API.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

import httpx
from pydantic import BaseModel
from structlog import get_logger

from trackrat.config.stations.wmata import WMATA_STATION_NAMES, map_wmata_api_stop
from trackrat.utils.metrics import track_api_call
from trackrat.utils.time import ET, now_et

logger = get_logger(__name__)

# WMATA API base URL
WMATA_API_BASE = "https://api.wmata.com"


class WMATAPrediction(BaseModel):
    """Single arrival prediction from WMATA GetPrediction API."""

    location_code: str  # Station code where prediction applies (e.g., "A01")
    location_name: str  # Station name
    destination_code: str | None  # Destination station code (can be None)
    destination_name: str  # Abbreviated destination (e.g., "Shady Gr")
    line: str  # Line code: RD, BL, OR, SV, YL, GR
    minutes: int | None  # Minutes to arrival (None for ARR/BRD/---)
    is_arriving: bool  # True when Min == "ARR"
    is_boarding: bool  # True when Min == "BRD"
    car_count: int | None  # Number of cars (6 or 8, None if unknown)
    group: str  # Track/platform group indicator ("1" or "2")


class WMATATrainPosition(BaseModel):
    """Real-time train position from WMATA TrainPositions API."""

    train_id: str  # WMATA train ID (can be empty)
    train_number: str  # Train number
    car_count: int
    direction_num: int  # 1 or 2
    circuit_id: int  # Track circuit ID
    destination_code: str | None
    line_code: str | None  # RD, BL, OR, SV, YL, GR (None for out-of-service)
    seconds_at_location: int
    service_type: str  # "Normal", "NoPassengers", "Special", "Unknown"


class WMATAIncident(BaseModel):
    """Rail service incident from WMATA Incidents API."""

    incident_id: str
    description: str
    incident_type: str  # "Delay", "Alert", etc.
    lines_affected: list[str]  # Parsed from semicolon-separated string
    date_updated: datetime | None


class WMATAClient:
    """Client for WMATA developer API.

    Provides access to real-time predictions, train positions, and service
    incidents for the Washington DC Metrorail system.
    """

    def __init__(self, api_key: str, timeout: float = 30.0):
        """Initialize the WMATA client.

        Args:
            api_key: WMATA developer API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

        # Simple in-memory cache for predictions
        self._pred_cache: list[WMATAPrediction] | None = None
        self._pred_cache_time: datetime | None = None
        self._pred_cache_ttl = 20  # WMATA updates every 20-30s

        # Cache for train positions
        self._pos_cache: list[WMATATrainPosition] | None = None
        self._pos_cache_time: datetime | None = None
        self._pos_cache_ttl = 20

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create the HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": "TrackRat-V2/1.0",
                    "Accept": "application/json",
                    "api_key": self.api_key,
                },
            )
        return self._session

    async def __aenter__(self) -> "Self":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    @track_api_call("wmata_predictions")
    async def get_all_predictions(self) -> list[WMATAPrediction]:
        """Fetch arrival predictions for all stations in a single API call.

        Returns:
            List of WMATAPrediction objects
        """
        now = now_et()

        # Check cache
        if (
            self._pred_cache is not None
            and self._pred_cache_time is not None
            and (now - self._pred_cache_time).total_seconds() < self._pred_cache_ttl
        ):
            return self._pred_cache

        url = f"{WMATA_API_BASE}/StationPrediction.svc/json/GetPrediction/All"
        response = await self.session.get(url)
        response.raise_for_status()
        data = response.json()

        predictions = []
        for train in data.get("Trains", []):
            prediction = self._parse_prediction(train)
            if prediction is not None:
                predictions.append(prediction)

        self._pred_cache = predictions
        self._pred_cache_time = now

        logger.debug(
            "wmata_predictions_fetched",
            count=len(predictions),
        )
        return predictions

    @track_api_call("wmata_positions")
    async def get_train_positions(self) -> list[WMATATrainPosition]:
        """Fetch real-time positions for all trains.

        Returns:
            List of WMATATrainPosition objects
        """
        now = now_et()

        # Check cache
        if (
            self._pos_cache is not None
            and self._pos_cache_time is not None
            and (now - self._pos_cache_time).total_seconds() < self._pos_cache_ttl
        ):
            return self._pos_cache

        url = f"{WMATA_API_BASE}/TrainPositions/TrainPositions"
        response = await self.session.get(url, params={"contentType": "json"})
        response.raise_for_status()
        data = response.json()

        positions = []
        for pos in data.get("TrainPositions", []):
            position = self._parse_position(pos)
            if position is not None:
                positions.append(position)

        self._pos_cache = positions
        self._pos_cache_time = now

        logger.debug(
            "wmata_positions_fetched",
            count=len(positions),
        )
        return positions

    @track_api_call("wmata_incidents")
    async def get_incidents(self) -> list[WMATAIncident]:
        """Fetch current rail service incidents.

        Returns:
            List of WMATAIncident objects
        """
        url = f"{WMATA_API_BASE}/Incidents.svc/json/Incidents"
        response = await self.session.get(url)
        response.raise_for_status()
        data = response.json()

        incidents = []
        for inc in data.get("Incidents", []):
            incident = self._parse_incident(inc)
            if incident is not None:
                incidents.append(incident)

        logger.debug(
            "wmata_incidents_fetched",
            count=len(incidents),
        )
        return incidents

    def _parse_prediction(self, train: dict) -> WMATAPrediction | None:
        """Parse a single prediction from the API response."""
        location_code = train.get("LocationCode", "")
        line = train.get("Line", "")
        destination_name = train.get("Destination", "")

        # Skip entries with no useful data
        if not location_code or not line or line == "--":
            return None

        # Skip "No Passenger" and "Train" (generic non-revenue) trains
        if destination_name in ("No Passenger", "Train", ""):
            return None

        # Skip if station code is not recognized
        if not map_wmata_api_stop(location_code):
            return None

        # Parse minutes
        min_str = train.get("Min", "")
        minutes: int | None = None
        is_arriving = False
        is_boarding = False

        if min_str == "ARR":
            is_arriving = True
            minutes = 0
        elif min_str == "BRD":
            is_boarding = True
            minutes = 0
        elif min_str and min_str not in ("---", "", "--"):
            try:
                minutes = int(min_str)
            except ValueError:
                return None

        # Parse car count
        car_str = train.get("Car", "")
        car_count: int | None = None
        if car_str and car_str not in ("-", ""):
            try:
                car_count = int(car_str)
            except ValueError:
                pass

        return WMATAPrediction(
            location_code=location_code,
            location_name=train.get("LocationName", WMATA_STATION_NAMES.get(location_code, location_code)),
            destination_code=train.get("DestinationCode") or None,
            destination_name=destination_name,
            line=line,
            minutes=minutes,
            is_arriving=is_arriving,
            is_boarding=is_boarding,
            car_count=car_count,
            group=train.get("Group", "1"),
        )

    def _parse_position(self, pos: dict) -> WMATATrainPosition | None:
        """Parse a single train position from the API response."""
        train_id = pos.get("TrainId", "")
        service_type = pos.get("ServiceType", "Unknown")

        # Skip non-revenue trains
        if service_type == "NoPassengers":
            return None

        line_code = pos.get("LineCode") or None
        if not line_code:
            return None

        return WMATATrainPosition(
            train_id=train_id or "",
            train_number=pos.get("TrainNumber", ""),
            car_count=pos.get("CarCount", 0),
            direction_num=pos.get("DirectionNum", 0),
            circuit_id=pos.get("CircuitId", 0),
            destination_code=pos.get("DestinationStationCode") or None,
            line_code=line_code,
            seconds_at_location=pos.get("SecondsAtLocation", 0),
            service_type=service_type,
        )

    def _parse_incident(self, inc: dict) -> WMATAIncident | None:
        """Parse a single incident from the API response."""
        incident_id = inc.get("IncidentID", "")
        if not incident_id:
            return None

        # Parse LinesAffected: "RD; BL; " -> ["RD", "BL"]
        lines_str = inc.get("LinesAffected", "")
        lines = [
            line.strip()
            for line in lines_str.split(";")
            if line.strip()
        ]

        # Parse date
        date_str = inc.get("DateUpdated", "")
        date_updated: datetime | None = None
        if date_str:
            try:
                date_updated = datetime.fromisoformat(date_str).replace(tzinfo=ET)
            except (ValueError, TypeError):
                pass

        return WMATAIncident(
            incident_id=incident_id,
            description=inc.get("Description", ""),
            incident_type=inc.get("IncidentType", ""),
            lines_affected=lines,
            date_updated=date_updated,
        )
