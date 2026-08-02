"""Tests for ``departed_stop_time`` — the guard that keeps a stop flagged
``has_departed_station`` from carrying a *future* timestamp.

Background (regression-protects issue #1701, the PATH analogue of #1689):
  ``hide_departed`` does not simply drop rows whose ``has_departed_station``
  is true. Its second branch keeps any row whose
  ``coalesce(actual_departure, scheduled_departure)`` is still upcoming, so a
  train dwelling at its origin terminal stays boardable (issue #1422). The
  consequence is that any stop written as departed but stamped with a future
  time is served as a boardable departure at a station the train has not
  reached.

  PATH reaches that state by back-computing an origin departure from a
  RidePATH *prediction* (routinely in the future) and laying every stop out
  from it, so the guard has to be applied to an already-computed timestamp
  rather than to an ``ORIGIN_TRAVEL_BUFFER`` subtraction the way
  ``collectors.mta_common.synthetic_origin_departure`` does.

The naive-datetime cases matter in production, not just in tests: journey stop
times reach this helper from a mix of the RidePATH client (tz-aware ET) and
the database, and the codebase's convention (``utils.time.ensure_timezone_aware``)
is that a naive value means Eastern Time. A helper that compared naive values
against a tz-aware ``now`` would raise ``TypeError`` mid-collection.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from trackrat.utils.time import ET, now_et
from trackrat.utils.train import departed_stop_time

UTC_TZ = pytz.UTC


class TestDepartedStopTimeAdmissible:
    """Past timestamps are admissible and returned unchanged."""

    def test_returns_past_time_unchanged(self):
        now = now_et()
        passed = now - timedelta(minutes=4)

        result = departed_stop_time(passed, now)

        assert result is passed, "an admissible time must be returned as-is"

    def test_accepts_time_one_second_in_the_past(self):
        """The boundary is strict-less-than, so a second ago is admissible."""
        now = now_et()
        passed = now - timedelta(seconds=1)

        assert departed_stop_time(passed, now) == passed

    def test_accepts_long_past_time(self):
        """A stop passed an hour ago is the ordinary case for a running train."""
        now = now_et()
        passed = now - timedelta(hours=1)

        assert departed_stop_time(passed, now) == passed


class TestDepartedStopTimeInadmissible:
    """Future timestamps are declined — this is the whole point of the guard."""

    def test_declines_future_time(self):
        """The #1701 case: PJS back-computed to now+2 while the train is still
        approaching it."""
        now = now_et()
        upcoming = now + timedelta(minutes=2)

        assert departed_stop_time(upcoming, now) is None

    def test_declines_time_one_second_in_the_future(self):
        now = now_et()

        assert departed_stop_time(now + timedelta(seconds=1), now) is None

    def test_declines_now_exactly(self):
        """``now`` is not in the past. Equality must decline, otherwise a stop
        stamped exactly at wall clock survives ``hide_departed``'s ``> now``
        comparison on the very next tick."""
        now = now_et()

        assert departed_stop_time(now, now) is None

    def test_declines_none(self):
        """A missing schedule cannot evidence that the train passed the stop."""
        assert departed_stop_time(None, now_et()) is None


class TestDepartedStopTimeTimezoneHandling:
    """Mixed naive / aware inputs must compare in a single frame, not crash."""

    def test_naive_input_is_read_as_eastern(self):
        """A naive value 10 minutes before the ET wall clock is in the past.

        On a UTC host, comparing it as UTC instead would place it 4-5 hours in
        the future and the guard would wrongly decline every legitimate stop.
        """
        now = now_et()
        naive_past = now.astimezone(ET).replace(tzinfo=None) - timedelta(minutes=10)

        assert departed_stop_time(naive_past, now) == naive_past

    def test_naive_future_input_is_declined(self):
        now = now_et()
        naive_future = now.astimezone(ET).replace(tzinfo=None) + timedelta(minutes=10)

        assert departed_stop_time(naive_future, now) is None

    def test_utc_aware_input_compares_correctly(self):
        """Database reads come back UTC-aware; the same instant must be judged
        identically regardless of which zone it is expressed in."""
        now = now_et()
        passed_et = now - timedelta(minutes=5)
        passed_utc = passed_et.astimezone(UTC_TZ)

        assert departed_stop_time(passed_utc, now) == passed_utc
        assert (
            departed_stop_time((now + timedelta(minutes=5)).astimezone(UTC_TZ), now)
            is None
        )

    def test_naive_now_is_accepted(self):
        """Callers passing a naive ``now`` must not crash the collector."""
        naive_now = datetime(2026, 8, 1, 12, 0, 0)

        assert (
            departed_stop_time(naive_now - timedelta(minutes=1), naive_now) is not None
        )
        assert departed_stop_time(naive_now + timedelta(minutes=1), naive_now) is None
