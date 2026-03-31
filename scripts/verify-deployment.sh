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
