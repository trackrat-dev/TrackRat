#!/bin/bash
#

# Function to validate APNS configuration
validate_apns_config() {
    echo "Validating APNS configuration..."
    
    # Check if P8 file exists
    if [ ! -f "certs/AuthKey_4WC3F645FR.p8" ]; then
        echo "❌ APNS P8 file not found: certs/AuthKey_4WC3F645FR.p8"
        return 1
    fi
    
    # Check if P8 file is readable and has content
    if [ ! -s "certs/AuthKey_4WC3F645FR.p8" ]; then
        echo "❌ APNS P8 file is empty: certs/AuthKey_4WC3F645FR.p8"
        return 1
    fi
    
    # Check if required environment variables are set
    if [ -z "$APNS_TEAM_ID" ] || [ -z "$APNS_KEY_ID" ] || [ -z "$APNS_AUTH_KEY" ]; then
        echo "❌ Missing APNS environment variables:"
        echo "   APNS_TEAM_ID: ${APNS_TEAM_ID:-'NOT SET'}"
        echo "   APNS_KEY_ID: ${APNS_KEY_ID:-'NOT SET'}"
        echo "   APNS_AUTH_KEY: ${APNS_AUTH_KEY:+'SET'}"
        return 1
    fi
    
    echo "✅ APNS configuration validated successfully"
    return 0
}

# Set APNS environment variables (without TRACKRAT_ prefix for compatibility with V1)
export APNS_TEAM_ID="D5RZZ55J9R"
export APNS_KEY_ID="4WC3F645FR"
export APNS_AUTH_KEY="$(cat certs/AuthKey_4WC3F645FR.p8)"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"

# Validate APNS configuration before starting
if ! validate_apns_config; then
    echo "⚠️  APNS configuration validation failed. Live Activities will not work."
    echo "   Continuing with backend startup..."
fi

# Run database migrations
poetry run alembic upgrade head

# Start the application (scheduler starts automatically)
#export TRACKRAT_LOG_LEVEL=DEBUG 
poetry run uvicorn trackrat.main:app --reload
