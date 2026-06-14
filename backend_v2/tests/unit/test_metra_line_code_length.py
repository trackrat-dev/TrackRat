"""Regression tests for the Metra line-code length overflow (issue #1241).

Production logs showed `get_departures` raising:

    1 validation error for LineInfo
    code: String should have at most 10 characters
          [type=string_too_long, input_value='METRA-UP-NW', input_type=str]

The Metra collector assigns line codes of the form ``METRA-<route_id>``; the
longest current code, ``METRA-UP-NW`` (Union Pacific Northwest), is 11
characters and exceeded the old ``LineInfo.code`` ``max_length=10`` constraint.
Every Metra train on the UP-NW line therefore failed the departures endpoint
with an HTTP 500. The fix raises the limit so legitimate codes validate and are
returned untruncated (truncating would collide ``METRA-UP-NW`` with the
distinct ``METRA-UP-N`` line).

These tests:

1. Assert every code in ``METRA_ROUTES`` builds a valid ``LineInfo`` and is
   preserved in full (the model-level regression for the exact production error,
   and a guard for any future Metra route additions).
2. Assert the ``METRA-<route_id>`` fallback for an unknown route validates.
3. Exercise the real ``DepartureService.get_departures`` path with a UP-NW
   journey to confirm the endpoint that crashed now returns the departure with
   the full line code.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.config.stations.metra import METRA_ROUTES
from trackrat.models.api import LineInfo, TrainPosition
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et

# ---------------------------------------------------------------------------
# 1. Model-level: every real Metra code validates and round-trips untruncated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code,name,color",
    list(METRA_ROUTES.values()),
    ids=list(METRA_ROUTES),
)
def test_all_metra_line_codes_build_valid_lineinfo(code, name, color):
    """Every code in METRA_ROUTES must construct a valid LineInfo with the
    full, untruncated code preserved.

    ``METRA-UP-NW`` (11 chars) is the specific code that triggered the
    production HTTP 500; the others guard future additions.
    """
    line = LineInfo(code=code, name=name, color=color)

    assert line.code == code, (
        f"Metra code {code!r} must be preserved untruncated; got {line.code!r}. "
        "Truncation would collide distinct lines (e.g. METRA-UP-NW -> METRA-UP-N)."
    )


def test_metra_up_nw_code_specifically_validates():
    """The exact code from the production error must validate.

    Before the fix this raised pydantic ValidationError
    (`String should have at most 10 characters`).
    """
    line = LineInfo(code="METRA-UP-NW", name="Union Pacific Northwest", color="#FFE600")
    assert line.code == "METRA-UP-NW"
    assert len("METRA-UP-NW") == 11  # would have failed the old max_length=10


def test_metra_unknown_route_fallback_code_validates():
    """The collector's ``METRA-<route_id>`` fallback for an unrecognized route
    must also validate within the limit."""
    # Mirrors collector.py: line_code = f"METRA-{route_id}" for unknown routes.
    fallback_code = f"METRA-{'NW-EXT'}"
    line = LineInfo(code=fallback_code, name="Metra NW-EXT", color="#00558A")
    assert line.code == fallback_code


# ---------------------------------------------------------------------------
# 2. Integration: the real get_departures path no longer 500s for UP-NW
# ---------------------------------------------------------------------------


def _create_metra_up_nw_journey() -> TrainJourney:
    """Build a UP-NW Metra journey (HARVARD -> OTC) as the collector would,
    with the 11-char ``METRA-UP-NW`` line code that broke the endpoint."""
    now = now_et()
    dep_time = now + timedelta(minutes=30)

    journey = Mock(spec=TrainJourney)
    journey.id = 7777
    journey.train_id = "MT630"
    journey.journey_date = now.date()
    journey.line_code = "METRA-UP-NW"
    journey.line_name = "Union Pacific Northwest"
    journey.line_color = "#FFE600"
    journey.destination = "Chicago OTC"
    journey.origin_station_code = "HARVARD"
    journey.terminal_station_code = "OTC"
    journey.scheduled_departure = dep_time
    journey.data_source = "METRA"
    journey.observation_type = "OBSERVED"
    journey.is_expired = False
    journey.is_completed = False
    journey.is_cancelled = False
    journey.cancellation_reason = None
    journey.last_updated_at = now
    journey.first_seen_at = now
    journey.update_count = 1
    journey.stops_count = 2

    from_stop = Mock(spec=JourneyStop)
    from_stop.station_code = "HARVARD"
    from_stop.station_name = "Harvard"
    from_stop.stop_sequence = 1
    from_stop.scheduled_departure = dep_time
    from_stop.scheduled_arrival = dep_time
    from_stop.updated_departure = None
    from_stop.updated_arrival = None
    from_stop.actual_departure = None
    from_stop.actual_arrival = None
    from_stop.track = None
    from_stop.has_departed_station = False

    to_stop = Mock(spec=JourneyStop)
    to_stop.station_code = "OTC"
    to_stop.station_name = "Chicago OTC"
    to_stop.stop_sequence = 2
    to_stop.scheduled_departure = dep_time + timedelta(hours=2)
    to_stop.scheduled_arrival = dep_time + timedelta(hours=2)
    to_stop.updated_departure = None
    to_stop.updated_arrival = None
    to_stop.actual_departure = None
    to_stop.actual_arrival = None
    to_stop.track = None
    to_stop.has_departed_station = False

    journey.stops = [from_stop, to_stop]
    return journey


@pytest.mark.asyncio
async def test_get_departures_returns_up_nw_train_without_validation_error():
    """The endpoint that crashed in production must now return the UP-NW
    departure with the full ``METRA-UP-NW`` line code.

    Before the fix, building ``LineInfo(code=journey.line_code)`` inside
    get_departures raised pydantic ValidationError -> HTTP 500.
    """
    journey = _create_metra_up_nw_journey()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = Mock()
    mock_scalars = Mock()
    mock_scalars.unique.return_value.all.return_value = [journey]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=None)

    service = DepartureService()

    train_position = TrainPosition(
        last_departed_station_code=None,
        at_station_code=None,
        next_station_code="HARVARD",
        between_stations=False,
    )

    with patch.object(
        service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
    ):
        with patch.object(
            service, "_get_path_cutoff_time", new_callable=AsyncMock
        ) as mock_cutoff:
            mock_cutoff.return_value = now_et() + timedelta(hours=2)
            with patch.object(
                service, "_calculate_train_position", return_value=train_position
            ):
                with patch("trackrat.services.gtfs.GTFSService") as mock_gtfs_class:
                    mock_gtfs = AsyncMock()
                    mock_gtfs.get_scheduled_departures = AsyncMock(
                        return_value=Mock(departures=[])
                    )
                    mock_gtfs_class.return_value = mock_gtfs

                    result = await service.get_departures(
                        db=mock_session,
                        from_station="HARVARD",
                        to_station="OTC",
                    )

    assert len(result.departures) == 1
    departure = result.departures[0]
    assert departure.train_id == "MT630"
    assert departure.line.code == "METRA-UP-NW", (
        "UP-NW line code must be returned in full; a truncated 'METRA-UP-N' "
        "would be indistinguishable from the separate UP-N line."
    )
