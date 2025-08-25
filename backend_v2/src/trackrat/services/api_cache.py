"""
API response caching service for performance optimization.

Pre-computes expensive API responses and serves from cache for sub-100ms response times.
"""

import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, delete, select
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
            logger.info(
                "cache_hit",
                endpoint=endpoint,
                params=params,
                generated_at=cached.generated_at,
                age_seconds=(
                    (now_et() - cached.generated_at).total_seconds()
                    if cached.generated_at
                    else 0
                ),
            )
            return cached.response

        return None

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
        param_sets: list[dict[str, Any]] = [
            # Default API call: timeWindowHours=3, maxPerSegment=100, dataSource=nil
            {"time_window_hours": 3, "max_per_segment": 100, "data_source": None},
            # Journey view call: timeWindowHours=2, maxPerSegment=100, dataSource=nil
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": None},
            # User filtering with NJT only
            {"time_window_hours": 3, "max_per_segment": 100, "data_source": "NJT"},
            {"time_window_hours": 2, "max_per_segment": 100, "data_source": "NJT"},
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
                    error=str(e),
                    exc_info=True,
                )

    async def _compute_congestion_response(
        self, db: AsyncSession, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute congestion response using the existing congestion service logic."""

        # Extract parameters
        time_window_hours = params.get("time_window_hours", 3)
        max_per_segment = params.get("max_per_segment", 100)
        data_source = params.get("data_source")

        # Use existing congestion analyzer logic
        aggregated_segments, journeys, individual_segments = (
            await self.congestion_analyzer.get_network_congestion_with_trains(
                db, time_window_hours, max_per_segment
            )
        )

        # Filter by data source if specified (same logic as routes.py)
        if data_source:
            aggregated_segments = [
                c for c in aggregated_segments if c.data_source == data_source
            ]
            individual_segments = [
                s for s in individual_segments if s.data_source == data_source
            ]
            journeys = [j for j in journeys if j.data_source == data_source]

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

    async def cleanup_expired_cache(self, db: AsyncSession) -> int:
        """Remove expired cache entries. Returns number of entries removed."""

        delete_stmt = delete(CachedApiResponse).where(
            CachedApiResponse.expires_at <= now_et()
        )

        result = await db.execute(delete_stmt)
        await db.commit()

        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info("cleaned_up_expired_cache", deleted_count=deleted_count)

        return deleted_count
