"""
Unit tests for congestion NJT time semantics (issue #1503).

At NJT intermediate stops the raw JourneyStop.updated_departure is the
immutable schedule (DEP_TIME passthrough) while the live delayed estimate is
in updated_arrival (TIME). The congestion pipeline consumed
from_updated_departure raw as the segment departure, so a delayed NJT
train's full lateness was attributed as extra transit time to every segment
it hadn't traversed yet — factor 2-3x "severe" congestion for segments the
train would run at normal speed, continuously re-warmed by the cache
precompute whenever anything ran late.

Covered here: the shared stop_pairs SQL CTE (used by all the optimized
queries), exercised against real PostgreSQL. This is the only consumption
path — the divergent Python fallback that carried a second copy of this
correction was removed in issue #1603.

The from-stop of a segment pair is never the journey terminal (every
consumer discards rows without a to_station), so the intermediate-stop
max() semantics apply unconditionally — no terminal exemption needed.
"""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import _stop_pairs_cte
from trackrat.utils.time import now_et


def _journey(train_id: str, data_source: str) -> TrainJourney:
    return TrainJourney(
        train_id=train_id,
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=now_et() - timedelta(hours=1),
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
        last_updated_at=now_et(),
    )


class TestStopPairsCteNjtCorrection:
    """The CTE must expose an inversion-corrected from_updated_departure."""

    @pytest.mark.asyncio
    async def test_njt_from_updated_departure_uses_live_estimate(
        self, db_session: AsyncSession
    ):
        """For an NJT stop with both fields set, from_updated_departure must
        be GREATEST(updated_departure, updated_arrival) — the live delayed
        estimate, not the schedule.
        """
        schedule = now_et().replace(microsecond=0) - timedelta(minutes=30)
        live_estimate = schedule + timedelta(minutes=25)

        journey = _journey("3855", "NJT")
        db_session.add(journey)
        await db_session.flush()

        stops = [
            JourneyStop(
                journey=journey,
                station_code="NY",
                station_name="New York Penn Station",
                stop_sequence=0,
                scheduled_departure=schedule - timedelta(minutes=20),
                actual_departure=schedule - timedelta(minutes=20),
                has_departed_station=True,
            ),
            JourneyStop(
                journey=journey,
                station_code="NP",
                station_name="Newark Penn Station",
                stop_sequence=1,
                scheduled_departure=schedule,
                updated_departure=schedule,  # raw DEP_TIME = schedule
                updated_arrival=live_estimate,  # raw TIME = live estimate
                has_departed_station=False,
            ),
            JourneyStop(
                journey=journey,
                station_code="TR",
                station_name="Trenton",
                stop_sequence=2,
                scheduled_arrival=schedule + timedelta(minutes=10),
                updated_arrival=live_estimate + timedelta(minutes=10),
                has_departed_station=False,
            ),
        ]
        db_session.add_all(stops)
        await db_session.flush()

        result = await db_session.execute(
            text(
                f"WITH {_stop_pairs_cte('')} "
                "SELECT from_station, from_updated_departure "
                "FROM stop_pairs WHERE journey_id = :jid "
                "AND from_station = 'NP'"
            ),
            {"jid": journey.id, "cutoff_time": now_et() - timedelta(hours=3)},
        )
        row = result.one()

        assert row.from_updated_departure == live_estimate, (
            "NJT from_updated_departure must be the live estimate "
            "(GREATEST of the raw pair), not the schedule sitting in "
            "updated_departure (issue #1503)"
        )

    @pytest.mark.asyncio
    async def test_non_njt_from_updated_departure_passes_through_raw(
        self, db_session: AsyncSession
    ):
        """Non-NJT providers have genuine live estimates in both fields —
        no GREATEST may be applied (arrival can legitimately exceed
        departure by dwell time).
        """
        departure_estimate = now_et().replace(microsecond=0) - timedelta(minutes=20)
        later_arrival_estimate = departure_estimate + timedelta(minutes=5)

        journey = _journey("LIRR_123", "LIRR")
        db_session.add(journey)
        await db_session.flush()

        stops = [
            JourneyStop(
                journey=journey,
                station_code="ST1",
                station_name="Stop One",
                stop_sequence=0,
                updated_departure=departure_estimate,
                updated_arrival=later_arrival_estimate,
                has_departed_station=False,
            ),
            JourneyStop(
                journey=journey,
                station_code="ST2",
                station_name="Stop Two",
                stop_sequence=1,
                updated_arrival=departure_estimate + timedelta(minutes=12),
                has_departed_station=False,
            ),
        ]
        db_session.add_all(stops)
        await db_session.flush()

        result = await db_session.execute(
            text(
                f"WITH {_stop_pairs_cte('')} "
                "SELECT from_station, from_updated_departure "
                "FROM stop_pairs WHERE journey_id = :jid "
                "AND from_station = 'ST1'"
            ),
            {"jid": journey.id, "cutoff_time": now_et() - timedelta(hours=3)},
        )
        row = result.one()

        assert (
            row.from_updated_departure == departure_estimate
        ), "Non-NJT updated_departure must pass through unmodified"
