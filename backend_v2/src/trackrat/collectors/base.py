"""
Base collector classes for TrackRat V2.

Provides abstract base classes for discovery and journey collectors
that can be implemented for different data sources (NJT, Amtrak, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

from trackrat.models.database import TrainJourney


class BaseDiscoveryCollector(ABC):
    """Abstract base class for train discovery collectors."""

    @abstractmethod
    async def discover_trains(self) -> list[str]:
        """Discover active trains.

        Returns:
            List of train IDs that are currently active
        """
        pass

    @abstractmethod
    async def run(self) -> dict[str, Any]:
        """Run the discovery collector with a database session.

        Returns:
            Collection results summary
        """
        pass


class BaseJourneyCollector(ABC):
    """Abstract base class for journey collectors."""

    @abstractmethod
    async def collect_journey(self, train_id: str) -> TrainJourney | None:
        """Collect journey details for a specific train.

        Args:
            train_id: The train ID to collect journey details for

        Returns:
            TrainJourney object if successful, None if failed
        """
        pass

    @abstractmethod
    async def run(self) -> dict[str, Any]:
        """Run the journey collector for all discovered trains.

        Returns:
            Collection results summary
        """
        pass


class BaseClient(ABC):
    """Abstract base class for API clients."""

    @abstractmethod
    async def get_train_data(self, *args: Any, **kwargs: Any) -> Any:
        """Get train data from the API.

        Returns:
            Raw API response data
        """
        pass
