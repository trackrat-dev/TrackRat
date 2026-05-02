"""
Test fixtures for NJ Transit API responses.

Provides builders and helpers for creating realistic mock API responses
without making actual API calls.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from trackrat.utils.time import now_et

# NJT API time format: "30-May-2024 10:52:30 AM"
NJT_TIME_FORMAT = "%d-%b-%Y %I:%M:%S %p"


class StopBuilder:
    """Builder for creating mock stop data."""

    def __init__(self, base_date: Optional[datetime] = None):
        """Initialize the builder with optional base date."""
        self.base_date = base_date or now_et().date()

    def build_stop(
        self,
        station_code: str,
        station_name: str,
        dep_time: str,
        arr_time: Optional[str] = None,
        departed: bool = False,
        track: Optional[str] = None,
        cancelled: bool = False,
        cancelled_spelling: str = "CANCELLED",
        stop_status: Optional[str] = None,
    ) -> MagicMock:
        """Build a mock stop object matching NJT API structure.

        Args:
            station_code: Station code (e.g., "NY")
            station_name: Full station name
            dep_time: Scheduled departure time string → DEP_TIME field
            arr_time: Estimated/actual arrival time string → TIME field (optional)
            departed: Whether stop has DEPARTED="YES" flag
            track: Track assignment (optional)
            cancelled: Whether stop is cancelled
            cancelled_spelling: STOP_STATUS text for cancelled stops. Defaults to
                "CANCELLED" (British), but NJT also returns "CANCELED" (American)
                in practice — sometimes both within the same train's stop list
                (observed on train #3830, 2026-04-16). Tests that specifically
                exercise the spelling normalizer should override this.
            stop_status: Explicit STOP_STATUS override (wins over `cancelled`).
                Real NJT values include "ON TIME", "ONTIME", "LATE",
                "ALL ABOARD". Defaults to "ON TIME".

        Returns:
            Mock object matching NJT API stop structure with correct field semantics:
            - TIME: arr_time (estimated/actual arrival) or dep_time for origin stations
            - DEP_TIME: dep_time (scheduled departure, never changes)
        """
        stop = MagicMock()

        # Basic fields
        stop.ITEM = f"{station_code} | {station_name}"
        stop.STATIONCODE = station_code
        stop.STATION_2CHAR = station_code  # 2-character station code
        stop.STATIONNAME = f"{station_name} Station"

        # Time fields - corrected to match actual NJT API semantics
        # TIME: Estimated/actual arrival time (what passengers see)
        # DEP_TIME: Scheduled departure time (fixed schedule)
        stop.TIME = (
            arr_time if arr_time else dep_time
        )  # Arrival time (or dep for origin)
        stop.DEP_TIME = dep_time  # Scheduled departure
        stop.ARR_TIME = arr_time  # Legacy field

        # Status fields
        stop.DEPARTED = "YES" if departed else "NO"
        stop.TRACK = track
        stop.CANCELLED = "YES" if cancelled else "NO"
        # STOP_STATUS is used for cancellation detection and delay parsing.
        # Default to "ON TIME" (a real NJT value) rather than "OK" (which NJT
        # never returns). Cancelled stops use the configured spelling.
        if stop_status is not None:
            stop.STOP_STATUS = stop_status
        elif cancelled:
            stop.STOP_STATUS = cancelled_spelling
        else:
            stop.STOP_STATUS = "ON TIME"

        # Additional fields from real API
        stop.LINE = "LINE_1"
        stop.STATUS = "OK"
        stop.SEC_LATE = "0"
        stop.CONNECTING = None
        stop.PICKUP = None
        stop.DROPOFF = None
        stop.SCHED_ARR_DATE = None
        stop.SCHED_DEP_DATE = None

        return stop


def create_stop_list_response(
    train_id: str,
    line_code: str = "TE",
    destination: str = "Test Destination",
    stops: Optional[List[MagicMock]] = None,
    capacity: int = 100,
    error: bool = False,
) -> MagicMock:
    """Create a complete mock train stop list response.

    Args:
        train_id: Train identifier
        line_code: Line code (e.g., "NE", "NC")
        destination: Train destination
        stops: List of stops (created with StopBuilder)
        capacity: Train capacity percentage
        error: Whether to simulate an error response

    Returns:
        Mock response matching getTrainStopList structure
    """
    response = MagicMock()

    if error:
        # Error response - all fields None
        response.TRAIN_ID = None
        response.LINECODE = None
        response.DESTINATION = None
        response.STOPS = None
        response.CAPACITY = None
        return response

    # Success response
    response.TRAIN_ID = train_id
    response.LINECODE = line_code
    response.DESTINATION = destination
    response.CAPACITY = capacity

    # Color codes (from real API)
    response.BACKCOLOR = "#FFFFFF"
    response.FORECOLOR = "#000000"
    response.SHADOWCOLOR = "#808080"

    # Transfer information
    response.TRANSFERAT = None

    # Stops list
    response.STOPS = stops or []
    response.ITEMS = stops or []  # Alias for compatibility with different API endpoints

    return response


def create_departed_stop(
    station_code: str, station_name: str, scheduled_time: datetime, track: str = "1"
) -> MagicMock:
    """Create a stop that has already departed.

    Args:
        station_code: Station code
        station_name: Station name
        scheduled_time: Scheduled departure time
        track: Track assignment

    Returns:
        Mock stop with DEPARTED=YES
    """
    builder = StopBuilder()
    time_str = scheduled_time.strftime(NJT_TIME_FORMAT)

    return builder.build_stop(
        station_code=station_code,
        station_name=station_name,
        dep_time=time_str,
        arr_time=None if station_code == "NY" else time_str,  # Origin has no arrival
        departed=True,
        track=track,
    )


def create_pending_stop(
    station_code: str,
    station_name: str,
    scheduled_time: datetime,
    track: Optional[str] = None,
) -> MagicMock:
    """Create a stop that hasn't departed yet.

    Args:
        station_code: Station code
        station_name: Station name
        scheduled_time: Scheduled departure time
        track: Track assignment (optional)

    Returns:
        Mock stop with DEPARTED=NO
    """
    builder = StopBuilder()
    time_str = scheduled_time.strftime(NJT_TIME_FORMAT)

    return builder.build_stop(
        station_code=station_code,
        station_name=station_name,
        dep_time=time_str,
        arr_time=time_str,
        departed=False,
        track=track,
    )


def create_journey_with_mixed_statuses() -> MagicMock:
    """Create a journey with realistic mix of departed/pending stops.

    Returns:
        Mock response with stops in various states
    """
    builder = StopBuilder()
    current_time = now_et()

    stops = [
        # Past stops - should be departed
        builder.build_stop("NY", "New York", "08:00:00 AM", departed=True, track="7"),
        builder.build_stop(
            "NP",
            "Newark Penn",
            "08:15:00 AM",
            arr_time="08:13:00 AM",
            departed=True,
            track="2",
        ),
        # Recent stop - might or might not be departed
        builder.build_stop(
            "MP",
            "Metropark",
            "08:30:00 AM",
            arr_time="08:28:00 AM",
            departed=False,
            track="1",
        ),
        # Future stops - not departed
        builder.build_stop(
            "NB", "New Brunswick", "08:45:00 AM", arr_time="08:43:00 AM", departed=False
        ),
        builder.build_stop(
            "TR", "Trenton", "09:15:00 AM", arr_time="09:13:00 AM", departed=False
        ),
    ]

    return create_stop_list_response(
        train_id="TEST_MIXED", line_code="NE", destination="Trenton", stops=stops
    )


def create_cancelled_journey() -> MagicMock:
    """Create a cancelled journey response (train never ran).

    Every stop is marked CANCELLED. Real-world analog: train #3720 on 2026-04-16.

    Returns:
        Mock response for fully-cancelled train
    """
    builder = StopBuilder()

    stops = [
        builder.build_stop(
            "NY", "New York", "10:00:00 AM", departed=False, cancelled=True
        ),
        builder.build_stop(
            "TR",
            "Trenton",
            "11:00:00 AM",
            arr_time="11:00:00 AM",
            departed=False,
            cancelled=True,
        ),
    ]

    response = create_stop_list_response(train_id="CANCELLED_001", stops=stops)

    # Add cancellation indicator
    for stop in response.STOPS:
        stop.CANCELLED = "YES"

    return response


def create_mid_journey_cancelled_response() -> MagicMock:
    """Train left origin, then NJT cancelled everything after.

    Real-world analog: train #3930 on 2026-04-16. The origin stop (Trenton)
    shows STOP_STATUS="ON TIME" because the train physically departed before
    being annulled, while every stop afterwards is "CANCELLED".

    Returns:
        Mock response for a mid-journey cancellation
    """
    builder = StopBuilder()

    stops = [
        # Origin — departed before the cancellation took effect
        builder.build_stop("TR", "Trenton", "08:06:00 AM", departed=True, track="1"),
        builder.build_stop(
            "HL",
            "Hamilton",
            "08:13:00 AM",
            arr_time="08:11:30 AM",
            departed=False,
            cancelled=True,
        ),
        builder.build_stop(
            "PJ",
            "Princeton Junction",
            "08:20:00 AM",
            arr_time="08:18:15 AM",
            departed=False,
            cancelled=True,
        ),
        builder.build_stop(
            "NP",
            "Newark Penn",
            "08:56:00 AM",
            arr_time="08:54:00 AM",
            departed=False,
            cancelled=True,
            track="2",
        ),
        builder.build_stop(
            "SE",
            "Secaucus Upper Lvl",
            "09:03:00 AM",
            arr_time="09:02:30 AM",
            departed=False,
            cancelled=True,
        ),
        builder.build_stop(
            "NY",
            "New York Penn",
            "09:29:00 AM",
            arr_time="09:16:00 AM",
            departed=False,
            cancelled=True,
        ),
    ]

    return create_stop_list_response(
        train_id="3930", line_code="NE", destination="New York", stops=stops
    )


def create_mixed_spelling_cancelled_response() -> MagicMock:
    """NJT returned both "CANCELED" and "CANCELLED" in a single response.

    Real-world analog: train #3830 on 2026-04-16. The origin stop came back
    as "CANCELED" (American spelling) while all 14 downstream stops were
    "CANCELLED" (British). Verifies that the cancellation check is robust
    to NJT's spelling inconsistency.

    Returns:
        Mock response for a cancelled train with mixed spellings
    """
    builder = StopBuilder()

    stops = [
        # American spelling at the first stop
        builder.build_stop(
            "TR",
            "Trenton",
            "07:46:00 AM",
            departed=False,
            cancelled=True,
            cancelled_spelling="CANCELED",
        ),
        # British spelling at the rest
        builder.build_stop(
            "HL", "Hamilton", "07:53:00 AM", departed=False, cancelled=True
        ),
        builder.build_stop(
            "PJ",
            "Princeton Junction",
            "08:00:00 AM",
            departed=False,
            cancelled=True,
        ),
        builder.build_stop(
            "NY", "New York Penn", "09:19:00 AM", departed=False, cancelled=True
        ),
    ]

    return create_stop_list_response(
        train_id="3830", line_code="NE", destination="New York", stops=stops
    )


def create_train_not_found_response() -> MagicMock:
    """Create a response for when train is not found.

    Returns:
        Mock error response with all None fields
    """
    return create_stop_list_response(train_id="NOT_FOUND", error=True)


def create_swapped_times_response() -> MagicMock:
    """Create a response with swapped arrival/departure times.

    This simulates the NJT API bug where intermediate stops
    have arrival > departure.

    Returns:
        Mock response with time swap issue
    """
    builder = StopBuilder()

    stops = [
        # Origin - normal
        builder.build_stop("NY", "New York", "10:00:00 AM", departed=True, track="7"),
        # Intermediate - SWAPPED times
        builder.build_stop(
            "NP",
            "Newark Penn",
            "10:15:00 AM",  # Departure
            arr_time="10:20:00 AM",  # Arrival AFTER departure!
            departed=True,
            track="2",
        ),
        # Another intermediate - also swapped
        builder.build_stop(
            "MP",
            "Metropark",
            "10:30:00 AM",  # Departure
            arr_time="10:35:00 AM",  # Arrival AFTER departure!
            departed=False,
            track="1",
        ),
        # Terminal - normal
        builder.build_stop(
            "TR", "Trenton", None, arr_time="11:00:00 AM", departed=False
        ),
    ]

    return create_stop_list_response(train_id="SWAP_TEST", stops=stops)
