"""
Amtrak train discovery collector for TrackRat V2.

Discovers active Amtrak trains that stop at major network hubs.
"""

from typing import Any

from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.models.api import AmtrakTrainData

logger = get_logger(__name__)

# Major hubs for Amtrak discovery - trains passing through any hub are tracked
DISCOVERY_HUBS = {
    # Eastern hubs (existing)
    "NYP",  # New York Penn Station
    "PHL",  # Philadelphia
    "WAS",  # Washington Union Station
    "BOS",  # Boston South Station
    "WIL",  # Wilmington
    "RVR",  # Richmond Staples Mill Road
    "CLT",  # Charlotte
    # Midwest hubs
    "CHI",  # Chicago Union Station - Empire Builder, Zephyr, Chief, etc.
    "STL",  # St. Louis - Texas Eagle, Missouri River Runner
    "MKE",  # Milwaukee - Empire Builder, Hiawatha
    # West Coast hubs
    "LAX",  # Los Angeles - Chief, Starlight, Sunset, Surfliner
    "SEA",  # Seattle - Empire Builder, Coast Starlight, Cascades
    "PDX",  # Portland - Empire Builder, Coast Starlight, Cascades
    "EMY",  # Emeryville/Oakland - Zephyr, Starlight, Capitol Corridor
    "SAC",  # Sacramento - Zephyr, Starlight, Capitol Corridor
    # Southern/Southwest hubs
    "NOL",  # New Orleans - Sunset Limited, City of New Orleans, Crescent
    "SAS",  # San Antonio - Texas Eagle, Sunset Limited
    "DEN",  # Denver - California Zephyr, Southwest Chief
}


class AmtrakDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active Amtrak trains serving major network hubs nationwide."""

    def __init__(self) -> None:
        """Initialize the Amtrak discovery collector."""
        self.client = AmtrakClient()

    async def discover_trains(self) -> list[str]:
        """Discover all Amtrak trains that stop at major network hubs.

        Returns:
            List of Amtrak train IDs (e.g., ["2150-4", "141-4"])
        """
        try:
            # Get all trains from API (will use cache if available)
            all_trains = await self.client.get_all_trains()

            discovered_train_ids = []

            # Check each train to see if it stops at any discovery hub
            for train_list in all_trains.values():
                for train in train_list:
                    if self._stops_at_any_hub(train):
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

    def _stops_at_any_hub(self, train: AmtrakTrainData) -> bool:
        """Check if a train stops at any of the major network hubs.

        Args:
            train: Amtrak train data

        Returns:
            True if the train stops at any station in DISCOVERY_HUBS
        """
        train_stations = {station.code for station in train.stations}
        return bool(train_stations.intersection(DISCOVERY_HUBS))
