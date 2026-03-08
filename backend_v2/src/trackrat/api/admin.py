"""
Server usage statistics page.

Serves a self-contained HTML page at /admin/stats showing live server usage:
request traffic, popular routes, per-provider health, scheduler status, and errors.
All request-level stats are in-memory and reset on restart.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
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
        provider_stmt = select(
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
        ).where(
            TrainJourney.journey_date == today,
        ).group_by(
            TrainJourney.data_source
        ).order_by(
            TrainJourney.data_source
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
        return status.get("jobs", [])
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


def _render_html(
    request_stats: dict,
    db_stats: dict[str, Any],
    scheduler_jobs: list[dict[str, Any]],
    settings: Settings,
) -> str:
    """Render the stats page as self-contained HTML."""
    now = now_et()
    uptime = _format_uptime(request_stats["uptime_seconds"])

    # -- Header --
    header = f"""
    <div class="header">
        <h1>TrackRat Server Stats</h1>
        <div class="meta">
            {settings.environment.upper()} &middot; Uptime: {uptime} &middot;
            {now.strftime('%Y-%m-%d %H:%M:%S ET')} &middot;
            {request_stats['total_requests']} total requests since restart
        </div>
    </div>"""

    # -- Traffic by client --
    client_rows = ""
    for client, count in request_stats["requests_by_client"].items():
        client_rows += f"<tr><td>{_esc(client)}</td><td class='num'>{count}</td></tr>"

    # -- Traffic by endpoint --
    endpoint_rows = ""
    for path, count in list(request_stats["requests_by_path"].items())[:15]:
        lat = request_stats["latency"].get(path)
        lat_str = (
            f"{_format_duration(lat['avg'] * 1000)} avg / "
            f"{_format_duration(lat['p95'] * 1000)} p95"
            if lat
            else "-"
        )
        endpoint_rows += (
            f"<tr><td><code>{_esc(path)}</code></td>"
            f"<td class='num'>{count}</td>"
            f"<td class='num'>{lat_str}</td></tr>"
        )

    # -- Status codes --
    status_parts = []
    for code, count in sorted(request_stats["requests_by_status"].items()):
        cls = "ok" if 200 <= code < 300 else ("warn" if 300 <= code < 500 else "err")
        status_parts.append(f"<span class='{cls}'>{code}: {count}</span>")
    status_line = " &middot; ".join(status_parts) if status_parts else "No requests yet"

    # -- Popular route searches --
    route_rows = ""
    for (from_code, to_code), count in request_stats["route_searches"].items():
        from_name = get_station_name(from_code)
        to_name = get_station_name(to_code)
        route_rows += (
            f"<tr><td>{_esc(from_name)}</td>"
            f"<td>{_esc(to_name)}</td>"
            f"<td class='num'>{count}</td></tr>"
        )

    # -- Providers --
    provider_rows = ""
    for p in db_stats["providers"]:
        fresh_cls = ""
        if p["freshness_min"] is not None:
            fresh_cls = "ok" if p["freshness_min"] < 10 else ("warn" if p["freshness_min"] < 30 else "err")
        fresh_str = f"{p['freshness_min']}m ago" if p["freshness_min"] is not None else "never"
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
  .header {{ margin-bottom: 24px; }}
  h1 {{ color: #58a6ff; font-size: 1.4em; }}
  .meta {{ color: #8b949e; font-size: 0.85em; margin-top: 4px; }}
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
</style>
</head>
<body>
{header}

<div class="status-line">Status codes: {status_line}</div>
<div class="reg-line">{reg_line}</div>

<div class="grid">
<div>
<h2>Traffic by Endpoint</h2>
<table>
<tr><th>Path</th><th class="num">Hits</th><th class="num">Latency</th></tr>
{endpoint_rows if endpoint_rows else "<tr><td colspan='3'>No requests yet</td></tr>"}
</table>

<h2>Popular Route Searches</h2>
<table>
<tr><th>From</th><th>To</th><th class="num">Count</th></tr>
{route_rows if route_rows else "<tr><td colspan='3'>No searches yet</td></tr>"}
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
) -> HTMLResponse:
    """Server usage statistics page."""
    request_data = get_request_stats().snapshot()
    db_data = await _db_stats(db)
    scheduler_jobs = _scheduler_stats()
    html = _render_html(request_data, db_data, scheduler_jobs, settings)
    return HTMLResponse(content=html)


@router.get("/admin/stats.json")
async def stats_json(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Server usage statistics as JSON."""
    request_data = get_request_stats().snapshot()
    db_data = await _db_stats(db)

    # Convert tuple keys to strings for JSON serialization
    route_searches = {
        f"{from_code} -> {to_code}": count
        for (from_code, to_code), count in get_request_stats()
        .snapshot()["route_searches"]
        .items()
    }
    request_data["route_searches"] = route_searches

    return {**request_data, **db_data}
