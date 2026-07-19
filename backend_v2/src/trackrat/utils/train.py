"""
Train-related utility functions for TrackRat V2.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.base import NO_VALUE

if TYPE_CHECKING:
    from trackrat.models.database import JourneyStop, TrainJourney


def _stops_loaded(journey: "TrainJourney") -> bool:
    """Check if the stops relationship is eagerly loaded (safe to access in sync context).

    Accessing a lazy-loaded relationship in a sync function within an async
    SQLAlchemy session triggers MissingGreenlet. This helper uses SQLAlchemy's
    instance inspection to check whether stops were eagerly loaded (via
    selectinload/joinedload) without triggering a lazy load.
    """
    state = sa_inspect(journey, raiseerr=False)
    if state is None:
        return False
    return state.attrs.stops.loaded_value is not NO_VALUE


def get_effective_observation_type(journey: "TrainJourney") -> str:
    """
    Get the effective observation type for display.

    For SCHEDULED trains from systems without real-time discovery (e.g. PATCO),
    we upgrade to OBSERVED if the origin departure time has passed and a stop
    has actually departed. This prevents showing "Scheduled" for trains that
    are running but lack real-time confirmation.

    For NJT, SCHEDULED trains that were never observed should NOT be promoted
    — they are likely cancelled. The reconciliation job will eventually mark
    them as such. Other real-time systems still auto-promote because they
    either don't create SCHEDULED records (PATH, LIRR, MNR) or rely on
    auto-promotion for pattern-scheduled trains (Amtrak).

    Args:
        journey: The train journey record

    Returns:
        "OBSERVED" or "SCHEDULED"
    """
    from trackrat.utils.time import now_et

    if journey.observation_type != "SCHEDULED":
        return journey.observation_type or "OBSERVED"

    # For NJT, don't promote SCHEDULED trains that have no evidence of
    # actually running. NJT has a reconciliation job that marks unobserved
    # trains as cancelled. Other real-time systems (Amtrak, PATH, LIRR, MNR)
    # either don't create SCHEDULED records or rely on auto-promotion for
    # pattern-scheduled trains that haven't been discovered yet.
    if journey.data_source == "NJT":
        return "SCHEDULED"

    # For schedule-only systems (PATCO): promote if departure time has passed.
    # Guard against lazy-load in sync context — if stops weren't eagerly loaded,
    # fall back to SCHEDULED rather than triggering MissingGreenlet.
    if not _stops_loaded(journey) or not journey.stops:
        return "SCHEDULED"

    sorted_stops = sorted(journey.stops, key=stop_sequence_sort_key)
    first_stop = sorted_stops[0]

    origin_departure = first_stop.scheduled_departure or first_stop.scheduled_arrival
    if origin_departure and origin_departure <= now_et():
        return "OBSERVED"

    return "SCHEDULED"


def is_amtrak_train(train_id: str) -> bool:
    """Determine if a train ID is for an Amtrak train.

    Amtrak trains follow the pattern: A + digits (e.g., A153, A2290)

    Args:
        train_id: The train identifier

    Returns:
        True if this is an Amtrak train ID
    """
    if not train_id or len(train_id) < 2:
        return False

    return train_id.startswith("A") and train_id[1:].isdigit()


def get_train_data_source(train_id: str) -> str:
    """Get the data source for a train based on its ID.

    Note: This function can only distinguish Amtrak trains (A-prefixed) from NJT.
    PATH, PATCO, LIRR, and MNR trains must be identified by their database
    data_source field, not by train_id pattern alone.

    Args:
        train_id: The train identifier

    Returns:
        Data source: "AMTRAK" or "NJT" (default fallback)
    """
    return "AMTRAK" if is_amtrak_train(train_id) else "NJT"


def stop_sequence_sort_key(stop: "JourneyStop") -> tuple[bool, int]:
    """Ordering key for a ``JourneyStop`` that sorts a NULL ``stop_sequence`` last.

    Discovery-created stops (and schedule-only rows) carry
    ``stop_sequence = NULL`` until a full collection assigns one. The historical
    ``key=lambda s: s.stop_sequence or 0`` idiom collapsed NULL to ``0``, tying an
    unsequenced stop with the origin (sequence 0) so it floated to the top of a
    stops list and misclassified from/to direction checks (issue #1536).

    Returning ``(stop.stop_sequence is None, stop.stop_sequence or 0)`` keeps every
    fully-sequenced journey ordered exactly as before — for non-NULL sequences
    ``(False, a) < (False, b)`` iff ``a < b`` — while ordering any NULL-sequence
    stop *after* all known ones (nulls-last). Use it wherever stops are sorted,
    ``min()``-ed for the origin, or compared for from/to direction (tuple keys
    compare lexicographically, so ``stop_sequence_sort_key(a) > stop_sequence_sort_key(b)``
    is the nulls-last equivalent of ``(a.stop_sequence or 0) > (b.stop_sequence or 0)``).

    Terminal/last-stop detection deliberately does **not** use this key: a
    nulls-last ``max()`` would pick the unsequenced stop as the terminal. Those
    callers keep the ``or 0`` form — where a NULL collapses to 0 and can never win
    the ``max()`` over a real terminal — or the fully-sequenced guard in
    :func:`terminal_stop_index`.
    """
    return (stop.stop_sequence is None, stop.stop_sequence or 0)


def terminal_stop_index(
    sorted_stops: "list[JourneyStop]", terminal_station_code: str | None
) -> int | None:
    """Index of the genuine terminal stop in a ``stop_sequence``-sorted list,
    or ``None`` when positional detection can't be trusted.

    Callers sort stops with :func:`stop_sequence_sort_key` (nulls-last), so the
    last element is only reliably the terminal once a journey is **fully
    collected**. NJT discovery/schedule rows carry ``stop_sequence = NULL`` (sorted
    to the *end* by that key) and the journey's ``terminal_station_code`` is still
    an origin/discovery placeholder until full collection rewrites it to the last
    API stop. On such a partially-collected journey ``sorted_stops[-1]`` can be an
    unsequenced or intermediate stop; flagging it terminal would skip
    ``effective_njt_updated_times``'s ``max()`` and expose NJT's raw scheduled
    ``DEP_TIME``, hiding that stop's delay (PR #1495 review).

    Guard against that by only accepting the last stop as terminal when every stop
    has a non-null ``stop_sequence`` (i.e. the journey has been fully sequenced)
    **and** that last stop's ``station_code`` matches ``terminal_station_code``.
    Both conditions hold together only after full journey collection, which is
    exactly when the terminal exemption is meant to apply.
    """
    if not sorted_stops:
        return None
    if any(s.stop_sequence is None for s in sorted_stops):
        return None
    last_index = len(sorted_stops) - 1
    if sorted_stops[last_index].station_code != terminal_station_code:
        return None
    return last_index


def effective_njt_updated_times(
    stop: "JourneyStop", data_source: str | None, is_terminal: bool = False
) -> tuple[datetime | None, datetime | None]:
    """Return ``(updated_arrival, updated_departure)`` with NJT inversion correction.

    NJT's ``TIME`` and ``DEP_TIME`` API fields have inverted semantics at
    intermediate stops: ``DEP_TIME`` is the original schedule (immutable) while
    ``TIME`` is the live delayed estimate. The collector persists both as raw
    passthroughs on ``JourneyStop.updated_departure`` and ``.updated_arrival``,
    so any client that reads ``updated_departure`` directly at an intermediate
    NJT stop sees the schedule and thinks the train is on time.

    For NJT records where both fields are populated, this helper returns
    ``max(updated_arrival, updated_departure)`` for both — the canonical
    pattern already used by ``services/departure.py`` for the departures
    endpoint. For all other providers (Amtrak, GTFS-RT, PATH, WMATA) both
    fields are genuine live estimates that may legitimately differ by the
    stop's dwell time, so we return them unmodified to preserve that
    distinction.

    The ``max()`` is correct at intermediate stops but wrong at the **terminal**:
    the train does not continue onward there, so ``DEP_TIME`` is not a live
    departure estimate. When NJT nonetheless populates it (e.g. with a later
    scheduled/turnaround departure), an on-time or lightly delayed train has
    ``TIME < DEP_TIME`` and the ``max()`` would promote the departure value into
    the arrival slot, inflating the displayed terminal arrival by several
    minutes (issue #1492). At the terminal the live arrival estimate is ``TIME``
    (``updated_arrival``) alone, so pass ``is_terminal=True`` to skip the
    ``max()`` and return the raw fields.
    """
    if data_source != "NJT":
        return stop.updated_arrival, stop.updated_departure

    if is_terminal:
        return stop.updated_arrival, stop.updated_departure

    if stop.updated_arrival is not None and stop.updated_departure is not None:
        latest = max(stop.updated_arrival, stop.updated_departure)
        return latest, latest

    return stop.updated_arrival, stop.updated_departure


def is_njt_stop_cancelled(status: str | None) -> bool:
    """True if an NJT STOP_STATUS value indicates a cancellation.

    NJT's getTrainStopList API returns both spellings in practice — sometimes
    within the same train's stop list. Observed on production train #3830 on
    2026-04-16: the origin stop was "CANCELED" (American) while all 14 other
    stops were "CANCELLED" (British). Normalize both here so no caller has to
    remember.
    """
    if not status:
        return False
    return status.strip().upper() in ("CANCELLED", "CANCELED")


def njt_stops_indicate_cancellation(stop_statuses: list[str | None]) -> bool:
    """True if a train's NJT stop statuses indicate the train is cancelled.

    Mirrors the collector's cancellation rule (``collect_journey_details``):
    a train is cancelled if NJT marks *every* stop cancelled (train never ran)
    OR the *terminal* stop is cancelled (train didn't complete its journey —
    origin may read "ON TIME" while every later stop is "CANCELLED").

    ``stop_statuses`` must be in stop order; the last element is treated as the
    terminal stop. An empty list is not a cancellation (absent evidence), so
    callers gating on this stay conservative.
    """
    if not stop_statuses:
        return False
    cancelled = [is_njt_stop_cancelled(s) for s in stop_statuses]
    cancelled_count = sum(cancelled)
    if not cancelled_count:
        return False
    return cancelled_count == len(stop_statuses) or cancelled[-1]


def normalize_njt_destination(destination: str | None) -> str:
    """Normalize an NJT destination string for cross-source matching.

    NJT's daily schedule API (``getTrainSchedule`` used for schedule
    generation) returns the full official station name as ``DESTINATION``
    (e.g. "TRENTON TRANSIT CENTER"), while the real-time discovery feed
    returns the short common name for the same station (e.g. "Trenton").
    Without normalization, SCHEDULED rows created from the schedule API
    never match the OBSERVED row created from the real-time feed for the
    same physical train — the discovery merge misses it (creating a
    duplicate journey) and the departures dedup safety net also misses it
    (leaving the stale "Train TBD" row visible alongside the real train).
    Strip the generic " TRANSIT CENTER" suffix so both forms compare equal.
    """
    if not destination:
        return ""
    normalized = destination.strip().lower()
    suffix = " transit center"
    if normalized.endswith(suffix):
        normalized = normalized[: -len(suffix)]
    return normalized
