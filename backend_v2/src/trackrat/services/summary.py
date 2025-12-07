"""
Operations summary service - Template-based natural language generation for train operations summaries.

Generates brief, human-readable summaries of recent train operations at three scopes:
- Network: Overall system status across all lines
- Route: Performance between specific origin and destination
- Train: Historical performance of a specific train
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.stations import get_station_name
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)

# Fixed time window for summaries (90 minutes as per requirements)
SUMMARY_TIME_WINDOW_MINUTES = 90


@dataclass
class LineStats:
    """Statistics for a single line."""

    line_name: str
    line_code: str
    train_count: int
    on_time_count: int
    cancellation_count: int
    total_delay_minutes: float
    data_source: str

    @property
    def on_time_percentage(self) -> float:
        non_cancelled = self.train_count - self.cancellation_count
        if non_cancelled <= 0:
            return 0.0
        return (self.on_time_count / non_cancelled) * 100

    @property
    def average_delay_minutes(self) -> float:
        non_cancelled = self.train_count - self.cancellation_count
        if non_cancelled <= 0:
            return 0.0
        return self.total_delay_minutes / non_cancelled


@dataclass
class SummaryMetrics:
    """Raw metrics for summary generation."""

    on_time_percentage: float | None = None
    average_delay_minutes: float | None = None
    cancellation_count: int | None = None
    train_count: int | None = None
    most_common_track: str | None = None


@dataclass
class OperationsSummary:
    """Complete operations summary with headline and body."""

    headline: str
    body: str
    scope: Literal["network", "route", "train"]
    time_window_minutes: int
    data_freshness_seconds: int
    generated_at: datetime
    metrics: SummaryMetrics | None = None


class SummaryService:
    """Service for generating operations summaries."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[OperationsSummary, datetime]] = {}
        self._cache_ttl = 300  # 5 minutes cache

    async def get_network_summary(
        self,
        db: AsyncSession,
        data_source: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a network-wide operations summary.

        Args:
            db: Database session
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"network_{data_source or 'all'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_network_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        cutoff_time = now_et() - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query journeys in the time window
        conditions = [
            TrainJourney.last_updated_at >= cutoff_time,
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        stmt = (
            select(TrainJourney)
            .where(and_(*conditions))
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        logger.info(
            "network_summary_query",
            journey_count=len(journeys),
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_source=data_source,
        )

        # Calculate per-line statistics
        line_stats = self._calculate_line_stats(journeys)

        # Generate summary
        summary = self._generate_network_summary(line_stats)

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    async def get_route_summary(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a route-specific operations summary.

        Args:
            db: Database session
            from_station: Origin station code
            to_station: Destination station code
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"route_{from_station}_{to_station}_{data_source or 'all'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_route_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        cutoff_time = now_et() - timedelta(minutes=SUMMARY_TIME_WINDOW_MINUTES)

        # Query journeys that include both stations
        conditions = [
            TrainJourney.last_updated_at >= cutoff_time,
        ]
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_([from_station, to_station]),
                ),
            )
            .where(and_(*conditions))
            .group_by(TrainJourney.id)
            .having(func.count(func.distinct(JourneyStop.station_code)) == 2)
            .options(selectinload(TrainJourney.stops))
        )

        result = await db.execute(stmt)
        all_journeys = list(result.scalars().all())

        # Filter to journeys that actually travel from origin to destination
        route_journeys = []
        for journey in all_journeys:
            from_stop = None
            to_stop = None
            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_stop = stop
                elif stop.station_code == to_station:
                    to_stop = stop

            if (
                from_stop
                and to_stop
                and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
            ):
                route_journeys.append(journey)

        logger.info(
            "route_summary_query",
            journey_count=len(route_journeys),
            from_station=from_station,
            to_station=to_station,
        )

        # Generate summary
        summary = self._generate_route_summary(route_journeys, from_station, to_station)

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    async def get_train_summary(
        self,
        db: AsyncSession,
        train_id: str,
        from_station: str | None = None,
        to_station: str | None = None,
    ) -> OperationsSummary:
        """
        Generate a train-specific operations summary based on historical performance.

        Args:
            db: Database session
            train_id: Train number (e.g., "3847")
            from_station: Optional origin station code for route context
            to_station: Optional destination station code for route context

        Returns:
            OperationsSummary with headline and body
        """
        cache_key = f"train_{train_id}_{from_station or 'any'}_{to_station or 'any'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            age_seconds = (now_et() - timestamp).total_seconds()
            if age_seconds < self._cache_ttl:
                logger.debug(
                    "returning_cached_train_summary",
                    cache_age_seconds=age_seconds,
                )
                return cached_data

        # For train summaries, look back 30 days for historical context
        cutoff_date = now_et().date() - timedelta(days=30)

        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date >= cutoff_date,
                )
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(TrainJourney.journey_date.desc())
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        logger.info(
            "train_summary_query",
            train_id=train_id,
            journey_count=len(journeys),
            days=30,
        )

        # Generate summary
        summary = self._generate_train_summary(
            journeys, train_id, from_station, to_station
        )

        # Cache the result
        self._cache[cache_key] = (summary, now_et())

        return summary

    def _calculate_line_stats(
        self, journeys: list[TrainJourney]
    ) -> dict[str, LineStats]:
        """Calculate statistics grouped by line."""
        stats: dict[str, dict] = defaultdict(
            lambda: {
                "line_name": "",
                "line_code": "",
                "train_count": 0,
                "on_time_count": 0,
                "cancellation_count": 0,
                "total_delay_minutes": 0.0,
                "data_source": "",
            }
        )

        for journey in journeys:
            line_key = journey.line_name or journey.line_code or "Unknown"
            line_data = stats[line_key]

            line_data["line_name"] = journey.line_name or line_key
            line_data["line_code"] = journey.line_code or ""
            line_data["data_source"] = journey.data_source
            line_data["train_count"] += 1

            if journey.is_cancelled:
                line_data["cancellation_count"] += 1
            else:
                # Calculate delay from last stop
                if journey.stops:
                    last_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)
                    if last_stop.actual_arrival and last_stop.scheduled_arrival:
                        delay = (
                            last_stop.actual_arrival - last_stop.scheduled_arrival
                        ).total_seconds() / 60
                        line_data["total_delay_minutes"] += max(0, delay)
                        if delay <= 5:
                            line_data["on_time_count"] += 1
                    else:
                        # No arrival data, assume on time
                        line_data["on_time_count"] += 1

        return {
            key: LineStats(
                line_name=data["line_name"],
                line_code=data["line_code"],
                train_count=data["train_count"],
                on_time_count=data["on_time_count"],
                cancellation_count=data["cancellation_count"],
                total_delay_minutes=data["total_delay_minutes"],
                data_source=data["data_source"],
            )
            for key, data in stats.items()
        }

    def _generate_network_summary(
        self, line_stats: dict[str, LineStats]
    ) -> OperationsSummary:
        """Generate network-wide summary from line statistics."""
        if not line_stats:
            return OperationsSummary(
                headline="No recent train data",
                body="No train operations recorded in the past 90 minutes.",
                scope="network",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Aggregate totals
        total_trains = sum(ls.train_count for ls in line_stats.values())
        total_on_time = sum(ls.on_time_count for ls in line_stats.values())
        total_cancellations = sum(ls.cancellation_count for ls in line_stats.values())
        total_delay = sum(ls.total_delay_minutes for ls in line_stats.values())

        non_cancelled = total_trains - total_cancellations
        on_time_pct = (total_on_time / non_cancelled * 100) if non_cancelled > 0 else 0
        avg_delay = total_delay / non_cancelled if non_cancelled > 0 else 0

        # Generate headline
        headline = self._get_network_headline(
            on_time_pct, avg_delay, total_cancellations
        )

        # Generate body
        body_parts = []

        # Lead sentence
        if on_time_pct >= 85:
            body_parts.append(
                f"Most trains running on time with average delays of {avg_delay:.0f} minutes."
            )
        elif on_time_pct >= 70:
            body_parts.append(
                f"Some delays across the network. {on_time_pct:.0f}% of trains on schedule, "
                f"averaging {avg_delay:.0f} minute delays."
            )
        else:
            body_parts.append(
                f"Widespread delays today. Only {on_time_pct:.0f}% of trains running on time, "
                f"with delays averaging {avg_delay:.0f} minutes."
            )

        # Per-line breakdown for lines with issues
        problem_lines = [
            ls
            for ls in line_stats.values()
            if ls.cancellation_count > 0 or ls.average_delay_minutes > 10
        ]

        if problem_lines:
            for ls in sorted(
                problem_lines, key=lambda x: x.cancellation_count, reverse=True
            )[:2]:
                if ls.cancellation_count > 0:
                    body_parts.append(
                        f"{ls.line_name}: {ls.cancellation_count} cancellation(s), "
                        f"averaging {ls.average_delay_minutes:.0f} min delays."
                    )
                elif ls.average_delay_minutes > 10:
                    body_parts.append(
                        f"{ls.line_name}: averaging {ls.average_delay_minutes:.0f} min delays."
                    )

        body = " ".join(body_parts)

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="network",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=now_et(),
            metrics=SummaryMetrics(
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
                cancellation_count=total_cancellations,
                train_count=total_trains,
            ),
        )

    def _get_network_headline(
        self, on_time_pct: float, avg_delay: float, cancellations: int
    ) -> str:
        """Generate a concise headline based on network status."""
        if on_time_pct >= 95 and avg_delay < 3:
            return "Trains running smoothly"
        elif on_time_pct >= 85 and avg_delay < 6:
            return "Trains mostly on time"
        elif on_time_pct >= 70 and avg_delay < 10:
            return "Some delays across network"
        elif on_time_pct >= 50:
            return "Widespread delays today"
        else:
            return "Major disruptions"

    def _generate_route_summary(
        self,
        journeys: list[TrainJourney],
        from_station: str,
        to_station: str,
    ) -> OperationsSummary:
        """Generate route-specific summary."""
        from_name = get_station_name(from_station)
        to_name = get_station_name(to_station)

        if not journeys:
            return OperationsSummary(
                headline=f"{from_name} to {to_name}: No data",
                body=f"No trains have completed this route in the past 90 minutes.",
                scope="route",
                time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Calculate statistics
        on_time_count = 0
        cancellation_count = 0
        total_delay = 0.0
        track_counts: dict[str, int] = defaultdict(int)
        late_trains: list[tuple[str, float]] = []

        for journey in journeys:
            if journey.is_cancelled:
                cancellation_count += 1
                continue

            # Find the destination stop for delay calculation
            to_stop = None
            from_stop_data = None
            for stop in journey.stops:
                if stop.station_code == to_station:
                    to_stop = stop
                if stop.station_code == from_station:
                    from_stop_data = stop

            # Track usage at origin
            if from_stop_data and from_stop_data.track:
                track_counts[from_stop_data.track] += 1

            if to_stop and to_stop.actual_arrival and to_stop.scheduled_arrival:
                delay = (
                    to_stop.actual_arrival - to_stop.scheduled_arrival
                ).total_seconds() / 60
                delay = max(0, delay)
                total_delay += delay
                if delay <= 5:
                    on_time_count += 1
                elif delay > 10:
                    late_trains.append((journey.train_id, delay))
            else:
                on_time_count += 1

        non_cancelled = len(journeys) - cancellation_count
        on_time_pct = (on_time_count / non_cancelled * 100) if non_cancelled > 0 else 0
        avg_delay = total_delay / non_cancelled if non_cancelled > 0 else 0

        # Most common track
        most_common_track = (
            max(track_counts, key=track_counts.get) if track_counts else None
        )

        # Generate headline
        headline = f"{from_name} to {to_name}: {on_time_pct:.0f}% on time"

        # Generate body
        body_parts = []
        body_parts.append(
            f"{len(journeys)} train(s) have completed this route in the past 90 minutes."
        )

        if non_cancelled > 0:
            body_parts.append(f"{on_time_count} arrived within 5 minutes of schedule.")

        if late_trains:
            worst = max(late_trains, key=lambda x: x[1])
            body_parts.append(f"Train {worst[0]} ran {worst[1]:.0f} minutes late.")

        if most_common_track:
            body_parts.append(
                f"Track {most_common_track} has been the most common departure track."
            )

        body = " ".join(body_parts)

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="route",
            time_window_minutes=SUMMARY_TIME_WINDOW_MINUTES,
            data_freshness_seconds=0,
            generated_at=now_et(),
            metrics=SummaryMetrics(
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
                cancellation_count=cancellation_count,
                train_count=len(journeys),
                most_common_track=most_common_track,
            ),
        )

    def _generate_train_summary(
        self,
        journeys: list[TrainJourney],
        train_id: str,
        from_station: str | None,
        to_station: str | None,
    ) -> OperationsSummary:
        """Generate train-specific summary based on 30-day history."""
        if not journeys:
            return OperationsSummary(
                headline="No historical data",
                body=f"No historical data available for Train {train_id}.",
                scope="train",
                time_window_minutes=30 * 24 * 60,  # 30 days in minutes
                data_freshness_seconds=0,
                generated_at=now_et(),
                metrics=None,
            )

        # Calculate historical performance
        on_time_count = 0
        total_delay = 0.0
        delay_samples = 0
        station_delays: dict[str, list[float]] = defaultdict(list)

        for journey in journeys:
            if journey.is_cancelled:
                continue

            # Calculate overall delay
            if journey.stops:
                last_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)
                if last_stop.actual_arrival and last_stop.scheduled_arrival:
                    delay = (
                        last_stop.actual_arrival - last_stop.scheduled_arrival
                    ).total_seconds() / 60
                    delay = max(0, delay)
                    total_delay += delay
                    delay_samples += 1
                    if delay <= 5:
                        on_time_count += 1

                # Track per-station delays
                for stop in journey.stops:
                    if stop.actual_arrival and stop.scheduled_arrival:
                        stop_delay = (
                            stop.actual_arrival - stop.scheduled_arrival
                        ).total_seconds() / 60
                        station_delays[stop.station_code].append(stop_delay)

        on_time_pct = (on_time_count / delay_samples * 100) if delay_samples > 0 else 0
        avg_delay = total_delay / delay_samples if delay_samples > 0 else 0

        # Find problem stations (where delays typically occur)
        problem_stations = []
        for station_code, delays in station_delays.items():
            avg_station_delay = sum(delays) / len(delays)
            if avg_station_delay > 3 and len(delays) >= 3:
                problem_stations.append((station_code, avg_station_delay))
        problem_stations.sort(key=lambda x: x[1], reverse=True)

        # Generate headline based on on-time percentage (primary) and average delay (secondary)
        if on_time_pct >= 90:
            headline = "Usually runs on time"
        elif on_time_pct >= 75:
            headline = f"Usually runs {avg_delay:.0f} min late"
        else:
            headline = f"Often runs {avg_delay:.0f}+ min late"

        # Generate body
        body_parts = []
        body_parts.append(
            f"Over the past 30 days, Train {train_id} has been on time {on_time_pct:.0f}% of the time."
        )

        if problem_stations:
            worst_station = problem_stations[0]
            station_name = get_station_name(worst_station[0])
            body_parts.append(f"It tends to pick up delays around {station_name}.")

        # Check today's status
        today = now_et().date()
        today_journey = next((j for j in journeys if j.journey_date == today), None)
        if today_journey:
            if today_journey.is_cancelled:
                body_parts.append("Today's service was cancelled.")
            elif today_journey.stops:
                first_stop = min(
                    today_journey.stops, key=lambda s: s.stop_sequence or 0
                )
                if first_stop.actual_departure and first_stop.scheduled_departure:
                    dep_delay = (
                        first_stop.actual_departure - first_stop.scheduled_departure
                    ).total_seconds() / 60
                    if dep_delay > 1:
                        body_parts.append(
                            f"Today it departed {dep_delay:.0f} minutes late."
                        )
                    elif dep_delay < -1:
                        body_parts.append("Today it departed on time.")

        body = " ".join(body_parts)

        return OperationsSummary(
            headline=headline,
            body=body,
            scope="train",
            time_window_minutes=30 * 24 * 60,  # 30 days in minutes
            data_freshness_seconds=0,
            generated_at=now_et(),
            metrics=SummaryMetrics(
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
                train_count=len(journeys),
            ),
        )
