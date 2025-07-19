#!/bin/sh
#
# Docker entrypoint script for TrackRat V2 Backend
# Validates APNS configuration before starting the application
#

set -e

# Function to validate APNS configuration
validate_apns_config() {
    echo "🔍 Validating APNS configuration..."
    local errors=0
    
    # Check if P8 file exists (using APNS_AUTH_KEY_PATH if set, or default)
    P8_PATH="${APNS_AUTH_KEY_PATH:-certs/AuthKey_4WC3F645FR.p8}"
    
    if [ ! -f "$P8_PATH" ]; then
        echo "❌ APNS P8 file not found: $P8_PATH"
        errors=$((errors + 1))
    fi
    
    # Check if P8 file has content
    if [ ! -s "$P8_PATH" ]; then
        echo "❌ APNS P8 file is empty: $P8_PATH"
        errors=$((errors + 1))
    fi
    
    # Check if P8 file has valid PEM format
    if [ -f "$P8_PATH" ]; then
        if ! head -1 "$P8_PATH" | grep -q "BEGIN PRIVATE KEY"; then
            echo "❌ APNS P8 file does not start with '-----BEGIN PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi
        
        if ! tail -1 "$P8_PATH" | grep -q "END PRIVATE KEY"; then
            echo "❌ APNS P8 file does not end with '-----END PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi
        
        # Check file size (should be around 250-300 bytes for P-256 key)
        file_size=$(wc -c < "$P8_PATH")
        if [ "$file_size" -lt 200 ] || [ "$file_size" -gt 400 ]; then
            echo "⚠️  APNS P8 file size is unusual: ${file_size} bytes (expected 200-400)"
        fi
    fi
    
    # Check if required environment variables are set
    if [ -z "$APNS_TEAM_ID" ]; then
        echo "❌ APNS_TEAM_ID is not set"
        errors=$((errors + 1))
    elif [ ${#APNS_TEAM_ID} -ne 10 ]; then
        echo "❌ APNS_TEAM_ID should be 10 characters, got: ${#APNS_TEAM_ID} characters"
        errors=$((errors + 1))
    fi
    
    if [ -z "$APNS_KEY_ID" ]; then
        echo "❌ APNS_KEY_ID is not set"
        errors=$((errors + 1))
    elif [ ${#APNS_KEY_ID} -ne 10 ]; then
        echo "❌ APNS_KEY_ID should be 10 characters, got: ${#APNS_KEY_ID} characters"
        errors=$((errors + 1))
    fi
    
    if [ -z "$APNS_BUNDLE_ID" ]; then
        echo "❌ APNS_BUNDLE_ID is not set"
        errors=$((errors + 1))
    elif ! echo "$APNS_BUNDLE_ID" | grep -q "^[a-zA-Z0-9.-]*$"; then
        echo "❌ APNS_BUNDLE_ID contains invalid characters: $APNS_BUNDLE_ID"
        errors=$((errors + 1))
    fi
    
    if [ -z "$APNS_ENVIRONMENT" ]; then
        echo "❌ APNS_ENVIRONMENT is not set"
        errors=$((errors + 1))
    elif [ "$APNS_ENVIRONMENT" != "dev" ] && [ "$APNS_ENVIRONMENT" != "prod" ]; then
        echo "❌ APNS_ENVIRONMENT must be 'dev' or 'prod', got: $APNS_ENVIRONMENT"
        errors=$((errors + 1))
    fi
    
    # Test loading the P8 file with Python cryptography library
    if [ -f "$P8_PATH" ]; then
        echo "🔧 Testing P8 certificate loading..."
        if ! python -c "
from cryptography.hazmat.primitives import serialization
try:
    with open('$P8_PATH', 'rb') as f:
        serialization.load_pem_private_key(f.read(), password=None)
    print('✅ P8 certificate loads successfully')
except Exception as e:
    print(f'❌ P8 certificate failed to load: {e}')
    exit(1)
" 2>/dev/null; then
            errors=$((errors + 1))
        fi
    fi
    
    # Summary
    if [ $errors -eq 0 ]; then
        echo "✅ APNS configuration validation passed"
        echo "   Team ID: $APNS_TEAM_ID"
        echo "   Key ID: $APNS_KEY_ID"
        echo "   Bundle ID: $APNS_BUNDLE_ID"
        echo "   Environment: $APNS_ENVIRONMENT"
        if [ -f "$P8_PATH" ]; then
            echo "   P8 File: $P8_PATH ($(wc -c < "$P8_PATH") bytes)"
        fi
        return 0
    else
        echo "❌ APNS configuration validation failed with $errors error(s)"
        echo ""
        echo "🚫 FATAL: Container will exit due to invalid APNS configuration"
        echo "   Live Activities require valid APNS credentials to function."
        echo "   Please ensure all APNS environment variables are set and the P8 certificate is valid."
        echo ""
        echo "📋 Required environment variables:"
        echo "   - APNS_TEAM_ID (10 characters)"
        echo "   - APNS_KEY_ID (10 characters)" 
        echo "   - APNS_BUNDLE_ID (iOS app bundle identifier)"
        echo "   - APNS_ENVIRONMENT (dev or prod)"
        echo ""
        echo "📋 Required file:"
        echo "   - Valid APNS P8 certificate at: $P8_PATH"
        echo "     OR set APNS_AUTH_KEY environment variable with P8 content"
        return 1
    fi
}

echo "🚀 Starting TrackRat V2 Backend..."
echo "📋 Environment: ${TRACKRAT_ENVIRONMENT:-development}"

# Validate APNS configuration before proceeding
if ! validate_apns_config; then
    exit 1
fi

echo ""
echo "🔧 Running database migrations..."
alembic upgrade head

echo ""
echo "🌟 Starting application server..."
exec uvicorn trackrat.main:app --host 0.0.0.0 --port 8000