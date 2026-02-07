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

SA_KEY_PATH = "/root/.config/gcloud/service-account.json"
PROJECT = "trackrat-v2"
# Stable prefix — GCP MIG appends random suffixes (e.g. trackrat-staging-s565)
HOSTNAME_PREFIX = {
    "staging": "trackrat-staging-",
    "production": "trackrat-production-",
}


def get_credentials():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import requests

    with open(SA_KEY_PATH, "r") as f:
        sa_info = json.loads(f.read(), strict=False)

    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/logging.read"]
    )
    credentials.refresh(Request(session=requests.Session()))
    return credentials.token


def discover_instance_id(token, env):
    """Find the GCE instance_id for an environment via hostname prefix match."""
    import requests

    prefix = HOSTNAME_PREFIX[env]
    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": f'jsonPayload._HOSTNAME=~"^{prefix}"',
        "orderBy": "timestamp desc",
        "pageSize": 1,
    }
    resp = requests.post(url, json=body, headers=headers)
    entries = resp.json().get("entries", [])
    if entries:
        e = entries[0]
        hostname = e.get("jsonPayload", {}).get("_HOSTNAME", "")
        instance_id = e.get("resource", {}).get("labels", {}).get("instance_id", "")
        if hostname and instance_id:
            return instance_id, hostname
    return None, None


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
    for key in ("task", "duration_ms", "route", "train_id", "error", "params"):
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

    token = get_credentials()

    # Discover instance
    instance_id, hostname = discover_instance_id(token, args.env)
    if not instance_id:
        print(f"Could not find a running {args.env} instance.", file=sys.stderr)
        sys.exit(1)
    print(f"Instance: {hostname} ({instance_id})", file=sys.stderr)

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
