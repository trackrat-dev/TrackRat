#!/usr/bin/env python3
"""Query GCP logs for TrackRat backend instances.

Usage:
    PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py [OPTIONS]

Options:
    --env staging|production   Environment to query (default: staging)
    --filter FILTER            Additional log filter expression
    --errors                   Show only severity>=ERROR
    --warnings                 Show only severity>=WARNING
    --search PATTERN           Search log messages for pattern
    --limit N                  Max entries to return (default: 100)
    --output FILE              Write output to file (for file-analyzer)
    --raw                      Include Docker events (default: app logs only)

Examples:
    # Recent staging app logs
    python3 .claude/scripts/gcp-logs.py

    # Production errors
    python3 .claude/scripts/gcp-logs.py --env production --errors

    # Search for a pattern
    python3 .claude/scripts/gcp-logs.py --search "departure_cache"

    # Save output for file-analyzer
    python3 .claude/scripts/gcp-logs.py --output /tmp/logs.txt

    # Include raw Docker events too
    python3 .claude/scripts/gcp-logs.py --raw
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

SA_KEY_PATH = "/root/.config/gcloud/service-account.json"
PROJECT = "trackrat-v2"
# Stable prefix — GCP MIG appends random suffixes (e.g. trackrat-staging-s565)
HOSTNAME_PREFIX = {
    "staging": "trackrat-staging-",
    "production": "trackrat-production-",
}
# Instance discovery searches this far back (Cloud Logging's default retention
# is 30 days) and follows at most this many result pages.
DISCOVERY_LOOKBACK_DAYS = 30
DISCOVERY_MAX_PAGES = 10
# A newest host entry older than this suggests the instance has stopped.
DISCOVERY_STALE_AFTER = timedelta(hours=1)


def _check_dependencies():
    """Verify required packages are importable, with actionable error on failure."""
    try:
        import google.oauth2.service_account  # noqa: F401
        import google.auth.transport.requests  # noqa: F401
        import requests  # noqa: F401
    except ImportError as e:
        print(
            f"❌ Missing dependency: {e}\n\n"
            "Run these commands to install:\n"
            "  pip install google-cloud-logging 2>&1 | tail -3\n"
            "  pip install cffi cryptography --force-reinstall --target=/tmp/pylibs 2>&1 | tail -3\n\n"
            "Then invoke with:\n"
            "  PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py",
            file=sys.stderr,
        )
        sys.exit(1)


def get_credentials():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import requests

    import os

    if not os.path.exists(SA_KEY_PATH):
        print(
            f"❌ Service account key not found at {SA_KEY_PATH}\n\n"
            "The SessionStart hook should write GCP_SA_KEY_JSON to this path.\n"
            "Check that GCP_SA_KEY_JSON is set in your environment and\n"
            "the hook in .claude/settings.json ran successfully.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SA_KEY_PATH, "r") as f:
        sa_info = json.loads(f.read(), strict=False)

    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/logging.read"]
    )
    credentials.refresh(Request(session=requests.Session()))
    return credentials.token


def discover_instance_id(token, env, now=None):
    """Find the newest GCE instance for an environment via hostname prefix match.

    Returns ``(instance_id, hostname, timestamp)`` of the newest matching
    entry, or ``(None, None, None)`` when no instance of ``env`` has logged
    within ``DISCOVERY_LOOKBACK_DAYS``.

    Only the journald ``cos_system`` source carries ``_HOSTNAME``;
    ``cos_containers`` app entries have the instance_id but no hostname or
    environment, so they cannot stand in for it. Two things made this miss a
    running instance (issue #1994): the filter had no time bound, and an
    unbounded regex scan can return a page with no entries but a
    ``nextPageToken`` — which was read as "no instance". The window bounds the
    scan and the loop follows the token.
    """
    import requests

    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=DISCOVERY_LOOKBACK_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    prefix = HOSTNAME_PREFIX[env]
    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": f'jsonPayload._HOSTNAME=~"^{prefix}" AND timestamp>="{since}"',
        "orderBy": "timestamp desc",
        "pageSize": 1,
    }
    for _ in range(DISCOVERY_MAX_PAGES):
        data = requests.post(url, json=body, headers=headers).json()
        if "error" in data:
            print(
                f"API error: {data['error'].get('message', data['error'])}",
                file=sys.stderr,
            )
            sys.exit(1)
        for e in data.get("entries", []):
            hostname = e.get("jsonPayload", {}).get("_HOSTNAME", "")
            instance_id = e.get("resource", {}).get("labels", {}).get("instance_id", "")
            if hostname and instance_id:
                return instance_id, hostname, e.get("timestamp", "")
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        body["pageToken"] = page_token
    return None, None, None


def is_stale(timestamp, now):
    """True when a Cloud Logging RFC 3339 timestamp is older than DISCOVERY_STALE_AFTER."""
    seen = datetime.fromisoformat(timestamp[:19]).replace(tzinfo=timezone.utc)
    return now - seen > DISCOVERY_STALE_AFTER


def query_logs(token, log_filter, limit):
    import requests

    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": log_filter,
        "orderBy": "timestamp desc",
        "pageSize": limit,
    }
    resp = requests.post(url, json=body, headers=headers)
    data = resp.json()
    if "error" in data:
        print(f"API error: {data['error'].get('message', data['error'])}", file=sys.stderr)
        sys.exit(1)
    return data.get("entries", [])


def format_app_entry(entry):
    """Format a cos_containers structured app log entry."""
    ts = entry.get("timestamp", "?")[:19]
    jp = entry.get("jsonPayload", {})
    level = jp.get("level", "info").upper()
    event = jp.get("event", "")
    logger = jp.get("logger", "").replace("trackrat.", "")
    message = jp.get("message", "")

    # Build a readable summary from structured fields
    detail_parts = []
    if message:
        detail_parts.append(message)
    elif event:
        detail_parts.append(event)

    # Include key structured data if present
    for key in (
        "task",
        "duration_ms",
        "route",
        "train_id",
        "error",
        "error_type",
        "params",
    ):
        if key in jp and key != "event":
            val = jp[key]
            if isinstance(val, dict):
                val = json.dumps(val, default=str)
            detail_parts.append(f"{key}={val}")

    detail = " | ".join(detail_parts)
    prefix = f"[{ts}] {level}"
    if logger:
        prefix += f" [{logger}]"
    return f"{prefix}: {detail[:400]}"


def format_raw_entry(entry):
    """Format a docker-events / system log entry."""
    ts = entry.get("timestamp", "?")[:19]
    severity = entry.get("severity", "DEFAULT")
    text = entry.get("textPayload", "")
    if not text:
        jp = entry.get("jsonPayload", {})
        text = jp.get("MESSAGE", jp.get("message", ""))
        if not text and jp:
            text = json.dumps(jp, default=str)[:500]
    return f"[{ts}] {severity}: {text[:400]}"


def main():
    parser = argparse.ArgumentParser(description="Query TrackRat GCP logs")
    parser.add_argument("--env", choices=["staging", "production"], default="staging")
    parser.add_argument("--filter", dest="extra_filter", default="")
    parser.add_argument("--errors", action="store_true")
    parser.add_argument("--warnings", action="store_true")
    parser.add_argument("--search", default="")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", default="")
    parser.add_argument("--raw", action="store_true", help="Include Docker events (noisy)")
    args = parser.parse_args()

    _check_dependencies()
    token = get_credentials()

    # Discover instance
    instance_id, hostname, last_seen = discover_instance_id(token, args.env)
    if not instance_id:
        print(
            f"No {args.env} instance has logged in the last "
            f"{DISCOVERY_LOOKBACK_DAYS} days (no cos_system entry with a "
            f"{HOSTNAME_PREFIX[args.env]}* hostname). The instance is missing "
            "or stopped; this is not a query failure.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Instance: {hostname} ({instance_id}), newest host entry {last_seen}", file=sys.stderr)
    if is_stale(last_seen, datetime.now(timezone.utc)):
        print(
            f"⚠️  {hostname} has not logged for over {DISCOVERY_STALE_AFTER}; "
            "it may be stopped. Showing its last logs.",
            file=sys.stderr,
        )

    # Build filter
    parts = [f'resource.labels.instance_id="{instance_id}"']

    if not args.raw:
        # App logs only: cos_containers log with trackrat-api container
        parts.append(f'logName="projects/{PROJECT}/logs/cos_containers"')

    if args.errors:
        if args.raw:
            parts.append("severity>=ERROR")
        else:
            parts.append('jsonPayload.level="error"')
    elif args.warnings:
        if args.raw:
            parts.append("severity>=WARNING")
        else:
            parts.append('(jsonPayload.level="error" OR jsonPayload.level="warning")')

    if args.search:
        # Search across event and message fields
        parts.append(
            f'(jsonPayload.event=~"{args.search}" OR jsonPayload.message=~"{args.search}"'
            f' OR jsonPayload.MESSAGE=~"{args.search}")'
        )

    if args.extra_filter:
        parts.append(args.extra_filter)

    log_filter = " AND ".join(parts)
    entries = query_logs(token, log_filter, args.limit)

    formatter = format_raw_entry if args.raw else format_app_entry
    lines = [formatter(e) for e in entries]

    if args.output:
        with open(args.output, "w") as f:
            for line in lines:
                f.write(line + "\n")
        print(f"Wrote {len(entries)} entries to {args.output}", file=sys.stderr)
    else:
        print(f"--- {len(entries)} entries ---")
        for line in lines:
            print(line)


if __name__ == "__main__":
    main()
