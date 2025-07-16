"""
Departure service for handling train departure queries.
"""

from datetime import datetime, timedelta

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
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.time import now_et, safe_datetime_subtract

logger = get_logger(__name__)


class DepartureService:
    """Service for handling departure queries and processing."""

    async def get_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int = 50,
    ) -> DeparturesResponse:
        """Get train departures between stations."""

        # Set default time range
        if time_from is None:
            time_from = now_et().replace(
                tzinfo=None
            )  # Convert to naive Eastern for consistent DB comparison
        if time_to is None:
            time_to = time_from + timedelta(hours=6)

        # Query journeys from both NJT and Amtrak data sources
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
                    TrainJourney.is_cancelled.is_not(True),
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

        # Ensure fresh data for NJT trains only (Amtrak data is already fresh from API)
        njt_journeys = [j for j in journeys if j.data_source == "NJT"]
        if njt_journeys:
            njt_client = NJTransitClient()
            try:
                async with JustInTimeUpdateService(njt_client) as jit_service:
                    await jit_service.ensure_fresh_departures(db, njt_journeys)
            finally:
                await njt_client.close()

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
                line=LineInfo(
                    code=journey.line_code,
                    name=journey.line_name or journey.line_code,
                    color=journey.line_color or "#000000",
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
