"""
Train discovery collector for TrackRat V2.

Discovers active trains by polling station departure boards.
Also detects cancellations from NJT station alerts.
"""

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.collectors.njt.cancellation_parser import (
    CancellationAlert,
    parse_cancellation_alerts,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.config.stations import DISCOVERY_STATIONS
from trackrat.db.engine import get_session
from trackrat.models.database import DiscoveryRun, JourneyStop, TrainJourney
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class TrainDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active trains from station schedules."""

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the discovery collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def discover_trains(self) -> list[str]:
        """Discover active train IDs from all stations.

        Returns:
            List of discovered train IDs
        """
        discovered_ids = []
        for station_code in DISCOVERY_STATIONS:
            try:
                schedule_response = await self.njt_client.get_train_schedule_with_stops(
                    station_code
                )
                trains_data = schedule_response.get("ITEMS") or []
                for train_data in trains_data:
                    train_id = train_data.get("TRAIN_ID", "").strip()
                    if train_id and train_id not in discovered_ids:
                        discovered_ids.append(train_id)
            except Exception as e:
                logger.error(
                    "failed_to_discover_from_station",
                    station=station_code,
                    error=str(e),
                )
                continue

        return discovered_ids

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
        logger.info("discovery.njt.started", stations=DISCOVERY_STATIONS)

        # Check for cancellation alerts first (one API call to NY Penn)
        cancelled_trains = await self.check_for_cancellations(session)

        total_discovered = 0
        total_new = 0
        station_results = {}

        for station_code in DISCOVERY_STATIONS:
            result = await self.discover_station_trains(session, station_code)
            station_results[station_code] = result
            total_discovered += result["trains_discovered"]
            total_new += result["new_trains"]

        logger.info(
            "discovery.njt.completed",
            total_discovered=total_discovered,
            total_new=total_new,
            stations_processed=len(DISCOVERY_STATIONS),
            cancelled_trains=len(cancelled_trains),
        )

        return {
            "stations_processed": len(DISCOVERY_STATIONS),
            "total_discovered": total_discovered,
            "total_new": total_new,
            "cancelled_trains": cancelled_trains,
            "station_results": station_results,
        }

    async def check_for_cancellations(self, session: AsyncSession) -> list[str]:
        """Check NY Penn station alerts for train cancellations.

        NY Penn's STATIONMSGS contains alerts for all NJT lines, so we only
        need to check one station to detect cancellations system-wide.

        Args:
            session: Database session

        Returns:
            List of train IDs that were marked as cancelled
        """
        try:
            # Fetch departure vision data which includes STATIONMSGS
            response = await self.njt_client.get_departure_vision_data("NY")
            station_data = response.get("STATION", {})
            messages = station_data.get("STATIONMSGS", [])

            if not messages:
                return []

            # Parse cancellation alerts from messages
            alerts = parse_cancellation_alerts(messages)

            if not alerts:
                return []

            logger.info(
                "cancellation_alerts_found",
                count=len(alerts),
                train_ids=[a.train_id for a in alerts],
            )

            # Mark affected journeys as cancelled
            marked_trains = await self._mark_cancelled_journeys(session, alerts)

            return marked_trains

        except Exception as e:
            # Don't let cancellation check failures break discovery
            logger.error(
                "cancellation_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    async def _mark_cancelled_journeys(
        self, session: AsyncSession, alerts: list[CancellationAlert]
    ) -> list[str]:
        """Mark journeys as cancelled based on alerts.

        Args:
            session: Database session
            alerts: List of parsed cancellation alerts

        Returns:
            List of train IDs that were marked as cancelled
        """
        marked_trains = []
        today = now_et().date()

        for alert in alerts:
            # Find matching journey for today
            journey = await session.scalar(
                select(TrainJourney).where(
                    TrainJourney.train_id == alert.train_id,
                    TrainJourney.journey_date == today,
                    TrainJourney.data_source == "NJT",
                )
            )

            if journey and not journey.is_cancelled:
                # Mark existing journey as cancelled
                journey.is_cancelled = True
                journey.cancellation_reason = alert.reason
                journey.last_updated_at = now_et()
                marked_trains.append(alert.train_id)

                logger.info(
                    "journey_marked_cancelled_from_alert",
                    train_id=alert.train_id,
                    reason=alert.reason,
                    alternative=alert.alternative_train_id,
                )

        if marked_trains:
            await session.commit()

        return marked_trains

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
            # Get train schedule data with embedded stops
            schedule_response = await self.njt_client.get_train_schedule_with_stops(
                station_code
            )
            trains_data = schedule_response.get("ITEMS") or []

            # Track ALL train IDs for batch collection
            all_train_ids = []
            for train_data in trains_data:
                train_id = train_data.get("TRAIN_ID", "").strip()
                if train_id:
                    all_train_ids.append(train_id)

            # Process discovered trains (creates/updates journey records)
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
                "all_train_ids": all_train_ids,  # Return ALL discovered train IDs
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

    async def _update_stop_track_if_needed(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        station_code: str,
        track: str,
    ) -> None:
        """Update track for a specific journey stop, creating the stop if needed.

        Args:
            session: Database session
            journey: The journey to update
            station_code: Station code where track was discovered
            track: Track number to assign
        """
        # Find the stop for this station
        stmt = select(JourneyStop).where(
            and_(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == station_code,
            )
        )
        stop = await session.scalar(stmt)

        if stop:
            # Stop exists - update track if not already set
            if not stop.track:
                sanitized_track = sanitize_track(track)
                if sanitized_track:
                    stop.track = sanitized_track
                    stop.track_assigned_at = now_et()
                    logger.info(
                        "updated_existing_stop_track_during_discovery",
                        train_id=journey.train_id,
                        station_code=station_code,
                        track=sanitized_track,
                    )
        else:
            # Stop doesn't exist - create it with the track
            from trackrat.config.stations import get_station_name

            sanitized_track = sanitize_track(track)
            if sanitized_track:
                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=station_code,
                    station_name=get_station_name(station_code),
                    # Don't set stop_sequence - let journey collector handle it exclusively
                    track=sanitized_track,
                    track_assigned_at=now_et(),
                )
                session.add(stop)
                logger.info(
                    "created_stop_with_track_during_discovery",
                    train_id=journey.train_id,
                    station_code=station_code,
                    track=sanitized_track,
                )

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

                # Skip Amtrak trains (format: A + digits) - these should be handled by Amtrak discovery
                if (
                    train_id.startswith("A")
                    and len(train_id) > 1
                    and train_id[1:].isdigit()
                ):
                    logger.debug(
                        "skipping_amtrak_train_in_njt_discovery",
                        train_id=train_id,
                        station_code=station_code,
                    )
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
                    TrainJourney.data_source == "NJT",
                )
                existing = await session.scalar(stmt)

                if existing:
                    # Re-activate expired trains that reappear in discovery
                    if existing.is_expired:
                        existing.is_expired = False
                        existing.api_error_count = 0
                        logger.info(
                            "reactivated_expired_train",
                            train_id=train_id,
                            journey_date=journey_date,
                        )

                    # Update last seen time
                    existing.last_updated_at = now_et()

                    # Mark as observed if it was previously scheduled
                    if existing.observation_type == "SCHEDULED":
                        existing.observation_type = "OBSERVED"
                        logger.info(
                            "upgraded_scheduled_to_observed",
                            train_id=train_id,
                            journey_date=journey_date,
                        )

                    # Update track directly in journey stop
                    track = train_data.get("TRACK")
                    if track and station_code:
                        await self._update_stop_track_if_needed(
                            session, existing, station_code, track
                        )

                    continue

                # Create new journey
                # NOTE: We temporarily use the discovery station as origin, but this might be
                # an intermediate stop. The journey collector will correct this when it fetches
                # the full journey details (see journey.py lines 685-694).
                journey = TrainJourney(
                    train_id=train_id,
                    journey_date=journey_date,
                    line_code=train_data.get("LINE", "").strip()[:2],
                    line_name=train_data.get("LINE_NAME", ""),
                    destination=train_data.get("DESTINATION", "").strip(),
                    origin_station_code=station_code,  # May be wrong - journey collector will fix
                    terminal_station_code=station_code,  # Will be updated later
                    scheduled_departure=scheduled_departure,  # May be wrong - journey collector will fix
                    data_source="NJT",
                    observation_type="OBSERVED",  # Real-time discovery data
                    first_seen_at=now_et(),
                    last_updated_at=now_et(),
                    has_complete_journey=False,
                    update_count=1,
                )

                # Extract line color if available
                if "BACKCOLOR" in train_data:
                    journey.line_color = train_data["BACKCOLOR"].strip()

                session.add(journey)
                await session.flush()  # Ensure journey has ID before creating stops
                new_train_ids.add(train_id)

                # Update track directly in journey stop
                track = train_data.get("TRACK")
                if track and station_code:
                    await self._update_stop_track_if_needed(
                        session, journey, station_code, track
                    )

                logger.debug(
                    "new_journey_discovered",
                    train_id=train_id,
                    journey_date=journey_date,
                    line=journey.line_code,
                    destination=journey.destination,
                    departure=scheduled_departure.isoformat(),
                    track=track,
                )

            except Exception as e:
                logger.error(
                    "failed_to_process_train", train_data=train_data, error=str(e)
                )
                continue

        return new_train_ids
