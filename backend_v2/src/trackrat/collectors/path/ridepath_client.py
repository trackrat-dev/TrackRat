"""
Native PATH RidePATH API client for TrackRat V2.

Fetches real-time arrival predictions from the official PATH API,
which provides data for all 13 stations (unlike Transiter which only
exposes terminus data).
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

import httpx
from pydantic import BaseModel
from structlog import get_logger

from trackrat.config.stations import PATH_RIDEPATH_API_TO_INTERNAL_MAP
from trackrat.utils.metrics import track_api_call
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Native PATH API URL
RIDEPATH_API_URL = "https://www.panynj.gov/bin/portauthority/ridepath.json"


class PathArrival(BaseModel):
    """Single arrival prediction from RidePATH API."""

    station_code: str  # Internal code (PJS, PGR, etc.)
    headsign: str  # "World Trade Center", "33rd Street", etc.
    direction: str  # "ToNY" or "ToNJ"
    minutes_away: int  # Parsed from "X min"
    arrival_time: datetime  # Computed: now + minutes_away
    line_color: str  # Hex color(s), e.g., "D93A30" or "4D92FB,FF9900"
    last_updated: datetime | None  # When PATH last updated this prediction


class RidePathClient:
    """Client for native PATH RidePATH API.

    This API provides real-time arrival predictions at ALL PATH stations,
    enabling intermediate stop tracking that Transiter doesn't support.
    """

    def __init__(self, timeout: float = 30.0):
        """Initialize the RidePATH client.

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = RIDEPATH_API_URL
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

        # Simple in-memory cache
        self._cache: list[PathArrival] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 30  # 30 second cache TTL

    @property
    def session(self) -> httpx.AsyncClient:
        """Get or create the HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": "TrackRat-V2/1.0",
                    "Accept": "application/json",
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
        if self._session:
            await self._session.aclose()
            self._session = None

    @track_api_call(api_name="path_ridepath", endpoint="all_arrivals")
    async def get_all_arrivals(self) -> list[PathArrival]:
        """Fetch arrivals from all PATH stations.

        Returns:
            List of PathArrival objects for all stations/directions
        """
        # Check cache first
        if self._is_cache_valid():
            logger.debug("returning_cached_ridepath_arrivals")
            return self._cache or []

        try:
            logger.debug("fetching_ridepath_arrivals", url=self.base_url)

            response = await self.session.get(self.base_url)
            response.raise_for_status()

            data = response.json()
            arrivals = self._parse_response(data)

            # Update cache
            self._cache = arrivals
            self._cache_time = datetime.now()

            logger.debug(
                "ridepath_arrivals_fetched",
                arrival_count=len(arrivals),
                stations=len({a.station_code for a in arrivals}),
            )

            return arrivals

        except httpx.HTTPStatusError as e:
            logger.error(
                "ridepath_api_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "ridepath_api_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _parse_response(self, data: dict[str, Any]) -> list[PathArrival]:
        """Parse the RidePATH API response into PathArrival objects.

        Args:
            data: Raw JSON response from the API

        Returns:
            List of parsed PathArrival objects
        """
        arrivals: list[PathArrival] = []
        now = now_et()

        for result in data.get("results", []):
            api_station_code = result.get("consideredStation")
            station_code = PATH_RIDEPATH_API_TO_INTERNAL_MAP.get(api_station_code)

            if not station_code:
                logger.warning(
                    "unknown_path_station_code",
                    api_code=api_station_code,
                )
                continue

            for dest_group in result.get("destinations", []):
                direction = dest_group.get("label", "")

                for msg in dest_group.get("messages", []):
                    arrival = self._parse_arrival_message(
                        station_code=station_code,
                        direction=direction,
                        msg=msg,
                        now=now,
                    )
                    if arrival:
                        arrivals.append(arrival)

        return arrivals

    def _parse_arrival_message(
        self,
        station_code: str,
        direction: str,
        msg: dict[str, Any],
        now: datetime,
    ) -> PathArrival | None:
        """Parse a single arrival message.

        Args:
            station_code: Internal station code
            direction: Direction label (ToNY, ToNJ)
            msg: Raw message data
            now: Current time for computing arrival_time

        Returns:
            PathArrival if parseable, None otherwise
        """
        try:
            # Parse minutes from "14 min" format
            arr_msg = msg.get("arrivalTimeMessage", "")
            minutes = self._parse_minutes(arr_msg)

            if minutes is None:
                return None

            # Parse last_updated timestamp
            last_updated = self._parse_timestamp(msg.get("lastUpdated"))

            return PathArrival(
                station_code=station_code,
                headsign=msg.get("headSign", "Unknown"),
                direction=direction,
                minutes_away=minutes,
                arrival_time=now + timedelta(minutes=minutes),
                line_color=msg.get("lineColor", ""),
                last_updated=last_updated,
            )
        except Exception as e:
            logger.warning(
                "failed_to_parse_path_arrival",
                error=str(e),
                station=station_code,
                msg=msg,
            )
            return None

    def _parse_minutes(self, msg: str) -> int | None:
        """Parse arrival time message to minutes.

        Args:
            msg: Message like "14 min", "1 min", "Arriving"

        Returns:
            Minutes as int, or None if unparseable
        """
        if not msg:
            return None

        msg_lower = msg.lower().strip()

        # Handle "Arriving" or similar
        if "arriving" in msg_lower or "now" in msg_lower:
            return 0

        # Handle "X min" format
        if "min" in msg_lower:
            try:
                # Extract number before "min"
                parts = msg_lower.replace("min", "").strip()
                return int(parts)
            except ValueError:
                pass

        return None

    def _parse_timestamp(self, ts_str: str | None) -> datetime | None:
        """Parse ISO timestamp string.

        Args:
            ts_str: ISO format timestamp string

        Returns:
            Parsed datetime or None
        """
        if not ts_str:
            return None

        try:
            # Handle format: "2026-01-19T07:36:57.674251-05:00"
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid.

        Returns:
            True if cache exists and is not expired
        """
        if self._cache is None or self._cache_time is None:
            return False

        age = datetime.now() - self._cache_time
        return age < timedelta(seconds=self._cache_ttl)

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache = None
        self._cache_time = None
        logger.debug("ridepath_cache_cleared")
