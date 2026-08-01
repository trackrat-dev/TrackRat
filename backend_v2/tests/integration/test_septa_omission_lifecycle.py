"""PostgreSQL coverage for SEPTA presence and omission reconciliation."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.septa_common import reconcile_journey_omissions
from trackrat.models.database import TrainJourney
from trackrat.utils.time import ET


def _journey(data_source: str, train_id: str, **overrides) -> TrainJourney:
    departure = ET.localize(datetime.combine(date.today(), datetime.min.time()))
    values = {
        "train_id": train_id,
        "journey_date": date.today(),
        "line_code": "SEPTA-TEST",
        "line_name": "SEPTA Test",
        "line_color": "#4F758B",
        "destination": "Destination",
        "origin_station_code": "ORIGIN",
        "terminal_station_code": "TERMINAL",
        "data_source": data_source,
        "observation_type": "OBSERVED",
        "scheduled_departure": departure,
        "scheduled_arrival": departure + timedelta(hours=1),
        "api_error_count": 0,
        "is_expired": False,
        "is_completed": False,
        "is_cancelled": False,
    }
    values.update(overrides)
    return TrainJourney(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("data_source", ["SEPTA_METRO", "SEPTA_RR"])
async def test_reconciliation_persists_lifecycle_policy(
    db_session: AsyncSession, data_source: str
) -> None:
    recovering = _journey(data_source, "recovering", api_error_count=3, is_expired=True)
    streak = _journey(data_source, "streak", api_error_count=2)
    interrupted = _journey(data_source, "interrupted", api_error_count=1)
    completed = _journey(
        data_source,
        "completed",
        api_error_count=3,
        is_expired=True,
        is_completed=True,
    )
    cancelled = _journey(
        data_source,
        "cancelled",
        api_error_count=3,
        is_expired=True,
        is_cancelled=True,
    )
    unrelated_expiry = _journey(
        data_source, "unrelated", api_error_count=1, is_expired=True
    )
    previous_day_same_number = _journey(
        data_source,
        "recovering",
        journey_date=date.today() - timedelta(days=1),
        api_error_count=1,
    )
    unresolved_previous_day = _journey(
        data_source,
        "unresolved",
        journey_date=date.today() - timedelta(days=1),
        api_error_count=1,
    )
    db_session.add_all(
        [
            recovering,
            streak,
            interrupted,
            completed,
            cancelled,
            unrelated_expiry,
            previous_day_same_number,
            unresolved_previous_day,
        ]
    )
    await db_session.commit()

    expired = await reconcile_journey_omissions(
        db_session,
        data_source,
        date.today(),
        {
            ("recovering", date.today()),
            ("interrupted", date.today()),
            ("completed", date.today()),
            ("cancelled", date.today()),
            ("unrelated", date.today()),
        },
        {"unresolved"},
    )
    await db_session.commit()

    assert expired == 1
    assert recovering.api_error_count == 0
    assert recovering.is_expired is False
    assert streak.api_error_count == 3
    assert streak.is_expired is True
    assert interrupted.api_error_count == 0
    assert interrupted.is_expired is False
    assert completed.api_error_count == 3
    assert completed.is_expired is True
    assert cancelled.api_error_count == 3
    assert cancelled.is_expired is True
    assert unrelated_expiry.api_error_count == 0
    assert unrelated_expiry.is_expired is True
    assert previous_day_same_number.api_error_count == 2
    assert previous_day_same_number.is_expired is False
    assert unresolved_previous_day.api_error_count == 1
    assert unresolved_previous_day.is_expired is False

    await reconcile_journey_omissions(
        db_session, data_source, date.today(), {("interrupted", date.today())}
    )
    await db_session.commit()

    assert interrupted.api_error_count == 0
    await reconcile_journey_omissions(db_session, data_source, date.today(), set())
    await db_session.commit()
    assert interrupted.api_error_count == 1
    assert interrupted.is_expired is False
