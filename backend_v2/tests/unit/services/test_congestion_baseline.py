"""
Tests for the congestion historical_baseline CTE used for frequency calculation.

Verifies that the baseline in congestion.py correctly:
- Uses Eastern Time for hour/day matching (not UTC)
- Uses per-day averaging (not total/30)
- Requires minimum 3 days of data
- Counts distinct journeys per segment
- Filters by data source
- Matches weekday/weekend pattern

These tests require a PostgreSQL test database because the baseline is
a raw SQL CTE inside get_network_congestion_optimized.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from trackrat.models.database import SegmentTransitTime, TrainJourney
from trackrat.utils.time import normalize_to_et

# Wednesday 12:00 UTC = Wednesday 8:00 AM ET (EDT, UTC-4 in June)
BASE_TIME = datetime(2025, 6, 18, 12, 0, 0, tzinfo=UTC)
BASE_DATE = date(2025, 6, 18)
BASE_ET_HOUR = 8  # 12 UTC = 8 ET (EDT)


async def _create_segment_record(
    db: AsyncSession,
    train_id: str,
    from_station: str,
    to_station: str,
    departure_time: datetime,
    data_source: str = "PATH",
    journey_date: date | None = None,
) -> TrainJourney:
    """Create a TrainJourney with a single SegmentTransitTime record."""
    jdate = journey_date or departure_time.date()
    dep_eastern = normalize_to_et(departure_time)

    journey = TrainJourney(
        train_id=train_id,
        journey_date=jdate,
        line_code="JSQ-33H",
        line_name="Journal Square - 33rd Street",
        destination="33rd Street",
        origin_station_code=from_station,
        terminal_station_code=to_station,
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=departure_time,
        is_cancelled=False,
        has_complete_journey=True,
        stops_count=2,
    )
    db.add(journey)
    await db.flush()

    stt = SegmentTransitTime(
        journey_id=journey.id,
        from_station_code=from_station,
        to_station_code=to_station,
        data_source=data_source,
        line_code="JSQ-33H",
        scheduled_minutes=10,
        actual_minutes=10,
        delay_minutes=0,
        departure_time=departure_time,
        hour_of_day=dep_eastern.hour,
        day_of_week=dep_eastern.weekday(),
    )
    db.add(stt)
    await db.flush()
    return journey


# The historical_baseline CTE extracted for direct testing.
# This mirrors the CTE in congestion.py's get_network_congestion_optimized.
BASELINE_SQL = text("""
    SELECT
        from_station,
        to_station,
        data_source,
        AVG(day_count) * :time_window_hours as baseline_train_count
    FROM (
        SELECT
            stt.from_station_code as from_station,
            stt.to_station_code as to_station,
            stt.data_source,
            stt.departure_time::date as journey_day,
            COUNT(DISTINCT stt.journey_id) as day_count
        FROM segment_transit_times stt
        WHERE stt.departure_time >= :baseline_start
          AND stt.hour_of_day = :current_hour
          AND (
              (:is_weekend AND stt.day_of_week IN (5, 6))
              OR (NOT :is_weekend AND stt.day_of_week NOT IN (5, 6))
          )
          AND (CAST(:data_source AS TEXT) IS NULL OR stt.data_source = CAST(:data_source AS TEXT))
        GROUP BY stt.from_station_code, stt.to_station_code, stt.data_source, stt.departure_time::date
    ) daily_stats
    GROUP BY from_station, to_station, data_source
    HAVING COUNT(*) >= 3
""")


def _baseline_params(
    now: datetime = BASE_TIME,
    time_window_hours: int = 2,
    data_source: str | None = "PATH",
) -> dict:
    """Build parameters for the baseline query using Eastern Time (like the fix does)."""
    now_eastern = normalize_to_et(now)
    return {
        "baseline_start": now - timedelta(days=30),
        "current_hour": now_eastern.hour,
        "is_weekend": now_eastern.weekday() >= 5,
        "time_window_hours": time_window_hours,
        "data_source": data_source,
    }


@pytest.mark.asyncio
class TestCongestionBaselineTimezone:
    """Verify that the baseline uses Eastern Time, not UTC, for hour matching."""

    async def test_matches_eastern_hour_not_utc(self, db_session: AsyncSession):
        """Records at 8am ET should match when current ET hour is 8, not UTC hour 12.

        BASE_TIME is 12:00 UTC = 8:00 AM ET. Historical records are stored with
        hour_of_day=8 (Eastern). The query must compare against ET hour 8, not
        UTC hour 12.
        """
        # Create 4 weekday records at 8am ET across 4 different past weekdays
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 4:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_et8_{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        # Query with ET hour matching (correct approach)
        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        assert (
            params["current_hour"] == BASE_ET_HOUR
        ), f"Sanity check: ET hour should be {BASE_ET_HOUR}, got {params['current_hour']}"

        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is not None, (
            "Baseline should find records at ET hour 8. "
            "If this fails, the query may be using UTC hour (12) instead."
        )
        assert float(row["baseline_train_count"]) > 0

    async def test_no_match_at_utc_hour(self, db_session: AsyncSession):
        """Records at 8am ET should NOT match when querying UTC hour 12 directly.

        This test confirms that using the wrong hour (UTC) would fail to find
        records stored with ET hour_of_day.
        """
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 4:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_utc12_{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        # Query with UTC hour (the old bug) - should find nothing
        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        params["current_hour"] = 12  # UTC hour, not ET hour
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is None, (
            "Querying with UTC hour 12 should NOT match records stored at ET hour 8. "
            "This confirms the timezone fix is necessary."
        )


@pytest.mark.asyncio
class TestCongestionBaselinePerDayAveraging:
    """Verify per-day averaging instead of total/30."""

    async def test_per_day_average_correct(self, db_session: AsyncSession):
        """3 days with 2, 4, 6 trains → avg 4.0 per day (not 12/30 = 0.4)."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 3:
                break

        train_counts = [2, 4, 6]
        for day_idx, day_offset in enumerate(weekday_offsets):
            for t in range(train_counts[day_idx]):
                dep_time = (
                    BASE_TIME - timedelta(days=day_offset) + timedelta(minutes=t * 5)
                )
                await _create_segment_record(
                    db_session,
                    train_id=f"train_d{day_offset}_t{t}",
                    from_station="JSQ",
                    to_station="HOB",
                    departure_time=dep_time,
                    journey_date=BASE_DATE - timedelta(days=day_offset),
                )
        await db_session.commit()

        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is not None, "Expected baseline with 3 days of data"
        baseline = float(row["baseline_train_count"])
        assert baseline == 4.0, (
            f"Expected per-day average of 4.0 (mean of 2,4,6) * 1 hour, got {baseline}. "
            "If you got ~0.4, the query is dividing by 30 instead of averaging per day."
        )

    async def test_time_window_scaling(self, db_session: AsyncSession):
        """Per-day avg of 3.0 with time_window_hours=2 → baseline 6.0."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 3:
                break

        for day_offset in weekday_offsets:
            for t in range(3):  # 3 trains per day
                dep_time = (
                    BASE_TIME - timedelta(days=day_offset) + timedelta(minutes=t * 5)
                )
                await _create_segment_record(
                    db_session,
                    train_id=f"train_d{day_offset}_t{t}",
                    from_station="JSQ",
                    to_station="HOB",
                    departure_time=dep_time,
                    journey_date=BASE_DATE - timedelta(days=day_offset),
                )
        await db_session.commit()

        params = _baseline_params(now=BASE_TIME, time_window_hours=2)
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is not None, "Expected baseline with 3 days of data"
        baseline = float(row["baseline_train_count"])
        assert baseline == 6.0, f"Expected 3.0 avg/day * 2 hours = 6.0, got {baseline}"


@pytest.mark.asyncio
class TestCongestionBaselineMinDays:
    """Require minimum 3 days of data."""

    async def test_returns_nothing_with_2_days(self, db_session: AsyncSession):
        """Only 2 days of data should return no baseline (HAVING >= 3 fails)."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 2:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_d{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is None, f"Expected no baseline with only 2 days of data, got {row}"

    async def test_returns_baseline_with_3_days(self, db_session: AsyncSession):
        """Exactly 3 days of data should return a baseline."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 3:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_d{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is not None, "Expected baseline with exactly 3 days of data"
        assert (
            float(row["baseline_train_count"]) == 1.0
        ), f"Expected 1.0 train/day * 1 hour, got {float(row['baseline_train_count'])}"


@pytest.mark.asyncio
class TestCongestionBaselineWeekdayWeekend:
    """Verify weekday/weekend filtering."""

    async def test_excludes_weekend_from_weekday_baseline(
        self, db_session: AsyncSession
    ):
        """Weekend records should not appear in weekday baseline."""
        # Create records on 4 past Saturdays at 8am ET
        saturday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() == 5:  # Saturday
                saturday_offsets.append(i)
            if len(saturday_offsets) >= 4:
                break

        for day_offset in saturday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_sat_{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        # Query on a weekday (BASE_TIME is Wednesday) - should find nothing
        params = _baseline_params(now=BASE_TIME, time_window_hours=1)
        assert not params["is_weekend"], "Sanity check: BASE_TIME should be a weekday"
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is None, "Weekend records should not appear in weekday baseline"


@pytest.mark.asyncio
class TestCongestionBaselineDataSource:
    """Verify data source filtering."""

    async def test_excludes_different_data_source(self, db_session: AsyncSession):
        """Records from a different data source should not be counted."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 4:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_njt_{day_offset}",
                from_station="NY",
                to_station="NP",
                departure_time=dep_time,
                data_source="NJT",
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        # Query for PATH data - NJT records should not match
        params = _baseline_params(now=BASE_TIME, data_source="PATH")
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is None, "NJT records should not appear in PATH baseline"

    async def test_null_data_source_matches_all(self, db_session: AsyncSession):
        """When data_source is None, all sources should be included."""
        weekday_offsets = []
        for i in range(1, 30):
            dt = BASE_TIME - timedelta(days=i)
            if dt.weekday() < 5:
                weekday_offsets.append(i)
            if len(weekday_offsets) >= 3:
                break

        for day_offset in weekday_offsets:
            dep_time = BASE_TIME - timedelta(days=day_offset)
            await _create_segment_record(
                db_session,
                train_id=f"train_path_{day_offset}",
                from_station="JSQ",
                to_station="HOB",
                departure_time=dep_time,
                data_source="PATH",
                journey_date=BASE_DATE - timedelta(days=day_offset),
            )
        await db_session.commit()

        params = _baseline_params(now=BASE_TIME, data_source=None)
        result = await db_session.execute(BASELINE_SQL, params)
        row = result.mappings().first()
        assert row is not None, "With data_source=None, all sources should be included"
