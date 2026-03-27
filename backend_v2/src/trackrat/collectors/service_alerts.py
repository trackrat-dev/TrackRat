"""
Service alerts collector.

Fetches service alerts from multiple sources:
- MTA (SUBWAY, LIRR, MNR): GTFS-RT service alert feeds
- NJT: NJ Transit getStationMSG API
- WMATA: WMATA Rail Incidents API

Upserts into the service_alerts table. Supports alert types:
- planned_work: scheduled track work, reroutes, suspensions
- alert: real-time delays, incidents
- elevator: elevator/escalator outages
"""

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from google.transit import gtfs_realtime_pb2
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitAPIError, NJTransitClient
from trackrat.config.stations import (
    LIRR_ALERTS_FEED_URL,
    MNR_ALERTS_FEED_URL,
    SUBWAY_ALERTS_FEED_URL,
)
from trackrat.db.engine import get_session
from trackrat.models.database import ServiceAlert

logger = logging.getLogger(__name__)

# Feed configuration: data_source -> alert feed URL
MTA_ALERT_FEEDS: dict[str, str] = {
    "SUBWAY": SUBWAY_ALERTS_FEED_URL,
    "LIRR": LIRR_ALERTS_FEED_URL,
    "MNR": MNR_ALERTS_FEED_URL,
}

# NJT MSG_LINE_SCOPE name -> internal line code(s)
# The API returns names like "*Northeast Corridor Line" in MSG_LINE_SCOPE.
# Multiple lines are space-delimited with * prefix: "*Main Line *Bergen County Line"
NJT_LINE_SCOPE_TO_CODES: dict[str, list[str]] = {
    "Northeast Corridor Line": ["NE"],
    "Northeast Corrior Line": ["NE"],  # Known typo in NJT API
    "Northeast Corridor": ["NE"],
    "North Jersey Coast Line": ["NC"],
    "ME Line": ["ME", "GL"],  # Morris & Essex covers Morristown + Gladstone
    "Morris & Essex Line": ["ME", "GL"],
    "Morris and Essex Line": ["ME", "GL"],
    "Morristown Line": ["ME"],
    "Gladstone Branch": ["GL"],
    "Raritan Valley Line": ["RV"],
    "Montclair-Boonton Line": ["MO"],
    "Main Line": ["MA"],
    "Bergen County Line": ["BE"],
    "Port Jervis Line": ["PJ"],
    "Pascack Valley Line": ["PV"],
    "Atlantic City Line": ["AC"],
    "Atlantic City Rail Line": ["AC"],
    "Princeton Branch": ["PR"],
}


class ParsedAlert(BaseModel):
    """A single parsed service alert from a GTFS-RT feed."""

    alert_id: str
    alert_type: str  # planned_work, alert, elevator
    affected_route_ids: list[str]
    header_text: str
    description_text: str | None
    active_periods: list[dict[str, int | None]]  # [{"start": epoch, "end": epoch}]


def classify_alert_type(entity_id: str) -> str:
    """Classify MTA alert type from entity ID prefix.

    MTA uses entity ID conventions:
    - "lmm:planned_work:NNNNN" for planned/scheduled service changes
    - "lmm:alert:NNNNNN" for real-time delays/incidents
    - "STOPID#ELXXX" for elevator/escalator outages
    """
    if entity_id.startswith("lmm:planned_work:"):
        return "planned_work"
    elif entity_id.startswith("lmm:alert:"):
        return "alert"
    elif "#EL" in entity_id:
        return "elevator"
    return "unknown"


def extract_english_text(translated_string: Any) -> str | None:
    """Extract English plain text from a GTFS-RT TranslatedString."""
    if not translated_string or not translated_string.translation:
        return None
    for t in translated_string.translation:
        if t.language == "en":
            return str(t.text)
    # Fallback: first translation
    if translated_string.translation:
        return str(translated_string.translation[0].text)
    return None


def parse_alert_entity(entity: Any) -> ParsedAlert | None:
    """Parse a single GTFS-RT alert entity into our internal model.

    Returns None if the entity is not a valid alert or has no useful data.
    """
    if not entity.HasField("alert"):
        return None

    alert = entity.alert
    entity_id = entity.id
    alert_type = classify_alert_type(entity_id)

    # Extract affected route_ids from informed_entity list
    route_ids: list[str] = []
    for ie in alert.informed_entity:
        if ie.route_id and ie.route_id not in route_ids:
            route_ids.append(ie.route_id)

    # Extract text
    header = extract_english_text(alert.header_text)
    if not header:
        return None  # Skip alerts with no header

    description = extract_english_text(alert.description_text)

    # Extract active periods
    active_periods: list[dict[str, int | None]] = []
    for period in alert.active_period:
        start = period.start if period.start else None
        end = period.end if period.end else None
        active_periods.append({"start": start, "end": end})

    return ParsedAlert(
        alert_id=entity_id,
        alert_type=alert_type,
        affected_route_ids=route_ids,
        header_text=header,
        description_text=description,
        active_periods=active_periods,
    )


async def fetch_and_parse_alerts(
    feed_url: str, data_source: str, timeout: float = 30.0
) -> list[ParsedAlert]:
    """Fetch a GTFS-RT service alerts feed and parse all alert entities.

    Args:
        feed_url: URL of the GTFS-RT alerts feed
        data_source: Data source identifier (SUBWAY, LIRR, MNR)
        timeout: HTTP request timeout in seconds

    Returns:
        List of parsed alerts
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={
            "User-Agent": "TrackRat/2.0 (MTA Service Alerts Collector)",
            "Accept": "application/x-protobuf",
        },
    ) as client:
        response = await client.get(feed_url)
        response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    # Deduplicate by alert_id (MTA feeds can contain duplicate entity IDs,
    # e.g. elevator alerts). Last occurrence wins.
    alerts_by_id: dict[str, ParsedAlert] = {}
    for entity in feed.entity:
        parsed = parse_alert_entity(entity)
        if parsed:
            alerts_by_id[parsed.alert_id] = parsed

    alerts = list(alerts_by_id.values())

    logger.info(
        "Parsed %d service alerts from %s feed (%d entities total)",
        len(alerts),
        data_source,
        len(feed.entity),
    )
    return alerts


def parse_njt_line_scope(line_scope: str) -> list[str]:
    """Parse NJT MSG_LINE_SCOPE into internal line codes.

    The API uses '*'-prefixed names, space-delimited for multiple lines:
    - Single: "*North Jersey Coast Line"
    - Multiple: "*Main Line *Bergen County Line"
    - None: " " (single space)

    Returns:
        List of internal line codes (e.g., ["NE", "NC"]).
    """
    if not line_scope or line_scope.strip() == "":
        return []

    # Split on '*' to get individual line names
    codes: list[str] = []
    for part in line_scope.split("*"):
        name = part.strip()
        if not name:
            continue
        mapped = NJT_LINE_SCOPE_TO_CODES.get(name)
        if mapped:
            for code in mapped:
                if code not in codes:
                    codes.append(code)
        else:
            logger.warning("NJT unknown line scope: %s", name)
    return codes


def parse_njt_station_scope(station_scope: str) -> list[str]:
    """Parse NJT MSG_STATION_SCOPE into station display names.

    The API returns comma-separated station names with '*' prefixes,
    e.g. "*Newark Penn Station,*Metropark". A single space " " means
    no station scope.

    Returns:
        List of station display names (e.g., ["Newark Penn Station", "Metropark"]).
    """
    if not station_scope or station_scope.strip() == "":
        return []

    names: list[str] = []
    for part in station_scope.split(","):
        name = part.strip().lstrip("*").strip()
        if name and name not in names:
            names.append(name)
    return names


def parse_njt_message(msg: dict[str, Any]) -> ParsedAlert | None:
    """Parse a single NJT getStationMSG response into a ParsedAlert.

    Args:
        msg: A single message dict from the getStationMSG API.

    Returns:
        ParsedAlert or None if the message has no useful text.
    """
    text = (msg.get("MSG_TEXT") or "").strip()
    if not text:
        return None

    # Build a stable alert_id from MSG_ID if present, otherwise hash the text
    msg_id = (msg.get("MSG_ID") or "").strip()
    if msg_id:
        alert_id = f"njt-rss-{msg_id}"
    else:
        # For non-RSS messages without MSG_ID, use a hash of the text
        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        alert_id = f"njt-msg-{text_hash}"

    # Classify: RSS source = real-time delay alerts, others = general advisories
    source = (msg.get("MSG_SOURCE") or "").strip()
    if source == "RSS_NJTRailAlerts":
        alert_type = "alert"
    else:
        alert_type = "planned_work"

    # Extract affected route IDs from line scope
    line_scope = msg.get("MSG_LINE_SCOPE") or ""
    affected_route_ids = parse_njt_line_scope(line_scope)

    # If no line scope, try to include station names in description for context
    station_scope = msg.get("MSG_STATION_SCOPE") or ""
    station_names = parse_njt_station_scope(station_scope)

    # Build description with station context if available
    description = None
    if station_names:
        description = f"Stations: {', '.join(station_names)}"

    # Parse publication time as active period
    active_periods: list[dict[str, int | None]] = []
    pub_utc = (msg.get("MSG_PUBDATE_UTC") or "").strip()
    if pub_utc:
        try:
            # Format: "12/21/2023 4:13:00 PM"
            dt = datetime.strptime(pub_utc, "%m/%d/%Y %I:%M:%S %p")
            dt = dt.replace(tzinfo=UTC)
            epoch = int(dt.timestamp())
            active_periods.append({"start": epoch, "end": None})
        except ValueError:
            logger.debug("NJT msg unparseable date: %s", pub_utc)

    return ParsedAlert(
        alert_id=alert_id,
        alert_type=alert_type,
        affected_route_ids=affected_route_ids,
        header_text=text,
        description_text=description,
        active_periods=active_periods,
    )


async def fetch_and_parse_njt_alerts() -> list[ParsedAlert]:
    """Fetch NJT service messages and parse into ParsedAlert objects.

    Calls getStationMSG with no filters to get all active messages.
    """
    async with NJTransitClient() as client:
        messages = await client.get_station_messages()

    # Deduplicate by alert_id — NJT messages without MSG_ID use a text hash,
    # so identical messages or duplicate MSG_IDs would collide. Last wins.
    alerts_by_id: dict[str, ParsedAlert] = {}
    for msg in messages:
        parsed = parse_njt_message(msg)
        if parsed:
            alerts_by_id[parsed.alert_id] = parsed

    alerts = list(alerts_by_id.values())

    logger.info(
        "Parsed %d NJT service alerts from %d messages",
        len(alerts),
        len(messages),
    )
    return alerts


async def _fetch_and_parse_wmata_alerts() -> list[ParsedAlert] | None:
    """Fetch WMATA rail incidents and parse into ParsedAlert objects.

    Returns None if no API key is configured (WMATA is optional).
    """
    from trackrat.collectors.wmata.client import WMATAClient
    from trackrat.settings import get_settings

    settings = get_settings()
    if not settings.wmata_api_key:
        return None

    async with WMATAClient(api_key=settings.wmata_api_key) as client:
        incidents = await client.get_incidents()

    alerts = []
    for incident in incidents:
        # Map WMATA IncidentType to our alert_type
        # "Delay" and "Alert" are the common types; treat both as real-time alerts
        alert_type = "alert"

        alerts.append(
            ParsedAlert(
                alert_id=f"WMATA-{incident.incident_id}",
                alert_type=alert_type,
                affected_route_ids=incident.lines_affected,
                header_text=incident.description[:200] if incident.description else "",
                description_text=incident.description,
                active_periods=[
                    {
                        "start": (
                            int(incident.date_updated.timestamp())
                            if incident.date_updated
                            else None
                        ),
                        "end": None,
                    }
                ],
            )
        )

    logger.info(
        "Parsed %d WMATA service alerts from %d incidents",
        len(alerts),
        len(incidents),
    )
    return alerts


async def upsert_service_alerts(
    session: AsyncSession, alerts: list[ParsedAlert], data_source: str
) -> dict[str, int]:
    """Upsert parsed alerts into the service_alerts table.

    Inserts new alerts, updates changed alerts, and marks missing alerts
    as inactive. Uses alert_id + data_source as the unique key.

    Returns:
        Stats dict with counts of inserted, updated, deactivated alerts.
    """
    stats = {"inserted": 0, "updated": 0, "deactivated": 0}

    # Load all existing alerts for this data source (including inactive,
    # so we can reactivate them instead of inserting duplicates)
    result = await session.execute(
        select(ServiceAlert).where(
            ServiceAlert.data_source == data_source,
        )
    )
    existing_by_id: dict[str, ServiceAlert] = {
        sa.alert_id: sa for sa in result.scalars().all() if sa.alert_id is not None
    }

    seen_ids: set[str] = set()

    for alert in alerts:
        seen_ids.add(alert.alert_id)
        existing = existing_by_id.get(alert.alert_id)

        if existing:
            # Update if content changed
            changed = False
            if existing.header_text != alert.header_text:
                existing.header_text = alert.header_text
                changed = True
            if existing.description_text != alert.description_text:
                existing.description_text = alert.description_text
                changed = True
            if existing.active_periods != alert.active_periods:
                existing.active_periods = alert.active_periods
                changed = True
            if existing.affected_route_ids != alert.affected_route_ids:
                existing.affected_route_ids = alert.affected_route_ids
                changed = True
            if existing.alert_type != alert.alert_type:
                existing.alert_type = alert.alert_type
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if changed:
                stats["updated"] += 1
        else:
            # Insert new alert
            new_alert = ServiceAlert(
                alert_id=alert.alert_id,
                data_source=data_source,
                alert_type=alert.alert_type,
                affected_route_ids=alert.affected_route_ids,
                header_text=alert.header_text,
                description_text=alert.description_text,
                active_periods=alert.active_periods,
            )
            session.add(new_alert)
            stats["inserted"] += 1

    # Deactivate alerts no longer in the feed
    for alert_id, existing in existing_by_id.items():
        if alert_id not in seen_ids and existing.is_active:
            existing.is_active = False
            stats["deactivated"] += 1

    return stats


async def collect_service_alerts() -> dict[str, Any]:
    """Collect service alerts from all feeds (MTA + NJT).

    This is the main entry point called by the scheduler.
    Fetches all feeds, upserts alerts, and returns stats.
    """
    all_stats: dict[str, Any] = {}

    async with get_session() as session:
        # MTA feeds (GTFS-RT)
        for data_source, feed_url in MTA_ALERT_FEEDS.items():
            try:
                alerts = await fetch_and_parse_alerts(feed_url, data_source)
                # Use savepoint so a DB error on one feed doesn't poison
                # the transaction for remaining feeds
                async with session.begin_nested():
                    stats = await upsert_service_alerts(session, alerts, data_source)
                all_stats[data_source] = {
                    "total_parsed": len(alerts),
                    **stats,
                }
                logger.info(
                    "Service alerts collected for %s: %s",
                    data_source,
                    stats,
                )
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch %s service alerts: %s", data_source, e)
                all_stats[data_source] = {"error": str(e)}
            except Exception as e:
                logger.error(
                    "Error collecting %s service alerts: %s",
                    data_source,
                    e,
                    exc_info=True,
                )
                all_stats[data_source] = {"error": str(e)}

        # NJT feed (getStationMSG API)
        try:
            njt_alerts = await fetch_and_parse_njt_alerts()
            async with session.begin_nested():
                stats = await upsert_service_alerts(session, njt_alerts, "NJT")
            all_stats["NJT"] = {
                "total_parsed": len(njt_alerts),
                **stats,
            }
            logger.info("Service alerts collected for NJT: %s", stats)
        except NJTransitAPIError as e:
            logger.warning("Failed to fetch NJT service alerts: %s", e)
            all_stats["NJT"] = {"error": str(e)}
        except Exception as e:
            logger.error(
                "Error collecting NJT service alerts: %s",
                e,
                exc_info=True,
            )
            all_stats["NJT"] = {"error": str(e)}

        # WMATA feed (Rail Incidents API)
        try:
            wmata_alerts = await _fetch_and_parse_wmata_alerts()
            if wmata_alerts is not None:
                async with session.begin_nested():
                    stats = await upsert_service_alerts(session, wmata_alerts, "WMATA")
                all_stats["WMATA"] = {
                    "total_parsed": len(wmata_alerts),
                    **stats,
                }
                logger.info("Service alerts collected for WMATA: %s", stats)
        except Exception as e:
            logger.error(
                "Error collecting WMATA service alerts: %s",
                e,
                exc_info=True,
            )
            all_stats["WMATA"] = {"error": str(e)}

        await session.commit()

    return all_stats
