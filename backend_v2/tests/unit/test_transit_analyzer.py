"""
Unit tests for the TransitAnalyzer service.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models import (
    JourneyProgress,
    JourneyStop,
    SegmentTransitTime,
    StationDwellTime,
    TrainJourney,
)
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_et


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    # Track added objects
    session.added_objects = []
    session.add = MagicMock(side_effect=lambda obj: session.added_objects.append(obj))
    return session


@pytest.fixture
def sample_journey():
    """Create a sample journey with stops."""
    base_time = datetime(2025, 7, 15, 8, 0, 0)  # 8:00 AM

    journey = TrainJourney(
        id=1,
        train_id="3835",
        journey_date=base_time.date(),
        line_code="NE",
        data_source="NJT",
        actual_departure=base_time + timedelta(minutes=5),  # 5 min late departure
    )

    # Create stops with realistic times
    stops = [
        JourneyStop(
            journey_id=1,
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=base_time,
            actual_departure=base_time + timedelta(minutes=5),  # 5 min late
        ),
        JourneyStop(
            journey_id=1,
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=15),
            scheduled_departure=base_time + timedelta(minutes=17),
            actual_arrival=base_time + timedelta(minutes=20),  # 5 min late
            actual_departure=base_time + timedelta(minutes=23),  # 6 min late
        ),
        JourneyStop(
            journey_id=1,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=50),
            actual_arrival=base_time + timedelta(minutes=58),  # 8 min late
        ),
    ]

    journey.stops = stops
    return journey


@pytest.mark.asyncio
async def test_analyze_journey_basic(mock_session, sample_journey):
    """Test basic journey analysis functionality."""
    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, sample_journey)

    # Check that objects were added to the session
    assert len(mock_session.added_objects) > 0

    # Check for segment transit times
    segment_times = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    assert len(segment_times) == 2  # NY->NP and NP->TR

    # Check NY->NP segment
    ny_np_segment = next(
        (s for s in segment_times if s.from_station_code == "NY"), None
    )
    assert ny_np_segment is not None
    assert ny_np_segment.to_station_code == "NP"
    assert ny_np_segment.scheduled_minutes == 15
    assert ny_np_segment.actual_minutes == 15  # 20 - 5 = 15 minutes
    assert ny_np_segment.delay_minutes == 0

    # Check NP->TR segment
    np_tr_segment = next(
        (s for s in segment_times if s.from_station_code == "NP"), None
    )
    assert np_tr_segment is not None
    assert np_tr_segment.to_station_code == "TR"
    assert np_tr_segment.scheduled_minutes == 33  # 50 - 17 = 33 minutes
    assert np_tr_segment.actual_minutes == 35  # 58 - 23 = 35 minutes
    assert np_tr_segment.delay_minutes == 2


@pytest.mark.asyncio
async def test_analyze_dwell_times(mock_session, sample_journey):
    """Test station dwell time analysis."""
    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, sample_journey)

    # Check for dwell times
    dwell_times = [
        obj for obj in mock_session.added_objects if isinstance(obj, StationDwellTime)
    ]
    assert len(dwell_times) == 2  # Origin (NY) and Newark

    # Check origin dwell (initial delay)
    origin_dwell = next((d for d in dwell_times if d.is_origin), None)
    assert origin_dwell is not None
    assert origin_dwell.station_code == "NY"
    assert origin_dwell.excess_dwell_minutes == 5  # 5 min late departure

    # Check Newark dwell time
    newark_dwell = next((d for d in dwell_times if d.station_code == "NP"), None)
    assert newark_dwell is not None
    assert newark_dwell.scheduled_minutes == 2  # 17 - 15 = 2 minutes scheduled
    assert newark_dwell.actual_minutes == 3  # 23 - 20 = 3 minutes actual
    assert newark_dwell.excess_dwell_minutes == 1


@pytest.mark.asyncio
async def test_journey_progress(mock_session, sample_journey):
    """Test journey progress calculation."""
    # Mark first two stops as departed
    sample_journey.stops[0].has_departed_station = True
    sample_journey.stops[1].has_departed_station = True

    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, sample_journey)

    # Check journey progress
    progress_records = [
        obj for obj in mock_session.added_objects if isinstance(obj, JourneyProgress)
    ]
    assert len(progress_records) == 1

    progress = progress_records[0]
    assert progress.journey_id == 1
    assert progress.last_departed_station == "NP"
    assert progress.next_station == "TR"
    assert progress.stops_completed == 2
    assert progress.stops_total == 3
    assert progress.journey_percent == pytest.approx(66.67, rel=0.01)
    assert progress.initial_delay_minutes == 5


@pytest.mark.asyncio
async def test_invalid_transit_times(mock_session, sample_journey):
    """Test handling of invalid transit times."""
    # Create invalid scenario: arrival before departure
    sample_journey.stops[1].actual_arrival = sample_journey.stops[
        0
    ].actual_departure - timedelta(minutes=5)

    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, sample_journey)

    # Should skip invalid segment
    segment_times = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    # Only NP->TR segment should be created
    assert len(segment_times) == 1
    assert segment_times[0].from_station_code == "NP"


@pytest.mark.asyncio
async def test_missing_actual_times(mock_session, sample_journey):
    """Test handling when actual times are missing."""
    # Remove actual times from middle stop
    sample_journey.stops[1].actual_arrival = None
    sample_journey.stops[1].actual_departure = None

    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, sample_journey)

    # Should not create segments involving the stop with missing times
    segment_times = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    assert len(segment_times) == 0  # No valid segments can be created


@pytest.mark.asyncio
async def test_empty_journey(mock_session):
    """Test handling of journey with no stops."""
    journey = TrainJourney(
        id=1,
        train_id="3835",
        journey_date=datetime.now().date(),
        line_code="NE",
        data_source="NJT",
        stops=[],
    )

    analyzer = TransitAnalyzer()

    await analyzer.analyze_journey(mock_session, journey)

    # Should not add any objects
    assert len(mock_session.added_objects) == 0
