#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== TrackCast Container Startup ==="
echo "Timestamp: $(date)"
echo "Script PID: $$"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to log errors
log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

# Function to log success
log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"
}

# Function to log warnings
log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Function to wait for database to be ready
wait_for_database() {
    log "Starting database connectivity check..."
    local max_attempts=30
    local attempt=1
    local wait_seconds=2
    
    # First check if TrackCast CLI is available
    if ! command -v trackcast &> /dev/null; then
        log_error "TrackCast CLI is not installed or not in PATH"
        exit 1
    fi
    
    log "TrackCast CLI version: $(trackcast --version 2>&1 || echo 'Unable to get version')"
    
    while [ $attempt -le $max_attempts ]; do
        log "Database connection attempt $attempt/$max_attempts..."
        
        # Create a temporary Python script for better error handling
        TEMP_SCRIPT=$(mktemp)
        cat > "$TEMP_SCRIPT" << 'EOF'
import sys
import os
import traceback

# Log environment for debugging
print(f"Python version: {sys.version}")
print(f"DATABASE_URL env var exists: {'DATABASE_URL' in os.environ}")
print(f"TRACKCAST_ENV: {os.environ.get('TRACKCAST_ENV', 'not set')}")

try:
    from trackcast.db.connection import engine, DATABASE_URL
    from sqlalchemy import text
    
    # Log the connection string (with password masked)
    if DATABASE_URL:
        # Mask password in connection string
        import re
        masked_url = re.sub(r':([^:@]+)@', ':****@', DATABASE_URL)
        print(f"Attempting connection to: {masked_url}")
    
    # Attempt connection
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1')).scalar()
        if result == 1:
            print("Database connection test successful - SELECT 1 returned 1")
            sys.exit(0)
        else:
            print(f"Database connection test failed - SELECT 1 returned: {result}")
            sys.exit(1)
            
except ImportError as e:
    print(f"Import error: {e}")
    print("Failed to import TrackCast modules. Ensure TrackCast is installed.")
    traceback.print_exc()
    sys.exit(1)
    
except Exception as e:
    print(f"Connection error: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
EOF
        
        if python "$TEMP_SCRIPT"; then
            rm -f "$TEMP_SCRIPT"
            log_success "Database connection established!"
            return 0
        else
            EXIT_CODE=$?
            log_warning "Database connection failed (exit code: $EXIT_CODE)"
        fi
        
        rm -f "$TEMP_SCRIPT"
        
        if [ $attempt -lt $max_attempts ]; then
            log "Waiting $wait_seconds seconds before retry..."
            sleep $wait_seconds
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "Database failed to become ready after $max_attempts attempts"
    log_error "Please check:"
    log_error "  1. Database service is running"
    log_error "  2. DATABASE_URL environment variable is correctly set"
    log_error "  3. Network connectivity to database host"
    log_error "  4. Database credentials are correct"
    exit 1
}

# Function to run database initialization
initialize_database() {
    log "Starting database initialization..."
    
    # Run database initialization (creates tables if they don't exist)
    log "Running database schema initialization..."
    if OUTPUT=$(trackcast init-db 2>&1); then
        log_success "Database schema initialization completed"
        echo "$OUTPUT" | while IFS= read -r line; do
            log "  $line"
        done
    else
        log_error "Database schema initialization failed"
        echo "$OUTPUT" | while IFS= read -r line; do
            log_error "  $line"
        done
        exit 1
    fi
    
    # Run database migrations (applies any pending schema changes)
    log "Running database migrations..."
    if OUTPUT=$(trackcast update-schema 2>&1); then
        log_success "Database migrations completed"
        echo "$OUTPUT" | while IFS= read -r line; do
            log "  $line"
        done
    else
        log_error "Database migrations failed"
        echo "$OUTPUT" | while IFS= read -r line; do
            log_error "  $line"
        done
        exit 1
    fi
}

# Function to validate the setup
validate_setup() {
    log "Starting database validation..."
    
    # Create a temporary Python script for validation
    TEMP_SCRIPT=$(mktemp)
    cat > "$TEMP_SCRIPT" << 'EOF'
import sys
import traceback

try:
    from trackcast.db.connection import engine
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"Found {len(tables)} tables in database: {sorted(tables)}")
    
    required_tables = ['trains', 'train_stops', 'model_data', 'prediction_data']
    missing_tables = [t for t in required_tables if t not in tables]
    
    if missing_tables:
        print(f"ERROR: Missing required tables: {missing_tables}")
        sys.exit(1)
    else:
        print(f"SUCCESS: All required tables exist: {required_tables}")
        
        # Additional validation: check table row counts
        from sqlalchemy import text
        with engine.connect() as conn:
            for table in required_tables:
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    print(f"  Table '{table}' has {count} rows")
                except Exception as e:
                    print(f"  WARNING: Could not count rows in table '{table}': {e}")
        
        sys.exit(0)
        
except Exception as e:
    print(f"Validation error: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
EOF
    
    if python "$TEMP_SCRIPT"; then
        rm -f "$TEMP_SCRIPT"
        log_success "Database validation passed"
    else
        rm -f "$TEMP_SCRIPT"
        log_error "Database validation failed"
        exit 1
    fi
}

# Function to check environment
check_environment() {
    log "Checking environment configuration..."
    
    # Check critical environment variables
    if [ -z "$DATABASE_URL" ]; then
        log_warning "DATABASE_URL environment variable is not set"
    else
        # Mask password in log
        MASKED_URL=$(echo "$DATABASE_URL" | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/')
        log "DATABASE_URL is set: $MASKED_URL"
    fi
    
    log "TRACKCAST_ENV: ${TRACKCAST_ENV:-not set (defaulting to 'dev')}"
    log "Python executable: $(which python)"
    log "Python version: $(python --version 2>&1)"
    
    # Check if TrackCast package is installed
    if python -c "import trackcast; print(f'TrackCast module found at: {trackcast.__file__}')" 2>/dev/null; then
        log_success "TrackCast package is installed"
    else
        log_error "TrackCast package is not installed"
        exit 1
    fi
}

# Main execution
main() {
    log "=== TrackCast Container Startup Sequence ==="
    log "Container started with command: $@"
    
    # Check environment first
    check_environment
    
    # Wait for database to be available
    wait_for_database
    
    # Initialize database and run migrations
    initialize_database
    
    # Validate setup
    validate_setup
    
    log "=== Starting Application ==="
    log_success "All startup checks passed. Starting API server..."
    log "Executing command: $@"
    
    # Execute the main application command
    exec "$@"
}

# Trap errors and log them
trap 'log_error "Script failed at line $LINENO with exit code $?"' ERR

# Run main function
main "$@"