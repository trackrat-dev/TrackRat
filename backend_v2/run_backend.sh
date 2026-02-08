#!/bin/bash
#
# TrackRat V2 Backend Startup Script
# Starts PostgreSQL (if needed) and the TrackRat backend server

# Function to check PostgreSQL availability
check_postgresql() {
    echo "🔍 Checking PostgreSQL connection..."
    
    # Try to connect to PostgreSQL using the configured database URL
    if [ -n "$TRACKRAT_DATABASE_URL" ]; then
        # Extract connection details from the URL for testing
        # This is a simple check - the app will do full validation
        if poetry run python -c "
import asyncio
import asyncpg
import os
from urllib.parse import urlparse

async def test_connection():
    try:
        # Parse the database URL
        db_url = os.getenv('TRACKRAT_DATABASE_URL', '')
        if not db_url.startswith('postgresql'):
            print('❌ TRACKRAT_DATABASE_URL must be a PostgreSQL URL')
            exit(1)
            
        # Convert asyncpg URL to basic postgres URL for connection test
        url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(url)
        
        # Test connection
        conn = await asyncpg.connect(
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5433,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/') if parsed.path else 'postgres'
        )
        await conn.execute('SELECT 1')
        await conn.close()
        print('✅ PostgreSQL connection successful')
        
    except Exception as e:
        print(f'❌ PostgreSQL connection failed: {e}')
        exit(1)

asyncio.run(test_connection())
" 2>/dev/null; then
            return 0
        else
            return 1
        fi
    else
        echo "❌ TRACKRAT_DATABASE_URL not set"
        return 1
    fi
}

# Function to start local PostgreSQL (if needed)
start_local_postgresql() {
    echo "🐘 Starting local PostgreSQL..."
    
    # Check if Docker is available
    if ! command -v docker >/dev/null 2>&1; then
        echo "❌ Docker not found. Please install Docker or set up PostgreSQL manually."
        exit 1
    fi
    
    # Check if PostgreSQL container is already running
    if docker ps --format "table {{.Names}}" | grep -q "trackrat-postgres"; then
        echo "✅ PostgreSQL container already running"
        return 0
    fi
    
    # Remove any existing stopped container
    if docker ps -a --format "table {{.Names}}" | grep -q "trackrat-postgres"; then
        echo "🗑️  Removing existing PostgreSQL container..."
        docker rm trackrat-postgres >/dev/null 2>&1
    fi
    
    # Start PostgreSQL container with default postgres user on port 5433 to avoid conflicts
    echo "🚀 Starting PostgreSQL container on port 5433..."
    docker run -d \
        --name trackrat-postgres \
        -e POSTGRES_DB=trackratdb \
        -e POSTGRES_PASSWORD=password \
        -p 5433:5432 \
        postgres:15
    
    # Wait for PostgreSQL to be ready
    echo "⏳ Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec trackrat-postgres pg_isready -U postgres -d trackratdb >/dev/null 2>&1; then
            echo "✅ PostgreSQL is ready"
            
            # Create the trackratuser if it doesn't exist
            echo "👤 Creating trackratuser..."
            docker exec trackrat-postgres psql -U postgres -d trackratdb -c "
                DO \$\$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'trackratuser') THEN
                        CREATE USER trackratuser WITH PASSWORD 'password';
                        GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;
                        GRANT ALL PRIVILEGES ON SCHEMA public TO trackratuser;
                        ALTER USER trackratuser CREATEDB;
                    END IF;
                END
                \$\$;
            " >/dev/null 2>&1
            
            # Verify the user can connect
            if docker exec trackrat-postgres psql -U trackratuser -d trackratdb -c "SELECT 1;" >/dev/null 2>&1; then
                echo "✅ Database user created and verified"
                return 0
            else
                echo "❌ User verification failed"
                return 1
            fi
        fi
        echo -n "."
        sleep 1
    done
    
    echo "❌ PostgreSQL failed to start within 30 seconds"
    exit 1
}

# Function to validate APNS configuration
validate_apns_config() {
    echo "🔍 Validating APNS configuration..."
    local errors=0
    
    # Check if APNS_AUTH_KEY_PATH is set and file exists
    if [ -n "$APNS_AUTH_KEY_PATH" ] && [ -f "$APNS_AUTH_KEY_PATH" ]; then
        # Check if P8 file has content
        if [ ! -s "$APNS_AUTH_KEY_PATH" ]; then
            echo "❌ APNS P8 file is empty: $APNS_AUTH_KEY_PATH"
            errors=$((errors + 1))
        fi

        # Check if P8 file has valid PEM format
        if ! head -1 "$APNS_AUTH_KEY_PATH" | grep -q "BEGIN PRIVATE KEY"; then
            echo "❌ APNS P8 file does not start with '-----BEGIN PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi

        if ! tail -1 "$APNS_AUTH_KEY_PATH" | grep -q "END PRIVATE KEY"; then
            echo "❌ APNS P8 file does not end with '-----END PRIVATE KEY-----'"
            errors=$((errors + 1))
        fi

        # Check file size (should be around 250-300 bytes for P-256 key)
        file_size=$(wc -c < "$APNS_AUTH_KEY_PATH")
        if [ "$file_size" -lt 200 ] || [ "$file_size" -gt 400 ]; then
            echo "⚠️  APNS P8 file size is unusual: ${file_size} bytes (expected 200-400)"
        fi
    elif [ -z "$APNS_AUTH_KEY" ]; then
        echo "❌ Neither APNS_AUTH_KEY_PATH file nor APNS_AUTH_KEY env var found"
        errors=$((errors + 1))
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
    if [ -n "$APNS_AUTH_KEY_PATH" ] && [ -f "$APNS_AUTH_KEY_PATH" ] && command -v poetry >/dev/null 2>&1; then
        echo "🔧 Testing P8 certificate loading..."
        if ! poetry run python -c "
import os, sys
from cryptography.hazmat.primitives import serialization
try:
    with open(os.environ['APNS_AUTH_KEY_PATH'], 'rb') as f:
        serialization.load_pem_private_key(f.read(), password=None)
    print('✅ P8 certificate loads successfully')
except Exception as e:
    print(f'❌ P8 certificate failed to load: {e}')
    sys.exit(1)
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
        if [ -n "$APNS_AUTH_KEY_PATH" ] && [ -f "$APNS_AUTH_KEY_PATH" ]; then
            echo "   P8 File: $APNS_AUTH_KEY_PATH ($(wc -c < "$APNS_AUTH_KEY_PATH") bytes)"
        fi
        return 0
    else
        echo "❌ APNS configuration validation failed with $errors error(s)"
        return 1
    fi
}

echo "🚀 TrackRat V2 Backend Startup"
echo "================================"

# Set database URL for local development (if not already set)
if [ -z "$TRACKRAT_DATABASE_URL" ]; then
    echo "📝 Setting local PostgreSQL database URL..."
    export TRACKRAT_DATABASE_URL="postgresql+asyncpg://trackratuser:password@127.0.0.1:5433/trackratdb"
fi

# Check PostgreSQL connection, start local container if needed
if ! check_postgresql; then
    echo "🐘 PostgreSQL not available, attempting to start local container..."
    start_local_postgresql
    
    # Recheck connection after starting container
    if ! check_postgresql; then
        echo "❌ FATAL: Could not establish PostgreSQL connection"
        exit 1
    fi
fi

# Set APNS environment variables (without TRACKRAT_ prefix for compatibility with V1)
# These must be configured in your environment or .env file:
#   APNS_TEAM_ID, APNS_KEY_ID, APNS_AUTH_KEY_PATH (or APNS_AUTH_KEY),
#   APNS_BUNDLE_ID, APNS_ENVIRONMENT
export APNS_ENVIRONMENT="${APNS_ENVIRONMENT:-dev}"  # Default to sandbox for local development

# Validate APNS configuration before starting
if ! validate_apns_config; then
    echo "FATAL: ⚠️ APNS configuration validation failed. Live Activities will not work."
    exit 1
fi

echo "✅ All prerequisites validated successfully!"
echo ""
echo "🔗 Database: $TRACKRAT_DATABASE_URL"
echo "📱 APNS Environment: $APNS_ENVIRONMENT"
echo ""

# Start the application (database migrations and scheduler start automatically)
export TRACKRAT_LOG_LEVEL=INFO
echo "🎯 Starting TrackRat V2 Backend..."
poetry run uvicorn trackrat.main:app --reload
