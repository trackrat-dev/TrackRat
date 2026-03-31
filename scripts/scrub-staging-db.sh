#!/usr/bin/env bash
# scrub-staging-db.sh - Remove production user data from a cloned staging database
#
# After cloning a production disk to staging, this script removes device tokens,
# Live Activity tokens, and other user-specific data that would cause staging to
# send push notifications to real production users.
#
# Usage:
#   ./scripts/scrub-staging-db.sh [options]
#
# Options:
#   --db-host HOST       PostgreSQL host (default: localhost)
#   --db-port PORT       PostgreSQL port (default: 5432)
#   --db-user USER       PostgreSQL user (default: trackrat)
#   --db-name NAME       Database name (default: trackrat)
#   --db-password PASS   Database password (or set PGPASSWORD env var)
#   --docker             Run via docker exec against trackrat-postgres container
#   --dry-run            Show what would be scrubbed without executing
#   --help               Show this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Defaults
DB_HOST="localhost"
DB_PORT="5432"
DB_USER="trackrat"
DB_NAME="trackrat"
DB_PASSWORD=""
USE_DOCKER=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-host)    DB_HOST="$2"; shift 2 ;;
    --db-port)    DB_PORT="$2"; shift 2 ;;
    --db-user)    DB_USER="$2"; shift 2 ;;
    --db-name)    DB_NAME="$2"; shift 2 ;;
    --db-password) DB_PASSWORD="$2"; shift 2 ;;
    --docker)     USE_DOCKER=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --help|-h)
      head -20 "$0" | grep '^#' | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

run_sql() {
  local sql="$1"
  if $USE_DOCKER; then
    docker exec trackrat-postgres psql -U "$DB_USER" -d "$DB_NAME" -c "$sql"
  else
    PGPASSWORD="${DB_PASSWORD:-${PGPASSWORD:-}}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$sql"
  fi
}

# Tables to scrub and why:
#
# device_tokens (CASCADE → route_alert_subscriptions, route_preferences)
#   Contains production APNS tokens. If not scrubbed, staging sends real push
#   notifications to production users' phones within minutes of startup.
#
# live_activity_tokens
#   Contains production APNS Live Activity push tokens. Staging's scheduler
#   would send Live Activity updates to real users every minute, potentially
#   showing wrong data or ending their active Live Activities.
#
# cached_api_responses
#   Stale production caches could mask bugs in staging cache generation.
#
# scheduler_task_runs
#   Contains production instance hostnames and last_successful_run timestamps.
#   If not scrubbed, staging's freshness-check logic may skip scheduled runs
#   for up to their full interval (thinking tasks already ran recently).

SCRUB_SQL="
-- Remove all device tokens and cascade to route_alert_subscriptions + route_preferences
TRUNCATE TABLE device_tokens CASCADE;

-- Remove all Live Activity tokens
TRUNCATE TABLE live_activity_tokens;

-- Clear stale production caches
TRUNCATE TABLE cached_api_responses;

-- Reset scheduler state so staging runs collectors immediately
TRUNCATE TABLE scheduler_task_runs;
"

COUNT_SQL="
SELECT 'device_tokens' AS table_name, COUNT(*) AS row_count FROM device_tokens
UNION ALL
SELECT 'live_activity_tokens', COUNT(*) FROM live_activity_tokens
UNION ALL
SELECT 'cached_api_responses', COUNT(*) FROM cached_api_responses
UNION ALL
SELECT 'scheduler_task_runs', COUNT(*) FROM scheduler_task_runs
UNION ALL
SELECT 'route_alert_subscriptions', COUNT(*) FROM route_alert_subscriptions
UNION ALL
SELECT 'route_preferences', COUNT(*) FROM route_preferences;
"

echo "=== Staging Database Scrub ==="

if $DRY_RUN; then
  echo "[DRY RUN] Would scrub the following tables:"
  echo ""
  run_sql "$COUNT_SQL"
  echo ""
  echo "[DRY RUN] No changes made."
  exit 0
fi

echo "Row counts before scrub:"
run_sql "$COUNT_SQL"

echo ""
echo "Scrubbing production user data..."
run_sql "$SCRUB_SQL"

echo ""
echo "Row counts after scrub:"
run_sql "$COUNT_SQL"

echo ""
echo "Staging database scrubbed successfully."
