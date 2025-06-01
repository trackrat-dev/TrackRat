"""
Command-line interface for TrackCast.
"""

import logging
import os
import sys
import time

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
from trackcast.services.scheduler import SchedulerService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("trackcast.log")],
)

logger = logging.getLogger(__name__)


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
    """Initialize the database schema"""
    try:
        # Get database URL from settings
        db_url = settings.database.url
        logger.info(f"Initializing database at {db_url}")

        # Create engine and tables
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        sys.exit(1)


@main.command()
def collect_data() -> None:
    """Run a one-time data collection from NJ Transit API"""
    try:
        session = get_db_session()
        collector = DataCollectorService(session)

        success, stats = collector.run_collection()
        if success:
            logger.info(f"Data collection completed: {stats}")
        else:
            logger.error(f"Data collection failed: {stats}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in collect_data command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


@main.command()
@click.option("--clear", is_flag=True, help="Clear features instead of processing them")
@click.option("--train-id", type=str, help="Clear features for a specific train ID (used with --clear)")
@click.option("--time-range", nargs=2, type=click.DateTime(), help="Clear features for a time range (used with --clear)")
@click.option("--debug", is_flag=True, help="Enable debug logging for detailed track usage information")
def process_features(clear: bool, train_id: str, time_range: tuple, debug: bool) -> None:
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
                train_id=train_id, 
                start_time=start_time, 
                end_time=end_time
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
@click.option("--train-id", type=str, help="Clear predictions for a specific train ID (not implemented yet)")
@click.option("--time-range", nargs=2, type=click.DateTime(), help="Clear predictions for a time range (not implemented yet)")
def generate_predictions(clear: bool, train_id: str, time_range: tuple) -> None:
    """Generate track predictions for upcoming trains"""
    try:
        session = get_db_session()
        prediction_service = PredictionService(session)

        if clear:
            # Handle clearing predictions
            if train_id or time_range:
                logger.error("Train ID and time range filtering for prediction clearing is not implemented yet")
                sys.exit(1)

            logger.info("Clearing predictions as requested")
            success, stats = prediction_service.clear_all_predictions()

            if success:
                logger.info(f"Prediction clearing completed: {stats}")
            else:
                logger.error(f"Prediction clearing failed: {stats}")
                sys.exit(1)
        else:
            # Normal prediction generation
            success, stats = prediction_service.run_prediction()
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


@main.command()
def start_scheduler() -> None:
    """Start the scheduler for automatic periodic execution"""
    try:
        logger.info("Starting scheduler")
        scheduler = SchedulerService()
        scheduler.start()

        # Keep the main thread alive while scheduler runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down scheduler")
            scheduler.stop()
    except Exception as e:
        logger.error(f"Error in scheduler: {str(e)}")
        sys.exit(1)


@main.command()
def update_schema() -> None:
    """Update the database schema with migrations"""
    try:
        logger.info("Running database schema migrations")
        session = get_db_session()

        try:
            results = run_migrations(session)

            # Log results
            for result in results:
                if result["status"] == "success":
                    logger.info(f"Migration {result['name']} completed: {result['message']}")
                elif result["status"] == "skipped":
                    logger.info(f"Migration {result['name']} skipped: {result['message']}")
                else:
                    logger.error(f"Migration {result['name']} failed: {result['message']}")
                    sys.exit(1)

            logger.info("Database schema update completed successfully")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error updating database schema: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--station", "-s", type=str, help="Train model for specific station code (e.g., 'NY', 'TR')")
@click.option("--all-stations", is_flag=True, help="Train models for all stations")
def train_model(station: str, all_stations: bool) -> None:
    """Train prediction models using historical data"""
    try:
        from trackcast.models.training import train_new_model, train_model_for_station, train_models_for_all_stations

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
def import_data(source: str, format: str, pattern: str, clear: bool) -> None:
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
                    source_dir=source,
                    file_format=format,
                    file_pattern=pattern
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
@click.option("--dry-run", is_flag=True, help="Show what would be updated without making changes")
@click.option("--limit", type=int, help="Limit the number of stops to process")
def backfill_station_codes(dry_run: bool, limit: int) -> None:
    """Backfill missing station codes based on station names"""
    try:
        from trackcast.services.station_mapping import StationMapper
        from trackcast.db.models import TrainStop
        from sqlalchemy import func
        
        session = get_db_session()
        station_mapper = StationMapper()
        
        # Count total stops without station codes
        total_missing = session.query(func.count(TrainStop.id)).filter(
            TrainStop.station_code == None
        ).scalar()
        
        logger.info(f"Found {total_missing} stops without station codes")
        
        if total_missing == 0:
            logger.info("No stops need station code backfilling")
            return
        
        # Get stops without station codes
        query = session.query(TrainStop).filter(
            TrainStop.station_code == None
        ).order_by(TrainStop.scheduled_time.desc())
        
        if limit:
            query = query.limit(limit)
        
        stops = query.all()
        
        # Track statistics
        stats = {
            "processed": 0,
            "updated": 0,
            "no_match": 0,
            "unmatched_names": set()
        }
        
        # Process each stop
        for stop in stops:
            stats["processed"] += 1
            
            if stop.station_name:
                code = station_mapper.get_code_for_name(stop.station_name)
                if code:
                    if not dry_run:
                        try:
                            stop.station_code = code
                            # Commit individual stop to catch constraint violations
                            session.commit()
                            stats["updated"] += 1
                            logger.debug(f"Mapped '{stop.station_name}' -> '{code}'")
                        except Exception as e:
                            session.rollback()
                            logger.warning(f"Failed to update stop {stop.id} ('{stop.station_name}' -> '{code}'): {str(e)}")
                            # Check if there's already a stop with this station code
                            existing = session.query(TrainStop).filter(
                                TrainStop.train_id == stop.train_id,
                                TrainStop.train_departure_time == stop.train_departure_time,
                                TrainStop.station_code == code
                            ).first()
                            if existing:
                                logger.debug(f"Duplicate stop found: train {stop.train_id} already has a stop with code '{code}'")
                    else:
                        stats["updated"] += 1
                        logger.debug(f"Mapped '{stop.station_name}' -> '{code}'")
                else:
                    stats["no_match"] += 1
                    stats["unmatched_names"].add(stop.station_name)
                    logger.debug(f"No match for station name: '{stop.station_name}'")
            
            # Progress update
            if stats["processed"] % 100 == 0:
                logger.info(f"Progress: {stats['processed']}/{len(stops)} stops processed")
        
        # No final commit needed since we commit individually
        
        # Report results
        logger.info(f"Backfill completed:")
        logger.info(f"  - Processed: {stats['processed']} stops")
        logger.info(f"  - Updated: {stats['updated']} stops")
        logger.info(f"  - No match: {stats['no_match']} stops")
        
        if stats["unmatched_names"]:
            logger.info(f"  - Unmatched station names ({len(stats['unmatched_names'])}):")
            for name in sorted(stats["unmatched_names"])[:10]:
                logger.info(f"    - '{name}'")
            if len(stats["unmatched_names"]) > 10:
                logger.info(f"    ... and {len(stats['unmatched_names']) - 10} more")
        
        if dry_run:
            logger.info("Dry run completed - no changes were made")
        
    except Exception as e:
        logger.error(f"Error in backfill_station_codes command: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()