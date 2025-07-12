"""
Tests for train API endpoints.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, AsyncMock

from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et, ET


@pytest.mark.asyncio
async def test_get_departures_empty(client):
    """Test departures endpoint with no data."""
    response = client.get("/api/v2/trains/departures?from=NY")
    assert response.status_code == 200

    data = response.json()
    assert "departures" in data
    assert data["departures"] == []
    assert data["metadata"]["from_station"]["code"] == "NY"
    assert data["metadata"]["count"] == 0


@pytest.mark.asyncio
async def test_get_departures_with_data(client, db_session):
    """Test departures endpoint with train data."""
    # Create test journey
    journey = TrainJourney(
        train_id="3840",
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        line_color="#F7505E",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=now_et() + timedelta(hours=1),
        first_seen_at=now_et(),
        last_updated_at=now_et(),
        has_complete_journey=True,
        stops_count=3,
        is_cancelled=False,
        is_completed=False,
    )
    db_session.add(journey)
    await db_session.flush()

    # Add stops
    stops_data = [
        ("NY", "New York Penn Station", 0, 1, 0),
        ("NP", "Newark Penn Station", 1, 1, 15),
        ("TR", "Trenton", 2, 1, 75),
    ]

    for code, name, seq, hours, minutes in stops_data:
        stop = JourneyStop(
            journey_id=journey.id,
            station_code=code,
            station_name=name,
            stop_sequence=seq,
            scheduled_departure=now_et() + timedelta(hours=hours, minutes=minutes),
            scheduled_arrival=now_et() + timedelta(hours=hours, minutes=minutes),
            departed=False,
            status="OnTime",
        )
        if code == "NY":
            stop.track = "7"
        db_session.add(stop)

    await db_session.commit()

    # Mock JIT service to not refresh
    with patch("trackrat.api.trains.JustInTimeUpdateService") as mock_jit:
        mock_service = AsyncMock()
        mock_service.ensure_fresh_departures = AsyncMock(
            return_value={journey.id: True}
        )
        mock_jit.return_value.__aenter__.return_value = mock_service

        # Test from NY
        response = client.get("/api/v2/trains/departures?from=NY")
        assert response.status_code == 200

        data = response.json()
        assert len(data["departures"]) == 1

        departure = data["departures"][0]
        assert departure["train_id"] == "3840"
        assert departure["line"]["code"] == "NE"
        assert departure["destination"] == "Trenton"
        assert departure["departure"]["code"] == "NY"
        assert departure["departure"]["track"] == "7"

        # Test from NY to TR
        response = client.get("/api/v2/trains/departures?from=NY&to=TR")
        assert response.status_code == 200

        data = response.json()
        assert len(data["departures"]) == 1
        assert data["departures"][0]["arrival"]["code"] == "TR"


@pytest.mark.skip(
    reason="Timezone handling in test environment - known SQLite/timezone interaction issue"
)
@pytest.mark.asyncio
async def test_get_train_details(client, db_session):
    """Test train details endpoint."""
    # Ensure consistent timezone-aware datetimes
    base_time = now_et()

    # Create test journey with stops
    journey = TrainJourney(
        train_id="3840",
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        line_color="#F7505E",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        scheduled_departure=base_time - timedelta(minutes=30),
        scheduled_arrival=base_time + timedelta(minutes=45),
        first_seen_at=base_time - timedelta(hours=1),
        last_updated_at=base_time - timedelta(minutes=5),
        has_complete_journey=True,
        stops_count=3,
        is_cancelled=False,
        is_completed=False,
    )
    db_session.add(journey)
    await db_session.flush()

    # Add stops with one departed
    stops = [
        JourneyStop(
            journey_id=journey.id,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=base_time - timedelta(minutes=30),
            actual_departure=base_time - timedelta(minutes=28),
            departed=True,
            status="OnTime",
            track="7",
        ),
        JourneyStop(
            journey_id=journey.id,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_arrival=base_time - timedelta(minutes=15),
            scheduled_departure=base_time - timedelta(minutes=13),
            departed=False,
            status="OnTime",
            track="2",
        ),
        JourneyStop(
            journey_id=journey.id,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=45),
            departed=False,
            status="OnTime",
        ),
    ]

    for stop in stops:
        db_session.add(stop)

    await db_session.commit()

    # Refresh the journey with stops to avoid lazy loading issues
    await db_session.refresh(journey)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select

    stmt = (
        select(TrainJourney)
        .where(TrainJourney.id == journey.id)
        .options(selectinload(TrainJourney.stops))
    )
    journey_with_stops = await db_session.scalar(stmt)

    # Mock JIT service
    with patch("trackrat.api.trains.JustInTimeUpdateService") as mock_jit:
        mock_service = AsyncMock()
        mock_service.get_fresh_train = AsyncMock(return_value=journey_with_stops)
        mock_jit.return_value.__aenter__.return_value = mock_service

        response = client.get(f"/api/v2/trains/3840")
        assert response.status_code == 200

        data = response.json()
        train = data["train"]

        assert train["train_id"] == "3840"
        assert train["journey_date"] == str(date.today())
        assert train["line"]["code"] == "NE"
        assert len(train["stops"]) == 3

        # Check current status
        assert train["current_status"]["status"] == "BOARDING"
        assert "Newark" in train["current_status"]["location"]

        # Check stops
        assert train["stops"][0]["departed"] is True
        assert train["stops"][0]["track"] == "7"
        assert train["stops"][1]["departed"] is False
        assert train["stops"][1]["track"] == "2"


@pytest.mark.asyncio
async def test_get_train_not_found(client):
    """Test train details endpoint with non-existent train."""
    with patch("trackrat.api.trains.JustInTimeUpdateService") as mock_jit:
        mock_service = AsyncMock()
        mock_service.get_fresh_train = AsyncMock(return_value=None)
        mock_jit.return_value.__aenter__.return_value = mock_service

        response = client.get("/api/v2/trains/9999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_train_history(client, db_session):
    """Test train history endpoint."""
    # Create historical journeys
    for i in range(3):
        journey = TrainJourney(
            train_id="3840",
            journey_date=date.today() - timedelta(days=i),
            line_code="NE",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=now_et() - timedelta(days=i, hours=2),
            scheduled_arrival=now_et() - timedelta(days=i, hours=1),
            actual_departure=now_et()
            - timedelta(days=i, hours=2)
            + timedelta(minutes=5),
            actual_arrival=now_et() - timedelta(days=i, hours=1) + timedelta(minutes=5),
            first_seen_at=now_et() - timedelta(days=i, hours=3),
            last_updated_at=now_et() - timedelta(days=i),
            has_complete_journey=True,
            is_cancelled=False,
            is_completed=True,
        )
        db_session.add(journey)
        await db_session.flush()

        # Add minimal stops
        for code, seq in [("NY", 0), ("TR", 1)]:
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=f"{code} Station",
                stop_sequence=seq,
                scheduled_departure=now_et() - timedelta(days=i, hours=2 - seq),
                scheduled_arrival=now_et() - timedelta(days=i, hours=2 - seq),
                actual_departure=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                actual_arrival=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                departed=True,
                status="OnTime" if i == 0 else "Late",
                track="7" if code == "NY" else None,
            )
            db_session.add(stop)

    await db_session.commit()

    response = client.get("/api/v2/trains/3840/history?days=7")
    assert response.status_code == 200

    data = response.json()
    assert data["train_id"] == "3840"
    assert len(data["journeys"]) == 3

    # Check statistics
    stats = data["statistics"]
    assert stats["total_journeys"] == 3
    assert stats["average_delay_minutes"] == 5.0
    assert stats["cancellation_rate"] == 0.0

    # Check journey data
    latest = data["journeys"][0]
    assert latest["delay_minutes"] == 5
    assert latest["was_cancelled"] is False
    assert "NY" in latest["track_assignments"]
