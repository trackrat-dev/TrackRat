"""
Transit time analysis service for TrackRat.

Analyzes journey data to calculate segment transit times and station dwell times.
"""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from structlog import get_logger

from trackrat.models import (
    JourneyProgress,
    JourneyStop,
    SegmentTransitTime,
    StationDwellTime,
    TrainJourney,
)
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)


class TransitAnalyzer:
    """Analyzes transit times and station dwell times from journey data."""

    async def analyze_journey(self, db: AsyncSession, journey: TrainJourney) -> None:
        """
        Analyze and store transit metrics for a journey.

        This is typically called after a journey's data has been collected.
        It calculates segment transit times, station dwell times, and journey progress.

        Args:
            db: Database session
            journey: The journey to analyze
        """
        # Query stops directly to avoid lazy loading issues
        stops_stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        result = await db.execute(stops_stmt)
        stops = list(result.scalars().all())

        if not stops:
            logger.debug("no_stops_to_analyze", journey_id=journey.id)
            return
        if len(stops) < 2:
            logger.debug(
                "insufficient_stops", journey_id=journey.id, stop_count=len(stops)
            )
            return

        # Analyze segment transit times
        await self._analyze_segments(db, journey, stops, check_duplicates=False)

        # Analyze station dwell times
        await self._analyze_dwell_times(db, journey, stops)

        # Update journey progress
        await self._update_journey_progress(db, journey, stops)

        logger.info(
            "journey_analysis_complete",
            journey_id=journey.id,
            train_id=journey.train_id,
            stop_count=len(stops),
        )

    async def analyze_new_segments(
        self, db: AsyncSession, journey: TrainJourney
    ) -> int:
        """
        Analyze only new segments that have completed since last analysis.
        This is designed to be called frequently during journey updates.

        Returns:
            Number of new segments created
        """
        # Query stops directly to avoid lazy loading issues
        stops_stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        result = await db.execute(stops_stmt)
        stops = list(result.scalars().all())

        if len(stops) < 2:
            return 0

        return await self._analyze_segments(db, journey, stops, check_duplicates=True)

    async def _analyze_segments(
        self,
        db: AsyncSession,
        journey: TrainJourney,
        stops: list[JourneyStop],
        check_duplicates: bool = False,
    ) -> int:
        """Calculate and store transit times between consecutive stations.

        Args:
            db: Database session
            journey: Journey to analyze
            stops: List of journey stops
            check_duplicates: If True, check if segment already exists before creating

        Returns:
            Number of segments created
        """
        segments_created = 0

        for i in range(len(stops) - 1):
            current_stop = stops[i]
            next_stop = stops[i + 1]

            # Use actual times when available, fall back to scheduled times (COALESCE logic)
            departure_time = current_stop.actual_departure or current_stop.scheduled_departure
            arrival_time = next_stop.actual_arrival or next_stop.scheduled_arrival
            
            # Skip if we don't have ANY times at all
            if not (departure_time and arrival_time):
                continue

            # Check if segment already exists (to avoid duplicates)
            if check_duplicates:
                exists_stmt = select(SegmentTransitTime).where(
                    and_(
                        SegmentTransitTime.journey_id == journey.id,
                        SegmentTransitTime.from_station_code
                        == current_stop.station_code,
                        SegmentTransitTime.to_station_code == next_stop.station_code,
                    )
                )
                result = await db.execute(exists_stmt)
                if result.scalar():
                    continue  # Skip if already analyzed

            # Calculate scheduled transit time
            scheduled_minutes = None
            if current_stop.scheduled_departure and next_stop.scheduled_arrival:
                scheduled_delta = ensure_timezone_aware(
                    next_stop.scheduled_arrival
                ) - ensure_timezone_aware(current_stop.scheduled_departure)
                scheduled_minutes = int(scheduled_delta.total_seconds() / 60)

            # Calculate actual transit time using COALESCE variables
            actual_delta = ensure_timezone_aware(arrival_time) - ensure_timezone_aware(departure_time)
            actual_minutes = int(actual_delta.total_seconds() / 60)

            # Skip invalid times (negative or unreasonably long)
            if actual_minutes <= 0 or actual_minutes > 300:
                logger.warning(
                    "invalid_transit_time",
                    journey_id=journey.id,
                    segment=f"{current_stop.station_code}-{next_stop.station_code}",
                    minutes=actual_minutes,
                )
                continue

            # Create segment record
            segment = SegmentTransitTime(
                journey_id=journey.id,
                from_station_code=current_stop.station_code,
                to_station_code=next_stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_minutes or actual_minutes,
                actual_minutes=actual_minutes,
                delay_minutes=actual_minutes - (scheduled_minutes or actual_minutes),
                departure_time=ensure_timezone_aware(departure_time),
                hour_of_day=ensure_timezone_aware(departure_time).hour,
                day_of_week=ensure_timezone_aware(departure_time).weekday(),
            )

            db.add(segment)
            segments_created += 1

        if segments_created > 0:
            logger.debug(
                "segments_analyzed",
                journey_id=journey.id,
                segments_created=segments_created,
            )

        return segments_created

    async def _analyze_dwell_times(
        self, db: AsyncSession, journey: TrainJourney, stops: list[JourneyStop]
    ) -> None:
        """Calculate and store station dwell times."""
        dwell_times_created = 0

        for i, stop in enumerate(stops):
            # For origin station, measure delay from scheduled to actual departure
            if i == 0:
                if stop.actual_departure and stop.scheduled_departure:
                    delay = int(
                        (
                            ensure_timezone_aware(stop.actual_departure)
                            - ensure_timezone_aware(stop.scheduled_departure)
                        ).total_seconds()
                        / 60
                    )

                    dwell = StationDwellTime(
                        journey_id=journey.id,
                        station_code=stop.station_code,
                        data_source=journey.data_source,
                        line_code=journey.line_code,
                        scheduled_minutes=0,
                        actual_minutes=max(
                            0, delay
                        ),  # Don't record negative delays as dwell
                        excess_dwell_minutes=delay,
                        is_origin=True,
                        departure_time=ensure_timezone_aware(stop.actual_departure),
                        hour_of_day=ensure_timezone_aware(stop.actual_departure).hour,
                        day_of_week=ensure_timezone_aware(
                            stop.actual_departure
                        ).weekday(),
                    )
                    db.add(dwell)
                    dwell_times_created += 1
                continue

            # For other stations, calculate actual dwell time
            if not (stop.actual_arrival and stop.actual_departure):
                continue

            actual_dwell_delta = ensure_timezone_aware(
                stop.actual_departure
            ) - ensure_timezone_aware(stop.actual_arrival)
            actual_dwell = int(actual_dwell_delta.total_seconds() / 60)

            # Skip invalid dwell times
            if actual_dwell < 0 or actual_dwell > 180:  # Max 3 hours dwell
                logger.warning(
                    "invalid_dwell_time",
                    journey_id=journey.id,
                    station=stop.station_code,
                    minutes=actual_dwell,
                )
                continue

            # Calculate scheduled dwell if available
            scheduled_dwell = None
            if stop.scheduled_arrival and stop.scheduled_departure:
                scheduled_dwell_delta = ensure_timezone_aware(
                    stop.scheduled_departure
                ) - ensure_timezone_aware(stop.scheduled_arrival)
                scheduled_dwell = int(scheduled_dwell_delta.total_seconds() / 60)

            excess_dwell = actual_dwell - (scheduled_dwell or 0)

            dwell = StationDwellTime(
                journey_id=journey.id,
                station_code=stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_dwell,
                actual_minutes=actual_dwell,
                excess_dwell_minutes=excess_dwell,
                is_terminal=(i == len(stops) - 1),
                arrival_time=ensure_timezone_aware(stop.actual_arrival),
                departure_time=ensure_timezone_aware(stop.actual_departure),
                hour_of_day=ensure_timezone_aware(stop.actual_departure).hour,
                day_of_week=ensure_timezone_aware(stop.actual_departure).weekday(),
            )
            db.add(dwell)
            dwell_times_created += 1

        if dwell_times_created > 0:
            logger.debug(
                "dwell_times_analyzed",
                journey_id=journey.id,
                dwell_times_created=dwell_times_created,
            )

    async def _update_journey_progress(
        self, db: AsyncSession, journey: TrainJourney, stops: list[JourneyStop]
    ) -> None:
        """Create a journey progress snapshot."""
        # Find current position
        last_departed_station = None
        next_station = None
        stops_completed = 0

        for i, stop in enumerate(stops):
            if stop.has_departed_station:
                last_departed_station = stop.station_code
                stops_completed = i + 1
            else:
                # For actual departure comparison, handle timezone awareness
                if stop.actual_departure:
                    current_time = now_et()
                    # Ensure both datetimes are timezone-aware
                    actual_dep = ensure_timezone_aware(stop.actual_departure)
                    if actual_dep <= current_time:
                        last_departed_station = stop.station_code
                        stops_completed = i + 1
                        continue

                next_station = stop.station_code
                break

        # If all stops have been departed, we're at the terminal
        if stops_completed == len(stops):
            next_station = None

        # Calculate journey percentage
        journey_percent: float = (stops_completed / len(stops)) * 100 if stops else 0.0

        # Calculate delays
        initial_delay_minutes = 0
        if stops and stops[0].actual_departure and stops[0].scheduled_departure:
            initial_delay_minutes = int(
                (
                    ensure_timezone_aware(stops[0].actual_departure)
                    - ensure_timezone_aware(stops[0].scheduled_departure)
                ).total_seconds()
                / 60
            )

        # Sum up transit and dwell delays (simplified for now)
        total_delay = initial_delay_minutes
        if stops and stops[-1].scheduled_arrival:
            last_stop = stops[-1]
            if last_stop.actual_arrival and last_stop.scheduled_arrival:
                arrival_delay = int(
                    (
                        ensure_timezone_aware(last_stop.actual_arrival)
                        - ensure_timezone_aware(last_stop.scheduled_arrival)
                    ).total_seconds()
                    / 60
                )
                total_delay = arrival_delay
            elif last_stop.updated_arrival and last_stop.scheduled_arrival:
                arrival_delay = int(
                    (
                        ensure_timezone_aware(last_stop.updated_arrival)
                        - ensure_timezone_aware(last_stop.scheduled_arrival)
                    ).total_seconds()
                    / 60
                )
                total_delay = arrival_delay

        # Create progress record
        progress = JourneyProgress(
            journey_id=journey.id,
            last_departed_station=last_departed_station,
            next_station=next_station,
            stops_completed=stops_completed,
            stops_total=len(stops),
            journey_percent=journey_percent,  # type: ignore[arg-type]
            initial_delay_minutes=initial_delay_minutes,
            cumulative_transit_delay=0,  # Will be calculated in phase 2
            cumulative_dwell_delay=0,  # Will be calculated in phase 2
            total_delay_minutes=total_delay,
        )

        db.add(progress)

        logger.debug(
            "journey_progress_updated",
            journey_id=journey.id,
            stops_completed=stops_completed,
            stops_total=len(stops),
            journey_percent=journey_percent,
        )

    def analyze_journey_sync(self, db: Session, journey: TrainJourney) -> None:
        """
        Synchronous version of analyze_journey for use in scheduler.

        This method is used by the NJT synchronous collection path to avoid
        greenlet/async issues in APScheduler contexts.

        Args:
            db: Synchronous database session
            journey: The journey to analyze
        """
        # Query stops directly
        stops_stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        result = db.execute(stops_stmt)
        stops = list(result.scalars().all())

        if not stops:
            logger.debug("no_stops_to_analyze_sync", journey_id=journey.id)
            return
        if len(stops) < 2:
            logger.debug(
                "insufficient_stops_sync", journey_id=journey.id, stop_count=len(stops)
            )
            return

        # Analyze segment transit times
        self._analyze_segments_sync(db, journey, stops)

        # Analyze station dwell times
        self._analyze_dwell_times_sync(db, journey, stops)

        # Update journey progress
        self._update_journey_progress_sync(db, journey, stops)

        logger.info(
            "journey_analysis_complete_sync",
            journey_id=journey.id,
            train_id=journey.train_id,
            stop_count=len(stops),
        )

    def _analyze_segments_sync(
        self, db: Session, journey: TrainJourney, stops: list[JourneyStop]
    ) -> None:
        """Synchronous version of _analyze_segments."""
        segments_created = 0

        for i in range(len(stops) - 1):
            current_stop = stops[i]
            next_stop = stops[i + 1]

            # Use actual times when available, fall back to scheduled times (COALESCE logic)
            departure_time = current_stop.actual_departure or current_stop.scheduled_departure
            arrival_time = next_stop.actual_arrival or next_stop.scheduled_arrival
            
            # Skip if we don't have ANY times at all
            if not (departure_time and arrival_time):
                continue

            # Calculate scheduled transit time
            scheduled_minutes = None
            if current_stop.scheduled_departure and next_stop.scheduled_arrival:
                scheduled_delta = ensure_timezone_aware(
                    next_stop.scheduled_arrival
                ) - ensure_timezone_aware(current_stop.scheduled_departure)
                scheduled_minutes = int(scheduled_delta.total_seconds() / 60)

            # Calculate actual transit time using COALESCE variables
            actual_delta = ensure_timezone_aware(arrival_time) - ensure_timezone_aware(departure_time)
            actual_minutes = int(actual_delta.total_seconds() / 60)

            # Skip invalid times (negative or unreasonably long)
            if actual_minutes <= 0 or actual_minutes > 300:
                logger.warning(
                    "invalid_transit_time_sync",
                    journey_id=journey.id,
                    segment=f"{current_stop.station_code}-{next_stop.station_code}",
                    minutes=actual_minutes,
                )
                continue

            # Create segment record
            segment = SegmentTransitTime(
                journey_id=journey.id,
                from_station_code=current_stop.station_code,
                to_station_code=next_stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_minutes or actual_minutes,
                actual_minutes=actual_minutes,
                delay_minutes=actual_minutes - (scheduled_minutes or actual_minutes),
                departure_time=ensure_timezone_aware(departure_time),
                hour_of_day=ensure_timezone_aware(departure_time).hour,
                day_of_week=ensure_timezone_aware(departure_time).weekday(),
            )

            db.add(segment)
            segments_created += 1

        if segments_created > 0:
            logger.debug(
                "segments_analyzed_sync",
                journey_id=journey.id,
                segments_created=segments_created,
            )

    def _analyze_dwell_times_sync(
        self, db: Session, journey: TrainJourney, stops: list[JourneyStop]
    ) -> None:
        """Synchronous version of _analyze_dwell_times."""
        dwell_times_created = 0

        for i, stop in enumerate(stops):
            # For origin station, measure delay from scheduled to actual departure
            if i == 0:
                if stop.actual_departure and stop.scheduled_departure:
                    delay = int(
                        (
                            ensure_timezone_aware(stop.actual_departure)
                            - ensure_timezone_aware(stop.scheduled_departure)
                        ).total_seconds()
                        / 60
                    )

                    dwell = StationDwellTime(
                        journey_id=journey.id,
                        station_code=stop.station_code,
                        data_source=journey.data_source,
                        line_code=journey.line_code,
                        scheduled_minutes=0,
                        actual_minutes=max(
                            0, delay
                        ),  # Don't record negative delays as dwell
                        excess_dwell_minutes=delay,
                        is_origin=True,
                        departure_time=ensure_timezone_aware(stop.actual_departure),
                        hour_of_day=ensure_timezone_aware(stop.actual_departure).hour,
                        day_of_week=ensure_timezone_aware(
                            stop.actual_departure
                        ).weekday(),
                    )
                    db.add(dwell)
                    dwell_times_created += 1
                continue

            # For other stations, calculate actual dwell time
            if not (stop.actual_arrival and stop.actual_departure):
                continue

            actual_dwell_delta = ensure_timezone_aware(
                stop.actual_departure
            ) - ensure_timezone_aware(stop.actual_arrival)
            actual_dwell = int(actual_dwell_delta.total_seconds() / 60)

            # Skip invalid dwell times
            if actual_dwell < 0 or actual_dwell > 180:  # Max 3 hours dwell
                logger.warning(
                    "invalid_dwell_time_sync",
                    journey_id=journey.id,
                    station=stop.station_code,
                    minutes=actual_dwell,
                )
                continue

            # Calculate scheduled dwell if available
            scheduled_dwell = None
            if stop.scheduled_arrival and stop.scheduled_departure:
                scheduled_dwell_delta = ensure_timezone_aware(
                    stop.scheduled_departure
                ) - ensure_timezone_aware(stop.scheduled_arrival)
                scheduled_dwell = int(scheduled_dwell_delta.total_seconds() / 60)

            excess_dwell = actual_dwell - (scheduled_dwell or 0)

            dwell = StationDwellTime(
                journey_id=journey.id,
                station_code=stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_dwell,
                actual_minutes=actual_dwell,
                excess_dwell_minutes=excess_dwell,
                is_terminal=(i == len(stops) - 1),
                arrival_time=ensure_timezone_aware(stop.actual_arrival),
                departure_time=ensure_timezone_aware(stop.actual_departure),
                hour_of_day=ensure_timezone_aware(stop.actual_departure).hour,
                day_of_week=ensure_timezone_aware(stop.actual_departure).weekday(),
            )
            db.add(dwell)
            dwell_times_created += 1

        if dwell_times_created > 0:
            logger.debug(
                "dwell_times_analyzed_sync",
                journey_id=journey.id,
                dwell_times_created=dwell_times_created,
            )

    def _update_journey_progress_sync(
        self, db: Session, journey: TrainJourney, stops: list[JourneyStop]
    ) -> None:
        """Synchronous version of _update_journey_progress."""
        # Find current position
        last_departed_station = None
        next_station = None
        stops_completed = 0

        for i, stop in enumerate(stops):
            if stop.has_departed_station:
                last_departed_station = stop.station_code
                stops_completed = i + 1
            else:
                # For actual departure comparison, handle timezone awareness
                if stop.actual_departure:
                    current_time = now_et()
                    # Ensure both datetimes are timezone-aware
                    actual_dep = ensure_timezone_aware(stop.actual_departure)
                    if actual_dep <= current_time:
                        last_departed_station = stop.station_code
                        stops_completed = i + 1
                        continue

                next_station = stop.station_code
                break

        # If all stops have been departed, we're at the terminal
        if stops_completed == len(stops):
            next_station = None

        # Calculate journey percentage
        journey_percent: float = (stops_completed / len(stops)) * 100 if stops else 0.0

        # Calculate delays
        initial_delay_minutes = 0
        if stops and stops[0].actual_departure and stops[0].scheduled_departure:
            initial_delay_minutes = int(
                (
                    ensure_timezone_aware(stops[0].actual_departure)
                    - ensure_timezone_aware(stops[0].scheduled_departure)
                ).total_seconds()
                / 60
            )

        # Sum up transit and dwell delays (simplified for now)
        total_delay = initial_delay_minutes
        if stops and stops[-1].scheduled_arrival:
            last_stop = stops[-1]
            if last_stop.actual_arrival and last_stop.scheduled_arrival:
                arrival_delay = int(
                    (
                        ensure_timezone_aware(last_stop.actual_arrival)
                        - ensure_timezone_aware(last_stop.scheduled_arrival)
                    ).total_seconds()
                    / 60
                )
                total_delay = arrival_delay
            elif last_stop.updated_arrival and last_stop.scheduled_arrival:
                arrival_delay = int(
                    (
                        ensure_timezone_aware(last_stop.updated_arrival)
                        - ensure_timezone_aware(last_stop.scheduled_arrival)
                    ).total_seconds()
                    / 60
                )
                total_delay = arrival_delay

        # Create progress record
        progress = JourneyProgress(
            journey_id=journey.id,
            last_departed_station=last_departed_station,
            next_station=next_station,
            stops_completed=stops_completed,
            stops_total=len(stops),
            journey_percent=journey_percent,  # type: ignore[arg-type]
            initial_delay_minutes=initial_delay_minutes,
            cumulative_transit_delay=0,  # Will be calculated in phase 2
            cumulative_dwell_delay=0,  # Will be calculated in phase 2
            total_delay_minutes=total_delay,
        )

        db.add(progress)

        logger.debug(
            "journey_progress_updated_sync",
            journey_id=journey.id,
            stops_completed=stops_completed,
            stops_total=len(stops),
            journey_percent=journey_percent,
        )
