"""Test live activity delay calculation, especially for Amtrak trains with null delay_minutes."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import ET, now_et


async def test_amtrak_journey_with_null_delay_minutes(db_session: AsyncSession):
    """Test that Amtrak journey delay is calculated correctly from stop timestamps."""
    # Create an Amtrak journey
    journey = TrainJourney(
        train_id="A2150",
        journey_date=now_et().date(),
        line_code="AM",
        line_name="Amtrak",
        destination="Washington",
        origin_station_code="NY",
        terminal_station_code="WAS",
        data_source="AMTRAK",
        scheduled_departure=ET.localize(datetime(2024, 7, 4, 14, 30)),
        has_complete_journey=True,
        stops_count=2,
    )
    db_session.add(journey)
    await db_session.flush()

    # Add stops with delay information
    stop1 = JourneyStop(
        journey_id=journey.id,
        journey_date=journey.journey_date,
        station_code="NY",
        station_name="New York Penn",
        stop_sequence=1,
        scheduled_departure=ET.localize(datetime(2024, 7, 4, 14, 30)),
        updated_departure=ET.localize(datetime(2024, 7, 4, 14, 35)),
        actual_departure=ET.localize(datetime(2024, 7, 4, 14, 35)),  # 5 minutes late
        has_departed_station=True,
        raw_amtrak_status="Departed",
    )
    stop2 = JourneyStop(
        journey_id=journey.id,
        journey_date=journey.journey_date,
        station_code="WAS",
        station_name="Washington Union",
        stop_sequence=2,
        scheduled_arrival=ET.localize(datetime(2024, 7, 4, 17, 30)),
        updated_arrival=ET.localize(datetime(2024, 7, 4, 17, 30)),
        has_departed_station=False,
        raw_amtrak_status="Enroute",
    )
    db_session.add_all([stop1, stop2])
    await db_session.commit()

    # Query stops explicitly to avoid lazy loading issues
    from sqlalchemy import select

    stops_stmt = (
        select(JourneyStop)
        .where(JourneyStop.journey_id == journey.id)
        .order_by(JourneyStop.stop_sequence)
    )
    stops_result = await db_session.execute(stops_stmt)
    stops = list(stops_result.scalars().all())

    # Verify the setup
    assert len(stops) > 0
    assert stops[0].actual_departure is not None
    assert stops[0].scheduled_departure is not None

    # Calculate delay from stops using new fields
    from trackrat.utils.time import calculate_delay

    calculated_delay = 0
    sorted_stops = sorted(stops, key=lambda s: s.stop_sequence or 0)
    for stop in reversed(sorted_stops):
        if stop.has_departed_station:
            if stop.actual_departure and stop.scheduled_departure:
                calculated_delay = calculate_delay(
                    stop.scheduled_departure, stop.actual_departure
                )
                break
            elif stop.actual_arrival and stop.scheduled_arrival:
                calculated_delay = calculate_delay(
                    stop.scheduled_arrival, stop.actual_arrival
                )
                break

    # Should calculate 5 minutes delay from the stops
    assert calculated_delay == 5


async def test_njt_journey_with_delay_minutes(db_session: AsyncSession):
    """Test that NJT journey delay is calculated correctly from stop timestamps."""
    # Create an NJT journey
    journey = TrainJourney(
        train_id="3955",
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source="NJT",
        scheduled_departure=ET.localize(datetime(2024, 7, 4, 14, 30)),
        has_complete_journey=True,
        stops_count=2,
    )
    db_session.add(journey)
    await db_session.flush()

    # Add stops
    stop1 = JourneyStop(
        journey_id=journey.id,
        journey_date=journey.journey_date,
        station_code="NY",
        station_name="New York Penn",
        stop_sequence=1,
        scheduled_departure=ET.localize(datetime(2024, 7, 4, 14, 30)),
        updated_departure=ET.localize(datetime(2024, 7, 4, 14, 33)),
        actual_departure=ET.localize(datetime(2024, 7, 4, 14, 33)),  # 3 minutes late
        has_departed_station=True,
        raw_njt_departed_flag="YES",
    )
    stop2 = JourneyStop(
        journey_id=journey.id,
        journey_date=journey.journey_date,
        station_code="TR",
        station_name="Trenton",
        stop_sequence=2,
        scheduled_arrival=ET.localize(datetime(2024, 7, 4, 15, 30)),
        updated_arrival=ET.localize(datetime(2024, 7, 4, 15, 30)),
        has_departed_station=False,
        raw_njt_departed_flag="NO",
    )
    db_session.add_all([stop1, stop2])
    await db_session.commit()

    # Query stops explicitly to avoid lazy loading issues
    from sqlalchemy import select

    stops_stmt = (
        select(JourneyStop)
        .where(JourneyStop.journey_id == journey.id)
        .order_by(JourneyStop.stop_sequence)
    )
    stops_result = await db_session.execute(stops_stmt)
    stops = list(stops_result.scalars().all())

    # Calculate delay from stops
    from trackrat.utils.time import calculate_delay

    calculated_delay = 0
    sorted_stops = sorted(stops, key=lambda s: s.stop_sequence or 0)
    for stop in reversed(sorted_stops):
        if stop.has_departed_station:
            if stop.actual_departure and stop.scheduled_departure:
                calculated_delay = calculate_delay(
                    stop.scheduled_departure, stop.actual_departure
                )
                break

    assert calculated_delay == 3
