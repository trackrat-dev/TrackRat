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
    JourneySnapshot,
    JourneyStop,
    RouteAlertSubscription,
    SchedulerTaskRun,
    ServiceAlert,
    StationDwellTime,
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
    "idx_journey_sequence",
    "idx_track_occupancy_lookup",
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


def test_dropped_indexes_not_in_journey_snapshots_model():
    indexes = _get_index_names(JourneySnapshot)
    assert "idx_captured_at" not in indexes, (
        f"idx_captured_at should be removed from JourneySnapshot, "
        f"found indexes: {indexes}"
    )


def test_dropped_indexes_not_in_station_dwell_times_model():
    indexes = _get_index_names(StationDwellTime)
    assert "idx_station_dwell" not in indexes, (
        f"idx_station_dwell should be removed from StationDwellTime"
    )
    assert "idx_recent_dwell" not in indexes, (
        f"idx_recent_dwell should be removed from StationDwellTime"
    )


def test_dropped_indexes_not_in_discovery_runs_model():
    indexes = _get_index_names(DiscoveryRun)
    assert "idx_discovery_time" not in indexes, (
        f"idx_discovery_time should be removed from DiscoveryRun"
    )


def test_dropped_indexes_not_in_validation_results_model():
    indexes = _get_index_names(ValidationResult)
    assert "idx_validation_time" not in indexes
    assert "idx_validation_coverage" not in indexes


def test_dropped_indexes_not_in_service_alerts_model():
    indexes = _get_index_names(ServiceAlert)
    assert "idx_service_alert_type" not in indexes, (
        f"idx_service_alert_type should be removed from ServiceAlert"
    )


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
        "idx_journey_sequence",
        "idx_track_occupancy_lookup",
        "idx_stop_track_distribution",
        "idx_stop_delay_forecaster",
        "idx_stop_journey_station_seq",
    }
    missing = expected - indexes
    assert not missing, (
        f"JourneyStop is missing retained indexes: {missing}. "
        f"Current indexes: {indexes}"
    )


def test_track_occupancy_lookup_explicitly_retained():
    """idx_track_occupancy_lookup must be kept — track_occupancy.py uses it."""
    indexes = _get_index_names(JourneyStop)
    assert "idx_track_occupancy_lookup" in indexes, (
        "idx_track_occupancy_lookup must NOT be dropped; "
        "track_occupancy.py queries on (station_code, has_departed_station, "
        "scheduled_departure)"
    )


def test_retained_indexes_still_present_on_journey_snapshots():
    indexes = _get_index_names(JourneySnapshot)
    assert "idx_journey_time" in indexes, (
        f"idx_journey_time should be retained on JourneySnapshot"
    )


def test_retained_indexes_still_present_on_service_alerts():
    indexes = _get_index_names(ServiceAlert)
    assert "idx_service_alert_active" in indexes, (
        f"idx_service_alert_active should be retained on ServiceAlert"
    )


def test_retained_indexes_still_present_on_route_alert_subscriptions():
    indexes = _get_index_names(RouteAlertSubscription)
    expected = {"idx_alert_sub_device", "idx_alert_sub_train"}
    missing = expected - indexes
    assert not missing, (
        f"RouteAlertSubscription is missing retained indexes: {missing}"
    )


def test_unique_constraint_preserved_on_journey_stops():
    """unique_journey_stop constraint must survive the index cleanup."""
    table_args = getattr(JourneyStop, "__table_args__", ())
    constraints = [
        arg for arg in table_args if isinstance(arg, UniqueConstraint)
    ]
    names = {c.name for c in constraints}
    assert "unique_journey_stop" in names, (
        f"unique_journey_stop constraint missing from JourneyStop"
    )


def test_unique_constraint_preserved_on_service_alerts():
    """uq_service_alert_id constraint must survive the index cleanup."""
    table_args = getattr(ServiceAlert, "__table_args__", ())
    constraints = [
        arg for arg in table_args if isinstance(arg, UniqueConstraint)
    ]
    names = {c.name for c in constraints}
    assert "uq_service_alert_id" in names


def test_no_dropped_index_appears_in_any_model():
    """Cross-check: none of the 11 dropped indexes appear in any model."""
    all_models = [
        JourneyStop,
        JourneySnapshot,
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
        assert not overlap, (
            f"{model.__name__} still has dropped indexes: {overlap}"
        )


def test_migration_drops_exactly_eleven_indexes():
    """Verify the migration upgrade function drops exactly 11 indexes."""
    migration = importlib.import_module(
        "trackrat.db.migrations.versions."
        "20260423_1749-d170389c0848_drop_unused_indexes"
    )
    assert migration.revision == "d170389c0848"
    assert migration.down_revision == "6feb0d5b5600"

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


def test_migration_does_not_drop_track_occupancy_lookup():
    """idx_track_occupancy_lookup must NOT be in the migration drop list."""
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

    assert "idx_track_occupancy_lookup" not in calls, (
        "Migration must NOT drop idx_track_occupancy_lookup; "
        "it is actively used by track_occupancy.py"
    )


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
    assert len(calls) == 11, (
        f"Expected 11 create_index calls, got {len(calls)}"
    )
