"""
Cancellation-detection regression tests for the NJT journey collector.

Each DB-level test pins a real, observed NJT API scenario from production so
the rationale survives future refactors. If NJT changes their feed shape in
a way that breaks these, that's a signal to update the fixture and re-derive
the rule — not to silently relax the test.

Background (2026-04-16 production incident):
  * Train #3720 — NJT marked all 8 stops "CANCELLED" — detected correctly.
  * Train #3930 — NJT marked the origin "ON TIME" (train left Trenton before
    being annulled) and all 5 downstream stops "CANCELLED" — MISSED by the
    previous "all stops cancelled" rule.
  * Train #3830 — NJT returned one stop as "CANCELED" (American spelling)
    and fourteen as "CANCELLED" (British) in the same response — MISSED by
    the previous literal string-equality check.

Uses an in-memory SQLite database to avoid requiring PostgreSQL, matching
the pattern in test_terminal_stop_completion.py.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import DateTime as SADateTime
from sqlalchemy import TypeDecorator, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.api import NJTransitStopData
from trackrat.models.database import Base, JourneyStop, TrainJourney
from trackrat.utils.time import now_et
from trackrat.utils.train import is_njt_stop_cancelled

# ---------------------------------------------------------------------------
# Pure-function tests — the helper that backs every call site
# ---------------------------------------------------------------------------


class TestIsNjtStopCancelled:
    """Unit tests for the spelling-tolerant cancellation predicate."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            # Canonical spellings — both observed in production on 2026-04-16
            ("CANCELLED", True),  # British, most common
            ("CANCELED", True),  # American, observed mixed into 3830's stops
            # Defensive case handling — the Pydantic validator already
            # uppercases, but this helper is also called on raw dict data
            # in services/departure.py where no validator has run.
            ("cancelled", True),
            ("Cancelled", True),
            ("canceled", True),
            # Whitespace tolerance — NJT has shipped stray spaces before
            ("  CANCELLED  ", True),
            # Real non-cancellation values NJT actually returns
            ("ON TIME", False),
            ("ONTIME", False),  # NJT uses both spacings inconsistently
            ("LATE", False),
            ("ALL ABOARD", False),
            ("BOARDING", False),
            ("5 MINUTES LATE", False),
            # Empty / missing
            ("", False),
            (None, False),
        ],
    )
    def test_recognizes_cancellation_and_rejects_other_statuses(self, status, expected):
        assert is_njt_stop_cancelled(status) is expected


class TestDetermineTrainStatus:
    """determine_train_status() is a pure function — no DB needed."""

    @staticmethod
    def _stop(status: str | None) -> NJTransitStopData:
        # The Pydantic validator uppercases STOP_STATUS on construction, so
        # "canceled" becomes "CANCELED" — which the previous literal check
        # still missed. The helper catches both spellings post-validation.
        return NJTransitStopData(STOP_STATUS=status)

    def test_all_cancelled_returns_cancelled(self):
        stops = [self._stop("CANCELLED")] * 3
        collector = JourneyCollector(AsyncMock(spec=NJTransitClient))
        assert collector.determine_train_status(stops) == "CANCELLED"

    def test_mixed_spelling_returns_cancelled(self):
        # 3830-shaped: one CANCELED + the rest CANCELLED
        stops = [
            self._stop("CANCELED"),
            self._stop("CANCELLED"),
            self._stop("CANCELLED"),
        ]
        collector = JourneyCollector(AsyncMock(spec=NJTransitClient))
        assert collector.determine_train_status(stops) == "CANCELLED"

    def test_one_cancelled_stop_is_not_all_cancelled(self):
        stops = [self._stop("ON TIME"), self._stop("CANCELLED"), self._stop("ON TIME")]
        collector = JourneyCollector(AsyncMock(spec=NJTransitClient))
        # Only "CANCELLED" when every stop is cancelled. Otherwise this returns
        # something else ("NOT_DEPARTED" / "BOARDING" / etc.) based on DEPARTED.
        assert collector.determine_train_status(stops) != "CANCELLED"


# ---------------------------------------------------------------------------
# SQLite in-memory fixtures — same pattern as test_terminal_stop_completion.py
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_engine():
    """In-memory SQLite engine with timezone-aware datetime handling."""
    import pytz

    _ET = pytz.timezone("America/New_York")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    class TZDateTime(TypeDecorator):
        impl = SADateTime
        cache_ok = True

        def process_bind_param(self, value, _):
            return value

        def process_result_value(self, value, _):
            return _ET.localize(value) if value is not None else value

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SADateTime) and column.type.timezone:
                column.type = TZDateTime()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TZDateTime):
                column.type = SADateTime(timezone=True)

    await engine.dispose()


@pytest.fixture
async def sqlite_session(sqlite_engine) -> AsyncSession:
    session_factory = async_sessionmaker(
        sqlite_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def journey_collector():
    return JourneyCollector(AsyncMock(spec=NJTransitClient))


# ---------------------------------------------------------------------------
# Helpers for DB-level tests
# ---------------------------------------------------------------------------


async def _make_journey_with_stops(
    session: AsyncSession,
    stop_statuses: list[str],
    *,
    train_id: str = "TEST",
    origin_departed: bool = False,
) -> tuple[TrainJourney, list[NJTransitStopData]]:
    """Create a TrainJourney + JourneyStop rows in the DB, and return the
    matching NJTransitStopData list (what the NJT API would return for the
    same journey).

    By default no stop is marked departed so the completion rule cannot fire
    — we're isolating the cancellation rule. Pass origin_departed=True for
    the mid-journey-cancellation scenario where the train physically left
    its first stop before being annulled.
    """
    base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

    journey = TrainJourney(
        train_id=train_id,
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="S0",
        terminal_station_code=f"S{len(stop_statuses) - 1}",
        data_source="NJT",
        observation_type="OBSERVED",
        scheduled_departure=base_time,
        is_cancelled=False,
        is_completed=False,
    )
    session.add(journey)
    await session.flush()

    stops_data: list[NJTransitStopData] = []
    for seq, status in enumerate(stop_statuses):
        sched = base_time + timedelta(minutes=10 * seq)
        code = f"S{seq}"
        name = f"Stop {seq}"
        has_departed = origin_departed and seq == 0

        session.add(
            JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=seq,
                has_departed_station=has_departed,
                scheduled_departure=sched,
                scheduled_arrival=sched,
            )
        )
        stops_data.append(
            NJTransitStopData(
                STATION_2CHAR=code,
                STATIONNAME=name,
                STOP_STATUS=status,
                DEPARTED="YES" if has_departed else "NO",
            )
        )

    await session.flush()
    return journey, stops_data


# ---------------------------------------------------------------------------
# Journey-level cancellation rule — check_journey_completion()
# ---------------------------------------------------------------------------


class TestCheckJourneyCompletionCancellation:
    """The rule at collectors/njt/journey.py (post-edit):

    A journey is cancelled if NJT marks every stop cancelled (train never ran)
    OR the terminal stop is cancelled (train didn't complete its journey).
    """

    @pytest.mark.asyncio
    async def test_all_stops_cancelled_flags_journey(
        self, sqlite_session, journey_collector
    ):
        """Train #3720 shape — NJT explicitly cancelled every stop."""
        journey, stops = await _make_journey_with_stops(
            sqlite_session, ["CANCELLED"] * 8, train_id="3720"
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, stops)

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == "All stops cancelled by NJT"
        assert journey.is_completed is False

    @pytest.mark.asyncio
    async def test_mid_journey_cancellation_flags_journey(
        self, sqlite_session, journey_collector
    ):
        """Train #3930 shape — origin ON TIME, every downstream stop CANCELLED.

        Previously missed because the rule required 100% of stops to be
        CANCELLED, which can't happen once the train has physically left
        its origin.
        """
        statuses = [
            "ON TIME",
            "CANCELLED",
            "CANCELLED",
            "CANCELLED",
            "CANCELLED",
            "CANCELLED",
        ]
        journey, stops = await _make_journey_with_stops(
            sqlite_session,
            statuses,
            train_id="3930",
            origin_departed=True,
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, stops)

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == (
            "Journey terminated before reaching destination"
        )
        assert journey.is_completed is False

    @pytest.mark.asyncio
    async def test_mixed_spelling_flags_journey(
        self, sqlite_session, journey_collector
    ):
        """Train #3830 shape — NJT served one CANCELED + fourteen CANCELLED."""
        statuses = ["CANCELED"] + ["CANCELLED"] * 14
        journey, stops = await _make_journey_with_stops(
            sqlite_session,
            statuses,
            train_id="3830",
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, stops)

        assert journey.is_cancelled is True
        # All stops cancelled (one via American spelling) → full-cancellation reason
        assert journey.cancellation_reason == "All stops cancelled by NJT"

    @pytest.mark.asyncio
    async def test_intermediate_only_cancellation_does_not_flag(
        self, sqlite_session, journey_collector
    ):
        """Safety: a few middle stops cancelled while the terminal is fine
        must NOT mark the journey cancelled. This could happen if NJT only
        skips a few intermediate stops but still runs the route end-to-end.
        """
        statuses = ["ON TIME", "ON TIME", "CANCELLED", "CANCELLED", "ON TIME"]
        journey, stops = await _make_journey_with_stops(
            sqlite_session,
            statuses,
            train_id="PARTIAL",
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, stops)

        assert journey.is_cancelled is False
        assert journey.cancellation_reason is None

    @pytest.mark.asyncio
    async def test_normal_journey_is_not_flagged(
        self, sqlite_session, journey_collector
    ):
        statuses = ["ON TIME", "LATE", "LATE", "ALL ABOARD", "ON TIME"]
        journey, stops = await _make_journey_with_stops(
            sqlite_session,
            statuses,
            train_id="NORMAL",
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, stops)

        assert journey.is_cancelled is False
        assert journey.cancellation_reason is None

    @pytest.mark.asyncio
    async def test_empty_stops_list_is_safe(self, sqlite_session, journey_collector):
        """Upstream may return no stops — must not crash and must not flag."""
        journey, _ = await _make_journey_with_stops(
            sqlite_session,
            ["ON TIME"],
            train_id="NOSTOPS",
        )

        await journey_collector.check_journey_completion(sqlite_session, journey, [])

        assert journey.is_cancelled is False
