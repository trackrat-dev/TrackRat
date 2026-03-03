#!/usr/bin/env bash
# server-usage.sh - Quick server usage report
#
# Queries GCP load balancer logs and backend endpoints to show:
#   - API traffic breakdown by endpoint
#   - Route searches and train follows
#   - Client breakdown (iOS versions, bots, etc.)
#   - Latency by endpoint
#   - Scheduler task health
#   - Errors and warnings
#
# Usage: ./scripts/server-usage.sh [--env production|staging] [--hours N] [--json] [--output FILE]
#   --env       defaults to production
#   --hours     time window (default: 1)
#   --json      output as JSON
#   --output    write to file (disables color)
#
# Requires GCP service account credentials (same setup as gcp-logs.py).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-install Python dependencies if missing
python3 -c "import google.oauth2.service_account" 2>/dev/null || {
    echo "Installing GCP dependencies..."
    pip install google-cloud-logging 2>&1 | tail -3
    pip install cffi cryptography --force-reinstall --target=/tmp/pylibs 2>&1 | tail -3
}

PYTHONPATH="${PYTHONPATH:-}":/tmp/pylibs
export PYTHONPATH

exec python3 "$SCRIPT_DIR/server-usage.py" "$@"
