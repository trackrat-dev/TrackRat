"""
Route congestion analysis service - On-the-fly calculation from journey data.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.models.database import TrainJourney
from trackrat.services.congestion_types import (
    CONGESTION_THRESHOLD_HEAVY,
    CONGESTION_THRESHOLD_MODERATE,
    CONGESTION_THRESHOLD_NORMAL,
    FREQ_THRESHOLD_HEALTHY,
    FREQ_THRESHOLD_MODERATE,
    FREQ_THRESHOLD_REDUCED,
    SegmentCongestion,
    get_congestion_level,
    get_frequency_level,
)
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger(__name__)


# Data sources with real-time data (frequency metrics are meaningful)
REALTIME_SOURCES = {
    "NJT",
    "AMTRAK",
    "PATH",
    "LIRR",
    "MNR",
    "SUBWAY",
    "METRA",
    "WMATA",
    "BART",
    "MBTA",
}


# Re-export for backward compatibility
__all__ = [
    "SegmentCongestion",
    "get_congestion_level",
    "get_frequency_level",
    "CongestionAnalyzer",
    "CONGESTION_THRESHOLD_NORMAL",
    "CONGESTION_THRESHOLD_MODERATE",
    "CONGESTION_THRESHOLD_HEAVY",
    "FREQ_THRESHOLD_HEALTHY",
    "FREQ_THRESHOLD_MODERATE",
    "FREQ_THRESHOLD_REDUCED",
    "REALTIME_SOURCES",
]


class CongestionAnalyzer:
    """Analyzes route congestion in real-time from journey data."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[list[SegmentCongestion], datetime]] = {}
        self._cache_ttl = 300  # 5 minutes cache

    async def get_network_congestion_with_trains(
        self,
        db: AsyncSession,
        time_window_hours: int = 3,
        max_per_segment: int = 100,
        data_source: str | None = None,
    ) -> tuple[list[SegmentCongestion], list[TrainJourney], list[Any]]:
        """
        Get congestion data, train journeys, and individual journey segments.

        This optimized version uses database aggregation for congestion calculation
        while still providing journey data for train positions.

        Args:
            db: Database session
            time_window_hours: How many hours to look back
            max_per_segment: Maximum segments per route (0 = unlimited)
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            Tuple of (aggregated segments, train journeys, individual segments)
        """

        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # OPTIMIZATION: Use database aggregation for congestion segments
        aggregated_segments = await self.get_network_congestion_optimized(
            db, time_window_hours, data_source
        )

        # Load journeys with minimal data - we'll get current positions separately
        # Only load active journeys (not cancelled, expired, or completed)
        conditions = [
            TrainJourney.last_updated_at >= cutoff_time,
            TrainJourney.is_cancelled.is_not(True),
            TrainJourney.is_expired.is_not(True),
            TrainJourney.is_completed.is_not(True),
        ]

        # Add data_source filter if specified
        if data_source:
            conditions.append(TrainJourney.data_source == data_source)

        # OPTIMIZATION: Don't load stops here - they're not needed for basic journey info
        # We only need stops for current position, which we'll load separately below
        stmt = (
            select(TrainJourney)
            .where(and_(*conditions))
            .options(selectinload(TrainJourney.progress))
        )

        # Execute with performance logging
        query_start = now_et()
        result = await db.execute(stmt)
        journeys = list(result.scalars().all())
        query_duration_ms = (now_et() - query_start).total_seconds() * 1000

        if query_duration_ms > 100:
            logger.warning(
                "slow_journey_load_query",
                duration_ms=round(query_duration_ms, 2),
                journey_count=len(journeys),
                data_source=data_source,
            )
        else:
            logger.debug(
                "journey_load_completed",
                duration_ms=round(query_duration_ms, 2),
                journey_count=len(journeys),
            )

        # OPTIMIZATION: Load current positions for all journeys in a single efficient query
        # This replaces N queries (one per journey) with 1 query
        if journeys:
            await self._load_current_positions(db, journeys)

        # Use SQL-based individual segments calculation for better performance and accuracy
        individual_segments = []
        if max_per_segment > 0:  # positive means limited; 0 or negative means skip
            individual_segments = await self.get_individual_segments_optimized(
                db, time_window_hours, max_per_segment, data_source
            )

        return aggregated_segments, journeys, individual_segments

    async def get_network_congestion(
        self, db: AsyncSession, time_window_hours: int = 3
    ) -> list[SegmentCongestion]:
        """
        Get congestion data calculated on-the-fly from journey data.

        Args:
            db: Database session
            time_window_hours: How many hours to look back

        Returns:
            List of segment congestion data
        """
        # Check cache first
        cache_key = f"congestion_{time_window_hours}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if (now_et() - timestamp).total_seconds() < self._cache_ttl:
                logger.debug(
                    "returning_cached_congestion_data",
                    cache_age_seconds=(now_et() - timestamp).total_seconds(),
                )
                return cached_data

        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # Query journeys in the time window (including cancelled ones for stats)
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.last_updated_at >= cutoff_time,
                    # Include all journeys to capture cancellations
                )
            )
            .options(
                selectinload(TrainJourney.stops), selectinload(TrainJourney.progress)
            )
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().all())

        logger.info(
            "queried_journeys_for_congestion",
            journey_count=len(journeys),
            time_window_hours=time_window_hours,
            cutoff_time=cutoff_time.isoformat(),
        )

        # Calculate segments from journey data (separate active and cancelled)
        segment_data, cancellation_data = self._calculate_segments_from_journeys(
            journeys, cutoff_time
        )

        # Analyze congestion for each segment
        congestion_results = self._analyze_segment_congestion(
            segment_data, cancellation_data
        )

        # Cache the results
        self._cache[cache_key] = (congestion_results, now_et())

        logger.info(
            "network_congestion_calculated_on_the_fly",
            segment_count=len(congestion_results),
            time_window_hours=time_window_hours,
            total_journeys=len(journeys),
            unique_segment_groups=len(segment_data),
        )

        return congestion_results

    async def _load_current_positions(
        self, db: AsyncSession, journeys: list[TrainJourney]
    ) -> None:
        """
        Load current positions (latest departed stop) for all journeys in a single query.

        This method efficiently loads the most recent stop with an actual departure
        for each journey, avoiding the N+1 query problem that would occur if we
        loaded all stops for each journey.

        Args:
            db: Database session
            journeys: List of journey objects to populate with current position
        """
        from dataclasses import dataclass

        # Get journey IDs
        journey_ids = [j.id for j in journeys]

        if not journey_ids:
            return

        # Single query to get the latest departed stop for each journey
        # Uses DISTINCT ON to get one row per journey_id (the most recent)
        query = text("""
            SELECT DISTINCT ON (journey_id)
                journey_id,
                station_code,
                station_name,
                stop_sequence,
                scheduled_departure,
                scheduled_arrival,
                actual_departure,
                actual_arrival,
                track,
                has_departed_station,
                raw_amtrak_status
            FROM journey_stops
            WHERE journey_id = ANY(:journey_ids)
                AND actual_departure IS NOT NULL
            ORDER BY journey_id, actual_departure DESC NULLS LAST
            """)

        result = await db.execute(query, {"journey_ids": journey_ids})
        rows = result.fetchall()

        # Create a simple dataclass to hold stop data without SQLAlchemy machinery
        @dataclass
        class SimpleStop:
            journey_id: int
            station_code: str
            station_name: str
            stop_sequence: int | None
            scheduled_departure: datetime | None
            scheduled_arrival: datetime | None
            actual_departure: datetime | None
            actual_arrival: datetime | None
            track: str | None
            has_departed_station: bool
            raw_amtrak_status: str | None

        # Create a map of journey_id -> current position data
        position_map: dict[int, SimpleStop] = {}
        for row in rows:
            position_map[row.journey_id] = SimpleStop(
                journey_id=row.journey_id,
                station_code=row.station_code,
                station_name=row.station_name,
                stop_sequence=row.stop_sequence,
                scheduled_departure=row.scheduled_departure,
                scheduled_arrival=row.scheduled_arrival,
                actual_departure=row.actual_departure,
                actual_arrival=row.actual_arrival,
                track=row.track,
                has_departed_station=row.has_departed_station,
                raw_amtrak_status=row.raw_amtrak_status,
            )

        # Populate each journey's stops list with just the current position
        # Using a simple dataclass instead of ORM object to avoid greenlet issues
        # Use set_committed_value to tell SQLAlchemy the relationship is already loaded
        from sqlalchemy.orm.attributes import set_committed_value

        for journey in journeys:
            if journey.id in position_map:
                stops_list = [position_map[journey.id]]
            else:
                # No departed stops yet - empty list
                stops_list = []

            # Use set_committed_value to mark the relationship as loaded
            # This prevents SQLAlchemy from trying to lazy-load in async context
            # Check if it's a real SQLAlchemy instance (not a Mock in tests)
            if hasattr(journey, "_sa_instance_state"):
                set_committed_value(journey, "stops", stops_list)  # type: ignore[no-untyped-call]
            else:
                # Fallback for tests with Mock objects
                journey.stops = stops_list  # type: ignore[assignment]

        logger.debug(
            "loaded_current_positions",
            journey_count=len(journeys),
            positions_found=len(position_map),
        )

    async def get_network_congestion_optimized(
        self,
        db: AsyncSession,
        time_window_hours: int = 3,
        data_source: str | None = None,
    ) -> list[SegmentCongestion]:
        """
        Optimized congestion calculation using database-level aggregation.

        This method calculates congestion directly in PostgreSQL instead of
        loading all journey data into memory, significantly reducing response time.

        Args:
            db: Database session
            time_window_hours: How many hours to look back
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            List of segment congestion data
        """
        # Check cache first (include data_source in cache key)
        cache_key = f"congestion_{time_window_hours}_{data_source or 'all'}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if (now_et() - timestamp).total_seconds() < self._cache_ttl:
                logger.debug(
                    "returning_cached_congestion_data",
                    cache_age_seconds=(now_et() - timestamp).total_seconds(),
                    data_source=data_source,
                )
                return cached_data

        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # Build data_source filter dynamically so PostgreSQL can use the
        # composite index (journey_date, data_source) when a source is specified.
        # The old CAST(:data_source AS TEXT) IS NULL OR pattern prevented index usage.
        ds_filter = "AND tj_pre.data_source = :data_source" if data_source else ""
        ds_filter_stt = "AND stt.data_source = :data_source" if data_source else ""

        # SQL query that calculates segment times and aggregates in database
        # This replaces loading thousands of objects into Python memory
        query = text(f"""
        WITH stop_pairs AS (
            -- Pair each stop with its next stop using LEAD window function.
            -- Pre-filter by journey_date to avoid scanning the entire history.
            -- Handles non-consecutive stop_sequence values (common in GTFS
            -- static data from MTA feeds like MNR/LIRR) by ordering by
            -- stop_sequence and taking the actual next mapped stop.
            SELECT
                js.journey_id,
                js.station_code as from_station,
                js.actual_departure as from_actual_departure,
                js.actual_arrival as from_actual_arrival,
                js.scheduled_departure as from_scheduled_departure,
                LEAD(js.station_code) OVER w as to_station,
                LEAD(js.actual_arrival) OVER w as to_actual_arrival,
                LEAD(js.scheduled_arrival) OVER w as to_scheduled_arrival
            FROM journey_stops js
            JOIN train_journeys tj_pre ON tj_pre.id = js.journey_id
            WHERE js.station_code IS NOT NULL
              AND tj_pre.journey_date >= CURRENT_DATE - INTERVAL '1 day'
              {ds_filter}
            WINDOW w AS (PARTITION BY js.journey_id ORDER BY js.stop_sequence)
        ),
        segment_data AS (
            -- Calculate segment transit times from paired stops
            SELECT
                sp.from_station,
                sp.to_station,
                tj.data_source,
                tj.is_cancelled,
                tj.id as journey_id,
                tj.train_id,
                -- Calculate actual transit time in minutes.
                -- For MTA (subway/LIRR/MNR), GTFS-RT often omits departure
                -- times at intermediate stops. Fall back to actual_arrival
                -- as a proxy (dwell time is negligible for rapid transit).
                EXTRACT(EPOCH FROM (
                    COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) -
                    COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
                )) / 60.0 as actual_minutes,
                -- Calculate scheduled transit time
                CASE
                    WHEN sp.from_scheduled_departure IS NOT NULL
                     AND sp.to_scheduled_arrival IS NOT NULL
                     AND sp.to_scheduled_arrival > sp.from_scheduled_departure
                    THEN EXTRACT(EPOCH FROM (
                        sp.to_scheduled_arrival - sp.from_scheduled_departure
                    )) / 60.0
                    ELSE NULL
                END as scheduled_minutes,
                -- Track when this segment departed for recency sorting
                COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) as departure_time
            FROM train_journeys tj
            JOIN stop_pairs sp ON sp.journey_id = tj.id
            WHERE
                -- LEAD returns NULL for last stop in journey (no next stop)
                sp.to_station IS NOT NULL
                -- Within time window
                AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) >= :cutoff_time
                -- Valid times: need some departure time and some arrival time
                AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) IS NOT NULL
                AND COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) IS NOT NULL
                -- Ensure arrival is after departure (positive transit time)
                AND COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) >
                    COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
        ),
        segment_with_recency AS (
            -- Add recency window for efficient filtering
            SELECT
                *,
                MAX(departure_time) OVER (
                    PARTITION BY from_station, to_station, data_source
                ) as max_departure_time
            FROM segment_data
        ),
        segment_aggregates AS (
            -- Aggregate by segment (from-to-datasource)
            SELECT
                from_station,
                to_station,
                data_source,
                -- Active journey metrics (only positive transit times)
                COUNT(*) FILTER (WHERE NOT is_cancelled AND actual_minutes > 0) as active_count,
                AVG(actual_minutes) FILTER (WHERE NOT is_cancelled AND actual_minutes > 0) as avg_actual,
                AVG(scheduled_minutes) FILTER (WHERE NOT is_cancelled AND scheduled_minutes > 0) as avg_scheduled,
                -- For baseline: use scheduled if available, otherwise median of actuals
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY actual_minutes
                ) FILTER (WHERE NOT is_cancelled AND actual_minutes > 0) as median_actual,
                -- Cancellation metrics
                COUNT(*) FILTER (WHERE is_cancelled) as cancelled_count,
                -- Recent samples (last hour) - now using window function result
                AVG(actual_minutes) FILTER (
                    WHERE NOT is_cancelled
                    AND actual_minutes > 0
                    AND departure_time >= max_departure_time - INTERVAL '1 hour'
                ) as recent_avg,
                -- Train count for frequency calculation (non-cancelled trains)
                COUNT(DISTINCT journey_id) FILTER (WHERE NOT is_cancelled) as train_count
            FROM segment_with_recency
            GROUP BY from_station, to_station, data_source
        ),
        -- Historical baseline for frequency: average train count per time window
        -- for same hour of day and weekday/weekend pattern over past 30 days.
        -- Uses per-day averaging (not /30) so weekday-only or weekend-only
        -- counts are not diluted. Requires >= 3 days of data.
        -- IMPORTANT: hour_of_day/day_of_week in segment_transit_times are stored
        -- in Eastern Time (via ensure_timezone_aware + DB session tz), so we
        -- must compare against NOW() AT TIME ZONE 'America/New_York', not
        -- raw NOW() (which is UTC).
        historical_baseline AS (
            SELECT
                from_station,
                to_station,
                data_source,
                AVG(day_count) * :time_window_hours as baseline_train_count
            FROM (
                SELECT
                    stt.from_station_code as from_station,
                    stt.to_station_code as to_station,
                    stt.data_source,
                    stt.departure_time::date as journey_day,
                    COUNT(DISTINCT stt.journey_id) as day_count
                FROM segment_transit_times stt
                WHERE stt.departure_time >= NOW() - INTERVAL '30 days'
                  AND stt.hour_of_day = EXTRACT(HOUR FROM (NOW() AT TIME ZONE 'America/New_York'))
                  -- Match weekday vs weekend
                  -- EXTRACT(DOW) uses Sun=0,Sat=6; Python weekday() uses Mon=0,Sat=5,Sun=6
                  AND (
                      (EXTRACT(DOW FROM (NOW() AT TIME ZONE 'America/New_York')) IN (0, 6) AND stt.day_of_week IN (5, 6))
                      OR (EXTRACT(DOW FROM (NOW() AT TIME ZONE 'America/New_York')) NOT IN (0, 6) AND stt.day_of_week NOT IN (5, 6))
                  )
                  {ds_filter_stt}
                GROUP BY stt.from_station_code, stt.to_station_code, stt.data_source, stt.departure_time::date
            ) daily_stats
            GROUP BY from_station, to_station, data_source
            HAVING COUNT(*) >= 3
        )
        SELECT
            sa.from_station,
            sa.to_station,
            sa.data_source,
            sa.active_count,
            sa.cancelled_count,
            sa.avg_actual,
            sa.avg_scheduled,
            sa.median_actual,
            sa.recent_avg,
            -- Calculate baseline (scheduled avg if available, else median actual)
            COALESCE(sa.avg_scheduled, sa.median_actual) as baseline_minutes,
            -- Use recent average if available, otherwise overall average
            COALESCE(sa.recent_avg, sa.avg_actual) as current_avg_minutes,
            -- Frequency metrics
            sa.train_count,
            hb.baseline_train_count,
            CASE
                WHEN hb.baseline_train_count > 0 AND hb.baseline_train_count IS NOT NULL
                THEN sa.train_count::float / hb.baseline_train_count
                ELSE NULL
            END as frequency_factor
        FROM segment_aggregates sa
        LEFT JOIN historical_baseline hb
            ON sa.from_station = hb.from_station
            AND sa.to_station = hb.to_station
            AND sa.data_source = hb.data_source
        WHERE (sa.active_count + sa.cancelled_count) >= 1  -- Show all segments with any data
        """)

        # Execute query with performance logging
        params: dict[str, Any] = {
            "cutoff_time": cutoff_time,
            "time_window_hours": time_window_hours,
        }
        if data_source:
            params["data_source"] = data_source

        # Guard against runaway queries (especially for high-volume providers
        # like SUBWAY). SET LOCAL is transaction-scoped and auto-resets.
        await db.execute(text("SET LOCAL statement_timeout = '30000'"))

        query_start = now_et()
        result = await db.execute(query, params)
        rows = result.fetchall()
        query_duration_ms = (now_et() - query_start).total_seconds() * 1000

        # Log slow queries (>100ms threshold)
        if query_duration_ms > 100:
            logger.warning(
                "slow_congestion_query",
                duration_ms=round(query_duration_ms, 2),
                time_window_hours=time_window_hours,
                data_source=data_source,
                row_count=len(rows),
            )
        else:
            logger.debug(
                "congestion_query_completed",
                duration_ms=round(query_duration_ms, 2),
                row_count=len(rows),
            )

        congestion_results = []
        for row in rows:
            # Calculate derived metrics
            total_journeys = row.active_count + row.cancelled_count
            cancellation_rate = (
                (row.cancelled_count / total_journeys * 100)
                if total_journeys > 0
                else 0
            )

            # Calculate congestion factor (convert Decimal to float)
            baseline = float(
                row.baseline_minutes or row.median_actual or row.avg_actual or 1.0
            )
            current_avg = float(row.current_avg_minutes or row.avg_actual or baseline)
            congestion_factor = current_avg / baseline if baseline > 0 else 1.0

            level = get_congestion_level(congestion_factor)

            # Calculate average delay
            average_delay = current_avg - baseline

            # Calculate frequency metrics (only for real-time sources)
            train_count: int | None = None
            baseline_train_count: float | None = None
            frequency_factor: float | None = None
            frequency_level: str | None = None

            if row.data_source in REALTIME_SOURCES:
                train_count = int(row.train_count) if row.train_count else 0
                if (
                    row.baseline_train_count is not None
                    and row.baseline_train_count > 0
                ):
                    baseline_train_count = float(row.baseline_train_count)
                    if row.frequency_factor is not None:
                        frequency_factor = float(row.frequency_factor)
                        frequency_level = get_frequency_level(frequency_factor)
                # When no historical baseline exists, frequency_factor stays None
                # and iOS will show gray to indicate "no data available"

            congestion_results.append(
                SegmentCongestion(
                    from_station=row.from_station,
                    to_station=row.to_station,
                    data_source=row.data_source,
                    congestion_factor=congestion_factor,
                    congestion_level=level,
                    avg_transit_minutes=current_avg,
                    baseline_minutes=baseline,
                    sample_count=row.active_count,
                    average_delay_minutes=average_delay,
                    cancellation_count=row.cancelled_count,
                    cancellation_rate=cancellation_rate,
                    train_count=train_count,
                    baseline_train_count=baseline_train_count,
                    frequency_factor=frequency_factor,
                    frequency_level=frequency_level,
                )
            )

        # Normalize segments to canonical pairs (expand skip-stop segments)
        # Import here to avoid circular import
        from trackrat.services.segment_normalizer import normalize_aggregated_segments

        congestion_results = normalize_aggregated_segments(congestion_results)

        # Cache the results
        self._cache[cache_key] = (congestion_results, now_et())

        logger.info(
            "network_congestion_calculated_optimized",
            segment_count=len(congestion_results),
            time_window_hours=time_window_hours,
            method="database_aggregation",
        )

        return congestion_results

    async def get_individual_segments_optimized(
        self,
        db: AsyncSession,
        time_window_hours: int = 3,
        max_per_segment: int = 100,
        data_source: str | None = None,
    ) -> list[Any]:
        """
        Get individual journey segments using SQL-based approach.

        This calculates individual train segments directly in the database
        instead of loading all journey objects into memory. Each segment
        represents one train's journey between consecutive stations.

        Args:
            db: Database session
            time_window_hours: How many hours to look back
            max_per_segment: Maximum segments per route (0 = unlimited)
            data_source: Optional filter by data source (NJT or AMTRAK)

        Returns:
            List of IndividualJourneySegment objects for visualization
        """
        from trackrat.config.stations import get_station_name
        from trackrat.models.api import IndividualJourneySegment

        cutoff_time = now_et() - timedelta(hours=time_window_hours)

        # Build data_source filter dynamically for index usage
        ds_filter = "AND tj_pre.data_source = :data_source" if data_source else ""

        # SQL query to get individual segments with per-route limiting
        if max_per_segment > 0:
            # With per-route limiting using ROW_NUMBER()
            query = text(f"""
            WITH stop_pairs AS (
                -- Pre-filter by journey_date to avoid scanning entire history
                SELECT
                    js.journey_id,
                    js.station_code as from_station,
                    js.actual_departure as from_actual_departure,
                    js.actual_arrival as from_actual_arrival,
                    js.scheduled_departure as from_scheduled_departure,
                    LEAD(js.station_code) OVER w as to_station,
                    LEAD(js.actual_arrival) OVER w as to_actual_arrival,
                    LEAD(js.scheduled_arrival) OVER w as to_scheduled_arrival
                FROM journey_stops js
                JOIN train_journeys tj_pre ON tj_pre.id = js.journey_id
                WHERE js.station_code IS NOT NULL
                  AND tj_pre.journey_date >= CURRENT_DATE - INTERVAL '1 day'
                  {ds_filter}
                WINDOW w AS (PARTITION BY js.journey_id ORDER BY js.stop_sequence)
            ),
            segment_data AS (
                -- Calculate individual train segments between adjacent stops
                SELECT
                    sp.from_station,
                    sp.to_station,
                    tj.data_source,
                    tj.id as journey_id,
                    tj.train_id,
                    tj.journey_date,
                    -- Timing data (fall back to actual_arrival for MTA intermediate stops)
                    COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) as departure_time,
                    COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) as arrival_time,
                    sp.from_scheduled_departure as scheduled_departure,
                    sp.to_scheduled_arrival as scheduled_arrival,
                    -- Calculate actual transit time in minutes
                    EXTRACT(EPOCH FROM (
                        COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) -
                        COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
                    )) / 60.0 as actual_minutes,
                    -- Calculate scheduled transit time
                    CASE
                        WHEN sp.from_scheduled_departure IS NOT NULL
                         AND sp.to_scheduled_arrival IS NOT NULL
                         AND sp.to_scheduled_arrival > sp.from_scheduled_departure
                        THEN EXTRACT(EPOCH FROM (
                            sp.to_scheduled_arrival - sp.from_scheduled_departure
                        )) / 60.0
                        ELSE NULL
                    END as scheduled_minutes
                FROM train_journeys tj
                JOIN stop_pairs sp ON sp.journey_id = tj.id
                WHERE
                    sp.to_station IS NOT NULL
                    -- Within time window
                    AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) >= :cutoff_time
                    -- Active journeys only (cancelled trains handled separately)
                    AND NOT tj.is_cancelled
                    -- Valid times: need some departure and arrival time
                    AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) IS NOT NULL
                    AND COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) IS NOT NULL
                    -- Ensure arrival is after departure (positive transit time)
                    AND COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) >
                        COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
            ),
            ranked_segments AS (
                -- Rank segments by recency within each route
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY from_station, to_station, data_source
                        ORDER BY departure_time DESC
                    ) as rank_within_route
                FROM segment_data
                WHERE actual_minutes > 0  -- Valid positive transit times only
            )
            SELECT
                journey_id,
                train_id,
                from_station,
                to_station,
                data_source,
                journey_date,
                departure_time,
                arrival_time,
                scheduled_departure,
                scheduled_arrival,
                actual_minutes,
                scheduled_minutes,
                -- Calculate delay
                actual_minutes - COALESCE(scheduled_minutes, actual_minutes) as delay_minutes,
                -- Calculate congestion factor
                CASE
                    WHEN scheduled_minutes > 0
                    THEN actual_minutes / scheduled_minutes
                    ELSE 1.0
                END as congestion_factor
            FROM ranked_segments
            WHERE rank_within_route <= :max_per_segment
            ORDER BY departure_time DESC
            LIMIT :global_limit
            """)
        else:
            # No per-route limiting - return ALL individual segments
            query = text(f"""
            WITH stop_pairs AS (
                -- Pre-filter by journey_date to avoid scanning entire history
                SELECT
                    js.journey_id,
                    js.station_code as from_station,
                    js.actual_departure as from_actual_departure,
                    js.actual_arrival as from_actual_arrival,
                    js.scheduled_departure as from_scheduled_departure,
                    LEAD(js.station_code) OVER w as to_station,
                    LEAD(js.actual_arrival) OVER w as to_actual_arrival,
                    LEAD(js.scheduled_arrival) OVER w as to_scheduled_arrival
                FROM journey_stops js
                JOIN train_journeys tj_pre ON tj_pre.id = js.journey_id
                WHERE js.station_code IS NOT NULL
                  AND tj_pre.journey_date >= CURRENT_DATE - INTERVAL '1 day'
                  {ds_filter}
                WINDOW w AS (PARTITION BY js.journey_id ORDER BY js.stop_sequence)
            ),
            segment_data AS (
                -- Calculate individual train segments between adjacent stops
                SELECT
                    sp.from_station,
                    sp.to_station,
                    tj.data_source,
                    tj.id as journey_id,
                    tj.train_id,
                    tj.journey_date,
                    -- Timing data (fall back to actual_arrival for MTA intermediate stops)
                    COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) as departure_time,
                    COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) as arrival_time,
                    sp.from_scheduled_departure as scheduled_departure,
                    sp.to_scheduled_arrival as scheduled_arrival,
                    -- Calculate actual transit time in minutes
                    EXTRACT(EPOCH FROM (
                        COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) -
                        COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
                    )) / 60.0 as actual_minutes,
                    -- Calculate scheduled transit time
                    CASE
                        WHEN sp.from_scheduled_departure IS NOT NULL
                         AND sp.to_scheduled_arrival IS NOT NULL
                         AND sp.to_scheduled_arrival > sp.from_scheduled_departure
                        THEN EXTRACT(EPOCH FROM (
                            sp.to_scheduled_arrival - sp.from_scheduled_departure
                        )) / 60.0
                        ELSE NULL
                    END as scheduled_minutes
                FROM train_journeys tj
                JOIN stop_pairs sp ON sp.journey_id = tj.id
                WHERE
                    sp.to_station IS NOT NULL
                    -- Within time window
                    AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) >= :cutoff_time
                    -- Active journeys only
                    AND NOT tj.is_cancelled
                    -- Valid times: need some departure and arrival time
                    AND COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure) IS NOT NULL
                    AND COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) IS NOT NULL
                    -- Valid positive transit times
                    AND EXTRACT(EPOCH FROM (
                        COALESCE(sp.to_actual_arrival, sp.to_scheduled_arrival) -
                        COALESCE(sp.from_actual_departure, sp.from_actual_arrival, sp.from_scheduled_departure)
                    )) > 0
            )
            SELECT
                journey_id,
                train_id,
                from_station,
                to_station,
                data_source,
                journey_date,
                departure_time,
                arrival_time,
                scheduled_departure,
                scheduled_arrival,
                actual_minutes,
                scheduled_minutes,
                -- Calculate delay
                actual_minutes - COALESCE(scheduled_minutes, actual_minutes) as delay_minutes,
                -- Calculate congestion factor
                CASE
                    WHEN scheduled_minutes > 0
                    THEN actual_minutes / scheduled_minutes
                    ELSE 1.0
                END as congestion_factor
            FROM segment_data
            ORDER BY departure_time DESC
            LIMIT :global_limit
            """)

        # Execute query with performance logging
        # Global limit prevents unbounded response sizes (e.g. SUBWAY with 700+ station pairs)
        global_limit = 5000
        seg_params: dict[str, Any] = {
            "cutoff_time": cutoff_time,
            "global_limit": global_limit,
        }
        if data_source:
            seg_params["data_source"] = data_source
        if max_per_segment > 0:
            seg_params["max_per_segment"] = max_per_segment

        query_start = now_et()
        result = await db.execute(query, seg_params)
        rows = result.fetchall()
        query_duration_ms = (now_et() - query_start).total_seconds() * 1000

        if query_duration_ms > 100:
            logger.warning(
                "slow_individual_segments_query",
                duration_ms=round(query_duration_ms, 2),
                segment_count=len(rows),
                max_per_segment=max_per_segment,
                data_source=data_source,
            )
        else:
            logger.debug(
                "individual_segments_query_completed",
                duration_ms=round(query_duration_ms, 2),
                segment_count=len(rows),
            )

        # Convert to IndividualJourneySegment objects
        individual_segments = []
        for row in rows:
            # Determine congestion level from factor (convert Decimal to float)
            congestion_factor = float(row.congestion_factor)
            level = get_congestion_level(congestion_factor)

            # Convert database types to Python types
            actual_minutes = float(row.actual_minutes)
            scheduled_minutes = (
                float(row.scheduled_minutes)
                if row.scheduled_minutes
                else actual_minutes
            )
            delay_minutes = float(row.delay_minutes)

            segment = IndividualJourneySegment(
                journey_id=str(row.journey_id),
                train_id=row.train_id,
                from_station=row.from_station,
                to_station=row.to_station,
                from_station_name=get_station_name(row.from_station),
                to_station_name=get_station_name(row.to_station),
                data_source=row.data_source,
                scheduled_departure=row.scheduled_departure or row.departure_time,
                actual_departure=row.departure_time,
                scheduled_arrival=row.scheduled_arrival or row.arrival_time,
                actual_arrival=row.arrival_time,
                scheduled_minutes=scheduled_minutes,
                actual_minutes=actual_minutes,
                delay_minutes=delay_minutes,
                congestion_factor=congestion_factor,
                congestion_level=level,
                is_cancelled=False,  # We only process active journeys
                journey_date=row.journey_date,
            )
            individual_segments.append(segment)

        # Normalize segments to canonical pairs (expand skip-stop segments)
        # Import here to avoid circular import
        from trackrat.services.segment_normalizer import normalize_individual_segments

        individual_segments = normalize_individual_segments(individual_segments)

        logger.info(
            "individual_segments_calculated_optimized",
            segment_count=len(individual_segments),
            time_window_hours=time_window_hours,
            max_per_segment=max_per_segment,
            method="sql_direct",
        )

        return individual_segments

    def _calculate_segments_from_journeys(
        self, journeys: list[TrainJourney], cutoff_time: datetime
    ) -> tuple[
        dict[tuple[str, str, str], list[dict[str, Any]]],
        dict[tuple[str, str, str], int],
    ]:
        """Extract segment data from journeys and track cancellations."""
        segment_groups: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = (
            defaultdict(list)
        )
        cancellation_counts: defaultdict[tuple[str, str, str], int] = defaultdict(int)

        for journey in journeys:
            if not journey.stops:
                continue

            # Sort stops by sequence
            sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

            # Track cancellations for each potential segment
            if journey.is_cancelled:
                # For cancelled journeys, count them against all segments they would have traveled
                for i in range(len(sorted_stops) - 1):
                    from_stop = sorted_stops[i]
                    to_stop = sorted_stops[i + 1]

                    if (
                        from_stop.station_code
                        and to_stop.station_code
                        and journey.data_source
                    ):
                        key = (
                            from_stop.station_code,
                            to_stop.station_code,
                            journey.data_source,
                        )
                        cancellation_counts[key] += 1
                continue  # Skip cancelled journeys from active segment calculation

            # Calculate segments between consecutive stops for active journeys
            for i in range(len(sorted_stops) - 1):
                from_stop = sorted_stops[i]
                to_stop = sorted_stops[i + 1]

                # Skip if missing critical data
                if not all(
                    [
                        from_stop.station_code,
                        to_stop.station_code,
                        from_stop.actual_departure or from_stop.scheduled_departure,
                        to_stop.actual_arrival or to_stop.scheduled_arrival,
                    ]
                ):
                    continue

                # Use actual times when available, fall back to scheduled
                departure_time = (
                    from_stop.actual_departure or from_stop.scheduled_departure
                )
                arrival_time = to_stop.actual_arrival or to_stop.scheduled_arrival

                if not departure_time or not arrival_time:
                    continue
                # Ensure timezone awareness
                departure_time = ensure_timezone_aware(departure_time)
                arrival_time = ensure_timezone_aware(arrival_time)

                # Skip if outside time window
                if departure_time < cutoff_time:
                    continue

                # Calculate segment duration
                actual_minutes = (arrival_time - departure_time).total_seconds() / 60
                if actual_minutes <= 0:
                    continue  # Skip invalid segments

                # Calculate scheduled duration if available
                scheduled_minutes = None
                if from_stop.scheduled_departure and to_stop.scheduled_arrival:
                    sched_dep = ensure_timezone_aware(from_stop.scheduled_departure)
                    sched_arr = ensure_timezone_aware(to_stop.scheduled_arrival)
                    scheduled_minutes = (sched_arr - sched_dep).total_seconds() / 60

                assert from_stop.station_code
                assert to_stop.station_code
                assert journey.data_source

                # Group by segment key
                key = (
                    from_stop.station_code,
                    to_stop.station_code,
                    journey.data_source,
                )
                segment_groups[key].append(
                    {
                        "actual_minutes": actual_minutes,
                        "scheduled_minutes": scheduled_minutes,
                        "departure_time": departure_time,
                        "journey_id": journey.id,
                        "train_id": journey.train_id,
                    }
                )

        return segment_groups, dict(cancellation_counts)

    def _analyze_segment_congestion(
        self,
        segment_groups: dict[tuple[str, str, str], list[dict[str, Any]]],
        cancellation_counts: dict[tuple[str, str, str], int],
    ) -> list[SegmentCongestion]:
        """Analyze congestion for each segment."""
        congestion_data = []

        # Get all unique segment keys from both active and cancelled data
        all_segment_keys = set(segment_groups.keys()) | set(cancellation_counts.keys())

        for segment_key in all_segment_keys:
            from_station, to_station, data_source = segment_key
            segments = segment_groups.get(segment_key, [])
            cancellation_count = cancellation_counts.get(segment_key, 0)

            # Filter out invalid transit times (≤ 0 minutes)
            valid_segments = [s for s in segments if s.get("actual_minutes", 0) > 0]

            # Calculate total journeys (valid active + cancelled)
            total_journeys = len(valid_segments) + cancellation_count

            # Skip if we have no data at all
            if total_journeys < 1:
                continue

            # Calculate cancellation rate
            cancellation_rate = (
                (cancellation_count / total_journeys * 100)
                if total_journeys > 0
                else 0.0
            )

            # For segments with only cancellations, create a special entry
            if len(valid_segments) == 0:
                congestion_data.append(
                    SegmentCongestion(
                        from_station=from_station,
                        to_station=to_station,
                        data_source=data_source,
                        congestion_factor=1.0,  # No congestion data available
                        congestion_level="normal",  # Default level
                        avg_transit_minutes=0.0,
                        baseline_minutes=0.0,
                        sample_count=0,
                        average_delay_minutes=0.0,
                        cancellation_count=cancellation_count,
                        cancellation_rate=cancellation_rate,
                    )
                )
                continue

            # Calculate baseline (scheduled average or median of actuals)
            scheduled_times = [
                s["scheduled_minutes"]
                for s in valid_segments
                if s["scheduled_minutes"] is not None
            ]

            if scheduled_times:
                baseline_minutes = statistics.mean(scheduled_times)
            else:
                # Use median of actual times as baseline
                actual_times = [s["actual_minutes"] for s in valid_segments]
                baseline_minutes = statistics.median(actual_times)

            # Calculate current average (recent 50 samples, sorted by time)
            recent_segments = sorted(
                valid_segments, key=lambda x: x["departure_time"], reverse=True
            )[:50]
            current_avg = statistics.mean(
                [s["actual_minutes"] for s in recent_segments]
            )

            # Calculate congestion factor
            congestion_factor = (
                current_avg / baseline_minutes if baseline_minutes > 0 else 1.0
            )

            # Calculate average delay
            average_delay_minutes = current_avg - baseline_minutes

            level = get_congestion_level(congestion_factor)

            congestion_data.append(
                SegmentCongestion(
                    from_station=from_station,
                    to_station=to_station,
                    data_source=data_source,
                    congestion_factor=congestion_factor,
                    congestion_level=level,
                    avg_transit_minutes=current_avg,
                    baseline_minutes=baseline_minutes,
                    sample_count=len(recent_segments),
                    average_delay_minutes=average_delay_minutes,
                    cancellation_count=cancellation_count,
                    cancellation_rate=cancellation_rate,
                )
            )

        return congestion_data

    def _extract_individual_segments(
        self,
        segment_groups: dict[tuple[str, str, str], list[dict[str, Any]]],
        max_per_segment: int = 100,
    ) -> list[Any]:
        """Extract individual journey segments for visualization."""
        from trackrat.config.stations import get_station_name
        from trackrat.models.api import IndividualJourneySegment

        individual_segments = []

        for segment_key, segments in segment_groups.items():
            from_station, to_station, data_source = segment_key

            # Sort by departure time (most recent first) and limit
            recent_segments = sorted(
                segments, key=lambda x: x["departure_time"], reverse=True
            )[:max_per_segment]

            for segment_data in recent_segments:
                # Calculate congestion level
                actual_minutes = segment_data["actual_minutes"]
                scheduled_minutes = segment_data.get("scheduled_minutes")

                if scheduled_minutes and scheduled_minutes > 0:
                    congestion_factor = actual_minutes / scheduled_minutes
                    delay_minutes = actual_minutes - scheduled_minutes
                else:
                    congestion_factor = 1.0
                    delay_minutes = 0.0

                level = get_congestion_level(congestion_factor)

                individual_segment = IndividualJourneySegment(
                    journey_id=str(segment_data["journey_id"]),
                    train_id=segment_data["train_id"],
                    from_station=from_station,
                    to_station=to_station,
                    from_station_name=get_station_name(from_station),
                    to_station_name=get_station_name(to_station),
                    data_source=data_source,
                    scheduled_departure=segment_data[
                        "departure_time"
                    ],  # Using actual as proxy for scheduled
                    actual_departure=segment_data["departure_time"],
                    scheduled_arrival=segment_data["departure_time"]
                    + timedelta(
                        minutes=(
                            scheduled_minutes if scheduled_minutes else actual_minutes
                        )
                    ),
                    actual_arrival=segment_data["departure_time"]
                    + timedelta(minutes=actual_minutes),
                    scheduled_minutes=(
                        scheduled_minutes if scheduled_minutes else actual_minutes
                    ),
                    actual_minutes=actual_minutes,
                    delay_minutes=delay_minutes,
                    congestion_factor=congestion_factor,
                    congestion_level=level,
                    is_cancelled=False,  # These segments are from active journeys
                    journey_date=segment_data["departure_time"].date(),
                )

                individual_segments.append(individual_segment)

        return individual_segments
