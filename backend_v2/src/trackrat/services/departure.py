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
    JourneyInfo,
    JourneyProgress,
    LineInfo,
    StationInfo,
    TrainDeparture,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.time import calculate_delay, now_et, safe_datetime_subtract

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
            time_from = now_et()
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
                    actual_time=from_stop.actual_departure or from_stop.actual_arrival,
                    track=from_stop.track,
                    status=(
                        "DEPARTED"
                        if from_stop.departed
                        else (
                            "BOARDING"
                            if from_stop.track
                            else (
                                "CANCELLED"
                                if from_stop.status == "Cancelled"
                                else "LATE" if from_stop.status == "Late" else "ON_TIME"
                            )
                        )
                    ),
                    delay_minutes=(
                        calculate_delay(
                            from_stop.scheduled_departure, from_stop.actual_departure
                        )
                        if from_stop.departed
                        and from_stop.actual_departure
                        and from_stop.scheduled_departure
                        else (
                            calculate_delay(
                                from_stop.scheduled_arrival, from_stop.actual_arrival
                            )
                            if from_stop.departed
                            and from_stop.actual_arrival
                            and from_stop.scheduled_arrival
                            else 0
                        )
                    ),
                ),
                arrival=(
                    StationInfo(
                        code=to_stop.station_code,
                        name=to_stop.station_name,
                        scheduled_time=to_stop.scheduled_departure
                        or to_stop.scheduled_arrival,
                        actual_time=to_stop.actual_departure or to_stop.actual_arrival,
                        track=to_stop.track,
                        status=(
                            "DEPARTED"
                            if to_stop.departed
                            else (
                                "BOARDING"
                                if to_stop.track
                                else (
                                    "CANCELLED"
                                    if to_stop.status == "Cancelled"
                                    else (
                                        "LATE"
                                        if to_stop.status == "Late"
                                        else "ON_TIME"
                                    )
                                )
                            )
                        ),
                        delay_minutes=(
                            calculate_delay(
                                to_stop.scheduled_departure, to_stop.actual_departure
                            )
                            if to_stop.departed
                            and to_stop.actual_departure
                            and to_stop.scheduled_departure
                            else (
                                calculate_delay(
                                    to_stop.scheduled_arrival, to_stop.actual_arrival
                                )
                                if to_stop.departed
                                and to_stop.actual_arrival
                                and to_stop.scheduled_arrival
                                else 0
                            )
                        ),
                    )
                    if to_stop
                    else None
                ),
                journey=JourneyInfo(
                    origin=journey.origin_station_code,
                    origin_name=(
                        min(
                            journey.stops, key=lambda s: s.stop_sequence or 0
                        ).station_name
                        if journey.stops
                        else journey.origin_station_code or ""
                    ),
                    duration_minutes=(
                        max(
                            0,
                            int(
                                safe_datetime_subtract(
                                    to_stop.scheduled_arrival,
                                    from_stop.scheduled_departure,
                                ).total_seconds()
                                / 60
                            ),
                        )
                        if to_stop
                        and from_stop.scheduled_departure
                        and to_stop.scheduled_arrival
                        else 0
                    ),
                    stops_between=(
                        sum(
                            1
                            for stop in journey.stops
                            if (from_stop.stop_sequence or 0)
                            < (stop.stop_sequence or 0)
                            < (to_stop.stop_sequence or 0)
                        )
                        if to_stop
                        else 0
                    ),
                    progress=JourneyProgress(
                        completed_stops=sum(
                            1
                            for s in sorted(
                                journey.stops, key=lambda s: s.stop_sequence or 0
                            )
                            if s.departed
                            and (s.stop_sequence or 0) <= (from_stop.stop_sequence or 0)
                        ),
                        total_stops=len(journey.stops),
                        percentage=(
                            int(
                                (
                                    sum(
                                        1
                                        for s in sorted(
                                            journey.stops,
                                            key=lambda s: s.stop_sequence or 0,
                                        )
                                        if s.departed
                                        and (s.stop_sequence or 0)
                                        <= (from_stop.stop_sequence or 0)
                                    )
                                    / len(journey.stops)
                                )
                                * 100
                            )
                            if journey.stops
                            else 0
                        ),
                        current_location=journey.origin_station_code,
                        next_stop=None,
                    ),
                ),
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
