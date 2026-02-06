"""
Train-related utility functions for TrackRat V2.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trackrat.models.database import TrainJourney


def get_effective_observation_type(journey: "TrainJourney") -> str:
    """
    Get the effective observation type for display.

    For SCHEDULED trains, we upgrade to OBSERVED if the train's origin
    departure time has passed. This prevents showing "Scheduled" for
    trains that are likely already running but haven't been confirmed
    via real-time data yet (common with Amtrak pattern-based schedules).

    Args:
        journey: The train journey record

    Returns:
        "OBSERVED" or "SCHEDULED"
    """
    from trackrat.utils.time import now_et

    if journey.observation_type != "SCHEDULED":
        return journey.observation_type or "OBSERVED"

    # Find the first stop (train's actual origin)
    if not journey.stops:
        return "SCHEDULED"

    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
    first_stop = sorted_stops[0]

    # Check if the origin departure time has passed
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
