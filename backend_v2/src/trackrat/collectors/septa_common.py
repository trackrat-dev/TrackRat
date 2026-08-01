"""Shared lifecycle policy for SEPTA real-time collectors."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import TrainJourney

OMISSION_EXPIRY_THRESHOLD = 3


class SeptaFeedFetchError(RuntimeError):
    """Raised when a SEPTA feed cannot provide a usable snapshot."""


def mark_journey_present(journey: TrainJourney) -> None:
    """Reset omission state after a journey reappears in a SEPTA feed.

    SEPTA collectors are currently the only writers that expire SEPTA journeys,
    and they do so with ``api_error_count >= OMISSION_EXPIRY_THRESHOLD``. That
    signature lets a recovered journey be reactivated without clearing unrelated
    expiry states. Completed and cancelled journeys are final here.
    """
    if journey.is_completed or journey.is_cancelled:
        return

    omission_expired = (
        journey.is_expired
        and (journey.api_error_count or 0) >= OMISSION_EXPIRY_THRESHOLD
    )
    journey.api_error_count = 0
    if omission_expired:
        journey.is_expired = False


def mark_journey_omitted(journey: TrainJourney) -> bool:
    """Record one valid consecutive omission and return whether it expired."""
    if journey.is_completed or journey.is_cancelled or journey.is_expired:
        return False

    journey.api_error_count = (journey.api_error_count or 0) + 1
    if journey.api_error_count >= OMISSION_EXPIRY_THRESHOLD:
        journey.is_expired = True
        return True
    return False


async def reconcile_journey_omissions(
    session: AsyncSession,
    data_source: str,
    service_date: date,
    present_journey_keys: set[tuple[str, date]],
    unresolved_present_train_ids: set[str] | None = None,
) -> int:
    """Apply SEPTA presence/omission state from one valid nonempty snapshot."""
    unresolved_present_train_ids = unresolved_present_train_ids or set()
    result = await session.execute(
        select(TrainJourney).where(
            TrainJourney.data_source == data_source,
            TrainJourney.observation_type == "OBSERVED",
            TrainJourney.journey_date >= service_date - timedelta(days=1),
        )
    )

    expired = 0
    for journey in result.scalars():
        journey_key = (journey.train_id, journey.journey_date)
        if journey_key in present_journey_keys:
            mark_journey_present(journey)
        elif journey.train_id in unresolved_present_train_ids:
            # RR feed items have no service date until static-schedule resolution.
            # Presence still suppresses a false omission, but must not reactivate a
            # same-number journey from a different service day.
            continue
        elif mark_journey_omitted(journey):
            expired += 1
    return expired
