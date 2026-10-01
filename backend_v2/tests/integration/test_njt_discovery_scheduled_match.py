"""
Integration tests for NJT discovery's SCHEDULED-row merge
(TrainDiscoveryCollector._find_matching_scheduled_train) against real Postgres.

The destination comparison is a SQL twin of ``normalize_njt_destination``
(``regexp_replace`` with the shared patterns), so only a real database can
show the two sides agree. Issue #1839: the real-time feed reported NJCL
train 3227 to "Long Branch -SEC &#9992" while the schedule API's row for the
same train (4070) said "LONG BRANCH"; the merge missed and the board showed
both, one as "Train TBD".
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et

DEPARTURE = ET.localize(datetime(2026, 10, 1, 8, 46))


def _make_scheduled_journey(*, train_id: str, destination: str) -> TrainJourney:
    """SCHEDULED NJCL journey as the schedule collector stores it."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=DEPARTURE.date(),
        data_source="NJT",
        observation_type="SCHEDULED",
        line_code="NC",
        line_name="North Jersey Coast Line",
        line_color="#03A3DF",
        destination=destination,
        origin_station_code="NY",
        terminal_station_code="LB",
        scheduled_departure=DEPARTURE,
        first_seen_at=now_et(),
        last_updated_at=now_et(),
        has_complete_journey=True,
        update_count=0,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            scheduled_departure=DEPARTURE,
            stop_sequence=0,
            has_departed_station=False,
        ),
        JourneyStop(
            station_code="LB",
            station_name="Long Branch",
            scheduled_arrival=DEPARTURE + timedelta(minutes=95),
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


@pytest.fixture
async def collector() -> AsyncGenerator[TrainDiscoveryCollector, None]:
    # The NJT client is never called by _find_matching_scheduled_train.
    client = NJTransitClient()
    try:
        yield TrainDiscoveryCollector(client)
    finally:
        await client.close()


async def _find(
    collector: TrainDiscoveryCollector, db_session: AsyncSession, destination: str
) -> TrainJourney | None:
    return await collector._find_matching_scheduled_train(
        session=db_session,
        station_code="NY",
        destination=destination,
        scheduled_departure=DEPARTURE,
        journey_date=DEPARTURE.date(),
    )


@pytest.mark.asyncio
async def test_sec_marker_destination_matches_schedule_row(
    collector: TrainDiscoveryCollector, db_session: AsyncSession
) -> None:
    """Real-time 'Long Branch -SEC &#9992' finds the 'LONG BRANCH' schedule row."""
    db_session.add(_make_scheduled_journey(train_id="4070", destination="LONG BRANCH"))
    await db_session.commit()

    match = await _find(collector, db_session, "Long Branch -SEC &#9992")

    print(f"match: {match and (match.train_id, match.destination)}")
    assert match is not None, "SEC-marked real-time destination did not match"
    assert match.train_id == "4070"


@pytest.mark.asyncio
async def test_sec_marker_on_stored_destination_matches(
    collector: TrainDiscoveryCollector, db_session: AsyncSession
) -> None:
    """The SQL side strips the marker too, if a stored row carries it."""
    db_session.add(
        _make_scheduled_journey(train_id="4070", destination="Long Branch -SEC &#9992")
    )
    await db_session.commit()

    match = await _find(collector, db_session, "Long Branch")

    print(f"match: {match and (match.train_id, match.destination)}")
    assert match is not None, "SEC-marked stored destination did not match"
    assert match.train_id == "4070"


@pytest.mark.asyncio
async def test_transit_center_suffix_still_matches(
    collector: TrainDiscoveryCollector, db_session: AsyncSession
) -> None:
    """Regression guard for #1329 after nesting the SQL normalization."""
    db_session.add(
        _make_scheduled_journey(
            train_id="4070", destination="LONG BRANCH TRANSIT CENTER"
        )
    )
    await db_session.commit()

    match = await _find(collector, db_session, "Long Branch -SEC &#9992")

    print(f"match: {match and (match.train_id, match.destination)}")
    assert match is not None
    assert match.train_id == "4070"


@pytest.mark.asyncio
async def test_different_destination_does_not_match(
    collector: TrainDiscoveryCollector, db_session: AsyncSession
) -> None:
    """Stripping the marker must not make distinct termini compare equal."""
    db_session.add(_make_scheduled_journey(train_id="4100", destination="BAY HEAD"))
    await db_session.commit()

    match = await _find(collector, db_session, "Long Branch -SEC &#9992")

    print(f"match: {match and (match.train_id, match.destination)}")
    assert match is None
