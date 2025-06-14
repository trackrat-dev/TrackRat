"""
API service for TrackCast.
"""

import logging
import os
import time
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from trackcast.api.routers import stops, trains
from trackcast.db.connection import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TrackCast API",
    description="API for accessing train track predictions",
    version="0.1.0",
)

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
    Verifies database connection, model availability, and service readiness.
    """
    health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}

    overall_healthy = True

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
