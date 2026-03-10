"""
Tests for MTA service alerts collector.

Tests parsing logic, alert type classification, and database upsert.
Uses real PostgreSQL via db_session fixture.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.service_alerts import (
    ParsedAlert,
    classify_alert_type,
    extract_english_text,
    parse_alert_entity,
    upsert_service_alerts,
)
from trackrat.models.database import ServiceAlert


class TestClassifyAlertType:
    """Tests for classify_alert_type() entity ID classification."""

    def test_planned_work_prefix(self):
        """Entity IDs starting with 'lmm:planned_work:' classify as planned_work."""
        assert classify_alert_type("lmm:planned_work:12345") == "planned_work"

    def test_alert_prefix(self):
        """Entity IDs starting with 'lmm:alert:' classify as alert."""
        assert classify_alert_type("lmm:alert:678901") == "alert"

    def test_elevator_prefix(self):
        """Entity IDs containing '#EL' classify as elevator."""
        assert classify_alert_type("A42N#EL001") == "elevator"

    def test_unknown_prefix(self):
        """Unrecognized entity IDs classify as unknown."""
        assert classify_alert_type("some_other_id_format") == "unknown"

    def test_planned_work_various_numbers(self):
        """Planned work classification works with various numeric suffixes."""
        assert classify_alert_type("lmm:planned_work:99999") == "planned_work"
        assert classify_alert_type("lmm:planned_work:1") == "planned_work"

    def test_elevator_mid_string(self):
        """Elevator classification works when #EL is in the middle of the ID."""
        assert classify_alert_type("STOP123#EL456") == "elevator"


class TestExtractEnglishText:
    """Tests for extract_english_text() protobuf text extraction."""

    def test_english_translation(self):
        """Extracts English text when available."""
        ts = MagicMock()
        en = MagicMock(language="en", text="Service change on G line")
        ts.translation = [en]
        assert extract_english_text(ts) == "Service change on G line"

    def test_fallback_to_first_translation(self):
        """Falls back to first translation when no English available."""
        ts = MagicMock()
        es = MagicMock(language="es", text="Cambio de servicio")
        ts.translation = [es]
        assert extract_english_text(ts) == "Cambio de servicio"

    def test_none_for_empty(self):
        """Returns None for empty TranslatedString."""
        ts = MagicMock()
        ts.translation = []
        assert extract_english_text(ts) is None

    def test_none_for_none_input(self):
        """Returns None for None input."""
        assert extract_english_text(None) is None

    def test_prefers_english_over_other(self):
        """When multiple translations exist, English is preferred."""
        ts = MagicMock()
        es = MagicMock(language="es", text="Cambio de servicio")
        en = MagicMock(language="en", text="Service change")
        ts.translation = [es, en]
        assert extract_english_text(ts) == "Service change"


class TestParseAlertEntity:
    """Tests for parse_alert_entity() protobuf parsing."""

    def _make_entity(
        self,
        entity_id: str = "lmm:planned_work:12345",
        route_ids: list[str] | None = None,
        header: str = "G train: No service",
        description: str | None = "Planned maintenance work",
        periods: list[tuple[int, int]] | None = None,
    ) -> MagicMock:
        """Build a mock GTFS-RT entity for testing."""
        entity = MagicMock()
        entity.id = entity_id
        entity.HasField.return_value = True

        alert = MagicMock()
        entity.alert = alert

        # Route IDs
        if route_ids is None:
            route_ids = ["G"]
        informed_entities = []
        for rid in route_ids:
            ie = MagicMock()
            ie.route_id = rid
            informed_entities.append(ie)
        alert.informed_entity = informed_entities

        # Header text
        header_ts = MagicMock()
        header_trans = MagicMock(language="en", text=header)
        header_ts.translation = [header_trans]
        alert.header_text = header_ts

        # Description text
        if description:
            desc_ts = MagicMock()
            desc_trans = MagicMock(language="en", text=description)
            desc_ts.translation = [desc_trans]
            alert.description_text = desc_ts
        else:
            alert.description_text = MagicMock(translation=[])

        # Active periods
        if periods is None:
            periods = [(1710100000, 1710200000)]
        active_periods = []
        for start, end in periods:
            period = MagicMock()
            period.start = start
            period.end = end
            active_periods.append(period)
        alert.active_period = active_periods

        return entity

    def test_parses_planned_work(self):
        """Correctly parses a planned work alert entity."""
        entity = self._make_entity()
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.alert_id == "lmm:planned_work:12345"
        assert result.alert_type == "planned_work"
        assert result.affected_route_ids == ["G"]
        assert result.header_text == "G train: No service"
        assert result.description_text == "Planned maintenance work"
        assert len(result.active_periods) == 1
        assert result.active_periods[0]["start"] == 1710100000
        assert result.active_periods[0]["end"] == 1710200000

    def test_parses_realtime_alert(self):
        """Correctly parses a real-time alert entity."""
        entity = self._make_entity(
            entity_id="lmm:alert:67890",
            route_ids=["4", "5", "6"],
            header="Delays on 4/5/6 lines",
        )
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.alert_type == "alert"
        assert result.affected_route_ids == ["4", "5", "6"]

    def test_parses_elevator_alert(self):
        """Correctly parses an elevator/escalator alert entity."""
        entity = self._make_entity(
            entity_id="A42N#EL001",
            header="Elevator out of service at 42 St",
        )
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.alert_type == "elevator"

    def test_skips_non_alert_entity(self):
        """Returns None for entities without an alert field."""
        entity = MagicMock()
        entity.HasField.return_value = False
        assert parse_alert_entity(entity) is None

    def test_skips_alert_without_header(self):
        """Returns None for alerts with no header text."""
        entity = self._make_entity(header="")
        # Override header to return None
        entity.alert.header_text = MagicMock(translation=[])
        assert parse_alert_entity(entity) is None

    def test_multiple_active_periods(self):
        """Parses alerts with multiple active periods (recurring work)."""
        entity = self._make_entity(
            periods=[(1710100000, 1710200000), (1710700000, 1710800000)]
        )
        result = parse_alert_entity(entity)

        assert result is not None
        assert len(result.active_periods) == 2
        assert result.active_periods[1]["start"] == 1710700000

    def test_deduplicates_route_ids(self):
        """Route IDs are not duplicated when repeated in informed_entity."""
        entity = self._make_entity(route_ids=["G", "G", "G"])
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.affected_route_ids == ["G"]


@pytest.mark.asyncio
class TestUpsertServiceAlerts:
    """Tests for upsert_service_alerts() database operations."""

    def _make_parsed_alert(
        self,
        alert_id: str = "lmm:planned_work:100",
        alert_type: str = "planned_work",
        route_ids: list[str] | None = None,
        header: str = "G train: Service change",
    ) -> ParsedAlert:
        return ParsedAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            affected_route_ids=route_ids or ["G"],
            header_text=header,
            description_text="Details here",
            active_periods=[{"start": 1710100000, "end": 1710200000}],
        )

    async def test_inserts_new_alerts(self, db_session: AsyncSession):
        """New alerts are inserted into the database."""
        alerts = [
            self._make_parsed_alert(alert_id="lmm:planned_work:1"),
            self._make_parsed_alert(alert_id="lmm:planned_work:2"),
        ]
        stats = await upsert_service_alerts(db_session, alerts, "SUBWAY")
        await db_session.flush()

        assert stats["inserted"] == 2
        assert stats["updated"] == 0
        assert stats["deactivated"] == 0

        result = await db_session.execute(
            select(ServiceAlert).where(ServiceAlert.data_source == "SUBWAY")
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert all(r.is_active for r in rows)

    async def test_updates_changed_alerts(self, db_session: AsyncSession):
        """Existing alerts are updated when content changes."""
        # Insert initial
        alerts = [self._make_parsed_alert(alert_id="lmm:planned_work:10")]
        await upsert_service_alerts(db_session, alerts, "SUBWAY")
        await db_session.flush()

        # Update with changed header
        updated = [
            self._make_parsed_alert(
                alert_id="lmm:planned_work:10",
                header="UPDATED: G train service change",
            )
        ]
        stats = await upsert_service_alerts(db_session, updated, "SUBWAY")
        await db_session.flush()

        assert stats["updated"] == 1
        assert stats["inserted"] == 0

        result = await db_session.execute(
            select(ServiceAlert).where(ServiceAlert.alert_id == "lmm:planned_work:10")
        )
        row = result.scalar_one()
        assert row.header_text == "UPDATED: G train service change"

    async def test_deactivates_missing_alerts(self, db_session: AsyncSession):
        """Alerts no longer in the feed are deactivated."""
        # Insert two alerts
        alerts = [
            self._make_parsed_alert(alert_id="lmm:planned_work:20"),
            self._make_parsed_alert(alert_id="lmm:planned_work:21"),
        ]
        await upsert_service_alerts(db_session, alerts, "SUBWAY")
        await db_session.flush()

        # New feed only has one alert
        updated = [self._make_parsed_alert(alert_id="lmm:planned_work:20")]
        stats = await upsert_service_alerts(db_session, updated, "SUBWAY")
        await db_session.flush()

        assert stats["deactivated"] == 1

        result = await db_session.execute(
            select(ServiceAlert).where(ServiceAlert.alert_id == "lmm:planned_work:21")
        )
        row = result.scalar_one()
        assert row.is_active is False

    async def test_no_changes_for_identical_alert(self, db_session: AsyncSession):
        """No updates when alert content is identical."""
        alerts = [self._make_parsed_alert(alert_id="lmm:planned_work:30")]
        await upsert_service_alerts(db_session, alerts, "SUBWAY")
        await db_session.flush()

        # Upsert again with same data
        stats = await upsert_service_alerts(db_session, alerts, "SUBWAY")

        assert stats["updated"] == 0
        assert stats["inserted"] == 0
        assert stats["deactivated"] == 0

    async def test_data_source_isolation(self, db_session: AsyncSession):
        """Alerts from different data sources don't interfere."""
        subway_alerts = [self._make_parsed_alert(alert_id="lmm:planned_work:40")]
        lirr_alerts = [self._make_parsed_alert(alert_id="lmm:planned_work:41")]

        await upsert_service_alerts(db_session, subway_alerts, "SUBWAY")
        await upsert_service_alerts(db_session, lirr_alerts, "LIRR")
        await db_session.flush()

        # Now update only SUBWAY with empty feed
        stats = await upsert_service_alerts(db_session, [], "SUBWAY")
        await db_session.flush()

        assert stats["deactivated"] == 1

        # LIRR alert should still be active
        result = await db_session.execute(
            select(ServiceAlert).where(
                ServiceAlert.data_source == "LIRR",
                ServiceAlert.is_active.is_(True),
            )
        )
        lirr_row = result.scalar_one()
        assert lirr_row.alert_id == "lmm:planned_work:41"
