"""
SQLAlchemy database models for TrackRat V2.

Follows the simplified single-journey design documented in backend_v2/CLAUDE.md.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
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
    train_id = Column(String(30), nullable=False)  # PATH train IDs are ~21 chars
    journey_date = Column(Date, nullable=False)
    line_code = Column(String(10), nullable=False)  # PATH line codes are ~6 chars
    line_name = Column(String(100))
    line_color = Column(String(7))
    destination = Column(String(100), nullable=False)
    origin_station_code = Column(String(10), nullable=False)
    terminal_station_code = Column(String(10), nullable=False)
    data_source = Column(String(10), nullable=False, default="NJT")
    observation_type = Column(String(10), nullable=False, default="OBSERVED")

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
    cancellation_reason = Column(String(255), nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)

    # API error tracking
    api_error_count = Column(Integer, default=0, nullable=False)
    is_expired = Column(Boolean, default=False, nullable=False)

    # Discovery track information (temporary storage)
    discovery_track = Column(String(5))
    discovery_station_code = Column(String(10))

    # Relationships — use lazy="raise_on_sql" to prevent accidental lazy loads
    # in async context, which cause greenlet_spawn errors (sqlalche.me/e/20/xd2s).
    # All access must use explicit eager loading (selectinload) or direct queries.
    stops: Mapped[list["JourneyStop"]] = relationship(
        "JourneyStop",
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    snapshots: Mapped[list["JourneySnapshot"]] = relationship(
        "JourneySnapshot",
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    progress: Mapped["JourneyProgress"] = relationship(
        "JourneyProgress",
        back_populates="journey",
        uselist=False,
        primaryjoin="and_(TrainJourney.id==JourneyProgress.journey_id)",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    segment_times: Mapped[list["SegmentTransitTime"]] = relationship(
        "SegmentTransitTime",
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    dwell_times: Mapped[list["StationDwellTime"]] = relationship(
        "StationDwellTime",
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    progress_snapshots: Mapped[list["JourneyProgress"]] = relationship(
        "JourneyProgress",
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="progress",
        lazy="raise_on_sql",
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
        # Composite index for delay forecaster 365-day lookback queries
        Index(
            "idx_delay_forecaster",
            "train_id",
            "origin_station_code",
            "data_source",
            "journey_date",
        ),
    )


class JourneyStop(Base):
    """Detailed stop information for each journey."""

    __tablename__ = "journey_stops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False)
    station_code = Column(String(10), nullable=False)
    station_name = Column(String(100), nullable=False)
    stop_sequence = Column(
        Integer, nullable=True
    )  # Allow NULL until journey collector sets it

    # Scheduled times (from initial schedule)
    scheduled_arrival = Column(DateTime(timezone=True))
    scheduled_departure = Column(DateTime(timezone=True))

    # Updated times (current best estimate)
    updated_arrival = Column(DateTime(timezone=True))
    updated_departure = Column(DateTime(timezone=True))

    # Actual times (recorded when events occur)
    actual_arrival = Column(DateTime(timezone=True))
    actual_departure = Column(DateTime(timezone=True))

    # Raw status information from data source
    raw_amtrak_status = Column(String(50))  # Amtrak status values
    raw_njt_departed_flag = Column(String(10))  # NJT DEPARTED flag
    has_departed_station = Column(Boolean, default=False, nullable=False)

    # How we determined departure (api_explicit, sequential_inference, time_inference)
    departure_source = Column(String(30))

    # How we determined actual_arrival (api_observed, scheduled_fallback)
    arrival_source = Column(String(30))

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
        "TrainJourney", back_populates="stops", lazy="raise_on_sql"
    )

    __table_args__ = (
        UniqueConstraint("journey_id", "station_code", name="unique_journey_stop"),
        Index("idx_station_times", "station_code", "scheduled_departure"),
        Index("idx_journey_sequence", "journey_id", "stop_sequence"),
        # Performance optimization: composite index for track occupancy queries
        # Used by track_occupancy.py to find occupied tracks at a station
        Index(
            "idx_track_occupancy_lookup",
            "station_code",
            "has_departed_station",
            "scheduled_departure",
        ),
        # Performance optimization: composite index for track distribution queries
        # Used by historical_track_predictor.py for GROUP BY aggregations
        Index("idx_stop_track_distribution", "station_code", "track"),
        # Performance optimization: composite index for stop-level delay forecaster joins
        # Used by delay_forecaster.py to join journey_stops to train_journeys
        Index("idx_stop_delay_forecaster", "station_code", "journey_id"),
        # Performance optimization: composite index for route history EXISTS subquery
        # Used by routes.py to check station pair ordering on journeys
        Index(
            "idx_stop_journey_station_seq",
            "journey_id",
            "station_code",
            "stop_sequence",
        ),
    )


class JourneySnapshot(Base):
    """Historical snapshots for analysis and ML training."""

    __tablename__ = "journey_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False)
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
        "TrainJourney", back_populates="snapshots", lazy="raise_on_sql"
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
    station_code = Column(String(10), nullable=False)
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
    train_number = Column(String(30), nullable=False)  # PATH IDs are ~21 chars
    origin_code = Column(String(10), nullable=False)  # e.g., "NY"
    destination_code = Column(String(10), nullable=False)  # e.g., "WAS"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Auto-expire after journey
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_active_tokens", "is_active", "train_number"),
        Index("idx_token_expiry", "expires_at"),
    )


class DeviceToken(Base):
    """Device registration for push notification alerts."""

    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), unique=True, nullable=False)
    apns_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    subscriptions: Mapped[list["RouteAlertSubscription"]] = relationship(
        "RouteAlertSubscription",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="RouteAlertSubscription.device_id",
        primaryjoin="DeviceToken.device_id == RouteAlertSubscription.device_id",
        lazy="raise_on_sql",
    )


class RouteAlertSubscription(Base):
    """User subscription for delay/cancellation alerts on a route."""

    __tablename__ = "route_alert_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("device_tokens.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source = Column(String(10), nullable=False)
    line_id = Column(String(30), nullable=True)
    from_station_code = Column(String(10), nullable=True)
    to_station_code = Column(String(10), nullable=True)
    train_id = Column(String(30), nullable=True)
    direction = Column(String(10), nullable=True)
    active_days = Column(
        Integer, default=127, nullable=False, server_default="127"
    )  # Bitmask: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64
    active_start_minutes = Column(Integer, nullable=True)  # Minutes from midnight
    active_end_minutes = Column(Integer, nullable=True)  # Minutes from midnight
    timezone = Column(String(40), nullable=True)  # IANA timezone
    delay_threshold_minutes = Column(Integer, nullable=True)  # NULL = system default
    service_threshold_pct = Column(Integer, nullable=True)  # NULL = system default
    cancellation_threshold_pct = Column(Integer, nullable=True)  # NULL = system default
    notify_cancellation = Column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    notify_delay = Column(Boolean, default=True, nullable=False, server_default="true")
    notify_recovery = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    digest_time_minutes = Column(Integer, nullable=True)  # Minutes from midnight
    include_planned_work = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)
    last_alert_hash = Column(String(64), nullable=True)
    last_digest_at = Column(DateTime(timezone=True), nullable=True)
    last_service_alert_ids = Column(JSON, nullable=True)  # Alert IDs already notified

    # Relationships
    device: Mapped["DeviceToken"] = relationship(
        "DeviceToken",
        back_populates="subscriptions",
        foreign_keys=[device_id],
        lazy="raise_on_sql",
    )

    __table_args__ = (
        CheckConstraint(
            "(line_id IS NOT NULL) OR "
            "(from_station_code IS NOT NULL AND to_station_code IS NOT NULL) OR "
            "(train_id IS NOT NULL)",
            name="ck_alert_sub_type",
        ),
        Index("idx_alert_sub_device", "device_id"),
        Index("idx_alert_sub_line", "data_source", "line_id"),
        Index(
            "idx_alert_sub_stations",
            "data_source",
            "from_station_code",
            "to_station_code",
        ),
        Index("idx_alert_sub_train", "data_source", "train_id"),
    )


class ServiceAlert(Base):
    """MTA service alerts (planned work, delays, service changes).

    Stores alerts ingested from GTFS-RT service alert feeds for subway,
    LIRR, and Metro-North. Used to send planned work notifications to
    users subscribed to affected routes.
    """

    __tablename__ = "service_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(
        String(100), nullable=False
    )  # MTA entity ID (e.g. "lmm:planned_work:30497")
    data_source = Column(String(10), nullable=False)  # SUBWAY, LIRR, MNR
    alert_type = Column(String(20), nullable=False)  # planned_work, alert, elevator
    affected_route_ids = Column(JSON, nullable=False)  # ["G", "4"] - GTFS route_ids
    header_text = Column(Text, nullable=False)  # English plain text header
    description_text = Column(Text, nullable=True)  # English plain text description
    active_periods = Column(
        JSON, nullable=False
    )  # [{"start": epoch, "end": epoch}, ...]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("alert_id", "data_source", name="uq_service_alert_id"),
        Index("idx_service_alert_active", "is_active", "data_source"),
        Index("idx_service_alert_type", "alert_type", "data_source"),
    )


class SegmentTransitTime(Base):
    """Track transit times between consecutive stations."""

    __tablename__ = "segment_transit_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False)
    from_station_code = Column(String(10), nullable=False)
    to_station_code = Column(String(10), nullable=False)
    data_source = Column(String(10), nullable=False)
    line_code = Column(String(10))

    # Timing data
    scheduled_minutes = Column(Integer, nullable=False)
    actual_minutes = Column(Integer, nullable=False)
    delay_minutes = Column(Integer, nullable=False)

    # Context for analysis
    departure_time = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    journey: Mapped["TrainJourney"] = relationship(
        "TrainJourney", back_populates="segment_times", lazy="raise_on_sql"
    )

    __table_args__ = (
        Index(
            "idx_segment_lookup",
            "from_station_code",
            "to_station_code",
            "data_source",
            "departure_time",
        ),
        Index(
            "idx_recent_segments", "from_station_code", "to_station_code", "created_at"
        ),
    )


class StationDwellTime(Base):
    """Track time spent at stations."""

    __tablename__ = "station_dwell_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False)
    station_code = Column(String(10), nullable=False)
    data_source = Column(String(10), nullable=False)
    line_code = Column(String(10))

    # Timing data
    scheduled_minutes = Column(Integer)  # Can be NULL for unscheduled stops
    actual_minutes = Column(Integer, nullable=False)
    excess_dwell_minutes = Column(Integer, nullable=False)

    # Station type flags
    is_origin = Column(Boolean, default=False, nullable=False)
    is_terminal = Column(Boolean, default=False, nullable=False)

    # Context
    arrival_time = Column(DateTime(timezone=True))
    departure_time = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    journey: Mapped["TrainJourney"] = relationship(
        "TrainJourney", back_populates="dwell_times", lazy="raise_on_sql"
    )

    __table_args__ = (
        Index("idx_station_dwell", "station_code", "data_source", "departure_time"),
        Index("idx_recent_dwell", "station_code", "created_at"),
    )


class JourneyProgress(Base):
    """Journey progress snapshots for real-time tracking."""

    __tablename__ = "journey_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False)
    captured_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Current position
    last_departed_station = Column(String(10))
    next_station = Column(String(10))

    # Progress metrics
    stops_completed = Column(Integer, nullable=False)
    stops_total = Column(Integer, nullable=False)
    journey_percent = Column(Float, nullable=False)

    # Delay tracking
    initial_delay_minutes = Column(Integer, default=0, nullable=False)
    cumulative_transit_delay = Column(Integer, default=0, nullable=False)
    cumulative_dwell_delay = Column(Integer, default=0, nullable=False)
    total_delay_minutes = Column(Integer, nullable=False)

    # Predictions (when available)
    predicted_arrival = Column(DateTime(timezone=True))
    prediction_confidence = Column(Float)
    prediction_based_on = Column(Text)  # JSON array of train_ids

    # Relationships
    journey: Mapped["TrainJourney"] = relationship(
        "TrainJourney", back_populates="progress", lazy="raise_on_sql"
    )

    __table_args__ = (Index("idx_journey_progress", "journey_id", "captured_at"),)


class CachedApiResponse(Base):
    """Pre-computed API responses for performance optimization."""

    __tablename__ = "cached_api_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String(100), nullable=False)
    params_hash = Column(String(64), nullable=False)
    params = Column(JSON, nullable=False)
    response = Column(JSON, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_cached_api_endpoint_params", "endpoint", "params_hash"),
        Index("idx_cached_api_expires", "expires_at"),
        UniqueConstraint(
            "endpoint", "params_hash", name="uq_cached_api_endpoint_params"
        ),
    )


class SchedulerTaskRun(Base):
    """Track when scheduled tasks last ran to prevent duplicate execution across replicas."""

    __tablename__ = "scheduler_task_runs"

    # Primary key is the task name itself
    task_name = Column(String(50), primary_key=True)

    # When the task last successfully completed
    last_successful_run = Column(DateTime(timezone=True), nullable=False)

    # When the task was last attempted (may not have succeeded)
    last_attempt = Column(DateTime(timezone=True))

    # Metrics for monitoring
    run_count = Column(Integer, default=0, nullable=False)
    average_duration_ms = Column(Integer)
    last_duration_ms = Column(Integer)

    # Track which Cloud Run instance ran it (for debugging)
    last_instance_id = Column(String(100))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (Index("idx_task_freshness", "task_name", "last_successful_run"),)


class ValidationResult(Base):
    """Store results from train validation service for monitoring and analysis."""

    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Route and source information
    route = Column(String(10), nullable=False)  # e.g., "NY->PJ"
    source = Column(String(10), nullable=False)  # e.g., "NJT", "AMTRAK"

    # Coverage metrics
    transit_train_count = Column(Integer, nullable=False)
    api_train_count = Column(Integer, nullable=False)
    coverage_percent = Column(Float, nullable=False)

    # Missing and extra trains (stored as JSON arrays for simplicity)
    missing_trains = Column(JSON)  # Trains in transit API but not our API
    extra_trains = Column(JSON)  # Trains in our API but not transit API

    # Additional details for debugging
    details = Column(JSON)  # Store sample accessibility checks, error details, etc.

    # Indexing for efficient queries
    __table_args__ = (
        Index("idx_validation_time", "run_at", "route", "source"),
        Index("idx_validation_coverage", "route", "source", "coverage_percent"),
    )


# =============================================================================
# GTFS Static Schedule Tables
# =============================================================================


class GTFSFeedInfo(Base):
    """Track GTFS feed download status for rate limiting (max once per 24hrs)."""

    __tablename__ = "gtfs_feed_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(10), nullable=False, unique=True)  # "NJT" or "AMTRAK"
    feed_url = Column(String(500), nullable=False)
    last_downloaded_at = Column(DateTime(timezone=True))
    last_successful_parse_at = Column(DateTime(timezone=True))
    feed_start_date = Column(Date)  # From feed_info.txt if available
    feed_end_date = Column(Date)
    route_count = Column(Integer)
    trip_count = Column(Integer)
    stop_time_count = Column(Integer)
    error_message = Column(Text)  # Last error if download/parse failed

    __table_args__ = (Index("idx_gtfs_feed_source", "data_source"),)


class GTFSRoute(Base):
    """Route definitions from GTFS routes.txt."""

    __tablename__ = "gtfs_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(10), nullable=False)
    route_id = Column(String(50), nullable=False)  # GTFS route_id
    route_short_name = Column(String(20))  # Line code (e.g., "NEC", "MOBO")
    route_long_name = Column(String(200))  # Full name
    route_color = Column(String(6))  # Hex color without #

    # Relationships
    trips: Mapped[list["GTFSTrip"]] = relationship(
        "GTFSTrip",
        back_populates="route",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )

    __table_args__ = (
        UniqueConstraint("data_source", "route_id", name="uq_gtfs_route"),
        Index("idx_gtfs_route_lookup", "data_source", "route_id"),
    )


class GTFSTrip(Base):
    """Trip definitions from GTFS trips.txt."""

    __tablename__ = "gtfs_trips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(10), nullable=False)
    trip_id = Column(String(100), nullable=False)  # GTFS trip_id
    route_id = Column(Integer, ForeignKey("gtfs_routes.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(String(50), nullable=False)  # Links to calendar
    trip_headsign = Column(String(100))  # Destination name
    train_id = Column(String(20))  # Extracted train number if available
    direction_id = Column(Integer)  # 0=outbound, 1=inbound

    # Relationships
    route: Mapped["GTFSRoute"] = relationship(
        "GTFSRoute", back_populates="trips", lazy="raise_on_sql"
    )
    stop_times: Mapped[list["GTFSStopTime"]] = relationship(
        "GTFSStopTime",
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )

    __table_args__ = (
        UniqueConstraint("data_source", "trip_id", name="uq_gtfs_trip"),
        Index("idx_gtfs_trip_service", "data_source", "service_id"),
        Index("idx_gtfs_trip_lookup", "data_source", "trip_id"),
    )


class GTFSStopTime(Base):
    """Stop times from GTFS stop_times.txt."""

    __tablename__ = "gtfs_stop_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("gtfs_trips.id", ondelete="CASCADE"), nullable=False)
    stop_sequence = Column(Integer, nullable=False)

    # GTFS stop_id and our mapped station code
    gtfs_stop_id = Column(String(50), nullable=False)
    station_code = Column(String(10))  # Our internal code (null if unmapped)

    # Times stored as strings to handle >24:00 (e.g., "25:30:00" for 1:30 AM next day)
    arrival_time = Column(String(8))  # HH:MM:SS format
    departure_time = Column(String(8))  # HH:MM:SS format

    # Pickup/dropoff type (0=regular, 1=none, 2=phone agency, 3=coordinate with driver)
    pickup_type = Column(Integer, default=0)
    drop_off_type = Column(Integer, default=0)

    # Relationships
    trip: Mapped["GTFSTrip"] = relationship(
        "GTFSTrip", back_populates="stop_times", lazy="raise_on_sql"
    )

    __table_args__ = (
        Index("idx_gtfs_stop_time_trip", "trip_id", "stop_sequence"),
        Index("idx_gtfs_stop_time_station", "station_code", "departure_time"),
    )


class GTFSCalendar(Base):
    """Service calendar from GTFS calendar.txt - weekly patterns."""

    __tablename__ = "gtfs_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(10), nullable=False)
    service_id = Column(String(50), nullable=False)

    # Day of week flags
    monday = Column(Boolean, nullable=False, default=False)
    tuesday = Column(Boolean, nullable=False, default=False)
    wednesday = Column(Boolean, nullable=False, default=False)
    thursday = Column(Boolean, nullable=False, default=False)
    friday = Column(Boolean, nullable=False, default=False)
    saturday = Column(Boolean, nullable=False, default=False)
    sunday = Column(Boolean, nullable=False, default=False)

    # Validity period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("data_source", "service_id", name="uq_gtfs_calendar"),
        Index("idx_gtfs_calendar_dates", "data_source", "start_date", "end_date"),
    )


class GTFSCalendarDate(Base):
    """Service exceptions from GTFS calendar_dates.txt."""

    __tablename__ = "gtfs_calendar_dates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(10), nullable=False)
    service_id = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    exception_type = Column(
        Integer, nullable=False
    )  # 1=service added, 2=service removed

    __table_args__ = (
        UniqueConstraint(
            "data_source", "service_id", "date", name="uq_gtfs_calendar_date"
        ),
        Index("idx_gtfs_calendar_date_lookup", "data_source", "date"),
    )


# =============================================================================
# Developer Chat Tables
# =============================================================================


class ChatMessage(Base):
    """Messages between users and the developer (admin)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("device_tokens.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_role = Column(String(5), nullable=False)  # "user" or "admin"
    message = Column(String(255), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "sender_role IN ('user', 'admin')",
            name="ck_chat_sender_role",
        ),
        Index("idx_chat_device_id", "device_id"),
        Index("idx_chat_created_at", "device_id", "created_at"),
        Index("idx_chat_unread", "device_id", "sender_role", "read_at"),
    )


class AdminDevice(Base):
    """Devices registered as admin for developer chat."""

    __tablename__ = "admin_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
