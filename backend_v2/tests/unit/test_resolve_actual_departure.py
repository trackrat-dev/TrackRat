"""Tests for ``resolve_actual_departure`` — the rule that decides what
``JourneyStop.actual_departure`` may hold.

Background (regression-protects issue #1768):
  A rider on NJT train 7825 (NY→TR, running 35 minutes late) reported that
  "a few stops are showing 30+ minute delays but some are showing no delays".
  Six of its eleven departed stops carried an ``actual_departure`` exactly
  equal to their ``scheduled_departure``, five of them recording a departure
  37–46 minutes *before* the arrival recorded at that same stop.

  Two writers produced it. ``DepartureService._update_stops_from_embedded_data``
  assigned ``stop.scheduled_arrival or stop.scheduled_departure`` — the comment
  intended the live TIME estimate, but ``scheduled_arrival`` is a different
  column and is almost always NULL for NJT, so every departed stop got its
  timetable. NJT's tiers 1 and 2 in ``collect_journey_details`` fell back to
  ``scheduled_departure`` whenever the live estimate was not yet in the past,
  which for a delayed train is the normal case at the moment NJT first flips
  ``DEPARTED=YES``.

  A scheduled time in the actuals column is indistinguishable from a train that
  ran on time, so the stop's delay computes to zero everywhere: the train-detail
  row drops its delay badge, ``summary`` counts the train as punctual, and the
  segment analyzer measures the following hop from the scheduled time.

The two halves of the rule tested here are therefore:
  * never write the timetable, and never write a time that has not happened yet
    (``departed_stop_time``'s past-only guard);
  * freeze the first real capture — NJT revises estimates for hours — *except*
    when the stored value precedes the arrival recorded at the same stop, which
    is impossible and would otherwise stay corrupt forever, since both writers
    only ever filled a NULL.

Naive-datetime cases are not academic: stop times reach this helper from the
database (naive, Eastern by the ``utils.time.ensure_timezone_aware``
convention) and from the NJT client (tz-aware ET), so a comparison that did not
normalize would raise ``TypeError`` mid-collection.
"""

from __future__ import annotations

from datetime import timedelta

from trackrat.utils.time import now_et
from trackrat.utils.train import resolve_actual_departure


class TestNoStoredValue:
    """First write: record a real past observation, or nothing at all."""

    def test_records_past_observation(self):
        now = now_et()
        observed = now - timedelta(minutes=3)

        result = resolve_actual_departure(None, observed, None, now)

        print(f"  - observed (3 min ago): {observed}")
        print(f"  - resolved: {result}")
        assert result == observed, "a past live reading is the value to record"

    def test_future_observation_records_nothing(self):
        """The exact shape that produced #1768.

        NJT flags DEPARTED=YES while its live estimate for the stop still sits
        in the future. The old code answered that by writing
        ``scheduled_departure``; the correct answer is to write nothing and let
        a later cycle, when the estimate has moved into the past, record it.
        """
        now = now_et()
        observed = now + timedelta(minutes=2)

        result = resolve_actual_departure(None, observed, None, now)

        print(f"  - observed (2 min in the future): {observed}")
        print(f"  - resolved: {result}")
        assert result is None, (
            "a live estimate that has not happened yet must not be recorded, "
            "and must not be replaced by the schedule"
        )

    def test_missing_observation_records_nothing(self):
        now = now_et()

        assert resolve_actual_departure(None, None, None, now) is None


class TestFreeze:
    """A stored real capture is not revised by later NJT estimates."""

    def test_keeps_stored_value_against_later_revision(self):
        """NJT keeps revising TIME after a train passes; the reading taken while
        the train was at the stop is the accurate one."""
        now = now_et()
        captured = now - timedelta(minutes=30)
        revised = now - timedelta(minutes=25)

        result = resolve_actual_departure(captured, revised, None, now)

        print(f"  - stored at the stop: {captured}")
        print(f"  - NJT's later revision: {revised}")
        print(f"  - resolved: {result}")
        assert result == captured, "the first real capture must win"

    def test_keeps_stored_value_when_observation_missing(self):
        now = now_et()
        captured = now - timedelta(minutes=30)

        assert resolve_actual_departure(captured, None, None, now) == captured

    def test_keeps_stored_value_consistent_with_arrival(self):
        """Departure at or after arrival is the ordinary, valid case."""
        now = now_et()
        arrival = now - timedelta(minutes=20)
        departure = arrival + timedelta(seconds=40)

        result = resolve_actual_departure(
            departure, now - timedelta(minutes=1), arrival, now
        )

        assert result == departure, "a dwell of 40s is normal, not corruption"

    def test_keeps_stored_value_equal_to_arrival(self):
        """NJT publishes one TIME per stop, so departure == arrival is the norm
        for an intermediate stop and must not be treated as inverted."""
        now = now_et()
        arrival = now - timedelta(minutes=20)

        result = resolve_actual_departure(
            arrival, now - timedelta(minutes=1), arrival, now
        )

        assert result == arrival


class TestRepairsImpossibleOrdering:
    """A departure recorded before the arrival at the same stop is replaced."""

    def test_replaces_inverted_value_with_live_reading(self):
        """Train 7825 at Newark Airport, as served by production on 2026-08-08:
        actual_departure 08:38:30 (its schedule) against actual_arrival
        09:15:30 — the train left 37 minutes before it got there."""
        now = now_et()
        arrival = now - timedelta(minutes=38)
        corrupt = arrival - timedelta(minutes=37)  # the scheduled departure
        observed = now - timedelta(minutes=37)

        result = resolve_actual_departure(corrupt, observed, arrival, now)

        print(f"  - stored (schedule): {corrupt}")
        print(f"  - recorded arrival:  {arrival}")
        print(f"  - live reading:      {observed}")
        print(f"  - resolved:          {result}")
        assert result == observed, (
            "a departure before the arrival at the same stop cannot be true and "
            "must not be frozen — the freeze is what made #1768 permanent"
        )

    def test_clears_inverted_value_when_no_reading_is_admissible(self):
        """Clearing is a repair, not a loss: every consumer has an honest
        fallback (coalesce to the schedule on the departure board,
        ``actual_departure or actual_arrival`` in the segment analyzer, the live
        estimate branch in summary). Keeping the impossible value instead makes
        a late train read as punctual."""
        now = now_et()
        arrival = now - timedelta(minutes=38)
        corrupt = arrival - timedelta(minutes=37)

        result = resolve_actual_departure(
            corrupt, now + timedelta(minutes=5), arrival, now
        )

        print(f"  - stored (schedule): {corrupt}")
        print(f"  - recorded arrival:  {arrival}")
        print("  - live reading:      in the future (inadmissible)")
        print(f"  - resolved:          {result}")
        assert result is None, "an impossible value must be cleared, not kept"

    def test_repair_is_idempotent(self):
        """Re-running against an already-repaired stop changes nothing, so the
        every-few-minutes refresh cycle does not flap the column."""
        now = now_et()
        arrival = now - timedelta(minutes=38)
        observed = now - timedelta(minutes=37)

        first = resolve_actual_departure(
            arrival - timedelta(minutes=37), observed, arrival, now
        )
        second = resolve_actual_departure(first, observed, arrival, now)

        assert first == observed
        assert second == first, "a second pass must be a no-op"


class TestNaiveDatetimes:
    """Database values arrive naive; the NJT client's arrive tz-aware."""

    def test_naive_stored_value_compares_against_aware_arrival(self):
        now = now_et()
        arrival = now - timedelta(minutes=38)
        corrupt = (arrival - timedelta(minutes=37)).replace(tzinfo=None)
        observed = now - timedelta(minutes=37)

        result = resolve_actual_departure(corrupt, observed, arrival, now)

        assert result == observed, (
            "a naive stored value must be normalized to ET for the ordering "
            "check rather than raising TypeError mid-collection"
        )

    def test_naive_arrival_compares_against_aware_stored_value(self):
        now = now_et()
        arrival = now - timedelta(minutes=38)
        corrupt = arrival - timedelta(minutes=37)
        observed = now - timedelta(minutes=37)

        result = resolve_actual_departure(
            corrupt, observed, arrival.replace(tzinfo=None), now
        )

        assert result == observed
