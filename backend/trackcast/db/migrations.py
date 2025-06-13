"""
Database migration utilities for TrackCast.

This module provides utilities to apply schema migrations to the database.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def add_delay_minutes_column(session: Session) -> Dict[str, Any]:
    """
    Add the delay_minutes column to the trains table if it doesn't exist.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if column already exists
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trains' AND column_name = 'delay_minutes'
        """
        )
        result = session.execute(check_query).fetchone()

        if result:
            logger.info("Column delay_minutes already exists in trains table")
            return {"status": "skipped", "message": "Column already exists"}

        # Add the column
        logger.info("Adding delay_minutes column to trains table")
        add_column_query = text(
            """
            ALTER TABLE trains 
            ADD COLUMN delay_minutes INTEGER
        """
        )
        session.execute(add_column_query)

        # Create index
        logger.info("Creating index on delay_minutes column")
        create_index_query = text(
            """
            CREATE INDEX ix_trains_delay_minutes ON trains (delay_minutes)
        """
        )
        session.execute(create_index_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully added delay_minutes column to trains table")
        return {"status": "success", "message": "Column added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding delay_minutes column: {str(e)}")
        return {"status": "error", "message": str(e)}


def create_train_stops_table(session: Session) -> Dict[str, Any]:
    """
    Create the train_stops table if it doesn't exist.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if table already exists
        check_query = text(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'train_stops'
        """
        )
        result = session.execute(check_query).fetchone()

        if result:
            logger.info("Table train_stops already exists")
            return {"status": "skipped", "message": "Table already exists"}

        # Create the table
        logger.info("Creating train_stops table")
        create_table_query = text(
            """
            CREATE TABLE train_stops (
                id SERIAL PRIMARY KEY,
                train_id VARCHAR(20) NOT NULL,
                train_departure_time TIMESTAMP NOT NULL,
                station_code VARCHAR(10) NOT NULL,
                station_name VARCHAR(100) NOT NULL,
                scheduled_time TIMESTAMP,
                departure_time TIMESTAMP,
                pickup_only BOOLEAN NOT NULL DEFAULT FALSE,
                dropoff_only BOOLEAN NOT NULL DEFAULT FALSE,
                departed BOOLEAN NOT NULL DEFAULT FALSE,
                stop_status VARCHAR(20),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """
        )
        session.execute(create_table_query)

        # Create indexes
        logger.info("Creating indexes on train_stops table")
        create_indexes_query = text(
            """
            CREATE INDEX ix_train_stops_train_id ON train_stops (train_id);
            CREATE INDEX ix_train_stops_train_departure_time ON train_stops (train_departure_time);
            CREATE INDEX ix_train_stops_station_code ON train_stops (station_code);
            CREATE UNIQUE INDEX uix_train_stop_unique ON train_stops (train_id, train_departure_time, station_code);
        """
        )
        session.execute(create_indexes_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully created train_stops table")
        return {"status": "success", "message": "Table created successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error creating train_stops table: {str(e)}")
        return {"status": "error", "message": str(e)}


def update_train_stops_schema(session: Session) -> Dict[str, Any]:
    """
    Update the train_stops table to make station_code nullable and update constraints.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if the column is already nullable
        check_nullable_query = text(
            """
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' AND column_name = 'station_code'
        """
        )
        result = session.execute(check_nullable_query).fetchone()

        if result and result[0] == "YES":
            logger.info("Column station_code is already nullable")
            return {"status": "skipped", "message": "Column already nullable"}

        logger.info("Updating train_stops schema to make station_code nullable")

        # Drop the old unique constraint
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            ALTER TABLE train_stops DROP CONSTRAINT IF EXISTS uix_train_stop_unique
        """
        )
        session.execute(drop_constraint_query)

        # Make station_code nullable
        logger.info("Making station_code column nullable")
        alter_column_query = text(
            """
            ALTER TABLE train_stops ALTER COLUMN station_code DROP NOT NULL
        """
        )
        session.execute(alter_column_query)

        # Create new unique constraint using station_name instead of station_code
        logger.info("Creating new unique constraint using station_name")
        create_constraint_query = text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uix_train_stop_unique 
            ON train_stops (train_id, train_departure_time, station_name)
        """
        )
        session.execute(create_constraint_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully updated train_stops schema")
        return {"status": "success", "message": "Schema updated successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating train_stops schema: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_stop_query_indexes(session: Session) -> Dict[str, Any]:
    """
    Add database indexes to optimize stop-based queries.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        logger.info("Adding indexes for stop-based queries")

        # Index for station_code queries
        station_code_index = text(
            """
            CREATE INDEX IF NOT EXISTS ix_train_stops_station_code_departure 
            ON train_stops (station_code, train_departure_time)
        """
        )
        session.execute(station_code_index)

        # Index for station_name queries (for partial matching)
        station_name_index = text(
            """
            CREATE INDEX IF NOT EXISTS ix_train_stops_station_name_departure 
            ON train_stops (station_name, train_departure_time)
        """
        )
        session.execute(station_name_index)

        # Composite index for efficient JOINs
        composite_index = text(
            """
            CREATE INDEX IF NOT EXISTS ix_train_stops_train_lookup 
            ON train_stops (train_id, train_departure_time, station_code)
        """
        )
        session.execute(composite_index)

        # Commit the changes
        session.commit()

        logger.info("Successfully added stop query indexes")
        return {"status": "success", "message": "Stop query indexes added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding stop query indexes: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_origin_station_columns(session: Session) -> Dict[str, Any]:
    """
    Add origin station columns to the trains table.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if columns already exist
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trains' 
            AND column_name IN ('origin_station_code', 'origin_station_name')
        """
        )
        result = session.execute(check_query).fetchall()

        if len(result) == 2:
            logger.info("Origin station columns already exist in trains table")
            return {"status": "skipped", "message": "Columns already exist"}

        # Add the columns
        logger.info("Adding origin station columns to trains table")

        # Add origin_station_code column
        add_code_query = text(
            """
            ALTER TABLE trains 
            ADD COLUMN IF NOT EXISTS origin_station_code VARCHAR(10) NOT NULL DEFAULT 'NY'
        """
        )
        session.execute(add_code_query)

        # Add origin_station_name column
        add_name_query = text(
            """
            ALTER TABLE trains 
            ADD COLUMN IF NOT EXISTS origin_station_name VARCHAR(100) NOT NULL DEFAULT 'New York Penn Station'
        """
        )
        session.execute(add_name_query)

        # Create indexes
        logger.info("Creating indexes on origin station columns")
        create_indexes_query = text(
            """
            CREATE INDEX IF NOT EXISTS ix_trains_origin_station_code ON trains (origin_station_code);
            CREATE INDEX IF NOT EXISTS ix_trains_origin_station_name ON trains (origin_station_name);
        """
        )
        session.execute(create_indexes_query)

        # Drop old unique constraint if it exists
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            ALTER TABLE trains DROP CONSTRAINT IF EXISTS uix_train_id_departure_time
        """
        )
        session.execute(drop_constraint_query)

        # Also drop the index version if it exists
        drop_index_query = text(
            """
            DROP INDEX IF EXISTS uix_train_id_departure_time
        """
        )
        session.execute(drop_index_query)

        # Create new unique constraint including origin station
        logger.info("Creating new unique constraint with origin station")
        create_constraint_query = text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uix_train_origin_departure 
            ON trains (train_id, departure_time, origin_station_code)
        """
        )
        session.execute(create_constraint_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully added origin station columns to trains table")
        return {"status": "success", "message": "Origin station columns added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding origin station columns: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_data_source_column(session: Session) -> Dict[str, Any]:
    """
    Add the data_source column to the trains table if it doesn't exist.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if column already exists
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trains' AND column_name = 'data_source'
        """
        )
        result = session.execute(check_query).fetchone()

        if result:
            logger.info("Column data_source already exists in trains table")
            return {"status": "skipped", "message": "Column already exists"}

        # Add the column
        logger.info("Adding data_source column to trains table")
        add_column_query = text(
            """
            ALTER TABLE trains 
            ADD COLUMN data_source VARCHAR(20) NOT NULL DEFAULT 'njtransit'
        """
        )
        session.execute(add_column_query)

        # Create index
        logger.info("Creating index on data_source column")
        create_index_query = text(
            """
            CREATE INDEX ix_trains_data_source ON trains (data_source)
        """
        )
        session.execute(create_index_query)

        # Drop old unique constraint if it exists
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            DROP INDEX IF EXISTS uix_train_origin_departure
        """
        )
        session.execute(drop_constraint_query)

        # Create new unique constraint including data_source
        logger.info("Creating new unique constraint with data_source")
        create_constraint_query = text(
            """
            CREATE UNIQUE INDEX uix_train_origin_departure_source 
            ON trains (train_id, departure_time, origin_station_code, data_source)
        """
        )
        session.execute(create_constraint_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully added data_source column to trains table")
        return {"status": "success", "message": "Column added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding data_source column: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_data_source_to_train_stops(session: Session) -> Dict[str, Any]:
    """
    Add the data_source column to the train_stops table and update the unique constraint.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if column already exists
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' AND column_name = 'data_source'
        """
        )
        result = session.execute(check_query).fetchone()

        if result:
            logger.info("Column data_source already exists in train_stops table")
            return {"status": "skipped", "message": "Column already exists"}

        # Add the column
        logger.info("Adding data_source column to train_stops table")
        add_column_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN data_source VARCHAR(20) NOT NULL DEFAULT 'njtransit'
        """
        )
        session.execute(add_column_query)

        # Create index
        logger.info("Creating index on data_source column")
        create_index_query = text(
            """
            CREATE INDEX ix_train_stops_data_source ON train_stops (data_source)
        """
        )
        session.execute(create_index_query)

        # Drop old unique constraint
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            ALTER TABLE train_stops DROP CONSTRAINT IF EXISTS uix_train_stop_unique
        """
        )
        session.execute(drop_constraint_query)

        # Create new unique constraint including data_source
        logger.info("Creating new unique constraint with data_source")
        create_constraint_query = text(
            """
            CREATE UNIQUE INDEX uix_train_stop_unique 
            ON train_stops (train_id, train_departure_time, station_name, data_source)
        """
        )
        session.execute(create_constraint_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully added data_source column to train_stops table")
        return {"status": "success", "message": "Column added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding data_source column to train_stops: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_train_stops_lifecycle_fields(session: Session) -> Dict[str, Any]:
    """
    Add lifecycle tracking fields to the train_stops table for non-destructive updates.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if columns already exist
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('last_seen_at', 'is_active', 'api_removed_at', 
                               'data_version', 'original_scheduled_time', 'audit_trail')
        """
        )
        result = session.execute(check_query).fetchall()

        if len(result) == 6:
            logger.info("Lifecycle tracking columns already exist in train_stops table")
            return {"status": "skipped", "message": "Columns already exist"}

        logger.info("Adding lifecycle tracking columns to train_stops table")

        # Add last_seen_at column
        add_last_seen_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        """
        )
        session.execute(add_last_seen_query)

        # Add is_active column
        add_is_active_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
        """
        )
        session.execute(add_is_active_query)

        # Add api_removed_at column
        add_api_removed_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS api_removed_at TIMESTAMP
        """
        )
        session.execute(add_api_removed_query)

        # Add data_version column
        add_data_version_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS data_version INTEGER NOT NULL DEFAULT 1
        """
        )
        session.execute(add_data_version_query)

        # Add original_scheduled_time column
        add_original_scheduled_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS original_scheduled_time TIMESTAMP
        """
        )
        session.execute(add_original_scheduled_query)

        # Add audit_trail column
        add_audit_trail_query = text(
            """
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS audit_trail JSONB NOT NULL DEFAULT '[]'::jsonb
        """
        )
        session.execute(add_audit_trail_query)

        # Create indexes
        logger.info("Creating indexes on lifecycle tracking columns")
        create_indexes_query = text(
            """
            CREATE INDEX IF NOT EXISTS ix_train_stops_last_seen_at ON train_stops (last_seen_at);
            CREATE INDEX IF NOT EXISTS ix_train_stops_is_active ON train_stops (is_active);
        """
        )
        session.execute(create_indexes_query)

        # Update existing records
        logger.info("Updating existing train_stops records with initial values")
        update_existing_query = text(
            """
            UPDATE train_stops 
            SET last_seen_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP),
                original_scheduled_time = scheduled_time,
                audit_trail = jsonb_build_array(
                    jsonb_build_object(
                        'timestamp', COALESCE(created_at, CURRENT_TIMESTAMP)::text,
                        'action', 'migrated',
                        'note', 'Existing stop migrated to new schema'
                    )
                )
            WHERE audit_trail = '[]'::jsonb
        """
        )
        session.execute(update_existing_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully added lifecycle tracking columns to train_stops table")
        return {"status": "success", "message": "Lifecycle tracking columns added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding lifecycle tracking columns: {str(e)}")
        return {"status": "error", "message": str(e)}


def update_train_stop_unique_constraint(session: Session) -> Dict[str, Any]:
    """
    Update the unique constraint on train_stops to include scheduled_time,
    allowing multiple stops at the same station if they occur at different times.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if the new constraint already exists
        check_constraint_query = text(
            """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'train_stops' 
            AND indexname = 'uix_train_stop_unique_with_time'
        """
        )
        result = session.execute(check_constraint_query).fetchone()

        if result:
            logger.info("Updated unique constraint already exists")
            return {"status": "skipped", "message": "Updated constraint already exists"}

        logger.info("Updating train_stops unique constraint to include scheduled_time")

        # Drop the old unique constraint
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            DROP INDEX IF EXISTS uix_train_stop_unique
        """
        )
        session.execute(drop_constraint_query)

        # Create new unique constraint including scheduled_time
        logger.info("Creating new unique constraint with scheduled_time")
        create_constraint_query = text(
            """
            CREATE UNIQUE INDEX uix_train_stop_unique_with_time 
            ON train_stops (train_id, train_departure_time, station_name, data_source, scheduled_time)
        """
        )
        session.execute(create_constraint_query)

        # Commit the changes
        session.commit()

        logger.info("Successfully updated train_stops unique constraint")
        return {"status": "success", "message": "Unique constraint updated successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating unique constraint: {str(e)}")
        return {"status": "error", "message": str(e)}


def run_migrations(session: Session) -> List[Dict[str, Any]]:
    """
    Run all pending migrations.

    Args:
        session: SQLAlchemy database session

    Returns:
        List of dictionaries with migration results
    """
    results = []

    # Add migrations in order
    migrations = [
        ("add_delay_minutes", add_delay_minutes_column),
        ("create_train_stops_table", create_train_stops_table),
        ("update_train_stops_schema", update_train_stops_schema),
        ("add_stop_query_indexes", add_stop_query_indexes),
        ("add_origin_station_columns", add_origin_station_columns),
        ("add_data_source_column", add_data_source_column),
        ("add_data_source_to_train_stops", add_data_source_to_train_stops),
        ("add_train_stops_lifecycle_fields", add_train_stops_lifecycle_fields),
        ("update_train_stop_unique_constraint", update_train_stop_unique_constraint),
    ]

    for name, migration_func in migrations:
        logger.info(f"Running migration: {name}")
        try:
            result = migration_func(session)
            results.append(
                {"name": name, "status": result.get("status"), "message": result.get("message")}
            )
        except Exception as e:
            results.append({"name": name, "status": "error", "message": str(e)})
            logger.error(f"Error in migration {name}: {str(e)}")

    return results
