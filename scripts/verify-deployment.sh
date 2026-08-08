#!/bin/bash
# Shared health check and deployment verification script
# Used by both Terraform and Ocuroot deployment methods

set -e

SERVICE_URL=""
ENVIRONMENT="staging"
NO_WAIT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-wait) NO_WAIT=true; shift ;;
        *) if [[ -z "$SERVICE_URL" ]]; then SERVICE_URL="$1"; else ENVIRONMENT="$1"; fi; shift ;;
    esac
done

if [[ -z "$SERVICE_URL" ]]; then
    echo "❌ Error: SERVICE_URL is required"
    echo "Usage: $0 <SERVICE_URL> [ENVIRONMENT] [--no-wait]"
    exit 1
fi

echo "🔍 Verifying deployment at: $SERVICE_URL"
echo "   Environment: $ENVIRONMENT"
echo ""

# Wait for service to stabilize
WAIT_TIME=30
if [[ "$ENVIRONMENT" == "production" ]]; then
    WAIT_TIME=60
fi

if [[ "$NO_WAIT" == "true" ]]; then
    echo "⏩ Skipping stabilization wait (--no-wait)"
else
    echo "⏳ Waiting ${WAIT_TIME} seconds for service to stabilize..."
    sleep $WAIT_TIME
fi

# Health Check with retries
HEALTH_URL="${SERVICE_URL}/health"
MAX_RETRIES=5
if [[ "$ENVIRONMENT" == "production" ]]; then
    MAX_RETRIES=10
fi

echo ""
echo "🏥 Running health checks..."
echo "   Endpoint: $HEALTH_URL"
echo "   Max retries: $MAX_RETRIES"
echo ""

for i in $(seq 1 $MAX_RETRIES); do
    echo "Health check attempt $i/$MAX_RETRIES..."

    if curl -f -s "$HEALTH_URL" > /tmp/health-response.json 2>/dev/null; then
        echo "✅ Health check passed!"
        echo ""
        echo "Response:"
        cat /tmp/health-response.json | jq '.' 2>/dev/null || cat /tmp/health-response.json
        HEALTH_PASSED=true
        break
    else
        echo "❌ Health check failed"
        if [ $i -eq $MAX_RETRIES ]; then
            echo ""
            echo "❌ All health checks failed after $MAX_RETRIES attempts"
            exit 1
        fi
        echo "   Retrying in 30 seconds..."
        sleep 30
    fi
done

# GTFS calendar window checks (lapsed, and not yet started)
#
# /health reports both as a `warning` and still returns HTTP 200, so the curl
# above passes while a source serves an expired timetable — or no timetable at
# all. Asserted here rather than left to an operator reading JSON, so the
# staging validation path actually gates them.
#
# A lapse is the dominant silent failure for a schedule-first source (PATCO,
# SEPTA Metro): the feed re-downloads nightly and looks fresh, departures keep
# appearing, and every one of them is fabricated from a dead calendar
# (issue #1634).
#
# A not-yet-active bundle is the mirror image and fails the opposite way — the
# source goes silent rather than serving fiction. An agency publishes next
# week's bundle early, the refresh job adopts it, and nothing is served until
# its start date. SEPTA Regional Rail served zero departures for a day and a
# half this way while /health reported healthy (issue #1770).
#
# Both fields are absent on deployments predating them and read as empty —
# unknown is neither lapsed nor pending, matching GTFSFeedStatus.
echo ""
echo "📅 Checking GTFS feed calendars..."

if ! GTFS_CALENDAR_STATE=$(python3 -c '
import json

with open("/tmp/health-response.json") as fh:
    health = json.load(fh)

gtfs = health.get("checks", {}).get("gtfs_feeds") or {}
print(",".join(gtfs.get("lapsed_sources") or []))
print(",".join(gtfs.get("not_yet_active_sources") or []))
' 2>/dev/null); then
    echo "   ❌ Could not parse the health response for GTFS feed status"
    exit 1
fi

LAPSED_SOURCES=$(sed -n 1p <<< "$GTFS_CALENDAR_STATE")
NOT_YET_ACTIVE_SOURCES=$(sed -n 2p <<< "$GTFS_CALENDAR_STATE")

if [[ -n "$LAPSED_SOURCES" ]]; then
    echo "   ❌ GTFS bundle calendar has lapsed: $LAPSED_SOURCES"
    echo "      These sources are still serving departures, generated from a"
    echo "      timetable whose service period has already ended. Check the daily"
    echo "      gtfs_feed_refresh job and the upstream feed URL."
    exit 1
fi

if [[ -n "$NOT_YET_ACTIVE_SOURCES" ]]; then
    echo "   ❌ GTFS bundle has not taken effect yet: $NOT_YET_ACTIVE_SOURCES"
    echo "      The stored bundle's calendar starts in the future, so these"
    echo "      sources have no schedule for today and serve nothing. The agency"
    echo "      published the next bundle early and it was adopted over the one"
    echo "      still in force. Check feed_start_date in /health."
    exit 1
fi

echo "   ✅ No lapsed or not-yet-active GTFS bundles"

# API Endpoint Tests
echo ""
echo "🧪 Testing API endpoints..."

# Test trains API
TRAINS_URL="${SERVICE_URL}/api/v2/trains/departures?from=NY&limit=5"
echo "   Testing: $TRAINS_URL"

if curl -f -s "$TRAINS_URL" > /dev/null 2>/dev/null; then
    echo "   ✅ Trains API is responding"
else
    echo "   ⚠️  Trains API check failed (may be expected if no data)"
fi

# Test scheduler status (if applicable)
SCHEDULER_URL="${SERVICE_URL}/scheduler/status"
echo "   Testing: $SCHEDULER_URL"

if curl -f -s "$SCHEDULER_URL" > /dev/null 2>/dev/null; then
    echo "   ✅ Scheduler status is responding"
else
    echo "   ⚠️  Scheduler status check failed"
fi

# Test metrics endpoint
METRICS_URL="${SERVICE_URL}/metrics"
echo "   Testing: $METRICS_URL"

if curl -f -s "$METRICS_URL" > /dev/null 2>/dev/null; then
    echo "   ✅ Metrics endpoint is responding"
else
    echo "   ⚠️  Metrics endpoint check failed"
fi

echo ""
echo "✅ Deployment verification complete!"
echo "   Service URL: $SERVICE_URL"
echo "   All critical checks passed"

exit 0
