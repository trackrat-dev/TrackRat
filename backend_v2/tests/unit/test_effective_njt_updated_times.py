"""Tests for ``effective_njt_updated_times`` — the helper that normalizes NJT's
inverted ``TIME``/``DEP_TIME`` semantics before they leak to API clients.

Background (regression-protects issue #1268):
  NJT's intermediate-stop API rows have ``DEP_TIME`` = original schedule and
  ``TIME`` = live delayed estimate. The collector persists these as raw
  passthroughs on ``JourneyStop.updated_departure`` / ``.updated_arrival``.
  Any consumer that reads ``updated_departure`` directly at an intermediate
  NJT stop sees the schedule and silently shows the train as on-time. The
  ``/api/v2/trains/{train_id}`` endpoint was guilty of this until the
  helper here started normalizing the pair before serialization.

The helper is also a deliberate no-op for non-NJT providers — their
``updated_arrival`` / ``updated_departure`` are distinct live estimates of
arrival vs. departure at a stop, and conflating them via ``max()`` would
overwrite the arrival display with the (typically later) departure time.
"""

from __future__ import annotations

from datetime import UTC, datetime

from trackrat.models.database import JourneyStop
from trackrat.utils.train import effective_njt_updated_times

# Realistic delayed-train sample times (HH:MM in UTC; ET semantics don't matter
# for arithmetic but production data is always tz-aware).
_SCHEDULE = datetime(2026, 6, 4, 21, 30, tzinfo=UTC)
_LIVE_ESTIMATE = datetime(2026, 6, 4, 21, 50, tzinfo=UTC)  # 20-min delay


class TestNJTIntermediateStopInversion:
    """The bug from issue #1268: intermediate NJT stops should expose the live
    estimate via both fields, not the schedule via ``updated_departure``."""

    def test_intermediate_stop_with_inversion_returns_live_estimate_on_both_fields(
        self,
    ) -> None:
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=_LIVE_ESTIMATE,  # NJT TIME — actually the live estimate
            updated_departure=_SCHEDULE,  # NJT DEP_TIME — actually the schedule
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr == _LIVE_ESTIMATE
        assert dep == _LIVE_ESTIMATE
        # Sanity: caller should no longer see the schedule when they read
        # updated_departure — that was the bug.
        assert dep != _SCHEDULE

    def test_intermediate_stop_when_estimate_lives_in_updated_departure(self) -> None:
        """Defensive case: production has occasionally shown both orderings
        as collector bugs were fixed. ``max()`` resolves either direction."""
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=_SCHEDULE,
            updated_departure=_LIVE_ESTIMATE,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr == _LIVE_ESTIMATE
        assert dep == _LIVE_ESTIMATE


class TestNJTEdgeCases:
    """Cases where only one ``updated_*`` field is populated — origin and
    terminal stops, plus malformed data — should pass through untouched."""

    def test_origin_stop_only_has_updated_departure(self) -> None:
        """NJT origin: ``updated_departure`` is the actual departure time and
        ``updated_arrival`` is None. We must not invent an arrival value."""
        stop = JourneyStop(
            station_code="DV",
            station_name="Dover",
            updated_arrival=None,
            updated_departure=_LIVE_ESTIMATE,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr is None
        assert dep == _LIVE_ESTIMATE

    def test_terminal_stop_only_has_updated_arrival(self) -> None:
        """NJT terminal: DEP_TIME isn't published, so ``updated_departure`` is
        None and ``updated_arrival`` carries the live estimate."""
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=_LIVE_ESTIMATE,
            updated_departure=None,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr == _LIVE_ESTIMATE
        assert dep is None

    def test_both_fields_none(self) -> None:
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=None,
            updated_departure=None,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr is None
        assert dep is None


class TestNJTTerminalStop:
    """Regression-protects issue #1492: at the terminal, NJT sometimes populates
    ``DEP_TIME`` with a later turnaround/layover departure. For an on-time or
    lightly delayed train ``TIME < DEP_TIME``, so the intermediate-stop ``max()``
    would promote the departure into the arrival slot and inflate the displayed
    terminal arrival by several minutes. The terminal arrival is ``TIME``
    (``updated_arrival``) alone — ``is_terminal=True`` must skip the ``max()``."""

    def test_terminal_with_later_dep_time_keeps_arrival_estimate(self) -> None:
        # The exact reported shape: NYP arrival estimate 8:04 (TIME) but a later
        # 8:18 turnaround DEP_TIME. Without is_terminal the user saw 8:18.
        arrival_estimate = datetime(2026, 7, 14, 12, 4, tzinfo=UTC)  # 8:04 ET
        later_departure = datetime(2026, 7, 14, 12, 18, tzinfo=UTC)  # 8:18 ET
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn",
            updated_arrival=arrival_estimate,
            updated_departure=later_departure,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT", is_terminal=True)
        assert arr == arrival_estimate, "terminal arrival was inflated by DEP_TIME"
        assert arr != later_departure
        # Departure is passed through untouched (the train terminates here).
        assert dep == later_departure

    def test_same_stop_inflates_when_not_flagged_terminal(self) -> None:
        """Contrast: the identical stop treated as intermediate (the default)
        DOES apply max() — this is what produced the wrong 8:18 arrival."""
        arrival_estimate = datetime(2026, 7, 14, 12, 4, tzinfo=UTC)
        later_departure = datetime(2026, 7, 14, 12, 18, tzinfo=UTC)
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn",
            updated_arrival=arrival_estimate,
            updated_departure=later_departure,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT")
        assert arr == later_departure
        assert dep == later_departure

    def test_terminal_delayed_train_still_shows_delay(self) -> None:
        """A genuinely delayed terminal (TIME > DEP_TIME) is unaffected: the
        live estimate is already the arrival, so skipping max() keeps it."""
        schedule = datetime(2026, 7, 14, 12, 4, tzinfo=UTC)
        delayed_estimate = datetime(2026, 7, 14, 12, 24, tzinfo=UTC)  # 20-min late
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn",
            updated_arrival=delayed_estimate,
            updated_departure=schedule,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT", is_terminal=True)
        assert arr == delayed_estimate
        assert dep == schedule

    def test_terminal_without_dep_time_unchanged(self) -> None:
        """The documented terminal shape (DEP_TIME absent) is unaffected by the
        flag — arrival is the live estimate, departure stays None."""
        stop = JourneyStop(
            station_code="NY",
            station_name="New York Penn",
            updated_arrival=_LIVE_ESTIMATE,
            updated_departure=None,
        )
        arr, dep = effective_njt_updated_times(stop, "NJT", is_terminal=True)
        assert arr == _LIVE_ESTIMATE
        assert dep is None

    def test_terminal_flag_is_noop_for_non_njt(self) -> None:
        """is_terminal only affects NJT — other providers short-circuit before
        the max() regardless, so the flag must not change their passthrough."""
        arrival = datetime(2026, 7, 14, 12, 4, tzinfo=UTC)
        departure = datetime(2026, 7, 14, 12, 6, tzinfo=UTC)
        stop = JourneyStop(
            station_code="NYP",
            station_name="New York Penn",
            updated_arrival=arrival,
            updated_departure=departure,
        )
        arr, dep = effective_njt_updated_times(stop, "AMTRAK", is_terminal=True)
        assert arr == arrival
        assert dep == departure


class TestNonNJTPassthrough:
    """For Amtrak / PATH / GTFS-RT / WMATA, ``updated_arrival`` and
    ``updated_departure`` are distinct live estimates of arrival vs. departure.
    The helper must preserve that distinction — collapsing them via ``max()``
    would silently shift the arrival display forward by the dwell time."""

    def test_amtrak_intermediate_stop_keeps_distinct_arrival_and_departure(
        self,
    ) -> None:
        arrival = datetime(2026, 6, 4, 21, 30, tzinfo=UTC)
        departure = datetime(2026, 6, 4, 21, 31, tzinfo=UTC)  # 1-min dwell
        stop = JourneyStop(
            station_code="NYP",
            station_name="New York Penn",
            updated_arrival=arrival,
            updated_departure=departure,
        )
        arr, dep = effective_njt_updated_times(stop, "AMTRAK")
        assert arr == arrival
        assert dep == departure
        # Critical: arr is NOT pulled forward to the departure time
        assert arr != departure

    def test_path_passthrough(self) -> None:
        arrival = datetime(2026, 6, 4, 21, 30, tzinfo=UTC)
        departure = datetime(2026, 6, 4, 21, 32, tzinfo=UTC)
        stop = JourneyStop(
            station_code="WTC",
            station_name="World Trade Center",
            updated_arrival=arrival,
            updated_departure=departure,
        )
        arr, dep = effective_njt_updated_times(stop, "PATH")
        assert arr == arrival
        assert dep == departure

    def test_lirr_subway_metro_north_passthrough(self) -> None:
        # One spot-check is enough — same code path as PATH/AMTRAK; any
        # non-NJT data_source short-circuits to a raw passthrough.
        arrival = datetime(2026, 6, 4, 21, 30, tzinfo=UTC)
        departure = datetime(2026, 6, 4, 21, 31, tzinfo=UTC)
        stop = JourneyStop(
            station_code="ABC",
            station_name="Anywhere",
            updated_arrival=arrival,
            updated_departure=departure,
        )
        for source in ("LIRR", "MNR", "SUBWAY", "BART", "MBTA", "METRA", "WMATA"):
            arr, dep = effective_njt_updated_times(stop, source)
            assert arr == arrival, f"{source} arrival was rewritten"
            assert dep == departure, f"{source} departure was rewritten"

    def test_none_data_source_treated_as_non_njt(self) -> None:
        """Defensive: a missing data_source should not silently apply the NJT
        inversion fix to arbitrary records."""
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=_LIVE_ESTIMATE,
            updated_departure=_SCHEDULE,
        )
        arr, dep = effective_njt_updated_times(stop, None)
        assert arr == _LIVE_ESTIMATE
        assert dep == _SCHEDULE  # untouched
