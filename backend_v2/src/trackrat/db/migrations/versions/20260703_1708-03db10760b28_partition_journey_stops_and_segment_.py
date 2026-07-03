"""partition journey_stops and segment_transit_times by month

Issue #1343: `journey_stops` (~33 GB, ~70% of journey-table storage) and
`segment_transit_times` are pruned by retention via `DELETE` (cascading from
`train_journeys`), which marks tuples dead but never returns space to the
filesystem — `VACUUM FULL`/`pg_repack` need free space roughly equal to the
table size to rewrite it in place, which production doesn't have.

This migration does NOT touch the existing ~33 GB of data — no backfill, no
table rewrite, no long-running scan. (A prior backfill migration, f7a8b9c0d1e2,
was reverted because it took too long on large tables and caused MIG health
check failures; this migration is designed to avoid that entirely.) Instead:

1. Rename the existing tables to `*_legacy` (instant, metadata-only). Their
   `ON DELETE CASCADE` FK from train_journeys follows the table through the
   rename, so retention_cleanup's existing batched DELETE keeps draining them
   exactly as before — no code change needed for the legacy data. Once fully
   drained (`retention_days`, default 60 days), an operator can `DROP TABLE`
   them to reclaim the remaining space in one shot.
2. Create new, empty tables under the original names, partitioned by month
   (RANGE on `journey_date` / `departure_time`). All new writes land here.
   Retention can then `DROP TABLE` an aged-out partition directly instead of
   relying on DELETE + autovacuum.
3. Bootstrap a rolling partition window (previous/current/+2 months) plus a
   DEFAULT catch-all partition for each table.

`journey_stops` gains a `journey_date` column (denormalized from
`train_journeys.journey_date`) because Postgres requires every unique/primary
key constraint on a partitioned table to include the partition key column;
`unique_journey_stop` becomes `(journey_id, station_code, journey_date)`
(equivalent to before since journey_date is functionally determined by
journey_id). `segment_transit_times` already had a NOT NULL `departure_time`
column, so no new column is needed there.

Revision ID: 03db10760b28
Revises: fd85e7f3abb3
Create Date: 2026-07-03 17:08:39.489186

"""

from datetime import date

from alembic import op

from trackrat.db.partitioning import initial_setup_sql

# revision identifiers, used by Alembic.
revision = "03db10760b28"
down_revision = "fd85e7f3abb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename existing tables — instant, metadata-only. Their FK to
    # train_journeys (ON DELETE CASCADE) follows the table through the
    # rename, so retention_cleanup keeps draining them unchanged.
    op.execute("ALTER TABLE journey_stops RENAME TO journey_stops_legacy")
    op.execute(
        "ALTER TABLE segment_transit_times RENAME TO segment_transit_times_legacy"
    )

    # Table/sequence renames don't rename dependent constraint, index, or
    # sequence objects — they're independently-named catalog objects. Free
    # up the original names (reused below by the new partitioned tables) by
    # renaming them out of the way on the legacy tables first.
    op.execute(
        "ALTER SEQUENCE journey_stops_id_seq RENAME TO journey_stops_legacy_id_seq"
    )
    op.execute(
        "ALTER TABLE journey_stops_legacy RENAME CONSTRAINT journey_stops_pkey "
        "TO journey_stops_legacy_pkey"
    )
    op.execute(
        "ALTER TABLE journey_stops_legacy RENAME CONSTRAINT unique_journey_stop "
        "TO unique_journey_stop_legacy"
    )
    op.execute(
        "ALTER TABLE journey_stops_legacy RENAME CONSTRAINT "
        "journey_stops_journey_id_fkey TO journey_stops_legacy_journey_id_fkey"
    )
    for index_name in (
        "idx_station_times",
        "idx_journey_stops_sequence_lookup",
        "idx_stop_track_distribution",
        "idx_stop_delay_forecaster",
        "idx_stop_journey_station_seq",
    ):
        op.execute(f"ALTER INDEX {index_name} RENAME TO {index_name}_legacy")

    op.execute(
        "ALTER SEQUENCE segment_transit_times_id_seq "
        "RENAME TO segment_transit_times_legacy_id_seq"
    )
    op.execute(
        "ALTER TABLE segment_transit_times_legacy RENAME CONSTRAINT "
        "segment_transit_times_pkey TO segment_transit_times_legacy_pkey"
    )
    op.execute(
        "ALTER TABLE segment_transit_times_legacy RENAME CONSTRAINT "
        "segment_transit_times_journey_id_fkey "
        "TO segment_transit_times_legacy_journey_id_fkey"
    )
    for index_name in (
        "idx_segment_journey",
        "idx_segment_lookup",
        "idx_recent_segments",
        "idx_segment_baseline",
    ):
        op.execute(f"ALTER INDEX {index_name} RENAME TO {index_name}_legacy")
    # idx_segment_hour_baseline is a leftover from 062a92685e12, superseded by
    # idx_segment_baseline (fdc1bcf576de) and already absent from the ORM
    # model — left as-is on the legacy table; not recreated on the new one.

    # 2. Create the new partitioned journey_stops table.
    op.execute("""
        CREATE TABLE journey_stops (
            id SERIAL NOT NULL,
            journey_id INTEGER NOT NULL REFERENCES train_journeys(id) ON DELETE CASCADE,
            journey_date DATE NOT NULL,
            station_code VARCHAR(10) NOT NULL,
            station_name VARCHAR(100) NOT NULL,
            stop_sequence INTEGER,
            scheduled_arrival TIMESTAMP WITH TIME ZONE,
            scheduled_departure TIMESTAMP WITH TIME ZONE,
            updated_arrival TIMESTAMP WITH TIME ZONE,
            updated_departure TIMESTAMP WITH TIME ZONE,
            actual_arrival TIMESTAMP WITH TIME ZONE,
            actual_departure TIMESTAMP WITH TIME ZONE,
            raw_amtrak_status VARCHAR(50),
            raw_njt_departed_flag VARCHAR(10),
            has_departed_station BOOLEAN NOT NULL DEFAULT false,
            departure_source VARCHAR(30),
            arrival_source VARCHAR(30),
            track VARCHAR(5),
            track_assigned_at TIMESTAMP WITH TIME ZONE,
            pickup_only BOOLEAN NOT NULL DEFAULT false,
            dropoff_only BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            PRIMARY KEY (id, journey_date),
            CONSTRAINT unique_journey_stop UNIQUE (journey_id, station_code, journey_date)
        ) PARTITION BY RANGE (journey_date)
        """)
    op.execute(
        "CREATE INDEX idx_station_times ON journey_stops "
        "(station_code, scheduled_departure)"
    )
    op.execute(
        "CREATE INDEX idx_journey_stops_sequence_lookup ON journey_stops "
        "(journey_id, stop_sequence, station_code) "
        "INCLUDE (scheduled_departure, scheduled_arrival, actual_departure, actual_arrival)"
    )
    op.execute(
        "CREATE INDEX idx_stop_track_distribution ON journey_stops (station_code, track)"
    )
    op.execute(
        "CREATE INDEX idx_stop_delay_forecaster ON journey_stops (station_code, journey_id)"
    )
    op.execute(
        "CREATE INDEX idx_stop_journey_station_seq ON journey_stops "
        "(journey_id, station_code, stop_sequence)"
    )

    # 3. Create the new partitioned segment_transit_times table.
    op.execute("""
        CREATE TABLE segment_transit_times (
            id SERIAL NOT NULL,
            journey_id INTEGER NOT NULL REFERENCES train_journeys(id) ON DELETE CASCADE,
            from_station_code VARCHAR(10) NOT NULL,
            to_station_code VARCHAR(10) NOT NULL,
            data_source VARCHAR(10) NOT NULL,
            line_code VARCHAR(15),
            scheduled_minutes INTEGER NOT NULL,
            actual_minutes INTEGER NOT NULL,
            delay_minutes INTEGER NOT NULL,
            departure_time TIMESTAMP WITH TIME ZONE NOT NULL,
            hour_of_day INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id, departure_time)
        ) PARTITION BY RANGE (departure_time)
        """)
    op.execute("CREATE INDEX idx_segment_journey ON segment_transit_times (journey_id)")
    op.execute(
        "CREATE INDEX idx_segment_lookup ON segment_transit_times "
        "(from_station_code, to_station_code, data_source, departure_time)"
    )
    op.execute(
        "CREATE INDEX idx_recent_segments ON segment_transit_times "
        "(from_station_code, to_station_code, created_at)"
    )
    op.execute(
        "CREATE INDEX idx_segment_baseline ON segment_transit_times "
        "(data_source, hour_of_day, day_of_week, departure_time)"
    )

    # 4. Bootstrap the rolling partition window (previous/current/+2 months)
    # plus a DEFAULT catch-all partition for each table.
    for statement in initial_setup_sql(date.today()):
        op.execute(statement)


def downgrade() -> None:
    # Dropping a partitioned parent drops all its partitions in one step.
    op.execute("DROP TABLE journey_stops")
    op.execute("DROP TABLE segment_transit_times")

    op.execute("ALTER TABLE journey_stops_legacy RENAME TO journey_stops")
    op.execute(
        "ALTER SEQUENCE journey_stops_legacy_id_seq RENAME TO journey_stops_id_seq"
    )
    op.execute(
        "ALTER TABLE journey_stops RENAME CONSTRAINT journey_stops_legacy_pkey "
        "TO journey_stops_pkey"
    )
    op.execute(
        "ALTER TABLE journey_stops RENAME CONSTRAINT unique_journey_stop_legacy "
        "TO unique_journey_stop"
    )
    op.execute(
        "ALTER TABLE journey_stops RENAME CONSTRAINT "
        "journey_stops_legacy_journey_id_fkey TO journey_stops_journey_id_fkey"
    )
    for index_name in (
        "idx_station_times",
        "idx_journey_stops_sequence_lookup",
        "idx_stop_track_distribution",
        "idx_stop_delay_forecaster",
        "idx_stop_journey_station_seq",
    ):
        op.execute(f"ALTER INDEX {index_name}_legacy RENAME TO {index_name}")

    op.execute(
        "ALTER TABLE segment_transit_times_legacy RENAME TO segment_transit_times"
    )
    op.execute(
        "ALTER SEQUENCE segment_transit_times_legacy_id_seq "
        "RENAME TO segment_transit_times_id_seq"
    )
    op.execute(
        "ALTER TABLE segment_transit_times RENAME CONSTRAINT "
        "segment_transit_times_legacy_pkey TO segment_transit_times_pkey"
    )
    op.execute(
        "ALTER TABLE segment_transit_times RENAME CONSTRAINT "
        "segment_transit_times_legacy_journey_id_fkey "
        "TO segment_transit_times_journey_id_fkey"
    )
    for index_name in (
        "idx_segment_journey",
        "idx_segment_lookup",
        "idx_recent_segments",
        "idx_segment_baseline",
    ):
        op.execute(f"ALTER INDEX {index_name}_legacy RENAME TO {index_name}")
