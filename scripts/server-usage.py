#!/usr/bin/env python3
"""Server usage report for TrackRat backend.

Queries GCP load balancer logs and backend endpoints to generate a
comprehensive usage summary: API traffic, route searches, train follows,
scheduler health, errors, and latency breakdown.

Requires GCP service account credentials (same as gcp-logs.py).

Usage:
    PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 scripts/server-usage.py [OPTIONS]

Options:
    --env production|staging   Environment (default: production)
    --hours N                  Time window in hours (default: 1)
    --output FILE              Write report to file
    --json                     Output as JSON instead of formatted text

Examples:
    # Production usage, last hour
    python3 scripts/server-usage.py

    # Staging, last 6 hours
    python3 scripts/server-usage.py --env staging --hours 6

    # Save report
    python3 scripts/server-usage.py --hours 24 --output /tmp/usage.txt
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SA_KEY_PATH = "/root/.config/gcloud/service-account.json"
PROJECT = "trackrat-v2"

FORWARDING_RULES = {
    "production": "trackrat-production-https",
    "staging": "trackrat-staging-https",
}

HOSTNAME_PREFIX = {
    "staging": "trackrat-staging-",
    "production": "trackrat-production-",
}

API_URLS = {
    "production": "https://apiv2.trackrat.net",
    "staging": "https://staging.apiv2.trackrat.net",
}


# ---------------------------------------------------------------------------
# GCP Auth (mirrors gcp-logs.py pattern)
# ---------------------------------------------------------------------------
def _check_dependencies():
    try:
        import google.auth.transport.requests  # noqa: F401
        import google.oauth2.service_account  # noqa: F401
        import requests  # noqa: F401
    except ImportError as e:
        print(
            f"Missing dependency: {e}\n\n"
            "Run:\n"
            "  pip install google-cloud-logging 2>&1 | tail -3\n"
            "  pip install cffi cryptography --force-reinstall --target=/tmp/pylibs 2>&1 | tail -3\n\n"
            "Then invoke with:\n"
            "  PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 scripts/server-usage.py",
            file=sys.stderr,
        )
        sys.exit(1)


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    import requests

    if not os.path.exists(SA_KEY_PATH):
        print(
            f"Service account key not found at {SA_KEY_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SA_KEY_PATH) as f:
        sa_info = json.loads(f.read(), strict=False)

    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/logging.read"]
    )
    credentials.refresh(Request(session=requests.Session()))
    return credentials.token


# ---------------------------------------------------------------------------
# GCP Log Queries
# ---------------------------------------------------------------------------
def query_logs(token, log_filter, limit=1000, max_pages=10):
    """Query GCP Cloud Logging API, paginating up to max_pages."""
    import requests as req

    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    all_entries = []
    page_token = None
    for _ in range(max_pages):
        body = {
            "resourceNames": [f"projects/{PROJECT}"],
            "filter": log_filter,
            "orderBy": "timestamp desc",
            "pageSize": limit,
        }
        if page_token:
            body["pageToken"] = page_token
        resp = req.post(url, json=body, headers=headers)
        data = resp.json()
        if "error" in data:
            print(
                f"GCP API error: {data['error'].get('message', data['error'])}",
                file=sys.stderr,
            )
            break
        entries = data.get("entries", [])
        all_entries.extend(entries)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return all_entries


def discover_instance_id(token, env):
    """Find the GCE instance_id for an environment (mirrors gcp-logs.py)."""
    import requests as req

    prefix = HOSTNAME_PREFIX[env]
    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": f'jsonPayload._HOSTNAME=~"^{prefix}"',
        "orderBy": "timestamp desc",
        "pageSize": 1,
    }
    resp = req.post(url, json=body, headers=headers)
    entries = resp.json().get("entries", [])
    if entries:
        e = entries[0]
        hostname = e.get("jsonPayload", {}).get("_HOSTNAME", "")
        instance_id = (
            e.get("resource", {}).get("labels", {}).get("instance_id", "")
        )
        if hostname and instance_id:
            return instance_id, hostname
    return None, None


# ---------------------------------------------------------------------------
# Station Name Resolver
# ---------------------------------------------------------------------------
def load_station_names():
    """Parse station name dicts from backend config files without importing."""
    names = {}
    stations_dir = (
        Path(__file__).resolve().parent.parent
        / "backend_v2"
        / "src"
        / "trackrat"
        / "config"
        / "stations"
    )
    # Pattern matches:  "CODE": "Name",  or  "CODE": "Name"
    pattern = re.compile(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"', re.MULTILINE)

    for filename in ["njt.py", "amtrak.py", "path.py", "lirr.py", "mnr.py", "subway.py", "patco.py"]:
        filepath = stations_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            # Only parse the STATION_NAMES dict (stop at first non-dict line after it)
            in_names_dict = False
            for line in content.splitlines():
                if "_STATION_NAMES" in line and "dict" in line:
                    in_names_dict = True
                    continue
                if in_names_dict:
                    if line.strip() == "}":
                        in_names_dict = False
                        continue
                    m = pattern.match(line)
                    if m:
                        code, name = m.group(1), m.group(2)
                        # Don't overwrite (NJT takes priority for shared codes)
                        if code not in names:
                            names[code] = name
    return names


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------
def fetch_lb_logs(token, env, hours):
    """Fetch GCP load balancer logs for the given environment and time window."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rule = FORWARDING_RULES[env]
    log_filter = (
        f'resource.type="http_load_balancer"'
        f' AND resource.labels.forwarding_rule_name="{rule}"'
        f' AND timestamp>="{since}"'
    )
    return query_logs(token, log_filter, limit=1000, max_pages=20)


def fetch_app_logs(token, instance_id, hours, level=None, search=None):
    """Fetch structured app logs from cos_containers."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    parts = [
        f'resource.labels.instance_id="{instance_id}"',
        f'logName="projects/{PROJECT}/logs/cos_containers"',
        f'timestamp>="{since}"',
    ]
    if level:
        parts.append(f'jsonPayload.level="{level}"')
    if search:
        parts.append(
            f'(jsonPayload.event=~"{search}" OR jsonPayload.message=~"{search}")'
        )
    return query_logs(token, " AND ".join(parts), limit=500, max_pages=5)


def fetch_health(env):
    """Fetch /health and /scheduler/status from the server."""
    import requests as req

    base = API_URLS[env]
    health = {}
    scheduler = {}
    try:
        r = req.get(f"{base}/health", timeout=10)
        if r.status_code == 200:
            health = r.json()
    except Exception:
        pass
    try:
        r = req.get(f"{base}/scheduler/status", timeout=10)
        if r.status_code == 200:
            scheduler = r.json()
    except Exception:
        pass
    return health, scheduler


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def classify_entry(path, params):
    """Classify an API request into a business category."""
    if "/trains/departures" in path:
        return "departures"
    if "/trains/" in path and "/history" in path:
        return "train_history"
    if "/trains/" in path:
        return "train_detail"
    if "/routes/congestion" in path:
        return "congestion"
    if "/routes/history" in path:
        return "route_history"
    if "/routes/summary" in path:
        return "route_summary"
    if "/routes/segments" in path:
        return "segment_trains"
    if "/predictions/track" in path:
        return "track_predictions"
    if "/predictions/delay" in path:
        return "delay_predictions"
    if "/predictions/supported" in path:
        return "prediction_stations"
    if "/live-activities/register" in path:
        return "live_activity"
    if "/devices/register" in path:
        return "device_register"
    if "/alerts/subscriptions" in path:
        return "alert_subscriptions"
    if "/validation" in path:
        return "validation"
    if "/feedback" in path:
        return "feedback"
    return None


def parse_user_agent(ua):
    """Extract a readable client label from user agent string."""
    if not ua:
        return "unknown"
    if "TrackRat/" in ua:
        version = ua.split("TrackRat/")[1].split(" ")[0]
        return f"iOS/{version}"
    if "Mozilla" in ua or "Safari" in ua:
        return "browser"
    if "GoogleStackdriver" in ua:
        return "gcp-healthcheck"
    if "python" in ua.lower() or "requests" in ua.lower():
        return "python-script"
    if "curl" in ua.lower():
        return "curl"
    if "Go-http-client" in ua:
        return "go-scanner"
    return "other"


def analyze_lb_entries(entries, station_names):
    """Analyze load balancer log entries into structured report data."""
    # Counters
    api_endpoint_counts = Counter()
    route_searches = Counter()
    train_lookups = Counter()
    user_agents = Counter()
    status_codes = Counter()
    latencies = defaultdict(list)
    unique_ips = set()
    total_api = 0
    total_non_api = 0
    scanner_count = 0
    healthcheck_count = 0

    for e in entries:
        hr = e.get("httpRequest", {})
        raw_url = hr.get("requestUrl", "")
        parsed = urlparse(raw_url)
        path = parsed.path
        params = parse_qs(parsed.query)
        ua_raw = hr.get("userAgent", "")
        ua = parse_user_agent(ua_raw)
        status = hr.get("status", 0)
        lat_str = hr.get("latency", "0s")
        lat = float(lat_str.rstrip("s"))
        remote_ip = hr.get("remoteIp", "")

        # Filter out health checks
        if path in ("/health", "/health/live", "/health/ready", "/metrics"):
            healthcheck_count += 1
            continue

        # Filter out scanner probes (not real API usage)
        if "/api/v2/" not in path and path not in ("/", ""):
            category = classify_entry(path, params)
            if category is None:
                scanner_count += 1
                continue

        # Classify
        category = classify_entry(path, params)
        if category is None:
            total_non_api += 1
            continue

        total_api += 1
        api_endpoint_counts[category] += 1
        status_codes[status] += 1
        unique_ips.add(remote_ip)
        user_agents[ua] += 1
        latencies[category].append(lat)

        # Extract business details
        if category == "departures":
            from_s = (params.get("from", params.get("from_station", ["?"])) or ["?"])[0]
            to_s = (params.get("to", params.get("to_station", ["?"])) or ["?"])[0]
            from_name = station_names.get(from_s, from_s)
            to_name = station_names.get(to_s, to_s)
            route_searches[f"{from_name} -> {to_name}"] += 1

        elif category == "train_detail":
            parts = path.split("/trains/")
            if len(parts) > 1:
                train_id = parts[1].split("/")[0].split("?")[0]
                train_lookups[train_id] += 1

    return {
        "total_api": total_api,
        "total_non_api": total_non_api,
        "healthcheck_count": healthcheck_count,
        "scanner_count": scanner_count,
        "endpoint_counts": api_endpoint_counts,
        "route_searches": route_searches,
        "train_lookups": train_lookups,
        "user_agents": user_agents,
        "status_codes": status_codes,
        "latencies": latencies,
        "unique_ips": len(unique_ips),
    }


def analyze_app_logs(task_entries, error_entries, warning_entries):
    """Analyze app log entries for scheduler tasks and errors."""
    task_counts = Counter()
    task_durations = defaultdict(list)
    for e in task_entries:
        jp = e.get("jsonPayload", {})
        task = jp.get("task", "unknown")
        dur = jp.get("duration_ms", 0)
        task_counts[task] += 1
        if dur:
            task_durations[task].append(dur)

    errors = []
    for e in error_entries:
        jp = e.get("jsonPayload", {})
        ts = e.get("timestamp", "")[:19]
        event = jp.get("event", "")
        msg = jp.get("message", "")
        error = jp.get("error", "")
        logger = jp.get("logger", "").replace("trackrat.", "")
        errors.append(
            {"timestamp": ts, "logger": logger, "event": event, "message": msg, "error": error}
        )

    warn_counts = Counter()
    for e in warning_entries:
        jp = e.get("jsonPayload", {})
        event = jp.get("event", jp.get("message", "unknown"))
        warn_counts[event[:80]] += 1

    return {
        "task_counts": task_counts,
        "task_durations": task_durations,
        "errors": errors,
        "warning_counts": warn_counts,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
DIM = "\033[2m"
NC = "\033[0m"


def fmt_latency(lats):
    """Format latency stats for a list of latency values."""
    if not lats:
        return "n/a"
    lats_sorted = sorted(lats)
    n = len(lats_sorted)
    p50 = lats_sorted[n // 2]
    p95 = lats_sorted[int(n * 0.95)] if n >= 20 else max(lats_sorted)
    avg = statistics.mean(lats_sorted)
    return f"avg={avg:.2f}s  p50={p50:.2f}s  p95={p95:.2f}s  max={max(lats_sorted):.2f}s"


def format_report(env, hours, health, scheduler, lb_analysis, app_analysis, use_color=True):
    """Format the full report as a string."""
    lines = []
    b = BOLD if use_color else ""
    g = GREEN if use_color else ""
    y = YELLOW if use_color else ""
    r = RED if use_color else ""
    d = DIM if use_color else ""
    nc = NC if use_color else ""

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"{b}TrackRat Server Usage Report{nc}")
    lines.append(f"Environment: {env}  |  Window: {hours}h  |  Generated: {now_str}")
    lines.append("")

    # --- Section 1: Server State ---
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}SERVER STATE{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    if health:
        status = health.get("status", "unknown")
        color = g if status == "healthy" else (y if status == "degraded" else r)
        lines.append(f"  Status:           {color}{status}{nc}")
        lines.append(f"  Version:          {health.get('version', '?')}")
        checks = health.get("checks", {})
        db = checks.get("database", {})
        lines.append(f"  DB journeys:      {db.get('journey_count', '?'):,}")
        fresh = checks.get("data_freshness", {})
        lines.append(f"  Fresh journeys:   {fresh.get('fresh_journeys', '?')} (last {fresh.get('cutoff_hours', '?')}h)")
        disc = checks.get("discovery", {})
        lines.append(f"  Discovery:        {disc.get('recent_runs', '?')} runs, {disc.get('success_rate', '?')}% success")
    else:
        lines.append(f"  {r}Could not reach /health{nc}")

    if scheduler:
        lines.append(f"  Scheduler:        {'running' if scheduler.get('running') else 'stopped'}, {scheduler.get('jobs_count', '?')} jobs")
        jobs = scheduler.get("jobs", [])
        active = scheduler.get("active_tasks", [])
        if active:
            lines.append(f"  Active tasks:     {', '.join(active)}")
    lines.append("")

    # --- Section 2: API Traffic ---
    la = lb_analysis
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}API TRAFFIC{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    rate = la["total_api"] / hours if hours > 0 else 0
    lines.append(f"  API requests:     {la['total_api']}  ({rate:.1f}/hour)")
    lines.append(f"  Unique clients:   {la['unique_ips']}")
    lines.append(f"  Health checks:    {la['healthcheck_count']}")
    lines.append(f"  Scanner probes:   {la['scanner_count']}")
    lines.append("")

    # Endpoint breakdown
    lines.append(f"  {b}Endpoint Breakdown:{nc}")
    ep_labels = {
        "departures": "Departure searches",
        "train_detail": "Train detail views",
        "train_history": "Train history",
        "congestion": "Congestion checks",
        "route_history": "Route history",
        "route_summary": "Route summaries",
        "segment_trains": "Segment trains",
        "track_predictions": "Track predictions",
        "delay_predictions": "Delay predictions",
        "prediction_stations": "Prediction stations",
        "live_activity": "Live Activity registrations",
        "device_register": "Device registrations",
        "alert_subscriptions": "Alert subscriptions",
        "validation": "Validation queries",
        "feedback": "Feedback submissions",
    }
    for ep, count in la["endpoint_counts"].most_common():
        label = ep_labels.get(ep, ep)
        pct = count / la["total_api"] * 100 if la["total_api"] > 0 else 0
        lines.append(f"    {count:>5}  {label:<30s}  ({pct:.0f}%)")
    lines.append("")

    # Status codes
    lines.append(f"  {b}Status Codes:{nc}")
    for status, count in sorted(la["status_codes"].items()):
        color = g if 200 <= status < 300 else (y if 300 <= status < 400 else r)
        lines.append(f"    {color}{status}{nc}: {count}")
    lines.append("")

    # User agents
    lines.append(f"  {b}Clients:{nc}")
    for ua, count in la["user_agents"].most_common():
        lines.append(f"    {count:>5}  {ua}")
    lines.append("")

    # --- Section 3: Business Activity ---
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}BUSINESS ACTIVITY{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    # Route searches
    if la["route_searches"]:
        lines.append(f"  {b}Route Searches ({la['endpoint_counts'].get('departures', 0)} total):{nc}")
        for route, count in la["route_searches"].most_common(15):
            lines.append(f"    {count:>5}x  {route}")
    else:
        lines.append(f"  {d}No departure searches in this window{nc}")
    lines.append("")

    # Train detail views
    if la["train_lookups"]:
        lines.append(f"  {b}Trains Viewed ({la['endpoint_counts'].get('train_detail', 0)} total):{nc}")
        for tid, count in la["train_lookups"].most_common(10):
            lines.append(f"    {count:>5}x  Train {tid}")
    else:
        lines.append(f"  {d}No train detail views in this window{nc}")
    lines.append("")

    # Live activities & device registrations
    la_count = la["endpoint_counts"].get("live_activity", 0)
    dev_count = la["endpoint_counts"].get("device_register", 0)
    alert_count = la["endpoint_counts"].get("alert_subscriptions", 0)
    feedback_count = la["endpoint_counts"].get("feedback", 0)
    lines.append(f"  {b}Engagement:{nc}")
    lines.append(f"    Live Activity registrations:  {la_count}")
    lines.append(f"    Device registrations (APNS):  {dev_count}")
    lines.append(f"    Alert subscriptions synced:   {alert_count}")
    lines.append(f"    Feedback submissions:         {feedback_count}")
    lines.append("")

    # --- Section 4: Latency ---
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}LATENCY{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    for ep, lats in sorted(la["latencies"].items(), key=lambda x: -len(x[1])):
        if lats:
            label = ep_labels.get(ep, ep)
            lines.append(f"  {label:<30s}  n={len(lats):>4}  {fmt_latency(lats)}")
    lines.append("")

    # --- Section 5: Scheduler Tasks ---
    aa = app_analysis
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}SCHEDULER TASKS{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    if aa["task_counts"]:
        for task, count in aa["task_counts"].most_common():
            durs = aa["task_durations"].get(task, [])
            avg_dur = statistics.mean(durs) if durs else 0
            lines.append(f"    {count:>4}x  {task:<35s}  avg {avg_dur:,.0f}ms")
    else:
        lines.append(f"  {d}No scheduler task completions found{nc}")
    lines.append("")

    # --- Section 6: Errors & Warnings ---
    lines.append(f"{b}{'=' * 60}{nc}")
    lines.append(f"{b}ERRORS & WARNINGS{nc}")
    lines.append(f"{b}{'=' * 60}{nc}")

    if aa["errors"]:
        lines.append(f"  {r}Errors ({len(aa['errors'])}):{nc}")
        for err in aa["errors"][:10]:
            ts = err["timestamp"]
            logger = err["logger"]
            event = err["event"]
            error_msg = err["error"]
            lines.append(f"    {ts}  [{logger}] {event}")
            if error_msg:
                lines.append(f"      {r}{error_msg[:120]}{nc}")
    else:
        lines.append(f"  {g}No errors{nc}")
    lines.append("")

    if aa["warning_counts"]:
        lines.append(f"  {y}Warnings ({sum(aa['warning_counts'].values())}):{nc}")
        for warn, count in aa["warning_counts"].most_common(10):
            lines.append(f"    {count:>4}x  {warn}")
    else:
        lines.append(f"  {g}No warnings{nc}")
    lines.append("")

    return "\n".join(lines)


def build_json_report(env, hours, health, scheduler, lb_analysis, app_analysis):
    """Build a JSON-serializable report dict."""
    la = lb_analysis
    aa = app_analysis
    return {
        "environment": env,
        "window_hours": hours,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "server_state": {
            "health": health,
            "scheduler_running": scheduler.get("running"),
            "scheduler_jobs": scheduler.get("jobs_count"),
        },
        "api_traffic": {
            "total_requests": la["total_api"],
            "requests_per_hour": round(la["total_api"] / hours, 1) if hours > 0 else 0,
            "unique_clients": la["unique_ips"],
            "healthcheck_count": la["healthcheck_count"],
            "scanner_count": la["scanner_count"],
            "endpoints": dict(la["endpoint_counts"].most_common()),
            "status_codes": {str(k): v for k, v in la["status_codes"].items()},
            "clients": dict(la["user_agents"].most_common()),
        },
        "business_activity": {
            "route_searches": dict(la["route_searches"].most_common(20)),
            "trains_viewed": dict(la["train_lookups"].most_common(20)),
            "live_activities": la["endpoint_counts"].get("live_activity", 0),
            "device_registrations": la["endpoint_counts"].get("device_register", 0),
            "alert_subscriptions": la["endpoint_counts"].get("alert_subscriptions", 0),
            "feedback_submissions": la["endpoint_counts"].get("feedback", 0),
        },
        "latency": {
            ep: {
                "count": len(lats),
                "avg": round(statistics.mean(lats), 3),
                "p50": round(sorted(lats)[len(lats) // 2], 3),
                "max": round(max(lats), 3),
            }
            for ep, lats in la["latencies"].items()
            if lats
        },
        "scheduler_tasks": dict(aa["task_counts"].most_common()),
        "errors": aa["errors"][:20],
        "warnings": dict(aa["warning_counts"].most_common(10)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="TrackRat server usage report")
    parser.add_argument(
        "--env", choices=["production", "staging"], default="production"
    )
    parser.add_argument("--hours", type=float, default=1)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    _check_dependencies()

    print(f"Collecting data for {args.env} (last {args.hours}h)...", file=sys.stderr)

    # Auth
    token = get_credentials()

    # Discover instance for app logs
    instance_id, hostname = discover_instance_id(token, args.env)
    if instance_id:
        print(f"Instance: {hostname} ({instance_id})", file=sys.stderr)
    else:
        print("Could not find instance — app logs will be skipped", file=sys.stderr)

    # Station names for friendly display
    station_names = load_station_names()
    print(f"Loaded {len(station_names)} station names", file=sys.stderr)

    # Fetch data in parallel-ish (sequential but fast)
    print("Fetching LB logs...", file=sys.stderr)
    lb_entries = fetch_lb_logs(token, args.env, args.hours)
    print(f"  {len(lb_entries)} LB log entries", file=sys.stderr)

    task_entries = []
    error_entries = []
    warning_entries = []
    if instance_id:
        print("Fetching app logs...", file=sys.stderr)
        task_entries = fetch_app_logs(
            token, instance_id, args.hours, search="task_completed"
        )
        error_entries = fetch_app_logs(
            token, instance_id, args.hours, level="error"
        )
        warning_entries = fetch_app_logs(
            token, instance_id, args.hours, level="warning"
        )
        print(
            f"  {len(task_entries)} task completions, {len(error_entries)} errors, {len(warning_entries)} warnings",
            file=sys.stderr,
        )

    print("Fetching health/scheduler...", file=sys.stderr)
    health, scheduler = fetch_health(args.env)

    # Analyze
    lb_analysis = analyze_lb_entries(lb_entries, station_names)
    app_analysis = analyze_app_logs(task_entries, error_entries, warning_entries)

    # Output
    if args.json_output:
        report = build_json_report(
            args.env, args.hours, health, scheduler, lb_analysis, app_analysis
        )
        output = json.dumps(report, indent=2, default=str)
    else:
        use_color = not args.output and sys.stdout.isatty()
        output = format_report(
            args.env, args.hours, health, scheduler, lb_analysis, app_analysis,
            use_color=use_color,
        )

    if args.output:
        with open(args.output, "w") as f:
            f.write(output + "\n")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
