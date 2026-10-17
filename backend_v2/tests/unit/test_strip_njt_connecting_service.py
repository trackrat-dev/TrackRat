"""Tests for ``strip_njt_connecting_service`` (follow-up to issue #1878).

Collection adopts getTrainStopList's DESTINATION in place, and that API names
the onward connection ("Long Branch with connecting service to Penn Station
New York"). Stored as sent, the long form showed up as the destination label
in every client and never compared equal to the schedule API's "Long Branch"
in the departures dedup, so a SCHEDULED duplicate under another train_id
could survive beside the live train.
"""

import pytest

from trackrat.services.departure import _destination_prefix
from trackrat.utils.train import strip_njt_connecting_service


@pytest.mark.parametrize(
    ("api_destination", "stored"),
    [
        ("Long Branch with connecting service to Bay Head", "Long Branch"),
        (
            "Long Branch with connecting service to Penn Station New York",
            "Long Branch",
        ),
        ("Newark Penn with connecting service to Long Branch", "Newark Penn"),
        ("Matawan with connecting service to Bay Head", "Matawan"),
        ("LONG BRANCH WITH CONNECTING SERVICE TO BAY HEAD", "LONG BRANCH"),
    ],
)
def test_strips_the_connection_suffix(api_destination: str, stored: str) -> None:
    result = strip_njt_connecting_service(api_destination)
    print(f"{api_destination!r} -> {result!r}")
    assert result == stored


@pytest.mark.parametrize(
    "destination",
    [
        "Long Branch",
        "Penn Station New York",
        "Newark Penn Station",
        "Long Branch-BH &#9992",
        "Hoboken",
    ],
)
def test_other_destinations_unchanged(destination: str) -> None:
    assert strip_njt_connecting_service(destination) == destination


def test_stored_form_dedups_against_the_schedule_spelling() -> None:
    """The departures dedup compares ``_destination_prefix`` values; the long
    form never matched the schedule API's terminal name, the stored form does."""
    api = "Long Branch with connecting service to Penn Station New York"
    schedule = "LONG BRANCH"

    assert _destination_prefix(api) != _destination_prefix(schedule)
    assert _destination_prefix(
        strip_njt_connecting_service(api)
    ) == _destination_prefix(schedule)
