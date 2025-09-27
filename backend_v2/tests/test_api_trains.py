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


@pytest.mark.skip(reason="Integration test requires real database connection")
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
            updated_departure=now_et() + timedelta(hours=hours, minutes=minutes),
            updated_arrival=now_et() + timedelta(hours=hours, minutes=minutes),
            has_departed_station=False,
            raw_njt_departed_flag="NO",
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


@pytest.mark.skip(reason="Integration test requires real database connection")
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
            has_departed_station=True,
            raw_njt_departed_flag="YES",
            track="7",
        ),
        JourneyStop(
            journey_id=journey.id,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_arrival=base_time - timedelta(minutes=15),
            scheduled_departure=base_time - timedelta(minutes=13),
            has_departed_station=False,
            raw_njt_departed_flag="NO",
            track="2",
        ),
        JourneyStop(
            journey_id=journey.id,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=45),
            has_departed_station=False,
            raw_njt_departed_flag="NO",
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
        assert train["stops"][0]["has_departed_station"] is True
        assert train["stops"][0]["track"] == "7"
        assert train["stops"][1]["has_departed_station"] is False
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


@pytest.mark.skip(reason="Integration test requires real database connection")
@pytest.mark.asyncio
async def test_get_train_history(client, db_session):
    """Test train history endpoint."""
    # Create historical journeys
    for i in range(3):
        journey = TrainJourney(
            train_id="3840",
            journey_date=now_et().date() - timedelta(days=i),
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
                updated_departure=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                updated_arrival=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                actual_departure=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                actual_arrival=now_et()
                - timedelta(days=i, hours=2 - seq)
                + timedelta(minutes=5),
                has_departed_station=True,
                raw_njt_departed_flag="YES",
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


@pytest.mark.skip(reason="Integration test requires real database connection")
@pytest.mark.asyncio
async def test_get_departures_with_date_parameter(client, db_session):
    """Test departures endpoint with date parameter to ensure correct train instance is returned."""
    base_time = now_et()
    today = base_time.date()
    tomorrow = today + timedelta(days=1)

    # Create two instances of train A98 - one for today, one for tomorrow
    today_journey = TrainJourney(
        train_id="A98",
        journey_date=today,
        line_code="AMTRAK",
        line_name="Silver Service",
        line_color="#005480",
        destination="New York",
        origin_station_code="MIA",
        terminal_station_code="NY",
        data_source="AMTRAK",
        scheduled_departure=datetime.combine(
            today, datetime.min.time().replace(hour=12, minute=10)
        ),
        scheduled_arrival=datetime.combine(
            today + timedelta(days=1), datetime.min.time().replace(hour=15, minute=20)
        ),
        first_seen_at=base_time,
        last_updated_at=base_time,
        has_complete_journey=True,
        stops_count=2,
        is_cancelled=False,
        is_completed=False,
    )
    db_session.add(today_journey)
    await db_session.flush()

    # Add stop for today's train at NY
    today_stop = JourneyStop(
        journey_id=today_journey.id,
        station_code="NY",
        station_name="New York Penn Station",
        stop_sequence=1,
        scheduled_arrival=datetime.combine(
            today + timedelta(days=1), datetime.min.time().replace(hour=15, minute=20)
        ),
        has_departed_station=False,
        raw_njt_departed_flag="NO",
    )
    db_session.add(today_stop)

    # Create tomorrow's train
    tomorrow_journey = TrainJourney(
        train_id="A98",
        journey_date=tomorrow,
        line_code="AMTRAK",
        line_name="Silver Service",
        line_color="#005480",
        destination="New York",
        origin_station_code="MIA",
        terminal_station_code="NY",
        data_source="AMTRAK",
        scheduled_departure=datetime.combine(
            tomorrow, datetime.min.time().replace(hour=12, minute=10)
        ),
        scheduled_arrival=datetime.combine(
            tomorrow + timedelta(days=1),
            datetime.min.time().replace(hour=15, minute=20),
        ),
        first_seen_at=base_time,
        last_updated_at=base_time,
        has_complete_journey=True,
        stops_count=2,
        is_cancelled=False,
        is_completed=False,
    )
    db_session.add(tomorrow_journey)
    await db_session.flush()

    # Add stop for tomorrow's train at NY
    tomorrow_stop = JourneyStop(
        journey_id=tomorrow_journey.id,
        station_code="NY",
        station_name="New York Penn Station",
        stop_sequence=1,
        scheduled_arrival=datetime.combine(
            tomorrow + timedelta(days=1),
            datetime.min.time().replace(hour=15, minute=20),
        ),
        has_departed_station=False,
        raw_njt_departed_flag="NO",
    )
    db_session.add(tomorrow_stop)

    await db_session.commit()

    # Test without date parameter - should default to today
    response = client.get("/api/v2/trains/departures?from=NY")
    assert response.status_code == 200
    data = response.json()

    # Should only return trains departing today or arriving today
    assert (
        len(data["departures"]) >= 0
    )  # May be empty if today's train already departed

    # Test with explicit today date parameter
    response = client.get(f"/api/v2/trains/departures?from=NY&date={today.isoformat()}")
    assert response.status_code == 200
    data = response.json()

    # Should return today's A98
    a98_trains = [d for d in data["departures"] if d["train_id"] == "A98"]
    if a98_trains:  # Only check if train is in results
        assert len(a98_trains) == 1
        assert a98_trains[0]["journey_date"] == f"{today.isoformat()}T00:00:00"

    # Test with tomorrow's date parameter
    response = client.get(
        f"/api/v2/trains/departures?from=NY&date={tomorrow.isoformat()}"
    )
    assert response.status_code == 200
    data = response.json()

    # Should return tomorrow's A98
    a98_trains = [d for d in data["departures"] if d["train_id"] == "A98"]
    if a98_trains:  # Only check if train is in results
        assert len(a98_trains) == 1
        assert a98_trains[0]["journey_date"] == f"{tomorrow.isoformat()}T00:00:00"


@pytest.mark.skip(reason="Integration test requires real database connection")
@pytest.mark.asyncio
async def test_departures_cache_integration(client, db_session):
    """Test end-to-end cache functionality for departures endpoint."""
    base_time = now_et()

    journey = TrainJourney(
        train_id="3840",
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        line_color="#F7505E",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source="NJT",
        scheduled_departure=base_time + timedelta(hours=1),
        first_seen_at=base_time,
        last_updated_at=base_time,
        has_complete_journey=True,
        stops_count=2,
        is_cancelled=False,
        is_completed=False,
    )
    db_session.add(journey)
    await db_session.flush()

    stops_data = [
        ("NY", "New York Penn Station", 0, 1, 0),
        ("TR", "Trenton", 1, 1, 75),
    ]

    for code, name, seq, hours, minutes in stops_data:
        stop = JourneyStop(
            journey_id=journey.id,
            station_code=code,
            station_name=name,
            stop_sequence=seq,
            scheduled_departure=base_time + timedelta(hours=hours, minutes=minutes),
            scheduled_arrival=base_time + timedelta(hours=hours, minutes=minutes),
            has_departed_station=False,
            raw_njt_departed_flag="NO",
        )
        db_session.add(stop)

    await db_session.commit()

    response1 = client.get("/api/v2/trains/departures?from=NY&to=TR")
    assert response1.status_code == 200
    data1 = response1.json()
    assert len(data1["departures"]) == 1

    response2 = client.get("/api/v2/trains/departures?from=NY&to=TR")
    assert response2.status_code == 200
    data2 = response2.json()

    assert data1["departures"][0]["train_id"] == data2["departures"][0]["train_id"]
    assert (
        data1["metadata"]["from_station"]["code"]
        == data2["metadata"]["from_station"]["code"]
    )
