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


def setup_mock_query(mock_session, stops):
    """Helper function to set up mock database query to return stops."""
    mock_result = AsyncMock()
    # Mock scalars to return an object with .all() method that returns stops
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=stops)
    mock_result.scalars = MagicMock(return_value=scalars_mock)
    mock_session.execute.return_value = mock_result


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

    # Mock the database query to return the journey stops
    setup_mock_query(mock_session, sample_journey.stops)

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

    # Mock the database query to return the journey stops
    setup_mock_query(mock_session, sample_journey.stops)

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

    # Mock the database query to return the journey stops
    setup_mock_query(mock_session, sample_journey.stops)

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

    # Mock the database query to return the journey stops
    setup_mock_query(mock_session, sample_journey.stops)

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

    # Mock the database query to return the journey stops
    setup_mock_query(mock_session, sample_journey.stops)

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

    # Mock the database query to return empty stops
    setup_mock_query(mock_session, [])

    await analyzer.analyze_journey(mock_session, journey)

    # Should not add any objects
    assert len(mock_session.added_objects) == 0


# =============================================================================
# Bulk segment analysis tests (issue #958)
# =============================================================================


def _make_journey(journey_id: int, data_source: str, line_code: str) -> TrainJourney:
    """Build a TrainJourney with three consecutive stops at 15-minute spacing.

    All stops have actual arrival/departure times set, so two consecutive
    segments are analyzable. Stops are attached to the journey via `stops`
    so that callers which want to pre-populate stops can still do so;
    ``analyze_new_segments_bulk`` itself fetches stops from the DB.
    """
    base_time = datetime(2026, 4, 23, 8, 0, 0)
    journey = TrainJourney(
        id=journey_id,
        train_id=f"T{journey_id}",
        journey_date=base_time.date(),
        data_source=data_source,
        line_code=line_code,
    )
    journey.stops = [
        JourneyStop(
            journey_id=journey_id,
            station_code="A",
            stop_sequence=0,
            scheduled_departure=base_time,
            actual_departure=base_time,
        ),
        JourneyStop(
            journey_id=journey_id,
            station_code="B",
            stop_sequence=1,
            scheduled_arrival=base_time + timedelta(minutes=15),
            scheduled_departure=base_time + timedelta(minutes=15),
            actual_arrival=base_time + timedelta(minutes=15),
            actual_departure=base_time + timedelta(minutes=15),
        ),
        JourneyStop(
            journey_id=journey_id,
            station_code="C",
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=30),
            actual_arrival=base_time + timedelta(minutes=30),
        ),
    ]
    return journey


def _setup_bulk_mocks(
    mock_session,
    stops_by_journey: dict[int, list[JourneyStop]],
    existing_tuples: list[tuple[int, str, str]],
) -> None:
    """Wire up two sequential execute() results: existing segments, then stops.

    The bulk method issues exactly two queries; this fixture mirrors that
    contract so a test failure tied to an extra query surfaces immediately.
    """
    existing_result = MagicMock()
    existing_result.all = MagicMock(return_value=existing_tuples)

    stops_flat = [s for stops in stops_by_journey.values() for s in stops]
    stops_scalars = MagicMock()
    stops_scalars.__iter__ = lambda self: iter(stops_flat)
    stops_result = MagicMock()
    stops_result.scalars = MagicMock(return_value=stops_scalars)

    mock_session.execute = AsyncMock(side_effect=[existing_result, stops_result])


@pytest.mark.asyncio
async def test_bulk_analyzer_empty_list_returns_zero(mock_session):
    """Empty input must not issue any DB queries."""
    analyzer = TransitAnalyzer()
    created = await analyzer.analyze_new_segments_bulk(mock_session, [])
    assert created == 0
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_analyzer_no_ids_returns_zero(mock_session):
    """Journeys without IDs (not yet flushed) must be skipped entirely."""
    analyzer = TransitAnalyzer()
    j = TrainJourney(train_id="T0", data_source="SUBWAY", line_code="1")
    # Intentionally no id assigned; simulates a journey that wasn't flushed.
    created = await analyzer.analyze_new_segments_bulk(mock_session, [j])
    assert created == 0
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_analyzer_creates_segments_for_multiple_journeys(mock_session):
    """Processes multiple journeys in two queries total."""
    j1 = _make_journey(1, "SUBWAY", "1")
    j2 = _make_journey(2, "LIRR", "BBR")
    _setup_bulk_mocks(
        mock_session,
        stops_by_journey={1: j1.stops, 2: j2.stops},
        existing_tuples=[],
    )

    analyzer = TransitAnalyzer()
    created = await analyzer.analyze_new_segments_bulk(mock_session, [j1, j2])

    # Two consecutive segments per journey, no existing records -> 4 total.
    assert created == 4
    segments = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    assert len(segments) == 4
    # Bulk method must issue exactly two queries regardless of journey count.
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_bulk_analyzer_skips_existing_segments(mock_session):
    """Segments already recorded in the DB must not be re-created."""
    j1 = _make_journey(1, "MNR", "HDN")
    # Both A->B and B->C are already recorded, so nothing new should be created.
    _setup_bulk_mocks(
        mock_session,
        stops_by_journey={1: j1.stops},
        existing_tuples=[(1, "A", "B"), (1, "B", "C")],
    )

    analyzer = TransitAnalyzer()
    created = await analyzer.analyze_new_segments_bulk(mock_session, [j1])

    assert created == 0
    segments = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    assert len(segments) == 0


@pytest.mark.asyncio
async def test_bulk_analyzer_skips_journeys_with_too_few_stops(mock_session):
    """Journeys with fewer than 2 stops must be skipped silently."""
    j1 = _make_journey(1, "SUBWAY", "6")
    short = TrainJourney(
        id=2,
        train_id="T2",
        journey_date=datetime(2026, 4, 23).date(),
        data_source="SUBWAY",
        line_code="6",
    )
    # A fresh stop bound to journey 2 — reusing a stop from j1 would wrongly
    # inflate j1's stop list since journey_id is what groups stops.
    short.stops = [
        JourneyStop(
            journey_id=2,
            station_code="A",
            stop_sequence=0,
            scheduled_departure=datetime(2026, 4, 23, 8, 0, 0),
            actual_departure=datetime(2026, 4, 23, 8, 0, 0),
        )
    ]

    _setup_bulk_mocks(
        mock_session,
        stops_by_journey={1: j1.stops, 2: short.stops},
        existing_tuples=[],
    )

    analyzer = TransitAnalyzer()
    created = await analyzer.analyze_new_segments_bulk(mock_session, [j1, short])

    # Only the 3-stop journey should yield segments.
    assert created == 2
    segments = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    assert len(segments) == 2
    assert {s.journey_id for s in segments} == {1}


@pytest.mark.asyncio
async def test_bulk_analyzer_respects_existing_per_journey(mock_session):
    """Existing set is scoped by journey_id; identical segments on different
    journeys must still each be created."""
    j1 = _make_journey(1, "LIRR", "BBR")
    j2 = _make_journey(2, "LIRR", "BBR")
    # j1's A->B is already recorded, j2's isn't.
    _setup_bulk_mocks(
        mock_session,
        stops_by_journey={1: j1.stops, 2: j2.stops},
        existing_tuples=[(1, "A", "B")],
    )

    analyzer = TransitAnalyzer()
    created = await analyzer.analyze_new_segments_bulk(mock_session, [j1, j2])

    # j1 -> B->C only, j2 -> A->B + B->C -> 3 total.
    assert created == 3
    segments = [
        obj for obj in mock_session.added_objects if isinstance(obj, SegmentTransitTime)
    ]
    created_keys = {
        (s.journey_id, s.from_station_code, s.to_station_code) for s in segments
    }
    assert created_keys == {(1, "B", "C"), (2, "A", "B"), (2, "B", "C")}
