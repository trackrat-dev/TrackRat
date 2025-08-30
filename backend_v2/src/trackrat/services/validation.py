"""
End-to-end train validation service.

Validates that trains from transit APIs are properly accessible through our API endpoints.
"""

import time
from datetime import datetime
from typing import Any

import httpx
from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.njt.client import NJTransitClient
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
        self.timestamp = timestamp
        self.coverage_percent = (
            (len(api_trains) / len(transit_trains) * 100) if transit_trains else 100
        )


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
        self.api_base_url = "http://localhost:8000"  # Internal API calls

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
                "njt_route_scan_complete",
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
                error=str(e),
            )
            return set()

    async def get_amtrak_trains_for_route(
        self, from_station: str, to_station: str
    ) -> set[str]:
        """Get Amtrak trains for a specific route."""
        if not self.amtrak_client:
            logger.error("Amtrak client not initialized")
            return set()

        try:
            # Get all trains and filter for our route
            all_trains = await self.amtrak_client.get_all_trains()

            relevant_trains = set()
            # Look for trains that serve both stations
            for _, station_trains in all_trains.items():
                for train in station_trains:
                    # Check if this train serves our route
                    # For simplicity, we'll add all Amtrak trains and let the API filter
                    if hasattr(train, "trainID"):
                        train_id = train.trainID
                        # Extract just the train number (before the dash)
                        train_num = (
                            train_id.split("-")[0] if "-" in train_id else train_id
                        )
                        # Add "A" prefix for internal format
                        internal_id = f"A{train_num}"
                        relevant_trains.add(internal_id)

            logger.info(
                "amtrak_route_scan_complete",
                from_station=from_station,
                to_station=to_station,
                trains_found=len(relevant_trains),
                train_ids=sorted(relevant_trains),
            )

            return relevant_trains

        except Exception as e:
            logger.error(
                "amtrak_route_scan_failed",
                from_station=from_station,
                to_station=to_station,
                error=str(e),
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
                error=str(e),
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
                "error": str(e),
            }

    async def validate_route(
        self, from_station: str, to_station: str, sources: list[str]
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

            # Log detailed info about missing trains
            if result.missing_trains:
                # Verify each missing train's accessibility
                missing_details = {}
                for train_id in result.missing_trains:
                    details = await self.verify_train_details_accessible(train_id)
                    missing_details[train_id] = details

                logger.warning(
                    "missing_trains_detected",
                    route=result.route,
                    source=result.source,
                    missing_count=len(result.missing_trains),
                    missing_trains=sorted(result.missing_trains),
                    coverage_percent=result.coverage_percent,
                    transit_trains_full=sorted(transit_trains),
                    api_trains_full=sorted(api_trains),
                    missing_train_details=missing_details,
                    timestamp=timestamp.isoformat(),
                )
            else:
                logger.info(
                    "route_validation_passed",
                    route=result.route,
                    source=result.source,
                    coverage_percent=result.coverage_percent,
                    train_count=len(transit_trains),
                )

            results.append(result)

        return results

    async def run_validation(self) -> list[ValidationResult]:
        """Run validation for all monitored routes."""
        logger.info("starting_train_validation", routes=self.MONITORED_ROUTES)

        all_results = []
        validation_status = "success"

        for from_st, to_st, sources in self.MONITORED_ROUTES:
            try:
                results = await self.validate_route(from_st, to_st, sources)
                all_results.extend(results)
            except Exception as e:
                validation_status = "failure"
                logger.error(
                    "route_validation_failed",
                    from_station=from_st,
                    to_station=to_st,
                    sources=sources,
                    error=str(e),
                )

        # Record overall validation run metric
        train_validation_runs.labels(status=validation_status).inc()

        # Log summary
        total_missing = sum(len(r.missing_trains) for r in all_results)
        routes_with_issues = sum(1 for r in all_results if r.missing_trains)

        logger.info(
            "train_validation_complete",
            total_routes_checked=len(all_results),
            routes_with_issues=routes_with_issues,
            total_missing_trains=total_missing,
            summary={
                f"{r.route}_{r.source}": {
                    "coverage": f"{r.coverage_percent:.1f}%",
                    "missing": len(r.missing_trains),
                }
                for r in all_results
            },
        )

        return all_results
