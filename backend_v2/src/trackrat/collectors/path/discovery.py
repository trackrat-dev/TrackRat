"""
PATH train discovery collector for TrackRat V2.

Discovers active PATH trains by polling station arrival boards via Transiter API.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.collectors.path.client import PathClient, PathStopTime
from trackrat.config.stations import (
    INTERNAL_TO_PATH_TRANSITER_MAP,
    PATH_DISCOVERY_STATIONS,
    get_path_route_info,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import now_et

logger = get_logger(__name__)


def _generate_path_train_id(route_id: str, trip_id: str) -> str:
    """Generate a stable train ID for PATH trains.

    PATH doesn't have traditional train numbers, so we generate IDs from
    the route and trip. The trip_id from Transiter is stable for a given
    departure.

    Args:
        route_id: Transiter route ID (e.g., '859')
        trip_id: Transiter trip ID

    Returns:
        Generated train ID (e.g., 'PATH_859_abc123')
    """
    # Use a shortened trip ID to keep the train_id reasonable
    short_trip = trip_id[:12] if len(trip_id) > 12 else trip_id
    return f"PATH_{route_id}_{short_trip}"


class PathDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active PATH trains from station arrival boards."""

    def __init__(self, client: PathClient | None = None) -> None:
        """Initialize the PATH discovery collector.

        Args:
            client: Optional PATH client (creates one if not provided)
        """
        self.client = client or PathClient()
        self._owns_client = client is None

    async def discover_trains(self) -> list[str]:
        """Discover active PATH train IDs from all discovery stations.

        Returns:
            List of discovered train IDs
        """
        discovered_ids: set[str] = set()

        for station_code in PATH_DISCOVERY_STATIONS:
            try:
                transiter_id = INTERNAL_TO_PATH_TRANSITER_MAP.get(station_code)
                if not transiter_id:
                    logger.warning(
                        "path_station_not_mapped",
                        station_code=station_code,
                    )
                    continue

                arrivals = await self.client.get_station_arrivals(transiter_id)

                for arrival in arrivals:
                    train_id = _generate_path_train_id(
                        arrival.route_id, arrival.trip_id
                    )
                    discovered_ids.add(train_id)

            except Exception as e:
                logger.error(
                    "path_discovery_station_failed",
                    station_code=station_code,
                    error=str(e),
                )
                continue

        return list(discovered_ids)

    async def run(self) -> dict[str, Any]:
        """Run the discovery collector with a database session.

        Returns:
            Collection results summary
        """
        try:
            async with get_session() as session:
                return await self.collect(session)
        finally:
            if self._owns_client:
                await self.client.close()

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Run discovery for all configured PATH stations.

        Args:
            session: Database session

        Returns:
            Discovery results summary
        """
        logger.info("discovery.path.started", stations=PATH_DISCOVERY_STATIONS)

        total_arrivals = 0
        total_new = 0
        station_results = {}

        for station_code in PATH_DISCOVERY_STATIONS:
            result = await self._discover_station_trains(session, station_code)
            station_results[station_code] = result
            total_arrivals += result.get("arrivals_found", 0)
            total_new += result.get("new_journeys", 0)

        await session.commit()

        logger.info(
            "discovery.path.completed",
            total_arrivals=total_arrivals,
            total_new=total_new,
            stations_processed=len(PATH_DISCOVERY_STATIONS),
        )

        return {
            "data_source": "PATH",
            "stations_processed": len(PATH_DISCOVERY_STATIONS),
            "total_arrivals": total_arrivals,
            "total_new": total_new,
            "station_results": station_results,
        }

    async def _discover_station_trains(
        self, session: AsyncSession, station_code: str
    ) -> dict[str, Any]:
        """Discover trains from a single PATH station.

        Args:
            session: Database session
            station_code: Internal station code (e.g., 'PATH_HOB')

        Returns:
            Discovery results for this station
        """
        transiter_id = INTERNAL_TO_PATH_TRANSITER_MAP.get(station_code)
        if not transiter_id:
            return {"error": f"No Transiter ID for {station_code}"}

        try:
            arrivals = await self.client.get_station_arrivals(transiter_id)

            new_journeys = 0
            for arrival in arrivals:
                created = await self._process_arrival(
                    session, station_code, arrival
                )
                if created:
                    new_journeys += 1

            return {
                "arrivals_found": len(arrivals),
                "new_journeys": new_journeys,
            }

        except Exception as e:
            logger.error(
                "path_station_discovery_failed",
                station_code=station_code,
                error=str(e),
            )
            return {"error": str(e), "arrivals_found": 0, "new_journeys": 0}

    async def _process_arrival(
        self,
        session: AsyncSession,
        discovery_station: str,
        arrival: PathStopTime,
    ) -> bool:
        """Process a single arrival and create/update journey record.

        Args:
            session: Database session
            discovery_station: Station where this arrival was discovered
            arrival: Arrival data from Transiter

        Returns:
            True if a new journey was created, False if existing
        """
        train_id = _generate_path_train_id(arrival.route_id, arrival.trip_id)

        # Determine journey date from departure time
        departure_time = arrival.departure_time or arrival.arrival_time
        if not departure_time:
            logger.debug("path_arrival_no_time", trip_id=arrival.trip_id)
            return False

        journey_date = departure_time.date()

        # Check if journey already exists
        stmt = select(TrainJourney).where(
            TrainJourney.train_id == train_id,
            TrainJourney.journey_date == journey_date,
            TrainJourney.data_source == "PATH",
        )
        existing = await session.scalar(stmt)

        if existing:
            # Update last seen time
            existing.last_updated_at = now_et()
            return False

        # Get route info for line code and name
        route_info = get_path_route_info(arrival.route_id)
        if route_info:
            line_code, line_name, line_color = route_info
        else:
            line_code = arrival.route_id[:6]
            line_name = f"PATH Route {arrival.route_id}"
            line_color = None

        # Use route color from API if available (without # prefix)
        if arrival.route_color:
            line_color = f"#{arrival.route_color}"

        # Get stop times from GTFS for accurate scheduling
        gtfs_service = GTFSService()
        gtfs_stop_times = await gtfs_service.get_path_route_stop_times(
            session,
            arrival.route_id,
            discovery_station,  # terminus station
            departure_time,  # observed terminus time
        )

        if gtfs_stop_times:
            # Use GTFS-based stop times
            origin_station = gtfs_stop_times[0][0]
            terminal_station = gtfs_stop_times[-1][0]
            origin_departure_time = gtfs_stop_times[0][2]  # departure from origin
            has_complete_journey = True
            stops_count = len(gtfs_stop_times)
        else:
            # No GTFS data - create minimal journey with just terminus info
            logger.warning(
                "path_no_gtfs_fallback",
                route_id=arrival.route_id,
                terminus=discovery_station,
            )
            origin_station = discovery_station
            terminal_station = discovery_station
            origin_departure_time = departure_time
            has_complete_journey = False
            stops_count = 1

        # Create new journey
        journey = TrainJourney(
            train_id=train_id,
            journey_date=journey_date,
            line_code=line_code,
            line_name=line_name,
            line_color=line_color,
            destination=arrival.headsign or "",
            origin_station_code=origin_station,
            terminal_station_code=terminal_station,
            scheduled_departure=origin_departure_time,
            scheduled_arrival=departure_time,  # Arrival at terminus
            data_source="PATH",
            observation_type="OBSERVED",
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=has_complete_journey,
            stops_count=stops_count,
            update_count=1,
        )

        session.add(journey)
        await session.flush()

        # Create stops from GTFS data or minimal terminus-only stop
        if gtfs_stop_times:
            for sequence, (station_code, arrival_dt, departure_dt) in enumerate(
                gtfs_stop_times, start=1
            ):
                is_origin = sequence == 1
                is_terminus = sequence == len(gtfs_stop_times)

                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=station_code,
                    station_name=get_station_name(station_code),
                    stop_sequence=sequence,
                    scheduled_arrival=arrival_dt if not is_origin else None,
                    scheduled_departure=departure_dt if not is_terminus else None,
                    updated_arrival=arrival_dt if not is_origin else None,
                    updated_departure=departure_dt if not is_terminus else None,
                )
                session.add(stop)
        else:
            # Minimal stop: just the terminus we observed
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=discovery_station,
                station_name=get_station_name(discovery_station),
                stop_sequence=1,
                scheduled_arrival=departure_time,
                scheduled_departure=None,  # Terminus has no departure
                updated_arrival=departure_time,
                updated_departure=None,
            )
            session.add(stop)

        logger.debug(
            "path_journey_created",
            train_id=train_id,
            journey_date=journey_date,
            line=line_code,
            destination=arrival.headsign,
            departure=departure_time.isoformat(),
            stops=stops_count,
            has_gtfs=gtfs_stop_times is not None,
        )

        return True
