"""Tests for the shared SEPTA omission lifecycle policy."""

import pytest

from trackrat.collectors.septa_common import (
    mark_journey_omitted,
    mark_journey_present,
)
from trackrat.models.database import TrainJourney


def _journey(**overrides) -> TrainJourney:
    values = {
        "api_error_count": 0,
        "is_expired": False,
        "is_completed": False,
        "is_cancelled": False,
    }
    values.update(overrides)
    return TrainJourney(**values)


def test_three_consecutive_omissions_expire_journey() -> None:
    journey = _journey()

    assert mark_journey_omitted(journey) is False
    assert mark_journey_omitted(journey) is False
    assert mark_journey_omitted(journey) is True

    assert journey.api_error_count == 3
    assert journey.is_expired is True


def test_reappearance_breaks_omission_streak() -> None:
    journey = _journey(api_error_count=2)

    mark_journey_present(journey)
    assert mark_journey_omitted(journey) is False

    assert journey.api_error_count == 1
    assert journey.is_expired is False


def test_reappearance_recovers_omission_expiry() -> None:
    journey = _journey(api_error_count=3, is_expired=True)

    mark_journey_present(journey)

    assert journey.api_error_count == 0
    assert journey.is_expired is False


def test_reappearance_preserves_non_omission_expiry() -> None:
    journey = _journey(api_error_count=1, is_expired=True)

    mark_journey_present(journey)

    assert journey.api_error_count == 0
    assert journey.is_expired is True


@pytest.mark.parametrize("final_flag", ["is_completed", "is_cancelled"])
def test_final_journey_is_never_mutated(final_flag: str) -> None:
    journey = _journey(api_error_count=3, is_expired=True, **{final_flag: True})

    mark_journey_present(journey)
    newly_expired = mark_journey_omitted(journey)

    assert newly_expired is False
    assert journey.api_error_count == 3
    assert journey.is_expired is True
