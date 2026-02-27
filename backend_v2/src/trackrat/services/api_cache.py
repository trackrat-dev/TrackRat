"""
API response caching service for performance optimization.

Pre-computes expensive API responses and serves from cache for sub-100ms response times.
"""

import hashlib
import json
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models.api import CongestionMapResponse
from trackrat.models.database import CachedApiResponse
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et

logger = get_logger(__name__)


class ApiCacheService:
    """Service for pre-computing and caching expensive API responses."""

    def __init__(self) -> None:
        self.congestion_analyzer = CongestionAnalyzer()
        self.departure_service = DepartureService()

    def _hash_params(self, params: dict[str, Any]) -> str:
        """Create a consistent hash of parameters for cache lookup."""
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(sorted_params.encode()).hexdigest()

    async def get_cached_response(
        self, db: AsyncSession, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Get cached response if available and not expired."""
        params_hash = self._hash_params(params)

        stmt = select(CachedApiResponse).where(
            and_(
                CachedApiResponse.endpoint == endpoint,
                CachedApiResponse.params_hash == params_hash,
                CachedApiResponse.expires_at > now_et(),
            )
        )

        result = await db.execute(stmt)
        cached = result.scalar_one_or_none()

        if cached:
            age_seconds = 0.0
            if cached.generated_at:
                try:
                    age_seconds = (now_et() - cached.generated_at).total_seconds()
                except (TypeError, AttributeError):
                    age_seconds = 0.0

            logger.info(
                "cache_hit",
                endpoint=endpoint,
                params=params,
                generated_at=cached.generated_at,
                age_seconds=age_seconds,
            )
            return cached.response

        return None

    async def invalidate_cache_entry(
        self, db: AsyncSession, endpoint: str, params: dict[str, Any]
    ) -> bool:
        """Invalidate a specific cache entry. Returns True if entry was deleted."""
        params_hash = self._hash_params(params)

        delete_stmt = delete(CachedApiResponse).where(
            and_(
                CachedApiResponse.endpoint == endpoint,
                CachedApiResponse.params_hash == params_hash,
            )
        )
        result = cast(CursorResult[tuple[()]], await db.execute(delete_stmt))
        await db.commit()

        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info(
                "cache_entry_invalidated",
                endpoint=endpoint,
                params=params,
            )
        return deleted

    async def store_cached_response(
        self,
        db: AsyncSession,
        endpoint: str,
        params: dict[str, Any],
        response: dict[str, Any],
        ttl_seconds: int = 120,
    ) -> None:
        """Store a pre-computed response in the cache."""
        params_hash = self._hash_params(params)
        generated_at = now_et()
        expires_at = generated_at + timedelta(seconds=ttl_seconds)

        # Use PostgreSQL UPSERT to handle concurrent updates gracefully
        cache_record = CachedApiResponse(
            endpoint=endpoint,
            params_hash=params_hash,
            params=params,
            response=response,
            generated_at=generated_at,
            expires_at=expires_at,
        )

        # Delete existing record if it exists, then insert new one
        delete_stmt = delete(CachedApiResponse).where(
            and_(
                CachedApiResponse.endpoint == endpoint,
                CachedApiResponse.params_hash == params_hash,
            )
        )
        await db.execute(delete_stmt)

        db.add(cache_record)
        await db.commit()

        logger.info(
            "cache_stored",
            endpoint=endpoint,
            params=params,
            expires_at=expires_at,
            ttl_seconds=ttl_seconds,
        )

    async def precompute_congestion_responses(self, db: AsyncSession) -> None:
        """Pre-compute congestion responses for common parameter combinations used by iOS app."""

        # Parameter combinations based on iOS app usage analysis
        # Cache keys use effective time window (minimum 2h enforced by API endpoint)
        param_sets: list[dict[str, Any]] = [
            # iOS summary mode (default): timeWindowHours=1 -> effective 2, maxPerSegment=0
            {"time_window_hours": 2, "max_per_segment": 0, "data_source": None},
            # iOS trains mode: timeWindowHours=1 -> effective 2, maxPerSegment=100
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": None},
            # Longer window views
            {"time_window_hours": 3, "max_per_segment": 100, "data_source": None},
            {"time_window_hours": 3, "max_per_segment": 0, "data_source": None},
            # Per-provider filtering (iOS RouteStatusView uses timeWindowHours=1 -> effective 2, maxPerSegment=100)
            {"time_window_hours": 2, "max_per_segment": 0, "data_source": "NJT"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "NJT"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "PATH"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "AMTRAK"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "LIRR"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "MNR"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "SUBWAY"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "PATCO"},
            # Longer window views with NJT
            {"time_window_hours": 3, "max_per_segment": 100, "data_source": "NJT"},
        ]

        logger.info("precomputing_congestion_responses", param_count=len(param_sets))

        for params in param_sets:
            try:
                # Compute the response using existing logic
                response_dict = await self._compute_congestion_response(db, params)

                # Store in cache with 10-minute TTL (longer than 15-min refresh to avoid gaps)
                await self.store_cached_response(
                    db=db,
                    endpoint="/api/v2/routes/congestion",
                    params=params,
                    response=response_dict,
                    ttl_seconds=600,  # 10 minutes
                )

                logger.info(
                    "precomputed_congestion_response",
                    params=params,
                    response_size_kb=len(json.dumps(response_dict)) / 1024,
                )

            except Exception as e:
                logger.error(
                    "precompute_congestion_error",
                    params=params,
                    error=str(e) or repr(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                # Rollback to clear aborted transaction state so subsequent
                # iterations don't fail with InFailedSqlTransaction
                await db.rollback()

    async def _compute_congestion_response(
        self, db: AsyncSession, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute congestion response using the existing congestion service logic."""

        # Extract parameters
        time_window_hours = params.get("time_window_hours", 3)
        max_per_segment = params.get("max_per_segment", 100)
        data_source = params.get("data_source")

        # Use existing congestion analyzer logic (pass data_source to filter at SQL level)
        aggregated_segments, journeys, individual_segments = (
            await self.congestion_analyzer.get_network_congestion_with_trains(
                db, time_window_hours, max_per_segment, data_source
            )
        )

        # Filter out SAN station code collision (same as routes.py)
        aggregated_segments = [
            s
            for s in aggregated_segments
            if s.from_station != "SAN" and s.to_station != "SAN"
        ]
        individual_segments = [
            s
            for s in individual_segments
            if s.from_station != "SAN" and s.to_station != "SAN"
        ]

        # Extract train positions from journeys (same logic as routes.py)
        train_positions = []
        for journey in journeys:
            if journey.is_cancelled:
                continue

            position = self.departure_service._calculate_train_position(journey)

            journey_percent = None
            if journey.progress:
                journey_percent = journey.progress.journey_percent

            from trackrat.models.api import TrainLocationData

            location_data = TrainLocationData(
                train_id=journey.train_id,
                line=journey.line_code,
                data_source=journey.data_source,
                last_departed_station=position.last_departed_station_code,
                at_station=position.at_station_code,
                next_station=position.next_station_code,
                between_stations=position.between_stations,
                journey_percent=journey_percent,
            )
            train_positions.append(location_data)

        # Convert aggregated segments to API models (same logic as routes.py)
        from trackrat.config.stations import get_station_name
        from trackrat.models.api import SegmentCongestion as SegmentCongestionModel

        aggregated_api_segments = []
        for segment in aggregated_segments:
            segment_model = SegmentCongestionModel(
                from_station=segment.from_station,
                to_station=segment.to_station,
                from_station_name=get_station_name(segment.from_station),
                to_station_name=get_station_name(segment.to_station),
                data_source=segment.data_source,
                congestion_level=segment.congestion_level,
                congestion_factor=segment.congestion_factor,
                average_delay_minutes=segment.average_delay_minutes,
                sample_count=segment.sample_count,
                baseline_minutes=segment.baseline_minutes,
                current_average_minutes=segment.avg_transit_minutes,
                cancellation_count=segment.cancellation_count,
                cancellation_rate=segment.cancellation_rate,
                train_count=segment.train_count,
                baseline_train_count=segment.baseline_train_count,
                frequency_factor=segment.frequency_factor,
                frequency_level=segment.frequency_level,
            )
            aggregated_api_segments.append(segment_model)

        # Create response (convert Pydantic models to dict for JSON storage)
        response = CongestionMapResponse(
            individual_segments=individual_segments,
            aggregated_segments=aggregated_api_segments,
            train_positions=train_positions,
            generated_at=now_et(),
            time_window_hours=time_window_hours,
            max_per_segment=max_per_segment,
            metadata={
                "total_individual_segments": len(individual_segments),
                "total_aggregated_segments": len(aggregated_api_segments),
                "congestion_levels": {
                    "normal": len(
                        [
                            s
                            for s in aggregated_api_segments
                            if s.congestion_level == "normal"
                        ]
                    ),
                    "moderate": len(
                        [
                            s
                            for s in aggregated_api_segments
                            if s.congestion_level == "moderate"
                        ]
                    ),
                    "heavy": len(
                        [
                            s
                            for s in aggregated_api_segments
                            if s.congestion_level == "heavy"
                        ]
                    ),
                    "severe": len(
                        [
                            s
                            for s in aggregated_api_segments
                            if s.congestion_level == "severe"
                        ]
                    ),
                },
                "total_trains": len(train_positions),
            },
        )

        # Convert to dict for storage with datetime serialization
        return response.model_dump(mode="json")

    async def precompute_departure_responses(self, db: AsyncSession) -> None:
        """Pre-compute departure responses for popular station pairs.

        Generates cache entries for both hide_departed=true (iOS) and
        hide_departed=false (web/default) variants.
        """

        # Base popular routes (with destination)
        base_routes = [
            {"from_station": "NY", "to_station": "TR"},
            {"from_station": "NY", "to_station": "NP"},
            {"from_station": "TR", "to_station": "NY"},
            {"from_station": "NP", "to_station": "NY"},
            {"from_station": "NY", "to_station": "PJ"},
            {"from_station": "PJ", "to_station": "NY"},
            {"from_station": "NY", "to_station": "LB"},
            {"from_station": "LB", "to_station": "NY"},
            # High-volume origin-only queries (no destination filter)
            {"from_station": "NY", "to_station": None},
            {"from_station": "GCT", "to_station": None},
            {"from_station": "JAM", "to_station": None},
            {"from_station": "PHO", "to_station": None},
            {"from_station": "PNK", "to_station": None},
            {"from_station": "PWC", "to_station": None},
        ]

        # Generate both hide_departed variants for each route
        # Include data_sources key to match the cache lookup in trains.py
        popular_routes: list[dict[str, Any]] = []
        for route in base_routes:
            # hide_departed=false (web/default)
            popular_routes.append(
                {**route, "date": None, "limit": 50, "hide_departed": False, "data_sources": None}
            )
            # hide_departed=true (iOS)
            popular_routes.append(
                {**route, "date": None, "limit": 50, "hide_departed": True, "data_sources": None}
            )

        logger.info("precomputing_departure_responses", route_count=len(popular_routes))

        for params in popular_routes:
            try:
                response_dict = await self._compute_departure_response(db, params)

                await self.store_cached_response(
                    db=db,
                    endpoint="/api/v2/trains/departures",
                    params=params,
                    response=response_dict,
                    ttl_seconds=120,
                )

                logger.info(
                    "precomputed_departure_response",
                    params=params,
                    response_size_kb=len(json.dumps(response_dict)) / 1024,
                )

            except Exception as e:
                logger.error(
                    "precompute_departure_error",
                    params=params,
                    error=str(e) or repr(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                # Rollback to clear aborted transaction state so subsequent
                # iterations don't fail with InFailedSqlTransaction
                await db.rollback()

    async def _compute_departure_response(
        self, db: AsyncSession, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute departure response using existing departure service logic."""

        from_station = params.get("from_station")
        assert from_station is not None, "from_station is required"
        to_station = params.get("to_station")
        limit = params.get("limit", 50)
        hide_departed = params.get("hide_departed", False)

        response = await self.departure_service.get_departures(
            db=db,
            from_station=from_station,
            to_station=to_station,
            date=None,
            time_from=None,
            time_to=None,
            limit=limit,
            hide_departed=hide_departed,
            skip_individual_refresh=True,  # Skip individual train refreshes during precompute
        )

        return response.model_dump(mode="json")

    async def cleanup_expired_cache(self, db: AsyncSession) -> int:
        """Remove expired cache entries. Returns number of entries removed."""

        delete_stmt = delete(CachedApiResponse).where(
            CachedApiResponse.expires_at <= now_et()
        )

        result = cast(CursorResult[tuple[()]], await db.execute(delete_stmt))
        await db.commit()

        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info("cleaned_up_expired_cache", deleted_count=deleted_count)

        return deleted_count
