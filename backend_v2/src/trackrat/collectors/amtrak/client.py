"""
Amtrak API client for TrackRat V2.

Handles communication with the Amtrak API (https://api-v3.amtraker.com).
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

import httpx
from structlog import get_logger

from trackrat.collectors.base import BaseClient
from trackrat.models.api import AmtrakTrainData
from trackrat.utils.metrics import track_api_call

logger = get_logger(__name__)


class AmtrakClient(BaseClient):
    """Client for interacting with the Amtrak API."""

    def __init__(self, timeout: float = 30.0):
        """Initialize the Amtrak client.

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = "https://api-v3.amtraker.com/v3/trains"
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

        # Simple in-memory cache
        self._cache: dict[str, Any] = {}
        self._cache_time: datetime | None = None
        self._cache_ttl = 60  # 1 minute cache TTL

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

    async def get_train_data(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, list[AmtrakTrainData]]:
        """Get all train data from Amtrak API.

        This method satisfies the BaseClient interface.

        Returns:
            Dictionary mapping train numbers to lists of train data
        """
        return await self.get_all_trains()  # type: ignore[no-any-return]

    @track_api_call(api_name="amtrak", endpoint="all_trains")
    async def get_all_trains(self) -> dict[str, list[AmtrakTrainData]]:
        """Fetch all active trains from Amtrak API.

        Returns:
            Dictionary mapping train numbers to lists of train data
        """
        # Check cache first
        if self._is_cache_valid():
            logger.debug("returning_cached_amtrak_data")
            return self._cache

        try:
            logger.info("fetching_amtrak_trains", url=self.base_url)

            response = await self.session.get(self.base_url)
            response.raise_for_status()

            raw_data = response.json()

            # Parse the response into our models
            parsed_data = {}
            for train_num, train_list in raw_data.items():
                if not isinstance(train_list, list):
                    continue

                parsed_trains = []
                for train_dict in train_list:
                    try:
                        train = AmtrakTrainData(**train_dict)
                        parsed_trains.append(train)
                    except Exception as e:
                        logger.warning(
                            "failed_to_parse_train", train_num=train_num, error=str(e)
                        )
                        continue

                if parsed_trains:
                    parsed_data[train_num] = parsed_trains

            # Update cache
            self._cache = parsed_data
            self._cache_time = datetime.now()

            logger.info(
                "amtrak_data_fetched",
                train_count=len(parsed_data),
                total_instances=sum(len(trains) for trains in parsed_data.values()),
            )

            return parsed_data

        except httpx.TimeoutException:
            logger.error("amtrak_api_timeout", timeout=self.timeout)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                "amtrak_api_http_error",
                status_code=e.response.status_code,
                response_text=e.response.text[:500],
            )
            raise
        except Exception as e:
            logger.error("amtrak_api_error", error=str(e), error_type=type(e).__name__)
            raise

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid.

        Returns:
            True if cache exists and is not expired
        """
        if not self._cache or not self._cache_time:
            return False

        age = datetime.now() - self._cache_time
        return age < timedelta(seconds=self._cache_ttl)

    def get_train_by_id(self, train_id: str) -> AmtrakTrainData | None:
        """Get a specific train by its ID from cached data.

        Args:
            train_id: Amtrak train ID (e.g., "2150-4")

        Returns:
            Train data if found, None otherwise
        """
        if not self._is_cache_valid():
            return None

        for train_list in self._cache.values():
            for train in train_list:
                if train.trainID == train_id:
                    return train  # type: ignore[no-any-return]

        return None

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
        self._cache_time = None
        logger.debug("amtrak_cache_cleared")
