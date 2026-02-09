"""
Train-related utility functions for TrackRat V2.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trackrat.models.database import TrainJourney


def get_effective_observation_type(journey: "TrainJourney") -> str:
    """
    Get the effective observation type for display.

    For SCHEDULED trains from systems without real-time discovery (e.g. PATCO),
    we upgrade to OBSERVED if the origin departure time has passed and a stop
    has actually departed. This prevents showing "Scheduled" for trains that
    are running but lack real-time confirmation.

    For real-time systems (NJT, Amtrak, PATH, LIRR, MNR), SCHEDULED trains
    that were never observed should NOT be promoted — they are likely cancelled.
    The reconciliation job will eventually mark them as such.

    Args:
        journey: The train journey record

    Returns:
        "OBSERVED" or "SCHEDULED"
    """
    from trackrat.utils.time import now_et

    if journey.observation_type != "SCHEDULED":
        return journey.observation_type or "OBSERVED"

    # For systems with real-time discovery, don't promote SCHEDULED trains
    # that have no evidence of actually running. If they were running,
    # discovery would have upgraded them to OBSERVED.
    REAL_TIME_SOURCES = {"NJT", "AMTRAK", "PATH", "LIRR", "MNR"}
    if journey.data_source in REAL_TIME_SOURCES:
        return "SCHEDULED"

    # For schedule-only systems (PATCO): promote if departure time has passed
    if not journey.stops:
        return "SCHEDULED"

    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
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
