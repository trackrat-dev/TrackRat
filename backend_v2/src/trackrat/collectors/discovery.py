"""
Train discovery collector for TrackRat V2.

Discovers active trains by polling station departure boards.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.db.engine import get_session
from trackrat.models.database import DiscoveryRun, TrainJourney
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class TrainDiscoveryCollector:
    """Discovers active trains from station schedules."""

    # Stations to poll for discovery - using major stations from config
    DISCOVERY_STATIONS = ["NY", "NP", "PJ", "TR", "LB", "PL", "DN"]

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the discovery collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def run(self) -> dict[str, Any]:
        """Run the collector with a database session.

        Returns:
            Collection results
        """
        async with get_session() as session:
            return await self.collect(session)

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Run discovery for all configured stations.

        Args:
            session: Database session

        Returns:
            Discovery results summary
        """
        logger.info("starting_train_discovery", stations=self.DISCOVERY_STATIONS)

        total_discovered = 0
        total_new = 0
        station_results = {}

        for station_code in self.DISCOVERY_STATIONS:
            result = await self.discover_station_trains(session, station_code)
            station_results[station_code] = result
            total_discovered += result["trains_discovered"]
            total_new += result["new_trains"]

        logger.info(
            "train_discovery_complete",
            total_discovered=total_discovered,
            total_new=total_new,
            stations_processed=len(self.DISCOVERY_STATIONS),
        )

        return {
            "stations_processed": len(self.DISCOVERY_STATIONS),
            "total_discovered": total_discovered,
            "total_new": total_new,
            "station_results": station_results,
        }

    async def discover_station_trains(
        self, session: AsyncSession, station_code: str
    ) -> dict[str, Any]:
        """Discover trains from a single station.

        Args:
            session: Database session
            station_code: Two-character station code

        Returns:
            Discovery results for this station
        """
        start_time = now_et()
        discovery_run = DiscoveryRun(station_code=station_code, run_at=start_time)

        try:
            # Get train schedule data
            trains_data = await self.njt_client.get_train_schedule(station_code)

            # Process discovered trains
            new_train_ids = await self.process_discovered_trains(
                session, station_code, trains_data
            )

            # Update discovery run
            duration_ms = int((now_et() - start_time).total_seconds() * 1000)
            discovery_run.trains_discovered = len(trains_data)
            discovery_run.new_trains = len(new_train_ids)
            discovery_run.duration_ms = duration_ms
            discovery_run.success = True

            session.add(discovery_run)
            await session.flush()

            logger.info(
                "station_discovery_complete",
                station_code=station_code,
                trains_discovered=len(trains_data),
                new_trains=len(new_train_ids),
                duration_ms=duration_ms,
            )

            return {
                "trains_discovered": len(trains_data),
                "new_trains": len(new_train_ids),
                "new_train_ids": list(new_train_ids),
            }

        except Exception as e:
            # Track failure
            logger.error(
                "station_discovery_failed",
                station_code=station_code,
                error=str(e),
                error_type=type(e).__name__,
            )

            discovery_run.success = False
            discovery_run.error_details = str(e)
            session.add(discovery_run)
            await session.flush()

            return {"trains_discovered": 0, "new_trains": 0, "error": str(e)}

    async def process_discovered_trains(
        self,
        session: AsyncSession,
        station_code: str,
        trains_data: list[dict[str, Any]],
    ) -> set[str]:
        """Process discovered trains and create journey records.

        Args:
            session: Database session
            station_code: Station where trains were discovered
            trains_data: Raw train data from API

        Returns:
            Set of newly discovered train IDs
        """
        new_train_ids = set()

        for train_data in trains_data:
            try:
                # Extract key fields
                train_id = train_data.get("TRAIN_ID", "").strip()
                if not train_id:
                    continue

                # Parse scheduled departure time
                sched_dep_str = train_data.get("SCHED_DEP_DATE", "")
                if not sched_dep_str:
                    continue

                scheduled_departure = parse_njt_time(sched_dep_str)
                journey_date = scheduled_departure.date()

                # Check if journey already exists
                stmt = select(TrainJourney).where(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date == journey_date,
                )
                existing = await session.scalar(stmt)

                if existing:
                    # Update last seen time
                    existing.last_updated_at = now_et()
                    continue

                # Create new journey
                journey = TrainJourney(
                    train_id=train_id,
                    journey_date=journey_date,
                    line_code=train_data.get("LINE", "").strip()[:2],
                    line_name=train_data.get("LINE_NAME", ""),
                    destination=train_data.get("DESTINATION", "").strip(),
                    origin_station_code=station_code,
                    terminal_station_code=station_code,  # Will be updated later
                    scheduled_departure=scheduled_departure,
                    first_seen_at=now_et(),
                    last_updated_at=now_et(),
                    has_complete_journey=False,
                    update_count=1,
                )

                # Extract line color if available
                if "BACKCOLOR" in train_data:
                    journey.line_color = train_data["BACKCOLOR"].strip()

                session.add(journey)
                new_train_ids.add(train_id)

                logger.debug(
                    "new_journey_discovered",
                    train_id=train_id,
                    journey_date=journey_date,
                    line=journey.line_code,
                    destination=journey.destination,
                    departure=scheduled_departure.isoformat(),
                )

            except Exception as e:
                logger.error(
                    "failed_to_process_train", train_data=train_data, error=str(e)
                )
                continue

        return new_train_ids
