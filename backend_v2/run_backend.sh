#!/bin/bash
#

# Function to validate APNS configuration
validate_apns_config() {
    echo "🔍 Validating APNS configuration..."
    local errors=0
    
    # Check if P8 file exists
    if [ ! -f "certs/AuthKey_4WC3F645FR.p8" ]; then
        echo "❌ APNS P8 file not found: certs/AuthKey_4WC3F645FR.p8"
        errors=$((errors + 1))
    fi
    
    # Check if P8 file has content
    if [ ! -s "certs/AuthKey_4WC3F645FR.p8" ]; then
        echo "❌ APNS P8 file is empty: certs/AuthKey_4WC3F645FR.p8"
        errors=$((errors + 1))
    fi
    
    # Check if P8 file has valid PEM format
    if [ -f "certs/AuthKey_4WC3F645FR.p8" ]; then
        if ! head -1 "certs/AuthKey_4WC3F645FR.p8" | grep -q "BEGIN PRIVATE KEY"; then
            echo "❌ APNS P8 file does not start with '-----BEGIN PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi
        
        if ! tail -1 "certs/AuthKey_4WC3F645FR.p8" | grep -q "END PRIVATE KEY"; then
            echo "❌ APNS P8 file does not end with '-----END PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi
        
        # Check file size (should be around 250-300 bytes for P-256 key)
        file_size=$(wc -c < "certs/AuthKey_4WC3F645FR.p8")
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
    if [ -f "certs/AuthKey_4WC3F645FR.p8" ] && command -v poetry >/dev/null 2>&1; then
        echo "🔧 Testing P8 certificate loading..."
        if ! poetry run python -c "
from cryptography.hazmat.primitives import serialization
try:
    with open('certs/AuthKey_4WC3F645FR.p8', 'rb') as f:
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
        if [ -f "certs/AuthKey_4WC3F645FR.p8" ]; then
            echo "   P8 File: certs/AuthKey_4WC3F645FR.p8 ($(wc -c < "certs/AuthKey_4WC3F645FR.p8") bytes)"
        fi
        return 0
    else
        echo "❌ APNS configuration validation failed with $errors error(s)"
        return 1
    fi
}

# Set APNS environment variables (without TRACKRAT_ prefix for compatibility with V1)
export APNS_TEAM_ID="D5RZZ55J9R"
export APNS_KEY_ID="4WC3F645FR"
export APNS_AUTH_KEY="$(cat certs/AuthKey_4WC3F645FR.p8)"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"
export APNS_ENVIRONMENT="dev"  # Use sandbox for local development

# Validate APNS configuration before starting
if ! validate_apns_config; then
    echo "FATAL: ⚠️ APNS configuration validation failed. Live Activities will not work."
    exit 1
fi

# Run database migrations
poetry run alembic upgrade head

# Start the application (scheduler starts automatically)
#export TRACKRAT_LOG_LEVEL=DEBUG 
poetry run uvicorn trackrat.main:app --reload
