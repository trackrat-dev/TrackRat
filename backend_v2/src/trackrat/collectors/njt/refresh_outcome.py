"""Freshness and strike bookkeeping shared by every NJT journey refresh path.

Three separate code paths ask NJT for a stop list and write the answer back to
the same journey row: ``JourneyCollector.collect_journey_details``
(``collectors/njt/journey.py``), ``SchedulerService._collect_single_njt_journey_safe``
(``services/scheduler.py``, through a synchronous session), and the just-in-time
station-board refresh (``services/departure.py``). They have to agree, because
the batch driving two of them is selected oldest-first::

    ORDER BY last_updated_at ASC LIMIT journey_update_batch_size

so **every** refresh outcome must advance ``last_updated_at``. A path that
returns without stamping leaves the journey pinned at the head of that queue,
re-selected on every tick for the rest of its in-flight window — burning NJT's
40,000/day ``getTrainStopList`` quota and starving the trains queued behind it.
That has now shipped as a bug twice: once for ``NJTransitNullDataError``
(#1748) and once for bare ``NJTransitAPIError`` (#1827), which is why the logic
lives here rather than being written out a third time.

The split between the two helpers is the distinction #1725 established:
``last_updated_at`` answers "when did we last ask", ``api_error_count`` answers
"is this train failing". Only evidence *about the train* belongs in the second.
NJT having no stop-list coverage, and NJT failing to answer at all, are both
facts about NJT — they stamp without striking. A train NJT has no record of is
evidence about the train, and strikes.

That boundary is load-bearing in two directions. A strike expires the journey at
the threshold, and ``get_departures`` excludes expired rows, so striking on
transport failures would clear the board of every in-flight NJT train a few
minutes into any provider-wide outage — recovering only via a later discovery
pass that needs the same broken API. And because the counter is shared, a couple
of transport blips would leave a journey primed so that the next *genuine*
``TrainNotFoundError`` expired it on the first occurrence instead of the third.
"""

from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et

# Consecutive strikes before a journey is expired. The counter is reset to 0 by
# any successful collection (``_apply_train_data``), so this counts a *run* of
# failures, and NJT discovery re-activates an expired train the moment it
# reappears (``collectors/njt/discovery.py``).
NJT_EXPIRY_THRESHOLD = 3


def mark_refresh_attempted(journey: TrainJourney) -> None:
    """Record that NJT was asked about this journey but had nothing usable.

    Advances the freshness clock *without* a strike: for missing stop-list
    coverage, and for an outright upstream failure, the absence is a fact about
    NJT rather than evidence about the train. The journey keeps its last known
    data and stays on the board; it simply leaves the head of the oldest-first
    queue, which is the whole of what #1748 and #1827 require.
    """
    journey.last_updated_at = now_et()


def mark_refresh_failed(journey: TrainJourney) -> bool:
    """Record one consecutive failed refresh; return whether expiry is now due.

    Returns ``True`` once ``api_error_count`` has reached
    ``NJT_EXPIRY_THRESHOLD``. Callers decide what expiry means for their
    failure mode — a train NJT has no record of may well have finished its run,
    while an HTTP error says nothing at all about the train.
    """
    journey.api_error_count = (journey.api_error_count or 0) + 1
    journey.last_updated_at = now_et()
    journey.update_count = (journey.update_count or 0) + 1
    return journey.api_error_count >= NJT_EXPIRY_THRESHOLD
