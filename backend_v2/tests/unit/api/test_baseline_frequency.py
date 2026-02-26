"""
Tests for the baseline train count calculation used for frequency coloring.

Tests _calculate_baseline_train_count to verify:
- Returns None when no historical segment data exists
- Correctly counts distinct journeys for 1-hour window (same hour + day type)
- Correctly counts distinct journeys for 24-hour window (same day type only)
- Correctly counts distinct journeys for 7-day window (no time/day filter)
- Only counts journeys that match both from and to stations
- Does not count journeys from different data sources

These tests require a PostgreSQL test database because the baseline calculation
uses raw SQL against segment_transit_times.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.api.routes import _calculate_baseline_train_count
from trackrat.models.database import SegmentTransitTime, TrainJourney
from trackrat.utils.time import normalize_to_et

# Wednesday 8am ET = Wednesday 13:00 UTC (ET is UTC-5 in winter)
BASE_TIME = datetime(
    2025, 6, 18, 12, 0, 0, tzinfo=timezone.utc
)  # Wednesday 8am ET (EDT)
BASE_DATE = date(2025, 6, 18)


async def _create_journey_with_segments(
    db: AsyncSession,
    train_id: str,
    segments: list[dict],
    data_source: str = "NJT",
    journey_date: date | None = None,
) -> TrainJourney:
    """Create a TrainJourney with SegmentTransitTime records."""
    jdate = journey_date or BASE_DATE
    journey = TrainJourney(
        train_id=train_id,
        journey_date=jdate,
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code=segments[0]["from_station"],
        terminal_station_code=segments[-1]["to_station"],
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=segments[0]["departure_time"],
        is_cancelled=False,
        has_complete_journey=True,
        stops_count=len(segments) + 1,
    )
    db.add(journey)
    await db.flush()

    for seg in segments:
        dep_time = seg["departure_time"]
        dep_eastern = normalize_to_et(dep_time)
        stt = SegmentTransitTime(
            journey_id=journey.id,
            from_station_code=seg["from_station"],
            to_station_code=seg["to_station"],
            data_source=data_source,
            line_code="NE",
            scheduled_minutes=seg.get("scheduled_minutes", 15),
            actual_minutes=seg.get("actual_minutes", 15),
            delay_minutes=seg.get("delay_minutes", 0),
            departure_time=dep_time,
            hour_of_day=dep_eastern.hour,
            day_of_week=dep_eastern.weekday(),
        )
        db.add(stt)

    await db.flush()
    return journey


@pytest.mark.asyncio
class TestBaselineNoData:
    """Returns None when no segment data exists."""

    async def test_returns_none_when_empty(self, db_session: AsyncSession):
        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert result is None, "Expected None when no historical segment data"


@pytest.mark.asyncio
class TestBaselineOneHour:
    """1-hour window: matches same hour-of-day and weekday/weekend."""

    async def test_counts_matching_journeys(self, db_session: AsyncSession):
        """30 journeys at hour 8 on weekdays over 30 days → baseline ~1.0."""
        for i in range(30):
            day_offset = i
            dep_time = BASE_TIME - timedelta(days=day_offset)
            # Skip weekends
            if dep_time.weekday() >= 5:
                continue
            await _create_journey_with_segments(
                db_session,
                train_id=f"train_{i}",
                segments=[
                    {
                        "from_station": "NY",
                        "to_station": "NP",
                        "departure_time": dep_time,
                    },
                    {
                        "from_station": "NP",
                        "to_station": "TR",
                        "departure_time": dep_time + timedelta(minutes=15),
                    },
                ],
                journey_date=(BASE_DATE - timedelta(days=day_offset)),
            )
        await db_session.commit()

        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert result is not None, "Expected a baseline value"
        assert result > 0, f"Expected positive baseline, got {result}"

    async def test_excludes_different_hour(self, db_session: AsyncSession):
        """Journey at a different hour should not be counted for 1-hour baseline."""
        # Create journey at hour 15 (3pm), but query at hour 8
        dep_time = BASE_TIME - timedelta(days=7) + timedelta(hours=7)  # 3pm
        await _create_journey_with_segments(
            db_session,
            train_id="train_wrong_hour",
            segments=[
                {"from_station": "NY", "to_station": "NP", "departure_time": dep_time},
                {
                    "from_station": "NP",
                    "to_station": "TR",
                    "departure_time": dep_time + timedelta(minutes=15),
                },
            ],
            journey_date=(BASE_DATE - timedelta(days=7)),
        )
        await db_session.commit()

        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert result is None, "Journey at different hour should not be counted"

    async def test_excludes_weekend_when_querying_weekday(
        self, db_session: AsyncSession
    ):
        """Weekend journeys should not appear in weekday 1-hour baseline."""
        # Create journey on a Saturday at the same hour
        # BASE_TIME is Wednesday; Saturday is 3 days later
        saturday = BASE_TIME + timedelta(days=3)
        saturday_date = BASE_DATE + timedelta(days=3)
        # But we need it within the past 30 days - use a past Saturday
        past_saturday = BASE_TIME - timedelta(days=4)  # Previous Saturday
        past_saturday_date = BASE_DATE - timedelta(days=4)

        await _create_journey_with_segments(
            db_session,
            train_id="train_weekend",
            segments=[
                {
                    "from_station": "NY",
                    "to_station": "NP",
                    "departure_time": past_saturday,
                },
                {
                    "from_station": "NP",
                    "to_station": "TR",
                    "departure_time": past_saturday + timedelta(minutes=15),
                },
            ],
            journey_date=past_saturday_date,
        )
        await db_session.commit()

        # Query on a weekday (BASE_TIME is Wednesday)
        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert result is None, "Weekend journey should not appear in weekday baseline"


@pytest.mark.asyncio
class TestBaselineTwentyFourHour:
    """24-hour window: matches weekday/weekend but not specific hour."""

    async def test_includes_all_hours_same_day_type(self, db_session: AsyncSession):
        """24-hour baseline should count journeys at any hour on matching day type."""
        # Create journeys at different hours on weekdays
        for hour_offset in [0, 2, 4, 6]:
            dep_time = BASE_TIME - timedelta(days=7) + timedelta(hours=hour_offset)
            await _create_journey_with_segments(
                db_session,
                train_id=f"train_h{hour_offset}",
                segments=[
                    {
                        "from_station": "NY",
                        "to_station": "NP",
                        "departure_time": dep_time,
                    },
                    {
                        "from_station": "NP",
                        "to_station": "TR",
                        "departure_time": dep_time + timedelta(minutes=15),
                    },
                ],
                journey_date=(BASE_DATE - timedelta(days=7)),
            )
        await db_session.commit()

        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=24, now=BASE_TIME
        )
        assert result is not None, "Expected a baseline for 24-hour window"
        assert result > 0, f"Expected positive baseline, got {result}"


@pytest.mark.asyncio
class TestBaselineSevenDay:
    """7-day window (hours=None): no time/day filtering."""

    async def test_includes_all_days_and_hours(self, db_session: AsyncSession):
        """7-day baseline should include all journeys regardless of hour/day."""
        # Create weekend journey at a different hour
        past_saturday = BASE_TIME - timedelta(days=4)
        past_saturday_date = BASE_DATE - timedelta(days=4)
        await _create_journey_with_segments(
            db_session,
            train_id="train_sat",
            segments=[
                {
                    "from_station": "NY",
                    "to_station": "NP",
                    "departure_time": past_saturday,
                },
                {
                    "from_station": "NP",
                    "to_station": "TR",
                    "departure_time": past_saturday + timedelta(minutes=15),
                },
            ],
            journey_date=past_saturday_date,
        )
        await db_session.commit()

        # hours=None means days-based query (7 days)
        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=None, now=BASE_TIME
        )
        assert result is not None, "Expected a baseline for 7-day window"
        assert result > 0, f"Expected positive baseline, got {result}"


@pytest.mark.asyncio
class TestBaselineRouteFiltering:
    """Only counts journeys that match both from and to stations."""

    async def test_excludes_wrong_destination(self, db_session: AsyncSession):
        """Journey from NY to EL (not TR) should not count for NY→TR baseline."""
        dep_time = BASE_TIME - timedelta(days=7)
        await _create_journey_with_segments(
            db_session,
            train_id="train_wrong_dest",
            segments=[
                {"from_station": "NY", "to_station": "NP", "departure_time": dep_time},
                {
                    "from_station": "NP",
                    "to_station": "EL",
                    "departure_time": dep_time + timedelta(minutes=15),
                },
            ],
            journey_date=(BASE_DATE - timedelta(days=7)),
        )
        await db_session.commit()

        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert result is None, "Journey to wrong destination should not be counted"

    async def test_excludes_wrong_data_source(self, db_session: AsyncSession):
        """Journey from a different data source should not be counted."""
        dep_time = BASE_TIME - timedelta(days=7)
        await _create_journey_with_segments(
            db_session,
            train_id="train_amtrak",
            segments=[
                {"from_station": "NY", "to_station": "NP", "departure_time": dep_time},
                {
                    "from_station": "NP",
                    "to_station": "TR",
                    "departure_time": dep_time + timedelta(minutes=15),
                },
            ],
            data_source="AMTRAK",
            journey_date=(BASE_DATE - timedelta(days=7)),
        )
        await db_session.commit()

        result = await _calculate_baseline_train_count(
            db_session, "NJT", ["NY"], ["TR"], hours=1, now=BASE_TIME
        )
        assert (
            result is None
        ), "Journey from different data source should not be counted"
