"""Tests for ``stop_sequence_sort_key`` — the nulls-last ordering key that keeps
a NULL ``stop_sequence`` from collapsing to 0 at serve time (issue #1536).

Background:
  Discovery-created NJT stops carry ``stop_sequence = NULL`` until the next full
  collection assigns one. The historical ``key=lambda s: s.stop_sequence or 0``
  idiom collapsed NULL to 0, so an unsequenced stop *tied with the origin*
  (sequence 0) and floated to the top of a stops list — the exact shape behind
  #1530 ("Newark Penn before Secaucus") and the from/to misclassification in
  #1536. ``stop_sequence_sort_key`` orders such stops last instead, while leaving
  every fully-sequenced journey ordered exactly as before.

These tests exercise the pure key and the real serve-path functions that use it
(``get_first_stop_code``/``get_first_stop_name``/``count_stops_between``/
``calculate_train_position`` in ``api/trains.py``, and the train-details /
share-preview sort expression) with real model objects and no database.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from trackrat.api.trains import (
    calculate_train_position,
    count_stops_between,
    get_first_stop_code,
    get_first_stop_name,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.train import stop_sequence_sort_key


def _stop(
    station_code: str,
    stop_sequence: int | None,
    *,
    station_name: str | None = None,
    has_departed_station: bool = False,
) -> JourneyStop:
    return JourneyStop(
        station_code=station_code,
        station_name=station_name or station_code,
        stop_sequence=stop_sequence,
        has_departed_station=has_departed_station,
    )


def _journey(stops: list[JourneyStop], data_source: str = "NJT") -> TrainJourney:
    """Synthesize a TrainJourney for pure-function tests. Not persisted."""
    j = TrainJourney(
        train_id="3701",
        journey_date=date(2026, 7, 16),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Metropark",
        origin_station_code="NY",
        terminal_station_code="MP",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=datetime(2026, 7, 16, 18, 0, tzinfo=UTC),
    )
    j.stops = stops
    return j


class TestSortKeyShape:
    """The key itself: NULL sorts last, real sequences keep their natural order."""

    def test_real_sequence_returns_not_none_flag_and_value(self) -> None:
        assert stop_sequence_sort_key(_stop("NY", 0)) == (False, 0)
        assert stop_sequence_sort_key(_stop("NP", 3)) == (False, 3)

    def test_null_sequence_sorts_after_every_real_sequence(self) -> None:
        null_key = stop_sequence_sort_key(_stop("SE", None))
        assert null_key == (True, 0)
        # A NULL key compares greater than any real key, however large.
        assert null_key > stop_sequence_sort_key(_stop("NY", 0))
        assert null_key > stop_sequence_sort_key(_stop("MP", 999))

    def test_matches_legacy_or_0_order_for_fully_sequenced_journeys(self) -> None:
        # For all-non-null journeys the new key must be a drop-in: same order as
        # the old ``s.stop_sequence or 0``. Shuffled input, both keys, same result.
        stops = [_stop("MP", 4), _stop("NY", 0), _stop("NP", 2), _stop("SE", 1)]
        legacy = [s.station_code for s in sorted(stops, key=lambda s: s.stop_sequence or 0)]
        new = [s.station_code for s in sorted(stops, key=stop_sequence_sort_key)]
        assert new == legacy == ["NY", "SE", "NP", "MP"]


class TestTrainDetailRenderOrder:
    """Acceptance criterion 1: a NULL-seq stop never renders above the origin.

    Reproduces #1530 exactly: NY Penn (origin, sequence 0), Newark Penn (fully
    sequenced), and a discovery-populated Secaucus (``stop_sequence = None``).
    The train-details endpoint renders ``sorted(journey.stops, key=...)`` verbatim.
    """

    def _sorted_codes(self, stops: list[JourneyStop]) -> list[str]:
        # The exact expression api/trains.py uses to build the stops list.
        return [s.station_code for s in sorted(stops, key=stop_sequence_sort_key)]

    def test_discovery_stop_does_not_render_above_origin(self) -> None:
        ny = _stop("NY", 0)
        secaucus = _stop("SE", None)  # discovery-created, not yet sequenced
        newark = _stop("NP", 1)
        # Insertion order deliberately puts the NULL stop first — the old sort
        # would have left it at/near the top (tied with NY at 0).
        order = self._sorted_codes([secaucus, ny, newark])
        assert order[0] == "NY", "origin must render first"
        assert order.index("NY") < order.index("SE"), "Secaucus rendered above origin"
        assert order == ["NY", "NP", "SE"]

    def test_legacy_or_0_key_reproduces_the_bug(self) -> None:
        # Guard-rail: prove the scenario is real. With the old key the NULL stop
        # ties the origin at 0 and (stable sort) keeps its leading insertion slot.
        ny = _stop("NY", 0)
        secaucus = _stop("SE", None)
        newark = _stop("NP", 1)
        buggy = [
            s.station_code
            for s in sorted([secaucus, ny, newark], key=lambda s: s.stop_sequence or 0)
        ]
        assert buggy[0] == "SE"  # the reported "Newark/Secaucus out of order" shape


class TestOriginSelection:
    """A NULL-seq discovery stop must not be chosen as the journey origin.

    ``get_first_stop_*`` use ``min(journey.stops, key=stop_sequence_sort_key)``.
    With the old ``or 0`` key the NULL stop tied the real origin at 0 and could
    win the ``min`` depending on iteration order.
    """

    def test_first_stop_code_is_real_origin_not_null_stop(self) -> None:
        journey = _journey([_stop("SE", None), _stop("NY", 0), _stop("NP", 1)])
        assert get_first_stop_code(journey) == "NY"

    def test_first_stop_name_is_real_origin_not_null_stop(self) -> None:
        journey = _journey(
            [
                _stop("SE", None, station_name="Secaucus"),
                _stop("NY", 0, station_name="New York Penn"),
            ]
        )
        assert get_first_stop_name(journey) == "New York Penn"

    def test_all_null_sequences_still_returns_a_stop(self) -> None:
        # Fully undiscovered journey (every sequence NULL): min is well-defined
        # and returns some stop rather than raising.
        journey = _journey([_stop("NY", None), _stop("NP", None)])
        assert get_first_stop_code(journey) in {"NY", "NP"}


class TestCountStopsBetween:
    """Acceptance criterion 2 (from/to comparison): explicit NULL semantics.

    ``count_stops_between`` uses the chained ``key(from) < key(stop) < key(to)``
    comparison. A NULL-seq intermediate stop sorts *after* both real endpoints
    (nulls-last), so it is deliberately not counted as "between" them.
    """

    def test_counts_real_intermediate_stops(self) -> None:
        journey = _journey(
            [_stop("NY", 0), _stop("SE", 1), _stop("NP", 2), _stop("MP", 3)]
        )
        from_stop, to_stop = journey.stops[0], journey.stops[3]
        assert count_stops_between(journey, from_stop, to_stop) == 2

    def test_null_sequence_intermediate_is_not_counted_between(self) -> None:
        # SE has an unknown position → nulls-last → not between NY(0) and MP(3).
        journey = _journey(
            [_stop("NY", 0), _stop("SE", None), _stop("NP", 2), _stop("MP", 3)]
        )
        from_stop = journey.stops[0]
        to_stop = journey.stops[3]
        # Only NP (sequence 2) is unambiguously between NY and MP.
        assert count_stops_between(journey, from_stop, to_stop) == 1


class TestFromToDirectionSemantics:
    """The shared from/to predicate used across departure/route/summary logic:
    ``stop_sequence_sort_key(a) > stop_sequence_sort_key(b)`` (nulls-last)."""

    def test_real_destination_after_real_origin(self) -> None:
        origin, dest = _stop("NY", 0), _stop("MP", 5)
        assert stop_sequence_sort_key(dest) > stop_sequence_sort_key(origin)

    def test_real_destination_before_origin_is_not_after(self) -> None:
        origin, dest = _stop("MP", 5), _stop("NY", 0)
        assert not (stop_sequence_sort_key(dest) > stop_sequence_sort_key(origin))

    def test_null_destination_sorts_after_real_origin(self) -> None:
        # A discovery-created destination (unknown position) is treated as
        # after the boarding stop under the nulls-last convention.
        origin, dest = _stop("NY", 0), _stop("SE", None)
        assert stop_sequence_sort_key(dest) > stop_sequence_sort_key(origin)

    def test_real_destination_is_not_after_null_origin(self) -> None:
        # If the boarding stop itself is unsequenced it sorts last, so nothing
        # is "after" it — conservative, no false ordering asserted.
        origin, dest = _stop("NY", None), _stop("MP", 5)
        assert not (stop_sequence_sort_key(dest) > stop_sequence_sort_key(origin))


class TestCalculateTrainPosition:
    """A NULL-seq discovery stop must not become the spurious "next station".

    ``calculate_train_position`` walks ``sorted(journey.stops, key=...)`` for the
    first undeparted stop. Under the old ``or 0`` key an unsequenced stop tied the
    origin at 0 and could be visited before the real next stop.
    """

    def test_next_station_is_real_stop_not_null_discovery_stop(self) -> None:
        journey = _journey(
            [
                _stop("SE", None),  # discovery, undeparted, unknown position
                _stop("NY", 0, has_departed_station=True),
                _stop("NP", 1),  # real next stop
            ]
        )
        position = calculate_train_position(journey)
        assert position.last_departed_station_code == "NY"
        assert position.next_station_code == "NP"
