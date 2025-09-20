#!/bin/bash
#
# TrackRat V2 Test Runner with Database
# Starts a test PostgreSQL container and runs all code quality checks and tests
#

set -x
set -e  # Exit on any error

# Test database configuration
TEST_DB_PORT=5434
TEST_DB_NAME="trackratdb_test"
TEST_DB_USER="trackratuser"
TEST_DB_PASSWORD="password"
TEST_CONTAINER_NAME="trackrat-test-postgres"

echo "🧪 TrackRat V2 Test Runner"
echo "=========================="

# Function to check if test database is available
check_test_database() {
    echo "🔍 Checking test database connection..."
    
    if poetry run python -c "
import asyncio
import asyncpg

async def test_connection():
    try:
        conn = await asyncpg.connect(
            host='127.0.0.1',
            port=$TEST_DB_PORT,
            user='$TEST_DB_USER',
            password='$TEST_DB_PASSWORD',
            database='$TEST_DB_NAME'
        )
        await conn.execute('SELECT 1')
        await conn.close()
        print('✅ Test database connection successful')
        
    except Exception as e:
        print(f'❌ Test database connection failed: {e}')
        exit(1)

asyncio.run(test_connection())
" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start test PostgreSQL container
start_test_database() {
    echo "🐘 Starting test PostgreSQL container..."
    
    # Check if Docker is available
    if ! command -v docker >/dev/null 2>&1; then
        echo "❌ Docker not found. Please install Docker."
        exit 1
    fi
    
    # Stop and remove existing test container if it exists
    if docker ps -a --format "table {{.Names}}" | grep -q "$TEST_CONTAINER_NAME"; then
        echo "🗑️  Removing existing test container..."
        docker stop $TEST_CONTAINER_NAME >/dev/null 2>&1 || true
        docker rm $TEST_CONTAINER_NAME >/dev/null 2>&1 || true
    fi
    
    # Start fresh test PostgreSQL container
    echo "🚀 Starting test PostgreSQL container on port $TEST_DB_PORT..."
    docker run -d \
        --name $TEST_CONTAINER_NAME \
        -e POSTGRES_DB=$TEST_DB_NAME \
        -e POSTGRES_USER=$TEST_DB_USER \
        -e POSTGRES_PASSWORD=$TEST_DB_PASSWORD \
        -p $TEST_DB_PORT:5432 \
        postgres:15
    
    # Wait for PostgreSQL to be ready
    echo "⏳ Waiting for test database to be ready..."
    for i in {1..30}; do
        if docker exec $TEST_CONTAINER_NAME pg_isready -U $TEST_DB_USER -d $TEST_DB_NAME >/dev/null 2>&1; then
            echo "✅ Test database is ready"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    echo "❌ Test database failed to start within 30 seconds"
    exit 1
}

# Function to cleanup test database
cleanup_test_database() {
    if [ "$CLEANUP_DB" = "true" ]; then
        echo "🧹 Cleaning up test database..."
        docker stop $TEST_CONTAINER_NAME >/dev/null 2>&1 || true
        docker rm $TEST_CONTAINER_NAME >/dev/null 2>&1 || true
        echo "✅ Test database cleaned up"
    fi
}

# Set up cleanup trap
CLEANUP_DB=false
trap cleanup_test_database EXIT

# Check if test database is available, start if needed
if ! check_test_database; then
    echo "🐘 Test database not available, starting container..."
    start_test_database
    CLEANUP_DB=true
    
    # Verify connection after starting
    if ! check_test_database; then
        echo "❌ FATAL: Could not establish test database connection"
        exit 1
    fi
fi

# Set database URL environment variable (used by the app)
export TRACKRAT_DATABASE_URL="postgresql+asyncpg://$TEST_DB_USER:$TEST_DB_PASSWORD@127.0.0.1:$TEST_DB_PORT/$TEST_DB_NAME"

# Also set the test-specific one for conftest.py
export TRACKRAT_TEST_DATABASE_URL="$TRACKRAT_DATABASE_URL"

echo "✅ Test database ready!"
echo "🔗 Test Database: $TRACKRAT_DATABASE_URL"
echo ""

# Run code quality checks first (same as run_tests.sh)
echo "🔍 Running code quality checks..."
echo "================================="
echo ""

echo "📝 Checking code formatting with black..."
poetry run black src/ tests/
poetry run black src/ tests/ --check

echo ""
echo "🔍 Running type checking with mypy..."
poetry run mypy src/

echo ""
echo "⚡ Running fast linting with ruff..."
poetry run ruff check src/ --fix

echo ""
echo "✅ All code quality checks passed!"
echo ""

# Ensure Sentry is disabled during tests
export SENTRY_DSN=""

# Run the tests
echo "🎯 Running tests..."
echo "=================="
poetry run pytest -v "$@"

echo ""
echo "🎉 All checks and tests completed successfully!"
