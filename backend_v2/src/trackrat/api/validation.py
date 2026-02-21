"""
API endpoints for train validation monitoring.

Provides access to validation results for system monitoring and debugging.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import ValidationResult as ValidationResultDB
from trackrat.utils.time import now_et

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/validation", tags=["validation"])


@router.get("/status")
async def get_validation_status(
    hours: int = Query(
        default=24, description="Hours of history to return", ge=1, le=168
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get validation status and recent results.

    Returns per-route coverage metrics, missing/extra trains, and trends over the
    specified time period. Overall health is derived from average coverage percentage.
    """
    try:
        # Calculate time window
        cutoff_time = now_et() - timedelta(hours=hours)

        # Query recent validation results
        stmt = (
            select(ValidationResultDB)
            .where(ValidationResultDB.run_at >= cutoff_time)
            .order_by(desc(ValidationResultDB.run_at))
        )

        result = await db.execute(stmt)
        results = result.scalars().all()

        if not results:
            return {
                "status": "no_data",
                "message": f"No validation results found in the last {hours} hours",
                "hours_requested": hours,
            }

        # Calculate aggregate statistics
        total_runs = len(results)
        latest_run = results[0].run_at if results else None

        # Group by route and source for coverage analysis
        route_stats: dict[str, Any] = {}
        for r in results:
            key = f"{r.route}_{r.source}"
            if key not in route_stats:
                route_stats[key] = {
                    "route": r.route,
                    "source": r.source,
                    "runs": 0,
                    "coverage_values": [],
                    "missing_trains_total": set(),
                    "extra_trains_total": set(),
                    "latest_coverage": 0,
                    "latest_missing": [],
                    "latest_extra": [],
                }

            stats = route_stats[key]
            stats["runs"] += 1
            stats["coverage_values"].append(r.coverage_percent)

            if r.missing_trains:
                stats["missing_trains_total"].update(r.missing_trains)
            if r.extra_trains:
                stats["extra_trains_total"].update(r.extra_trains)

            # Track latest values
            if stats["runs"] == 1:  # First (most recent) for this route
                stats["latest_coverage"] = r.coverage_percent
                stats["latest_missing"] = r.missing_trains or []
                stats["latest_extra"] = r.extra_trains or []

        # Calculate summary statistics for each route
        route_summary = []
        for stats in route_stats.values():
            coverage_values = stats["coverage_values"]
            route_summary.append(
                {
                    "route": stats["route"],
                    "source": stats["source"],
                    "runs": stats["runs"],
                    "latest_coverage": round(stats["latest_coverage"], 2),
                    "average_coverage": round(
                        sum(coverage_values) / len(coverage_values), 2
                    ),
                    "min_coverage": round(min(coverage_values), 2),
                    "max_coverage": round(max(coverage_values), 2),
                    "unique_missing_trains": len(stats["missing_trains_total"]),
                    "unique_extra_trains": len(stats["extra_trains_total"]),
                    "latest_missing": sorted(stats["latest_missing"])[:10],  # Top 10
                    "latest_extra": sorted(stats["latest_extra"])[:10],  # Top 10
                }
            )

        # Sort by route and source
        route_summary.sort(key=lambda x: (x["route"], x["source"]))

        # Calculate overall health score
        all_coverage_values = [
            r.coverage_percent for r in results if r.coverage_percent is not None
        ]
        avg_coverage = (
            sum(all_coverage_values) / len(all_coverage_values)
            if all_coverage_values
            else 0.0
        )

        # Determine overall status
        if avg_coverage >= 95:
            overall_status = "healthy"
        elif avg_coverage >= 85:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "summary": {
                "total_validation_runs": total_runs,
                "hours_analyzed": hours,
                "latest_run": latest_run.isoformat() if latest_run else None,
                "average_coverage": round(avg_coverage, 2),
                "routes_monitored": len(route_stats),
            },
            "routes": route_summary,
            "recent_results": [
                {
                    "run_at": r.run_at.isoformat() if r.run_at else None,
                    "route": r.route,
                    "source": r.source,
                    "coverage_percent": r.coverage_percent,
                    "transit_train_count": r.transit_train_count,
                    "api_train_count": r.api_train_count,
                    "missing_count": len(r.missing_trains) if r.missing_trains else 0,
                    "extra_count": len(r.extra_trains) if r.extra_trains else 0,
                }
                for r in results[:20]  # Most recent 20 results
            ],
        }

    except Exception as e:
        logger.error("validation_status_query_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to retrieve validation status"
        ) from e


@router.get("/results/{route}/{source}")
async def get_route_validation_details(
    route: str,
    source: str,
    limit: int = Query(
        default=10, description="Number of results to return", ge=1, le=100
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed validation results for a specific route and source.

    Returns recent validation runs with coverage percentages, train counts,
    and lists of missing/extra trains.
    """
    try:
        # Query validation results for this route/source
        stmt = (
            select(ValidationResultDB)
            .where(
                ValidationResultDB.route == route,
                ValidationResultDB.source == source,
            )
            .order_by(desc(ValidationResultDB.run_at))
            .limit(limit)
        )

        result = await db.execute(stmt)
        results = result.scalars().all()

        if not results:
            return {
                "route": route,
                "source": source,
                "message": "No validation results found for this route and source",
            }

        # Format detailed results
        detailed_results = []
        for r in results:
            detailed_results.append(
                {
                    "run_at": r.run_at.isoformat() if r.run_at else None,
                    "coverage_percent": r.coverage_percent,
                    "transit_train_count": r.transit_train_count,
                    "api_train_count": r.api_train_count,
                    "missing_trains": r.missing_trains or [],
                    "extra_trains": r.extra_trains or [],
                    "details": r.details or {},
                }
            )

        return {
            "route": route,
            "source": source,
            "results": detailed_results,
        }

    except Exception as e:
        logger.error(
            "route_validation_details_query_failed",
            route=route,
            source=source,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve route validation details"
        ) from e
