"""
Unit tests for the AmtrakPatternScheduler service.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.amtrak_pattern_scheduler import AmtrakPatternScheduler
from trackrat.utils.time import ET, now_et


@pytest.fixture
def pattern_scheduler():
    """Create an AmtrakPatternScheduler instance."""
    return AmtrakPatternScheduler()


@pytest.fixture
def sample_historical_journeys():
    """Create sample historical journey data for testing pattern detection."""
    # Create journeys for train 2150 that runs Mon-Fri at 15:05
    journeys = []
    base_date = date(2024, 1, 1)  # Start on a Monday

    for week in range(3):  # 3 weeks of data
        for day in range(5):  # Monday through Friday
            journey_date = base_date + timedelta(weeks=week, days=day)

            # Create a mock journey result
            journey = MagicMock()
            journey.train_id = "2150-4"
            journey.journey_date = journey_date
            journey.origin_station_code = "NYP"
            journey.terminal_station_code = "WAS"
            journey.destination = "Washington Union Station"
            journey.line_name = "Northeast Regional"
            # Add slight variance to departure time (±2 minutes)
            minutes_offset = (week * day) % 5 - 2  # Creates variance of -2 to +2
            journey.scheduled_departure = datetime.combine(
                journey_date, time(15, 5 + minutes_offset)
            )
            journey.day_of_week = (
                journey_date.weekday() + 1
            ) % 7  # PostgreSQL DOW format

            journeys.append(journey)

    # Add a different train (141) that runs less frequently
    for week in [0, 2]:  # Only 2 of 3 weeks
        journey_date = base_date + timedelta(weeks=week, days=2)  # Wednesday

        journey = MagicMock()
        journey.train_id = "141-4"
        journey.journey_date = journey_date
        journey.origin_station_code = "NYP"
        journey.terminal_station_code = "BOS"
        journey.destination = "Boston South Station"
        journey.line_name = "Acela"
        journey.scheduled_departure = datetime.combine(journey_date, time(8, 30))
        journey.day_of_week = (journey_date.weekday() + 1) % 7

        journeys.append(journey)

    return journeys


@pytest.mark.asyncio
async def test_analyze_historical_patterns(
    pattern_scheduler, sample_historical_journeys
):
    """Test that historical pattern analysis correctly identifies recurring trains."""
    target_date = date(2024, 1, 22)  # A Monday, 3 weeks after base date

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.all.return_value = [
            j
            for j in sample_historical_journeys
            if j.day_of_week == 1  # Monday in PostgreSQL format
        ]

        # Mock the execute method to return the result
        mock_execute = AsyncMock(return_value=mock_result)
        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        patterns = await pattern_scheduler.analyze_historical_patterns(target_date)

        # Should find train 2150 pattern for Monday
        assert len(patterns) == 1
        assert patterns[0]["train_number"] == "2150"
        assert patterns[0]["occurrence_count"] == 3  # 3 Mondays in sample data
        assert patterns[0]["origin"] == "NYP"
        assert patterns[0]["destination"] == "Washington Union Station"
        # Check median time calculation
        assert patterns[0]["median_departure"].hour == 15
        assert (
            3 <= patterns[0]["median_departure"].minute <= 7
        )  # Should be around 15:05


@pytest.mark.asyncio
async def test_minimum_occurrences_filter(pattern_scheduler):
    """Test that trains with insufficient occurrences are filtered out."""
    target_date = date(2024, 1, 24)  # A Wednesday

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Create only 1 occurrence (below minimum of 2)
        single_journey = MagicMock()
        single_journey.train_id = "999-1"
        single_journey.journey_date = date(2024, 1, 17)
        single_journey.origin_station_code = "NYP"
        single_journey.terminal_station_code = "PHL"
        single_journey.destination = "Philadelphia"
        single_journey.line_name = "Keystone"
        single_journey.scheduled_departure = datetime(2024, 1, 17, 10, 0)
        single_journey.day_of_week = 3  # Wednesday in PostgreSQL

        mock_result = MagicMock()
        mock_result.all.return_value = [single_journey]
        mock_execute = AsyncMock(return_value=mock_result)

        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        patterns = await pattern_scheduler.analyze_historical_patterns(target_date)

        # Should not find any patterns (insufficient occurrences)
        assert len(patterns) == 0


@pytest.mark.asyncio
async def test_high_variance_filter(pattern_scheduler):
    """Test that trains with high time variance are filtered out."""
    target_date = date(2024, 1, 22)  # A Monday

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Create journeys with high variance (>35 minutes)
        journeys = []
        for week, departure_hour in [(0, 10), (1, 11), (2, 12)]:
            journey = MagicMock()
            journey.train_id = "888-1"
            journey.journey_date = date(2024, 1, 1) + timedelta(weeks=week)
            journey.origin_station_code = "NYP"
            journey.terminal_station_code = "WAS"
            journey.destination = "Washington"
            journey.line_name = "Regional"
            journey.scheduled_departure = datetime.combine(
                journey.journey_date, time(departure_hour, 0)
            )
            journey.day_of_week = 1  # Monday
            journeys.append(journey)

        mock_result = MagicMock()
        mock_result.all.return_value = journeys
        mock_execute = AsyncMock(return_value=mock_result)

        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        patterns = await pattern_scheduler.analyze_historical_patterns(target_date)

        # Should not find any patterns (variance too high)
        assert len(patterns) == 0


@pytest.mark.asyncio
async def test_recent_matching_journeys_filters_amtrak_station_aliases(
    pattern_scheduler,
):
    """Historical route samples should match raw/internal Amtrak station aliases."""
    session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    await pattern_scheduler._get_recent_matching_journeys(
        session,
        {
            "train_number": "2150",
            "origin": "NYP",
            "terminal": "WAS",
        },
        date(2024, 1, 25),
    )

    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "origin_station_code IN ('NY', 'NYP')" in compiled
    assert "terminal_station_code IN ('WAS', 'WS')" in compiled


@pytest.mark.asyncio
async def test_create_scheduled_journeys_with_recent_stops(pattern_scheduler):
    """SCHEDULED journeys use a stable stop list from multiple recent runs."""
    target_date = date(2024, 1, 25)

    patterns = [
        {
            "train_number": "2150",
            "median_departure": time(15, 5),
            "occurrence_count": 3,
            "origin": "NYP",
            "destination": "Washington Union Station",
            "terminal": "WAS",
            "line_name": "Northeast Regional",
            "time_variance": 2.5,
            "sample_dates": ["2024-01-08", "2024-01-15", "2024-01-22"],
        }
    ]

    def make_recent_journey(journey_date: date, origin_minute: int) -> MagicMock:
        origin_departure = ET.localize(
            datetime.combine(journey_date, time(15, origin_minute))
        )
        recent_journey = MagicMock()
        recent_journey.journey_date = journey_date
        recent_journey.stops = [
            MagicMock(
                station_code="NYP",
                station_name="New York Penn Station",
                stop_sequence=0,
                scheduled_departure=origin_departure,
                scheduled_arrival=origin_departure,
            ),
            MagicMock(
                station_code="NWK",
                station_name="Newark Penn Station",
                stop_sequence=1,
                scheduled_departure=origin_departure + timedelta(minutes=19),
                scheduled_arrival=origin_departure + timedelta(minutes=17),
            ),
            MagicMock(
                station_code="TRE",
                station_name="Trenton",
                stop_sequence=2,
                scheduled_departure=origin_departure + timedelta(minutes=52),
                scheduled_arrival=origin_departure + timedelta(minutes=50),
            ),
            MagicMock(
                station_code="PH",
                station_name="Philadelphia 30th Street",
                stop_sequence=3,
                scheduled_departure=origin_departure + timedelta(minutes=82),
                scheduled_arrival=origin_departure + timedelta(minutes=79),
            ),
            MagicMock(
                station_code="WS",
                station_name="Washington Union Station",
                stop_sequence=4,
                scheduled_departure=None,
                scheduled_arrival=origin_departure + timedelta(minutes=207),
            ),
        ]
        return recent_journey

    recent_journeys = [
        make_recent_journey(date(2024, 1, 18), 3),
        make_recent_journey(date(2024, 1, 11), 7),
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        mock_no_existing = MagicMock()
        mock_no_existing.scalars.return_value.first.return_value = None

        mock_recent_result = MagicMock()
        mock_recent_result.scalars.return_value.all.return_value = recent_journeys

        mock_execute = AsyncMock(side_effect=[mock_no_existing, mock_recent_result])
        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        scheduled_journeys = await pattern_scheduler.create_scheduled_journeys(
            patterns, target_date
        )

        assert len(scheduled_journeys) == 1

        journey_data = scheduled_journeys[0]
        journey = journey_data["journey"]
        stops = journey_data["stops"]

        # Check journey properties
        assert journey.train_id == "2150"
        assert journey.journey_date == target_date
        assert journey.data_source == "AMTRAK"
        assert journey.observation_type == "SCHEDULED"
        assert journey.origin_station_code == "NYP"
        assert journey.terminal_station_code == "WAS"
        assert journey.destination == "Washington Union Station"
        assert journey.line_name == "Northeast Regional"
        assert journey.scheduled_departure == ET.localize(
            datetime.combine(target_date, time(15, 5))
        )

        # Should have all 5 stops from the stable route, not just origin
        assert len(stops) == 5
        assert journey.stops_count == 5

        # Verify station codes match the canonicalized full route
        station_codes = [s.station_code for s in stops]
        assert station_codes == ["NY", "NP", "TR", "PH", "WS"]

        # Verify time offset was applied correctly
        assert stops[0].scheduled_departure == ET.localize(datetime(2024, 1, 25, 15, 5))
        assert stops[1].scheduled_departure == ET.localize(
            datetime(2024, 1, 25, 15, 24)
        )
        assert stops[2].scheduled_departure == ET.localize(
            datetime(2024, 1, 25, 15, 57)
        )
        assert stops[3].scheduled_departure == ET.localize(
            datetime(2024, 1, 25, 16, 27)
        )
        assert stops[4].scheduled_departure is None  # Terminal has no departure

        # Verify arrivals also shifted
        assert stops[0].scheduled_arrival == ET.localize(datetime(2024, 1, 25, 15, 5))
        assert stops[4].scheduled_arrival == ET.localize(datetime(2024, 1, 25, 18, 32))


@pytest.mark.asyncio
async def test_create_scheduled_journeys_excludes_one_off_stop(pattern_scheduler):
    """A stop from only one historical run should not leak into SCHEDULED rows."""
    target_date = date(2024, 1, 25)
    patterns = [
        {
            "train_number": "2107",
            "median_departure": time(7, 35),
            "occurrence_count": 2,
            "origin": "NY",
            "destination": "Washington Union Station",
            "terminal": "WS",
            "line_name": "Acela",
            "time_variance": 1.0,
            "sample_dates": ["2024-01-11", "2024-01-18"],
        }
    ]

    def stop(code: str, seq: int, journey_date: date, minutes: int) -> MagicMock:
        base_time = ET.localize(datetime.combine(journey_date, time(7, 35)))
        return MagicMock(
            station_code=code,
            station_name=code,
            stop_sequence=seq,
            scheduled_departure=base_time + timedelta(minutes=minutes),
            scheduled_arrival=base_time + timedelta(minutes=minutes),
        )

    one_off = MagicMock()
    one_off.journey_date = date(2024, 1, 18)
    one_off.stops = [
        stop("NY", 0, one_off.journey_date, 0),
        stop("MP", 1, one_off.journey_date, 21),
        stop("PH", 2, one_off.journey_date, 66),
        stop("WS", 3, one_off.journey_date, 175),
    ]

    normal = MagicMock()
    normal.journey_date = date(2024, 1, 11)
    normal.stops = [
        stop("NY", 0, normal.journey_date, 0),
        stop("PH", 1, normal.journey_date, 66),
        stop("WS", 2, normal.journey_date, 175),
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        mock_no_existing = MagicMock()
        mock_no_existing.scalars.return_value.first.return_value = None
        mock_recent_result = MagicMock()
        mock_recent_result.scalars.return_value.all.return_value = [one_off, normal]
        mock_session.return_value.__aenter__.return_value.execute = AsyncMock(
            side_effect=[mock_no_existing, mock_recent_result]
        )

        scheduled_journeys = await pattern_scheduler.create_scheduled_journeys(
            patterns, target_date
        )

    stops = scheduled_journeys[0]["stops"]
    assert [s.station_code for s in stops] == ["NY", "PH", "WS"]


def test_consensus_stop_templates_canonicalize_amtrak_station_aliases(
    pattern_scheduler,
):
    """Raw/internal Amtrak stop aliases should intersect as the same route."""
    raw_base = ET.localize(datetime(2024, 1, 18, 7, 35))
    internal_base = ET.localize(datetime(2024, 1, 11, 7, 35))

    def stop(
        code: str, name: str, sequence: int, base_time: datetime, minutes: int
    ) -> MagicMock:
        return MagicMock(
            station_code=code,
            station_name=name,
            stop_sequence=sequence,
            scheduled_departure=base_time + timedelta(minutes=minutes),
            scheduled_arrival=base_time + timedelta(minutes=minutes),
        )

    raw_journey = MagicMock()
    raw_journey.stops = [
        stop("NYP", "New York Penn Station", 0, raw_base, 0),
        stop("PHL", "Philadelphia 30th Street", 1, raw_base, 66),
        stop("WAS", "Washington Union Station", 2, raw_base, 175),
    ]

    internal_journey = MagicMock()
    internal_journey.stops = [
        stop("NY", "New York Penn Station", 0, internal_base, 0),
        stop("PH", "Philadelphia 30th Street", 1, internal_base, 66),
        stop("WS", "Washington Union Station", 2, internal_base, 175),
    ]

    templates = pattern_scheduler._build_consensus_stop_templates(
        [raw_journey, internal_journey],
        {"NYP", "WAS"},
    )

    assert templates is not None
    assert [t["station_code"] for t in templates] == ["NY", "PH", "WS"]


@pytest.mark.asyncio
async def test_create_scheduled_journeys_fallback_no_recent(pattern_scheduler):
    """Test fallback to origin-only stop when no recent OBSERVED journey exists."""
    target_date = date(2024, 1, 25)

    patterns = [
        {
            "train_number": "9999",
            "median_departure": time(10, 0),
            "occurrence_count": 2,
            "origin": "NYP",
            "destination": "Albany",
            "terminal": "ALB",
            "line_name": "Empire Service",
            "time_variance": 1.0,
            "sample_dates": ["2024-01-11", "2024-01-18"],
        }
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        mock_no_existing = MagicMock()
        mock_no_existing.scalars.return_value.first.return_value = None

        mock_no_recent = MagicMock()
        mock_no_recent.scalars.return_value.all.return_value = []

        mock_execute = AsyncMock(side_effect=[mock_no_existing, mock_no_recent])
        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        scheduled_journeys = await pattern_scheduler.create_scheduled_journeys(
            patterns, target_date
        )

        assert len(scheduled_journeys) == 1
        stops = scheduled_journeys[0]["stops"]

        # Falls back to single origin stop
        assert len(stops) == 1
        assert stops[0].station_code == "NYP"
        assert stops[0].scheduled_departure == ET.localize(
            datetime.combine(target_date, time(10, 0))
        )


@pytest.mark.asyncio
async def test_skip_already_observed_trains(pattern_scheduler):
    """Test that OBSERVED trains are not overwritten with SCHEDULED data."""
    target_date = date(2024, 1, 25)

    patterns = [
        {
            "train_number": "2150",
            "median_departure": time(15, 5),
            "occurrence_count": 3,
            "origin": "NYP",
            "destination": "Washington",
            "terminal": "WAS",
            "line_name": "Regional",
            "time_variance": 2.5,
            "sample_dates": ["2024-01-18"],
        }
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock finding an existing OBSERVED journey
        existing_journey = MagicMock()
        existing_journey.observation_type = "OBSERVED"

        mock_scalars = MagicMock()
        mock_scalars.first.return_value = existing_journey
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_execute = AsyncMock(return_value=mock_result)

        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        scheduled_journeys = await pattern_scheduler.create_scheduled_journeys(
            patterns, target_date
        )

        # Should skip the train since it's already OBSERVED
        assert len(scheduled_journeys) == 0


@pytest.mark.asyncio
async def test_save_scheduled_journeys_new(pattern_scheduler):
    """Test saving new scheduled journeys to the database."""
    journey = TrainJourney(
        train_id="2150",
        journey_date=date(2024, 1, 25),
        data_source="AMTRAK",
        observation_type="SCHEDULED",
        origin_station_code="NYP",
        terminal_station_code="WAS",
        destination="Washington",
        line_name="Regional",
        line_code="AM",
        scheduled_departure=datetime(2024, 1, 25, 15, 5),
        has_complete_journey=False,
        stops_count=0,
    )

    stop = JourneyStop(
        journey=journey,
        station_code="NYP",
        station_name="New York Penn Station",
        stop_sequence=0,
        scheduled_departure=journey.scheduled_departure,
    )

    scheduled_journeys = [
        {
            "journey": journey,
            "stops": [stop],
            "pattern_info": {
                "occurrences": 3,
                "variance_minutes": 2.5,
                "sample_dates": ["2024-01-18"],
            },
        }
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock no existing journey
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_execute = AsyncMock(return_value=mock_result)

        mock_add = MagicMock()
        mock_flush = AsyncMock()
        mock_commit = AsyncMock()

        session_mock = mock_session.return_value.__aenter__.return_value
        session_mock.execute = mock_execute
        session_mock.add = mock_add
        session_mock.flush = mock_flush
        session_mock.commit = mock_commit

        stats = await pattern_scheduler.save_scheduled_journeys(scheduled_journeys)

        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert stats["errors"] == 0

        # Verify journey and stop were added
        assert mock_add.call_count == 2  # Journey + stop


@pytest.mark.asyncio
async def test_save_scheduled_journeys_update_replaces_stops(pattern_scheduler):
    """Test that updating an existing SCHEDULED record also replaces its stops."""
    journey = TrainJourney(
        train_id="2150",
        journey_date=date(2024, 1, 25),
        data_source="AMTRAK",
        observation_type="SCHEDULED",
        origin_station_code="NYP",
        terminal_station_code="WAS",
        destination="Washington",
        line_name="Regional",
        line_code="AM",
        scheduled_departure=datetime(2024, 1, 25, 15, 5),
        has_complete_journey=False,
        stops_count=3,
    )

    stops = [
        JourneyStop(
            journey=journey,
            station_code="NYP",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=datetime(2024, 1, 25, 15, 5),
        ),
        JourneyStop(
            journey=journey,
            station_code="PH",
            station_name="Philadelphia 30th Street",
            stop_sequence=1,
            scheduled_departure=datetime(2024, 1, 25, 16, 25),
        ),
        JourneyStop(
            journey=journey,
            station_code="WS",
            station_name="Washington Union Station",
            stop_sequence=2,
            scheduled_arrival=datetime(2024, 1, 25, 18, 30),
        ),
    ]

    scheduled_journeys = [
        {
            "journey": journey,
            "stops": stops,
            "pattern_info": {
                "occurrences": 3,
                "variance_minutes": 2.5,
                "sample_dates": ["2024-01-18"],
            },
        }
    ]

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock finding an existing SCHEDULED journey
        existing_journey = MagicMock()
        existing_journey.id = 42
        existing_journey.observation_type = "SCHEDULED"
        existing_journey.update_count = 1

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = existing_journey

        mock_delete_result = MagicMock()

        mock_execute = AsyncMock(side_effect=[mock_select_result, mock_delete_result])

        mock_add = MagicMock()
        mock_flush = AsyncMock()
        mock_commit = AsyncMock()

        session_mock = mock_session.return_value.__aenter__.return_value
        session_mock.execute = mock_execute
        session_mock.add = mock_add
        session_mock.flush = mock_flush
        session_mock.commit = mock_commit

        stats = await pattern_scheduler.save_scheduled_journeys(scheduled_journeys)

        assert stats["created"] == 0
        assert stats["updated"] == 1
        assert stats["errors"] == 0

        # Verify old stops were deleted (second execute call is the DELETE)
        assert mock_execute.call_count == 2

        # Verify new stops were added (3 stops)
        assert mock_add.call_count == 3

        # Verify journey metadata was updated
        assert existing_journey.stops_count == 3
        assert existing_journey.update_count == 2


@pytest.mark.asyncio
async def test_cleanup_old_scheduled_records(pattern_scheduler):
    """Test cleanup of old SCHEDULED records that never became OBSERVED."""
    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Create mock old journeys
        old_journey1 = MagicMock()
        old_journey1.id = 1
        old_journey2 = MagicMock()
        old_journey2.id = 2

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [old_journey1, old_journey2]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_execute = AsyncMock(return_value=mock_result)
        mock_delete = AsyncMock()
        mock_commit = AsyncMock()

        session_mock = mock_session.return_value.__aenter__.return_value
        session_mock.execute = mock_execute
        session_mock.delete = mock_delete
        session_mock.commit = mock_commit

        deleted_count = await pattern_scheduler.cleanup_old_scheduled_records(
            days_to_keep=1
        )

        assert deleted_count == 2
        assert mock_delete.call_count == 2
        assert mock_commit.called


def test_calculate_median_time(pattern_scheduler):
    """Test median time calculation."""
    times = [
        datetime(2024, 1, 1, 15, 3),
        datetime(2024, 1, 2, 15, 5),
        datetime(2024, 1, 3, 15, 7),
    ]

    median = pattern_scheduler._calculate_median_time(times)

    assert median == time(15, 5)  # Middle value


def test_calculate_median_time_even_count(pattern_scheduler):
    """Test median time calculation with even number of times."""
    times = [
        datetime(2024, 1, 1, 15, 0),
        datetime(2024, 1, 2, 15, 10),
        datetime(2024, 1, 3, 15, 20),
        datetime(2024, 1, 4, 15, 30),
    ]

    median = pattern_scheduler._calculate_median_time(times)

    assert median == time(15, 15)  # Average of middle two values


def test_calculate_time_variance(pattern_scheduler):
    """Test time variance calculation."""
    # Times with low variance (all at 15:05)
    low_variance_times = [
        datetime(2024, 1, 1, 15, 5),
        datetime(2024, 1, 2, 15, 5),
        datetime(2024, 1, 3, 15, 5),
    ]

    variance = pattern_scheduler._calculate_time_variance_minutes(low_variance_times)
    assert variance == 0.0

    # Times with some variance
    varied_times = [
        datetime(2024, 1, 1, 15, 0),
        datetime(2024, 1, 2, 15, 10),
        datetime(2024, 1, 3, 15, 20),
    ]

    variance = pattern_scheduler._calculate_time_variance_minutes(varied_times)
    # Standard deviation should be around 8.16 minutes
    assert 8 <= variance <= 9


def test_cross_midnight_trains(pattern_scheduler):
    """Test handling of trains that cross midnight."""
    # Train normally departing at 11:30 PM, sometimes delayed past midnight
    cross_midnight_times = [
        datetime(2024, 1, 1, 23, 30),  # 11:30 PM
        datetime(2024, 1, 2, 23, 35),  # 11:35 PM
        datetime(2024, 1, 3, 0, 15),  # 12:15 AM (delayed past midnight)
    ]

    # Calculate median - should be close to 11:40 PM, not skewed by midnight crossing
    median = pattern_scheduler._calculate_median_time(cross_midnight_times)
    assert median.hour == 23
    assert 35 <= median.minute <= 45  # Should be around 11:40 PM

    # Calculate variance - should be low since times are actually close together
    variance = pattern_scheduler._calculate_time_variance_minutes(cross_midnight_times)
    assert variance < 30  # Less than 30 minutes variance


def test_empty_list_handling(pattern_scheduler):
    """Test that empty lists are handled gracefully."""
    # Empty list for median calculation
    median = pattern_scheduler._calculate_median_time([])
    assert median == time(0, 0)  # Should return midnight as default

    # Empty list for variance calculation
    variance = pattern_scheduler._calculate_time_variance_minutes([])
    assert variance == 0.0

    # Single item for variance (needs at least 2)
    variance = pattern_scheduler._calculate_time_variance_minutes(
        [datetime(2024, 1, 1, 10, 0)]
    )
    assert variance == 0.0


@pytest.mark.asyncio
async def test_analyze_historical_patterns_optimized(pattern_scheduler):
    """Test the optimized database aggregation method for pattern analysis."""
    target_date = date(2024, 1, 22)  # A Monday

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock database row result
        mock_row = MagicMock()
        mock_row.train_number = "2150"
        mock_row.day_of_week = 0  # Monday (already converted)
        mock_row.occurrence_count = 3
        mock_row.median_minutes = 905  # 15:05 in minutes
        mock_row.time_variance = 2.5
        mock_row.origin = "NYP"
        mock_row.destination = "Washington Union Station"
        mock_row.terminal = "WAS"
        mock_row.line_name = "Northeast Regional"
        mock_row.sample_dates = [date(2024, 1, 15), date(2024, 1, 8), date(2024, 1, 1)]

        # Mock execute to return iterable result
        mock_execute = AsyncMock()
        mock_execute.return_value = [mock_row]

        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        patterns = await pattern_scheduler.analyze_historical_patterns_optimized(
            target_date
        )

        # Verify the SQL query was called with correct parameters
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1] if len(call_args) > 1 else mock_execute.call_args[1]

        assert params["target_day"] == 0  # Monday
        assert params["min_count"] == 2
        assert params["variance_threshold"] == 35

        # Verify pattern results
        assert len(patterns) == 1
        pattern = patterns[0]
        assert pattern["train_number"] == "2150"
        assert pattern["median_departure"] == time(15, 5)  # Converted from minutes
        assert pattern["occurrence_count"] == 3
        assert pattern["origin"] == "NYP"
        assert pattern["destination"] == "Washington Union Station"
        assert pattern["terminal"] == "WAS"
        assert pattern["line_name"] == "Northeast Regional"
        assert pattern["time_variance"] == 2.5
        assert len(pattern["sample_dates"]) == 3


@pytest.mark.asyncio
async def test_optimized_method_handles_nulls(pattern_scheduler):
    """Test that the optimized method handles NULL values gracefully."""
    target_date = date(2024, 1, 22)

    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_session"
    ) as mock_session:
        # Mock row with NULL values
        mock_row = MagicMock()
        mock_row.train_number = "999"
        mock_row.day_of_week = 0
        mock_row.occurrence_count = 2
        mock_row.median_minutes = None  # NULL median time
        mock_row.time_variance = None  # NULL variance
        mock_row.origin = "NYP"
        mock_row.destination = "Unknown"
        mock_row.terminal = "UNK"
        mock_row.line_name = None  # NULL line name
        mock_row.sample_dates = None  # NULL sample dates

        mock_execute = AsyncMock()
        mock_execute.return_value = [mock_row]

        mock_session.return_value.__aenter__.return_value.execute = mock_execute

        patterns = await pattern_scheduler.analyze_historical_patterns_optimized(
            target_date
        )

        # Should skip patterns with NULL median_minutes
        assert len(patterns) == 0


@pytest.mark.asyncio
async def test_generate_daily_schedules_uses_feature_flag(pattern_scheduler):
    """Test that generate_daily_schedules respects the feature flag."""
    target_date = date(2024, 1, 22)

    # Mock the settings to use optimized method
    with patch(
        "trackrat.services.amtrak_pattern_scheduler.get_settings"
    ) as mock_settings:
        mock_settings.return_value.use_optimized_amtrak_pattern_analysis = True

        with patch.object(
            pattern_scheduler, "analyze_historical_patterns_optimized"
        ) as mock_optimized:
            with patch.object(
                pattern_scheduler, "analyze_historical_patterns"
            ) as mock_original:
                with patch.object(
                    pattern_scheduler, "create_scheduled_journeys"
                ) as mock_create:
                    with patch.object(
                        pattern_scheduler, "save_scheduled_journeys"
                    ) as mock_save:
                        mock_optimized.return_value = []
                        mock_original.return_value = []
                        mock_create.return_value = []
                        mock_save.return_value = {
                            "created": 0,
                            "updated": 0,
                            "errors": 0,
                        }

                        await pattern_scheduler.generate_daily_schedules(target_date)

                        # Should call optimized method, not original
                        mock_optimized.assert_called_once_with(target_date)
                        mock_original.assert_not_called()

        # Now test with feature flag disabled
        mock_settings.return_value.use_optimized_amtrak_pattern_analysis = False

        with patch.object(
            pattern_scheduler, "analyze_historical_patterns_optimized"
        ) as mock_optimized:
            with patch.object(
                pattern_scheduler, "analyze_historical_patterns"
            ) as mock_original:
                with patch.object(
                    pattern_scheduler, "create_scheduled_journeys"
                ) as mock_create:
                    with patch.object(
                        pattern_scheduler, "save_scheduled_journeys"
                    ) as mock_save:
                        mock_optimized.return_value = []
                        mock_original.return_value = []
                        mock_create.return_value = []
                        mock_save.return_value = {
                            "created": 0,
                            "updated": 0,
                            "errors": 0,
                        }

                        await pattern_scheduler.generate_daily_schedules(target_date)

                        # Should call original method, not optimized
                        mock_original.assert_called_once_with(target_date)
                        mock_optimized.assert_not_called()
