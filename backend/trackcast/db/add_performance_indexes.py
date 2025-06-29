"""
Add performance indexes for train stops table.

This migration adds several indexes to improve query performance,
especially for the N+1 query problem when loading train stops.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def upgrade(session: Session):
    """Add performance indexes."""
    logger.info("Adding performance indexes for train stops...")

    # Check if scheduled_time column exists
    check_scheduled_time_query = text(
        """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'train_stops' AND column_name = 'scheduled_time'
        """
    )
    try:
        scheduled_time_result = session.execute(check_scheduled_time_query)
        scheduled_time_exists = scheduled_time_result.fetchone() if scheduled_time_result else None
    except (AttributeError, Exception):
        # Handle test environment where mock doesn't have fetchone
        scheduled_time_exists = None

    # Check if scheduled_arrival column exists (new column name)
    check_scheduled_arrival_query = text(
        """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'train_stops' AND column_name = 'scheduled_arrival'
        """
    )
    try:
        scheduled_arrival_result = session.execute(check_scheduled_arrival_query)
        scheduled_arrival_exists = (
            scheduled_arrival_result.fetchone() if scheduled_arrival_result else None
        )
    except (AttributeError, Exception):
        # Handle test environment where mock doesn't have fetchone
        scheduled_arrival_exists = None

    if scheduled_time_exists:
        # Indexes with old scheduled_time column
        indexes = [
            # Index for efficient stop lookups by train
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_train_lookup 
            ON train_stops(train_id, train_departure_time, scheduled_time)
            """,
            # Index for station code lookups (used in from/to station filtering)
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_scheduled 
            ON train_stops(station_code, scheduled_time) 
            WHERE station_code IS NOT NULL
            """,
            # Composite index for the complex from/to station queries
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_departed_scheduled
            ON train_stops(station_code, departed, scheduled_time)
            WHERE station_code IS NOT NULL
            """,
        ]
    elif scheduled_arrival_exists:
        # Indexes with new scheduled_arrival column
        indexes = [
            # Index for efficient stop lookups by train
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_train_lookup 
            ON train_stops(train_id, train_departure_time, scheduled_arrival)
            """,
            # Index for station code lookups (used in from/to station filtering)
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_scheduled 
            ON train_stops(station_code, scheduled_arrival) 
            WHERE station_code IS NOT NULL
            """,
            # Composite index for the complex from/to station queries
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_departed_scheduled
            ON train_stops(station_code, departed, scheduled_arrival)
            WHERE station_code IS NOT NULL
            """,
        ]
    else:
        # Alternative indexes without any scheduled time column
        indexes = [
            # Index for efficient stop lookups by train (without scheduled time)
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_train_lookup 
            ON train_stops(train_id, train_departure_time, station_code)
            """,
            # Index for station code lookups (used in from/to station filtering)
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_code 
            ON train_stops(station_code) 
            WHERE station_code IS NOT NULL
            """,
            # Composite index for the complex from/to station queries
            """
            CREATE INDEX IF NOT EXISTS idx_train_stops_station_departed
            ON train_stops(station_code, departed)
            WHERE station_code IS NOT NULL
            """,
        ]

    # Common indexes that don't depend on scheduled_time
    common_indexes = [
        # Index for departed status filtering (used in stops_at_station queries)
        """
        CREATE INDEX IF NOT EXISTS idx_train_stops_departed 
        ON train_stops(departed)
        """,
        # Index for data source filtering in stops
        """
        CREATE INDEX IF NOT EXISTS idx_train_stops_data_source
        ON train_stops(data_source)
        """,
        # Additional index for train table to speed up consolidation queries
        """
        CREATE INDEX IF NOT EXISTS idx_trains_id_train_id_departure
        ON trains(id, train_id, departure_time)
        """,
    ]

    # Combine all indexes
    all_indexes = indexes + common_indexes

    for index_sql in all_indexes:
        try:
            session.execute(text(index_sql))
            logger.info(f"Successfully created index: {index_sql.strip()[:50]}...")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise

    # Skip ANALYZE during migrations to prevent blocking issues
    # PostgreSQL's autovacuum daemon will update statistics automatically
    # without causing locks that can block concurrent operations
    logger.info("Skipping ANALYZE - statistics will be updated by autovacuum")

    session.commit()
    logger.info("Performance indexes migration completed successfully")


def downgrade(session: Session):
    """Remove performance indexes."""
    logger.info("Removing performance indexes...")

    index_names = [
        "idx_train_stops_train_lookup",
        "idx_train_stops_station_scheduled",
        "idx_train_stops_departed",
        "idx_train_stops_station_departed_scheduled",
        "idx_train_stops_data_source",
        "idx_trains_id_train_id_departure",
    ]

    for index_name in index_names:
        try:
            session.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            logger.info(f"Successfully dropped index: {index_name}")
        except Exception as e:
            logger.error(f"Failed to drop index {index_name}: {e}")
            raise

    session.commit()
    logger.info("Performance indexes rollback completed")


if __name__ == "__main__":
    # This allows running the migration standalone
    from trackcast.db.connection import get_db

    db = next(get_db())
    try:
        upgrade(db)
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()
