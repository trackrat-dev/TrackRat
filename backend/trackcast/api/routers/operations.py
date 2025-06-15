"""
Operations router for TrackCast API.
Provides endpoints for Cloud Scheduler to trigger various operations.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from trackcast.db.connection import get_db
from trackcast.services.data_collector import DataCollectorService
from trackcast.services.feature_engineering import FeatureEngineeringService
from trackcast.services.prediction import PredictionService

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_scheduler_auth(request: Request) -> bool:
    """
    Verify that the request comes from an authorized Cloud Scheduler.
    This checks for OIDC token authentication headers.
    """
    # Check for OIDC token in Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False

    # In production, you would validate the JWT token here
    # For now, we'll accept any Bearer token as valid
    # TODO: Implement proper OIDC token validation
    return True


async def get_scheduler_auth(request: Request):
    """Dependency for scheduler authentication."""
    if not verify_scheduler_auth(request):
        raise HTTPException(
            status_code=401, detail="Unauthorized: Valid scheduler authentication required"
        )


@router.post("/collect-data")
async def trigger_data_collection(
    request: Request, db: Session = Depends(get_db), _auth: None = Depends(get_scheduler_auth)
) -> Dict[str, Any]:
    """
    Trigger data collection from NJ Transit and Amtrak APIs.
    Called by Cloud Scheduler to replace internal scheduler data collection.
    """
    start_time = time.time()

    try:
        logger.info("Starting scheduled data collection")

        # Initialize data collector service
        collector = DataCollectorService(db)

        # Run data collection
        success, stats = collector.run_collection()

        processing_time = time.time() - start_time

        response_data = {
            "success": success,
            "operation": "data_collection",
            "timestamp": time.time(),
            "processing_time_seconds": round(processing_time, 3),
            "stats": stats,
        }

        if success:
            logger.info(
                f"Data collection completed successfully in {processing_time:.3f}s: {stats}"
            )
            return response_data
        else:
            logger.error(f"Data collection failed after {processing_time:.3f}s: {stats}")
            return JSONResponse(status_code=500, content=response_data)

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Data collection failed with exception: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "operation": "data_collection",
                "timestamp": time.time(),
                "processing_time_seconds": round(processing_time, 3),
                "error": error_msg,
            },
        )


@router.post("/process-features")
async def trigger_feature_processing(
    request: Request, db: Session = Depends(get_db), _auth: None = Depends(get_scheduler_auth)
) -> Dict[str, Any]:
    """
    Trigger feature processing for collected train data.
    Called by Cloud Scheduler to replace internal scheduler feature engineering.
    """
    start_time = time.time()

    try:
        logger.info("Starting scheduled feature processing")

        # Initialize feature engineering service
        feature_service = FeatureEngineeringService(db)

        # Process features for future trains (as done in scheduler)
        success, stats = feature_service.process_future_trains_with_regeneration()

        processing_time = time.time() - start_time

        response_data = {
            "success": success,
            "operation": "feature_processing",
            "timestamp": time.time(),
            "processing_time_seconds": round(processing_time, 3),
            "stats": stats,
        }

        if success:
            logger.info(
                f"Feature processing completed successfully in {processing_time:.3f}s: {stats}"
            )
            return response_data
        else:
            logger.error(f"Feature processing failed after {processing_time:.3f}s: {stats}")
            return JSONResponse(status_code=500, content=response_data)

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Feature processing failed with exception: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "operation": "feature_processing",
                "timestamp": time.time(),
                "processing_time_seconds": round(processing_time, 3),
                "error": error_msg,
            },
        )


@router.post("/generate-predictions")
async def trigger_prediction_generation(
    request: Request, db: Session = Depends(get_db), _auth: None = Depends(get_scheduler_auth)
) -> Dict[str, Any]:
    """
    Trigger prediction generation for upcoming trains.
    Called by Cloud Scheduler to replace internal scheduler prediction generation.
    """
    start_time = time.time()

    try:
        logger.info("Starting scheduled prediction generation")

        # Initialize prediction service
        prediction_service = PredictionService(db)

        # Run prediction generation with regeneration (as done in scheduler)
        success, stats = prediction_service.run_prediction_with_regeneration()

        processing_time = time.time() - start_time

        response_data = {
            "success": success,
            "operation": "prediction_generation",
            "timestamp": time.time(),
            "processing_time_seconds": round(processing_time, 3),
            "stats": stats,
        }

        if success:
            logger.info(
                f"Prediction generation completed successfully in {processing_time:.3f}s: {stats}"
            )
            return response_data
        else:
            logger.error(f"Prediction generation failed after {processing_time:.3f}s: {stats}")
            return JSONResponse(status_code=500, content=response_data)

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Prediction generation failed with exception: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "operation": "prediction_generation",
                "timestamp": time.time(),
                "processing_time_seconds": round(processing_time, 3),
                "error": error_msg,
            },
        )


@router.get("/health-check")
async def comprehensive_health_check(
    request: Request, db: Session = Depends(get_db), _auth: None = Depends(get_scheduler_auth)
) -> Dict[str, Any]:
    """
    Comprehensive health check for scheduler operations.
    Called by Cloud Scheduler to monitor system health.
    """
    try:
        logger.info("Running comprehensive health check")

        health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}

        overall_healthy = True

        # Database connectivity check
        try:
            from sqlalchemy import text

            db.execute(text("SELECT 1")).fetchone()
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful",
            }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}",
            }
            overall_healthy = False

        # Model availability check
        model_path = os.getenv("MODEL_PATH", "/app/models")
        try:
            if os.path.exists(model_path) and os.path.isdir(model_path):
                model_files = [
                    f for f in os.listdir(model_path) if f.endswith((".pt", ".pkl", ".json"))
                ]
                if model_files:
                    health_status["checks"]["models"] = {
                        "status": "healthy",
                        "message": f"Found {len(model_files)} model files",
                        "model_files": model_files,
                    }
                else:
                    health_status["checks"]["models"] = {
                        "status": "warning",
                        "message": "Model directory exists but no model files found",
                    }
            else:
                health_status["checks"]["models"] = {
                    "status": "warning",
                    "message": "Model directory not found",
                }
        except Exception as e:
            health_status["checks"]["models"] = {
                "status": "error",
                "message": f"Error checking model directory: {str(e)}",
            }

        # Check recent data collection
        try:
            from trackcast.db.models import Train

            recent_trains = (
                db.query(Train)
                .filter(Train.created_at >= datetime.utcnow() - timedelta(hours=1))  # Last hour
                .count()
            )

            health_status["checks"]["recent_data"] = {
                "status": "healthy" if recent_trains > 0 else "warning",
                "message": f"Found {recent_trains} trains collected in last hour",
                "recent_trains": recent_trains,
            }
        except Exception as e:
            health_status["checks"]["recent_data"] = {
                "status": "error",
                "message": f"Error checking recent data: {str(e)}",
            }

        # Environment configuration check
        required_env_vars = ["DATABASE_URL", "TRACKCAST_ENV"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            health_status["checks"]["environment"] = {
                "status": "warning",
                "message": f"Missing environment variables: {', '.join(missing_vars)}",
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

        logger.info("Health check completed successfully")
        return health_status

    except Exception as e:
        error_msg = f"Health check failed with exception: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return JSONResponse(
            status_code=500,
            content={"status": "error", "timestamp": time.time(), "error": error_msg},
        )


@router.get("/status")
async def operations_status() -> Dict[str, Any]:
    """
    Simple status endpoint for operations router.
    No authentication required - useful for basic connectivity checks.
    """
    return {
        "service": "TrackCast Operations API",
        "status": "running",
        "timestamp": time.time(),
        "endpoints": [
            "POST /api/ops/collect-data",
            "POST /api/ops/process-features",
            "POST /api/ops/generate-predictions",
            "GET /api/ops/health-check",
            "GET /api/ops/status",
        ],
    }
