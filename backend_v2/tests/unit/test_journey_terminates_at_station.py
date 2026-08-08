"""Tests for ``journey_terminates_at_station`` — the guard that stops TrackRat
presenting a *departure* track prediction for a station a train only arrives at
(issue #1773).

Background:
  A rider whose selected route began at NY Penn opened NJT 7832 (Trenton → New
  York Penn) and was shown "Track Predictions" for Penn. 7832 terminates there:
  it arrives and never departs, so there is no boarding track to predict. The
  number shown came from the ``time_line_code`` level of
  ``HistoricalTrackPredictor`` — the distribution of tracks used by *other,
  southbound* Northeast Corridor trains scheduled to depart Penn within ±30
  minutes. That fallback is unavoidable rather than incidental: providers
  publish tracks for departures, so a terminal stop carries no ``track`` of its
  own (confirmed across NJT arrivals into Penn, including completed runs), the
  train-id level can never reach ``MIN_TRAIN_ID_RECORDS``, and the hierarchy
  falls through every time.

  The client sends the *user's* route origin as ``from_station`` on every train
  it opens, so any train terminating at the user's home station reaches this
  path — not just ones found by searching a train number.

These tests exercise the pure predicate with real ``JourneyStop`` model objects
and no database. The direction that must not regress is at least as important
as the fix itself: a train genuinely departing the station — including a
just-discovered one whose stops are not sequenced yet — must keep its
prediction.
"""

from __future__ import annotations

from trackrat.config.stations import expand_station_codes
from trackrat.models.database import JourneyStop
from trackrat.utils.train import journey_terminates_at_station


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


class TestTerminatingTrain:
    """The reported bug: the requested station is where the train ends."""

    def test_njt_7832_terminating_at_ny_penn_is_flagged(self):
        """The exact #1773 shape: Trenton → NY Penn, asked about NY Penn.

        Every stop is sequenced and ``terminal_station_code`` agrees with the
        last stop, so positional detection is trustworthy and NY is the arrival.
        """
        stops = _sequenced("TR", "HL", "PJ", "NB", "EWR", "SE", "NY")

        assert (
            journey_terminates_at_station(stops, "NY", {"NY"}) is True
        ), "NY Penn is 7832's terminal stop; it never departs there"

    def test_metro_north_terminating_at_grand_central_is_flagged(self):
        """Not NJT-specific: every inbound Metro-North run ends at GCT, which is
        also a prediction-enabled station, so the same shape reaches GCT users.
        """
        stops = _sequenced("MNSTMFD", "MNSNORW", "MNSSTAM", "MNS125", "GCT")

        assert journey_terminates_at_station(stops, "GCT", {"GCT"}) is True

    def test_two_stop_journey_terminal_is_flagged(self):
        """A minimal sequenced journey still resolves its terminal correctly."""
        stops = _sequenced("SE", "NY")

        assert journey_terminates_at_station(stops, "NY", {"NY"}) is True


class TestDepartingTrain:
    """Predictions must survive for every station the train actually leaves."""

    def test_origin_station_is_not_terminal(self):
        """The core boarding case — NY Penn → Trenton asked about NY Penn.

        This is what the track prediction exists for; flagging it would delete
        the feature at its most-used station.
        """
        stops = _sequenced("NY", "SE", "EWR", "NB", "PJ", "HL", "TR")

        assert (
            journey_terminates_at_station(stops, "TR", {"NY"}) is False
        ), "NY Penn is the origin here — the train departs and must keep its prediction"

    def test_intermediate_station_is_not_terminal(self):
        """An Amtrak run through NY Penn boards there mid-journey."""
        stops = _sequenced("BOS", "NHV", "STM", "NY", "NWK", "PHL", "WAS")

        assert journey_terminates_at_station(stops, "WAS", {"NY"}) is False

    def test_station_not_served_at_all_is_not_terminal(self):
        """A station the journey never touches is not its terminal."""
        stops = _sequenced("HB", "NP", "TR")

        assert journey_terminates_at_station(stops, "TR", {"NY"}) is False

    def test_same_named_station_earlier_in_a_longer_journey(self):
        """Matching must be positional, not "does the terminal code appear".

        A journey whose terminal is TR passes through NY first; asked about NY
        the answer is still False even though NY is a terminal *elsewhere*.
        """
        stops = _sequenced("NY", "SE", "TR")

        assert journey_terminates_at_station(stops, "TR", {"NY"}) is False


class TestUntrustworthyPositionalDetection:
    """When the journey's shape isn't known, fail toward serving predictions.

    ``terminal_stop_index`` only trusts the last stop on a fully-sequenced
    journey whose ``terminal_station_code`` matches it. NJT discovery and
    schedule rows carry ``stop_sequence = NULL`` and a placeholder terminal
    until full collection, and those are exactly the pre-departure trains whose
    prediction matters most.
    """

    def test_single_unsequenced_discovery_stop_keeps_prediction(self):
        """The regression this guard could most easily cause.

        A train discovered on the NY Penn departure board has one stop, NULL
        sequence — trivially "the last stop". Treating that as an arrival would
        suppress predictions for boarding trains at Penn, the opposite of #1773.
        """
        stops = [_stop("NY", None)]

        assert (
            journey_terminates_at_station(stops, "NY", {"NY"}) is False
        ), "an unsequenced discovery stop proves nothing about journey shape"

    def test_partially_collected_journey_keeps_prediction(self):
        """Some stops sequenced, a discovery stop appended with NULL sequence."""
        stops = [*_sequenced("NY", "SE", "EWR"), _stop("NP", None)]

        assert journey_terminates_at_station(stops, "NP", {"NP"}) is False

    def test_placeholder_terminal_code_keeps_prediction(self):
        """Sequenced stops, but ``terminal_station_code`` is still the discovery
        placeholder and disagrees with the last stop — shape not yet proven.
        """
        stops = _sequenced("TR", "HL", "PJ", "NY")

        assert journey_terminates_at_station(stops, "TR", {"NY"}) is False

    def test_no_stops_keeps_prediction(self):
        """A journey row with no stops yet can't prove anything either."""
        assert journey_terminates_at_station([], "NY", {"NY"}) is False

    def test_null_terminal_code_keeps_prediction(self):
        stops = _sequenced("TR", "HL", "NY")

        assert journey_terminates_at_station(stops, None, {"NY"}) is False


class TestStationEquivalence:
    """Callers pass an equivalence-expanded set, so a station stored under a
    sibling code still matches."""

    def test_terminal_matches_via_expanded_codes(self):
        """Hoboken: the canonical code and its PATH-side equivalent name one
        physical station, so a journey terminating under either code is an
        arrival for a rider who asked about the other.
        """
        equivalents = set(expand_station_codes("HB"))
        assert len(equivalents) > 1, (
            "this test needs HB to actually have equivalents; "
            f"expand_station_codes('HB') returned {sorted(equivalents)}"
        )
        sibling = sorted(equivalents - {"HB"})[0]
        stops = _sequenced("SUF", "MP", sibling)

        assert (
            journey_terminates_at_station(stops, sibling, equivalents) is True
        ), f"terminal stored as {sibling} must match a request for HB"

    def test_unexpanded_single_code_still_matches_itself(self):
        """The plain case: no equivalence involved."""
        stops = _sequenced("TR", "NY")

        assert journey_terminates_at_station(stops, "NY", {"NY"}) is True
