"""
Health and monitoring endpoints for TrackRat V2.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import DiscoveryRun, TrainJourney
from trackrat.services.scheduler import get_scheduler
from trackrat.settings import Settings, get_settings
from trackrat.utils.time import now_et

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    """Comprehensive health check covering database, scheduler, data freshness, and discovery."""
    # Health check logging handled by middleware to reduce noise

    health_status: dict[str, Any] = {
        "status": "healthy",
        "timestamp": now_et().isoformat(),
        "version": "2.0.0",
        "environment": settings.environment,
        "checks": {},
    }

    # Database check
    try:
        result = await db.execute(select(func.count(TrainJourney.id)))
        journey_count = result.scalar()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "journey_count": journey_count,
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}

    # Scheduler check
    try:
        scheduler = get_scheduler()
        scheduler_status = scheduler.get_status()
        health_status["checks"]["scheduler"] = {
            "status": "healthy" if scheduler_status["running"] else "unhealthy",
            "running": scheduler_status["running"],
            "jobs_count": scheduler_status["jobs_count"],
            "active_tasks": len(scheduler_status["active_tasks"]),
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["scheduler"] = {"status": "unhealthy", "error": str(e)}

    # Data freshness check
    try:
        cutoff = now_et() - timedelta(hours=2)
        stmt = select(func.count(TrainJourney.id)).where(
            and_(
                TrainJourney.last_updated_at > cutoff,
                TrainJourney.is_completed.is_not(True),
                TrainJourney.is_cancelled.is_not(True),
            )
        )
        result = await db.execute(stmt)
        fresh_count = result.scalar()

        health_status["checks"]["data_freshness"] = {
            "status": (
                "healthy" if fresh_count is not None and fresh_count > 0 else "warning"
            ),
            "fresh_journeys": fresh_count,
            "cutoff_hours": 2,
        }
    except Exception as e:
        health_status["checks"]["data_freshness"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Recent discovery runs
    try:
        discovery_stmt = (
            select(DiscoveryRun)
            .where(DiscoveryRun.run_at > now_et() - timedelta(hours=2))
            .order_by(DiscoveryRun.run_at.desc())
            .limit(5)
        )

        discovery_result = await db.execute(discovery_stmt)
        recent_discoveries: list[DiscoveryRun] = list(discovery_result.scalars().all())

        runs_count = len(recent_discoveries)
        discovery_stats = {
            "recent_runs": runs_count,
            "last_run": (
                recent_discoveries[0].run_at.isoformat()
                if recent_discoveries and recent_discoveries[0].run_at
                else None
            ),
            "success_rate": (
                sum(1 for d in recent_discoveries if d.success) / runs_count * 100
                if recent_discoveries
                else 0
            ),
        }

        health_status["checks"]["discovery"] = {
            "status": "healthy" if runs_count > 0 else "warning",
            **discovery_stats,
        }
    except Exception as e:
        health_status["checks"]["discovery"] = {"status": "unhealthy", "error": str(e)}

    # PostgreSQL with Cloud SQL provides automated backups
    health_status["checks"]["backup"] = {
        "status": "info",
        "enabled": True,
        "message": "Cloud SQL automated backups enabled",
    }

    # Overall status
    if any(
        check.get("status") == "unhealthy" for check in health_status["checks"].values()
    ):
        health_status["status"] = "unhealthy"
    elif any(
        check.get("status") == "warning" for check in health_status["checks"].values()
    ):
        health_status["status"] = "degraded"

    return health_status


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """Simple liveness probe for container orchestration."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe that verifies database connectivity and scheduler status."""
    try:
        # Quick database check
        await db.execute(select(1))

        # Check scheduler is running
        scheduler = get_scheduler()
        if not scheduler.scheduler.running:
            return {"status": "not_ready", "reason": "scheduler_not_running"}

        return {"status": "ready"}
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return {"status": "not_ready", "reason": str(e)}


@router.get("/scheduler/status")
async def scheduler_status() -> dict[str, Any]:
    """Get detailed scheduler status including job list, run counts, and active tasks."""
    scheduler = get_scheduler()
    return scheduler.get_status()
