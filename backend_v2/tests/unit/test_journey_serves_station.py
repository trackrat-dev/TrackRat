"""Tests for ``journey_serves_station`` — the companion guard to
``journey_terminates_at_station`` that stops TrackRat presenting a *departure*
track prediction for a station a train never visits at all.

Background:
  #1773 established that the predictor's fallback hierarchy cannot suppress a
  meaningless prediction on its own — with no history for the train at the
  station it answers from *other* trains' platforms. The terminal guard covers
  "the train ends here"; this predicate covers the second way the same failure
  shape is reached: the requested station simply isn't on the route, so the
  static / service-distribution fallbacks would serve somebody else's tracks.

These tests exercise the pure predicate with real ``JourneyStop`` model objects
and no database, mirroring ``test_journey_terminates_at_station.py``. The
fail-open direction is deliberately identical and at least as important as the
guard itself: an NJT discovery/schedule row has an incomplete stop list, so a
station missing from it may still be served — those journeys must keep their
prediction (return ``True``), and only a fully-collected journey may prove a
station unserved (return ``False``).
"""

from __future__ import annotations

from trackrat.config.stations import expand_station_codes
from trackrat.models.database import JourneyStop
from trackrat.utils.train import journey_serves_station


def _stop(station_code: str, stop_sequence: int | None) -> JourneyStop:
    """A bare stop carrying only what the predicate reads. Not persisted."""
    return JourneyStop(
        station_code=station_code,
        station_name=station_code,
        stop_sequence=stop_sequence,
    )


def _sequenced(*station_codes: str) -> list[JourneyStop]:
    """Stops for a fully-collected journey, sequenced 0..n-1 in travel order."""
    return [_stop(code, index) for index, code in enumerate(station_codes)]


class TestServedStation:
    """Any station the train actually calls at — origin, intermediate, or
    terminal — is served, and the prediction path stays open (the terminal
    guard, not this one, decides what happens at the terminal)."""

    def test_origin_station_is_served(self):
        """NY Penn → Trenton asked about NY Penn: the boarding case the track
        prediction exists for."""
        stops = _sequenced("NY", "SE", "EWR", "NB", "PJ", "HL", "TR")

        assert (
            journey_serves_station(stops, "TR", {"NY"}) is True
        ), "the origin is on the route; the guard must not fire"

    def test_intermediate_station_is_served(self):
        """An Amtrak run through NY Penn boards there mid-journey."""
        stops = _sequenced("BOS", "NHV", "STM", "NY", "NWK", "PHL", "WAS")

        assert journey_serves_station(stops, "WAS", {"NY"}) is True

    def test_terminal_station_is_served(self):
        """The terminal is still a *served* stop — arrival-vs-departure is the
        terminal guard's question, not this predicate's."""
        stops = _sequenced("TR", "HL", "PJ", "NY")

        assert journey_serves_station(stops, "NY", {"NY"}) is True


class TestUnservedStation:
    """Only a fully-collected journey may prove a station off the route."""

    def test_station_off_the_route_is_unserved(self):
        """The new guard's trigger: an NEC run asked about Hoboken, which the
        line never touches. Every stop is sequenced and the last one agrees
        with ``terminal_station_code``, so the route shape is proven and the
        absence is real."""
        stops = _sequenced("NY", "SE", "EWR", "NB", "PJ", "HL", "TR")

        assert (
            journey_serves_station(stops, "TR", {"HB"}) is False
        ), "HB is not on this fully-sequenced route; predictions there would be other trains'"

    def test_two_stop_journey_still_proves_absence(self):
        """A minimal sequenced journey is enough to prove a third station off it."""
        stops = _sequenced("SE", "NY")

        assert journey_serves_station(stops, "NY", {"TR"}) is False


class TestUntrustworthyPositionalDetection:
    """When the journey's shape isn't known, fail toward serving predictions.

    The trust conditions are exactly ``terminal_stop_index``'s — the same ones
    the terminal guard uses. NJT discovery and schedule rows carry
    ``stop_sequence = NULL`` and a placeholder terminal until full collection;
    their stop lists are incomplete, so "not in the list" proves nothing.
    """

    def test_single_unsequenced_discovery_stop_keeps_prediction(self):
        """The regression this guard could most easily cause.

        A train discovered at NY Penn has one stop, NULL sequence. A rider
        asking about any *other* station on its (uncollected) route would find
        it absent from the list; 404ing there would strip predictions from
        exactly the pre-departure trains that matter most.
        """
        stops = [_stop("NY", None)]

        assert (
            journey_serves_station(stops, "NY", {"TR"}) is True
        ), "an unsequenced discovery stop list is incomplete — absence proves nothing"

    def test_partially_collected_journey_keeps_prediction(self):
        """Some stops sequenced, a discovery stop appended with NULL sequence."""
        stops = [*_sequenced("NY", "SE", "EWR"), _stop("NP", None)]

        assert journey_serves_station(stops, "EWR", {"TR"}) is True

    def test_placeholder_terminal_code_keeps_prediction(self):
        """Sequenced stops, but ``terminal_station_code`` is still the
        discovery placeholder and disagrees with the last stop — shape not yet
        proven, so an absent station may still be served later in the run."""
        stops = _sequenced("TR", "HL", "PJ", "NY")

        assert journey_serves_station(stops, "TR", {"HB"}) is True

    def test_no_stops_keeps_prediction(self):
        """A journey row with no stops yet can't prove anything either."""
        assert journey_serves_station([], "NY", {"HB"}) is True

    def test_null_terminal_code_keeps_prediction(self):
        stops = _sequenced("TR", "HL", "NY")

        assert journey_serves_station(stops, None, {"HB"}) is True


class TestStationEquivalence:
    """Callers pass an equivalence-expanded set, so a station stored under a
    sibling code still counts as served."""

    def test_station_matches_via_expanded_codes(self):
        """Hoboken: a journey that stores the PATH-side sibling code still
        serves a rider who asked about HB."""
        equivalents = set(expand_station_codes("HB"))
        assert len(equivalents) > 1, (
            "this test needs HB to actually have equivalents; "
            f"expand_station_codes('HB') returned {sorted(equivalents)}"
        )
        sibling = sorted(equivalents - {"HB"})[0]
        stops = _sequenced("SUF", sibling, "MP")

        assert (
            journey_serves_station(stops, "MP", equivalents) is True
        ), f"a stop stored as {sibling} must count as serving HB"

    def test_unexpanded_single_code_still_matches_itself(self):
        """The plain case: no equivalence involved."""
        stops = _sequenced("TR", "NY")

        assert journey_serves_station(stops, "NY", {"TR"}) is True
