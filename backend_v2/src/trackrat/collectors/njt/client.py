"""
NJ Transit API client for TrackRat V2.

Handles all communication with NJ Transit's rail data API.
"""

from typing import Any

import httpx
from structlog import get_logger

from trackrat.models.api import NJTransitTrainData
from trackrat.settings import Settings, get_settings
from trackrat.utils.metrics import track_api_call

logger = get_logger(__name__)


class NJTransitAPIError(Exception):
    """Exception raised when NJ Transit API calls fail."""

    pass


class TrainNotFoundError(NJTransitAPIError):
    """Exception raised when train data is not available from NJ Transit API."""

    pass


class NJTransitClient:
    """Async client for NJ Transit rail data API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the client."""
        self.settings: Settings | None = settings or get_settings()
        self.base_url = self.settings.njt_api_url.rstrip("/")
        self.token = self.settings.njt_api_token
        self._init_http_client()

    def _init_http_client(self) -> None:
        """Create long-lived HTTP client with connection pooling and retries."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(
                retries=3,  # Built-in retry handling
                verify=True,
            ),
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
            ),
        )

    @classmethod
    def from_token(
        cls, token: str, base_url: str = "https://raildata.njtransit.com/api"
    ) -> "NJTransitClient":
        """Create a lightweight client without requiring full backend Settings.

        Useful for standalone scripts that only need the NJT API.
        """
        instance = object.__new__(cls)
        instance.settings = None
        instance.base_url = base_url
        instance.token = token
        instance._init_http_client()
        return instance

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "NJTransitClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def _make_request(
        self, endpoint: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a request to the NJ Transit API.

        Args:
            endpoint: API endpoint path
            data: Form data to send

        Returns:
            JSON response data

        Raises:
            NJTransitAPIError: If the request fails
        """
        url = f"{self.base_url}/{endpoint}"
        data["token"] = self.token

        try:
            logger.debug(
                "making_njt_api_request",
                endpoint=endpoint,
                data_keys=list(data.keys()),
            )

            response = await self._client.post(
                url, data=data, headers={"accept": "application/json"}
            )

            response.raise_for_status()

            # NJ Transit API returns JSON
            result = response.json()

            logger.debug(
                "njt_api_request_success",
                endpoint=endpoint,
                response_size=len(response.text),
            )

            return result  # type: ignore[no-any-return]

        except httpx.HTTPStatusError as e:
            logger.error(
                "njt_api_http_error",
                endpoint=endpoint,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise NJTransitAPIError(
                f"HTTP {e.response.status_code} from {endpoint}: {e.response.text}"
            ) from e

        except Exception as e:
            logger.error(
                "njt_api_request_failed",
                endpoint=endpoint,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise NJTransitAPIError(f"Failed to call {endpoint}: {str(e)}") from e

    @track_api_call(api_name="njtransit", endpoint="train_schedule_with_stops")
    async def get_train_schedule_with_stops(self, station_code: str) -> dict[str, Any]:
        """Get train schedule for a station WITH embedded stop data.

        This uses getTrainSchedule (not getTrainSchedule19Rec) which includes
        a STOPS array for each train with complete journey information.

        Args:
            station_code: Two-character station code (e.g., "NY", "NP")

        Returns:
            Full response dict with ITEMS containing trains with STOPS data
        """
        logger.info(
            "API QUERY: getting train schedule with embedded stops using getTrainSchedule",
            station_code=station_code,
        )

        response = await self._make_request(
            "TrainData/getTrainSchedule", {"station": station_code}
        )

        # Handle None/empty response (some low-traffic stations have no trains at times)
        if response is None:
            logger.debug(
                "train_schedule_empty_response",
                station_code=station_code,
            )
            return {"ITEMS": []}

        # Log response structure for debugging
        logger.debug(
            "train_schedule_with_stops_response",
            station_code=station_code,
            response_type=type(response).__name__,
            response_keys=list(response.keys()) if isinstance(response, dict) else None,
            items_count=(
                len(response.get("ITEMS") or []) if isinstance(response, dict) else None
            ),
        )

        # Log sample stop data if available
        if (
            isinstance(response, dict)
            and response.get("ITEMS")
            and len(response["ITEMS"]) > 0
            and "STOPS" in response["ITEMS"][0]
        ):
            sample_train = response["ITEMS"][0]
            stops_count = len(sample_train.get("STOPS", []))
            logger.debug(
                "train_schedule_stops_sample",
                station_code=station_code,
                train_id=sample_train.get("TRAIN_ID"),
                stops_count=stops_count,
                has_stops_data=stops_count > 0,
            )

        return response

    @track_api_call(api_name="njtransit", endpoint="train_stop_list")
    async def get_train_stop_list(self, train_id: str) -> NJTransitTrainData:
        """Get detailed stop list for a specific train.

        This is the primary data collection method in V2.

        Args:
            train_id: Train ID (e.g., "3840")

        Returns:
            Parsed train data with all stops

        Raises:
            NJTransitAPIError: If the request fails or data is invalid
        """
        logger.info(
            "API QUERY: getting train stop list with getTrainStopList",
            train_id=train_id,
        )

        response = await self._make_request(
            "TrainData/getTrainStopList", {"train": train_id}
        )

        # Validate response is not None or empty
        if response is None:
            logger.warning(
                "train_not_found_none_response",
                train_id=train_id,
            )
            raise TrainNotFoundError(f"Train {train_id} not found - API returned None")

        if not isinstance(response, dict):
            logger.error(
                "invalid_response_type",
                train_id=train_id,
                response_type=type(response).__name__,
                response_content=str(response)[:200] if response else None,
            )
            raise NJTransitAPIError(
                f"Expected dict response for train {train_id}, got {type(response).__name__}"
            )

        # Check for empty response or missing required fields
        if not response:
            logger.warning(
                "train_not_found_empty_response",
                train_id=train_id,
            )
            raise TrainNotFoundError(
                f"Train {train_id} not found - API returned empty response"
            )

        # Check if all required fields are None (train no longer exists)
        required_fields = ["TRAIN_ID", "LINECODE", "BACKCOLOR", "DESTINATION"]
        if all(response.get(field) is None for field in required_fields):
            logger.warning(
                "train_not_found_all_fields_none",
                train_id=train_id,
                response_keys=list(response.keys()),
            )
            raise TrainNotFoundError(
                f"Train {train_id} not found - API returned null data"
            )

        # Validate and parse response
        try:
            # The response should match our NJTransitTrainData model
            train_data = NJTransitTrainData(**response)

            logger.debug(
                "train_stop_list_retrieved",
                train_id=train_id,
                destination=train_data.DESTINATION,
                stops_count=len(train_data.STOPS),
            )

            return train_data

        except Exception as e:
            logger.error(
                "failed_to_parse_train_data",
                train_id=train_id,
                error=str(e),
                error_type=type(e).__name__,
                response_keys=(
                    list(response.keys()) if isinstance(response, dict) else None
                ),
                response_sample=(
                    dict(list(response.items())[:5])
                    if isinstance(response, dict)
                    else str(response)[:200]
                ),
            )
            raise NJTransitAPIError(f"Invalid train data format: {str(e)}") from e

    @track_api_call(api_name="njtransit", endpoint="station_schedule")
    async def get_station_schedule(
        self, station_code: str | None = None, njt_only: bool = False
    ) -> list[dict[str, Any]]:
        """Get 27-hour schedule data for a station or all stations.

        This API has limited access (5 times per day) and should only be called
        once daily, ideally after 12:30 AM.

        Args:
            station_code: Two-character station code (e.g., "NY", "NP").
                         Pass None or empty string for all stations.
            njt_only: If True, return NJT trains only. If False, include Amtrak.

        Returns:
            List of station schedule dictionaries with train data

        Raises:
            NJTransitAPIError: If the request fails
        """
        logger.info(
            "API QUERY: getting station schedule using getStationSchedule",
            station_code=station_code or "ALL",
            njt_only=njt_only,
        )

        # Build request data
        data = {"NJTOnly": "true" if njt_only else "false"}
        if station_code:
            data["station"] = station_code
        else:
            # Empty string for all stations
            data["station"] = ""

        response = await self._make_request("TrainData/getStationSchedule", data)

        # The API returns a list of station dictionaries
        if not isinstance(response, list):
            logger.error(
                "invalid_schedule_response_type",
                response_type=type(response).__name__,
                station_code=station_code,
            )
            raise NJTransitAPIError(
                f"Expected list response for schedule, got {type(response).__name__}"
            )

        logger.info(
            "station_schedule_retrieved",
            station_count=len(response),
            station_code=station_code or "ALL",
        )

        return response
