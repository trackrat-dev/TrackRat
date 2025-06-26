"""
Command-line interface for TrackCast.
"""

import logging
import os
import sys
import time
from typing import Dict, Optional, Set, Tuple, Union

import click
import uvicorn
from sqlalchemy import create_engine

import trackcast.constants as constants
from trackcast.config import settings
from trackcast.db.connection import get_db_session
from trackcast.db.migrations import run_migrations
from trackcast.db.models import Base
from trackcast.services.data_collector import DataCollectorService
from trackcast.services.data_import import DataImportService
from trackcast.services.feature_engineering import FeatureEngineeringService
from trackcast.services.prediction import PredictionService
from trackcast.services.push_notification import event_detector, notification_service

# SchedulerService removed - using Cloud Run Jobs for scheduling

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("trackcast.log")],
)

logger = logging.getLogger(__name__)


def _process_push_notifications(session) -> None:
    """
    Shared push notification processing for both direct and pipeline usage.

    Args:
        session: Database session
    """
    try:
        import asyncio
        from datetime import datetime, timedelta

        from trackcast.db.repository import TrainRepository

        logger.info("🔔 Starting push notification processing")
        train_repo = TrainRepository(session)

        # Get recent trains that might have Live Activities
        recent_cutoff = datetime.utcnow() - timedelta(hours=6)
        logger.debug(f"🔍 Querying trains with Live Activities since {recent_cutoff}")
        recent_trains = train_repo.get_trains_with_live_activities(since=recent_cutoff)

        logger.info(f"🚂 Found {len(recent_trains)} trains with potential Live Activities")
        if len(recent_trains) == 0:
            logger.info("ℹ️ No trains with Live Activities found - skipping notification processing")
        else:
            # Log train details for debugging
            train_ids = [t.train_id for t in recent_trains[:5]]  # Show first 5
            logger.debug(
                f"📝 Sample train IDs: {train_ids}{'...' if len(recent_trains) > 5 else ''}"
            )

        # Process notifications asynchronously
        logger.info("📱 Processing train state changes for Live Activity updates")
        asyncio.run(notification_service.process_train_updates(recent_trains, session))

        logger.info(f"✅ Push notification processing completed for {len(recent_trains)} trains")

        # Process stop departure and approaching stop events
        logger.info("🚉 Processing stop events for Live Activities")
        stop_events_processed = 0
        for train in recent_trains:
            logger.debug(f"🔍 Processing stop events for train {train.train_id}")
            asyncio.run(event_detector.process_train_for_events(train, session))
            stop_events_processed += 1

        # Clean up old notification history
        logger.debug("🧹 Cleaning up old notification history")
        event_detector.cleanup_old_notifications()

        logger.info(f"✅ Stop event processing completed for {stop_events_processed} trains")

    except Exception as e:
        logger.warning(f"Push notification processing failed (continuing anyway): {e}")


@click.group()
@click.option("--env", "-e", type=str, default="dev", help="Environment (dev, prod)")
@click.version_option(version=constants.VERSION)
def main(env: str) -> None:
    """TrackCast CLI - Train Track Prediction System for NY Penn Station"""
    # Set environment variable for configuration
    os.environ["TRACKCAST_ENV"] = env
    logger.info(f"Using environment: {env}")


@main.command()
def init_db() -> None:
    """Initialize the database schema and run migrations"""
    try:
        # Get database URL from settings
        db_url = settings.database.url
        logger.info(f"Initializing database at {db_url}")

        # Create engine and tables
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        logger.info("Database initialized successfully")

        # Run migrations
        session = get_db_session()
        try:
            logger.info("Running database migrations...")
            results = run_migrations(session)
            for result in results:
                if result["status"] == "success":
                    logger.info(f"✓ {result['name']}: {result['message']}")
                elif result["status"] == "skipped":
                    logger.debug(f"- {result['name']}: {result['message']}")
                else:
                    logger.warning(f"✗ {result['name']}: {result['message']}")
            logger.info("Migrations completed")
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        sys.exit(1)


@main.command()
def update_schema() -> None:
    """Update database schema by running pending migrations"""
    try:
        logger.info("Running database migrations...")

        session = get_db_session()
        try:
            results = run_migrations(session)

            success_count = 0
            skipped_count = 0
            error_count = 0

            for result in results:
                if result["status"] == "success":
                    logger.info(f"✓ {result['name']}: {result['message']}")
                    success_count += 1
                elif result["status"] == "skipped":
                    logger.debug(f"- {result['name']}: {result['message']}")
                    skipped_count += 1
                else:
                    logger.error(f"✗ {result['name']}: {result['message']}")
                    error_count += 1

            logger.info(
                f"Migrations completed: {success_count} applied, "
                f"{skipped_count} skipped, {error_count} errors"
            )

            if error_count > 0:
                sys.exit(1)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error updating schema: {str(e)}")
        sys.exit(1)


@main.command()
@click.option(
    "--validate-journeys",
    is_flag=True,
    default=True,
    help="Run post-journey validation (default: enabled)",
)
def collect_data(validate_journeys: bool) -> None:
    """Run a one-time data collection from NJ Transit API with optional journey validation"""
    try:
        session = get_db_session()
        collector = DataCollectorService(session)

        success, stats = collector.run_collection()
        if success:
            # Log appropriate message based on whether there were any failures
            if stats.get("stations_failed", 0) > 0:
                logger.warning(f"Data collection completed with partial success: {stats}")
            else:
                logger.info(f"Data collection completed successfully: {stats}")

            # Process train updates for push notifications
            _process_push_notifications(session)

            # Run post-journey validation if enabled
            if validate_journeys:
                try:
                    from trackcast.db.repository import TrainRepository, TrainStopRepository
                    from trackcast.services.journey_validator import JourneyValidator

                    logger.info("Running post-journey validation")
                    train_repo = TrainRepository(session)
                    stop_repo = TrainStopRepository(session)
                    validator = JourneyValidator(train_repo, stop_repo)

                    validated_trains = validator.validate_completed_journeys(batch_size=10)
                    logger.info(
                        f"Journey validation completed: {len(validated_trains)} trains validated"
                    )

                except Exception as e:
                    logger.warning(f"Journey validation failed (continuing anyway): {e}")
        else:
            logger.error(f"Data collection failed: all stations failed: {stats}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in collect_data command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


@main.command()
@click.option("--clear", is_flag=True, help="Clear features instead of processing them")
@click.option(
    "--train-id", type=str, help="Clear features for a specific train ID (used with --clear)"
)
@click.option(
    "--time-range",
    nargs=2,
    type=click.DateTime(),
    help="Clear features for a time range (used with --clear)",
)
@click.option(
    "--debug", is_flag=True, help="Enable debug logging for detailed track usage information"
)
def process_features(
    clear: bool, train_id: Optional[str], time_range: Optional[Tuple], debug: bool
) -> None:
    """Process collected train data to generate features"""
    try:
        # Set debug logging if requested
        if debug:
            logging.getLogger("trackcast.features").setLevel(logging.DEBUG)
            logging.getLogger("trackcast.features.extractors").setLevel(logging.DEBUG)
            logging.getLogger().info("Debug logging enabled for feature extraction")

        session = get_db_session()
        feature_service = FeatureEngineeringService(session)

        if clear:
            # Parse time range if provided
            start_time = None
            end_time = None
            if time_range and len(time_range) == 2:
                start_time, end_time = time_range

            # Call clear_features with appropriate parameters
            logger.info("Clearing features as requested")
            success, stats = feature_service.clear_features(
                train_id=train_id, start_time=start_time, end_time=end_time
            )

            if success:
                logger.info(f"Feature clearing completed: {stats}")
            else:
                logger.error(f"Feature clearing failed: {stats}")
                sys.exit(1)
        else:
            # Normal process_features operation
            success, stats = feature_service.process_pending_trains()
            if success:
                logger.info(f"Feature engineering completed: {stats}")
            else:
                logger.error(f"Feature engineering failed: {stats}")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Error in process_features command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


@main.command()
@click.option("--clear", is_flag=True, help="Clear predictions instead of generating them")
@click.option("--train-id", type=str, help="Filter to a specific train ID")
@click.option(
    "--time-range",
    nargs=2,
    type=click.DateTime(),
    help="Filter to trains within a time range (start_time end_time)",
)
@click.option("--future", is_flag=True, help="Filter to trains with future departure times")
def generate_predictions(
    clear: bool, train_id: Optional[str], time_range: Optional[Tuple], future: Optional[bool]
) -> None:
    """Generate track predictions for upcoming trains"""
    try:
        session = get_db_session()
        prediction_service = PredictionService(session)

        # Parse time range if provided
        parsed_time_range = None
        if time_range:
            parsed_time_range = (time_range[0], time_range[1])

        # Validate conflicting options
        filter_count = sum([bool(train_id), bool(time_range), future])
        if filter_count > 1:
            click.echo(
                "Cannot use multiple filtering options simultaneously. Use only one of: --train-id, --time-range, or --future",
                err=True,
            )
            sys.exit(1)

        if clear:
            # Handle clearing predictions
            logger.info("Clearing predictions as requested")
            success, stats = prediction_service.clear_predictions(
                train_id=train_id, time_range=parsed_time_range, future_only=future
            )

            if success:
                logger.info(f"Prediction clearing completed: {stats}")
            else:
                logger.error(f"Prediction clearing failed: {stats}")
                sys.exit(1)
        else:
            # Normal prediction generation with optional filtering
            success, stats = prediction_service.run_prediction(
                train_id=train_id, time_range=parsed_time_range, future_only=future
            )

            if success:
                logger.info(f"Prediction completed: {stats}")
            else:
                logger.error(f"Prediction failed: {stats}")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Error in generate_predictions command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


@main.command()
@click.option("--limit", "-l", type=int, default=None, help="Limit number of trains to process")
@click.option("--clear-old", is_flag=True, help="Clear outdated estimated arrival times")
def update_estimated_arrivals(limit: Optional[int], clear_old: bool) -> None:
    """Update estimated arrival times for active trains with delays"""
    try:
        from trackcast.services.estimated_arrival_service import EstimatedArrivalService

        logger.info("Starting estimated arrival time updates")
        session = get_db_session()

        try:
            service = EstimatedArrivalService(session)

            # Clear old estimates if requested
            if clear_old:
                cleared_count = service.clear_outdated_estimates()
                logger.info(f"Cleared {cleared_count} outdated estimated arrival times")

            # Update estimates for active trains
            updated_count = service.update_estimated_arrivals_for_active_trains(limit=limit)

            if updated_count > 0:
                logger.info(
                    f"Successfully updated {updated_count} stops with estimated arrival times"
                )
            else:
                logger.info("No stops required estimated arrival time updates")

        except Exception as e:
            logger.error(f"Error updating estimated arrivals: {str(e)}")
            sys.exit(1)
        finally:
            session.close()

    except ImportError as e:
        logger.error(f"EstimatedArrivalService not available: {e}")
        sys.exit(1)


@main.command()
@click.option("--host", "-h", type=str, default="127.0.0.1", help="API host")
@click.option("--port", "-p", type=int, default=8000, help="API port")
def start_api(host: str, port: int) -> None:
    """Start the API service"""
    try:
        logger.info(f"Starting API server at {host}:{port}")
        uvicorn.run(
            "trackcast.api.app:app", host=host, port=port, reload=settings.debug, log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting API: {str(e)}")
        sys.exit(1)


# start_scheduler command removed - use Cloud Run Jobs for scheduling


@main.command()
@click.option(
    "--station", "-s", type=str, help="Train model for specific station code (e.g., 'NY', 'TR')"
)
@click.option("--all-stations", is_flag=True, help="Train models for all stations")
def train_model(station: Optional[str], all_stations: bool) -> None:
    """Train prediction models using historical data"""
    try:
        # Check if training dependencies are available
        try:
            import matplotlib
            import seaborn
        except ImportError as e:
            logger.error("Training dependencies not available (matplotlib, seaborn)")
            logger.error("This command is not available in inference-only environments")
            logger.error(f"Missing: {e}")
            sys.exit(1)

        from trackcast.models.training import (
            train_model_for_station,
            train_models_for_all_stations,
            train_new_model,
        )

        logger.info("Starting model training")
        session = get_db_session()

        try:
            if all_stations:
                # Train models for all stations
                logger.info("Training models for all stations")
                success, stats = train_models_for_all_stations(session)

                if success:
                    logger.info(f"Station-specific model training completed: {stats}")
                else:
                    logger.error(f"Some station models failed to train: {stats}")
                    sys.exit(1)
            elif station:
                # Train model for specific station
                logger.info(f"Training model for station {station}")
                success, stats = train_model_for_station(session, station)

                if success:
                    logger.info(f"Model training completed for station {station}: {stats}")
                else:
                    logger.error(f"Model training failed for station {station}: {stats}")
                    sys.exit(1)
            else:
                # Default behavior - train combined model (legacy)
                logger.info("Training combined model (legacy behavior)")
                train_new_model(session)
                logger.info("Model training completed")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in train_model command: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--source", "-s", type=str, help="Directory containing data files")
@click.option("--format", "-f", type=click.Choice(["csv", "json"]), help="Data file format")
@click.option("--pattern", "-p", type=str, help="File pattern (e.g., '*.csv')")
@click.option("--clear", is_flag=True, help="Clear all train data from the database before import")
def import_data(
    source: Optional[str], format: Optional[str], pattern: Optional[str], clear: bool
) -> None:
    """Import train data from files into the database"""
    try:
        session = get_db_session()

        try:
            # Create import service
            import_service = DataImportService(session)

            # If clear flag is set, clear the database first
            if clear:
                logger.info("Clearing database before import")
                success, clear_stats = import_service.clear_data()

                if not success:
                    logger.error(f"Failed to clear database: {clear_stats}")
                    sys.exit(1)

                logger.info(f"Database cleared: {clear_stats['trains_deleted']} trains removed")

            # If source is provided, run the import
            if source:
                logger.info(f"Starting data import from {source}")

                # Run import (always overwrite existing records)
                success, stats = import_service.import_data(
                    source_dir=source, file_format=format or "csv", file_pattern=pattern or "*.csv"
                )

                if success:
                    logger.info(
                        f"Data import completed: {stats['files_processed']} files, "
                        f"{stats['records_processed']} records, "
                        f"{stats['trains_new']} new trains, "
                        f"{stats['trains_updated']} updated trains"
                    )
                else:
                    logger.error(f"Data import encountered errors: {stats['errors']}")
                    sys.exit(1)
            elif not clear:
                # If neither source nor clear is provided, show an error
                logger.error("Either --source or --clear must be provided")
                sys.exit(1)

        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in import_data command: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--skip-collection", is_flag=True, help="Skip data collection step")
@click.option("--skip-features", is_flag=True, help="Skip feature processing step")
@click.option("--skip-predictions", is_flag=True, help="Skip prediction generation step")
@click.option("--dry-run", is_flag=True, help="Show what would be executed without running")
@click.option("--debug", is_flag=True, help="Enable debug logging for feature processing")
@click.option(
    "--regenerate",
    is_flag=True,
    help="Clear and regenerate features/predictions for future trains (next 24h)",
)
def run_pipeline(
    skip_collection: bool,
    skip_features: bool,
    skip_predictions: bool,
    dry_run: bool,
    debug: bool,
    regenerate: bool,
) -> None:
    """Run the complete data pipeline: collection -> features -> predictions"""
    try:
        # Log regeneration mode
        if regenerate:
            logger.info("Pipeline will regenerate features and predictions for future trains")

        steps = [
            ("collect-data", not skip_collection, lambda: _execute_collect_data()),
            (
                "process-features",
                not skip_features,
                lambda: _execute_process_features(debug, regenerate),
            ),
            (
                "generate-predictions",
                not skip_predictions,
                lambda: _execute_generate_predictions(regenerate),
            ),
        ]

        successful_steps = []
        failed_step = None

        logger.info("Starting data pipeline execution")

        for step_name, should_run, execute_func in steps:
            if should_run:
                logger.info(f"Pipeline step: {step_name}")

                if dry_run:
                    logger.info(f"[DRY RUN] Would execute: {step_name}")
                    successful_steps.append(step_name)
                else:
                    try:
                        success = execute_func()
                        if success:
                            logger.info(f"Pipeline step '{step_name}' completed successfully")
                            successful_steps.append(step_name)
                        else:
                            logger.error(f"Pipeline step '{step_name}' failed")
                            failed_step = step_name
                            break
                    except Exception as e:
                        logger.error(f"Pipeline step '{step_name}' failed with exception: {str(e)}")
                        failed_step = step_name
                        break
            else:
                logger.info(f"Pipeline step: {step_name} (skipped)")

        # Report results
        if dry_run:
            logger.info(f"Pipeline dry run completed successfully")
            logger.info(f"Would execute steps: {', '.join(successful_steps)}")
        elif failed_step:
            logger.error(f"Pipeline failed at step: {failed_step}")
            logger.info(f"Successfully completed steps: {', '.join(successful_steps)}")
            sys.exit(1)
        else:
            logger.info(f"Pipeline completed successfully")
            logger.info(f"Executed steps: {', '.join(successful_steps)}")

    except Exception as e:
        logger.error(f"Error in pipeline execution: {str(e)}")
        sys.exit(1)


def _execute_collect_data() -> bool:
    """Execute data collection step with journey validation"""
    try:
        session = get_db_session()
        try:
            collector = DataCollectorService(session)
            success, stats = collector.run_collection()
            if success:
                # Log appropriate message based on whether there were any failures
                if stats.get("stations_failed", 0) > 0:
                    logger.warning(f"Data collection completed with partial success: {stats}")
                else:
                    logger.info(f"Data collection completed successfully: {stats}")

                # Process train updates for push notifications
                _process_push_notifications(session)

                # Run post-journey validation
                try:
                    from trackcast.db.repository import TrainRepository, TrainStopRepository
                    from trackcast.services.journey_validator import JourneyValidator

                    logger.info("Running post-journey validation")
                    train_repo = TrainRepository(session)
                    stop_repo = TrainStopRepository(session)
                    validator = JourneyValidator(train_repo, stop_repo)

                    validated_trains = validator.validate_completed_journeys(batch_size=10)
                    logger.info(
                        f"Journey validation completed: {len(validated_trains)} trains validated"
                    )

                except Exception as e:
                    logger.warning(f"Journey validation failed (continuing anyway): {e}")

                return True
            else:
                logger.error(f"Data collection failed: all stations failed: {stats}")
                return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in data collection: {str(e)}")
        return False


def _execute_process_features(debug: bool = False, regenerate: bool = False) -> bool:
    """Execute feature processing step"""
    try:
        # Set debug logging if requested
        if debug:
            logging.getLogger("trackcast.features").setLevel(logging.DEBUG)
            logging.getLogger("trackcast.features.extractors").setLevel(logging.DEBUG)
            logger.info("Debug logging enabled for feature extraction")

        session = get_db_session()
        try:
            feature_service = FeatureEngineeringService(session)

            if regenerate:
                # Use regeneration method for future trains only
                logger.info("Regenerating features for future trains (next 24 hours)")
                success, stats = feature_service.process_future_trains_with_regeneration()
            else:
                # Use regular incremental processing
                success, stats = feature_service.process_pending_trains()

            if success:
                logger.info(f"Feature processing completed: {stats}")
                return True
            else:
                logger.error(f"Feature processing failed: {stats}")
                return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in feature processing: {str(e)}")
        return False


def _execute_generate_predictions(regenerate: bool = False) -> bool:
    """Execute prediction generation step"""
    try:
        session = get_db_session()
        try:
            prediction_service = PredictionService(session)

            if regenerate:
                # Use regeneration method for future trains only
                logger.info("Regenerating predictions for future trains (next 24 hours)")
                success, stats = prediction_service.run_prediction_with_regeneration()
            else:
                # Use regular incremental processing
                success, stats = prediction_service.run_prediction()

            if success:
                logger.info(f"Prediction generation completed: {stats}")
                return True
            else:
                logger.error(f"Prediction generation failed: {stats}")
                return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in prediction generation: {str(e)}")
        return False


@main.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def clear_notification_tokens(confirm):
    """Clear all notification tokens from the database."""
    if not confirm:
        click.confirm(
            "⚠️  This will delete ALL device and Live Activity tokens. Continue?", abort=True
        )

    logger.info("🧹 Clearing all notification tokens...")

    with get_db_session() as session:
        try:
            from trackcast.db.models import DeviceToken, LiveActivityToken

            # Count tokens before deletion
            device_count = session.query(DeviceToken).count()
            live_activity_count = session.query(LiveActivityToken).count()

            logger.info(
                f"Found {device_count} device tokens and {live_activity_count} Live Activity tokens"
            )

            # Delete all tokens
            session.query(LiveActivityToken).delete()
            session.query(DeviceToken).delete()

            session.commit()

            logger.info("✅ Successfully cleared all notification tokens")
            click.echo(
                f"Deleted {device_count} device tokens and {live_activity_count} Live Activity tokens"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Failed to clear tokens: {e}")
            click.echo(f"Error: {e}", err=True)
            raise


@main.command()
def check_apns_config() -> None:
    """Check APNS configuration status and validate setup"""
    try:
        from trackcast.services.push_notification import APNSPushService

        logger.info("Checking APNS configuration...")

        # Initialize APNS service to check configuration
        apns_service = APNSPushService()

        # Check configuration status
        config_status = {
            "configured": not apns_service._use_mock,
            "environment": (
                "production" if apns_service.apns_url == "https://api.push.apple.com" else "sandbox"
            ),
            "auth_method": None,
            "bundle_id": apns_service.bundle_id,
            "live_activity_bundle_id": apns_service.live_activity_bundle_id,
            "issues": [],
        }

        # Determine authentication method
        if apns_service.team_id and apns_service.key_id and apns_service.auth_key_path:
            config_status["auth_method"] = "auth_key"

            # Validate auth key file
            import os

            if not os.path.exists(apns_service.auth_key_path):
                config_status["issues"].append(
                    f"Auth key file not found: {apns_service.auth_key_path}"
                )
            elif not os.access(apns_service.auth_key_path, os.R_OK):
                config_status["issues"].append(
                    f"Auth key file not readable: {apns_service.auth_key_path}"
                )

        elif apns_service.cert_path and apns_service.key_path:
            config_status["auth_method"] = "certificate"

            # Validate certificate files
            import os

            if not os.path.exists(apns_service.cert_path):
                config_status["issues"].append(
                    f"Certificate file not found: {apns_service.cert_path}"
                )
            if not os.path.exists(apns_service.key_path):
                config_status["issues"].append(
                    f"Private key file not found: {apns_service.key_path}"
                )

        else:
            config_status["issues"].append("No valid authentication method configured")

        # Test JWT generation if using auth key
        if config_status["auth_method"] == "auth_key" and not config_status["issues"]:
            try:
                apns_service._generate_jwt_token()
                logger.info("✓ JWT token generation successful")
            except Exception as e:
                config_status["issues"].append(f"JWT token generation failed: {str(e)}")

        # Print results
        logger.info(f"APNS Configuration Status:")
        logger.info(
            f"  Status: {'✓ Configured' if config_status['configured'] else '✗ Using Mock Mode'}"
        )
        logger.info(f"  Environment: {config_status['environment']}")
        logger.info(f"  Authentication: {config_status['auth_method'] or 'None'}")
        logger.info(f"  Main App Bundle ID: {config_status['bundle_id']}")
        logger.info(f"  Live Activity Bundle ID: {config_status['live_activity_bundle_id']}")

        if config_status["issues"]:
            logger.error(f"Configuration Issues:")
            for issue in config_status["issues"]:
                logger.error(f"  - {issue}")
        else:
            logger.info(f"✓ Configuration appears valid")

        # Environment variable summary
        logger.info(f"Environment Variables:")
        env_vars = [
            ("TRACKCAST_ENV", os.getenv("TRACKCAST_ENV")),
            (
                "APNS_TEAM_ID",
                (
                    os.getenv("APNS_TEAM_ID", "").replace(os.getenv("APNS_TEAM_ID", ""), "***")
                    if os.getenv("APNS_TEAM_ID")
                    else None
                ),
            ),
            ("APNS_KEY_ID", os.getenv("APNS_KEY_ID")),
            ("APNS_AUTH_KEY_PATH", os.getenv("APNS_AUTH_KEY_PATH")),
            ("APNS_CERT_PATH", os.getenv("APNS_CERT_PATH")),
            ("APNS_KEY_PATH", os.getenv("APNS_KEY_PATH")),
            ("APNS_BUNDLE_ID", os.getenv("APNS_BUNDLE_ID")),
            ("APNS_LIVE_ACTIVITY_BUNDLE_ID", os.getenv("APNS_LIVE_ACTIVITY_BUNDLE_ID")),
        ]

        for var_name, var_value in env_vars:
            if var_value:
                logger.info(f"  {var_name}: {var_value}")
            else:
                logger.debug(f"  {var_name}: (not set)")

        if not config_status["configured"]:
            logger.info(f"")
            logger.info(f"To configure APNS, see: APNS_SETUP.md")
            logger.info(f"Required for Auth Key method:")
            logger.info(f"  APNS_TEAM_ID, APNS_KEY_ID, APNS_AUTH_KEY_PATH")
            logger.info(f"Required for Certificate method:")
            logger.info(f"  APNS_CERT_PATH, APNS_KEY_PATH")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error checking APNS configuration: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be updated without making changes")
@click.option("--limit", type=int, help="Limit the number of stops to process")
def backfill_station_codes(dry_run: bool, limit: Optional[int]) -> None:
    """Backfill missing station codes based on station names"""
    try:
        from sqlalchemy import func

        from trackcast.db.models import TrainStop
        from trackcast.services.station_mapping import StationMapper

        session = get_db_session()
        station_mapper = StationMapper()

        # Count total stops without station codes
        total_missing = (
            session.query(func.count(TrainStop.id)).filter(TrainStop.station_code == None).scalar()
        )

        logger.info(f"Found {total_missing} stops without station codes")

        if total_missing == 0:
            logger.info("No stops need station code backfilling")
            return

        # Get stops without station codes
        query = (
            session.query(TrainStop)
            .filter(TrainStop.station_code == None)
            .order_by(TrainStop.scheduled_arrival.desc())
        )

        if limit:
            query = query.limit(limit)

        stops = query.all()

        # Track statistics
        processed_count = 0
        updated_count = 0
        no_match_count = 0
        unmatched_names: Set[str] = set()

        # Process each stop
        for stop in stops:
            processed_count += 1

            if stop.station_name:
                code = station_mapper.get_code_for_name(str(stop.station_name))
                if code:
                    if not dry_run:
                        try:
                            stop.station_code = code
                            # Commit individual stop to catch constraint violations
                            session.commit()
                            updated_count += 1
                            logger.debug(f"Mapped '{stop.station_name}' -> '{code}'")
                        except Exception as e:
                            session.rollback()
                            logger.warning(
                                f"Failed to update stop {stop.id} ('{stop.station_name}' -> '{code}'): {str(e)}"
                            )
                            # Check if there's already a stop with this station code
                            existing = (
                                session.query(TrainStop)
                                .filter(
                                    TrainStop.train_id == stop.train_id,
                                    TrainStop.train_departure_time == stop.train_departure_time,
                                    TrainStop.station_code == code,
                                )
                                .first()
                            )
                            if existing:
                                logger.debug(
                                    f"Duplicate stop found: train {stop.train_id} already has a stop with code '{code}'"
                                )
                    else:
                        updated_count += 1
                        logger.debug(f"Mapped '{stop.station_name}' -> '{code}'")
                else:
                    no_match_count += 1
                    unmatched_names.add(str(stop.station_name))
                    logger.debug(f"No match for station name: '{stop.station_name}'")

            # Progress update
            if processed_count % 100 == 0:
                logger.info(f"Progress: {processed_count}/{len(stops)} stops processed")

        # No final commit needed since we commit individually

        # Report results
        logger.info(f"Backfill completed:")
        logger.info(f"  - Processed: {processed_count} stops")
        logger.info(f"  - Updated: {updated_count} stops")
        logger.info(f"  - No match: {no_match_count} stops")

        if unmatched_names:
            logger.info(f"  - Unmatched station names ({len(unmatched_names)}):")
            for name in sorted(unmatched_names)[:10]:
                logger.info(f"    - '{name}'")
            if len(unmatched_names) > 10:
                logger.info(f"    ... and {len(unmatched_names) - 10} more")

        if dry_run:
            logger.info("Dry run completed - no changes were made")

    except Exception as e:
        logger.error(f"Error in backfill_station_codes command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
