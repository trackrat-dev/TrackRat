"""
API service for TrackCast.
"""

import logging
import os
import time
from typing import Callable

import httpx  # Added for external API checks
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import or_, text

from trackcast.api.routers import stops, trains
from trackcast.db.connection import get_db, get_pool_status_metrics

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TrackCast API",
    description="API for accessing train track predictions",
    version="0.1.0",
)

Instrumentator().instrument(app).expose(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    """Middleware to log request details and timing."""
    start_time = time.time()

    # Process the request
    response = await call_next(request)

    # Update DB pool metrics
    try:
        get_pool_status_metrics()
    except Exception as e:
        logger.error(f"Error updating DB pool metrics: {str(e)}")

    # Log request details
    process_time = time.time() - start_time
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"- Status: {response.status_code} "
        f"- Time: {process_time:.3f}s"
    )

    return response


# Include routers
app.include_router(trains.router, prefix="/api/trains", tags=["trains"])
app.include_router(stops.router, prefix="/api/stops", tags=["stops"])


# Root endpoint
@app.get("/", tags=["status"])
async def root():
    """Root endpoint returning service status."""
    return {
        "service": "TrackCast API",
        "status": "running",
        "version": "0.1.0",
    }


# Health check endpoint
@app.get("/health", tags=["status"])
async def health(db=Depends(get_db)):
    """
    Comprehensive health check endpoint for containerized inference service.
    Verifies database connection, model availability, service readiness, and external API connectivity.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func

    health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}
    overall_healthy = True

    # Get current time in Eastern timezone for database queries
    current_time = datetime.utcnow()

    # Placeholder URLs for external API health checks - replace with actual status endpoints
    NJ_TRANSIT_STATUS_URL = os.getenv(
        "NJ_TRANSIT_STATUS_URL", "https://api.njtransit.com/v2/status_placeholder"
    )
    AMTRAK_STATUS_URL = os.getenv(
        "AMTRAK_STATUS_URL", "https://api.amtrak.com/v2/status_placeholder"
    )

    # Check database connection
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }
        overall_healthy = False

    # Database metrics (only if database is healthy)
    if health_status["checks"]["database"]["status"] == "healthy":
        try:
            from trackcast.db.models import PredictionData, Train

            # Get DB pool status
            try:
                from trackcast.db.connection import engine

                pool = engine.pool
                pool_status = {
                    "size": pool.size(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "total": pool.size() + pool.overflow(),
                    "max_overflow": getattr(pool, "_max_overflow", 10),
                }
            except Exception as e:
                logger.warning(f"Could not get pool status: {str(e)}")
                pool_status = None

            # Basic counts with time windows
            one_hour_ago = current_time - timedelta(hours=1)
            one_day_ago = current_time - timedelta(days=1)
            five_minutes_ago = current_time - timedelta(minutes=5)

            # Total trains in last hour
            trains_last_hour = (
                db.query(func.count(Train.id)).filter(Train.created_at >= one_hour_ago).scalar()
            )

            # Total trains in last 24 hours
            trains_last_24h = (
                db.query(func.count(Train.id)).filter(Train.created_at >= one_day_ago).scalar()
            )

            # Trains with predictions in last hour
            trains_with_predictions = (
                db.query(func.count(Train.id))
                .filter(Train.created_at >= one_hour_ago, Train.prediction_data_id.isnot(None))
                .scalar()
            )

            # Trains with track assignments
            trains_with_tracks = (
                db.query(func.count(Train.id))
                .filter(
                    Train.created_at >= one_hour_ago, Train.track.isnot(None), Train.track != ""
                )
                .scalar()
            )

            # Data freshness indicators
            most_recent_train = db.query(func.max(Train.created_at)).scalar()
            most_recent_prediction = db.query(func.max(PredictionData.created_at)).scalar()

            # Count of active trains (not departed)
            active_trains = (
                db.query(func.count(Train.id))
                .filter(
                    Train.departure_time >= current_time,
                    Train.status != "DEPARTED",
                    Train.track_released_at.is_(None),
                )
                .scalar()
            )

            # Source breakdown
            trains_by_source = dict(
                db.query(Train.data_source, func.count(Train.id))
                .filter(Train.created_at >= one_hour_ago)
                .group_by(Train.data_source)
                .all()
            )

            trains_by_station = dict(
                db.query(Train.origin_station_code, func.count(Train.id))
                .filter(Train.created_at >= one_hour_ago)
                .group_by(Train.origin_station_code)
                .all()
            )

            # Count trains missing critical fields (in last hour)
            trains_missing_fields = (
                db.query(func.count(Train.id))
                .filter(
                    Train.created_at >= one_hour_ago,
                    or_(
                        Train.line.is_(None),
                        Train.line == "",
                        Train.destination.is_(None),
                        Train.destination == "",
                        Train.departure_time.is_(None),
                    ),
                )
                .scalar()
            )

            # Quality metrics
            track_assignment_rate = (
                (trains_with_tracks / trains_last_hour * 100) if trains_last_hour > 0 else 0
            )
            prediction_rate = (
                (trains_with_predictions / trains_last_hour * 100) if trains_last_hour > 0 else 0
            )
            missing_fields_rate = (
                (trains_missing_fields / trains_last_hour * 100) if trains_last_hour > 0 else 0
            )

            # Check for stale data
            stale_data_warning = False
            if most_recent_train:
                minutes_since_update = (current_time - most_recent_train).total_seconds() / 60
                if minutes_since_update > 5:
                    stale_data_warning = True

            health_status["checks"]["database_metrics"] = {
                "status": "healthy" if not stale_data_warning else "warning",
                "basic_counts": {
                    "trains_last_hour": trains_last_hour,
                    "trains_last_24h": trains_last_24h,
                    "trains_with_predictions_last_hour": trains_with_predictions,
                    "trains_with_tracks_last_hour": trains_with_tracks,
                    "active_trains": active_trains,
                    "trains_missing_critical_fields": trains_missing_fields,
                },
                "data_freshness": {
                    "most_recent_train": (
                        most_recent_train.isoformat() if most_recent_train else None
                    ),
                    "most_recent_prediction": (
                        most_recent_prediction.isoformat() if most_recent_prediction else None
                    ),
                    "minutes_since_last_train": (
                        round(minutes_since_update, 1) if most_recent_train else None
                    ),
                    "stale_data_warning": stale_data_warning,
                },
                "source_breakdown": {
                    "by_data_source": trains_by_source,
                    "by_origin_station": trains_by_station,
                },
                "quality_metrics": {
                    "track_assignment_rate": round(track_assignment_rate, 1),
                    "prediction_rate": round(prediction_rate, 1),
                    "missing_fields_rate": round(missing_fields_rate, 1),
                },
                "connection_pool": pool_status,
            }

        except Exception as e:
            logger.error(f"Database metrics check failed: {str(e)}")
            health_status["checks"]["database_metrics"] = {
                "status": "error",
                "message": f"Failed to gather database metrics: {str(e)}",
            }

    # Check model directory and availability
    model_path = os.getenv("MODEL_PATH", "/app/models")
    try:
        if os.path.exists(model_path) and os.path.isdir(model_path):
            # Check if any model files exist
            model_files = [
                f for f in os.listdir(model_path) if f.endswith((".pt", ".pkl", ".json"))
            ]
            if model_files:
                health_status["checks"]["models"] = {
                    "status": "healthy",
                    "message": f"Found {len(model_files)} model files",
                    "model_path": model_path,
                }
            else:
                health_status["checks"]["models"] = {
                    "status": "warning",
                    "message": "Model directory exists but no model files found",
                    "model_path": model_path,
                }
                # Don't mark as unhealthy - models might be loaded later
        else:
            health_status["checks"]["models"] = {
                "status": "warning",
                "message": "Model directory not found",
                "model_path": model_path,
            }
    except Exception as e:
        logger.error(f"Model path health check failed: {str(e)}")
        health_status["checks"]["models"] = {
            "status": "error",
            "message": f"Error checking model path: {str(e)}",
            "model_path": model_path,
        }

    # Check environment configuration
    env_checks = {
        "TRACKCAST_ENV": os.getenv("TRACKCAST_ENV"),
        "MODEL_PATH": os.getenv("MODEL_PATH"),
        "DATABASE_URL": "***" if os.getenv("DATABASE_URL") else None,
    }

    missing_env = [k for k, v in env_checks.items() if v is None]
    if missing_env:
        health_status["checks"]["environment"] = {
            "status": "warning",
            "message": f"Missing environment variables: {', '.join(missing_env)}",
            "configured": {k: v for k, v in env_checks.items() if v is not None},
        }
    else:
        health_status["checks"]["environment"] = {
            "status": "healthy",
            "message": "All required environment variables configured",
        }

    # Check NJ Transit API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(NJ_TRANSIT_STATUS_URL)
            if response.status_code == 200:
                health_status["checks"]["nj_transit_api"] = {
                    "status": "healthy",
                    "message": "NJ Transit API reachable",
                }
            else:
                health_status["checks"]["nj_transit_api"] = {
                    "status": "unhealthy",
                    "message": f"NJ Transit API error: HTTP {response.status_code}",
                }
                overall_healthy = False
    except Exception as e:
        logger.error(f"NJ Transit API health check failed: {str(e)}")
        health_status["checks"]["nj_transit_api"] = {
            "status": "unhealthy",
            "message": f"NJ Transit API connection failed: {str(e)}",
        }
        overall_healthy = False

    # Check Amtrak API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(AMTRAK_STATUS_URL)
            if response.status_code == 200:
                health_status["checks"]["amtrak_api"] = {
                    "status": "healthy",
                    "message": "Amtrak API reachable",
                }
            else:
                health_status["checks"]["amtrak_api"] = {
                    "status": "unhealthy",
                    "message": f"Amtrak API error: HTTP {response.status_code}",
                }
                overall_healthy = False
    except Exception as e:
        logger.error(f"Amtrak API health check failed: {str(e)}")
        health_status["checks"]["amtrak_api"] = {
            "status": "unhealthy",
            "message": f"Amtrak API connection failed: {str(e)}",
        }
        overall_healthy = False

    # Set overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=health_status)

    return health_status


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
