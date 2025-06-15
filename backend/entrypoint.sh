#!/bin/bash
set -e

echo "=== TrackCast Container Startup ==="

# Function to wait for database to be ready
wait_for_database() {
    echo "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if trackcast --version >/dev/null 2>&1; then
            echo "TrackCast CLI is available"
            # Try to connect to database
            if python -c "
from trackcast.db.database import get_engine
from sqlalchemy import text
try:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('Database connection successful')
    exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" 2>/dev/null; then
                echo "✅ Database is ready!"
                return 0
            fi
        fi
        
        echo "⏳ Database not ready (attempt $attempt/$max_attempts), waiting 2 seconds..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "❌ Database failed to become ready after $max_attempts attempts"
    exit 1
}

# Function to run database initialization
initialize_database() {
    echo "=== Database Initialization ==="
    
    # Run database initialization (creates tables if they don't exist)
    echo "Running database schema initialization..."
    if trackcast init-db; then
        echo "✅ Database schema initialization completed"
    else
        echo "❌ Database schema initialization failed"
        exit 1
    fi
    
    # Run database migrations (applies any pending schema changes)
    echo "Running database migrations..."
    if trackcast update-schema; then
        echo "✅ Database migrations completed"
    else
        echo "❌ Database migrations failed"
        exit 1
    fi
}

# Function to validate the setup
validate_setup() {
    echo "=== Validation ==="
    
    # Check if critical tables exist
    echo "Validating database tables..."
    if python -c "
from trackcast.db.database import get_engine
from sqlalchemy import text, inspect
try:
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required_tables = ['trains', 'train_stops', 'model_data', 'prediction_data']
    missing_tables = [t for t in required_tables if t not in tables]
    if missing_tables:
        print(f'Missing required tables: {missing_tables}')
        exit(1)
    else:
        print(f'All required tables exist: {required_tables}')
        exit(0)
except Exception as e:
    print(f'Table validation failed: {e}')
    exit(1)
"; then
        echo "✅ Database validation passed"
    else
        echo "❌ Database validation failed"
        exit 1
    fi
}

# Main execution
main() {
    echo "Starting TrackCast with automatic database initialization..."
    echo "Environment: ${TRACKCAST_ENV:-dev}"
    echo "Database URL: ${DATABASE_URL:-not set}"
    
    # Wait for database to be available
    wait_for_database
    
    # Initialize database and run migrations
    initialize_database
    
    # Validate setup
    validate_setup
    
    echo "=== Starting Application ==="
    echo "Database initialization complete. Starting API server..."
    
    # Execute the main application command
    exec "$@"
}

# Run main function
main "$@"