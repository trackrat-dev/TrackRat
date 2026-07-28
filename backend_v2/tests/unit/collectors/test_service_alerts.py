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
    _SEPTA_ROUTE_TO_LINE_CODE,
    _SEPTA_STATION_LINES,
    ParsedAlert,
    _remap_septa_alert,
    _septa_lines_serving_stations,
    classify_alert_type,
    deactivate_disabled_source_alerts,
    extract_english_text,
    fetch_and_parse_njt_alerts,
    parse_alert_entity,
    parse_njt_line_scope,
    parse_njt_message,
    parse_njt_station_scope,
    upsert_service_alerts,
)
from trackrat.config.stations import (
    SEPTA_METRO_ROUTE_STATIONS,
    SEPTA_METRO_STATION_NAMES,
    SEPTA_RR_STATION_NAMES,
    map_septa_metro_gtfs_stop,
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
        stop_ids: list[str] | None = None,
    ) -> MagicMock:
        """Build a mock GTFS-RT entity for testing."""
        entity = MagicMock()
        entity.id = entity_id
        entity.HasField.return_value = True

        alert = MagicMock()
        entity.alert = alert

        # Informed entities. A real EntitySelector defaults every unset string
        # field to "", so stop_id must be set explicitly here — an unset
        # MagicMock attribute is a truthy MagicMock, which would look like a
        # stop scope the entity does not have.
        if route_ids is None:
            route_ids = ["G"]
        informed_entities = []
        for rid in route_ids:
            ie = MagicMock()
            ie.route_id = rid
            ie.stop_id = ""
            informed_entities.append(ie)
        for sid in stop_ids or []:
            ie = MagicMock()
            ie.route_id = ""
            ie.stop_id = sid
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

    def test_stop_ids_are_retained(self):
        """Stop entities survive the parse (issue #1630).

        A stop_id is the only scope some alerts carry; discarding it left them
        indistinguishable from a genuinely system-wide alert.
        """
        entity = self._make_entity(route_ids=[], stop_ids=["1272", "140"])
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.affected_route_ids == []
        assert result.affected_stop_ids == ["1272", "140"]

    def test_deduplicates_stop_ids(self):
        """Repeated stop entities collapse, as route IDs already do."""
        entity = self._make_entity(route_ids=[], stop_ids=["140", "140", "1272"])
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.affected_stop_ids == ["140", "1272"]

    def test_route_only_alert_has_no_stop_ids(self):
        """A route-scoped entity must not acquire a phantom stop scope."""
        entity = self._make_entity(route_ids=["G"])
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.affected_stop_ids == []

    def test_routes_and_stops_are_both_captured(self):
        """An alert scoped by both keeps both, in feed order."""
        entity = self._make_entity(route_ids=["G", "4"], stop_ids=["1272"])
        result = parse_alert_entity(entity)

        assert result is not None
        assert result.affected_route_ids == ["G", "4"]
        assert result.affected_stop_ids == ["1272"]


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

        # Build a protobuf feed with duplicate entity IDs
        from google.transit import gtfs_realtime_pb2

        from trackrat.collectors.service_alerts import fetch_and_parse_alerts

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

        with patch(
            "trackrat.collectors.service_alerts.httpx.AsyncClient",
            return_value=mock_client,
        ):
            alerts = await fetch_and_parse_alerts("https://fake-feed-url", "SUBWAY")

        # Should have 2 alerts (deduped), not 3
        assert len(alerts) == 2, (
            f"Expected 2 alerts after dedup, got {len(alerts)}. "
            f"IDs: {[a.alert_id for a in alerts]}"
        )

        alert_ids = [a.alert_id for a in alerts]
        assert "235N#EL301" in alert_ids, "Elevator alert should be present"
        assert (
            "lmm:planned_work:99999" in alert_ids
        ), "Planned work alert should be present"

        # Last occurrence should win
        elevator_alert = next(a for a in alerts if a.alert_id == "235N#EL301")
        assert (
            elevator_alert.header_text == "Elevator out of service (second)"
        ), "Last occurrence of duplicate entity ID should win"


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
        assert (
            "updated" in deduped.header_text
        ), "Last occurrence of duplicate MSG_ID should win"

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

        assert (
            len(alerts) == 1
        ), f"Identical NJT messages should deduplicate to 1, got {len(alerts)}"


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


class TestRemapSeptaAlert:
    """Tests for _remap_septa_alert() SEPTA route/type adaptation.

    SEPTA's GTFS-RT alert feeds carry raw GTFS route_ids (e.g. "AIR", "B1")
    rather than our line_codes ("SEPTA-AIR"), and the shared Metro feed
    ("septa-pa-us") mixes in ~130 bus routes we don't track. This function
    maps route_ids to our codes and drops bus-only alerts.
    """

    def _alert(
        self,
        route_ids: list[str],
        header: str = "Service adjustment",
        alert_id: str = "septa-1",
        stop_ids: list[str] | None = None,
    ) -> ParsedAlert:
        return ParsedAlert(
            alert_id=alert_id,
            alert_type="unknown",  # SEPTA entity IDs are opaque; remap reclassifies
            affected_route_ids=route_ids,
            affected_stop_ids=stop_ids or [],
            header_text=header,
            description_text=None,
            active_periods=[],
        )

    def test_rr_route_id_maps_to_line_code(self):
        """A Regional Rail route_id becomes our SEPTA-<code> line code."""
        result = _remap_septa_alert(self._alert(["AIR"]), "SEPTA_RR")
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-AIR"]
        assert result.alert_type == "alert"

    def test_metro_route_id_maps_to_line_code(self):
        """A Metro route_id (Broad St) becomes our SEPTA-<code> line code."""
        result = _remap_septa_alert(self._alert(["B1"]), "SEPTA_METRO")
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-B1"]

    def test_bus_only_alert_dropped(self):
        """An alert whose only routes are untracked (bus) routes is dropped."""
        # "17", "44" are SEPTA bus routes, not in SEPTA_METRO_ROUTES.
        assert _remap_septa_alert(self._alert(["17", "44"]), "SEPTA_METRO") is None

    def test_mixed_routes_keeps_only_tracked(self):
        """Bus routes are stripped but tracked rail routes are retained."""
        result = _remap_septa_alert(
            self._alert(["17", "B1", "44", "G1"]), "SEPTA_METRO"
        )
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-B1", "SEPTA-G1"]

    def test_system_wide_alert_kept(self):
        """A route-less (system-wide) alert is kept with no affected routes."""
        result = _remap_septa_alert(self._alert([]), "SEPTA_RR")
        assert result is not None
        assert result.affected_route_ids == []

    def test_elevator_header_classifies_as_elevator(self):
        """Headers mentioning an elevator classify as 'elevator'."""
        result = _remap_septa_alert(
            self._alert(["B1"], header="Elevator out of service at City Hall"),
            "SEPTA_METRO",
        )
        assert result is not None
        assert result.alert_type == "elevator"

    def test_escalator_header_classifies_as_elevator(self):
        """Headers mentioning an escalator also classify as 'elevator'."""
        result = _remap_septa_alert(
            self._alert(["AIR"], header="Escalator outage at Jefferson Station"),
            "SEPTA_RR",
        )
        assert result is not None
        assert result.alert_type == "elevator"

    def test_deduplicates_mapped_codes(self):
        """Repeated raw route_ids don't produce duplicate line codes."""
        result = _remap_septa_alert(self._alert(["AIR", "AIR"]), "SEPTA_RR")
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-AIR"]

    def test_preserves_other_fields(self):
        """Non-route/type fields (id, header, periods) pass through unchanged."""
        alert = self._alert(["B1"], header="Weekend detour", alert_id="septa-xyz")
        result = _remap_septa_alert(alert, "SEPTA_METRO")
        assert result is not None
        assert result.alert_id == "septa-xyz"
        assert result.header_text == "Weekend detour"


class TestSeptaStopScopedAlerts:
    """Issue #1630: a stop-only bus alert must not become a Metro-wide alert.

    The ``septa-pa-us`` feed mixes bus and Metro alerts. A route-tagged bus alert
    is dropped because its route_id isn't one we track, but a bus disruption
    scoped purely by ``stop_id`` names no route at all — so it used to be stored
    with an empty ``affected_route_ids``, which every consumer reads as
    system-wide: the alerts API returns it for any SEPTA_METRO query, the web
    banner shows it when ``affected_route_ids.length === 0``, and system-wide
    subscribers are pushed it.

    Real feed IDs are used throughout: stop "1272" is Wyoming on the Broad Street
    Line, "20965" is Fern Rock TC, "90401" is a Regional Rail Airport Line stop,
    and "283" is the 13th St trolley station. Bus stop IDs are not in either
    station map.
    """

    def _alert(
        self,
        route_ids: list[str],
        stop_ids: list[str] | None = None,
        header: str = "Detour in effect",
        alert_id: str = "septa-stop-1",
    ) -> ParsedAlert:
        return ParsedAlert(
            alert_id=alert_id,
            alert_type="unknown",
            affected_route_ids=route_ids,
            affected_stop_ids=stop_ids or [],
            header_text=header,
            description_text=None,
            active_periods=[],
        )

    def test_bus_stop_only_alert_is_dropped(self):
        """The #1630 bug: stops we don't serve, no routes -> not our alert."""
        alert = self._alert([], stop_ids=["31415", "999999"])
        assert _remap_septa_alert(alert, "SEPTA_METRO") is None

    def test_bus_stop_only_alert_was_previously_system_wide(self):
        """Pin why this matters: the same alert has no route scope to fall back on.

        Retaining it would store affected_route_ids=[], the exact value every
        consumer treats as "applies to the whole system".
        """
        alert = self._alert([], stop_ids=["31415"])
        assert alert.affected_route_ids == []
        assert _remap_septa_alert(alert, "SEPTA_METRO") is None

    def test_metro_stop_only_alert_is_kept_and_scoped_to_its_line(self):
        """A served stop scopes the alert to the line(s) serving it."""
        result = _remap_septa_alert(self._alert([], stop_ids=["1272"]), "SEPTA_METRO")
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-B1"], (
            "Wyoming is a Broad Street Line station, so the alert must be "
            "scoped to B1 rather than left system-wide"
        )

    def test_stop_serving_several_lines_scopes_to_all_of_them(self):
        """13th St is shared by every trolley route; none may be dropped."""
        result = _remap_septa_alert(self._alert([], stop_ids=["283"]), "SEPTA_METRO")
        assert result is not None
        assert result.affected_route_ids == [
            "SEPTA-T1",
            "SEPTA-T2",
            "SEPTA-T3",
            "SEPTA-T4",
            "SEPTA-T5",
        ]

    def test_mixed_served_and_unserved_stops_scope_to_the_served_one(self):
        """A bus stop alongside a Metro stop must not widen or void the scope."""
        result = _remap_septa_alert(
            self._alert([], stop_ids=["31415", "1272", "999999"]), "SEPTA_METRO"
        )
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-B1"]

    def test_named_route_wins_over_stop_entities(self):
        """Stops never widen an already route-scoped alert."""
        result = _remap_septa_alert(
            self._alert(["B1"], stop_ids=["283"]), "SEPTA_METRO"
        )
        assert result is not None
        assert result.affected_route_ids == [
            "SEPTA-B1"
        ], "the trolley stop must not add T1-T5 to a Broad Street alert"

    def test_bus_route_with_metro_stop_is_still_dropped(self):
        """An alert that names only bus routes stays dropped, stops or not.

        Conservative by design: a bus route is positive evidence the alert is
        about the bus network, so a nearby shared stop must not resurrect it.
        """
        alert = self._alert(["17"], stop_ids=["1272"])
        assert _remap_septa_alert(alert, "SEPTA_METRO") is None

    def test_alert_with_neither_routes_nor_stops_stays_system_wide(self):
        """A genuinely unscoped agency advisory is still kept and unscoped."""
        result = _remap_septa_alert(self._alert([], stop_ids=[]), "SEPTA_RR")
        assert result is not None
        assert result.affected_route_ids == []

    def test_regional_rail_stop_only_alert_is_scoped(self):
        """The same rule applies to the Regional Rail feed."""
        result = _remap_septa_alert(self._alert([], stop_ids=["90401"]), "SEPTA_RR")
        assert result is not None
        assert result.affected_route_ids == ["SEPTA-AIR"]

    def test_unserved_stop_on_the_rail_feed_is_dropped(self):
        """A stop ID absent from the RR station map is not a rail stop."""
        assert (
            _remap_septa_alert(self._alert([], stop_ids=["31415"]), "SEPTA_RR") is None
        )

    def test_unresolvable_served_stop_is_kept_unscoped(self):
        """A served stop whose line can't be resolved is kept, not dropped.

        One-way trolley curb stops can be absent from every direction-0 route
        sequence and have no same-named twin. Over-showing a genuine Metro alert
        beats hiding it — unlike a bus alert, it is at least ours.
        """
        assert map_septa_metro_gtfs_stop("21098") is not None, "fixture must be served"
        result = _remap_septa_alert(self._alert([], stop_ids=["21098"]), "SEPTA_METRO")
        assert result is not None
        assert result.affected_route_ids == []

    def test_stop_scoping_preserves_type_classification(self):
        """Header-based elevator classification still runs on stop-only alerts."""
        result = _remap_septa_alert(
            self._alert([], stop_ids=["20965"], header="Elevator out at Fern Rock"),
            "SEPTA_METRO",
        )
        assert result is not None
        assert result.alert_type == "elevator"
        assert result.affected_route_ids  # and it is still scoped


class TestSeptaStationLineIndex:
    """The station -> line index that scopes stop-only alerts.

    ``*_ROUTE_STATIONS`` holds only the direction_id=0 sequence and each trolley
    curb stop is its own station, so a naive membership test leaves 271 of the
    633 SEPTA Metro stations on no line. The index closes that by letting a
    station borrow its same-named twin's lines — the two are one physical stop.
    """

    def test_direct_route_membership_resolves(self):
        assert _septa_lines_serving_stations({"SEPM1272"}, "SEPTA_METRO") == [
            "SEPTA-B1"
        ]

    def test_unknown_station_resolves_to_nothing(self):
        assert _septa_lines_serving_stations({"SEPM_NOPE"}, "SEPTA_METRO") == []

    def test_lines_are_unioned_across_stations(self):
        lines = _septa_lines_serving_stations({"SEPM1272", "SEPM283"}, "SEPTA_METRO")
        assert "SEPTA-B1" in lines
        assert "SEPTA-T1" in lines

    def test_line_order_follows_the_route_table(self):
        """Deterministic ordering, so a stable alert doesn't churn on upsert."""
        lines = _septa_lines_serving_stations({"SEPM1272", "SEPM283"}, "SEPTA_METRO")
        assert lines == sorted(
            lines,
            key=lambda c: list(_SEPTA_ROUTE_TO_LINE_CODE["SEPTA_METRO"].values()).index(
                c
            ),
        )

    def test_twin_borrowing_covers_stations_absent_from_route_lists(self):
        """The reason the index exists, measured rather than asserted abstractly."""
        index = _SEPTA_STATION_LINES["SEPTA_METRO"]
        direct = {
            station
            for stations in SEPTA_METRO_ROUTE_STATIONS.values()
            for station in stations
        }
        borrowed = set(index) - direct
        assert borrowed, "twin borrowing must resolve stations no route lists"
        for station in borrowed:
            assert index[station], "a borrowed station must carry real lines"

    def test_every_indexed_station_is_a_real_station(self):
        for source, names in (
            ("SEPTA_METRO", SEPTA_METRO_STATION_NAMES),
            ("SEPTA_RR", SEPTA_RR_STATION_NAMES),
        ):
            unknown = set(_SEPTA_STATION_LINES[source]) - set(names)
            assert not unknown, f"{source} index has phantom stations: {unknown}"

    def test_every_indexed_line_is_a_tracked_line(self):
        for source in ("SEPTA_METRO", "SEPTA_RR"):
            valid = set(_SEPTA_ROUTE_TO_LINE_CODE[source].values())
            for station, lines in _SEPTA_STATION_LINES[source].items():
                assert set(lines) <= valid, f"{source}/{station} has untracked lines"

    def test_regional_rail_stations_all_resolve(self):
        """Every RR station sits on a line; a gap there would be a config bug."""
        missing = set(SEPTA_RR_STATION_NAMES) - set(_SEPTA_STATION_LINES["SEPTA_RR"])
        assert not missing, f"unresolved Regional Rail stations: {sorted(missing)}"


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


@pytest.mark.asyncio
class TestDeactivateDisabledSourceAlerts:
    """Tests for deactivate_disabled_source_alerts().

    When a source is turned off via TRACKRAT_DISABLED_DATA_SOURCES its feed is
    skipped, so upsert_service_alerts never deactivates its still-active rows.
    This sweep does — otherwise /alerts/service and the route-alert push
    evaluator (both filter only on is_active) keep surfacing stale alerts for a
    source that is supposed to be off. Regression guard for PR #1595.
    """

    def _alert(self, alert_id: str) -> ParsedAlert:
        return ParsedAlert(
            alert_id=alert_id,
            alert_type="alert",
            affected_route_ids=[],
            header_text="Service adjustment",
            description_text=None,
            active_periods=[],
        )

    async def test_deactivates_only_disabled_sources(self, db_session: AsyncSession):
        """Active alerts for disabled sources go inactive; enabled sources untouched."""
        # SEPTA_RR + SEPTA_METRO (to be disabled) and SUBWAY (stays enabled).
        await upsert_service_alerts(db_session, [self._alert("septa-rr-1")], "SEPTA_RR")
        await upsert_service_alerts(
            db_session, [self._alert("septa-metro-1")], "SEPTA_METRO"
        )
        await upsert_service_alerts(db_session, [self._alert("subway-1")], "SUBWAY")
        await db_session.flush()

        count = await deactivate_disabled_source_alerts(
            db_session, {"SEPTA_RR", "SEPTA_METRO"}
        )
        # Bulk UPDATE bypasses the identity map; force ORM reload before asserting.
        db_session.expire_all()

        assert count == 2, f"Expected 2 SEPTA alerts deactivated, got {count}"

        septa_rows = (
            (
                await db_session.execute(
                    select(ServiceAlert).where(
                        ServiceAlert.data_source.in_(["SEPTA_RR", "SEPTA_METRO"])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(septa_rows) == 2
        assert all(not r.is_active for r in septa_rows), (
            "Disabled SEPTA alerts must be inactive: "
            f"{[(r.data_source, r.is_active) for r in septa_rows]}"
        )

        subway_row = (
            await db_session.execute(
                select(ServiceAlert).where(ServiceAlert.data_source == "SUBWAY")
            )
        ).scalar_one()
        assert subway_row.is_active is True, "Enabled SUBWAY alert must stay active"

    async def test_empty_disabled_set_is_noop(self, db_session: AsyncSession):
        """With no disabled sources, nothing is deactivated."""
        await upsert_service_alerts(db_session, [self._alert("subway-2")], "SUBWAY")
        await db_session.flush()

        count = await deactivate_disabled_source_alerts(db_session, set())
        db_session.expire_all()

        assert count == 0
        row = (
            await db_session.execute(
                select(ServiceAlert).where(ServiceAlert.alert_id == "subway-2")
            )
        ).scalar_one()
        assert row.is_active is True

    async def test_idempotent_when_already_inactive(self, db_session: AsyncSession):
        """Re-running after everything is inactive deactivates nothing (count 0)."""
        await upsert_service_alerts(db_session, [self._alert("septa-rr-2")], "SEPTA_RR")
        await db_session.flush()

        first = await deactivate_disabled_source_alerts(db_session, {"SEPTA_RR"})
        db_session.expire_all()
        assert first == 1

        second = await deactivate_disabled_source_alerts(db_session, {"SEPTA_RR"})
        assert second == 0, "Already-inactive rows must not be re-counted"
