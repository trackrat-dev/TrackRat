"""
SQLAlchemy database models for TrackRat V2.

Follows the simplified single-journey design documented in backend_v2/CLAUDE.md.
"""

import itertools
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    false,
    func,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, declarative_base, relationship, validates

from trackrat.db.partitioning import (
    ensure_future_partitions_sync_for_table,
    get_partitioned_table,
)

Base = declarative_base()


class TrainJourney(Base):
    """Core train journey table - one record per train per day."""

    __tablename__ = "train_journeys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_id = Column(String(30), nullable=False)  # PATH train IDs are ~21 chars
    journey_date = Column(Date, nullable=False)
    line_code = Column(String(15), nullable=False)  # METRA-UP-NW is 11 chars
    line_name = Column(String(100))
    line_color = Column(String(7))
    destination = Column(String(100), nullable=False)
    origin_station_code = Column(String(10), nullable=False)
    terminal_station_code = Column(String(10), nullable=False)
    data_source = Column(String(20), nullable=False, default="NJT")
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
        # No standalone idx_train_id: train_id-only lookups use the leading
        # column of unique_train_journey (dropped in 82fd0005853a).
        Index("idx_data_source", "data_source"),
        Index("idx_active_journeys", "is_completed", "is_expired", "is_cancelled"),
        # Composite index for date + source queries (congestion, history, forecaster).
        # Supersedes a standalone idx_journey_date: journey_date is the leading
        # column, so date-only predicates (e.g. the retention sweep) use it too.
        Index("idx_journey_date_source", "journey_date", "data_source"),
        # Composite index for congestion queries:
        #   last_updated_at >= cutoff AND is_cancelled = false AND data_source = ?
        # Supersedes a standalone idx_last_updated (last_updated_at leads). Created
        # in production by migration 5b4681856a79.
        Index(
            "idx_congestion_journey_lookup",
            "last_updated_at",
            "is_cancelled",
            "data_source",
        ),
        # Composite index for delay forecaster lookback queries:
        #   train_id = ? AND origin_station_code = ? AND data_source = ?
        #   AND journey_date >= cutoff
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

    # Identity() (not autoincrement=True) because `id` is part of a composite
    # primary key (issue #1343 partitioning) — SQLite's compiler hard-rejects
    # autoincrement on a composite PK, while Identity() compiles to a real
    # Postgres GENERATED BY DEFAULT AS IDENTITY column and is simply ignored
    # (as a plain INTEGER) by SQLite, which the njt collector unit tests use.
    id = Column(Integer, Identity(), primary_key=True)
    journey_id = Column(
        Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized from TrainJourney.journey_date so this table can be a
    # Postgres RANGE partition on journey_date (issue #1343) — Postgres
    # requires every unique/primary key constraint on a partitioned table to
    # include the partition key column. Auto-populated by the `journey`
    # validator below for stops constructed via the ORM relationship; call
    # sites that only set journey_id must pass journey_date explicitly.
    journey_date = Column(Date, nullable=False, primary_key=True)
    station_code = Column(String(10), nullable=False)
    station_name = Column(String(100), nullable=False)
    stop_sequence = Column(
        Integer, nullable=True
    )  # Allow NULL until journey collector sets it

    # Scheduled times (from initial schedule)
    scheduled_arrival = Column(DateTime(timezone=True))
    scheduled_departure = Column(DateTime(timezone=True))

    # Updated times — raw real-time values from the transit provider API.
    #
    # WARNING — NJT SEMANTIC MISMATCH (position-dependent):
    # For most providers (Amtrak, GTFS-RT systems, PATH, WMATA), these are
    # genuine live estimates (i.e., "current best guess for arrival/departure").
    # For NJT, these are raw TIME/DEP_TIME passthroughs whose meaning depends
    # on the stop's position in the journey:
    #   - ORIGIN:       updated_arrival = original schedule (TIME);
    #                   updated_departure = LIVE departure estimate (DEP_TIME,
    #                   moves with delays — issue #1496)
    #   - INTERMEDIATE: updated_arrival = LIVE arrival estimate (TIME);
    #                   updated_departure = original schedule (DEP_TIME)
    #   - TERMINAL:     updated_arrival = LIVE arrival estimate (TIME);
    #                   updated_departure is usually absent, but when present
    #                   can be a later TURNAROUND departure that must not be
    #                   promoted into the arrival (issue #1492)
    # NEVER read these fields raw for NJT. The canonical correction is
    # utils/train.effective_njt_updated_times (max() at non-terminal stops,
    # skipped at the terminal) with utils/train.terminal_stop_index for
    # conservative terminal detection; the SQL twin is
    # GREATEST(updated_departure, updated_arrival) guarded to NJT rows (see
    # the congestion stop_pairs CTE). The arrival-side fallback
    # `updated_arrival or updated_departure` is safe for NJT.
    # Full reference: backend_v2/docs/journey-lifecycle.md §2.
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

    # How we determined actual_arrival (api_observed, scheduled_fallback).
    # NOTE: Historical stops (before ~March 2026) may have NULL arrival_source
    # even with valid actual_arrival data. A backfill migration was attempted
    # but removed (f7a8b9c0d1e2) because it took too long on large datasets
    # and caused MIG health check failures. New data is populated correctly.
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

    @validates("journey")
    def _set_journey_date_from_journey(
        self, key: str, journey: "TrainJourney | None"
    ) -> "TrainJourney | None":
        """Auto-populate journey_date for stops linked via the ORM
        relationship (`JourneyStop(journey=...)` or
        `TrainJourney.stops.append(...)`). Call sites that only set
        journey_id (no `journey` object in scope) must pass journey_date
        explicitly — see collectors that build stops from a bare journey_id.
        """
        if journey is not None and self.journey_date is None:
            self.journey_date = journey.journey_date
        return journey

    __table_args__ = (
        UniqueConstraint(
            "journey_id", "station_code", "journey_date", name="unique_journey_stop"
        ),
        Index("idx_station_times", "station_code", "scheduled_departure"),
        # Covering index for the consecutive-stop self-join in congestion
        # analytics. Supersedes a standalone idx_journey_sequence
        # (journey_id, stop_sequence) — it is the leading-column prefix here.
        # Created in production by migration 5b4681856a79.
        Index(
            "idx_journey_stops_sequence_lookup",
            "journey_id",
            "stop_sequence",
            "station_code",
            postgresql_include=[
                "scheduled_departure",
                "scheduled_arrival",
                "actual_departure",
                "actual_arrival",
            ],
        ),
        Index("idx_stop_track_distribution", "station_code", "track"),
        Index("idx_stop_delay_forecaster", "station_code", "journey_id"),
        # No (journey_id, station_code, stop_sequence) index: equality
        # lookups on (journey_id, station_code) use unique_journey_stop's
        # identical leading prefix, and journey_id-ordered scans use
        # idx_journey_stops_sequence_lookup (dropped in 82fd0005853a).
        # Companion to idx_station_times for the "actual if present, else
        # scheduled" departure-window filter used by summary.py and
        # congestion queries. Without this, that OR condition can't use an
        # index on either branch, so Postgres falls back to whichever
        # station_code-prefixed index is cheapest to scan (frequently
        # idx_stop_track_distribution) and filters ~everything else out by
        # hand — a multi-minute scan on busy stations (issue #1354). Partial
        # on IS NOT NULL since most rows never populate actual_departure
        # until the stop is actually observed departing, keeping this index
        # meaningfully smaller than a full one. Originally added standalone in
        # 67a02e68d9aa; folded into the #1343 partition rebuild so the fresh
        # partitioned journey_stops carries it too (created per empty
        # partition by 03db10760b28 — instant, no CONCURRENT hand-build).
        Index(
            "idx_stop_actual_departure",
            "station_code",
            "actual_departure",
            postgresql_where=actual_departure.isnot(None),
        ),
        {"postgresql_partition_by": "RANGE (journey_date)"},
    )


_sqlite_journey_stop_ids = itertools.count(1)


@event.listens_for(JourneyStop, "before_insert")
def _assign_sqlite_id(
    mapper: Mapper[Any], connection: Connection, target: "JourneyStop"
) -> None:
    """SQLite has no ROWID-alias autoincrement for a column in a composite
    primary key (`id` is part of `(id, journey_date)` since issue #1343), so
    `id` is never auto-populated there as it would be under a single-column
    PK. Postgres uses a real `Identity()` column and is unaffected — this
    only backstops the in-memory SQLite engine some collector unit tests use.

    Uses an in-memory counter rather than `SELECT MAX(id)`: SQLAlchemy
    batches same-mapper inserts within one flush (fires every `before_insert`
    before executing any of their INSERTs), so a DB-query-based counter would
    read the same stale MAX for every row in a batch and assign duplicates.
    """
    if target.id is not None or connection.dialect.name != "sqlite":
        return
    target.id = next(_sqlite_journey_stop_ids)


@event.listens_for(JourneyStop.__table__, "after_create")
def _create_journey_stops_partitions(
    target: Any, connection: Connection, **kw: Any
) -> None:
    """Bootstrap the rolling partition window when the table is created via
    `Base.metadata.create_all()` (tests). The Alembic migration bootstraps
    partitions for real deployments; this keeps `create_all()`-based tests
    working without running migrations.

    Postgres-only: some collector unit tests use an in-memory SQLite engine,
    which has no notion of partitioning and doesn't need this bootstrap.
    """
    if connection.dialect.name != "postgresql":
        return
    ensure_future_partitions_sync_for_table(
        connection, get_partitioned_table("journey_stops")
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


class LiveActivityToken(Base):
    """Minimal Live Activity token storage for iOS push notifications."""

    __tablename__ = "live_activity_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    push_token = Column(String, unique=True, nullable=False)  # APNS token
    activity_id = Column(String, nullable=False)  # iOS Activity ID
    train_number = Column(String(30), nullable=False)  # PATH IDs are ~21 chars
    origin_code = Column(String(10), nullable=False)  # e.g., "NY"
    destination_code = Column(String(10), nullable=False)  # e.g., "WAS"
    # Disambiguates journeys when train_number collides across systems.
    # Nullable so older clients that never sent it still receive updates
    # (with the legacy "first-match wins" behavior).
    data_source = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Auto-expire after journey
    is_active = Column(Boolean, default=True, nullable=False)
    track_notified_at = Column(DateTime(timezone=True), nullable=True)

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
    data_source = Column(String(20), nullable=False)
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
            "(train_id IS NOT NULL) OR "
            "(line_id IS NULL AND from_station_code IS NULL "
            "AND to_station_code IS NULL AND train_id IS NULL)",
            name="ck_alert_sub_type",
        ),
        Index("idx_alert_sub_device", "device_id"),
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
    data_source = Column(String(20), nullable=False)  # SUBWAY, LIRR, MNR
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
    )


class SegmentTransitTime(Base):
    """Track transit times between consecutive stations."""

    __tablename__ = "segment_transit_times"

    # See JourneyStop.id: Identity() (not autoincrement=True) because `id` is
    # part of a composite primary key.
    id = Column(Integer, Identity(), primary_key=True)
    journey_id = Column(
        Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False
    )
    from_station_code = Column(String(10), nullable=False)
    to_station_code = Column(String(10), nullable=False)
    data_source = Column(String(20), nullable=False)
    line_code = Column(String(15))

    # Timing data
    scheduled_minutes = Column(Integer, nullable=False)
    actual_minutes = Column(Integer, nullable=False)
    delay_minutes = Column(Integer, nullable=False)

    # Context for analysis.
    # Also the RANGE partition key (issue #1343) — part of the composite
    # primary key because Postgres requires every unique/primary key
    # constraint on a partitioned table to include the partition column.
    departure_time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
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
        Index("idx_segment_journey", "journey_id"),
        # No (from, to, data_source, departure_time) index: its consumers
        # moved to idx_segment_baseline (b8ca879ae8c5), and from-prefix
        # range scans use idx_recent_segments (dropped in 82fd0005853a).
        Index(
            "idx_recent_segments", "from_station_code", "to_station_code", "created_at"
        ),
        Index(
            "idx_segment_baseline",
            "data_source",
            "hour_of_day",
            "day_of_week",
            "departure_time",
        ),
        {"postgresql_partition_by": "RANGE (departure_time)"},
    )


_sqlite_segment_transit_time_ids = itertools.count(1)


@event.listens_for(SegmentTransitTime, "before_insert")
def _assign_sqlite_id_segment(
    mapper: Mapper[Any], connection: Connection, target: "SegmentTransitTime"
) -> None:
    """See `_assign_sqlite_id` on JourneyStop — same rationale."""
    if target.id is not None or connection.dialect.name != "sqlite":
        return
    target.id = next(_sqlite_segment_transit_time_ids)


@event.listens_for(SegmentTransitTime.__table__, "after_create")
def _create_segment_transit_times_partitions(
    target: Any, connection: Connection, **kw: Any
) -> None:
    """See `_create_journey_stops_partitions` — same rationale, Postgres-only."""
    if connection.dialect.name != "postgresql":
        return
    ensure_future_partitions_sync_for_table(
        connection, get_partitioned_table("segment_transit_times")
    )


class PartitionBackfillState(Base):
    """Progress cursor for the one-time #1343 backfill of `*_legacy` rows into
    the new partitioned tables. One row per legacy table. `last_copied_id` is
    the lowest legacy id copied so far (the backfill copies newest-first);
    `completed` flips true once the retention window is exhausted, after which
    the legacy table is dropped. See `db/partitioning.py`.
    """

    __tablename__ = "partition_backfill_state"

    # server_default (not default=) throughout: the backfill inserts new rows
    # via raw SQL (INSERT ... (legacy_table) VALUES (...)), which bypasses ORM
    # client-side defaults, so the DDL must carry the defaults itself — and it
    # must match migration 03db10760b28's CREATE TABLE.
    legacy_table = Column(String(64), primary_key=True)
    last_copied_id = Column(Integer, nullable=True)
    completed = Column(Boolean, nullable=False, server_default=false())
    rows_copied = Column(Integer, nullable=False, server_default="0")
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StationDwellTime(Base):
    """Track time spent at stations."""

    __tablename__ = "station_dwell_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(
        Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False
    )
    station_code = Column(String(10), nullable=False)
    data_source = Column(String(20), nullable=False)
    line_code = Column(String(15))

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

    __table_args__ = (Index("idx_dwell_journey", "journey_id"),)


class JourneyProgress(Base):
    """Journey progress snapshots for real-time tracking."""

    __tablename__ = "journey_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(
        Integer, ForeignKey("train_journeys.id", ondelete="CASCADE"), nullable=False
    )
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


class ValidationResult(Base):
    """Store results from train validation service for monitoring and analysis."""

    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Route and source information
    route = Column(String(10), nullable=False)  # e.g., "NY->PJ"
    source = Column(String(20), nullable=False)  # e.g., "NJT", "AMTRAK"

    # Coverage metrics
    transit_train_count = Column(Integer, nullable=False)
    api_train_count = Column(Integer, nullable=False)
    coverage_percent = Column(Float, nullable=False)

    # Missing and extra trains (stored as JSON arrays for simplicity)
    missing_trains = Column(JSON)  # Trains in transit API but not our API
    extra_trains = Column(JSON)  # Trains in our API but not transit API

    # Additional details for debugging
    details = Column(JSON)  # Store sample accessibility checks, error details, etc.


# =============================================================================
# GTFS Static Schedule Tables
# =============================================================================


class GTFSFeedInfo(Base):
    """Track GTFS feed download status for rate limiting (max once per 24hrs)."""

    __tablename__ = "gtfs_feed_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(20), nullable=False, unique=True)  # "NJT" or "AMTRAK"
    feed_url = Column(String(500), nullable=False)
    last_downloaded_at = Column(DateTime(timezone=True))
    last_successful_parse_at = Column(DateTime(timezone=True))
    feed_start_date = Column(Date)  # From feed_info.txt if available
    feed_end_date = Column(Date)
    route_count = Column(Integer)
    trip_count = Column(Integer)
    stop_time_count = Column(Integer)
    error_message = Column(Text)  # Last error if download/parse failed


class GTFSRoute(Base):
    """Route definitions from GTFS routes.txt."""

    __tablename__ = "gtfs_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source = Column(String(20), nullable=False)
    route_id = Column(String(50), nullable=False)  # GTFS route_id
    route_short_name = Column(String(50))  # Line code (e.g., "NEC", "MOBO")
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
    data_source = Column(String(20), nullable=False)
    trip_id = Column(String(100), nullable=False)  # GTFS trip_id
    route_id = Column(
        Integer, ForeignKey("gtfs_routes.id", ondelete="CASCADE"), nullable=False
    )
    service_id = Column(String(50), nullable=False)  # Links to calendar
    trip_headsign = Column(String(100))  # Destination name
    train_id = Column(String(50))  # Extracted train number if available
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
    trip_id = Column(
        Integer, ForeignKey("gtfs_trips.id", ondelete="CASCADE"), nullable=False
    )
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
    data_source = Column(String(20), nullable=False)
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
    data_source = Column(String(20), nullable=False)
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


class RoutePreference(Base):
    """Per-device filter preference for a station pair (which systems/lines to show)."""

    __tablename__ = "route_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        String(64),
        ForeignKey("device_tokens.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    from_station_code = Column(String(10), nullable=False)
    to_station_code = Column(String(10), nullable=False)
    # {"NJT": ["NE", "NEC"], "AMTRAK": ["AM"]} — system absent = disabled
    enabled_systems = Column(JSON, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "from_station_code",
            "to_station_code",
            name="uq_route_pref_device_stations",
        ),
        Index("idx_route_pref_device", "device_id"),
    )
