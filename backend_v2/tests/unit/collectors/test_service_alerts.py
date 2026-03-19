"""
Tests for service alerts collector (MTA + NJT).

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
    fetch_and_parse_njt_alerts,
    parse_alert_entity,
    parse_njt_line_scope,
    parse_njt_message,
    parse_njt_station_scope,
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


class TestFetchAndParseAlertsDedupe:
    """Tests for duplicate entity ID deduplication in fetch_and_parse_alerts.

    MTA feeds (especially SUBWAY) can contain duplicate entity IDs —
    e.g. elevator alerts like '235N#EL301' appearing twice. Without
    deduplication, the second occurrence causes a UniqueViolationError
    during upsert.
    """

    @pytest.mark.asyncio
    async def test_deduplicates_alerts_by_entity_id(self):
        """Duplicate entity IDs in the feed are deduplicated (last wins).

        Reproduces the production bug where MTA SUBWAY feed contains
        duplicate elevator alert entity IDs, causing IntegrityError on
        INSERT into service_alerts table.
        """
        from unittest.mock import AsyncMock, patch

        from trackrat.collectors.service_alerts import fetch_and_parse_alerts

        # Build a protobuf feed with duplicate entity IDs
        from google.transit import gtfs_realtime_pb2

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = 1710100000

        # First occurrence of duplicate elevator alert
        e1 = feed.entity.add()
        e1.id = "235N#EL301"
        a1 = e1.alert
        a1.informed_entity.add().route_id = "1"
        t1 = a1.header_text.translation.add()
        t1.language = "en"
        t1.text = "Elevator out of service (first)"

        # Duplicate with same entity ID but different text
        e2 = feed.entity.add()
        e2.id = "235N#EL301"
        a2 = e2.alert
        a2.informed_entity.add().route_id = "1"
        t2 = a2.header_text.translation.add()
        t2.language = "en"
        t2.text = "Elevator out of service (second)"

        # A unique alert to verify non-duplicates are preserved
        e3 = feed.entity.add()
        e3.id = "lmm:planned_work:99999"
        a3 = e3.alert
        a3.informed_entity.add().route_id = "L"
        t3 = a3.header_text.translation.add()
        t3.language = "en"
        t3.text = "L train service change"

        # Mock the HTTP fetch to return our crafted feed
        mock_response = AsyncMock()
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("trackrat.collectors.service_alerts.httpx.AsyncClient", return_value=mock_client):
            alerts = await fetch_and_parse_alerts("https://fake-feed-url", "SUBWAY")

        # Should have 2 alerts (deduped), not 3
        assert len(alerts) == 2, (
            f"Expected 2 alerts after dedup, got {len(alerts)}. "
            f"IDs: {[a.alert_id for a in alerts]}"
        )

        alert_ids = [a.alert_id for a in alerts]
        assert "235N#EL301" in alert_ids, "Elevator alert should be present"
        assert "lmm:planned_work:99999" in alert_ids, "Planned work alert should be present"

        # Last occurrence should win
        elevator_alert = next(a for a in alerts if a.alert_id == "235N#EL301")
        assert elevator_alert.header_text == "Elevator out of service (second)", (
            "Last occurrence of duplicate entity ID should win"
        )


class TestFetchAndParseNjtAlertsDedupe:
    """Tests for duplicate message deduplication in fetch_and_parse_njt_alerts.

    NJT API can return duplicate MSG_IDs, and messages without MSG_ID
    use a text hash — identical messages would produce the same alert_id.
    Without deduplication, these cause UniqueViolationError on upsert.
    """

    @pytest.mark.asyncio
    async def test_deduplicates_njt_messages_by_alert_id(self):
        """Duplicate NJT MSG_IDs are deduplicated (last wins)."""
        from unittest.mock import AsyncMock, patch

        duplicate_messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train #100 is delayed.",
                "MSG_PUBDATE": "3/19/2026 8:00:00 PM",
                "MSG_ID": "9999999",
                "MSG_AGENCY": "NJT",
                "MSG_SOURCE": "RSS_NJTRailAlerts",
                "MSG_STATION_SCOPE": " ",
                "MSG_LINE_SCOPE": "*Northeast Corridor Line",
                "MSG_PUBDATE_UTC": "3/20/2026 12:00:00 AM",
            },
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NEC train #100 is delayed (updated).",
                "MSG_PUBDATE": "3/19/2026 8:05:00 PM",
                "MSG_ID": "9999999",  # Same MSG_ID — duplicate
                "MSG_AGENCY": "NJT",
                "MSG_SOURCE": "RSS_NJTRailAlerts",
                "MSG_STATION_SCOPE": " ",
                "MSG_LINE_SCOPE": "*Northeast Corridor Line",
                "MSG_PUBDATE_UTC": "3/20/2026 12:05:00 AM",
            },
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "NJCL service restored.",
                "MSG_PUBDATE": "3/19/2026 8:10:00 PM",
                "MSG_ID": "9999998",
                "MSG_AGENCY": "NJT",
                "MSG_SOURCE": "RSS_NJTRailAlerts",
                "MSG_STATION_SCOPE": " ",
                "MSG_LINE_SCOPE": "*North Jersey Coast Line",
                "MSG_PUBDATE_UTC": "3/20/2026 12:10:00 AM",
            },
        ]

        mock_client = AsyncMock()
        mock_client.get_station_messages.return_value = duplicate_messages
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "trackrat.collectors.service_alerts.NJTransitClient",
            return_value=mock_client,
        ):
            alerts = await fetch_and_parse_njt_alerts()

        # Should have 2 alerts (deduped), not 3
        assert len(alerts) == 2, (
            f"Expected 2 alerts after dedup, got {len(alerts)}. "
            f"IDs: {[a.alert_id for a in alerts]}"
        )

        # Last occurrence should win for the duplicate
        deduped = next(a for a in alerts if a.alert_id == "njt-rss-9999999")
        assert "updated" in deduped.header_text, (
            "Last occurrence of duplicate MSG_ID should win"
        )

    @pytest.mark.asyncio
    async def test_deduplicates_njt_hash_based_ids(self):
        """Messages without MSG_ID that produce the same text hash are deduplicated."""
        from unittest.mock import AsyncMock, patch

        # Two identical messages without MSG_ID — same text = same hash = same alert_id
        identical_messages = [
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "System-wide advisory message.",
                "MSG_PUBDATE": "3/19/2026 8:00:00 PM",
                "MSG_ID": "",
                "MSG_AGENCY": "NJT",
                "MSG_SOURCE": "",
                "MSG_STATION_SCOPE": "*Newark Penn Station",
                "MSG_LINE_SCOPE": " ",
                "MSG_PUBDATE_UTC": "3/20/2026 12:00:00 AM",
            },
            {
                "MSG_TYPE": "banner",
                "MSG_TEXT": "System-wide advisory message.",  # Identical text
                "MSG_PUBDATE": "3/19/2026 8:00:00 PM",
                "MSG_ID": "",
                "MSG_AGENCY": "NJT",
                "MSG_SOURCE": "",
                "MSG_STATION_SCOPE": "*Newark Penn Station",
                "MSG_LINE_SCOPE": " ",
                "MSG_PUBDATE_UTC": "3/20/2026 12:00:00 AM",
            },
        ]

        mock_client = AsyncMock()
        mock_client.get_station_messages.return_value = identical_messages
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "trackrat.collectors.service_alerts.NJTransitClient",
            return_value=mock_client,
        ):
            alerts = await fetch_and_parse_njt_alerts()

        assert len(alerts) == 1, (
            f"Identical NJT messages should deduplicate to 1, got {len(alerts)}"
        )


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


class TestParseNjtLineScope:
    """Tests for parse_njt_line_scope() NJT line name -> code mapping."""

    def test_single_line(self):
        """Single line scope maps to correct code."""
        assert parse_njt_line_scope("*North Jersey Coast Line") == ["NC"]

    def test_me_line_maps_to_morristown_and_gladstone(self):
        """ME Line maps to both ME and GL codes."""
        assert parse_njt_line_scope("*ME Line") == ["ME", "GL"]

    def test_multiple_lines_space_separated(self):
        """Multiple lines are space-delimited with * prefix."""
        result = parse_njt_line_scope("*Main Line *Bergen County Line")
        assert result == ["MA", "BE"]

    def test_empty_scope(self):
        """Single space means no line scope."""
        assert parse_njt_line_scope(" ") == []

    def test_empty_string(self):
        """Empty string returns empty list."""
        assert parse_njt_line_scope("") == []

    def test_none(self):
        """None returns empty list."""
        assert parse_njt_line_scope(None) == []  # type: ignore[arg-type]

    def test_all_known_lines(self):
        """All NJT lines that appear in the API are mapped."""
        known_scopes = [
            ("*Northeast Corridor Line", ["NE"]),
            ("*North Jersey Coast Line", ["NC"]),
            ("*ME Line", ["ME", "GL"]),
            ("*Raritan Valley Line", ["RV"]),
            ("*Montclair-Boonton Line", ["MO"]),
            ("*Main Line", ["MA"]),
            ("*Bergen County Line", ["BE"]),
            ("*Port Jervis Line", ["PJ"]),
            ("*Pascack Valley Line", ["PV"]),
            ("*Atlantic City Line", ["AC"]),
            ("*Princeton Branch", ["PR"]),
            ("*Gladstone Branch", ["GL"]),
        ]
        for scope, expected in known_scopes:
            result = parse_njt_line_scope(scope)
            assert (
                result == expected
            ), f"Failed for {scope}: got {result}, expected {expected}"

    def test_deduplicates_codes(self):
        """Duplicate codes are not repeated."""
        # If API ever returns "*ME Line *Morris & Essex Line", ME shouldn't appear twice
        result = parse_njt_line_scope("*ME Line *Morris & Essex Line")
        assert result.count("ME") == 1
        assert result.count("GL") == 1


class TestParseNjtStationScope:
    """Tests for parse_njt_station_scope() station name extraction."""

    def test_single_station(self):
        """Single station is extracted."""
        assert parse_njt_station_scope("*Newark Penn Station") == [
            "Newark Penn Station"
        ]

    def test_multiple_stations(self):
        """Comma-separated stations are extracted."""
        result = parse_njt_station_scope(
            "*Newark Penn Station,*Metropark,*Newark Airport"
        )
        assert result == ["Newark Penn Station", "Metropark", "Newark Airport"]

    def test_empty_scope(self):
        """Single space means no station scope."""
        assert parse_njt_station_scope(" ") == []

    def test_deduplicates(self):
        """Duplicate station names are not repeated."""
        result = parse_njt_station_scope("*Newark Penn Station,*Newark Penn Station")
        assert result == ["Newark Penn Station"]


class TestParseNjtMessage:
    """Tests for parse_njt_message() — full NJT message parsing."""

    def _make_rss_message(
        self,
        msg_id: str = "2072532",
        text: str = "NEC train #3837 is up to 15 min. late.",
        line_scope: str = "*Northeast Corridor Line",
        station_scope: str = " ",
        pub_utc: str = "3/17/2026 12:58:38 AM",
    ) -> dict:
        """Build an RSS-sourced NJT message dict (real-time delay alert)."""
        return {
            "MSG_TYPE": "banner",
            "MSG_TEXT": text,
            "MSG_PUBDATE": "3/16/2026 8:58:38 PM",
            "MSG_ID": msg_id,
            "MSG_AGENCY": "NJT",
            "MSG_SOURCE": "RSS_NJTRailAlerts",
            "MSG_STATION_SCOPE": station_scope,
            "MSG_LINE_SCOPE": line_scope,
            "MSG_PUBDATE_UTC": pub_utc,
        }

    def _make_system_message(
        self,
        text: str = "Service suspended between A and B.",
        station_scope: str = "*Newark Penn Station",
        line_scope: str = " ",
        pub_utc: str = "3/17/2026 1:00:00 AM",
    ) -> dict:
        """Build a non-RSS NJT message dict (system/manual advisory)."""
        return {
            "MSG_TYPE": "banner",
            "MSG_TEXT": text,
            "MSG_PUBDATE": "3/16/2026 9:00:00 PM",
            "MSG_ID": "",
            "MSG_AGENCY": "NJT",
            "MSG_SOURCE": "",
            "MSG_STATION_SCOPE": station_scope,
            "MSG_LINE_SCOPE": line_scope,
            "MSG_PUBDATE_UTC": pub_utc,
        }

    def test_rss_alert_parses_correctly(self):
        """RSS-sourced messages become 'alert' type with line codes."""
        msg = self._make_rss_message()
        result = parse_njt_message(msg)

        assert result is not None
        assert result.alert_id == "njt-rss-2072532"
        assert result.alert_type == "alert"
        assert result.affected_route_ids == ["NE"]
        assert "train #3837" in result.header_text
        assert result.description_text is None  # No station scope

    def test_system_message_parses_correctly(self):
        """Non-RSS messages become 'planned_work' with station description."""
        msg = self._make_system_message()
        result = parse_njt_message(msg)

        assert result is not None
        assert result.alert_id.startswith("njt-msg-")
        assert result.alert_type == "planned_work"
        assert result.affected_route_ids == []  # No line scope
        assert result.description_text == "Stations: Newark Penn Station"

    def test_multi_line_scope(self):
        """Messages with multiple lines map to all codes."""
        msg = self._make_rss_message(
            msg_id="999",
            line_scope="*Main Line *Bergen County Line",
        )
        result = parse_njt_message(msg)

        assert result is not None
        assert result.affected_route_ids == ["MA", "BE"]

    def test_empty_text_skipped(self):
        """Messages with empty text are skipped."""
        msg = self._make_rss_message(text="")
        assert parse_njt_message(msg) is None

    def test_whitespace_text_skipped(self):
        """Messages with whitespace-only text are skipped."""
        msg = self._make_rss_message(text="   ")
        assert parse_njt_message(msg) is None

    def test_pub_date_utc_parsed(self):
        """Publication date is parsed into active_periods epoch."""
        msg = self._make_rss_message(pub_utc="12/21/2023 4:13:00 PM")
        result = parse_njt_message(msg)

        assert result is not None
        assert len(result.active_periods) == 1
        assert result.active_periods[0]["start"] == 1703175180
        assert result.active_periods[0]["end"] is None

    def test_invalid_date_handled(self):
        """Invalid date format doesn't crash, just skips active period."""
        msg = self._make_rss_message(pub_utc="not-a-date")
        result = parse_njt_message(msg)

        assert result is not None
        assert result.active_periods == []

    def test_missing_msg_id_uses_hash(self):
        """Messages without MSG_ID get a hash-based alert_id."""
        msg = self._make_system_message(text="Test advisory message")
        result = parse_njt_message(msg)

        assert result is not None
        assert result.alert_id.startswith("njt-msg-")
        assert len(result.alert_id) == len("njt-msg-") + 12  # 12-char hex hash

    def test_same_text_same_hash(self):
        """Same message text produces the same alert_id (idempotent)."""
        msg1 = self._make_system_message(text="Identical message")
        msg2 = self._make_system_message(text="Identical message")
        r1 = parse_njt_message(msg1)
        r2 = parse_njt_message(msg2)

        assert r1 is not None and r2 is not None
        assert r1.alert_id == r2.alert_id

    def test_different_text_different_hash(self):
        """Different message text produces different alert_ids."""
        msg1 = self._make_system_message(text="Message A")
        msg2 = self._make_system_message(text="Message B")
        r1 = parse_njt_message(msg1)
        r2 = parse_njt_message(msg2)

        assert r1 is not None and r2 is not None
        assert r1.alert_id != r2.alert_id

    def test_station_scope_in_description(self):
        """Station scope names appear in description."""
        msg = self._make_system_message(station_scope="*Brick Church,*Chatham,*Summit")
        result = parse_njt_message(msg)

        assert result is not None
        assert result.description_text == "Stations: Brick Church, Chatham, Summit"

    def test_real_me_line_alert(self):
        """Parse a real ME Line alert from production API."""
        msg = {
            "MSG_TYPE": "banner",
            "MSG_TEXT": "Morris and Essex and Gladstone Branch rail service "
            "is suspended in both directions between South Orange "
            "and Millburn due to fire department activity near Maplewood.",
            "MSG_PUBDATE": "3/16/2026 8:58:38 PM",
            "MSG_ID": "2072532",
            "MSG_AGENCY": "NJT",
            "MSG_SOURCE": "RSS_NJTRailAlerts",
            "MSG_STATION_SCOPE": " ",
            "MSG_LINE_SCOPE": "*ME Line",
            "MSG_PUBDATE_UTC": "3/17/2026 12:58:38 AM",
        }
        result = parse_njt_message(msg)

        assert result is not None
        assert result.alert_id == "njt-rss-2072532"
        assert result.alert_type == "alert"
        assert result.affected_route_ids == ["ME", "GL"]
        assert "suspended" in result.header_text
        assert "Maplewood" in result.header_text


@pytest.mark.asyncio
class TestNjtUpsertServiceAlerts:
    """Tests for upserting NJT alerts into the database."""

    async def test_njt_alerts_upsert(self, db_session: AsyncSession):
        """NJT alerts are inserted with data_source='NJT'."""
        alerts = [
            ParsedAlert(
                alert_id="njt-rss-100",
                alert_type="alert",
                affected_route_ids=["NE"],
                header_text="NEC delay alert",
                description_text=None,
                active_periods=[{"start": 1710100000, "end": None}],
            ),
            ParsedAlert(
                alert_id="njt-msg-abc123",
                alert_type="planned_work",
                affected_route_ids=[],
                header_text="System advisory",
                description_text="Stations: Newark Penn Station",
                active_periods=[{"start": 1710100000, "end": None}],
            ),
        ]
        stats = await upsert_service_alerts(db_session, alerts, "NJT")
        await db_session.flush()

        assert stats["inserted"] == 2

        result = await db_session.execute(
            select(ServiceAlert).where(ServiceAlert.data_source == "NJT")
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert all(r.is_active for r in rows)

        # Verify alert types
        by_id = {r.alert_id: r for r in rows}
        assert by_id["njt-rss-100"].alert_type == "alert"
        assert by_id["njt-msg-abc123"].alert_type == "planned_work"

    async def test_njt_isolation_from_mta(self, db_session: AsyncSession):
        """NJT alerts don't interfere with MTA alerts."""
        njt_alert = ParsedAlert(
            alert_id="njt-rss-200",
            alert_type="alert",
            affected_route_ids=["NC"],
            header_text="NJCL delay",
            description_text=None,
            active_periods=[],
        )
        mta_alert = ParsedAlert(
            alert_id="lmm:alert:300",
            alert_type="alert",
            affected_route_ids=["G"],
            header_text="G train delays",
            description_text=None,
            active_periods=[],
        )

        await upsert_service_alerts(db_session, [njt_alert], "NJT")
        await upsert_service_alerts(db_session, [mta_alert], "SUBWAY")
        await db_session.flush()

        # Deactivate all NJT alerts
        stats = await upsert_service_alerts(db_session, [], "NJT")
        await db_session.flush()

        assert stats["deactivated"] == 1

        # SUBWAY alert untouched
        result = await db_session.execute(
            select(ServiceAlert).where(
                ServiceAlert.data_source == "SUBWAY",
                ServiceAlert.is_active.is_(True),
            )
        )
        assert result.scalar_one().alert_id == "lmm:alert:300"

    async def test_reactivates_previously_deactivated_alert(
        self, db_session: AsyncSession
    ):
        """An alert that was deactivated then reappears is reactivated, not duplicated.

        This is a regression test for a UniqueViolationError that occurred when
        the upsert only loaded active alerts — a deactivated alert reappearing
        in the feed would attempt an INSERT and hit the unique constraint.
        """
        alert = ParsedAlert(
            alert_id="lmm:planned_work:reactivate-1",
            alert_type="planned_work",
            affected_route_ids=["G"],
            header_text="G: Weekend service change",
            description_text="Details",
            active_periods=[{"start": 1710100000, "end": 1710200000}],
        )

        # Insert the alert
        stats = await upsert_service_alerts(db_session, [alert], "SUBWAY")
        await db_session.flush()
        assert stats["inserted"] == 1

        # Deactivate it (empty feed)
        stats = await upsert_service_alerts(db_session, [], "SUBWAY")
        await db_session.flush()
        assert stats["deactivated"] == 1

        # Verify it's inactive
        result = await db_session.execute(
            select(ServiceAlert).where(
                ServiceAlert.alert_id == "lmm:planned_work:reactivate-1"
            )
        )
        row = result.scalar_one()
        assert row.is_active is False

        # Reappear in the feed — should update (reactivate), NOT insert
        stats = await upsert_service_alerts(db_session, [alert], "SUBWAY")
        await db_session.flush()
        assert stats["inserted"] == 0, "Should reactivate, not insert a duplicate"
        assert stats["updated"] == 1

        # Verify it's active again and there's only one row
        result = await db_session.execute(
            select(ServiceAlert).where(
                ServiceAlert.alert_id == "lmm:planned_work:reactivate-1"
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)} (duplicate inserted)"
        assert rows[0].is_active is True
