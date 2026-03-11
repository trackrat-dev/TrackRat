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
        actual_arrival = stop_data.get("actual_arrival")
        stop = JourneyStop(
            journey_id=journey.id,
            station_code=stop_data["station_code"],
            station_name=stop_data.get("station_name", stop_data["station_code"]),
            stop_sequence=stop_data.get("stop_sequence", i),
            scheduled_departure=stop_data.get("scheduled_departure"),
            actual_departure=stop_data.get("actual_departure"),
            scheduled_arrival=stop_data.get("scheduled_arrival"),
            actual_arrival=actual_arrival,
            arrival_source=stop_data.get(
                "arrival_source", "api_observed" if actual_arrival else None
            ),
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

    async def test_empty_journeys_returns_nulls_for_arrival_metrics(
        self, db_session: AsyncSession
    ):
        result = await _run_stats(db_session)

        assert result["total_journeys"] == 0
        assert result["on_time_percentage"] is None, (
            "on_time_percentage should be None when no arrival data exists, "
            "not 0.0 which would misleadingly suggest all trains are late"
        )
        assert (
            result["average_delay_minutes"] is None
        ), "average_delay_minutes should be None when no arrival data exists"
        assert result["average_departure_delay_minutes"] == 0.0
        assert result["cancellation_rate"] == 0.0
        assert (
            result["delay_breakdown"] is None
        ), "delay_breakdown should be None when no arrival data exists"
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
    """Verify arrival delay is calculated at the destination station (to_codes)."""

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

    async def test_arrival_delay_at_destination_not_last_stop(
        self, db_session: AsyncSession
    ):
        """Arrival delay should be measured at the to_station, not the train's final stop.

        A train NY -> TR -> HAM should measure arrival delay at TR (the to_station),
        not HAM (the train's final stop). This tests the fix for the bug where
        last_stops CTE picked the highest stop_sequence regardless of to_codes.
        """
        await _create_journey(
            db_session,
            train_id="train_continues_past",
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
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=3),
                },
                {
                    "station_code": "HAM",
                    "stop_sequence": 2,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1, minutes=30),
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=50),
                },
            ],
        )
        await db_session.commit()

        # to_codes=["TR"], so arrival delay should be 3 min (at TR), not 20 min (at HAM)
        result = await _run_stats(db_session)
        assert abs(result["average_delay_minutes"] - 3.0) < 0.1, (
            f"Expected 3.0m (delay at TR), got {result['average_delay_minutes']}. "
            "Arrival delay should be measured at the destination station, not the last stop."
        )


@pytest.mark.asyncio
class TestOnTimePercentageDenominator:
    """Verify on_time_percentage only counts trains with arrival data in denominator.

    This was the root cause of the '71% on-time but 0m avg delay' bug: trains
    without actual_arrival data were included in the denominator, deflating the
    on-time percentage while average delay (correctly) excluded them.
    """

    async def test_trains_without_arrival_data_excluded_from_denominator(
        self, db_session: AsyncSession
    ):
        """5 trains with arrival data (all on-time), 2 without = should be 100%, not 71%.

        Before the fix: on_time_count=5, non_cancelled=7 -> 71%
        After the fix:  on_time_count=5, with_arrival_data=5 -> 100%
        """
        # 5 trains with arrival data, all on-time
        for i in range(5):
            await _create_journey(
                db_session,
                train_id=f"train_with_data_{i}",
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
                        "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=2),
                    },
                ],
            )
        # 2 trains without arrival data (still in progress)
        for i in range(2):
            await _create_journey(
                db_session,
                train_id=f"train_no_arrival_{i}",
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
                        "actual_arrival": None,
                    },
                ],
            )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert result["total_journeys"] == 7
        assert result["on_time_percentage"] == 100.0, (
            f"Expected 100% (5/5 trains with data are on-time), got "
            f"{result['on_time_percentage']}%. Trains without arrival data "
            "should not be counted in the denominator."
        )
        # Average delay should also be very small (2 min, clamped positive)
        assert result["average_delay_minutes"] < 3.0

    async def test_delay_breakdown_sums_to_100(self, db_session: AsyncSession):
        """Delay breakdown percentages should sum to ~100% when trains have mixed delays."""
        delays = [2, 10, 25, 45]  # on_time, slight, significant, major
        for i, delay in enumerate(delays):
            await _create_journey(
                db_session,
                train_id=f"train_mix_{i}",
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
                        "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=delay),
                    },
                ],
            )
        # Add one train without arrival data (should not affect breakdown)
        await _create_journey(
            db_session,
            train_id="train_no_data",
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
                    "actual_arrival": None,
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)
        breakdown = result["delay_breakdown"]
        total_pct = (
            breakdown["on_time"]
            + breakdown["slight"]
            + breakdown["significant"]
            + breakdown["major"]
        )
        assert 98 <= total_pct <= 102, (
            f"Delay breakdown should sum to ~100%, got {total_pct}%: {breakdown}. "
            "Each category should be 25% (1 of 4 trains with data)."
        )
        # Each category should be 25% (1 of 4 trains with data)
        assert breakdown["on_time"] == 25
        assert breakdown["slight"] == 25
        assert breakdown["significant"] == 25
        assert breakdown["major"] == 25


@pytest.mark.asyncio
class TestNoArrivalDataReturnsNull:
    """Verify metrics are null (not zero) when no non-cancelled trains have arrival data.

    Reproduces the bug where a route with cancelled trains and in-progress trains
    showed 0% on-time and 0m delay, which misleadingly looked like all trains
    were late when in reality there was simply no arrival data yet.
    """

    async def test_cancelled_plus_in_progress_returns_null_metrics(
        self, db_session: AsyncSession
    ):
        """1 cancelled train + 1 departed-but-not-arrived train = null arrival metrics.

        This is the exact scenario reported: Trenton to NY Penn shows 0% on-time
        and 0m delay when trains are cancelled and remaining haven't arrived yet.
        """
        # Cancelled train
        await _create_journey(
            db_session,
            train_id="cancelled_train",
            is_cancelled=True,
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                },
            ],
        )
        # In-progress train: has departed but no arrival data yet
        await _create_journey(
            db_session,
            train_id="in_progress_train",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": BASE_TIME,
                    "actual_departure": BASE_TIME + timedelta(seconds=20),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": BASE_TIME + timedelta(hours=1),
                    "actual_arrival": None,
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert result["total_journeys"] == 2
        assert result["cancellation_rate"] == 50.0

        # Arrival-based metrics must be None, not 0
        assert result["on_time_percentage"] is None, (
            f"on_time_percentage should be None when no trains have arrival data, "
            f"got {result['on_time_percentage']}. Showing 0% misleads users into "
            "thinking all trains are late when there's simply no data yet."
        )
        assert result["average_delay_minutes"] is None, (
            f"average_delay_minutes should be None when no trains have arrival data, "
            f"got {result['average_delay_minutes']}. Showing 0m misleads users."
        )
        assert result["delay_breakdown"] is None, (
            f"delay_breakdown should be None when no arrival data exists, "
            f"got {result['delay_breakdown']}."
        )

        # Departure delay should still work (in-progress train has actual_departure)
        assert (
            result["average_departure_delay_minutes"] >= 0
        ), "Departure delay should still be computed for trains that have departed"

    async def test_all_cancelled_returns_null_metrics(self, db_session: AsyncSession):
        """When all trains are cancelled, arrival metrics should be null."""
        for i in range(3):
            await _create_journey(
                db_session,
                train_id=f"all_cancelled_{i}",
                is_cancelled=True,
                stops=[
                    {
                        "station_code": "NY",
                        "stop_sequence": 0,
                        "scheduled_departure": BASE_TIME + timedelta(minutes=i * 30),
                    },
                    {
                        "station_code": "TR",
                        "stop_sequence": 1,
                        "scheduled_arrival": BASE_TIME
                        + timedelta(hours=1, minutes=i * 30),
                    },
                ],
            )
        await db_session.commit()

        result = await _run_stats(db_session)

        assert result["total_journeys"] == 3
        assert result["cancellation_rate"] == 100.0
        assert result["on_time_percentage"] is None
        assert result["average_delay_minutes"] is None
        assert result["delay_breakdown"] is None


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


@pytest.mark.asyncio
class TestArrivalSourceFiltering:
    """Verify OTP excludes stops with scheduled_fallback arrival_source.

    This prevents inflated OTP from PATH/MTA collectors that fall back to
    scheduled_arrival when no real-time data is available (issue #585).
    """

    async def test_scheduled_fallback_excluded_from_otp(self, db_session: AsyncSession):
        """Stops with arrival_source='scheduled_fallback' should not count toward OTP.

        3 trains: 2 with api_observed arrivals (1 on-time, 1 late),
        1 with scheduled_fallback (appears on-time but is fake data).
        OTP should be 50% (1/2), not 67% (2/3).
        """
        # Train 1: api_observed, on-time
        await _create_journey(
            db_session,
            train_id="train_real_ontime",
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
                    "actual_arrival": BASE_TIME + timedelta(hours=1, minutes=2),
                    "arrival_source": "api_observed",
                },
            ],
        )
        # Train 2: api_observed, late (8 min)
        await _create_journey(
            db_session,
            train_id="train_real_late",
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
                    "arrival_source": "api_observed",
                },
            ],
        )
        # Train 3: scheduled_fallback, appears on-time (but is fake)
        await _create_journey(
            db_session,
            train_id="train_fallback",
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
                    "arrival_source": "scheduled_fallback",
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        # Only 2 trains should count toward OTP (the api_observed ones)
        assert result["on_time_percentage"] == 50.0, (
            f"Expected 50% (1/2 api_observed trains on-time), got "
            f"{result['on_time_percentage']}%. scheduled_fallback arrivals "
            "should be excluded from OTP calculation."
        )
        # Average delay should be from real data only: (2 + 8) / 2 = 5.0
        assert abs(result["average_delay_minutes"] - 5.0) < 0.1, (
            f"Expected 5.0m avg delay from real data, got "
            f"{result['average_delay_minutes']}m"
        )

    async def test_null_arrival_source_excluded_from_otp(
        self, db_session: AsyncSession
    ):
        """Historical data with NULL arrival_source should be excluded from OTP.

        This ensures a safe ramp-up: old data without the field populated
        doesn't inflate OTP while new data with proper tagging accumulates.
        """
        await _create_journey(
            db_session,
            train_id="train_legacy",
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
                    "arrival_source": None,
                },
            ],
        )
        await db_session.commit()

        result = await _run_stats(db_session)

        # Train has actual_arrival but NULL arrival_source -> excluded from OTP.
        # With no api_observed arrivals, the endpoint returns None (not 0.0)
        # to avoid misleading "0% on-time" displays.
        assert result["on_time_percentage"] is None, (
            f"Expected None (no api_observed arrivals), got "
            f"{result['on_time_percentage']}. NULL arrival_source should "
            "be excluded from OTP, yielding null metrics."
        )


@pytest.mark.asyncio
class TestCutoffTimeFiltersByArrival:
    """Verify hours-based cutoff filters by destination ARRIVAL time, not origin departure.

    This was a major bug: "last hour" stats filtered by scheduled_departure at the
    origin station. Since most trains that departed in the last hour haven't arrived yet,
    the stats would show "N/A" for on_time_percentage and average_delay_minutes.

    The fix filters by the destination stop's arrival time (actual or scheduled), so
    "last hour" means "trains that arrived at the destination in the last hour".
    """

    async def _run_stats_with_cutoff(
        self,
        db: AsyncSession,
        cutoff_time: datetime,
        now: datetime,
        from_codes: list[str] | None = None,
        to_codes: list[str] | None = None,
    ) -> dict:
        """Helper to call _calculate_route_stats_sql with a cutoff_time."""
        return await _calculate_route_stats_sql(
            db=db,
            data_source="NJT",
            start_date=cutoff_time.date(),
            end_date=now.date(),
            from_codes=from_codes or ["NY"],
            to_codes=to_codes or ["TR"],
            cutoff_time=cutoff_time,
            now=now,
        )

    async def test_recently_arrived_train_included_in_last_hour(
        self, db_session: AsyncSession
    ):
        """A train that arrived 30 minutes ago should appear in 'last hour' stats.

        Train departed 1.5 hours ago (outside the 1-hour window) but arrived
        30 minutes ago (inside the window). With the old departure-based filter,
        this train would be excluded. With the arrival-based filter, it's included.
        """
        now = BASE_TIME + timedelta(hours=3)
        cutoff = now - timedelta(hours=1)

        await _create_journey(
            db_session,
            train_id="train_arrived_recently",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": now - timedelta(hours=1, minutes=30),
                    "actual_departure": now - timedelta(hours=1, minutes=30),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": now - timedelta(minutes=30),
                    "actual_arrival": now - timedelta(minutes=25),
                    "arrival_source": "api_observed",
                },
            ],
        )
        await db_session.commit()

        result = await self._run_stats_with_cutoff(db_session, cutoff, now)

        assert result["total_journeys"] == 1, (
            f"Expected 1 journey (arrived 30min ago, within 1h window), "
            f"got {result['total_journeys']}. The cutoff should filter by "
            "destination arrival time, not origin departure time."
        )
        assert result["on_time_percentage"] is not None, (
            "on_time_percentage should not be N/A for a train that already arrived"
        )

    async def test_recently_departed_but_not_arrived_excluded(
        self, db_session: AsyncSession
    ):
        """A train that departed 30 minutes ago but hasn't arrived should NOT appear.

        With the old filter this train would be included (departed within the hour)
        but produce N/A stats since it has no arrival data. With the new filter,
        it's correctly excluded because it hasn't arrived yet.
        """
        now = BASE_TIME + timedelta(hours=3)
        cutoff = now - timedelta(hours=1)

        await _create_journey(
            db_session,
            train_id="train_still_en_route",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": now - timedelta(minutes=30),
                    "actual_departure": now - timedelta(minutes=30),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": now + timedelta(minutes=30),
                    "actual_arrival": None,
                },
            ],
        )
        await db_session.commit()

        result = await self._run_stats_with_cutoff(db_session, cutoff, now)

        assert result["total_journeys"] == 0, (
            f"Expected 0 journeys (train hasn't arrived yet, scheduled_arrival "
            f"is in the future), got {result['total_journeys']}. Trains still "
            "en route should not be included in arrival-based stats."
        )

    async def test_train_arrived_before_cutoff_excluded(
        self, db_session: AsyncSession
    ):
        """A train that arrived 2 hours ago should NOT appear in 'last hour' stats."""
        now = BASE_TIME + timedelta(hours=4)
        cutoff = now - timedelta(hours=1)

        await _create_journey(
            db_session,
            train_id="train_arrived_long_ago",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": now - timedelta(hours=3),
                    "actual_departure": now - timedelta(hours=3),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": now - timedelta(hours=2),
                    "actual_arrival": now - timedelta(hours=2),
                    "arrival_source": "api_observed",
                },
            ],
        )
        await db_session.commit()

        result = await self._run_stats_with_cutoff(db_session, cutoff, now)

        assert result["total_journeys"] == 0, (
            f"Expected 0 journeys (arrived 2h ago, outside 1h window), "
            f"got {result['total_journeys']}."
        )

    async def test_cutoff_uses_actual_arrival_over_scheduled(
        self, db_session: AsyncSession
    ):
        """When actual_arrival exists, it should be used for the cutoff filter.

        Train scheduled to arrive 70 minutes ago (outside window) but actually
        arrived 40 minutes ago (inside window due to delay). Should be included.
        """
        now = BASE_TIME + timedelta(hours=4)
        cutoff = now - timedelta(hours=1)

        await _create_journey(
            db_session,
            train_id="train_late_but_recent",
            stops=[
                {
                    "station_code": "NY",
                    "stop_sequence": 0,
                    "scheduled_departure": now - timedelta(hours=2),
                    "actual_departure": now - timedelta(hours=2),
                },
                {
                    "station_code": "TR",
                    "stop_sequence": 1,
                    "scheduled_arrival": now - timedelta(minutes=70),
                    "actual_arrival": now - timedelta(minutes=40),
                    "arrival_source": "api_observed",
                },
            ],
        )
        await db_session.commit()

        result = await self._run_stats_with_cutoff(db_session, cutoff, now)

        assert result["total_journeys"] == 1, (
            f"Expected 1 journey (actual_arrival 40min ago is within 1h window, "
            f"even though scheduled_arrival was 70min ago), got {result['total_journeys']}. "
            "COALESCE(actual_arrival, scheduled_arrival) should prefer actual."
        )

    async def test_no_cutoff_includes_all_journeys(self, db_session: AsyncSession):
        """When cutoff_time is None (days-based query), all journeys are included."""
        for i in range(3):
            await _create_journey(
                db_session,
                train_id=f"train_no_cutoff_{i}",
                stops=[
                    {
                        "station_code": "NY",
                        "stop_sequence": 0,
                        "scheduled_departure": BASE_TIME + timedelta(hours=i),
                        "actual_departure": BASE_TIME + timedelta(hours=i),
                    },
                    {
                        "station_code": "TR",
                        "stop_sequence": 1,
                        "scheduled_arrival": BASE_TIME + timedelta(hours=i + 1),
                        "actual_arrival": BASE_TIME + timedelta(hours=i + 1),
                        "arrival_source": "api_observed",
                    },
                ],
            )
        await db_session.commit()

        # No cutoff = all journeys included (the _run_stats default)
        result = await _run_stats(db_session)
        assert result["total_journeys"] == 3
