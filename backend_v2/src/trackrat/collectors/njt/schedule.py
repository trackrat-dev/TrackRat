"""
Schedule discovery collector for TrackRat V2.

Discovers scheduled trains from NJ Transit schedule API.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

# Removed base class to keep it simple
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class ScheduleDiscoveryCollector:
    """Discovers scheduled trains from NJ Transit schedule API."""

    # Same stations as regular discovery
    DISCOVERY_STATIONS = ["NY", "NP", "PJ", "TR", "LB", "PL", "DN"]

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the schedule discovery collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Run schedule discovery for all configured stations.

        Args:
            session: Database session

        Returns:
            Discovery results summary
        """
        logger.info("starting_schedule_discovery", stations=self.DISCOVERY_STATIONS)

        total_discovered = 0
        total_new = 0
        station_results = {}

        for station_code in self.DISCOVERY_STATIONS:
            result = await self.discover_station_schedule(session, station_code)
            station_results[station_code] = result
            total_discovered += result["trains_discovered"]
            total_new += result["new_trains"]

        logger.info(
            "schedule_discovery_complete",
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

    async def discover_station_schedule(
        self, session: AsyncSession, station_code: str
    ) -> dict[str, Any]:
        """Discover scheduled trains from a single station.

        Args:
            session: Database session
            station_code: Two-character station code

        Returns:
            Discovery results for this station
        """
        try:
            # Get train schedule data
            trains_data = await self.njt_client.get_train_schedule(station_code)

            new_trains = 0
            current_time = now_et()

            for train_data in trains_data:
                try:
                    # Extract key fields
                    train_id = train_data.get("TRAIN_ID", "").strip()
                    if not train_id:
                        continue

                    # Skip Amtrak trains
                    if (
                        train_id.startswith("A")
                        and len(train_id) > 1
                        and train_id[1:].isdigit()
                    ):
                        continue

                    # Parse scheduled departure time
                    sched_dep_str = train_data.get("SCHED_DEP_DATE", "")
                    if not sched_dep_str:
                        continue

                    scheduled_departure = parse_njt_time(sched_dep_str)
                    journey_date = scheduled_departure.date()

                    # Skip trains that have already departed (more than 30 minutes ago)
                    if scheduled_departure < current_time.replace(
                        second=0, microsecond=0
                    ) - timedelta(minutes=30):
                        continue

                    # Check if journey already exists
                    stmt = select(TrainJourney).where(
                        TrainJourney.train_id == train_id,
                        TrainJourney.journey_date == journey_date,
                        TrainJourney.data_source == "NJT",
                    )
                    existing = await session.scalar(stmt)

                    if existing:
                        # Don't update if it's already realtime data
                        if existing.data_source_type == "realtime":
                            continue
                        # Update schedule collection time only for schedule type
                        if existing.data_source_type == "schedule":
                            existing.schedule_collected_at = current_time
                        continue

                    # Create new journey as schedule type
                    journey = TrainJourney(
                        train_id=train_id,
                        journey_date=journey_date,
                        line_code=train_data.get("LINE", "").strip()[:2],
                        line_name=train_data.get("LINE_NAME", ""),
                        destination=train_data.get("DESTINATION", "").strip(),
                        origin_station_code=station_code,
                        terminal_station_code=station_code,  # Will be updated later
                        scheduled_departure=scheduled_departure,
                        data_source="NJT",
                        data_source_type="schedule",  # Mark as schedule data
                        schedule_collected_at=current_time,
                        first_seen_at=current_time,
                        last_updated_at=current_time,
                        has_complete_journey=False,
                        update_count=1,
                    )

                    # Extract line color if available
                    if "BACKCOLOR" in train_data:
                        journey.line_color = train_data["BACKCOLOR"].strip()

                    session.add(journey)
                    new_trains += 1

                    logger.debug(
                        "new_schedule_journey_discovered",
                        train_id=train_id,
                        journey_date=journey_date,
                        line=journey.line_code,
                        destination=journey.destination,
                        departure=scheduled_departure.isoformat(),
                    )

                except Exception as e:
                    logger.error(
                        "failed_to_process_schedule_train",
                        train_data=train_data,
                        error=str(e),
                    )
                    continue

            await session.flush()

            logger.info(
                "station_schedule_discovery_complete",
                station_code=station_code,
                trains_discovered=len(trains_data),
                new_trains=new_trains,
            )

            return {
                "trains_discovered": len(trains_data),
                "new_trains": new_trains,
            }

        except Exception as e:
            logger.error(
                "station_schedule_discovery_failed",
                station_code=station_code,
                error=str(e),
                error_type=type(e).__name__,
            )
            return {"trains_discovered": 0, "new_trains": 0, "error": str(e)}
