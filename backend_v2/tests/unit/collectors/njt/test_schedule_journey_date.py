"""
Unit tests for NJT schedule collector journey_date derivation (issue #1499).

The nightly schedule run covers a ~27-hour window, so it includes trains
departing after the next midnight. Those must be dated by their scheduled
departure date (the convention discovery uses: journey_date =
SCHED_DEP_DATE.date(), see discovery.py), NOT by the nightly run date.

The bug: every item was stamped journey_date = now_et().date() (the 00:30
run date). An after-midnight departure (visible in the window only as a
next-day occurrence) got a SCHEDULED row dated day D while discovery later
looked for day D+1 — both the exact match and the fuzzy match missed, a
duplicate OBSERVED journey was created, and the D-dated SCHEDULED row sat
as a permanent zombie on time-windowed departure queries.

Cross-midnight runs (origin departs before midnight, later stops after) are
the subtle case: each station's schedule item carries that station's own
departure date, so a naive per-item derivation would split one train across
two journey rows. The fix derives each train's journey_date from its
EARLIEST departure across all stations (= the origin), keeping one row.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.njt_api_responses import (
    NJT_TIME_FORMAT,
    StopBuilder,
    create_stop_list_response,
)
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et


@pytest.fixture
def mock_njt_client():
    return AsyncMock(spec=NJTransitClient)


@pytest.fixture
def schedule_collector(mock_njt_client):
    return NJTScheduleCollector(mock_njt_client)


def _station(code: str, name: str, items: list[dict]) -> dict:
    return {"STATION_2CHAR": code, "STATIONNAME": name, "ITEMS": items}


def _item(train_id: str, sched_dep, destination: str = "New York") -> dict:
    return {
        "TRAIN_ID": train_id,
        "SCHED_DEP_DATE": sched_dep.strftime(NJT_TIME_FORMAT),
        "DESTINATION": destination,
        "LINE": "Northeast Corridor",
        "TRACK": None,
    }


class TestScheduleJourneyDate:
    @pytest.mark.asyncio
    async def test_after_midnight_train_dated_by_departure_not_run_date(
        self, db_session: AsyncSession, schedule_collector
    ):
        """A train departing after the next midnight must get journey_date =
        its departure date (matching discovery's convention), not tonight's
        run date. Before the fix this produced a nightly zombie duplicate for
        every 00:00-00:30 departure (issue #1499).
        """
        run_date = now_et().date()
        # Tomorrow 00:15 — inside the 27h window, next service date.
        after_midnight_departure = (now_et() + timedelta(days=1)).replace(
            hour=0, minute=15, second=0, microsecond=0
        )

        schedule_data = [
            _station(
                "TR",
                "Trenton",
                [_item("9001", after_midnight_departure)],
            )
        ]

        await schedule_collector._process_schedule_data(db_session, schedule_data)

        journey = await db_session.scalar(
            select(TrainJourney).where(
                TrainJourney.train_id == "9001",
                TrainJourney.data_source == "NJT",
            )
        )
        assert journey is not None, "SCHEDULED journey must be created"
        assert journey.journey_date == after_midnight_departure.date(), (
            "journey_date must be the scheduled departure's date (what "
            "discovery derives from SCHED_DEP_DATE), not the nightly run date"
        )
        assert journey.journey_date != run_date or (
            after_midnight_departure.date() == run_date
        ), "After-midnight departures must not be stamped with the run date"

    @pytest.mark.asyncio
    async def test_cross_midnight_train_keeps_single_row_dated_by_origin(
        self, db_session: AsyncSession, schedule_collector
    ):
        """A train departing its origin before midnight with later stops
        after midnight must stay ONE journey row, dated by the origin
        departure — even when the post-midnight station is processed first.
        Each station's item carries that station's own departure date, so a
        naive per-item journey_date would split this train into two rows.
        """
        origin_departure = now_et().replace(hour=23, minute=50, second=0, microsecond=0)
        post_midnight_stop_departure = origin_departure + timedelta(minutes=30)
        assert post_midnight_stop_departure.date() != origin_departure.date()

        # Post-midnight station FIRST to prove order-independence: the
        # per-train earliest-departure pre-pass must supply the origin date
        # regardless of which station's item creates the row.
        schedule_data = [
            _station(
                "NP",
                "Newark Penn",
                [_item("9002", post_midnight_stop_departure)],
            ),
            _station(
                "NY",
                "New York Penn",
                [_item("9002", origin_departure)],
            ),
        ]

        await schedule_collector._process_schedule_data(db_session, schedule_data)

        journeys = (
            (
                await db_session.execute(
                    select(TrainJourney).where(
                        TrainJourney.train_id == "9002",
                        TrainJourney.data_source == "NJT",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(journeys) == 1, (
            "A cross-midnight train must produce exactly one journey row, "
            f"got {len(journeys)}: "
            f"{[(j.journey_date, j.scheduled_departure) for j in journeys]}"
        )
        journey = journeys[0]
        assert journey.journey_date == origin_departure.date(), (
            "The single row must be dated by the ORIGIN departure date, not "
            "a post-midnight intermediate stop's date"
        )
        assert journey.scheduled_departure == origin_departure, (
            "earliest-wins must converge scheduled_departure to the origin "
            "time even when a later station's item created the row"
        )

    @pytest.mark.asyncio
    async def test_same_date_train_unchanged_by_fix(
        self, db_session: AsyncSession, schedule_collector
    ):
        """A normal same-day train keeps run-date behavior: journey_date =
        departure date = today (regression guard for the common case).
        """
        departure = now_et().replace(hour=23, minute=0, second=0, microsecond=0)

        schedule_data = [_station("NY", "New York Penn", [_item("9003", departure)])]

        await schedule_collector._process_schedule_data(db_session, schedule_data)

        journey = await db_session.scalar(
            select(TrainJourney).where(
                TrainJourney.train_id == "9003",
                TrainJourney.data_source == "NJT",
            )
        )
        assert journey is not None
        assert journey.journey_date == departure.date()

    @pytest.mark.asyncio
    async def test_far_future_departure_date_rejected(
        self, db_session: AsyncSession, schedule_collector
    ):
        """A malformed-but-parseable SCHED_DEP_DATE that lands far in the
        future must be rejected before persisting, mirroring discovery's
        validate_journey_date guard. parse_njt_time is lenient and journey_date
        has no DB backstop, so otherwise a bad provider timestamp would create
        an out-of-window zombie SCHEDULED row.
        """
        far_future = now_et().replace(second=0, microsecond=0) + timedelta(days=400)

        schedule_data = [_station("NY", "New York Penn", [_item("9005", far_future)])]

        await schedule_collector._process_schedule_data(db_session, schedule_data)

        journey = await db_session.scalar(
            select(TrainJourney).where(
                TrainJourney.train_id == "9005",
                TrainJourney.data_source == "NJT",
            )
        )
        assert journey is None, (
            "A far-future (out-of-window) journey_date must be rejected, not "
            "persisted as a zombie SCHEDULED row"
        )

    @pytest.mark.asyncio
    async def test_stop_list_collection_covers_next_date_rows(
        self, db_session: AsyncSession, schedule_collector, mock_njt_client
    ):
        """The follow-up stop-list pass must pick up SCHEDULED rows dated
        tomorrow (after-midnight departures), not only run-date rows — a
        run-date-only filter would leave next-date rows without stop lists
        until observed.
        """
        tomorrow = now_et().date() + timedelta(days=1)
        departure = (now_et() + timedelta(days=1)).replace(
            hour=0, minute=15, second=0, microsecond=0
        )

        journey = TrainJourney(
            train_id="9004",
            journey_date=tomorrow,
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="TR",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=departure,
            has_complete_journey=False,
            stops_count=0,
        )
        db_session.add(journey)
        await db_session.flush()

        builder = StopBuilder()
        mock_njt_client.get_train_stop_list.return_value = create_stop_list_response(
            train_id="9004",
            line_code="NE",
            destination="New York",
            stops=[
                builder.build_stop(
                    "TR",
                    "Trenton",
                    departure.strftime(NJT_TIME_FORMAT),
                ),
                builder.build_stop(
                    "NY",
                    "New York Penn",
                    (departure + timedelta(minutes=75)).strftime(NJT_TIME_FORMAT),
                ),
            ],
        )

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            db_session
        )

        assert stats["stop_collections_attempted"] == 1, (
            "A next-date SCHEDULED row must be included in the stop-list "
            "collection window"
        )
        assert stats["stop_collections_successful"] == 1

        await db_session.refresh(journey)
        assert journey.has_complete_journey is True
        stop_count = len(
            (
                await db_session.execute(
                    select(JourneyStop).where(JourneyStop.journey_id == journey.id)
                )
            )
            .scalars()
            .all()
        )
        assert stop_count == 2, "Full stop list must replace the placeholder"

    @pytest.mark.asyncio
    async def test_two_same_numbered_runs_in_one_window_get_separate_rows(
        self, db_session: AsyncSession, schedule_collector
    ):
        """The 27h window can contain BOTH service days' occurrence of an
        overnight train (~00:30-03:30 departures): today's 01:00 run AND
        tomorrow's 01:00 run share a TRAIN_ID. A single earliest-per-train
        date collapsed them onto the earlier date, so tomorrow's run lost
        its SCHEDULED row until the next nightly pass (PR #1510 review).
        Run clustering must date each occurrence by its own run's origin,
        producing two rows.
        """
        first_run_origin = now_et().replace(hour=1, minute=0, second=0, microsecond=0)
        first_run_later_stop = first_run_origin + timedelta(minutes=40)
        second_run_origin = first_run_origin + timedelta(days=1)

        schedule_data = [
            # One station's 27h board legitimately lists the train twice.
            _station(
                "NY",
                "New York Penn",
                [
                    _item("9006", first_run_origin),
                    _item("9006", second_run_origin),
                ],
            ),
            # A later stop chains into the FIRST run (40-min gap), proving
            # clustering keeps intra-run stops on the origin's date.
            _station(
                "NP",
                "Newark Penn",
                [_item("9006", first_run_later_stop)],
            ),
        ]

        await schedule_collector._process_schedule_data(db_session, schedule_data)

        journeys = (
            (
                await db_session.execute(
                    select(TrainJourney)
                    .where(
                        TrainJourney.train_id == "9006",
                        TrainJourney.data_source == "NJT",
                    )
                    .order_by(TrainJourney.journey_date)
                )
            )
            .scalars()
            .all()
        )
        assert len(journeys) == 2, (
            "Two same-numbered runs in one window must produce two rows, "
            f"got {[(j.journey_date, j.scheduled_departure) for j in journeys]}"
        )
        first_row, second_row = journeys
        assert first_row.journey_date == first_run_origin.date(), (
            "Today's run must be dated by its own origin"
        )
        assert first_row.scheduled_departure == first_run_origin, (
            "The intra-run later stop must converge to the run origin's "
            "departure, not fork a row or shift the date"
        )
        assert second_row.journey_date == second_run_origin.date(), (
            "Tomorrow's run must keep its own SCHEDULED row dated by its "
            "own origin — not collapse onto today's run"
        )
        assert second_row.scheduled_departure == second_run_origin
