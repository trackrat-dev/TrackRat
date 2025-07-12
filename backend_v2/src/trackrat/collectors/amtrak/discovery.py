"""
Amtrak train discovery collector for TrackRat V2.

Discovers active Amtrak trains that stop at New York Penn Station.
"""

from typing import Any

from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.models.api import AmtrakTrainData

logger = get_logger(__name__)


class AmtrakDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active Amtrak trains serving New York Penn Station."""

    def __init__(self) -> None:
        """Initialize the Amtrak discovery collector."""
        self.client = AmtrakClient()

    async def discover_trains(self) -> list[str]:
        """Discover all Amtrak trains that stop at NYP.

        Returns:
            List of Amtrak train IDs (e.g., ["2150-4", "141-4"])
        """
        try:
            # Get all trains from API (will use cache if available)
            all_trains = await self.client.get_all_trains()

            discovered_train_ids = []

            # Check each train to see if it stops at NYP
            for train_list in all_trains.values():
                for train in train_list:
                    if self._stops_at_nyp(train):
                        discovered_train_ids.append(train.trainID)
                        logger.debug(
                            "discovered_amtrak_train",
                            train_id=train.trainID,
                            train_num=train.trainNum,
                            route=train.routeName,
                        )

            logger.info(
                "amtrak_discovery_complete", discovered_count=len(discovered_train_ids)
            )

            return discovered_train_ids

        except Exception as e:
            logger.error(
                "amtrak_discovery_failed", error=str(e), error_type=type(e).__name__
            )
            return []

    async def run(self) -> dict[str, Any]:
        """Run the discovery collector with a database session.

        Returns:
            Collection results summary
        """
        async with self.client:
            train_ids = await self.discover_trains()

        return {
            "discovered_trains": len(train_ids),
            "train_ids": train_ids,
            "data_source": "AMTRAK",
        }

    def _stops_at_nyp(self, train: AmtrakTrainData) -> bool:
        """Check if a train stops at New York Penn Station.

        Args:
            train: Amtrak train data

        Returns:
            True if the train has NYP as one of its stops
        """
        for station in train.stations:
            if station.code == "NYP":
                return True
        return False
