"""
Database migration to remove audit trail related fields from train_stops table.

This migration:
1. Drops the audit_trail JSON column
2. Drops the data_version column
3. Drops the original_scheduled_time column  
4. Drops the api_removed_at column
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def remove_audit_trail_fields(session: Session) -> None:
    """
    Remove audit trail related fields from train_stops table.
    
    Args:
        session: SQLAlchemy database session
    """
    try:
        # Check if columns exist before dropping
        check_columns_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'train_stops' 
            AND column_name IN ('audit_trail', 'data_version', 'original_scheduled_time', 'api_removed_at')
        """)
        
        result = session.execute(check_columns_query)
        existing_columns = [row[0] for row in result]
        
        if not existing_columns:
            logger.info("No audit trail columns found to drop")
            return
            
        logger.info(f"Found columns to drop: {existing_columns}")
        
        # Drop each column that exists
        for column in existing_columns:
            drop_query = text(f"ALTER TABLE train_stops DROP COLUMN IF EXISTS {column}")
            session.execute(drop_query)
            logger.info(f"Dropped column: {column}")
        
        session.commit()
        logger.info("Successfully removed audit trail fields from train_stops table")
        
    except Exception as e:
        logger.error(f"Error removing audit trail fields: {str(e)}")
        session.rollback()
        raise


def rollback_remove_audit_trail_fields(session: Session) -> None:
    """
    Rollback migration by adding the audit trail fields back.
    Note: This will not restore the data, only the schema.
    
    Args:
        session: SQLAlchemy database session
    """
    try:
        # Add audit_trail column back
        add_audit_trail_query = text("""
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS audit_trail JSON DEFAULT '[]'::json
        """)
        session.execute(add_audit_trail_query)
        
        # Add data_version column back
        add_data_version_query = text("""
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS data_version INTEGER DEFAULT 1
        """)
        session.execute(add_data_version_query)
        
        # Add original_scheduled_time column back
        add_original_scheduled_time_query = text("""
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS original_scheduled_time TIMESTAMP
        """)
        session.execute(add_original_scheduled_time_query)
        
        # Add api_removed_at column back
        add_api_removed_at_query = text("""
            ALTER TABLE train_stops 
            ADD COLUMN IF NOT EXISTS api_removed_at TIMESTAMP
        """)
        session.execute(add_api_removed_at_query)
        
        session.commit()
        logger.info("Successfully rolled back audit trail field removal")
        
    except Exception as e:
        logger.error(f"Error rolling back audit trail field removal: {str(e)}")
        session.rollback()
        raise


if __name__ == "__main__":
    # For testing the migration
    from trackcast.db.connection import get_session
    
    with get_session() as session:
        # Run the migration
        remove_audit_trail_fields(session)
        
        # To rollback (for testing):
        # rollback_remove_audit_trail_fields(session)