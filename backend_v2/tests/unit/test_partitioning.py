"""
Tests for the journey_stops / segment_transit_times partition management
helpers (issue #1343).

Pure unit tests of the SQL-generation and date-math logic — no database
required. See tests/integration/test_journey_stops_partitioning.py for
tests that exercise real Postgres partition creation, insert routing,
cascade delete, and partition dropping.
"""

from datetime import date

import pytest

from trackrat.db.partitioning import (
    MONTHS_BACK,
    PARTITIONED_TABLES,
    PartitionedTable,
    create_default_partition_sql,
    create_partition_sql,
    default_partition_name,
    get_partitioned_table,
    initial_setup_sql,
    month_end_exclusive,
    month_start,
    months_back_for_retention,
    partition_name,
    rolling_window_sql,
)


class TestMonthArithmetic:
    def test_month_start(self):
        assert month_start(2026, 7) == date(2026, 7, 1)

    def test_month_end_exclusive_mid_year(self):
        assert month_end_exclusive(2026, 7) == date(2026, 8, 1)

    def test_month_end_exclusive_year_rollover(self):
        assert month_end_exclusive(2026, 12) == date(2027, 1, 1)

    def test_month_start_january(self):
        assert month_start(2026, 1) == date(2026, 1, 1)


class TestPartitionNaming:
    def test_partition_name_format(self):
        assert partition_name("journey_stops", 2026, 7) == "journey_stops_y2026_m07"

    def test_partition_name_pads_single_digit_month(self):
        assert partition_name("journey_stops", 2026, 1) == "journey_stops_y2026_m01"

    def test_default_partition_name(self):
        assert default_partition_name("journey_stops") == "journey_stops_default"


class TestCreatePartitionSql:
    def test_date_column_bounds_have_no_time_component(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        sql = create_partition_sql(pt, 2026, 7)
        assert "FROM ('2026-07-01') TO ('2026-08-01')" in sql
        assert "journey_stops_y2026_m07" in sql
        assert "PARTITION OF journey_stops" in sql
        assert "CREATE TABLE IF NOT EXISTS" in sql

    def test_timestamptz_column_bounds_have_explicit_utc_offset(self):
        pt = PartitionedTable("segment_transit_times", "departure_time", "timestamptz")
        sql = create_partition_sql(pt, 2026, 7)
        assert "FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00')" in sql

    def test_year_rollover_partition(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        sql = create_partition_sql(pt, 2026, 12)
        assert "FROM ('2026-12-01') TO ('2027-01-01')" in sql

    def test_default_partition_sql(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        sql = create_default_partition_sql(pt)
        assert sql == (
            "CREATE TABLE IF NOT EXISTS journey_stops_default "
            "PARTITION OF journey_stops DEFAULT"
        )


class TestRollingWindowSql:
    def test_default_window_size(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        statements = rolling_window_sql(pt, date(2026, 7, 15))
        # 1 default + (1 back + current + 2 forward) = 5 statements
        assert len(statements) == 5
        assert any("journey_stops_default" in s for s in statements)
        assert any("journey_stops_y2026_m06" in s for s in statements)  # back
        assert any("journey_stops_y2026_m07" in s for s in statements)  # current
        assert any("journey_stops_y2026_m08" in s for s in statements)  # forward
        assert any("journey_stops_y2026_m09" in s for s in statements)  # forward

    def test_window_crosses_year_boundary(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        statements = rolling_window_sql(pt, date(2026, 12, 15))
        assert any("journey_stops_y2026_m11" in s for s in statements)
        assert any("journey_stops_y2026_m12" in s for s in statements)
        assert any("journey_stops_y2027_m01" in s for s in statements)
        assert any("journey_stops_y2027_m02" in s for s in statements)

    def test_custom_window_size(self):
        pt = PartitionedTable("journey_stops", "journey_date", "date")
        statements = rolling_window_sql(
            pt, date(2026, 7, 15), months_back=0, months_forward=0
        )
        # 1 default + current month only
        assert len(statements) == 2


class TestMonthsBackForRetention:
    """The migration's back-window must cover the whole retention horizon, or
    the one-time legacy backfill spills its oldest rows into DEFAULT (issue
    #1343 follow-up: 60-day retention with a 1-month back-window dumped ~26 days
    of May journey_stops into journey_stops_default on staging)."""

    def test_month_start_60_days_reaches_two_months_back(self):
        # 2026-07-04 - 60d = 2026-05-05 -> May is 2 buckets back from July.
        assert months_back_for_retention(date(2026, 7, 4), 60) == 2

    def test_month_end_60_days_reaches_one_month_back(self):
        # 2026-07-31 - 60d = 2026-06-01 -> June is 1 bucket back from July.
        assert months_back_for_retention(date(2026, 7, 31), 60) == 1

    def test_spans_three_calendar_months(self):
        # 2026-07-01 - 60d = 2026-05-02: window touches May, June, July.
        assert months_back_for_retention(date(2026, 7, 1), 60) == 2

    def test_year_boundary(self):
        # 2026-01-15 - 60d = 2025-11-16 -> Nov 2025 is 2 buckets back from Jan.
        assert months_back_for_retention(date(2026, 1, 15), 60) == 2

    def test_long_retention_reaches_further_back(self):
        # 2026-07-04 - 120d = 2026-03-06 -> March is 4 buckets back from July.
        assert months_back_for_retention(date(2026, 7, 4), 120) == 4

    def test_short_retention_floored_at_months_back(self):
        # 2026-07-15 - 5d = 2026-07-10: same month (0), floored to the
        # steady-state minimum so boundary late-writes still have last month.
        assert months_back_for_retention(date(2026, 7, 15), 5) == MONTHS_BACK

    def test_min_retention_30_days(self):
        # 2026-07-15 - 30d = 2026-06-15 -> June is 1 bucket back.
        assert months_back_for_retention(date(2026, 7, 15), 30) == 1


class TestInitialSetupSql:
    def test_covers_every_managed_table(self):
        statements = initial_setup_sql(date(2026, 7, 15))
        for pt in PARTITIONED_TABLES:
            assert any(pt.name in s for s in statements)

    def test_statement_count_matches_table_count(self):
        # 5 statements per table (1 default + 4 dated) with default window
        statements = initial_setup_sql(date(2026, 7, 15))
        assert len(statements) == 5 * len(PARTITIONED_TABLES)

    def test_default_window_omits_two_months_back(self):
        # Regression guard: the steady-state (default) window must NOT reach two
        # months back — that was the bug for the migration path, but the daily
        # top-up must stay narrow to avoid creating a back-partition over a
        # DEFAULT that already holds matching rows (which errors in Postgres).
        statements = initial_setup_sql(date(2026, 7, 4))
        assert not any("journey_stops_y2026_m05" in s for s in statements)

    def test_retention_aware_window_includes_oldest_in_retention_month(self):
        # Migration path: with 60-day retention on 2026-07-04, a May partition
        # must exist so backfilled May rows don't land in DEFAULT.
        months_back = months_back_for_retention(date(2026, 7, 4), 60)
        statements = initial_setup_sql(date(2026, 7, 4), months_back=months_back)
        assert any(
            "journey_stops_y2026_m05" in s and "('2026-05-01') TO ('2026-06-01')" in s
            for s in statements
        )
        assert any(
            "segment_transit_times_y2026_m05" in s for s in statements
        )


class TestGetPartitionedTable:
    def test_known_tables(self):
        assert get_partitioned_table("journey_stops").partition_column == "journey_date"
        assert (
            get_partitioned_table("segment_transit_times").partition_column
            == "departure_time"
        )

    def test_unknown_table_raises(self):
        with pytest.raises(KeyError):
            get_partitioned_table("not_a_real_table")
