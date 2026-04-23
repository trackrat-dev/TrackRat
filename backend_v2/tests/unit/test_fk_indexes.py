"""
Tests that foreign key columns used in selectinload have corresponding indexes.

Without indexes on journey_id in segment_transit_times and station_dwell_times,
SQLAlchemy's selectinload causes sequential scans on these large tables —
13M+ rows for segment_transit_times and 75k+ for station_dwell_times.

See: GitHub issue #985
"""

from sqlalchemy import inspect as sa_inspect

from trackrat.models.database import (
    SegmentTransitTime,
    StationDwellTime,
    TrainJourney,
)


def _get_index_columns(model):
    """Return a set of tuples, each being the column list of an index."""
    indexes = set()
    for idx in model.__table__.indexes:
        indexes.add(tuple(col.name for col in idx.columns))
    return indexes


def test_segment_transit_times_has_journey_id_index():
    """segment_transit_times must have an index on journey_id.

    This column is a foreign key to train_journeys.id and is used by
    selectinload(TrainJourney.segment_times) on every departure and
    train detail request. Without it, Postgres does a sequential scan
    on a 13M+ row table.
    """
    index_columns = _get_index_columns(SegmentTransitTime)
    journey_id_indexed = any(
        cols[0] == "journey_id" for cols in index_columns
    )
    assert journey_id_indexed, (
        "segment_transit_times is missing an index with journey_id as the "
        "leading column. This causes sequential scans on selectinload. "
        f"Current indexes: {index_columns}"
    )


def test_station_dwell_times_has_journey_id_index():
    """station_dwell_times must have an index on journey_id.

    Same issue as segment_transit_times — selectinload(TrainJourney.dwell_times)
    needs this index to avoid sequential scans.
    """
    index_columns = _get_index_columns(StationDwellTime)
    journey_id_indexed = any(
        cols[0] == "journey_id" for cols in index_columns
    )
    assert journey_id_indexed, (
        "station_dwell_times is missing an index with journey_id as the "
        "leading column. This causes sequential scans on selectinload. "
        f"Current indexes: {index_columns}"
    )


def test_all_selectinload_fk_tables_have_journey_id_index():
    """Every table related to TrainJourney via selectinload should have
    an index on journey_id.

    This is a broader check: inspect all relationships on TrainJourney
    that use lazy='raise_on_sql' (meaning they're always eager-loaded),
    and verify each target table has journey_id indexed.
    """
    mapper = sa_inspect(TrainJourney)
    missing = []

    for rel in mapper.relationships:
        if rel.lazy != "raise_on_sql":
            continue

        target_table = rel.entity.entity.__table__
        has_journey_id_col = "journey_id" in [c.name for c in target_table.columns]
        if not has_journey_id_col:
            continue

        has_index = any(
            tuple(c.name for c in idx.columns)[0] == "journey_id"
            for idx in target_table.indexes
        )
        if not has_index:
            missing.append(target_table.name)

    assert not missing, (
        f"Tables related to TrainJourney via selectinload are missing "
        f"an index on journey_id: {missing}. Without this index, "
        f"selectinload causes sequential scans."
    )


def test_migration_index_names_match_model():
    """Verify the index names in the model match what the migration creates."""
    segment_idx_names = {idx.name for idx in SegmentTransitTime.__table__.indexes}
    assert "idx_segment_journey" in segment_idx_names, (
        f"Expected idx_segment_journey in SegmentTransitTime indexes, "
        f"got: {segment_idx_names}"
    )

    dwell_idx_names = {idx.name for idx in StationDwellTime.__table__.indexes}
    assert "idx_dwell_journey" in dwell_idx_names, (
        f"Expected idx_dwell_journey in StationDwellTime indexes, "
        f"got: {dwell_idx_names}"
    )
