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
                station_code VARCHAR(10),
                station_name VARCHAR(100) NOT NULL,
                scheduled_arrival TIMESTAMP,
                scheduled_departure TIMESTAMP,
                actual_arrival TIMESTAMP,
                actual_departure TIMESTAMP,
                pickup_only BOOLEAN NOT NULL DEFAULT FALSE,
                dropoff_only BOOLEAN NOT NULL DEFAULT FALSE,
                departed BOOLEAN NOT NULL DEFAULT FALSE,
                stop_status VARCHAR(20),
                data_source VARCHAR(20) NOT NULL DEFAULT 'njtransit',
                last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
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
            CREATE INDEX ix_train_stops_data_source ON train_stops (data_source);
            CREATE INDEX ix_train_stops_last_seen_at ON train_stops (last_seen_at);
            CREATE INDEX ix_train_stops_is_active ON train_stops (is_active);
            CREATE UNIQUE INDEX uix_train_stop_unique_without_time ON train_stops (train_id, train_departure_time, station_name, data_source);
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
        # Check if essential lifecycle columns already exist
        check_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('last_seen_at', 'is_active')
        """
        )
        result = session.execute(check_query).fetchall()

        if len(result) == 2:
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

        # Update existing records - check if scheduled_time column exists first
        logger.info("Updating existing train_stops records with initial values")

        # Check if scheduled_time column exists
        check_scheduled_time_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' AND column_name = 'scheduled_time'
            """
        )
        scheduled_time_exists = session.execute(check_scheduled_time_query).fetchone()

        if scheduled_time_exists:
            # Update with scheduled_time if it exists
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
        else:
            # Update without scheduled_time if it doesn't exist
            update_existing_query = text(
                """
                UPDATE train_stops 
                SET last_seen_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP),
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
    Falls back to a simpler constraint if scheduled_time column doesn't exist.

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
            AND indexname IN ('uix_train_stop_unique_with_time', 'uix_train_stop_unique_without_time')
        """
        )
        result = session.execute(check_constraint_query).fetchone()

        if result:
            logger.info("Updated unique constraint already exists")
            return {"status": "skipped", "message": "Updated constraint already exists"}

        logger.info("Updating train_stops unique constraint")

        # Drop the old unique constraint
        logger.info("Dropping old unique constraint")
        drop_constraint_query = text(
            """
            DROP INDEX IF EXISTS uix_train_stop_unique
        """
        )
        session.execute(drop_constraint_query)

        # Check if scheduled_time column exists
        check_scheduled_time_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' AND column_name = 'scheduled_time'
            """
        )
        scheduled_time_exists = session.execute(check_scheduled_time_query).fetchone()

        if scheduled_time_exists:
            # Create new unique constraint including scheduled_time
            logger.info("Creating new unique constraint with scheduled_time")
            create_constraint_query = text(
                """
                CREATE UNIQUE INDEX uix_train_stop_unique_with_time 
                ON train_stops (train_id, train_departure_time, station_name, data_source, scheduled_time)
                """
            )
        else:
            # Create simpler constraint without scheduled_time
            logger.info("Creating new unique constraint without scheduled_time")
            create_constraint_query = text(
                """
                CREATE UNIQUE INDEX uix_train_stop_unique_without_time 
                ON train_stops (train_id, train_departure_time, station_name, data_source)
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


def remove_audit_trail_fields(session: Session) -> Dict[str, Any]:
    """
    Remove audit trail related fields from train_stops table.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if columns exist before dropping
        check_columns_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('audit_trail', 'data_version', 'original_scheduled_time', 'api_removed_at')
        """
        )

        result = session.execute(check_columns_query)
        existing_columns = [row[0] for row in result]

        if not existing_columns:
            logger.info("No audit trail columns found to drop")
            return {"status": "skipped", "message": "No audit trail columns to drop"}

        logger.info(f"Found columns to drop: {existing_columns}")

        # Drop each column that exists
        for column in existing_columns:
            drop_query = text(f"ALTER TABLE train_stops DROP COLUMN IF EXISTS {column}")
            session.execute(drop_query)
            logger.info(f"Dropped column: {column}")

        session.commit()
        logger.info("Successfully removed audit trail fields from train_stops table")
        return {"status": "success", "message": f"Dropped columns: {', '.join(existing_columns)}"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error removing audit trail fields: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_performance_indexes(session: Session) -> Dict[str, Any]:
    """
    Add performance indexes for train stops table to improve query performance.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        from trackcast.db.add_performance_indexes import upgrade

        logger.info("Adding performance indexes for better query performance")
        upgrade(session)

        logger.info("Successfully added performance indexes")
        return {"status": "success", "message": "Performance indexes added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding performance indexes: {str(e)}")
        return {"status": "error", "message": str(e)}


def add_arrival_time_tracking(session: Session) -> Dict[str, Any]:
    """
    Add arrival time tracking fields for journey validation.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        logger.info("Adding arrival time tracking fields")

        # Check if actual_arrival_time already exists in train_stops
        check_arrival_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' AND column_name = 'actual_arrival_time'
            """
        )
        result = session.execute(check_arrival_query).fetchone()

        if not result:
            # Add actual arrival time to train stops
            logger.info("Adding actual_arrival_time column to train_stops table")
            add_arrival_query = text(
                """
                ALTER TABLE train_stops 
                ADD COLUMN actual_arrival_time TIMESTAMP
                """
            )
            session.execute(add_arrival_query)

        # Check if journey tracking columns exist in trains
        check_journey_query = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trains' 
            AND column_name IN ('journey_completion_status', 'journey_validated_at', 
                               'next_validation_check', 'stops_last_updated')
            """
        )
        existing_columns = session.execute(check_journey_query).fetchall()
        existing_column_names = [row[0] for row in existing_columns]

        if len(existing_column_names) < 4:
            # Add missing journey tracking fields to trains
            if "journey_completion_status" not in existing_column_names:
                logger.info("Adding journey_completion_status column to trains table")
                add_status_query = text(
                    """
                    ALTER TABLE trains 
                    ADD COLUMN journey_completion_status VARCHAR(20)
                    """
                )
                session.execute(add_status_query)

            if "journey_validated_at" not in existing_column_names:
                logger.info("Adding journey_validated_at column to trains table")
                add_validated_query = text(
                    """
                    ALTER TABLE trains 
                    ADD COLUMN journey_validated_at TIMESTAMP
                    """
                )
                session.execute(add_validated_query)

            if "next_validation_check" not in existing_column_names:
                logger.info("Adding next_validation_check column to trains table")
                add_next_check_query = text(
                    """
                    ALTER TABLE trains 
                    ADD COLUMN next_validation_check TIMESTAMP
                    """
                )
                session.execute(add_next_check_query)

            if "stops_last_updated" not in existing_column_names:
                logger.info("Adding stops_last_updated column to trains table")
                add_stops_updated_query = text(
                    """
                    ALTER TABLE trains 
                    ADD COLUMN stops_last_updated TIMESTAMP
                    """
                )
                session.execute(add_stops_updated_query)

        # Check if indexes exist
        check_validation_index = text(
            """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'trains' 
            AND indexname = 'idx_trains_journey_validation'
            """
        )
        validation_index_exists = session.execute(check_validation_index).fetchone()

        if not validation_index_exists:
            # Create journey validation index
            logger.info("Creating journey validation index")
            create_validation_index = text(
                """
                CREATE INDEX idx_trains_journey_validation 
                ON trains(data_source, journey_completion_status, next_validation_check)
                WHERE data_source = 'njtransit'
                """
            )
            session.execute(create_validation_index)

        check_freshness_index = text(
            """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'trains' 
            AND indexname = 'idx_trains_stop_freshness'
            """
        )
        freshness_index_exists = session.execute(check_freshness_index).fetchone()

        if not freshness_index_exists:
            # Create stop freshness index
            logger.info("Creating stop freshness index")
            create_freshness_index = text(
                """
                CREATE INDEX idx_trains_stop_freshness 
                ON trains(data_source, status, stops_last_updated)
                WHERE data_source = 'njtransit' AND status IN ('BOARDING', 'DEPARTED')
                """
            )
            session.execute(create_freshness_index)

        # Commit the changes
        session.commit()

        logger.info("Successfully added arrival time tracking fields")
        return {"status": "success", "message": "Arrival time tracking fields added successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error adding arrival time tracking fields: {str(e)}")
        return {"status": "error", "message": str(e)}


def simplify_train_stop_constraint(session: Session) -> Dict[str, Any]:
    """
    Simplify the train_stops unique constraint by removing scheduled_time.
    This is the final state we want - allowing duplicate stops at same station
    only if they have different train_id, departure_time, or data_source.

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check which constraint currently exists
        check_with_time = text(
            """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'train_stops' 
            AND indexname = 'uix_train_stop_unique_with_time'
            """
        )
        with_time_exists = session.execute(check_with_time).fetchone()

        check_without_time = text(
            """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'train_stops' 
            AND indexname = 'uix_train_stop_unique_without_time'
            """
        )
        without_time_exists = session.execute(check_without_time).fetchone()

        if without_time_exists and not with_time_exists:
            logger.info("Simplified constraint already exists")
            return {"status": "skipped", "message": "Simplified constraint already in place"}

        # Drop any existing constraints
        if with_time_exists:
            logger.info("Dropping constraint with scheduled_time")
            drop_with_time = text(
                """
                DROP INDEX IF EXISTS uix_train_stop_unique_with_time
                """
            )
            session.execute(drop_with_time)

        # Also drop the old unnamed constraint if it exists
        drop_old_constraint = text(
            """
            DROP INDEX IF EXISTS uix_train_stop_unique
            """
        )
        session.execute(drop_old_constraint)

        # Create the simplified constraint if it doesn't exist
        if not without_time_exists:
            logger.info("Creating simplified unique constraint without scheduled_time")
            create_constraint = text(
                """
                CREATE UNIQUE INDEX uix_train_stop_unique_without_time 
                ON train_stops (train_id, train_departure_time, station_name, data_source)
                """
            )
            session.execute(create_constraint)

        # Commit the changes
        session.commit()

        logger.info("Successfully simplified train_stops unique constraint")
        return {"status": "success", "message": "Constraint simplified successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error simplifying train_stop constraint: {str(e)}")
        return {"status": "error", "message": str(e)}


def rename_train_stop_time_fields(session: Session) -> Dict[str, Any]:
    """
    Rename train stop time fields for clarity and add actual_departure field.

    This migration:
    1. Renames scheduled_time to scheduled_arrival
    2. Renames departure_time to scheduled_departure
    3. Renames actual_arrival_time to actual_arrival
    4. Adds actual_departure field

    Args:
        session: SQLAlchemy database session

    Returns:
        Dictionary with migration results
    """
    try:
        # Check if new columns already exist
        check_new_columns = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('scheduled_arrival', 'scheduled_departure', 
                               'actual_arrival', 'actual_departure')
            """
        )
        existing_new_columns = session.execute(check_new_columns).fetchall()
        existing_new_names = [row[0] for row in existing_new_columns]

        if len(existing_new_names) == 4:
            logger.info("Train stop time fields already renamed")
            return {"status": "skipped", "message": "Fields already renamed"}

        # Check if old columns exist
        check_old_columns = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('scheduled_time', 'departure_time', 'actual_arrival_time')
            """
        )
        existing_old_columns = session.execute(check_old_columns).fetchall()
        existing_old_names = [row[0] for row in existing_old_columns]

        if not existing_old_names:
            logger.warning("Old columns not found - may need manual intervention")
            return {"status": "warning", "message": "Old columns not found"}

        # Rename columns
        if "scheduled_time" in existing_old_names and "scheduled_arrival" not in existing_new_names:
            logger.info("Renaming scheduled_time to scheduled_arrival")
            rename_scheduled_time = text(
                """
                ALTER TABLE train_stops 
                RENAME COLUMN scheduled_time TO scheduled_arrival
                """
            )
            session.execute(rename_scheduled_time)

        if (
            "departure_time" in existing_old_names
            and "scheduled_departure" not in existing_new_names
        ):
            logger.info("Renaming departure_time to scheduled_departure")
            rename_departure_time = text(
                """
                ALTER TABLE train_stops 
                RENAME COLUMN departure_time TO scheduled_departure
                """
            )
            session.execute(rename_departure_time)

        if (
            "actual_arrival_time" in existing_old_names
            and "actual_arrival" not in existing_new_names
        ):
            logger.info("Renaming actual_arrival_time to actual_arrival")
            rename_actual_arrival = text(
                """
                ALTER TABLE train_stops 
                RENAME COLUMN actual_arrival_time TO actual_arrival
                """
            )
            session.execute(rename_actual_arrival)

        # Add actual_departure if it doesn't exist
        if "actual_departure" not in existing_new_names:
            logger.info("Adding actual_departure column to train_stops table")
            add_actual_departure = text(
                """
                ALTER TABLE train_stops 
                ADD COLUMN actual_departure TIMESTAMP
                """
            )
            session.execute(add_actual_departure)

        # Create indexes on new time columns for performance
        index_names = [
            ("idx_train_stops_scheduled_arrival", "scheduled_arrival"),
            ("idx_train_stops_actual_arrival", "actual_arrival"),
        ]

        for index_name, column_name in index_names:
            check_index = text(
                f"""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'train_stops' 
                AND indexname = '{index_name}'
                """
            )
            index_exists = session.execute(check_index).fetchone()

            if not index_exists:
                logger.info(f"Creating index {index_name}")
                create_index = text(
                    f"""
                    CREATE INDEX {index_name} 
                    ON train_stops({column_name})
                    """
                )
                session.execute(create_index)

        # Commit the changes
        session.commit()

        logger.info("Successfully renamed train stop time fields")
        return {"status": "success", "message": "Time fields renamed successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Error renaming train stop time fields: {str(e)}")
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
        ("remove_audit_trail_fields", remove_audit_trail_fields),
        ("add_arrival_time_tracking", add_arrival_time_tracking),  # Arrival time tracking
        (
            "simplify_train_stop_constraint",
            simplify_train_stop_constraint,
        ),  # Final constraint state
        (
            "rename_train_stop_time_fields",
            rename_train_stop_time_fields,
        ),  # Rename time fields for clarity
        ("add_performance_indexes", add_performance_indexes),  # Performance improvements (last)
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
