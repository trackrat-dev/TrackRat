"""
Database connection management for TrackCast.
"""

import logging
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import Gauge
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from trackcast.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create Base class for all models
Base = declarative_base()

# Define Prometheus metrics
DB_CONNECTION_POOL_UTILIZATION = Gauge(
    "db_connection_pool_utilization_ratio",
    "Ratio of active DB connections to max connections",
)

# Create engine
DATABASE_URL = settings.database.url
logger.info(f"Connecting to database: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    pool_size=getattr(settings.database, "pool_size", None) or 5,
    max_overflow=getattr(settings.database, "max_overflow", None) or 10,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.debug,  # Log SQL queries in debug mode
)

# Add SQLite pragma for foreign key support if using SQLite
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create session factory
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)


def get_db() -> Iterator[Session]:
    """
    Get a database session - for use with FastAPI dependency injection.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session - for direct use.

    Returns:
        Session: SQLAlchemy database session

    Note:
        Caller is responsible for closing the session.
    """
    return SessionLocal()


@contextmanager
def db_session() -> Iterator[Session]:
    """
    Context manager for database sessions.

    Yields:
        Session: SQLAlchemy database session

    Example:
        with db_session() as session:
            session.query(Train).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SessionContext:
    """
    Context manager class for database sessions.
    Provides a clean interface for session management in a with statement.

    Example:
        with SessionContext() as session:
            session.query(Train).all()
    """

    def __enter__(self) -> Session:
        """Enter the context manager and get a new session."""
        self.session = SessionLocal()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and close the session."""
        if exc_type is not None:
            # An exception occurred, roll back
            self.session.rollback()
        else:
            # No exception, commit
            self.session.commit()

        # Always close the session
        self.session.close()


def init_db() -> None:
    """Initialize the database by creating all tables."""
    logger.info("Creating database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def get_pool_status_metrics() -> None:
    """Retrieves DB connection pool status and updates Prometheus gauge."""
    try:
        status = engine.pool.status()
        checkedout = status.get("checkedout")
        checkedin = status.get("checkedin")
        overflow = status.get("overflow")  # Connections in excess of pool_size
        pool_size = engine.pool.size()

        if checkedout is not None and checkedin is not None:
            # Total connections currently managed by the pool (excluding overflow for this calculation)
            # or consider current_pool_size = checkedin + checkedout
            # Max connections can be pool_size + max_overflow
            # Ratio of active (checkedout) to total available (pool_size)
            # A simpler metric might be just the number of checkedout connections,
            # or checkedout / (checkedin + checkedout) if that represents utilization of current pool before overflow.
            # Let's define utilization as checkedout / (pool_size + overflow capacity if different from current overflow)
            # For now, a simple ratio of checkedout connections to the configured pool_size.
            # If max_overflow is part of settings, we can use pool_size + settings.database.max_overflow

            # Effective pool size including current overflow connections
            current_total_connections = checkedin + checkedout
            # Max possible connections = configured pool_size + configured max_overflow
            max_possible_connections = pool_size + getattr(settings.database, "max_overflow", 10)

            if max_possible_connections > 0:
                utilization_ratio = checkedout / max_possible_connections
                DB_CONNECTION_POOL_UTILIZATION.set(utilization_ratio)
                logger.debug(
                    f"DB Pool Status: checkedout={checkedout}, checkedin={checkedin}, "
                    f"overflow={overflow}, pool_size={pool_size}, max_possible={max_possible_connections} "
                    f"utilization_ratio={utilization_ratio:.2f}"
                )
            else:
                DB_CONNECTION_POOL_UTILIZATION.set(
                    0
                )  # Avoid division by zero if pool is not configured
        else:
            logger.warning("Could not retrieve detailed DB pool status (checkedout/checkedin).")

    except Exception as e:
        logger.error(f"Error getting DB pool status: {str(e)}")
