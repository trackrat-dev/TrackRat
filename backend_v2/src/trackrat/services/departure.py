"""
Departure service for handling train departure queries.
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.config.stations import get_station_name
from trackrat.models.api import (
    DataFreshness,
    DeparturesResponse,
    LineInfo,
    StationInfo,
    TrainDeparture,
    TrainPosition,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et, parse_njt_time, safe_datetime_subtract

logger = get_logger(__name__)


class DepartureService:
    """Service for handling departure queries and processing."""

    async def get_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None = None,
        date: date | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int = 50,
    ) -> DeparturesResponse:
        """Get train departures between stations."""

        # Set default time range
        if time_from is None:
            query_date = date or now_et().date()
            # Fix timezone bug: ensure time_from is timezone-aware in ET
            from trackrat.utils.time import ET

            time_from = ET.localize(datetime.combine(query_date, datetime.min.time()))
        else:
            # Ensure provided time_from is timezone-aware
            from trackrat.utils.time import ensure_timezone_aware

            time_from = ensure_timezone_aware(time_from)

        if time_to is None:
            # Extend window to 26 hours to handle edge cases:
            # - Tests that create data up to 2 hours in the future
            # - Overnight journeys that cross date boundaries
            time_to = time_from + timedelta(hours=26)
        else:
            # Ensure provided time_to is timezone-aware
            from trackrat.utils.time import ensure_timezone_aware

            time_to = ensure_timezone_aware(time_to)

        # Query journeys from both NJT and Amtrak data sources
        # Determine journey_date filter based on whether a specific date was provided
        if date:
            # If a specific date was provided, use it exactly
            journey_date_filter = TrainJourney.journey_date == date
        else:
            # For time-based queries, include a range to handle:
            # - Overnight journeys that cross date boundaries
            # - Multi-day Amtrak journeys
            # - Tests that create data slightly in the future
            journey_date_filter = and_(
                TrainJourney.journey_date >= (time_from.date() - timedelta(days=2)),
                TrainJourney.journey_date <= (time_to.date() + timedelta(days=1)),
            )

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code == from_station,
                ),
            )
            .where(
                and_(
                    JourneyStop.scheduled_departure >= time_from,
                    JourneyStop.scheduled_departure <= time_to,
                    journey_date_filter,
                    # Include both data sources
                    TrainJourney.data_source.in_(["NJT", "AMTRAK"]),
                )
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(JourneyStop.scheduled_departure)
            .limit(limit * 2)
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().unique().all())

        # Ensure fresh data for NJT trains using station-level refresh
        njt_journeys = [j for j in journeys if j.data_source == "NJT"]
        if njt_journeys:
            await self._ensure_fresh_station_data(db, from_station)

        # Build departures list
        departures = []
        for journey in journeys:
            # Find from and to stops
            from_stop = None
            to_stop = None
            for stop in sorted(journey.stops, key=lambda s: s.stop_sequence or 0):
                if stop.station_code == from_station and not from_stop:
                    from_stop = stop
                elif to_station and stop.station_code == to_station and from_stop:
                    # Ensure to_stop comes AFTER from_stop in the journey sequence
                    if (stop.stop_sequence or 0) > (from_stop.stop_sequence or 0):
                        to_stop = stop
                        break

            # Skip if stops not found
            if not from_stop or (to_station and not to_stop):
                continue

            # Calculate train position
            train_position = self._calculate_train_position(journey)

            # Build departure
            departure = TrainDeparture(
                train_id=journey.train_id,
                journey_date=journey.journey_date,
                line=LineInfo(
                    code=journey.line_code,
                    name=journey.line_name or journey.line_code,
                    color=(journey.line_color or "#000000").strip(),
                ),
                destination=journey.destination,
                departure=StationInfo(
                    code=from_stop.station_code,
                    name=from_stop.station_name,
                    scheduled_time=from_stop.scheduled_departure
                    or from_stop.scheduled_arrival,
                    updated_time=from_stop.updated_departure
                    or from_stop.updated_arrival,
                    actual_time=from_stop.actual_departure or from_stop.actual_arrival,
                    track=from_stop.track,
                ),
                arrival=(
                    StationInfo(
                        code=to_stop.station_code,
                        name=to_stop.station_name,
                        scheduled_time=to_stop.scheduled_arrival
                        or to_stop.scheduled_departure,
                        updated_time=to_stop.updated_arrival
                        or to_stop.updated_departure,
                        actual_time=to_stop.actual_arrival or to_stop.actual_departure,
                        track=to_stop.track,
                    )
                    if to_stop
                    else None
                ),
                train_position=train_position,
                data_freshness=DataFreshness(
                    last_updated=journey.last_updated_at or journey.first_seen_at,
                    age_seconds=int(
                        safe_datetime_subtract(
                            now_et(),
                            journey.last_updated_at
                            or journey.first_seen_at
                            or now_et(),
                        ).total_seconds()
                    ),
                    update_count=journey.update_count,
                ),
                data_source=journey.data_source,
                observation_type=journey.observation_type,
                is_cancelled=journey.is_cancelled,
            )
            departures.append(departure)

            if len(departures) >= limit:
                break

        return DeparturesResponse(
            departures=departures,
            metadata={
                "from_station": {
                    "code": from_station,
                    "name": get_station_name(from_station),
                },
                "to_station": (
                    {"code": to_station, "name": get_station_name(to_station)}
                    if to_station
                    else None
                ),
                "count": len(departures),
                "generated_at": now_et().isoformat(),
            },
        )

    def _calculate_train_position(self, journey: TrainJourney) -> TrainPosition:
        """Calculate current train position based on stops data."""
        if not journey.stops:
            return TrainPosition()

        # Sort stops by sequence
        sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

        # Find last departed station and next station
        last_departed_station_code = None
        at_station_code = None
        next_station_code = None

        for stop in sorted_stops:
            if stop.has_departed_station:
                last_departed_station_code = stop.station_code
            else:
                # This is the next station
                next_station_code = stop.station_code

                # Check if currently at this station (based on raw status)
                if journey.data_source == "AMTRAK":
                    # For Amtrak, "Station" means at the station
                    if stop.raw_amtrak_status == "Station":
                        at_station_code = stop.station_code
                elif journey.data_source == "NJT":
                    # For NJT, having a track assignment suggests at station
                    if stop.track and not stop.has_departed_station:
                        at_station_code = stop.station_code

                break

        # If no undeparted stops found, train may have completed journey
        if not next_station_code and sorted_stops:
            last_stop = sorted_stops[-1]
            if last_stop.has_departed_station:
                at_station_code = last_stop.station_code

        return TrainPosition(
            last_departed_station_code=last_departed_station_code,
            at_station_code=at_station_code,
            next_station_code=next_station_code,
            between_stations=(
                last_departed_station_code is not None
                and at_station_code is None
                and next_station_code is not None
            ),
        )

    async def _ensure_fresh_station_data(
        self, db: AsyncSession, station_code: str
    ) -> None:
        """Ensure station departure data is fresh using getTrainSchedule with embedded stops."""

        # Check if station data needs refresh (90 second staleness)
        cutoff_time = now_et() - timedelta(seconds=90)

        needs_refresh = await db.scalar(
            select(TrainJourney.id)
            .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code == station_code,
                    TrainJourney.data_source == "NJT",
                    TrainJourney.last_updated_at < cutoff_time,
                )
            )
            .limit(1)
        )

        if not needs_refresh:
            logger.debug("station_data_fresh", station_code=station_code)
            return

        logger.info("refreshing_station_data", station_code=station_code)

        # Refresh entire station using getTrainSchedule (with embedded STOPS)
        njt_client = NJTransitClient()
        try:
            schedule_data = await njt_client.get_train_schedule_with_stops(station_code)

            train_items = schedule_data.get("ITEMS", [])
            logger.info(
                "station_refresh_retrieved",
                station_code=station_code,
                train_count=len(train_items),
            )

            # Extract all train IDs for bulk loading
            train_ids = []
            for train_data in train_items:
                if train_id := train_data.get("TRAIN_ID"):
                    train_ids.append(train_id)

            if not train_ids:
                await db.commit()
                logger.info(
                    "station_refresh_complete",
                    station_code=station_code,
                    updated_trains=0,
                )
                return

            # Bulk load all journeys in a single query
            stmt = (
                select(TrainJourney)
                .where(
                    and_(
                        TrainJourney.train_id.in_(train_ids),
                        TrainJourney.journey_date == now_et().date(),
                        TrainJourney.data_source == "NJT",
                    )
                )
                .options(selectinload(TrainJourney.stops))
            )
            result = await db.execute(stmt)
            journeys_by_id = {j.train_id: j for j in result.scalars().all()}

            # Update journeys in memory
            updated_count = 0
            for train_data in train_items:
                train_id = train_data.get("TRAIN_ID")
                if not train_id:
                    continue

                # Check if this is an Amtrak train appearing in NJT station data
                is_amtrak = train_id.startswith("A") and train_id[1:].isdigit()

                journey = journeys_by_id.get(train_id)
                if not journey:
                    # Only log warning for non-Amtrak trains
                    if not is_amtrak:
                        logger.warning(
                            "journey_not_found_during_station_refresh",
                            train_id=train_id,
                            station_code=station_code,
                        )
                    else:
                        logger.debug(
                            "amtrak_train_in_njt_station",
                            train_id=train_id,
                            station_code=station_code,
                            reason="Amtrak trains appear in NJT stations but are tracked separately",
                        )
                    continue

                # Update journey metadata
                journey.destination = train_data.get("DESTINATION", journey.destination)

                # Clean color value (remove trailing spaces)
                if backcolor := train_data.get("BACKCOLOR"):
                    journey.line_color = backcolor.strip()
                journey.last_updated_at = now_et()
                journey.update_count = (journey.update_count or 0) + 1

                # Update stops from embedded STOPS data
                stops_data = train_data.get("STOPS", [])
                if stops_data:
                    await self._update_stops_from_embedded_data(journey, stops_data)
                    journey.has_complete_journey = True
                    journey.stops_count = len(stops_data)

                logger.debug(
                    "journey_updated_from_schedule",
                    train_id=train_id,
                    stops_count=len(stops_data),
                )
                updated_count += 1

            await db.commit()
            logger.info(
                "station_refresh_complete",
                station_code=station_code,
                updated_trains=updated_count,
            )

        except Exception as e:
            logger.error(
                "station_refresh_failed", station_code=station_code, error=str(e)
            )
            await db.rollback()
            raise
        finally:
            await njt_client.close()

    async def _update_stops_from_embedded_data(
        self, journey: TrainJourney, stops_data: list[dict[str, Any]]
    ) -> None:
        """Update journey stops from embedded STOPS data in getTrainSchedule response."""

        # Create a map of existing stops by station code
        existing_stops = {stop.station_code: stop for stop in journey.stops}

        # Update or create stops from embedded data
        for i, stop_data in enumerate(stops_data):
            station_code = stop_data.get("STATION_2CHAR")
            if not station_code:
                continue

            # Get existing stop or create new one
            stop = existing_stops.get(station_code)
            if not stop:
                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=station_code,
                    station_name=stop_data.get("STATIONNAME", ""),
                    stop_sequence=i,
                )
                journey.stops.append(stop)

            # Update stop data from schedule
            if arrival_time_str := stop_data.get("TIME"):
                stop.scheduled_arrival = parse_njt_time(arrival_time_str)

            if departure_time_str := stop_data.get("DEP_TIME"):
                stop.scheduled_departure = parse_njt_time(departure_time_str)

            # Update departure status with time validation
            departed = stop_data.get("DEPARTED")
            stop.raw_njt_departed_flag = departed

            # Never mark as departed if scheduled departure is in the future
            # This prevents stale NJT data from incorrectly marking future trains as departed
            if stop.scheduled_departure and stop.scheduled_departure > now_et():
                stop.has_departed_station = False
                if departed == "YES":
                    logger.debug(
                        "overriding_future_departure_flag",
                        station_code=station_code,
                        train_id=journey.train_id,
                        scheduled_departure=stop.scheduled_departure.isoformat(),
                        njt_flag=departed,
                    )
            else:
                stop.has_departed_station = departed == "YES"

            # Update stop sequence if not set
            if stop.stop_sequence is None:
                stop.stop_sequence = i
