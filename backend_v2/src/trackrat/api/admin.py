"""
Server usage statistics page.

Serves a self-contained HTML page at /admin/stats showing live server usage:
request traffic, popular routes, per-provider health, scheduler status, and errors.
All request-level stats are in-memory and reset on restart.

Supports query params:
  ?hours=N       — only show requests from the last N hours
  ?ios_only=true — filter to iOS clients only (shows per-IP breakdown)
"""

from datetime import timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.config.stations.common import get_station_name
from trackrat.db.engine import get_db
from trackrat.models.database import (
    DeviceToken,
    LiveActivityToken,
    RouteAlertSubscription,
    TrainJourney,
)
from trackrat.services.scheduler import get_scheduler
from trackrat.settings import Settings, get_settings
from trackrat.utils.request_stats import get_request_stats
from trackrat.utils.time import now_et

router = APIRouter(tags=["admin"])


async def _db_stats(db: AsyncSession) -> dict[str, Any]:
    """Gather database-level statistics. Degrades gracefully on errors."""
    now = now_et()
    today = now.date()
    providers: list[dict[str, Any]] = []
    device_count = 0
    alert_count = 0
    live_activity_count = 0

    try:
        provider_stmt = (
            select(
                TrainJourney.data_source,
                func.count().label("total_today"),
                func.sum(
                    case(
                        (
                            (TrainJourney.is_completed.is_not(True))
                            & (TrainJourney.is_cancelled.is_not(True))
                            & (TrainJourney.last_updated_at > now - timedelta(hours=2)),
                            1,
                        ),
                        else_=0,
                    )
                ).label("active"),
                func.sum(case((TrainJourney.is_cancelled.is_(True), 1), else_=0)).label(
                    "cancelled"
                ),
                func.max(TrainJourney.last_updated_at).label("last_update"),
            )
            .where(
                TrainJourney.journey_date == today,
            )
            .group_by(TrainJourney.data_source)
            .order_by(TrainJourney.data_source)
        )

        provider_result = await db.execute(provider_stmt)
        providers = [
            {
                "source": row.data_source,
                "total_today": row.total_today,
                "active": int(row.active or 0),
                "cancelled": int(row.cancelled or 0),
                "last_update": (
                    row.last_update.isoformat() if row.last_update else "never"
                ),
                "freshness_min": (
                    round((now - row.last_update).total_seconds() / 60, 1)
                    if row.last_update
                    else None
                ),
            }
            for row in provider_result
        ]
    except Exception:
        pass  # providers stays empty

    try:
        device_count = (
            await db.execute(select(func.count(DeviceToken.id)))
        ).scalar() or 0
        alert_count = (
            await db.execute(select(func.count(RouteAlertSubscription.id)))
        ).scalar() or 0
        live_activity_count = (
            await db.execute(
                select(func.count(LiveActivityToken.id)).where(
                    LiveActivityToken.expires_at > now
                )
            )
        ).scalar() or 0
    except Exception:
        pass  # counts stay 0

    return {
        "providers": providers,
        "device_count": device_count,
        "alert_subscription_count": alert_count,
        "live_activity_count": live_activity_count,
    }


def _scheduler_stats() -> list[dict[str, Any]]:
    """Gather scheduler job status."""
    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()
        return cast(list[dict[str, Any]], status.get("jobs", []))
    except Exception:
        return []


def _format_uptime(seconds: float) -> str:
    """Format seconds into human-readable uptime."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _format_duration(ms: float) -> str:
    """Format milliseconds for display."""
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    return f"{ms:.0f}ms"


def _render_latency_trend(
    trend_data: list[dict[str, Any]],
) -> str:
    """Render a CSS mini-bar chart for latency trend data (12 five-minute buckets)."""
    # Filter to buckets with actual data
    values = [b["avg_ms"] for b in trend_data]
    max_val = max((v for v in values if v > 0), default=0)
    if max_val == 0:
        return ""

    bars = []
    for b in trend_data:
        if b["count"] == 0:
            bars.append("<span class='trend-bar trend-bar-empty'></span>")
        else:
            height = max(2, int(16 * b["avg_ms"] / max_val))
            # Color: green < 100ms, yellow < 500ms, red >= 500ms
            color = (
                "#3fb950"
                if b["avg_ms"] < 100
                else ("#d29922" if b["avg_ms"] < 500 else "#f85149")
            )
            bars.append(
                f"<span class='trend-bar' style='height:{height}px;"
                f"background:{color}'></span>"
            )

    return f"<span class='trend-container'>{''.join(bars)}</span>"


def _build_filter_links(
    current_hours: int | None,
    current_ios_only: bool,
) -> str:
    """Build the filter control links for the HTML page."""

    def _link(label: str, hours: int | None, ios: bool, is_active: bool) -> str:
        params = []
        if hours is not None:
            params.append(f"hours={hours}")
        if ios:
            params.append("ios_only=true")
        qs = f"?{'&'.join(params)}" if params else "/admin/stats"
        cls = "filter-active" if is_active else "filter-link"
        return f"<a href='{qs}' class='{cls}'>{label}</a>"

    time_links = [
        _link("All time", None, current_ios_only, current_hours is None),
        _link("1h", 1, current_ios_only, current_hours == 1),
        _link("6h", 6, current_ios_only, current_hours == 6),
        _link("24h", 24, current_ios_only, current_hours == 24),
    ]
    client_links = [
        _link("All clients", current_hours, False, not current_ios_only),
        _link("iOS only", current_hours, True, current_ios_only),
    ]

    return (
        f"<div class='filters'>Time: {' &middot; '.join(time_links)} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Client: {' &middot; '.join(client_links)}</div>"
    )


def _render_html(
    request_stats: dict[str, Any],
    db_stats: dict[str, Any],
    scheduler_jobs: list[dict[str, Any]],
    settings: Settings,
    *,
    hours: int | None = None,
    ios_only: bool = False,
) -> str:
    """Render the stats page as self-contained HTML."""
    now = now_et()
    uptime = _format_uptime(request_stats["uptime_seconds"])
    unique_ips = request_stats.get("unique_ips", 0)

    # Window description for header
    window_desc = f"last {hours}h" if hours else "since restart"
    ios_desc = " (iOS only)" if ios_only else ""

    # -- Filter controls --
    filter_html = _build_filter_links(hours, ios_only)

    # -- Header --
    header = f"""
    <div class="header">
        <h1>TrackRat Server Stats</h1>
        <div class="meta">
            {settings.environment.upper()} &middot; Uptime: {uptime} &middot;
            {now.strftime('%Y-%m-%d %H:%M:%S ET')} &middot;
            {request_stats['total_requests']} requests {window_desc}{ios_desc} &middot;
            {unique_ips} unique IPs
        </div>
    </div>"""

    # -- Traffic by client --
    client_rows = ""
    for client, count in request_stats["requests_by_client"].items():
        client_rows += f"<tr><td>{_esc(client)}</td><td class='num'>{count}</td></tr>"

    # -- Traffic by endpoint --
    latency_trend = request_stats.get("latency_trend", {})
    endpoint_rows = ""
    for path, count in list(request_stats["requests_by_path"].items())[:15]:
        lat = request_stats["latency"].get(path)
        lat_str = (
            f"{_format_duration(lat['avg'] * 1000)} avg / "
            f"{_format_duration(lat['p95'] * 1000)} p95"
            if lat
            else "-"
        )
        trend_html = _render_latency_trend(latency_trend.get(path, []))
        endpoint_rows += (
            f"<tr><td><code>{_esc(path)}</code></td>"
            f"<td class='num'>{count}</td>"
            f"<td class='num'>{lat_str}</td>"
            f"<td>{trend_html}</td></tr>"
        )

    # -- Status codes --
    status_parts = []
    for code, count in sorted(request_stats["requests_by_status"].items()):
        cls = "ok" if 200 <= code < 300 else ("warn" if 300 <= code < 500 else "err")
        status_parts.append(f"<span class='{cls}'>{code}: {count}</span>")
    status_line = " &middot; ".join(status_parts) if status_parts else "No requests yet"

    # -- Popular route searches --
    route_rows = ""
    for entry in request_stats["route_searches"]:
        from_name = get_station_name(entry["from"])
        to_name = get_station_name(entry["to"])
        count = entry["count"]
        avg_trains = entry.get("avg_trains")
        empty_count = entry.get("empty_count", 0)
        avg_str = f"{avg_trains:.1f}" if avg_trains is not None else "-"
        empty_cls = "num warn" if empty_count > 0 else "num"
        route_rows += (
            f"<tr><td>{_esc(from_name)}</td>"
            f"<td>{_esc(to_name)}</td>"
            f"<td class='num'>{count}</td>"
            f"<td class='num'>{avg_str}</td>"
            f"<td class='{empty_cls}'>{empty_count}</td></tr>"
        )

    # -- Popular train detail views --
    train_detail_rows = ""
    for entry in request_stats.get("train_detail_views", []):
        from_name = get_station_name(entry["from"])
        to_name = get_station_name(entry["to"])
        train_detail_rows += (
            f"<tr><td><strong>{_esc(entry['train_id'])}</strong></td>"
            f"<td>{_esc(from_name)}</td>"
            f"<td>{_esc(to_name)}</td>"
            f"<td class='num'>{entry['count']}</td></tr>"
        )

    # -- Providers --
    provider_rows = ""
    for p in db_stats["providers"]:
        fresh_cls = ""
        if p["freshness_min"] is not None:
            fresh_cls = (
                "ok"
                if p["freshness_min"] < 10
                else ("warn" if p["freshness_min"] < 30 else "err")
            )
        fresh_str = (
            f"{p['freshness_min']}m ago" if p["freshness_min"] is not None else "never"
        )
        provider_rows += (
            f"<tr><td><strong>{_esc(p['source'])}</strong></td>"
            f"<td class='num'>{p['active']}</td>"
            f"<td class='num'>{p['total_today']}</td>"
            f"<td class='num'>{p['cancelled']}</td>"
            f"<td class='num {fresh_cls}'>{fresh_str}</td></tr>"
        )

    # -- Registrations --
    reg_line = (
        f"Devices: {db_stats['device_count']} &middot; "
        f"Alert subscriptions: {db_stats['alert_subscription_count']} &middot; "
        f"Active Live Activities: {db_stats['live_activity_count']}"
    )

    # -- Scheduler --
    sched_rows = ""
    for job in scheduler_jobs:
        next_run = job.get("next_run", "-")
        if next_run and next_run != "-":
            # Truncate to minutes
            next_run = next_run[:16] if len(next_run) > 16 else next_run
        pending = "yes" if job.get("pending") else ""
        sched_rows += (
            f"<tr><td>{_esc(job.get('name', job.get('id', '?')))}</td>"
            f"<td>{next_run}</td>"
            f"<td>{pending}</td></tr>"
        )

    # -- Requests by IP (shown when ios_only or always useful) --
    ip_section = ""
    requests_by_ip = request_stats.get("requests_by_ip", {})
    if ios_only and requests_by_ip:
        ip_rows = ""
        for ip, count in list(requests_by_ip.items())[:20]:
            ip_rows += (
                f"<tr><td><code>{_esc(ip)}</code></td><td class='num'>{count}</td></tr>"
            )
        ip_section = f"""
<h2>Requests by IP ({len(requests_by_ip)} unique)</h2>
<table>
<tr><th>IP Address</th><th class="num">Requests</th></tr>
{ip_rows}
</table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>TrackRat Stats - {settings.environment}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
         background: #0d1117; color: #c9d1d9; padding: 20px; line-height: 1.5; }}
  .header {{ margin-bottom: 16px; }}
  h1 {{ color: #58a6ff; font-size: 1.4em; }}
  .meta {{ color: #8b949e; font-size: 0.85em; margin-top: 4px; }}
  .filters {{ font-size: 0.85em; margin-bottom: 16px; padding: 8px 0; border-bottom: 1px solid #21262d; }}
  .filter-link {{ color: #58a6ff; text-decoration: none; }}
  .filter-link:hover {{ text-decoration: underline; }}
  .filter-active {{ color: #c9d1d9; font-weight: bold; text-decoration: none; }}
  h2 {{ color: #58a6ff; font-size: 1.05em; margin: 20px 0 8px; border-bottom: 1px solid #21262d; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
  th, td {{ text-align: left; padding: 4px 12px 4px 0; font-size: 0.85em; }}
  th {{ color: #8b949e; font-weight: normal; border-bottom: 1px solid #21262d; }}
  td {{ border-bottom: 1px solid #161b22; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ color: #79c0ff; font-size: 0.85em; }}
  .ok {{ color: #3fb950; }}
  .warn {{ color: #d29922; }}
  .err {{ color: #f85149; }}
  .status-line {{ font-size: 0.85em; margin-bottom: 12px; }}
  .reg-line {{ font-size: 0.85em; color: #8b949e; margin-bottom: 12px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 32px; }}
  @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .footer {{ margin-top: 24px; color: #484f58; font-size: 0.75em; text-align: center; }}
  .trend-container {{ display: inline-flex; align-items: flex-end; gap: 1px; height: 16px; vertical-align: middle; margin-left: 6px; }}
  .trend-bar {{ display: inline-block; width: 4px; border-radius: 1px; }}
  .trend-bar-empty {{ height: 2px; background: #21262d; }}
</style>
</head>
<body>
{header}
{filter_html}

<div class="status-line">Status codes: {status_line}</div>
<div class="reg-line">{reg_line}</div>

<div class="grid">
<div>
<h2>Traffic by Endpoint</h2>
<table>
<tr><th>Path</th><th class="num">Hits</th><th class="num">Latency</th><th>Trend</th></tr>
{endpoint_rows if endpoint_rows else "<tr><td colspan='4'>No requests yet</td></tr>"}
</table>

<h2>Popular Route Searches</h2>
<table>
<tr><th>From</th><th>To</th><th class="num">Searches</th><th class="num">Avg Trains</th><th class="num">Empty</th></tr>
{route_rows if route_rows else "<tr><td colspan='5'>No searches yet</td></tr>"}
</table>

<h2>Popular Train Details</h2>
<table>
<tr><th>Train ID</th><th>From</th><th>To</th><th class="num">Views</th></tr>
{train_detail_rows if train_detail_rows else "<tr><td colspan='4'>No views yet</td></tr>"}
</table>
</div>

<div>
<h2>Clients</h2>
<table>
<tr><th>Client</th><th class="num">Requests</th></tr>
{client_rows if client_rows else "<tr><td colspan='2'>No requests yet</td></tr>"}
</table>

<h2>Providers (Today)</h2>
<table>
<tr><th>Source</th><th class="num">Active</th><th class="num">Today</th><th class="num">Cancelled</th><th class="num">Freshness</th></tr>
{provider_rows if provider_rows else "<tr><td colspan='5'>No data</td></tr>"}
</table>
{ip_section}
</div>
</div>

<h2>Scheduler Jobs</h2>
<table>
<tr><th>Job</th><th>Next Run</th><th>Pending</th></tr>
{sched_rows if sched_rows else "<tr><td colspan='3'>Scheduler not available</td></tr>"}
</table>

<div class="footer">Auto-refreshes every 60s. In-memory stats reset on server restart.</div>
</body>
</html>"""


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@router.get("/admin/stats", response_class=HTMLResponse)
async def stats_page(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    hours: int | None = Query(None, ge=1, le=168),
    ios_only: bool = Query(False),
) -> HTMLResponse:
    """Server usage statistics page."""
    request_data = get_request_stats().snapshot(hours=hours, ios_only=ios_only)
    db_data = await _db_stats(db)
    scheduler_jobs = _scheduler_stats()
    html = _render_html(
        request_data,
        db_data,
        scheduler_jobs,
        settings,
        hours=hours,
        ios_only=ios_only,
    )
    return HTMLResponse(content=html)


@router.get("/admin/stats.json")
async def stats_json(
    db: AsyncSession = Depends(get_db),
    hours: int | None = Query(None, ge=1, le=168),
    ios_only: bool = Query(False),
) -> dict[str, Any]:
    """Server usage statistics as JSON."""
    request_data = get_request_stats().snapshot(hours=hours, ios_only=ios_only)
    db_data = await _db_stats(db)
    scheduler_jobs = _scheduler_stats()

    # Resolve station names in route searches for JSON consumers
    route_searches = {
        f"{get_station_name(entry['from'])} -> {get_station_name(entry['to'])}": {
            "count": entry["count"],
            **(
                {"avg_trains": round(entry["avg_trains"], 1)}
                if "avg_trains" in entry
                else {}
            ),
            **(
                {"empty_count": entry["empty_count"]}
                if entry.get("empty_count")
                else {}
            ),
        }
        for entry in request_data["route_searches"]
    }
    request_data["route_searches"] = route_searches

    # Include scheduler jobs (JSON parity with HTML)
    request_data["scheduler_jobs"] = scheduler_jobs

    train_detail_views = {
        f"{entry['train_id']} ({get_station_name(entry['from'])} -> {get_station_name(entry['to'])})": entry[
            "count"
        ]
        for entry in request_data.get("train_detail_views", [])
    }
    request_data["train_detail_views"] = train_detail_views

    return {**request_data, **db_data}
