"""
API service for TrackCast.
"""

import logging
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
    """Health check endpoint verifying database connection."""
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)},
        )


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
