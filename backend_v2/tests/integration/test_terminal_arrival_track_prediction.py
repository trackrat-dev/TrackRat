"""Regression tests for issue #1773: track predictions served for a station a
train only *arrives* at.

The report: a rider whose selected route started at NY Penn opened NJT 7832 —
a Trenton → New York Penn run — and the train details screen showed "Track
Predictions" for Penn. 7832 terminates at Penn. It arrives and never departs,
so there is no boarding track to predict.

Why the numbers looked plausible anyway, and why data scarcity alone will not
suppress them: providers publish tracks for *departures*, so a terminal stop
carries no ``track`` of its own. ``_get_train_id_distribution`` therefore finds
nothing for the arriving train, the hierarchy falls through to
``_get_time_line_distribution``, and that level happily returns the track
distribution of the *other, opposite-direction* trains on the same line
scheduled around the same minute — presented to the rider as this train's
platform. Production reproduced exactly that: ``model_version`` came back
``historical_v1_time_line_code`` with 93 records behind it.

These tests seed that precise shape against a live database — one southbound
train with real NY Penn departure-track history, one northbound train
terminating at NY Penn with none — and assert on the two real endpoints:

1. ``/predictions/track`` (used by the iOS fallback and the web app) 404s for
   the terminating train, and does so *because* it terminates, not because data
   was missing: the identical call for the departing train returns a
   prediction built from the very history the arriving train would have
   inherited.
2. ``/trains/{train_id}``'s inline ``track_prediction`` is omitted for the
   terminating train and present for the departing one.

Two follow-on review findings share the seed and are covered here too:

3. A station the train never serves at all reaches the same failure shape from
   the other direction — with no history for the train there, the hierarchy's
   static / service-distribution fallbacks answer from other trains' platforms.
   ``/predictions/track`` now 404s that as ``station_not_served``, with a
   served-intermediate control (Newark Penn) proving the guard is positional,
   not "any station that isn't the origin".
4. Both route-shape guards apply only to the journey row for the *requested*
   ``journey_date``. When none exists the endpoint falls back to an arbitrary
   historical journey with the same train ID; a timetable change can make that
   surrogate terminate where today's run departs, and 404ing on its stops
   would suppress a valid prediction. The date-fallback test pins the
   pre-guard behavior: surrogate journeys serve the prediction.
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.api.predictions import predict_track
from trackrat.api.trains import get_train_details
from trackrat.db.engine import close_engine
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture(autouse=True)
async def _fresh_app_engine():
    """Rebuild the process-global engine around every test in this module.

    ``get_train_details`` computes its inline track prediction on a *separate*
    session (``async with get_session()``) so a slow or failed prediction can't
    poison the request's session. That session comes from the process-global
    engine, whose pooled connections stay bound to whichever event loop first
    created them — across tests that means "Event loop is closed", which the
    inline path swallows into ``track_prediction = None``.

    That silence is right in production (a prediction is optional) and lethal
    in a test: the terminating-train assertion below would pass on an
    infrastructure error instead of on the guard, which is exactly what it did
    before this fixture existed. Disposing the engine on both sides pins each
    test to connections opened on its own loop.
    """
    await close_engine()
    yield
    await close_engine()


# Southbound NY Penn -> Trenton (departs NY Penn: prediction is meaningful).
DEPARTING_TRAIN_ID = "7841"
# Northbound Trenton -> NY Penn (terminates at NY Penn: nothing to board).
TERMINATING_TRAIN_ID = "7832"
# Northbound run that exists only on a past journey_date — exercises the
# arbitrary-historical-journey fallback in predict_track.

# Enough same-train history to clear MIN_TRAIN_ID_RECORDS (10) for the
# southbound train, which also makes the shared time+line level rich enough to
# answer for the northbound one — the fallback that produced the bug.
HISTORY_DAYS = 14

# NP (Newark Penn) is deliberately included: it is a prediction-enabled
# *intermediate* station, giving the unserved-station guard its control. HB
# (Hoboken) is prediction-enabled and genuinely never served by the NEC,
# giving the guard its trigger.
SOUTHBOUND_STOPS = ["NY", "SE", "NP", "EWR", "NB", "PJ", "HL", "TR"]
NORTHBOUND_STOPS = ["TR", "HL", "PJ", "NB", "EWR", "NP", "SE", "NY"]
UNSERVED_STATION = "HB"


def _journey(
    train_id: str,
    journey_date,
    station_codes: list[str],
    first_departure,
    *,
    tracks: dict[str, str] | None,
) -> TrainJourney:
    """Build a fully-collected NJT journey along ``station_codes``.

    Fully collected matters: ``terminal_stop_index`` (and therefore the guard)
    only trusts positional terminal detection when every stop is sequenced and
    the last one agrees with ``terminal_station_code``. Stops are spaced 10
    minutes apart from ``first_departure``.

    ``tracks`` maps station code -> recorded departure track — real values for
    southbound departure stops, ``None``/absent for northbound arrivals,
    mirroring what NJT actually publishes.
    """
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        data_source="NJT",
        observation_type="OBSERVED",
        line_code="NE",
        line_name="Northeast Corridor Line",
        line_color="#000000",
        destination=station_codes[-1],
        origin_station_code=station_codes[0],
        terminal_station_code=station_codes[-1],
        scheduled_departure=first_departure,
        first_seen_at=first_departure,
        last_updated_at=now_et(),
        has_complete_journey=True,
        stops_count=len(station_codes),
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
        update_count=5,
    )

    journey.stops = [
        JourneyStop(
            station_code=code,
            station_name=code,
            stop_sequence=index,
            scheduled_departure=first_departure + timedelta(minutes=10 * index),
            scheduled_arrival=first_departure + timedelta(minutes=10 * index),
            track=(tracks or {}).get(code),
            has_departed_station=False,
        )
        for index, code in enumerate(station_codes)
    ]
    return journey


async def _seed(db_session: AsyncSession) -> None:
    """Seed NY Penn and Newark Penn departure-track history plus today's runs.

    The southbound train has run daily for HISTORY_DAYS off tracks 1-4 (Penn's
    NJT-side tracks) with a track also recorded at Newark Penn, each departure
    at the same clock time so the ±30 minute time+line window covers today's
    northbound arrival too.
    """
    today = now_et().replace(hour=13, minute=30, second=0, microsecond=0)

    for days_ago in range(1, HISTORY_DAYS + 1):
        historical_departure = today - timedelta(days=days_ago)
        db_session.add(
            _journey(
                DEPARTING_TRAIN_ID,
                historical_departure.date(),
                SOUTHBOUND_STOPS,
                historical_departure,
                # Vary the tracks so the distributions have real spread rather
                # than a single degenerate 100% bucket.
                tracks={
                    "NY": str((days_ago % 4) + 1),
                    "NP": str((days_ago % 3) + 1),
                },
            )
        )

    # Today's southbound run: departs NY Penn, no tracks posted yet.
    db_session.add(
        _journey(
            DEPARTING_TRAIN_ID,
            today.date(),
            SOUTHBOUND_STOPS,
            today,
            tracks=None,
        )
    )

    # Today's northbound run: reaches NY Penn 70 min after it leaves Trenton,
    # at the same clock time as the southbound departures — inside the ±30
    # minute time+line window that produced the bug.
    db_session.add(
        _journey(
            TERMINATING_TRAIN_ID,
            today.date(),
            NORTHBOUND_STOPS,
            today - timedelta(minutes=70),
            tracks=None,
        )
    )

    await db_session.commit()


@pytest.mark.asyncio
class TestPredictTrackEndpoint:
    """/predictions/track — the path iOS falls back to and the web app always uses."""

    async def test_departing_train_still_gets_a_prediction(
        self, db_session: AsyncSession
    ):
        """Control: the guard must not suppress a genuine NY Penn departure.

        This is the feature's main use case (a rider boarding at Penn), and it
        establishes that the history seeded here is sufficient — so the 404 in
        the next test can only come from the terminal guard.
        """
        await _seed(db_session)
        today = now_et().date()

        response = await predict_track(
            station_code="NY",
            train_id=DEPARTING_TRAIN_ID,
            journey_date=today,
            db=db_session,
        )

        assert response.platform_probabilities, (
            "Southbound NY Penn departure returned no platform probabilities; "
            f"model_version={response.model_version}"
        )
        assert abs(sum(response.platform_probabilities.values()) - 1.0) < 1e-6, (
            "Platform probabilities must be a normalized distribution: "
            f"{response.platform_probabilities}"
        )

    async def test_terminating_train_is_rejected(self, db_session: AsyncSession):
        """The #1773 bug: NJT 7832 terminates at NY Penn -> 404, not a platform.

        The southbound history seeded above is exactly what this train would
        otherwise inherit through the time+line fallback, so a prediction here
        would be the reported defect reproduced.
        """
        await _seed(db_session)
        today = now_et().date()

        with pytest.raises(HTTPException) as exc_info:
            await predict_track(
                station_code="NY",
                train_id=TERMINATING_TRAIN_ID,
                journey_date=today,
                db=db_session,
            )

        assert exc_info.value.status_code == 404, (
            "A train terminating at the requested station must not be served a "
            f"departure track prediction (got {exc_info.value.status_code})"
        )
        assert "terminates" in str(exc_info.value.detail).lower(), (
            "The 404 must name the real reason (terminal arrival), not read as "
            f"missing data: {exc_info.value.detail}"
        )

    async def test_surrogate_lookup_answers_from_the_most_recent_run(
        self, db_session: AsyncSession
    ):
        """A date with no journey row must be answered by the *newest* run.

        Dates the collector has no row for — future boards served from GTFS
        static, and sources that only create rows on observation — fall back to
        "any journey with this train ID". That surrogate is not incidental: it
        supplies the route, the line code and the stop-level departure time the
        prediction is built from, so answering from an arbitrary run means
        describing a route the train may no longer take. Runs stay queryable
        for the whole 60-day retention window.

        Here the train number has been re-cut to terminate at NY Penn (its
        newest run arrives and never departs), while a fortnight of older runs
        still on file departed from Penn. Answering from any of those older
        runs serves the rider a boarding platform for a train that will not
        board — #1773 reached through the back door.
        """
        await _seed(db_session)

        # The re-cut run, dated after every seeded one.
        recut = (now_et() + timedelta(days=1)).replace(
            hour=13, minute=30, second=0, microsecond=0
        )
        db_session.add(
            _journey(
                DEPARTING_TRAIN_ID,
                recut.date(),
                NORTHBOUND_STOPS,
                recut,
                tracks=None,
            )
        )
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await predict_track(
                station_code="NY",
                train_id=DEPARTING_TRAIN_ID,
                journey_date=(now_et() + timedelta(days=7)).date(),
                db=db_session,
            )

        assert exc_info.value.status_code == 404, (
            "A date with no journey row was answered from an older run: the "
            "train's most recent run terminates at NY Penn, so there is no "
            f"boarding track to predict (got {exc_info.value.status_code})"
        )
        assert "terminates" in str(exc_info.value.detail).lower(), (
            "The 404 must come from the terminal guard reading the newest run, "
            f"not from a missing journey: {exc_info.value.detail}"
        )

    async def test_served_intermediate_station_still_gets_a_prediction(
        self, db_session: AsyncSession
    ):
        """Control for the unserved guard: Newark Penn is mid-route, not the
        origin, and the train genuinely departs it — the prediction must
        survive. Together with the unserved 404 below this proves the guard is
        positional ("is this stop on the route"), not "anything but the
        origin".
        """
        await _seed(db_session)
        today = now_et().date()

        response = await predict_track(
            station_code="NP",
            train_id=DEPARTING_TRAIN_ID,
            journey_date=today,
            db=db_session,
        )

        assert response.platform_probabilities, (
            "Served intermediate stop (Newark Penn) returned no platform "
            f"probabilities; model_version={response.model_version}"
        )
        assert abs(sum(response.platform_probabilities.values()) - 1.0) < 1e-6, (
            "Platform probabilities must be a normalized distribution: "
            f"{response.platform_probabilities}"
        )

    async def test_unserved_station_is_rejected(self, db_session: AsyncSession):
        """A station the train never calls at: NEC trains don't serve Hoboken,
        yet HB is prediction-enabled, so without the guard the request falls
        through to the hierarchy's station-level fallbacks — other trains'
        Hoboken platforms presented as this train's.
        """
        await _seed(db_session)
        today = now_et().date()

        with pytest.raises(HTTPException) as exc_info:
            await predict_track(
                station_code=UNSERVED_STATION,
                train_id=DEPARTING_TRAIN_ID,
                journey_date=today,
                db=db_session,
            )

        assert exc_info.value.status_code == 404, (
            "A station the train never serves must not get a departure track "
            f"prediction (got {exc_info.value.status_code})"
        )
        assert "does not serve" in str(exc_info.value.detail).lower(), (
            "The 404 must name the real reason (station not served), not read "
            f"as missing data: {exc_info.value.detail}"
        )


@pytest.mark.asyncio
class TestInlineTrackPredictionOnTrainDetails:
    """/trains/{train_id}?from_station=... — what the iOS details screen reads first."""

    async def test_terminating_train_omits_inline_prediction(
        self, db_session: AsyncSession
    ):
        """The exact request the app made: train 7832, from_station=NY.

        The client sends the user's selected route origin as ``from_station`` on
        every train it opens, so this is reachable for any train arriving into
        the rider's home station.
        """
        await _seed(db_session)
        today = now_et().date()

        response = await get_train_details(
            train_id=TERMINATING_TRAIN_ID,
            date=today,
            refresh=False,
            include_predictions=True,
            from_station="NY",
            data_source="NJT",
            db=db_session,
        )

        assert response.track_prediction is None, (
            "Train details served an inline track prediction for a station the "
            "train only arrives at: "
            f"{response.track_prediction}"
        )

    async def test_departing_train_keeps_inline_prediction(
        self, db_session: AsyncSession
    ):
        """Control: the same request shape for a train that does depart NY Penn."""
        await _seed(db_session)
        today = now_et().date()

        response = await get_train_details(
            train_id=DEPARTING_TRAIN_ID,
            date=today,
            refresh=False,
            include_predictions=True,
            from_station="NY",
            data_source="NJT",
            db=db_session,
        )

        assert response.track_prediction is not None, (
            "Inline track prediction disappeared for a genuine NY Penn "
            "departure — the guard is over-suppressing"
        )
        assert response.track_prediction.station_code == "NY"
        assert response.track_prediction.platform_probabilities
