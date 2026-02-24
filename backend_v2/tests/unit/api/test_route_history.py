"""
Tests for the route history endpoint statistics calculations.

Tests _calculate_route_stats_sql to verify:
- Cancellation rate is returned as a percentage (0-100), not a fraction
- Departure delay is calculated at the origin station
- Arrival delay is calculated at the destination station
- Delay categories are correctly assigned
- Empty journey lists return zero defaults
- Track usage counts at origin station only

These tests require a PostgreSQL test database because the stats calculation
is now done via SQL aggregation (no ORM object loading).
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.api.routes import _calculate_route_stats_sql
from trackrat.models.database import JourneyStop, TrainJourney

BASE_TIME = datetime(2025, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
BASE_DATE = date(2025, 6, 15)


async def _create_journey(
    db: AsyncSession,
    train_id: str,
    stops: list[dict],
    is_cancelled: bool = False,
    data_source: str = "NJT",
) -> TrainJourney:
    """Create a real TrainJourney with JourneyStop records in the database."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=BASE_DATE,
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code=stops[0]["station_code"],
        terminal_station_code=stops[-1]["station_code"],
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=stops[0].get("scheduled_departure", BASE_TIME),
        is_cancelled=is_cancelled,
        has_complete_journey=True,
        stops_count=len(stops),
    )
    db.add(journey)
    await db.flush()

    for i, stop_data in enumerate(stops):
        stop = JourneyStop(
            journey_id=journey.id,
            station_code=stop_data["station_code"],
            station_name=stop_data.get("station_name", stop_data["station_code"]),
            stop_sequence=stop_data.get("stop_sequence", i),
            scheduled_departure=stop_data.get("scheduled_departure"),
            actual_departure=stop_data.get("actual_departure"),
            scheduled_arrival=stop_data.get("scheduled_arrival"),
            actual_arrival=stop_data.get("actual_arrival"),
            track=stop_data.get("track"),
        )
        db.add(stop)

    await db.flush()
    return journey


async def _run_stats(
    db: AsyncSession,
    from_codes: list[str] | None = None,
    to_codes: list[str] | None = None,
    train_id_filter: str | None = None,
) -> dict:
    """Helper to call _calculate_route_stats_sql with common defaults."""
    return await _calculate_route_stats_sql(
        db=db,
        data_source="NJT",
        start_date=BASE_DATE - timedelta(days=1),
        end_date=BASE_DATE + timedelta(days=1),
        from_codes=from_codes or ["NY"],
        to_codes=to_codes or ["TR"],
        cutoff_time=None,
        now=BASE_TIME + timedelta(hours=2),
        train_id_filter=train_id_filter,
    )


@pytest.mark.asyncio
class TestCalculateRouteStatsEmpty:
    """Verify correct defaults when no journeys match."""

    async def test_empty_journeys_returns_zeros(self, db_session: AsyncSession):
        result = await _run_stats(db_session)

        assert result["total_journeys"] == 0
        assert result["on_time_percentage"] == 0.0
        assert result["average_delay_minutes"] == 0.0
        assert result["average_departure_delay_minutes"] == 0.0
        assert result["cancellation_rate"] == 0.0
        assert result["delay_breakdown"] == {
            "on_time": 0,
            "slight": 0,
            "significant": 0,
            "major": 0,
        }
        assert result["track_usage"] == {}


@pytest.mark.asyncio
class TestCancellationRate:
    """Verify cancellation_rate is a percentage (0-100), not a fraction (0-1).

    This was the root cause of the iOS '1009% Cancelled' bug - the backend
    returns a percentage but iOS multiplied by 100 again.
    """

    async def test_cancellation_rate_is_percentage(self, db_session: AsyncSession):
        """10 journeys, 2 cancelled = 20% (not 0.2)."""
        for i in range(10):
            await _create_journey(
                db_session,
                train_id=f"train_{i}",
                stops=[
                    {
                        "station_code": "NY",
                        "stop_sequence": 0,
                        "scheduled_departure": BASE_TIME,
                        "actual_departure": BASE_TIME,
                    },
                    {
                        "station_code": "TR",
                        "stop_sequence": 1,
                        "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                        "actual_arrival": BASE_TIME + timedelta(hours=1),
                    },
                ],
                is_cancelled=(i < 2),
            )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert result["cancellation_rate"] == 20.0, (
            f"Expected 20.0% but got {result['cancellation_rate']}. "
            "cancellation_rate should be a percentage (0-100)."
        )

    async def test_zero_cancellation_rate(self, db_session: AsyncSession):
        """All trains running = 0% cancelled."""
        await _create_journey(
            db_session,
            train_id="train_ok",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["cancellation_rate"] == 0.0

    async def test_full_cancellation_rate(self, db_session: AsyncSession):
        """All trains cancelled = 100%."""
        await _create_journey(
            db_session,
            train_id="train_cancelled",
            stops=[
                {"station_code": "NY", "stop_sequence": 0},
                {"station_code": "TR", "stop_sequence": 1},
            ],
            is_cancelled=True,
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["cancellation_rate"] == 100.0


@pytest.mark.asyncio
class TestDepartureDelay:
    """Verify departure delay is calculated at the origin station."""

    async def test_departure_delay_at_origin(self, db_session: AsyncSession):
        """Train departs 10 minutes late from origin."""
        await _create_journey(
            db_session,
            train_id="train_late",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME + timedelta(minutes=10),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=5),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert (
            abs(result["average_departure_delay_minutes"] - 10.0) < 0.1
        ), f"Expected 10m departure delay, got {result['average_departure_delay_minutes']}"
        assert (
            abs(result["average_delay_minutes"] - 5.0) < 0.1
        ), f"Expected 5m arrival delay, got {result['average_delay_minutes']}"

    async def test_departure_delay_only_at_specified_origin(
        self, db_session: AsyncSession
    ):
        """Departure delay uses the from_codes parameter, not just the first stop."""
        await _create_journey(
            db_session,
            train_id="train_se_ny",
            stops=[
                {
                    "station_code": "SE",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME - timedelta(minutes=30),
                    "actual_departure": BASE_TIME - timedelta(minutes=20),
                },
                {
                    "station_code": "NY",
                    "stop_sequence": 1,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME + timedelta(minutes=3),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 2,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        # Should use NY departure delay (3min), not SE (10min)
        assert abs(result["average_departure_delay_minutes"] - 3.0) < 0.1

    async def test_departure_delay_zero_when_on_time(self, db_session: AsyncSession):
        """Train departs on time = 0 delay."""
        await _create_journey(
            db_session,
            train_id="train_ontime",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["average_departure_delay_minutes"] == 0.0

    async def test_departure_delay_average_across_journeys(
        self, db_session: AsyncSession
    ):
        """Average departure delay across multiple trains."""
        for i, delay_mins in enumerate([0, 5, 10, 15]):
            await _create_journey(
                db_session,
                train_id=f"train_avg_{i}",
                stops=[
                    {
                        "station_code": "NY",
                        "stop_sequence": 0,
                        "scheduled_departure": BASE_TIME,
                        "actual_departure": BASE_TIME + timedelta(minutes=delay_mins),
                    },
                    {
                        "station_code": "TR",
                        "stop_sequence": 1,
                        "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                        "actual_arrival": BASE_TIME + timedelta(hours=1),
                    },
                ],
            )
        await db_session.commit()

        result = await _run_stats(db_session)
        # Average of 0, 5, 10, 15 = 7.5
        assert abs(result["average_departure_delay_minutes"] - 7.5) < 0.1

    async def test_departure_delay_excludes_no_actual(self, db_session: AsyncSession):
        """When actual_departure is missing, departure delay is not counted."""
        await _create_journey(
            db_session,
            train_id="train_no_actual",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": None,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["average_departure_delay_minutes"] == 0.0

    async def test_departure_delay_excludes_cancelled_trains(
        self, db_session: AsyncSession
    ):
        """Cancelled trains must not affect departure delay average."""
        # Non-cancelled train: 5 min late
        await _create_journey(
            db_session,
            train_id="train_normal",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME + timedelta(minutes=5),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        # Cancelled train: 20 min late at origin
        await _create_journey(
            db_session,
            train_id="train_cancelled",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME + timedelta(minutes=20),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": None,
                },
            ],
            is_cancelled=True,
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert abs(result["average_departure_delay_minutes"] - 5.0) < 0.1, (
            f"Expected 5.0 (non-cancelled only), got {result['average_departure_delay_minutes']}. "
            "Cancelled trains should be excluded from departure delay calculation."
        )
        assert result["cancellation_rate"] == 50.0


@pytest.mark.asyncio
class TestArrivalDelay:
    """Verify arrival delay is calculated at the last stop (destination)."""

    async def test_arrival_delay_at_destination(self, db_session: AsyncSession):
        """Train arrives 8 minutes late at the destination."""
        await _create_journey(
            db_session,
            train_id="train_arr_late",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=8),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert abs(result["average_delay_minutes"] - 8.0) < 0.1


@pytest.mark.asyncio
class TestDelayCategories:
    """Verify delay breakdown buckets match documented thresholds."""

    async def test_on_time_threshold(self, db_session: AsyncSession):
        """5 minutes or less = on_time."""
        await _create_journey(
            db_session,
            train_id="train_cat_ontime",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=5),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["delay_breakdown"]["on_time"] == 100

    async def test_slight_delay_threshold(self, db_session: AsyncSession):
        """6-15 minutes = slight."""
        await _create_journey(
            db_session,
            train_id="train_cat_slight",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=10),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["delay_breakdown"]["slight"] == 100

    async def test_significant_delay_threshold(self, db_session: AsyncSession):
        """16-30 minutes = significant."""
        await _create_journey(
            db_session,
            train_id="train_cat_sig",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=25),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["delay_breakdown"]["significant"] == 100

    async def test_major_delay_threshold(self, db_session: AsyncSession):
        """Over 30 minutes = major."""
        await _create_journey(
            db_session,
            train_id="train_cat_major",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=45),
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["delay_breakdown"]["major"] == 100


@pytest.mark.asyncio
class TestTrackUsage:
    """Verify track usage is counted at origin station only."""

    async def test_track_usage_at_origin(self, db_session: AsyncSession):
        await _create_journey(
            db_session,
            train_id="train_track",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                    "track": "5",
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                    "track": "3",
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["track_usage"] == {"5": 100}

    async def test_track_usage_ignores_destination(self, db_session: AsyncSession):
        """Track at destination should not appear in track_usage."""
        await _create_journey(
            db_session,
            train_id="train_no_orig_track",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": BASE_TIME + timedelta(hours=1),
                    "track": "7",
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        assert result["track_usage"] == {}
