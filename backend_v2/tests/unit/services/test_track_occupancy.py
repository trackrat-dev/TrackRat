"""
Unit tests for TrackOccupancyService._get_database_tracks.

Issue #1676: a rider reported currently-occupied tracks appearing heavily
weighted in NY Penn track predictions. The old occupancy query counted
"scheduled_departure within the next 2 hours" — which over-included
far-future reservations, and missed both delayed trains (scheduled time
slipped into the past) and trains terminating at the station (no
scheduled_departure at all). These tests pin the corrected semantics:
a track is occupied when a not-yet-departed train's effective departure
(or arrival, for terminating trains) is within the occupancy window
around now.

Runs against the real Postgres test database so the NJT GREATEST() guard
and COALESCE chain are exercised as deployed.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.track_occupancy import (
    OCCUPIED_WINDOW_FUTURE_MINUTES,
    OCCUPIED_WINDOW_PAST_MINUTES,
    TrackOccupancyService,
)
from trackrat.utils.time import now_et

STATION = "NY"


async def _seed_stop(
    db: AsyncSession,
    train_id: str,
    track: str | None,
    *,
    data_source: str = "AMTRAK",
    scheduled_departure: datetime | None = None,
    scheduled_arrival: datetime | None = None,
    updated_departure: datetime | None = None,
    updated_arrival: datetime | None = None,
    actual_arrival: datetime | None = None,
    has_departed_station: bool = False,
    is_cancelled: bool = False,
    terminal_station_code: str = "BOS",
    journey_date: datetime | None = None,
) -> None:
    """Create a journey with a single stop at NY Penn with the given times.

    Pass terminal_station_code=STATION to make the stop a terminal stop
    (the train terminates at NY Penn); the default "BOS" makes it a
    through/origin stop.
    """
    now = now_et()
    journey = TrainJourney(
        train_id=train_id,
        journey_date=(journey_date or now).date(),
        line_code="AM" if data_source == "AMTRAK" else "NE",
        destination="Test Destination",
        origin_station_code="WAS",
        terminal_station_code=terminal_station_code,
        data_source=data_source,
        scheduled_departure=scheduled_departure or scheduled_arrival or now,
        is_cancelled=is_cancelled,
    )
    db.add(journey)
    await db.flush()

    stop = JourneyStop(
        journey_id=journey.id,
        journey_date=journey.journey_date,
        station_code=STATION,
        station_name="New York Penn Station",
        stop_sequence=1,
        scheduled_departure=scheduled_departure,
        scheduled_arrival=scheduled_arrival,
        updated_departure=updated_departure,
        updated_arrival=updated_arrival,
        actual_arrival=actual_arrival,
        track=track,
        has_departed_station=has_departed_station,
    )
    db.add(stop)
    await db.commit()


async def _occupied(db: AsyncSession) -> set[str]:
    service = TrackOccupancyService()
    tracks = await service._get_database_tracks(STATION, db)
    print(f"occupied tracks at {STATION}: {sorted(tracks)}")
    return tracks


@pytest.mark.asyncio
async def test_boarding_train_included(db_session: AsyncSession) -> None:
    """A train departing within the future window is sitting on its track."""
    await _seed_stop(
        db_session,
        "A100",
        "5",
        scheduled_departure=now_et()
        + timedelta(minutes=OCCUPIED_WINDOW_FUTURE_MINUTES - 5),
    )
    assert await _occupied(db_session) == {"5"}


@pytest.mark.asyncio
async def test_far_future_departure_excluded(db_session: AsyncSession) -> None:
    """A track reserved for a departure beyond the boarding window is not
    occupied now — the old 2-hour window wrongly excluded these tracks from
    predictions for trains leaving much sooner."""
    await _seed_stop(
        db_session,
        "A101",
        "6",
        scheduled_departure=now_et()
        + timedelta(minutes=OCCUPIED_WINDOW_FUTURE_MINUTES + 10),
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_delayed_njt_train_included(db_session: AsyncSession) -> None:
    """Regression (#1676): an NJT train scheduled to leave in the past but
    delayed (live estimate in the future, in NJT's inverted TIME/DEP_TIME
    fields) is still on its track. The old query keyed on scheduled_departure
    and silently dropped it from the occupied set."""
    now = now_et()
    await _seed_stop(
        db_session,
        "3900",
        "3",
        data_source="NJT",
        scheduled_departure=now - timedelta(minutes=40),
        # NJT origin semantics: updated_departure carries the live estimate;
        # GREATEST(updated_departure, updated_arrival) must pick it.
        updated_departure=now + timedelta(minutes=5),
        updated_arrival=now - timedelta(minutes=40),
    )
    assert await _occupied(db_session) == {"3"}


@pytest.mark.asyncio
async def test_delayed_train_with_live_estimate_included(
    db_session: AsyncSession,
) -> None:
    """Non-NJT delayed train: live updated_departure in the window wins over
    a scheduled_departure that is already outside the past window."""
    now = now_et()
    await _seed_stop(
        db_session,
        "A102",
        "9",
        scheduled_departure=now - timedelta(minutes=OCCUPIED_WINDOW_PAST_MINUTES + 15),
        updated_departure=now + timedelta(minutes=3),
    )
    assert await _occupied(db_session) == {"9"}


@pytest.mark.asyncio
async def test_recently_due_train_included(db_session: AsyncSession) -> None:
    """A train just past its scheduled departure with no live estimate and no
    departure confirmation is assumed still on the track (within the grace
    window)."""
    await _seed_stop(
        db_session,
        "A103",
        "10",
        scheduled_departure=now_et()
        - timedelta(minutes=OCCUPIED_WINDOW_PAST_MINUTES - 5),
    )
    assert await _occupied(db_session) == {"10"}


@pytest.mark.asyncio
async def test_long_overdue_train_excluded(db_session: AsyncSession) -> None:
    """A train whose only known departure time is far in the past is treated
    as stale data, not a permanent occupation."""
    await _seed_stop(
        db_session,
        "A104",
        "11",
        scheduled_departure=now_et()
        - timedelta(minutes=OCCUPIED_WINDOW_PAST_MINUTES + 10),
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_terminating_train_included(db_session: AsyncSession) -> None:
    """Regression (#1676): a train that terminates at the station (no
    scheduled_departure at all) occupies its track while dwelling after
    arrival. The old query's `scheduled_departure >= now` silently excluded
    every terminating train — a large share of the trains on NY Penn tracks
    at any moment."""
    now = now_et()
    await _seed_stop(
        db_session,
        "A105",
        "14",
        scheduled_arrival=now - timedelta(minutes=10),
        updated_arrival=now - timedelta(minutes=5),
        terminal_station_code=STATION,
    )
    assert await _occupied(db_session) == {"14"}


@pytest.mark.asyncio
async def test_terminal_flagged_departed_on_arrival_included(
    db_session: AsyncSession,
) -> None:
    """Regression (#1677 review): the shared MTA collectors set
    has_departed_station=True the moment a train arrives at its terminal
    (mta_common.update_stop_departure_status paths A/B). The terminal
    branch must ignore that flag — arrival is exactly when the track
    becomes occupied."""
    now = now_et()
    await _seed_stop(
        db_session,
        "L200",
        "16",
        data_source="LIRR",
        scheduled_arrival=now - timedelta(minutes=6),
        actual_arrival=now - timedelta(minutes=5),
        has_departed_station=True,
        terminal_station_code=STATION,
    )
    assert await _occupied(db_session) == {"16"}


@pytest.mark.asyncio
async def test_inbound_terminal_not_occupied_before_arrival(
    db_session: AsyncSession,
) -> None:
    """Regression (#1677 review): a terminating train still inbound (arrival
    estimate in the future) has a track *reservation*, not occupancy — the
    boarding-window future bound applies to departures only."""
    now = now_et()
    await _seed_stop(
        db_session,
        "A113",
        "18",
        scheduled_arrival=now + timedelta(minutes=10),
        updated_arrival=now + timedelta(minutes=10),
        terminal_station_code=STATION,
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_old_terminated_arrival_excluded(db_session: AsyncSession) -> None:
    """A terminating train that arrived well beyond the dwell window has
    presumably moved to the yard."""
    await _seed_stop(
        db_session,
        "A106",
        "15",
        scheduled_arrival=now_et()
        - timedelta(minutes=OCCUPIED_WINDOW_PAST_MINUTES + 15),
        terminal_station_code=STATION,
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_old_journey_date_excluded(db_session: AsyncSession) -> None:
    """The sargable journey_date pre-filter (partition pruning) drops rows
    from journeys older than 2 days regardless of their stop times."""
    now = now_et()
    await _seed_stop(
        db_session,
        "A114",
        "19",
        scheduled_departure=now + timedelta(minutes=5),
        journey_date=now - timedelta(days=5),
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_departed_train_excluded(db_session: AsyncSession) -> None:
    """A train flagged as departed has left its track, whatever its times say."""
    await _seed_stop(
        db_session,
        "A107",
        "7",
        scheduled_departure=now_et() + timedelta(minutes=5),
        has_departed_station=True,
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_cancelled_journey_excluded(db_session: AsyncSession) -> None:
    """A cancelled train never shows up to occupy its assigned track."""
    await _seed_stop(
        db_session,
        "A108",
        "8",
        scheduled_departure=now_et() + timedelta(minutes=5),
        is_cancelled=True,
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_stop_without_track_ignored(db_session: AsyncSession) -> None:
    """Stops with no track assignment contribute nothing."""
    await _seed_stop(
        db_session,
        "A109",
        None,
        scheduled_departure=now_et() + timedelta(minutes=5),
    )
    assert await _occupied(db_session) == set()


@pytest.mark.asyncio
async def test_multiple_trains_union_of_tracks(db_session: AsyncSession) -> None:
    """Occupied set is the union across boarding, delayed, and terminating
    trains — the full mix present at a terminal like NY Penn."""
    now = now_et()
    await _seed_stop(
        db_session, "A110", "1", scheduled_departure=now + timedelta(minutes=10)
    )
    await _seed_stop(
        db_session,
        "3901",
        "2",
        data_source="NJT",
        scheduled_departure=now - timedelta(minutes=30),
        updated_departure=now + timedelta(minutes=4),
        updated_arrival=now - timedelta(minutes=30),
    )
    await _seed_stop(
        db_session,
        "A111",
        "4",
        scheduled_arrival=now - timedelta(minutes=8),
        terminal_station_code=STATION,
    )
    await _seed_stop(
        db_session,
        "A112",
        "12",
        scheduled_departure=now
        + timedelta(minutes=OCCUPIED_WINDOW_FUTURE_MINUTES + 30),
    )
    assert await _occupied(db_session) == {"1", "2", "4"}
