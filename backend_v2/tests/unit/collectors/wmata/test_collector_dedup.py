"""
Unit tests for WMATA collector fuzzy dedup logic.

Tests the two-phase deduplication in _discover_trains:
1. Exact match: same train_id + journey_date + data_source
2. Fuzzy match: same line + destination + time window (±5 min)

The bug this tests for: scalar_one_or_none() on the fuzzy query crashes
with MultipleResultsFound when two WMATA trains on the same line/dest
depart within 10 minutes of each other. Fix: use scalars().first().
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from trackrat.collectors.wmata.client import WMATAPrediction
from trackrat.collectors.wmata.collector import (
    DEDUP_TIME_WINDOW_MINUTES,
    WMATACollector,
    _generate_wmata_train_id,
)
from trackrat.models.database import TrainJourney

_PATCH_BASE = "trackrat.collectors.wmata.collector"


def _make_prediction(
    line: str = "RD",
    destination_code: str = "A15",
    location_code: str = "A01",
    minutes: int = 5,
    group: str = "1",
) -> WMATAPrediction:
    return WMATAPrediction(
        location_code=location_code,
        location_name="Test Station",
        destination_code=destination_code,
        destination_name="Test Dest",
        line=line,
        minutes=minutes,
        is_arriving=False,
        is_boarding=False,
        car_count=8,
        group=group,
    )


def _mock_execute_result(has_match: bool):
    """Mock session.execute() result supporting both dedup checks.

    Exact match uses: result.scalar_one_or_none()
    Fuzzy match uses: result.scalars().first()
    """
    result = Mock()
    if has_match:
        result.scalar_one_or_none.return_value = 1
        mock_scalars = Mock()
        mock_scalars.first.return_value = 1
        result.scalars.return_value = mock_scalars
    else:
        result.scalar_one_or_none.return_value = None
        mock_scalars = Mock()
        mock_scalars.first.return_value = None
        result.scalars.return_value = mock_scalars
    return result


def _make_session():
    session = AsyncMock()
    session.add = Mock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def collector():
    client = AsyncMock()
    return WMATACollector(client=client)


# Common patches for _discover_trains
def _common_patches(now=None, origin="B11", route_stops=None, route_info=None):
    """Return a list of patch context managers for _discover_trains."""
    if now is None:
        now = datetime(2026, 3, 28, 10, 0, 0)
    if route_stops is None:
        route_stops = ("RD", ["B11", "A01", "A15"])
    if route_info is None:
        route_info = ("RD", "Red Line", "#FF0000")

    return (
        patch(f"{_PATCH_BASE}.now_et", return_value=now),
        patch(f"{_PATCH_BASE}.infer_wmata_origin", return_value=origin),
        patch(f"{_PATCH_BASE}.get_wmata_route_and_stops", return_value=route_stops),
        patch(f"{_PATCH_BASE}.get_wmata_route_info", return_value=route_info),
        patch(f"{_PATCH_BASE}.WMATA_STATION_NAMES", {"A15": "Shady Grove", "B11": "Glenmont", "J03": "Largo", "C13": "Pentagon"}),
    )


class TestExactMatchDedup:
    """Check 1: exact train_id + date + data_source."""

    @pytest.mark.asyncio
    async def test_exact_match_skips_journey(self, collector):
        """Journey with same synthetic train_id already exists -> skip."""
        session = _make_session()
        session.execute = AsyncMock(return_value=_mock_execute_result(has_match=True))

        pred = _make_prediction(line="RD", destination_code="A15", minutes=10)
        patches = _common_patches()

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = await collector._discover_trains(session, [pred], [])

        assert result["skipped_existing"] == 1
        assert result["new_journeys"] == 0
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_exact_match_proceeds_to_fuzzy_then_creates(self, collector):
        """No exact match, no fuzzy match -> new journey created."""
        session = _make_session()
        session.execute = AsyncMock(
            side_effect=[
                _mock_execute_result(has_match=False),  # exact: miss
                _mock_execute_result(has_match=False),  # fuzzy: miss
            ]
        )

        pred = _make_prediction(line="RD", destination_code="A15", minutes=10)
        patches = _common_patches()

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = await collector._discover_trains(session, [pred], [])

        assert result["new_journeys"] == 1
        assert result["skipped_existing"] == 0

        # Find the TrainJourney among all added objects
        # (collector also adds JourneyStop and JourneySnapshot objects)
        added_journeys = [
            call.args[0] for call in session.add.call_args_list
            if isinstance(call.args[0], TrainJourney)
        ]
        assert len(added_journeys) == 1

        journey = added_journeys[0]
        assert journey.data_source == "WMATA"
        assert journey.line_code == "RD"
        assert journey.terminal_station_code == "A15"
        assert journey.observation_type == "OBSERVED"


class TestFuzzyMatchDedup:
    """Check 2: same line + destination + time window (±5 min)."""

    @pytest.mark.asyncio
    async def test_fuzzy_match_skips_journey(self, collector):
        """No exact match but fuzzy match hit -> skip."""
        session = _make_session()
        session.execute = AsyncMock(
            side_effect=[
                _mock_execute_result(has_match=False),  # exact: miss
                _mock_execute_result(has_match=True),   # fuzzy: hit
            ]
        )

        pred = _make_prediction(line="BL", destination_code="J03", minutes=8)
        patches = _common_patches(
            origin="C13",
            route_stops=("BL", ["C13", "A01", "J03"]),
            route_info=("BL", "Blue Line", "#0000FF"),
        )

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = await collector._discover_trains(session, [pred], [])

        assert result["skipped_existing"] == 1
        assert result["new_journeys"] == 0
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_fuzzy_uses_scalars_first_not_scalar_one_or_none(self, collector):
        """Verify the fuzzy query uses scalars().first() which handles
        multiple matching rows without raising MultipleResultsFound.

        This is the regression test for the production bug where
        scalar_one_or_none() crashed when 2+ trains on the same line
        had departures within the 10-minute window.
        """
        session = _make_session()

        # Exact match: miss
        exact_result = _mock_execute_result(has_match=False)

        # Fuzzy match: simulate multiple rows by verifying .scalars().first() is called
        fuzzy_result = Mock()
        fuzzy_result.scalar_one_or_none = Mock(
            side_effect=Exception("scalar_one_or_none should NOT be called on fuzzy result")
        )
        mock_scalars = Mock()
        mock_scalars.first.return_value = 42  # some journey id
        fuzzy_result.scalars.return_value = mock_scalars

        session.execute = AsyncMock(side_effect=[exact_result, fuzzy_result])

        pred = _make_prediction(line="RD", destination_code="A15", minutes=5)
        patches = _common_patches()

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = await collector._discover_trains(session, [pred], [])

        # Fuzzy match found a journey, so it should be skipped
        assert result["skipped_existing"] == 1

        # Verify scalars().first() was called, NOT scalar_one_or_none()
        fuzzy_result.scalars.assert_called_once()
        mock_scalars.first.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_lines_not_fuzzy_matched(self, collector):
        """Two trains with same destination but different lines both create journeys."""
        session = _make_session()
        session.execute = AsyncMock(
            side_effect=[
                _mock_execute_result(has_match=False),  # train 1 exact
                _mock_execute_result(has_match=False),  # train 1 fuzzy
                _mock_execute_result(has_match=False),  # train 2 exact
                _mock_execute_result(has_match=False),  # train 2 fuzzy
            ]
        )

        pred_rd = _make_prediction(line="RD", destination_code="A15", minutes=10, group="1")
        pred_bl = _make_prediction(line="BL", destination_code="A15", minutes=10, group="2")

        patches = _common_patches()

        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = await collector._discover_trains(session, [pred_rd, pred_bl], [])

        assert result["new_journeys"] == 2
        assert result["skipped_existing"] == 0


class TestDedupTimeWindow:
    """Verify time window constant and train ID generation."""

    def test_dedup_window_is_5_minutes(self):
        assert DEDUP_TIME_WINDOW_MINUTES == 5


class TestGenerateWMATATrainId:
    """Tests for _generate_wmata_train_id synthetic ID generation."""

    def test_basic_format(self):
        dt = datetime(2026, 3, 28, 10, 0, 0)
        tid = _generate_wmata_train_id("RD", "A15", dt)
        assert tid.startswith("WMATA_RD_A15_")

    def test_rounds_down_below_30s(self):
        dt = datetime(2026, 3, 28, 10, 0, 29)
        rounded_dt = datetime(2026, 3, 28, 10, 0, 0)
        tid = _generate_wmata_train_id("RD", "A15", dt)
        expected_ts = int(rounded_dt.timestamp())
        assert tid == f"WMATA_RD_A15_{expected_ts}"

    def test_rounds_up_at_30s(self):
        dt = datetime(2026, 3, 28, 10, 0, 30)
        rounded_dt = datetime(2026, 3, 28, 10, 1, 0)
        tid = _generate_wmata_train_id("RD", "A15", dt)
        expected_ts = int(rounded_dt.timestamp())
        assert tid == f"WMATA_RD_A15_{expected_ts}"

    def test_same_minute_same_id(self):
        """Two times within same rounded minute produce identical IDs."""
        dt1 = datetime(2026, 3, 28, 10, 5, 10)
        dt2 = datetime(2026, 3, 28, 10, 5, 20)
        assert _generate_wmata_train_id("BL", "J03", dt1) == \
               _generate_wmata_train_id("BL", "J03", dt2)

    def test_different_lines_different_ids(self):
        dt = datetime(2026, 3, 28, 10, 0, 0)
        assert _generate_wmata_train_id("RD", "A15", dt) != \
               _generate_wmata_train_id("BL", "A15", dt)

    def test_different_destinations_different_ids(self):
        dt = datetime(2026, 3, 28, 10, 0, 0)
        assert _generate_wmata_train_id("RD", "A15", dt) != \
               _generate_wmata_train_id("RD", "B11", dt)
