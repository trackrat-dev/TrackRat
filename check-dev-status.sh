#!/bin/bash
# check-dev-status.sh - Check the status of TrackRat development environment

set -euo pipefail

# Configuration
PROJECT_ID="trackrat-dev"
REGION="us-central1"
ENVIRONMENT="dev"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Status icons
CHECK="✓"
CROSS="✗"
WARN="⚠"
INFO="ℹ"

# Helper functions
log_info() {
    echo -e "${BLUE}${INFO}${NC} $1"
}

log_success() {
    echo -e "${GREEN}${CHECK}${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}${WARN}${NC} $1"
}

log_error() {
    echo -e "${RED}${CROSS}${NC} $1"
}

print_header() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}TrackRat Development Environment Status${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Check GCP authentication
check_auth() {
    echo
    echo "🔐 Authentication Status"
    echo "------------------------"
    
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        local account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
        log_success "Authenticated as: $account"
    else
        log_error "Not authenticated with Google Cloud"
        return 1
    fi
    
    local current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ "$current_project" == "$PROJECT_ID" ]]; then
        log_success "Project set to: $PROJECT_ID"
    else
        log_warning "Project is set to: $current_project (expected: $PROJECT_ID)"
    fi
}

# Check Cloud Run services
check_services() {
    echo
    echo "🚀 Cloud Run Services"
    echo "--------------------"
    
    # API Service
    local api_service="trackrat-api-${ENVIRONMENT}"
    if gcloud run services describe "$api_service" --region="$REGION" --project="$PROJECT_ID" &> /dev/null; then
        local api_url=$(gcloud run services describe "$api_service" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')
        local api_latest=$(gcloud run services describe "$api_service" --region="$REGION" --project="$PROJECT_ID" --format='value(status.latestReadyRevisionName)')
        log_success "API Service: RUNNING"
        echo "  URL: $api_url"
        echo "  Latest Revision: $api_latest"
        
        # Check health endpoint
        if curl -sf "${api_url}/health" > /dev/null 2>&1; then
            log_success "  Health Check: PASSING"
        else
            log_warning "  Health Check: FAILING"
        fi
    else
        log_error "API Service: NOT FOUND"
    fi
    
    echo
    
    # Scheduler Service
    local scheduler_service="trackrat-scheduler-${ENVIRONMENT}"
    if gcloud run services describe "$scheduler_service" --region="$REGION" --project="$PROJECT_ID" &> /dev/null; then
        local scheduler_latest=$(gcloud run services describe "$scheduler_service" --region="$REGION" --project="$PROJECT_ID" --format='value(status.latestReadyRevisionName)')
        log_success "Scheduler Service: RUNNING"
        echo "  Latest Revision: $scheduler_latest"
    else
        log_error "Scheduler Service: NOT FOUND"
    fi
}

# Check Cloud SQL database
check_database() {
    echo
    echo "🗄️  Cloud SQL Database"
    echo "--------------------"
    
    local instance_name="trackrat-${ENVIRONMENT}"
    if gcloud sql instances describe "$instance_name" --project="$PROJECT_ID" &> /dev/null; then
        local db_state=$(gcloud sql instances describe "$instance_name" --project="$PROJECT_ID" --format='value(state)')
        local db_version=$(gcloud sql instances describe "$instance_name" --project="$PROJECT_ID" --format='value(databaseVersion)')
        
        if [[ "$db_state" == "RUNNABLE" ]]; then
            log_success "Database Instance: RUNNING"
        else
            log_warning "Database Instance: $db_state"
        fi
        
        echo "  Version: $db_version"
        echo "  Instance: $instance_name"
    else
        log_error "Database Instance: NOT FOUND"
    fi
}

# Check Cloud Scheduler jobs
check_scheduler_jobs() {
    echo
    echo "⏰ Cloud Scheduler Jobs"
    echo "----------------------"
    
    local jobs=$(gcloud scheduler jobs list --location="$REGION" --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | grep -E "trackrat|trackcast" || true)
    
    if [[ -n "$jobs" ]]; then
        while IFS= read -r job; do
            local job_name=$(basename "$job")
            local state=$(gcloud scheduler jobs describe "$job" --location="$REGION" --project="$PROJECT_ID" --format="value(state)" 2>/dev/null || echo "UNKNOWN")
            local schedule=$(gcloud scheduler jobs describe "$job" --location="$REGION" --project="$PROJECT_ID" --format="value(schedule)" 2>/dev/null || echo "N/A")
            
            if [[ "$state" == "ENABLED" ]]; then
                log_success "$job_name: $state"
                echo "  Schedule: $schedule"
            else
                log_warning "$job_name: $state"
            fi
        done <<< "$jobs"
    else
        log_warning "No scheduler jobs found"
    fi
}

# Check recent deployments
check_recent_deployments() {
    echo
    echo "📦 Recent Deployments"
    echo "--------------------"
    
    # Get recent Cloud Run revisions
    local api_service="trackrat-api-${ENVIRONMENT}"
    local revisions=$(gcloud run revisions list --service="$api_service" --region="$REGION" --project="$PROJECT_ID" --format="table(name,metadata.creationTimestamp,status.conditions[0].status)" --limit=3 2>/dev/null || echo "")
    
    if [[ -n "$revisions" ]]; then
        echo "$revisions"
    else
        log_warning "No recent deployments found"
    fi
}

# Check Artifact Registry images
check_images() {
    echo
    echo "🐳 Docker Images"
    echo "---------------"
    
    local repository="trackcast-inference-${ENVIRONMENT}"
    local image_path="${REGION}-docker.pkg.dev/${PROJECT_ID}/${repository}/trackcast-inference"
    
    # List recent images
    local images=$(gcloud artifacts docker images list "$image_path" --include-tags --limit=3 --format="table(image,tags,createTime)" 2>/dev/null || echo "")
    
    if [[ -n "$images" ]]; then
        echo "$images"
    else
        log_warning "No images found in Artifact Registry"
    fi
}

# Check monitoring metrics
check_metrics() {
    echo
    echo "📊 System Metrics (Last Hour)"
    echo "----------------------------"
    
    local api_service="trackrat-api-${ENVIRONMENT}"
    
    # Get service URL for API calls
    local api_url=$(gcloud run services describe "$api_service" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)' 2>/dev/null || echo "")
    
    if [[ -n "$api_url" ]]; then
        # Try to get metrics from the health endpoint
        local health_response=$(curl -sf "${api_url}/health" 2>/dev/null || echo "{}")
        
        if [[ -n "$health_response" ]] && [[ "$health_response" != "{}" ]]; then
            echo "$health_response" | jq -r '.quality_metrics // empty' 2>/dev/null || log_info "Health metrics not available"
        else
            log_info "Unable to fetch health metrics"
        fi
    fi
    
    # Show Cloud Run metrics summary
    log_info "For detailed metrics, visit:"
    echo "  https://console.cloud.google.com/run/detail/${REGION}/${api_service}/metrics?project=${PROJECT_ID}"
}

# Show useful commands
show_commands() {
    echo
    echo "🔧 Useful Commands"
    echo "-----------------"
    echo "View logs:"
    echo "  gcloud run logs read --service=trackrat-api-${ENVIRONMENT} --region=${REGION}"
    echo
    echo "Deploy new version:"
    echo "  ./deploy-dev.sh"
    echo
    echo "Quick deployment (skip tests):"
    echo "  ./deploy-dev.sh --skip-tests --skip-terraform"
    echo
    echo "Access Cloud Console:"
    echo "  https://console.cloud.google.com/run?project=${PROJECT_ID}"
}

# Main execution
main() {
    print_header
    
    # Run all checks
    check_auth || exit 1
    check_services
    check_database
    check_scheduler_jobs
    check_recent_deployments
    check_images
    check_metrics
    show_commands
    
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Status check complete at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Run main function
main "$@"