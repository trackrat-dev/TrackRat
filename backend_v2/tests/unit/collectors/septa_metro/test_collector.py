"""Unit tests for SeptaMetroCollector.

Metro trip_ids are already unique per service day, so ``_generate_train_id`` is
the identity function. The collector otherwise mirrors the MBTA absolute-time
flow: group arrivals by trip, back-fill from GTFS static when available, else
build the journey directly from the real-time arrivals.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.septa_common import SeptaFeedFetchError
from trackrat.collectors.septa_metro.client import SeptaMetroArrival, SeptaMetroClient
from trackrat.collectors.septa_metro.collector import (
    SeptaMetroCollector,
    _generate_train_id,
)

_T = datetime(2026, 7, 18, 15, 0, 0, tzinfo=UTC)


def _arrival(
    station_code: str,
    trip_id: str,
    route_id: str,
    arrival_time: datetime,
    *,
    departure_time: datetime | None = None,
    delay_seconds: int = 0,
) -> SeptaMetroArrival:
    return SeptaMetroArrival(
        station_code=station_code,
        gtfs_stop_id=station_code.replace("SEPM", ""),
        trip_id=trip_id,
        route_id=route_id,
        direction_id=0,
        headsign=None,
        arrival_time=arrival_time,
        departure_time=departure_time,
        delay_seconds=delay_seconds,
        track=None,
    )


class TestGenerateTrainId:
    """Metro trip_ids are used verbatim as the train id."""

    def test_returns_trip_id_unchanged(self):
        assert _generate_train_id("12345") == "12345"

    def test_returns_complex_trip_id_unchanged(self):
        assert _generate_train_id("M1_weekday_007") == "M1_weekday_007"

    def test_empty_string(self):
        assert _generate_train_id("") == ""


class TestCollectorInit:
    def test_creates_own_client(self):
        collector = SeptaMetroCollector()
        assert collector.client is not None
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        client = SeptaMetroClient()
        collector = SeptaMetroCollector(client=client)
        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_owned_client(self):
        collector = SeptaMetroCollector()
        collector.client = AsyncMock(spec=SeptaMetroClient)
        collector._owns_client = True
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client_not_closed(self):
        client = AsyncMock(spec=SeptaMetroClient)
        collector = SeptaMetroCollector(client=client)
        await collector.close()
        client.close.assert_not_called()


class TestCollect:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=SeptaMetroClient)

    @pytest.fixture
    def collector(self, mock_client):
        return SeptaMetroCollector(client=mock_client)

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.begin_nested = MagicMock()
        session.begin_nested.return_value.__aenter__ = AsyncMock()
        session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
        return session

    @pytest.mark.asyncio
    async def test_empty_arrivals_returns_zero_stats(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = []
        stats = await collector.collect(mock_session)
        assert stats["total_arrivals"] == 0
        assert stats["discovered"] == 0
        assert stats["updated"] == 0
        mock_client.get_all_arrivals.assert_awaited_once_with(use_cache=False)

    @pytest.mark.asyncio
    async def test_groups_arrivals_by_trip(self, collector, mock_client, mock_session):
        """Arrivals are grouped by trip_id → _process_trip called once per unique trip."""
        arrivals = [
            _arrival("SEPM1272", "trip_A", "M1", _T),
            _arrival("SEPM1273", "trip_A", "M1", _T + timedelta(minutes=5)),
            _arrival("SEPM1392", "trip_B", "L1", _T),
        ]
        mock_client.get_all_arrivals.return_value = arrivals
        collector._process_trip = AsyncMock(return_value=("discovered", None))

        mock_stale = MagicMock()
        mock_stale.scalars.return_value = []
        mock_session.execute.return_value = mock_stale

        stats = await collector.collect(mock_session)

        assert stats["total_arrivals"] == 3
        assert collector._process_trip.call_count == 2  # two unique trips

    @pytest.mark.asyncio
    async def test_present_trip_is_reconciled_when_local_processing_skips_it(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = [
            _arrival("SEPM1272", "present_trip", "M1", _T)
        ]
        collector._process_trip = AsyncMock(return_value=(None, None))

        with (
            patch(
                "trackrat.collectors.septa_metro.collector."
                "TransitAnalyzer.analyze_new_segments_bulk",
                new_callable=AsyncMock,
            ),
            patch(
                "trackrat.collectors.septa_metro.collector."
                "reconcile_journey_omissions",
                new_callable=AsyncMock,
                return_value=2,
            ) as reconcile,
        ):
            stats = await collector.collect(mock_session)

        assert stats["expired"] == 2
        assert reconcile.await_args.args[3] == {("present_trip", _T.date())}

    @pytest.mark.asyncio
    async def test_fetch_error_never_reconciles_omissions(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.side_effect = SeptaFeedFetchError("unavailable")

        with patch(
            "trackrat.collectors.septa_metro.collector.reconcile_journey_omissions",
            new_callable=AsyncMock,
        ) as reconcile:
            stats = await collector.collect(mock_session)

        assert stats["errors"] == 1
        reconcile.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_trip_failures_never_reconcile_omissions(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = [
            _arrival("SEPM1272", "broken_trip", "M1", _T)
        ]
        collector._process_trip = AsyncMock(side_effect=ValueError("bad trip"))

        with patch(
            "trackrat.collectors.septa_metro.collector.reconcile_journey_omissions",
            new_callable=AsyncMock,
        ) as reconcile:
            stats = await collector.collect(mock_session)

        assert stats["errors"] == 2
        reconcile.assert_not_awaited()


class TestProcessTrip:
    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    @pytest.mark.asyncio
    async def test_empty_arrivals_returns_none(self, collector):
        session = AsyncMock()
        result, journey = await collector._process_trip(session, "trip_1", [])
        assert result is None
        assert journey is None

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.now_et")
    async def test_discovers_new_journey_without_static(self, mock_now, collector):
        """No GTFS static schedule → build the journey directly from RT arrivals."""
        mock_now.return_value = _T

        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)

        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute.return_value = no_existing

        arrivals = [
            _arrival(
                "SEPM1272", "trip_1", "M1", _T, departure_time=_T + timedelta(minutes=1)
            ),
            _arrival("SEPM1273", "trip_1", "M1", _T + timedelta(minutes=5)),
            _arrival("SEPM1392", "trip_1", "M1", _T + timedelta(minutes=10)),
        ]

        result, journey = await collector._process_trip(session, "trip_1", arrivals)

        assert result == "discovered"
        assert journey is not None
        assert journey.data_source == "SEPTA_METRO"
        assert journey.train_id == "trip_1"
        assert journey.line_code == "SEPTA-M1"
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.now_et")
    async def test_updates_existing_journey(self, mock_now, collector):
        """An existing journey for the same train/day is updated, not recreated."""
        mock_now.return_value = _T

        existing_journey = MagicMock()
        existing_journey.id = 1
        existing_journey.train_id = "trip_1"
        existing_journey.data_source = "SEPTA_METRO"
        existing_journey.stops = []
        existing_journey.is_completed = False
        existing_journey.is_cancelled = False
        existing_journey.is_expired = True
        existing_journey.api_error_count = 3

        found = MagicMock()
        found.scalar_one_or_none.return_value = existing_journey
        session = AsyncMock()
        session.execute.return_value = found

        arrivals = [
            _arrival("SEPM1272", "trip_1", "M1", _T),
            _arrival("SEPM1273", "trip_1", "M1", _T + timedelta(minutes=5)),
        ]

        result, journey = await collector._process_trip(session, "trip_1", arrivals)

        assert result == "updated"
        assert journey is existing_journey
        assert journey.api_error_count == 0
        assert journey.is_expired is False


class TestJourneyDetails:
    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    @pytest.mark.asyncio
    async def test_skips_non_metro_journey(self, collector):
        """A journey from another data source must not touch the Metro feed."""
        journey = MagicMock()
        journey.data_source = "LIRR"
        session = AsyncMock()

        await collector.collect_journey_details(session, journey)
        collector.client.get_all_arrivals.assert_not_called()


class TestRun:
    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.get_session")
    async def test_run_returns_stats(self, mock_get_session):
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock(spec=SeptaMetroClient)
        mock_client.get_all_arrivals.return_value = []

        collector = SeptaMetroCollector(client=mock_client)
        stats = await collector.run()

        assert isinstance(stats, dict)
        assert "discovered" in stats
        assert "updated" in stats
        assert "errors" in stats
