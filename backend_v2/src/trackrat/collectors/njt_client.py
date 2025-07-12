"""
NJ Transit API client for TrackRat V2.

Handles all communication with NJ Transit's rail data API.
"""

import asyncio
from typing import Any

import httpx
from structlog import get_logger

from trackrat.config import Settings, get_settings
from trackrat.models.api import NJTransitTrainData

logger = get_logger(__name__)


class NJTransitAPIError(Exception):
    """Exception raised when NJ Transit API calls fail."""

    pass


class NJTransitClient:
    """Async client for NJ Transit rail data API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the client."""
        self.settings = settings or get_settings()
        self.base_url = self.settings.njt_api_url.rstrip("/")
        self.token = self.settings.njt_api_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NJTransitClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),  # 30 second timeout
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    async def _make_request(
        self, endpoint: str, data: dict[str, Any], retry_count: int = 3
    ) -> dict[str, Any]:
        """Make a request to the NJ Transit API.

        Args:
            endpoint: API endpoint path
            data: Form data to send
            retry_count: Number of retries on failure

        Returns:
            JSON response data

        Raises:
            NJTransitAPIError: If the request fails
        """
        url = f"{self.base_url}/{endpoint}"
        data["token"] = self.token

        for attempt in range(retry_count):
            try:
                logger.info(
                    "making_njt_api_request",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    data_keys=list(data.keys()),
                )

                response = await self.client.post(
                    url, data=data, headers={"accept": "application/json"}
                )

                response.raise_for_status()

                # NJ Transit API returns JSON
                result = response.json()

                logger.info(
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
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt == retry_count - 1:
                    raise NJTransitAPIError(
                        f"HTTP {e.response.status_code} from {endpoint}: {e.response.text}"
                    ) from e

            except Exception as e:
                logger.error(
                    "njt_api_request_failed",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                if attempt == retry_count - 1:
                    raise NJTransitAPIError(
                        f"Failed to call {endpoint}: {str(e)}"
                    ) from e

            # Exponential backoff
            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        # This should never be reached due to exceptions, but satisfy type checker
        raise NJTransitAPIError(f"All retries exhausted for {endpoint}")

    async def get_train_schedule(self, station_code: str) -> list[dict[str, Any]]:
        """Get train schedule for a station.

        This is used for train discovery - finding which trains are active.

        Args:
            station_code: Two-character station code (e.g., "NY", "NP")

        Returns:
            List of train schedule data
        """
        logger.info("getting_train_schedule", station_code=station_code)

        response = await self._make_request(
            "TrainData/getTrainSchedule19Rec", {"station": station_code}
        )

        # Response should have a "STATION" key with station data
        # and train data in the response
        trains = []

        # The exact structure varies, but typically trains are in the root
        # or under a specific key. We'll need to adapt based on actual response.
        if isinstance(response, list):
            trains = response
        elif isinstance(response, dict):
            # Try common keys
            for key in ["TRAINS", "trains", "data"]:
                if key in response and isinstance(response[key], list):
                    trains = response[key]
                    break
            else:
                # If no known key, assume the whole response minus metadata
                trains = [
                    v
                    for k, v in response.items()
                    if isinstance(v, dict) and "TRAIN_ID" in v
                ]

        logger.info(
            "train_schedule_retrieved",
            station_code=station_code,
            train_count=len(trains),
        )

        return trains

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
        logger.info("getting_train_stop_list", train_id=train_id)

        response = await self._make_request(
            "TrainData/getTrainStopList", {"train": train_id}
        )

        # Validate and parse response
        try:
            # The response should match our NJTransitTrainData model
            train_data = NJTransitTrainData(**response)

            logger.info(
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
                response_keys=(
                    list(response.keys()) if isinstance(response, dict) else None
                ),
            )
            raise NJTransitAPIError(f"Invalid train data format: {str(e)}") from e


# Singleton instance management
_client_instance: NJTransitClient | None = None


async def get_njt_client() -> NJTransitClient:
    """Get or create the NJ Transit API client."""
    global _client_instance
    if _client_instance is None:
        _client_instance = NJTransitClient()
    return _client_instance
