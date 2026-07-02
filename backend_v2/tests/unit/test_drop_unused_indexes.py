"""Tests for unused index removal (Issue #986).

Verifies that dropped indexes are no longer in model definitions,
retained indexes are still present, and the migration drops/recreates
exactly the right set.
"""

import importlib
import types

from sqlalchemy import Index, UniqueConstraint

from trackrat.models.database import (
    DiscoveryRun,
    GTFSFeedInfo,
    JourneyStop,
    RouteAlertSubscription,
    SchedulerTaskRun,
    ServiceAlert,
    StationDwellTime,
    TrainJourney,
    ValidationResult,
)

DROPPED_INDEXES = {
    "idx_captured_at",
    "idx_station_dwell",
    "idx_recent_dwell",
    "idx_discovery_time",
    "idx_validation_coverage",
    "idx_validation_time",
    "idx_service_alert_type",
    "idx_alert_sub_line",
    "idx_alert_sub_stations",
    "idx_task_freshness",
    "idx_gtfs_feed_source",
}

RETAINED_INDEXES = {
    "idx_station_times",
    "idx_stop_track_distribution",
    "idx_stop_delay_forecaster",
    "idx_stop_journey_station_seq",
    "idx_journey_time",
    "idx_service_alert_active",
    "idx_alert_sub_device",
    "idx_alert_sub_train",
}


def _get_index_names(model_class):
    """Extract index names from a model's __table_args__."""
    table_args = getattr(model_class, "__table_args__", ())
    if isinstance(table_args, dict):
        return set()
    names = set()
    for arg in table_args:
        if isinstance(arg, Index):
            names.add(arg.name)
    return names


def test_dropped_indexes_not_in_station_dwell_times_model():
    indexes = _get_index_names(StationDwellTime)
    assert (
        "idx_station_dwell" not in indexes
    ), f"idx_station_dwell should be removed from StationDwellTime"
    assert (
        "idx_recent_dwell" not in indexes
    ), f"idx_recent_dwell should be removed from StationDwellTime"


def test_dropped_indexes_not_in_discovery_runs_model():
    indexes = _get_index_names(DiscoveryRun)
    assert (
        "idx_discovery_time" not in indexes
    ), f"idx_discovery_time should be removed from DiscoveryRun"


def test_dropped_indexes_not_in_validation_results_model():
    indexes = _get_index_names(ValidationResult)
    assert "idx_validation_time" not in indexes
    assert "idx_validation_coverage" not in indexes


def test_dropped_indexes_not_in_service_alerts_model():
    indexes = _get_index_names(ServiceAlert)
    assert (
        "idx_service_alert_type" not in indexes
    ), f"idx_service_alert_type should be removed from ServiceAlert"


def test_dropped_indexes_not_in_route_alert_subscriptions_model():
    indexes = _get_index_names(RouteAlertSubscription)
    assert "idx_alert_sub_line" not in indexes
    assert "idx_alert_sub_stations" not in indexes


def test_dropped_indexes_not_in_scheduler_task_runs_model():
    indexes = _get_index_names(SchedulerTaskRun)
    assert "idx_task_freshness" not in indexes, (
        f"idx_task_freshness should be removed from SchedulerTaskRun "
        f"(task_name is already PK)"
    )


def test_dropped_indexes_not_in_gtfs_feed_info_model():
    indexes = _get_index_names(GTFSFeedInfo)
    assert "idx_gtfs_feed_source" not in indexes, (
        f"idx_gtfs_feed_source should be removed from GTFSFeedInfo "
        f"(data_source already has unique=True)"
    )


def test_retained_indexes_still_present_on_journey_stops():
    indexes = _get_index_names(JourneyStop)
    expected = {
        "idx_station_times",
        "idx_stop_track_distribution",
        "idx_stop_delay_forecaster",
        "idx_stop_journey_station_seq",
        # Covering index that supersedes the dropped idx_journey_sequence.
        "idx_journey_stops_sequence_lookup",
    }
    missing = expected - indexes
    assert not missing, (
        f"JourneyStop is missing retained indexes: {missing}. "
        f"Current indexes: {indexes}"
    )


def test_track_occupancy_lookup_dropped():
    """idx_track_occupancy_lookup was dropped (migration d8c07a8efd43).

    Reverses the earlier decision to retain it: track_occupancy.py filters
    station_code + a scheduled_departure window, which idx_station_times serves,
    so the planner never used this index (0 scans on production against billions
    elsewhere) and it had bloated to ~4 GB.
    """
    indexes = _get_index_names(JourneyStop)
    assert "idx_track_occupancy_lookup" not in indexes, (
        "idx_track_occupancy_lookup should be removed from JourneyStop; "
        "it is redundant with idx_station_times for the track-occupancy query"
    )


def test_retained_indexes_still_present_on_service_alerts():
    indexes = _get_index_names(ServiceAlert)
    assert (
        "idx_service_alert_active" in indexes
    ), f"idx_service_alert_active should be retained on ServiceAlert"


def test_retained_indexes_still_present_on_route_alert_subscriptions():
    indexes = _get_index_names(RouteAlertSubscription)
    expected = {"idx_alert_sub_device", "idx_alert_sub_train"}
    missing = expected - indexes
    assert not missing, f"RouteAlertSubscription is missing retained indexes: {missing}"


def test_unique_constraint_preserved_on_journey_stops():
    """unique_journey_stop constraint must survive the index cleanup."""
    table_args = getattr(JourneyStop, "__table_args__", ())
    constraints = [arg for arg in table_args if isinstance(arg, UniqueConstraint)]
    names = {c.name for c in constraints}
    assert (
        "unique_journey_stop" in names
    ), f"unique_journey_stop constraint missing from JourneyStop"


def test_unique_constraint_preserved_on_service_alerts():
    """uq_service_alert_id constraint must survive the index cleanup."""
    table_args = getattr(ServiceAlert, "__table_args__", ())
    constraints = [arg for arg in table_args if isinstance(arg, UniqueConstraint)]
    names = {c.name for c in constraints}
    assert "uq_service_alert_id" in names


def test_no_dropped_index_appears_in_any_model():
    """Cross-check: none of the 11 dropped indexes appear in any model."""
    all_models = [
        JourneyStop,
        StationDwellTime,
        DiscoveryRun,
        ValidationResult,
        ServiceAlert,
        RouteAlertSubscription,
        SchedulerTaskRun,
        GTFSFeedInfo,
    ]
    for model in all_models:
        indexes = _get_index_names(model)
        overlap = DROPPED_INDEXES & indexes
        assert not overlap, f"{model.__name__} still has dropped indexes: {overlap}"


def test_migration_drops_exactly_eleven_indexes():
    """Verify the migration upgrade function drops exactly 11 indexes."""
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260423_1749-d170389c0848_drop_unused_indexes"
    )
    assert migration.revision == "d170389c0848"
    assert migration.down_revision == "c17a6a3e8c3c"

    calls = []
    mock_op = types.SimpleNamespace(
        drop_index=lambda name, **kwargs: calls.append(
            ("drop", name, kwargs.get("table_name"))
        )
    )

    import trackrat.db.migrations.versions as versions_pkg

    mod = getattr(
        versions_pkg,
        "20260423_1749-d170389c0848_drop_unused_indexes",
        migration,
    )

    original_op = None
    try:
        original_op = getattr(mod, "op", None)
        mod.op = mock_op
        mod.upgrade()
    finally:
        if original_op is not None:
            mod.op = original_op
        else:
            delattr(mod, "op")

    dropped_names = {name for _, name, _ in calls}
    assert dropped_names == DROPPED_INDEXES, (
        f"Migration should drop exactly {DROPPED_INDEXES}, "
        f"but dropped {dropped_names}. "
        f"Missing: {DROPPED_INDEXES - dropped_names}, "
        f"Extra: {dropped_names - DROPPED_INDEXES}"
    )
    assert len(calls) == 11, f"Expected 11 drop_index calls, got {len(calls)}"


def test_d170389c0848_does_not_drop_track_occupancy_lookup():
    """The #986 cleanup (d170389c0848) deferred dropping this index.

    Historical guard: that migration left idx_track_occupancy_lookup in place.
    The drop happens later in d8c07a8efd43 — see the test below.
    """
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260423_1749-d170389c0848_drop_unused_indexes"
    )

    calls = []
    mock_op = types.SimpleNamespace(
        drop_index=lambda name, **kwargs: calls.append(name)
    )

    try:
        original_op = getattr(migration, "op", None)
        migration.op = mock_op
        migration.upgrade()
    finally:
        if original_op is not None:
            migration.op = original_op
        else:
            delattr(migration, "op")

    assert "idx_track_occupancy_lookup" not in calls


def test_d8c07a8efd43_drops_track_occupancy_lookup_and_tunes_autovacuum():
    """The new migration drops the dead index and tightens autovacuum."""
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260630_2021-d8c07a8efd43_drop_unused_idx_track_occupancy_lookup_"
    )
    assert migration.revision == "d8c07a8efd43"
    assert migration.down_revision == "b9f37157aada"

    statements: list[str] = []
    mock_op = types.SimpleNamespace(execute=lambda sql: statements.append(str(sql)))

    original_op = getattr(migration, "op", None)
    try:
        migration.op = mock_op
        migration.upgrade()
    finally:
        migration.op = original_op

    joined = "\n".join(statements)
    assert "DROP INDEX IF EXISTS idx_track_occupancy_lookup" in joined
    # Autovacuum tightened on all three high-churn tables.
    for table in ("journey_stops", "segment_transit_times", "train_journeys"):
        assert any(
            table in s and "autovacuum_vacuum_scale_factor = 0.02" in s
            for s in statements
        ), f"missing autovacuum tuning for {table}"


def test_migration_downgrade_recreates_all_eleven_indexes():
    """Verify the migration downgrade recreates all 11 indexes."""
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260423_1749-d170389c0848_drop_unused_indexes"
    )

    calls = []
    mock_op = types.SimpleNamespace(
        create_index=lambda name, table, columns, **kwargs: calls.append(
            ("create", name, table, columns)
        )
    )

    try:
        original_op = getattr(migration, "op", None)
        migration.op = mock_op
        migration.downgrade()
    finally:
        if original_op is not None:
            migration.op = original_op
        else:
            delattr(migration, "op")

    created_names = {name for _, name, _, _ in calls}
    assert created_names == DROPPED_INDEXES, (
        f"Downgrade should recreate exactly {DROPPED_INDEXES}, "
        f"but created {created_names}"
    )
    assert len(calls) == 11, f"Expected 11 create_index calls, got {len(calls)}"


# ---------------------------------------------------------------------------
# Redundant prefix-index reconciliation (migration fd85e7f3abb3)
# ---------------------------------------------------------------------------

# Indexes dropped because they are a strict leading-column prefix of a wider
# index that already serves the same predicates.
REDUNDANT_PREFIX_DROPPED = {
    "idx_journey_date",  # -> idx_journey_date_source
    "idx_journey_sequence",  # -> idx_journey_stops_sequence_lookup
    "idx_last_updated",  # -> idx_congestion_journey_lookup
}


def test_redundant_prefix_indexes_removed_from_models():
    """The three superseded prefix indexes must be gone from the models."""
    train_journey_idx = _get_index_names(TrainJourney)
    journey_stop_idx = _get_index_names(JourneyStop)
    all_idx = train_journey_idx | journey_stop_idx
    overlap = REDUNDANT_PREFIX_DROPPED & all_idx
    assert not overlap, f"Models still declare dropped prefix indexes: {overlap}"


def test_superseding_indexes_present_in_models():
    """The wider indexes that absorb the dropped prefixes must be declared.

    These existed in production (migration 5b4681856a79) but were missing from
    the models, which is what made the prefix indexes look load-bearing.
    """
    train_journey_idx = _get_index_names(TrainJourney)
    journey_stop_idx = _get_index_names(JourneyStop)
    assert "idx_journey_date_source" in train_journey_idx
    assert "idx_congestion_journey_lookup" in train_journey_idx
    assert "idx_journey_stops_sequence_lookup" in journey_stop_idx


def test_idx_delay_forecaster_declared_in_model():
    """idx_delay_forecaster stays in the model; the migration creates it in prod."""
    assert "idx_delay_forecaster" in _get_index_names(TrainJourney)


def test_fd85e7f3abb3_upgrade_statements():
    """The migration creates idx_delay_forecaster, drops the prefixes, tunes vacuum."""
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260630_2303-fd85e7f3abb3_drop_redundant_prefix_indexes_create_"
    )
    assert migration.revision == "fd85e7f3abb3"
    assert migration.down_revision == "d8c07a8efd43"

    statements: list[str] = []
    mock_op = types.SimpleNamespace(execute=lambda sql: statements.append(str(sql)))

    original_op = getattr(migration, "op", None)
    try:
        migration.op = mock_op
        migration.upgrade()
    finally:
        migration.op = original_op

    joined = "\n".join(statements)
    assert "CREATE INDEX IF NOT EXISTS idx_delay_forecaster" in joined
    for name in REDUNDANT_PREFIX_DROPPED:
        assert f"DROP INDEX IF EXISTS {name}" in joined, f"missing drop for {name}"
    for table in ("journey_stops", "segment_transit_times", "train_journeys"):
        assert any(
            table in s and "autovacuum_vacuum_cost_limit = 1000" in s
            for s in statements
        ), f"missing cost_limit tuning for {table}"
