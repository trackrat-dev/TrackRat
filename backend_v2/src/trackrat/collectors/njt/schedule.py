"""
NJ Transit schedule collector for TrackRat V2.

Fetches 27-hour schedule data once daily and creates SCHEDULED journey records.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class NJTScheduleCollector:
    """Collects NJ Transit schedule data once daily."""

    def __init__(self, client: NJTransitClient) -> None:
        """Initialize the schedule collector.

        Args:
            client: NJ Transit API client instance
        """
        self.client = client

    async def collect_all_schedules(self) -> dict[str, Any]:
        """Collect 27-hour schedule data for all stations.

        This method:
        1. Fetches schedule data from NJ Transit API (single call)
        2. Parses schedule items into train journeys
        3. Creates SCHEDULED records for trains not already OBSERVED
        4. Updates existing SCHEDULED records with latest data

        Returns:
            Dictionary with collection statistics
        """
        logger.info("starting_njt_schedule_collection")

        try:
            # Get schedule for all stations (empty string = all)
            # Include both NJT and Amtrak trains in schedule
            schedule_data = await self.client.get_station_schedule(
                station_code=None, njt_only=False  # All stations  # Include Amtrak
            )

            logger.info(
                "schedule_data_retrieved",
                station_count=len(schedule_data),
                total_items=sum(
                    len(station.get("ITEMS", [])) for station in schedule_data
                ),
            )

            # Process the schedule data
            async with get_session() as session:
                stats = await self._process_schedule_data(session, schedule_data)

            logger.info("njt_schedule_collection_completed", **stats)

            return stats

        except Exception as e:
            logger.error(
                "njt_schedule_collection_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _process_schedule_data(
        self, session: AsyncSession, schedule_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Process schedule data and create/update journey records.

        Args:
            session: Database session
            schedule_data: Raw schedule data from API

        Returns:
            Processing statistics
        """
        stats = {
            "total_schedules": 0,
            "new_schedules": 0,
            "skipped_observed": 0,
            "updated_schedules": 0,
            "errors": 0,
        }

        # Get current date in Eastern Time for journey date
        journey_date = now_et().date()

        # Process each station's schedule items
        for station_data in schedule_data:
            station_code = station_data.get("STATION_2CHAR")
            station_name = station_data.get("STATIONNAME")
            items = station_data.get("ITEMS", [])

            if not station_code:
                logger.warning("station_missing_code", station_data=station_data)
                continue

            logger.debug(
                "processing_station_schedule",
                station_code=station_code,
                station_name=station_name,
                item_count=len(items),
            )

            for item in items:
                stats["total_schedules"] += 1

                try:
                    result = await self._process_schedule_item(
                        session,
                        item,
                        station_code,
                        station_name or "",
                        datetime.combine(journey_date, datetime.min.time()),
                    )

                    if result == "new":
                        stats["new_schedules"] += 1
                    elif result == "updated":
                        stats["updated_schedules"] += 1
                    elif result == "skipped":
                        stats["skipped_observed"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        "schedule_item_processing_failed",
                        station_code=station_code,
                        train_id=item.get("TRAIN_ID"),
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        # Commit all changes
        await session.commit()

        return stats

    async def _process_schedule_item(
        self,
        session: AsyncSession,
        item: dict[str, Any],
        station_code: str,
        station_name: str,
        journey_date: date,
    ) -> str:
        """Process a single schedule item.

        Args:
            session: Database session
            item: Schedule item data
            station_code: Station code where train departs
            station_name: Station name
            journey_date: Date of the journey

        Returns:
            "new", "updated", or "skipped"
        """
        train_id = item.get("TRAIN_ID")
        if not train_id:
            logger.warning("schedule_item_missing_train_id", item=item)
            return "skipped"

        # Parse scheduled departure time
        sched_dep_str = item.get("SCHED_DEP_DATE")
        if not sched_dep_str:
            logger.warning(
                "schedule_item_missing_departure",
                train_id=train_id,
                item=item,
            )
            return "skipped"

        # Parse the scheduled departure time
        scheduled_departure = parse_njt_time(sched_dep_str)
        if not scheduled_departure:
            logger.warning(
                "schedule_item_invalid_departure",
                train_id=train_id,
                departure_str=sched_dep_str,
            )
            return "skipped"

        # Extract other fields
        destination = item.get("DESTINATION", "Unknown")
        line = item.get("LINE", "")
        track = item.get("TRACK")  # May be line name for schedule data

        # Determine if this is NJT or Amtrak based on train ID format
        # Amtrak trains typically have non-numeric IDs
        data_source = "NJT"
        if not train_id.isdigit():
            # Could be Amtrak, but schedule API doesn't clearly distinguish
            # For now, assume numeric = NJT, non-numeric might be Amtrak
            # This is a simplification - may need refinement
            pass

        # Check if this journey already exists
        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == data_source,
            )
        )
        result = await session.execute(stmt)
        existing_journey = result.scalar_one_or_none()

        if existing_journey:
            # If it's already OBSERVED, skip updating it
            if existing_journey.observation_type == "OBSERVED":
                logger.debug(
                    "skipping_observed_journey",
                    train_id=train_id,
                    journey_date=journey_date,
                )
                return "skipped"

            # Update the scheduled journey with latest schedule data
            existing_journey.scheduled_departure = scheduled_departure
            existing_journey.destination = destination
            existing_journey.line_code = line[:2] if line else ""
            existing_journey.line_name = line
            existing_journey.last_updated_at = now_et()

            logger.debug(
                "updated_scheduled_journey",
                train_id=train_id,
                journey_date=journey_date,
            )
            return "updated"

        # Create new SCHEDULED journey
        new_journey = TrainJourney(
            train_id=train_id,
            journey_date=journey_date,
            line_code=line[:2] if line else "",
            line_name=line,
            destination=destination,
            origin_station_code=station_code,
            terminal_station_code=station_code,  # Will be updated if we get full route
            data_source=data_source,
            observation_type="SCHEDULED",
            scheduled_departure=scheduled_departure,
            discovery_station_code=station_code,
            discovery_track=track if track and track != line else None,
            has_complete_journey=False,  # Schedule doesn't include stop details
            stops_count=0,
            is_cancelled=False,
            is_completed=False,
            is_expired=False,
            api_error_count=0,
            update_count=1,
        )

        session.add(new_journey)

        # Create a single stop for the departure station
        # (Schedule API doesn't provide full stop list)
        departure_stop = JourneyStop(
            journey=new_journey,
            station_code=station_code,
            station_name=station_name,
            stop_sequence=0,
            scheduled_departure=scheduled_departure,
            scheduled_arrival=scheduled_departure,  # Same as departure for origin
            track=track if track and track != line else None,
            has_departed_station=False,
        )

        session.add(departure_stop)

        logger.debug(
            "created_scheduled_journey",
            train_id=train_id,
            journey_date=journey_date,
            station_code=station_code,
            destination=destination,
        )

        return "new"
