"""
Unit tests for _detect_at_station and the JourneyProgress optimization path
in _calculate_train_position.

These tests verify that at_station_code is correctly computed for:
1. NJT trains with track assignments (at-station when track assigned + not departed)
2. Amtrak trains with "Station" raw status
3. Providers without at-station signals (PATH, LIRR, Subway, etc.)
4. Completed journeys (at terminal station)
5. The JourneyProgress optimization path (previously hardcoded at_station_code=None)

The JourneyProgress bug: when the `progress` relationship was loaded on a
TrainJourney (e.g., as a side effect of JIT refresh loading `progress_snapshots`),
_calculate_train_position took an optimization shortcut that returned
at_station_code=None, breaking boarding detection for NJT and Amtrak trains.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm.base import NO_VALUE

from trackrat.models.api import TrainPosition
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService, _detect_at_station


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stop(
    station_code: str,
    stop_sequence: int,
    has_departed_station: bool = False,
    track: str | None = None,
    raw_amtrak_status: str | None = None,
) -> Mock:
    """Create a mock JourneyStop with the fields _detect_at_station reads."""
    stop = Mock(spec=JourneyStop)
    stop.station_code = station_code
    stop.stop_sequence = stop_sequence
    stop.has_departed_station = has_departed_station
    stop.track = track
    stop.raw_amtrak_status = raw_amtrak_status
    return stop


def _make_journey(
    data_source: str,
    stops: list[Mock],
    train_id: str = "1234",
) -> Mock:
    """Create a mock TrainJourney with the fields _detect_at_station reads."""
    journey = Mock(spec=TrainJourney)
    journey.train_id = train_id
    journey.data_source = data_source
    journey.stops = stops
    return journey


# ---------------------------------------------------------------------------
# _detect_at_station tests
# ---------------------------------------------------------------------------

class TestDetectAtStation:
    """Tests for the _detect_at_station helper function."""

    def test_njt_track_assigned_at_origin_means_at_station(self):
        """NJT: track assigned on undeparted stop -> at_station_code is that stop."""
        stops = [
            _make_stop("NY", 0, has_departed_station=False, track="9"),
            _make_stop("SE", 1, has_departed_station=False),
            _make_stop("NP", 2, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops)

        result = _detect_at_station(journey)

        assert result == "NY", (
            f"Expected at_station_code='NY' when track assigned at undeparted origin, "
            f"got '{result}'"
        )

    def test_njt_track_assigned_at_intermediate_stop(self):
        """NJT: track assigned at an intermediate undeparted stop."""
        stops = [
            _make_stop("NY", 0, has_departed_station=True),
            _make_stop("NP", 1, has_departed_station=False, track="4"),
            _make_stop("TR", 2, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops)

        result = _detect_at_station(journey)

        assert result == "NP", (
            f"Expected at_station_code='NP' when track assigned at undeparted intermediate stop, "
            f"got '{result}'"
        )

    def test_njt_no_track_means_not_at_station(self):
        """NJT: no track assigned -> at_station_code is None."""
        stops = [
            _make_stop("NY", 0, has_departed_station=False, track=None),
            _make_stop("SE", 1, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops)

        result = _detect_at_station(journey)

        assert result is None, (
            f"Expected None when NJT stop has no track assigned, got '{result}'"
        )

    def test_njt_departed_with_track_is_not_at_station(self):
        """NJT: track assigned but already departed -> skip to next undeparted stop."""
        stops = [
            _make_stop("NY", 0, has_departed_station=True, track="9"),
            _make_stop("SE", 1, has_departed_station=False, track=None),
        ]
        journey = _make_journey("NJT", stops)

        result = _detect_at_station(journey)

        assert result is None, (
            f"Expected None when departed stop has track but next stop doesn't, "
            f"got '{result}'"
        )

    def test_amtrak_at_station_status(self):
        """Amtrak: raw_amtrak_status='Station' -> at_station_code."""
        stops = [
            _make_stop("NYP", 0, has_departed_station=True),
            _make_stop("NWK", 1, has_departed_station=False, raw_amtrak_status="Station"),
            _make_stop("TRE", 2, has_departed_station=False),
        ]
        journey = _make_journey("AMTRAK", stops)

        result = _detect_at_station(journey)

        assert result == "NWK", (
            f"Expected at_station_code='NWK' for Amtrak station status, got '{result}'"
        )

    def test_amtrak_enroute_not_at_station(self):
        """Amtrak: raw_amtrak_status='Enroute' -> not at station."""
        stops = [
            _make_stop("NYP", 0, has_departed_station=True),
            _make_stop("NWK", 1, has_departed_station=False, raw_amtrak_status="Enroute"),
        ]
        journey = _make_journey("AMTRAK", stops)

        result = _detect_at_station(journey)

        assert result is None, (
            f"Expected None for Amtrak 'Enroute' status, got '{result}'"
        )

    def test_path_never_returns_at_station(self):
        """PATH: no at-station signal available -> always None."""
        stops = [
            _make_stop("WTC", 0, has_departed_station=True),
            _make_stop("EXP", 1, has_departed_station=False, track="A"),
        ]
        journey = _make_journey("PATH", stops)

        result = _detect_at_station(journey)

        assert result is None, (
            f"Expected None for PATH (no at-station signal), got '{result}'"
        )

    def test_subway_never_returns_at_station(self):
        """Subway: no at-station signal available -> always None."""
        stops = [
            _make_stop("A01", 0, has_departed_station=True),
            _make_stop("A02", 1, has_departed_station=False),
        ]
        journey = _make_journey("SUBWAY", stops)

        result = _detect_at_station(journey)

        assert result is None

    def test_completed_journey_at_terminal(self):
        """All stops departed -> train is at its final station."""
        stops = [
            _make_stop("NY", 0, has_departed_station=True),
            _make_stop("SE", 1, has_departed_station=True),
            _make_stop("NP", 2, has_departed_station=True),
        ]
        journey = _make_journey("NJT", stops)

        result = _detect_at_station(journey)

        assert result == "NP", (
            f"Expected at_station_code='NP' for completed journey at terminal, "
            f"got '{result}'"
        )

    def test_no_stops_returns_none(self):
        """No stops at all -> None."""
        journey = _make_journey("NJT", [])

        result = _detect_at_station(journey)

        assert result is None

    def test_none_stops_returns_none(self):
        """Stops is None -> None."""
        journey = _make_journey("NJT", [])
        journey.stops = None

        result = _detect_at_station(journey)

        assert result is None


# ---------------------------------------------------------------------------
# _calculate_train_position tests (JourneyProgress path)
# ---------------------------------------------------------------------------

class TestCalculateTrainPositionProgressPath:
    """
    Tests that _calculate_train_position correctly computes at_station_code
    even when the JourneyProgress optimization path is taken.

    This is the regression test for the bug where at_station_code was hardcoded
    to None in the JourneyProgress path, preventing boarding detection.

    We patch sqlalchemy.inspect since our journeys are Mock objects, not
    real SQLAlchemy mapped instances.
    """

    def setup_method(self):
        self.service = DepartureService.__new__(DepartureService)

    def _mock_inspect_state(
        self,
        stops: list[Mock],
        progress=NO_VALUE,
    ) -> Mock:
        """Create a mock SQLAlchemy inspection state."""
        state = Mock()
        state.attrs.stops.loaded_value = stops
        state.attrs.progress.loaded_value = progress
        return state

    @patch("sqlalchemy.inspect")
    def test_progress_path_preserves_njt_at_station(self, mock_inspect):
        """
        Regression test: when JourneyProgress is loaded (e.g., after JIT refresh),
        at_station_code should still be detected from stops for NJT trains
        with a track assignment.
        """
        from trackrat.models.database import JourneyProgress

        stops = [
            _make_stop("NY", 0, has_departed_station=False, track="9"),
            _make_stop("SE", 1, has_departed_station=False),
            _make_stop("NP", 2, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops, train_id="7869")

        progress = Mock(spec=JourneyProgress)
        progress.last_departed_station = None
        progress.next_station = "NY"

        mock_inspect.return_value = self._mock_inspect_state(stops, progress)

        result = self.service._calculate_train_position(journey)

        assert result.at_station_code == "NY", (
            f"REGRESSION: JourneyProgress path returned at_station_code="
            f"'{result.at_station_code}' instead of 'NY'. "
            f"The JourneyProgress optimization must not suppress at_station_code."
        )
        assert result.between_stations is False, (
            "Train at a station should not be marked as between_stations"
        )

    @patch("sqlalchemy.inspect")
    def test_progress_path_preserves_amtrak_at_station(self, mock_inspect):
        """Amtrak at-station detection works through JourneyProgress path."""
        from trackrat.models.database import JourneyProgress

        stops = [
            _make_stop("NYP", 0, has_departed_station=True),
            _make_stop("NWK", 1, has_departed_station=False, raw_amtrak_status="Station"),
            _make_stop("TRE", 2, has_departed_station=False),
        ]
        journey = _make_journey("AMTRAK", stops)

        progress = Mock(spec=JourneyProgress)
        progress.last_departed_station = "NYP"
        progress.next_station = "NWK"

        mock_inspect.return_value = self._mock_inspect_state(stops, progress)

        result = self.service._calculate_train_position(journey)

        assert result.at_station_code == "NWK", (
            f"REGRESSION: JourneyProgress path returned at_station_code="
            f"'{result.at_station_code}' instead of 'NWK' for Amtrak."
        )

    @patch("sqlalchemy.inspect")
    def test_progress_path_no_at_station_when_no_signal(self, mock_inspect):
        """PATH train via progress path -> at_station_code remains None."""
        from trackrat.models.database import JourneyProgress

        stops = [
            _make_stop("WTC", 0, has_departed_station=True),
            _make_stop("EXP", 1, has_departed_station=False),
        ]
        journey = _make_journey("PATH", stops)

        progress = Mock(spec=JourneyProgress)
        progress.last_departed_station = "WTC"
        progress.next_station = "EXP"

        mock_inspect.return_value = self._mock_inspect_state(stops, progress)

        result = self.service._calculate_train_position(journey)

        assert result.at_station_code is None
        assert result.between_stations is True

    @patch("sqlalchemy.inspect")
    def test_progress_path_uses_progress_for_last_departed_and_next(self, mock_inspect):
        """Progress path should still use JourneyProgress for last_departed/next."""
        from trackrat.models.database import JourneyProgress

        stops = [
            _make_stop("NY", 0, has_departed_station=False, track="9"),
            _make_stop("SE", 1, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops, train_id="7869")

        progress = Mock(spec=JourneyProgress)
        progress.last_departed_station = None
        progress.next_station = "NY"

        mock_inspect.return_value = self._mock_inspect_state(stops, progress)

        result = self.service._calculate_train_position(journey)

        # last_departed and next should come from progress, not stops
        assert result.last_departed_station_code is None
        assert result.next_station_code == "NY"
        assert result.at_station_code == "NY"

    @patch("sqlalchemy.inspect")
    def test_fallback_path_when_no_progress(self, mock_inspect):
        """When progress is not loaded, falls back to stops-based calculation."""
        stops = [
            _make_stop("NY", 0, has_departed_station=True, track="9"),
            _make_stop("SE", 1, has_departed_station=False),
            _make_stop("NP", 2, has_departed_station=False),
        ]
        journey = _make_journey("NJT", stops)

        # Simulate progress not loaded (NO_VALUE)
        mock_inspect.return_value = self._mock_inspect_state(stops, progress=NO_VALUE)

        result = self.service._calculate_train_position(journey)

        assert result.last_departed_station_code == "NY"
        assert result.next_station_code == "SE"
        assert result.at_station_code is None  # SE has no track
        assert result.between_stations is True

    @patch("sqlalchemy.inspect")
    def test_fallback_path_with_no_stops_loaded(self, mock_inspect):
        """When stops aren't loaded, returns empty TrainPosition."""
        journey = _make_journey("NJT", [])

        mock_inspect.return_value = self._mock_inspect_state(
            stops=NO_VALUE, progress=NO_VALUE,
        )

        result = self.service._calculate_train_position(journey)

        assert result.at_station_code is None
        assert result.last_departed_station_code is None
        assert result.next_station_code is None
        assert result.between_stations is False
