"""
SQLAlchemy database models for TrackRat V2.

Follows the simplified single-journey design from V2_BACKEND_API.md.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, declarative_base, relationship

Base = declarative_base()


class TrainJourney(Base):
    """Core train journey table - one record per train per day."""

    __tablename__ = "train_journeys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_id = Column(String(10), nullable=False)
    journey_date = Column(Date, nullable=False)
    line_code = Column(String(2), nullable=False)
    line_name = Column(String(100))
    line_color = Column(String(7))
    destination = Column(String(100), nullable=False)
    origin_station_code = Column(String(2), nullable=False)
    terminal_station_code = Column(String(2), nullable=False)
    data_source = Column(String(10), nullable=False, default="NJT")

    # Discovery metadata
    first_seen_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    update_count = Column(Integer, default=1, nullable=False)

    # Journey timing
    scheduled_departure = Column(DateTime(timezone=True), nullable=False)
    scheduled_arrival = Column(DateTime(timezone=True))
    actual_departure = Column(DateTime(timezone=True))
    actual_arrival = Column(DateTime(timezone=True))

    # Data completeness
    has_complete_journey = Column(Boolean, default=False, nullable=False)
    stops_count = Column(Integer)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)

    # API error tracking
    api_error_count = Column(Integer, default=0, nullable=False)
    is_expired = Column(Boolean, default=False, nullable=False)

    # Discovery track information (temporary storage)
    discovery_track = Column(String(5))
    discovery_station_code = Column(String(2))

    # Relationships
    stops: Mapped[list["JourneyStop"]] = relationship(
        "JourneyStop", back_populates="journey", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["JourneySnapshot"]] = relationship(
        "JourneySnapshot", back_populates="journey", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "train_id", "journey_date", "data_source", name="unique_train_journey"
        ),
        Index("idx_journey_date", "journey_date"),
        Index("idx_train_id", "train_id"),
        Index("idx_last_updated", "last_updated_at"),
        Index("idx_data_source", "data_source"),
        Index("idx_active_journeys", "is_completed", "is_expired", "is_cancelled"),
    )


class JourneyStop(Base):
    """Detailed stop information for each journey."""

    __tablename__ = "journey_stops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id"), nullable=False)
    station_code = Column(String(2), nullable=False)
    station_name = Column(String(100), nullable=False)
    stop_sequence = Column(Integer, nullable=False)

    # Scheduled times (from initial schedule)
    scheduled_arrival = Column(DateTime(timezone=True))
    scheduled_departure = Column(DateTime(timezone=True))

    # Actual times (updated in real-time)
    actual_arrival = Column(DateTime(timezone=True))
    actual_departure = Column(DateTime(timezone=True))

    # Status information
    departed = Column(Boolean, default=False, nullable=False)
    status = Column(String(20))  # OnTime, Late, Cancelled, etc.
    status_details = Column(JSON)  # Additional status metadata

    # Track assignment (null until assigned)
    track = Column(String(5))
    track_assigned_at = Column(DateTime(timezone=True))

    # Stop characteristics
    pickup_only = Column(Boolean, default=False, nullable=False)
    dropoff_only = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    journey: Mapped["TrainJourney"] = relationship(
        "TrainJourney", back_populates="stops"
    )

    __table_args__ = (
        UniqueConstraint("journey_id", "station_code", name="unique_journey_stop"),
        Index("idx_station_times", "station_code", "scheduled_departure"),
        Index("idx_journey_sequence", "journey_id", "stop_sequence"),
    )


class JourneySnapshot(Base):
    """Historical snapshots for analysis and ML training."""

    __tablename__ = "journey_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id"), nullable=False)
    captured_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Complete API response stored for analysis
    raw_stop_list_data = Column(JSON, nullable=False)

    # Extracted key metrics at snapshot time
    train_status = Column(String(50))
    delay_minutes = Column(Integer)
    completed_stops = Column(Integer)
    total_stops = Column(Integer)

    # Track assignments at snapshot time {station_code: track}
    track_assignments = Column(JSON)

    # Relationships
    journey: Mapped["TrainJourney"] = relationship(
        "TrainJourney", back_populates="snapshots"
    )

    __table_args__ = (
        Index("idx_journey_time", "journey_id", "captured_at"),
        Index("idx_captured_at", "captured_at"),
    )


class DiscoveryRun(Base):
    """Train discovery tracking for monitoring and optimization."""

    __tablename__ = "discovery_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    station_code = Column(String(2), nullable=False)
    trains_discovered = Column(Integer)
    new_trains = Column(Integer)
    duration_ms = Column(Integer)
    success = Column(Boolean, default=True, nullable=False)
    error_details = Column(Text)

    __table_args__ = (Index("idx_discovery_time", "station_code", "run_at"),)


class LiveActivityToken(Base):
    """Minimal Live Activity token storage for iOS push notifications."""

    __tablename__ = "live_activity_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    push_token = Column(String, unique=True, nullable=False)  # APNS token
    activity_id = Column(String, nullable=False)  # iOS Activity ID
    train_number = Column(String(10), nullable=False)  # e.g., "A2205"
    origin_code = Column(String(2), nullable=False)  # e.g., "NY"
    destination_code = Column(String(2), nullable=False)  # e.g., "WAS"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Auto-expire after journey
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_active_tokens", "is_active", "train_number"),
        Index("idx_token_expiry", "expires_at"),
    )
