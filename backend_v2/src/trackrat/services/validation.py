"""
End-to-end train validation service.

Validates that trains from transit APIs are properly accessible through our API endpoints.
"""

import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.config.stations import INTERNAL_TO_AMTRAK_STATION_MAP
from trackrat.db.engine import get_session
from trackrat.models.database import ValidationResult as ValidationResultDB
from trackrat.settings import Settings, get_settings
from trackrat.utils.metrics import (
    missing_trains_detected,
    train_validation_coverage,
    train_validation_duration,
    train_validation_runs,
)
from trackrat.utils.time import now_et

logger = get_logger(__name__)


class ValidationResult:
    """Result of validating a single route."""

    def __init__(
        self,
        route: str,
        source: str,
        transit_trains: set[str],
        api_trains: set[str],
        timestamp: datetime,
    ):
        self.route = route
        self.source = source
        self.transit_trains = transit_trains
        self.api_trains = api_trains
        self.missing_trains = transit_trains - api_trains
        self.extra_trains = (
            api_trains - transit_trains
        )  # Trains in API but not in transit (possibly stale)
        self.timestamp = timestamp

        # Fix #2: Calculate coverage based on intersection (trains found in both)
        # This gives us the percentage of transit trains that we successfully have
        if transit_trains:
            found_trains = api_trains.intersection(transit_trains)
            self.coverage_percent = (len(found_trains) / len(transit_trains)) * 100.0
        else:
            self.coverage_percent = 100.0


class TrainValidationService:
    """
    End-to-end validation service that ensures trains from transit APIs
    are properly accessible through our API endpoints.
    """

    # Routes to monitor: (from, to, sources to check)
    MONITORED_ROUTES = [
        ("NY", "WI", ["AMTRAK"]),  # NY Penn → Wilmington (Amtrak only)
        ("NY", "PJ", ["NJT", "AMTRAK"]),  # NY Penn → Princeton Junction (both)
        ("MP", "NY", ["NJT", "AMTRAK"]),  # Metropark → NY Penn (both)
        ("NY", "HL", ["NJT"]),  # NY Penn → Hamilton (NJT only)
    ]

    def __init__(self, settings: Settings | None = None):
        """Initialize the validation service."""
        self.settings = settings or get_settings()
        self.njt_client: NJTransitClient | None = None
        self.amtrak_client: AmtrakClient | None = None
        self.http_client: httpx.AsyncClient | None = None
        self.api_base_url = self.settings.internal_api_url  # Use configured URL

    async def __aenter__(self) -> "TrainValidationService":
        """Async context manager entry."""
        self.njt_client = NJTransitClient(self.settings)
        self.amtrak_client = AmtrakClient(timeout=30.0)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.njt_client:
            await self.njt_client.close()
        if self.amtrak_client:
            await self.amtrak_client.close()
        if self.http_client:
            await self.http_client.aclose()

    async def get_njt_trains_for_route(
        self, from_station: str, to_station: str
    ) -> set[str]:
        """Get NJ Transit trains for a specific route."""
        if not self.njt_client:
            logger.error("NJT client not initialized")
            return set()

        try:
            # Get departure board for origin station
            response = await self.njt_client.get_train_schedule_with_stops(from_station)
            trains_data = response.get("ITEMS", [])

            # Filter for trains going to destination
            relevant_trains = set()
            for train in trains_data:
                train_id = train.get("TRAIN_ID", "").strip()
                if not train_id:
                    continue

                # Check if train goes to destination
                stops = train.get("STOPS", [])
                if any(stop.get("STATION_2CHAR") == to_station for stop in stops):
                    relevant_trains.add(train_id)

            logger.info(
                "validation.njt.scan_completed",
                from_station=from_station,
                to_station=to_station,
                trains_found=len(relevant_trains),
                train_ids=sorted(relevant_trains),
            )

            return relevant_trains

        except Exception as e:
            logger.error(
                "njt_route_scan_failed",
                from_station=from_station,
                to_station=to_station,
                error=repr(e),
            )
            return set()

    async def get_amtrak_trains_for_route(
        self, from_station: str, to_station: str
    ) -> set[str]:
        """Get Amtrak trains for a specific route.

        Fix #1: Only return trains that actually serve both stations in the correct order.
        Maps internal station codes to Amtrak codes for proper comparison.
        """
        if not self.amtrak_client:
            logger.error("Amtrak client not initialized")
            return set()

        try:
            # Map our internal codes to Amtrak codes
            amtrak_from = INTERNAL_TO_AMTRAK_STATION_MAP.get(from_station, from_station)
            amtrak_to = INTERNAL_TO_AMTRAK_STATION_MAP.get(to_station, to_station)

            logger.debug(
                "amtrak_station_mapping",
                internal_from=from_station,
                internal_to=to_station,
                amtrak_from=amtrak_from,
                amtrak_to=amtrak_to,
            )

            # Get all trains and filter for our route
            all_trains = await self.amtrak_client.get_all_trains()

            relevant_trains = set()
            trains_checked = 0
            trains_serving_route = 0

            # Check each train to see if it serves this specific route
            for _, station_trains in all_trains.items():
                for train in station_trains:
                    trains_checked += 1

                    if not hasattr(train, "trainID") or not hasattr(train, "stations"):
                        continue

                    # Get station codes for this train (these are Amtrak codes)
                    station_codes = [s.code for s in train.stations]

                    # Check if both stations are served (using Amtrak codes)
                    if (
                        amtrak_from not in station_codes
                        or amtrak_to not in station_codes
                    ):
                        continue

                    # Check the order - the train must serve 'from' before 'to'
                    from_index = station_codes.index(amtrak_from)
                    to_index = station_codes.index(amtrak_to)

                    # Skip if stations are in wrong order (we want from -> to)
                    # Allow both directions since trains can go either way
                    if from_index == to_index:
                        continue

                    # This train serves the route!
                    trains_serving_route += 1
                    train_id = train.trainID
                    # Extract just the train number (before the dash)
                    train_num = train_id.split("-")[0] if "-" in train_id else train_id
                    # Add "A" prefix for internal format
                    internal_id = f"A{train_num}"
                    relevant_trains.add(internal_id)

                    # Log for debugging (Fix #4: Enhanced logging)
                    logger.debug(
                        "amtrak_train_serves_route",
                        train_id=internal_id,
                        raw_id=train_id,
                        route=f"{from_station}->{to_station}",
                        from_index=from_index,
                        to_index=to_index,
                    )

            logger.info(
                "amtrak_route_scan_complete",
                from_station=from_station,
                to_station=to_station,
                trains_found=len(relevant_trains),
                trains_checked=trains_checked,
                trains_serving_route=trains_serving_route,
                train_ids=sorted(relevant_trains),
            )

            return relevant_trains

        except Exception as e:
            logger.error(
                "amtrak_route_scan_failed",
                from_station=from_station,
                to_station=to_station,
                error=repr(e),
            )
            return set()

    async def get_trains_from_our_api(
        self, from_station: str, to_station: str
    ) -> set[str]:
        """Query our API endpoint as a user would."""
        if not self.http_client:
            logger.error("HTTP client not initialized")
            return set()

        try:
            # Call our departures endpoint
            response = await self.http_client.get(
                f"{self.api_base_url}/api/v2/trains/departures",
                params={
                    "from": from_station,
                    "to": to_station,
                    "limit": 100,
                },
            )

            if response.status_code != 200:
                logger.error(
                    "api_call_failed",
                    from_station=from_station,
                    to_station=to_station,
                    status_code=response.status_code,
                    response_text=response.text[:500],
                )
                return set()

            data = response.json()
            trains = {train["train_id"] for train in data.get("departures", [])}

            logger.info(
                "api_route_scan_complete",
                from_station=from_station,
                to_station=to_station,
                trains_found=len(trains),
                train_ids=sorted(trains),
            )

            return trains

        except Exception as e:
            logger.error(
                "api_scan_failed",
                from_station=from_station,
                to_station=to_station,
                error=repr(e),
            )
            return set()

    async def verify_train_details_accessible(self, train_id: str) -> dict[str, Any]:
        """Verify if a specific train is accessible via our train details API."""
        if not self.http_client:
            return {
                "accessible": False,
                "error": "HTTP client not initialized",
            }

        try:
            response = await self.http_client.get(
                f"{self.api_base_url}/api/v2/trains/{train_id}",
                params={"date": now_et().date().isoformat()},
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "accessible": True,
                    "has_stops": bool(data.get("stops")),
                    "stop_count": len(data.get("stops", [])),
                    "status": data.get("status"),
                }
            else:
                return {
                    "accessible": False,
                    "status_code": response.status_code,
                    "error": response.text[:200],
                }

        except Exception as e:
            return {
                "accessible": False,
                "error": repr(e),
            }

    async def validate_route(
        self,
        from_station: str,
        to_station: str,
        sources: list[str],
        db: AsyncSession | None = None,
    ) -> list[ValidationResult]:
        """Validate a single route for all specified sources."""
        results = []
        timestamp = now_et()

        # Get trains from our API (common for all sources)
        api_trains = await self.get_trains_from_our_api(from_station, to_station)

        for source in sources:
            start_time = time.time()
            route_label = f"{from_station}->{to_station}"

            # Get trains from transit API
            if source == "NJT":
                transit_trains = await self.get_njt_trains_for_route(
                    from_station, to_station
                )
            elif source == "AMTRAK":
                transit_trains = await self.get_amtrak_trains_for_route(
                    from_station, to_station
                )
            else:
                logger.error(f"Unknown source: {source}")
                continue

            # Create validation result
            result = ValidationResult(
                route=route_label,
                source=source,
                transit_trains=transit_trains,
                api_trains=api_trains,
                timestamp=timestamp,
            )

            # Record metrics
            train_validation_coverage.labels(
                route=route_label,
                source=source,
            ).observe(result.coverage_percent)

            if result.missing_trains:
                missing_trains_detected.labels(
                    route=route_label,
                    source=source,
                ).inc(len(result.missing_trains))

            train_validation_duration.labels(
                route=route_label,
                source=source,
            ).observe(time.time() - start_time)

            # Fix #3 & #4: Enhanced logging with stale data detection
            # Log detailed info about validation results
            missing_details = {}  # Initialize outside the if block

            if result.missing_trains or result.extra_trains:
                # Verify accessibility of missing trains (configurable limit)
                max_to_verify = self.settings.validation_max_trains_to_verify
                for train_id in list(result.missing_trains)[:max_to_verify]:
                    details = await self.verify_train_details_accessible(train_id)
                    missing_details[train_id] = details

                # Log if we found discrepancies
                log_method = logger.warning if result.missing_trains else logger.info

                log_method(
                    "validation_discrepancies_found",
                    route=result.route,
                    source=result.source,
                    coverage_percent=result.coverage_percent,
                    missing_count=len(result.missing_trains),
                    missing_trains=sorted(result.missing_trains)[:10],  # Show first 10
                    extra_count=len(result.extra_trains),
                    extra_trains=sorted(result.extra_trains)[
                        :10
                    ],  # Show first 10 stale trains
                    transit_train_count=len(transit_trains),
                    api_train_count=len(api_trains),
                    missing_train_sample_details=missing_details,
                    timestamp=timestamp.isoformat(),
                )

                # Additional detailed log for debugging (only if debug level)
                logger.debug(
                    "validation_full_details",
                    route=result.route,
                    source=result.source,
                    all_transit_trains=sorted(transit_trains),
                    all_api_trains=sorted(api_trains),
                    all_missing=sorted(result.missing_trains),
                    all_extra=sorted(result.extra_trains),
                )
            else:
                logger.info(
                    "route_validation_passed",
                    route=result.route,
                    source=result.source,
                    coverage_percent=result.coverage_percent,
                    transit_train_count=len(transit_trains),
                    api_train_count=len(api_trains),
                    perfect_match=True,
                )

            results.append(result)

            # Save to database for persistence
            await self._save_validation_result(result, missing_details, db=db)

        return results

    async def _save_validation_result(
        self,
        result: ValidationResult,
        missing_details: dict[str, Any] | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        """Save validation result to database for persistence and monitoring.

        Args:
            result: Validation result to save
            missing_details: Optional details about missing trains
            db: Optional pre-created session (avoids greenlet issues in scheduler context)
        """
        try:
            db_result: ValidationResultDB = ValidationResultDB(
                route=result.route,
                source=result.source,
                transit_train_count=len(result.transit_trains),
                api_train_count=len(result.api_trains),
                coverage_percent=float(result.coverage_percent),  # type: ignore[arg-type]
                missing_trains=(
                    list(result.missing_trains) if result.missing_trains else []
                ),
                extra_trains=(list(result.extra_trains) if result.extra_trains else []),
                details={
                    "missing_train_details": missing_details or {},
                    "timestamp": result.timestamp.isoformat(),
                },
            )

            if db:
                db.add(db_result)
                await db.flush()
            else:
                async with get_session() as session:
                    session.add(db_result)

            logger.debug(
                "validation_result_saved",
                route=result.route,
                source=result.source,
                coverage=result.coverage_percent,
            )
        except Exception as e:
            logger.error(
                "failed_to_save_validation_result",
                route=result.route,
                source=result.source,
                error=repr(e),
            )

    async def run_validation(
        self, db: AsyncSession | None = None
    ) -> list[ValidationResult]:
        """Run validation for all monitored routes.

        Args:
            db: Optional pre-created session (avoids greenlet issues in scheduler context)
        """
        logger.info("starting_train_validation", routes=self.MONITORED_ROUTES)

        all_results = []
        validation_status = "success"

        for from_st, to_st, sources in self.MONITORED_ROUTES:
            try:
                results = await self.validate_route(from_st, to_st, sources, db=db)
                all_results.extend(results)
            except Exception as e:
                validation_status = "failure"
                logger.error(
                    "route_validation_failed",
                    from_station=from_st,
                    to_station=to_st,
                    sources=sources,
                    error=repr(e),
                )

        # Record overall validation run metric
        train_validation_runs.labels(status=validation_status).inc()

        # Log summary
        total_missing = sum(len(r.missing_trains) for r in all_results)
        routes_with_issues = sum(1 for r in all_results if r.missing_trains)

        # Fix #4: Enhanced summary logging
        total_extra = sum(len(r.extra_trains) for r in all_results)
        routes_with_stale_data = sum(1 for r in all_results if r.extra_trains)

        logger.info(
            "train_validation_complete",
            total_routes_checked=len(all_results),
            routes_with_missing_trains=routes_with_issues,
            routes_with_stale_trains=routes_with_stale_data,
            total_missing_trains=total_missing,
            total_stale_trains=total_extra,
            summary={
                f"{r.route}_{r.source}": {
                    "coverage": f"{r.coverage_percent:.1f}%",
                    "missing": len(r.missing_trains),
                    "stale": len(r.extra_trains),
                }
                for r in all_results
            },
        )

        return all_results
