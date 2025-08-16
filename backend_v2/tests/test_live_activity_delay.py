"""Test live activity delay calculation, especially for Amtrak trains with null delay_minutes."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from trackrat.models.database import Base, TrainJourney, JourneyStop, JourneySnapshot
from trackrat.utils.time import ET, now_et


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use PostgreSQL for testing instead of SQLite
    engine = create_engine(
        "postgresql://trackratuser:password@localhost:5432/trackratdb_test"
    )

    # Create tables first
    Base.metadata.create_all(engine)

    # Clean existing data after tables exist
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE journey_stops CASCADE"))
        conn.execute(text("TRUNCATE TABLE journey_snapshots CASCADE"))
        conn.execute(text("TRUNCATE TABLE train_journeys CASCADE"))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_amtrak_journey_with_null_delay_minutes(db_session):
    """Test that Amtrak journeys with null delay_minutes in snapshots are handled correctly."""
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
    db_session.flush()

    # Add stops with delay information
    stop1 = JourneyStop(
        journey_id=journey.id,
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
        station_code="WAS",
        station_name="Washington Union",
        stop_sequence=2,
        scheduled_arrival=ET.localize(datetime(2024, 7, 4, 17, 30)),
        updated_arrival=ET.localize(datetime(2024, 7, 4, 17, 30)),
        has_departed_station=False,
        raw_amtrak_status="Enroute",
    )
    db_session.add_all([stop1, stop2])
    db_session.flush()

    # Add snapshot with null delay_minutes (like Amtrak does)
    snapshot = JourneySnapshot(
        journey_id=journey.id,
        captured_at=now_et(),
        raw_stop_list_data={"test": "data"},
        train_status="DEPARTED",
        delay_minutes=None,  # This is the key - Amtrak doesn't set this
        completed_stops=1,
        total_stops=2,
    )
    db_session.add(snapshot)
    db_session.commit()

    # Verify the setup
    assert journey.snapshots[0].delay_minutes is None
    assert journey.stops[0].actual_departure is not None
    assert journey.stops[0].scheduled_departure is not None

    # Calculate delay from stops using new fields
    from trackrat.utils.time import calculate_delay

    calculated_delay = 0
    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
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


def test_njt_journey_with_delay_minutes(db_session):
    """Test that NJT journeys with delay_minutes in snapshots work correctly."""
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
    db_session.flush()

    # Add stops
    stop1 = JourneyStop(
        journey_id=journey.id,
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
        station_code="TR",
        station_name="Trenton",
        stop_sequence=2,
        scheduled_arrival=ET.localize(datetime(2024, 7, 4, 15, 30)),
        updated_arrival=ET.localize(datetime(2024, 7, 4, 15, 30)),
        has_departed_station=False,
        raw_njt_departed_flag="NO",
    )
    db_session.add_all([stop1, stop2])
    db_session.flush()

    # Add snapshot with delay_minutes set (like NJT does)
    snapshot = JourneySnapshot(
        journey_id=journey.id,
        captured_at=now_et(),
        raw_stop_list_data={"test": "data"},
        train_status="DEPARTED",
        delay_minutes=3,  # NJT sets this
        completed_stops=1,
        total_stops=2,
    )
    db_session.add(snapshot)
    db_session.commit()

    # Verify the setup
    assert journey.snapshots[0].delay_minutes == 3

    # Calculate delay from stops
    from trackrat.utils.time import calculate_delay

    calculated_delay = 0
    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
    for stop in reversed(sorted_stops):
        if stop.has_departed_station:
            if stop.actual_departure and stop.scheduled_departure:
                calculated_delay = calculate_delay(
                    stop.scheduled_departure, stop.actual_departure
                )
                break

    # Should match the snapshot delay
    assert calculated_delay == 3
