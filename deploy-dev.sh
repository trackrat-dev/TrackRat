#!/bin/bash
# deploy-dev.sh - Deploy local changes to TrackRat development environment
# This script handles both infrastructure (Terraform) and application (Docker) deployments

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="trackrat-dev"
REGION="us-central1"
ENVIRONMENT="dev"
REPOSITORY="trackcast-inference-dev"
SERVICE_NAME="trackcast-inference"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
SKIP_TESTS=false
SKIP_TERRAFORM=false
SKIP_DOCKER=false
TERRAFORM_ONLY=false
DOCKER_ONLY=false
AUTO_APPROVE=false
DRY_RUN=false
VERBOSE=true  # Show full output by default for debugging

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Progress bar function
show_progress() {
    local message=$1
    echo -en "${BLUE}⠼${NC} $message..."
}

complete_progress() {
    echo -e "\r${GREEN}✓${NC} $1"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --skip-terraform)
                SKIP_TERRAFORM=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --terraform-only)
                TERRAFORM_ONLY=true
                SKIP_DOCKER=true
                shift
                ;;
            --docker-only)
                DOCKER_ONLY=true
                SKIP_TERRAFORM=true
                shift
                ;;
            --auto-approve)
                AUTO_APPROVE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help message
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy local changes to TrackRat development environment.

Options:
    --skip-tests          Skip running tests before deployment
    --skip-terraform      Skip Terraform apply (only update Cloud Run)
    --skip-docker         Skip Docker build (only run Terraform)
    --terraform-only      Only apply Terraform changes
    --docker-only         Only build/deploy Docker images
    --auto-approve        Skip confirmation prompts
    --dry-run             Show what would be done without executing
    -h, --help            Show this help message

Examples:
    # Full deployment (infrastructure + application)
    $0

    # Quick app-only deployment
    $0 --skip-terraform --skip-tests

    # Infrastructure-only update
    $0 --terraform-only

EOF
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local required_tools=("gcloud" "docker" "terraform")
    for tool in "${required_tools[@]}"; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is not installed. Please install it first."
            exit 1
        fi
    done
    
    # Check Docker buildx for multi-platform support
    if ! docker buildx version &> /dev/null; then
        log_warning "Docker buildx not found. Installing buildx for multi-platform builds..."
        docker buildx create --use --name mybuilder --driver docker-container &> /dev/null || true
    fi
    
    # Verify Docker can build for linux/amd64
    local current_builder=$(docker buildx inspect --bootstrap 2>/dev/null | grep -E "Platforms:.*linux/amd64" || echo "")
    if [[ -z "$current_builder" ]]; then
        log_info "Setting up Docker buildx for linux/amd64 platform..."
        docker buildx create --use --name trackrat-builder --platform linux/amd64,linux/arm64 &> /dev/null || true
    fi
    
    # Check GCP authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "Not authenticated with Google Cloud. Please run: gcloud auth login"
        exit 1
    fi
    
    local active_account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    log_info "Authenticated as: $active_account"
    
    # Set and verify project
    gcloud config set project $PROJECT_ID &> /dev/null
    local current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ "$current_project" != "$PROJECT_ID" ]]; then
        log_error "Failed to set project to $PROJECT_ID"
        exit 1
    fi
    
    log_info "Project: $PROJECT_ID"
    log_info "Region: $REGION"
    
    # Check Docker authentication for Artifact Registry
    log_info "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    
    complete_progress "Prerequisites checked"
}

# Check git status
check_git_status() {
    log_info "Checking git status..."
    
    if [[ -d .git ]]; then
        if [[ -n $(git status --porcelain) ]]; then
            log_warning "Uncommitted changes detected:"
            git status --short | head -10
            echo
            
            if [[ "$AUTO_APPROVE" != "true" ]]; then
                read -p "Deploy with uncommitted changes? [y/N]: " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    log_info "Deployment cancelled."
                    exit 0
                fi
            fi
        else
            log_success "Working directory is clean"
        fi
    fi
}

# Run tests
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_info "Skipping tests (--skip-tests flag)"
        return
    fi
    
    log_info "Running tests..."
    
    # Backend tests
    log_info "Running backend tests..."
    cd "$SCRIPT_DIR/backend"
    
    if [[ -f "requirements-cpu.txt" ]]; then
        # Use virtual environment if it exists
        if [[ -d "venv" ]] && [[ -f "venv/bin/activate" ]]; then
            source venv/bin/activate
        fi
        
        # Run unit tests
        log_info "Running unit tests..."
        local test_output="/tmp/pytest-output-$$"
        if pytest tests/unit/ -v --tb=short > "$test_output" 2>&1; then
            complete_progress "Unit tests passed"
            rm -f "$test_output"
        else
            log_error "Unit tests failed"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            cat "$test_output"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            rm -f "$test_output"
            exit 1
        fi
    else
        log_warning "Backend tests skipped - requirements-cpu.txt not found"
    fi
    
    # Terraform validation
    log_info "Validating Terraform configuration..."
    cd "$SCRIPT_DIR/infra"
    
    if [[ -f "Makefile" ]]; then
        log_info "Running Terraform validation..."
        local tf_output="/tmp/terraform-validation-$$"
        if make test > "$tf_output" 2>&1; then
            complete_progress "Terraform validation passed"
            rm -f "$tf_output"
        else
            log_error "Terraform validation failed"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            cat "$tf_output"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            rm -f "$tf_output"
            exit 1
        fi
    else
        log_warning "Terraform validation skipped - Makefile not found"
    fi
    
    cd "$SCRIPT_DIR"
    log_success "All tests passed"
}

# Get current timestamp for tagging
get_timestamp() {
    date -u +"%Y%m%d-%H%M%S"
}

# Get git short SHA
get_git_sha() {
    git rev-parse --short=7 HEAD 2>/dev/null || echo "0000000"
}

# Build and push Docker image
build_and_push_docker() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        log_info "Skipping Docker build (--skip-docker flag)"
        return
    fi
    
    log_info "Building Docker image..."
    
    cd "$SCRIPT_DIR/backend"
    
    # Generate version similar to CI/CD but for local development
    local timestamp=$(date -u +"%Y.%m.%d")
    local build_id=$(date +%s)  # Use timestamp as build ID for local
    local git_sha=$(get_git_sha)
    local version="${timestamp}-local${build_id}-${git_sha}"
    
    local image_tag="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"
    local version_tag="${image_tag}:${version}"
    local latest_tag="${image_tag}:latest"
    
    log_info "Building image with version: $version"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would build: docker build --platform linux/amd64 -t $version_tag -t $latest_tag --target runtime ."
        return
    fi
    
    # Build the Docker image
    log_info "Starting Docker build..."
    log_info "Building for platform: linux/amd64 (required for Cloud Run)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Force build for linux/amd64 platform (required for Cloud Run)
    if docker build --platform linux/amd64 -t "$version_tag" -t "$latest_tag" --target runtime . 2>&1 | while IFS= read -r line; do
        echo "  $line"
    done; then
        complete_progress "Docker image built for linux/amd64"
    else
        log_error "Docker build failed"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Push to Artifact Registry
    log_info "Pushing image to Artifact Registry..."
    
    # Push specific version tag
    echo "Pushing $version_tag..."
    if docker push "$version_tag" 2>&1 | grep -E "(Pushing|Copying|Mounted|Pushed|digest:|size:)" | while IFS= read -r line; do
        echo "  $line"
    done; then
        complete_progress "Image pushed: $version_tag"
    else
        log_error "Failed to push Docker image"
        exit 1
    fi
    
    # Push latest tag
    echo "Pushing $latest_tag..."
    if docker push "$latest_tag" 2>&1 | grep -E "(Pushing|Copying|Mounted|Pushed|digest:|size:)" | while IFS= read -r line; do
        echo "  $line"
    done; then
        complete_progress "Latest tag updated"
    else
        log_error "Failed to push latest tag"
        exit 1
    fi
    
    # Export for later use - use specific version for deployment
    export DOCKER_IMAGE_URL="$version_tag"
    export DOCKER_VERSION="$version"
    
    cd "$SCRIPT_DIR"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    if [[ "$SKIP_TERRAFORM" == "true" ]]; then
        log_info "Skipping Terraform deployment (--skip-terraform flag)"
        return
    fi
    
    log_info "Deploying infrastructure with Terraform..."
    
    cd "$SCRIPT_DIR/infra/environments/$ENVIRONMENT"
    
    # Initialize Terraform if needed
    if [[ ! -d ".terraform" ]]; then
        log_info "Initializing Terraform..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if terraform init 2>&1 | while IFS= read -r line; do
            echo "  $line"
        done; then
            complete_progress "Terraform initialized"
        else
            log_error "Terraform init failed"
            exit 1
        fi
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi
    
    # Create terraform.tfvars
    log_info "Creating terraform.tfvars..."
    
    # Use the specific version image URL or a placeholder
    local api_image="${DOCKER_IMAGE_URL:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest}"
    local scheduler_image="${DOCKER_IMAGE_URL:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest}"
    
    cat > terraform.tfvars << EOF
project_id = "$PROJECT_ID"
region = "$REGION"
zone = "${REGION}-b"
api_image_url = "$api_image"
scheduler_image_url = "$scheduler_image"
EOF
    
    # Plan changes
    log_info "Planning Terraform changes..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Running terraform plan..."
        terraform plan -var-file=terraform.tfvars
        return
    fi
    
    # Create plan with full output
    local plan_output_file="/tmp/terraform-plan-output-$$"
    if terraform plan -var-file=terraform.tfvars -out=tfplan 2>&1 | tee "$plan_output_file" | while IFS= read -r line; do
        echo "  $line"
    done; then
        complete_progress "Terraform plan created"
    else
        log_error "Terraform plan failed. See output above for details."
        rm -f "$plan_output_file"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Show plan summary
    log_info "Terraform will perform the following actions:"
    terraform show -no-color tfplan | grep -E "^  # |^Plan:" | head -20
    
    # Apply changes
    if [[ "$AUTO_APPROVE" != "true" ]]; then
        read -p "Apply these changes? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Terraform apply cancelled."
            cd "$SCRIPT_DIR"
            rm -f "$plan_output_file"
            return
        fi
    fi
    
    log_info "Applying Terraform changes..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if terraform apply -auto-approve tfplan 2>&1 | while IFS= read -r line; do
        echo "  $line"
    done; then
        complete_progress "Infrastructure deployed"
    else
        log_error "Terraform apply failed. See output above for details."
        echo
        log_error "Common issues:"
        echo "  - Resource already exists (may need to import or destroy)"
        echo "  - IAM permissions insufficient"
        echo "  - API not enabled in project"
        echo "  - Quota exceeded"
        echo
        log_info "To see more details, run: terraform apply tfplan"
        rm -f "$plan_output_file"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Clean up
    rm -f "$plan_output_file"
    
    # Get service URL
    SERVICE_URL=$(terraform output -raw trackrat_api_service_url 2>/dev/null || echo "")
    if [[ -n "$SERVICE_URL" ]]; then
        export SERVICE_URL
        log_info "Service URL: $SERVICE_URL"
    fi
    
    cd "$SCRIPT_DIR"
}

# Update Cloud Run services
update_cloud_run() {
    if [[ "$SKIP_DOCKER" == "true" ]] || [[ "$SKIP_TERRAFORM" != "true" ]]; then
        # If we skipped Docker or didn't skip Terraform, Cloud Run update is handled by Terraform
        return
    fi
    
    log_info "Updating Cloud Run services directly..."
    
    local image_url="${DOCKER_IMAGE_URL:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest}"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would update Cloud Run services with image: $image_url"
        return
    fi
    
    # Update API service
    show_progress "Updating API service"
    if gcloud run deploy trackrat-api-${ENVIRONMENT} \
        --image="$image_url" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --quiet > /dev/null 2>&1; then
        complete_progress "API service updated"
    else
        log_error "Failed to update API service"
        exit 1
    fi
    
    # Update scheduler service
    show_progress "Updating scheduler service"
    if gcloud run deploy trackrat-scheduler-${ENVIRONMENT} \
        --image="$image_url" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --quiet > /dev/null 2>&1; then
        complete_progress "Scheduler service updated"
    else
        log_error "Failed to update scheduler service"
        exit 1
    fi
    
    # Get service URL if not already set
    if [[ -z "$SERVICE_URL" ]]; then
        SERVICE_URL=$(gcloud run services describe trackrat-api-${ENVIRONMENT} \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --format='value(status.url)' 2>/dev/null || echo "")
        export SERVICE_URL
    fi
}

# Perform health checks
verify_deployment() {
    log_info "Verifying deployment..."
    
    if [[ -z "${SERVICE_URL:-}" ]]; then
        log_warning "Service URL not available, attempting to retrieve..."
        SERVICE_URL=$(gcloud run services describe trackrat-api-${ENVIRONMENT} \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --format='value(status.url)' 2>/dev/null || echo "")
    fi
    
    if [[ -z "$SERVICE_URL" ]]; then
        log_warning "Could not retrieve service URL, skipping health checks"
        return
    fi
    
    log_info "Service URL: $SERVICE_URL"
    
    # Wait for service to be ready
    log_info "Waiting for service to be ready..."
    sleep 30
    
    # Health check
    local health_url="${SERVICE_URL}/health"
    local max_attempts=5
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        show_progress "Health check attempt $attempt/$max_attempts"
        
        if curl -sf "$health_url" > /dev/null 2>&1; then
            complete_progress "Health check passed"
            
            # Show health status
            log_info "Health endpoint response:"
            curl -s "$health_url" | jq '.' 2>/dev/null || curl -s "$health_url"
            break
        else
            if [[ $attempt -eq $max_attempts ]]; then
                log_error "Health check failed after $max_attempts attempts"
                exit 1
            fi
            log_warning "Health check failed, retrying in 30 seconds..."
            sleep 30
            ((attempt++))
        fi
    done
    
    # Test API endpoints
    log_info "Testing API endpoints..."
    
    local trains_url="${SERVICE_URL}/api/trains/?limit=5"
    if curl -sf "$trains_url" > /dev/null 2>&1; then
        log_success "Trains API endpoint is responding"
    else
        log_warning "Trains API endpoint check failed (may be expected if no data)"
    fi
    
    local stops_url="${SERVICE_URL}/api/stops/"
    if curl -sf "$stops_url" > /dev/null 2>&1; then
        log_success "Stops API endpoint is responding"
    else
        log_warning "Stops API endpoint check failed (may be expected if no data)"
    fi
}

# Show deployment summary
show_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}🚀 Development Deployment Complete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}This was a dry run. No changes were made.${NC}"
        echo
    fi
    
    echo "Environment: $ENVIRONMENT"
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    
    if [[ -n "${SERVICE_URL:-}" ]]; then
        echo
        echo "Service URLs:"
        echo "  API: $SERVICE_URL"
        echo "  Health: ${SERVICE_URL}/health"
        echo "  Trains: ${SERVICE_URL}/api/trains/"
        echo "  Stops: ${SERVICE_URL}/api/stops/"
    fi
    
    if [[ -n "${DOCKER_IMAGE_URL:-}" ]]; then
        echo
        echo "Version: ${DOCKER_VERSION:-unknown}"
        echo "Docker Image: $DOCKER_IMAGE_URL"
    fi
    
    echo
    echo "Deployment Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    
    echo
    echo "Next Steps:"
    echo "  - Check service logs: gcloud run logs read --service=trackrat-api-${ENVIRONMENT} --region=${REGION}"
    echo "  - View in console: https://console.cloud.google.com/run/detail/${REGION}/trackrat-api-${ENVIRONMENT}/logs?project=${PROJECT_ID}"
    
    if [[ "$SKIP_TERRAFORM" == "true" ]] && [[ "$SKIP_DOCKER" != "true" ]]; then
        echo "  - Note: Only Docker image was updated. Infrastructure changes were skipped."
    fi
    
    if [[ "$SKIP_DOCKER" == "true" ]] && [[ "$SKIP_TERRAFORM" != "true" ]]; then
        echo "  - Note: Only infrastructure was updated. Docker image was not rebuilt."
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Main execution
main() {
    echo -e "${BLUE}🚀 TrackRat Development Deployment${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    parse_arguments "$@"
    
    # Validate option combinations
    if [[ "$TERRAFORM_ONLY" == "true" ]] && [[ "$DOCKER_ONLY" == "true" ]]; then
        log_error "Cannot use both --terraform-only and --docker-only"
        exit 1
    fi
    
    # Run deployment steps
    check_prerequisites
    check_git_status
    run_tests
    build_and_push_docker
    deploy_infrastructure
    update_cloud_run
    
    if [[ "$DRY_RUN" != "true" ]]; then
        verify_deployment
    fi
    
    show_summary
}

# Run main function
main "$@"