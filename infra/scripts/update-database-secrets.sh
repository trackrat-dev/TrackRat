#!/bin/bash
# Script to automatically update Secret Manager with database connection strings
# This script constructs database URLs from Terraform outputs and updates Secret Manager

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [ENVIRONMENT] [PROJECT_ID]"
    echo ""
    echo "Arguments:"
    echo "  ENVIRONMENT  Environment name (dev, staging, prod). Default: dev"
    echo "  PROJECT_ID   GCP Project ID. Default: trackrat-{ENVIRONMENT}"
    echo ""
    echo "Examples:"
    echo "  $0                           # Uses dev environment and trackrat-dev project"
    echo "  $0 staging                   # Uses staging environment and trackrat-staging project"
    echo "  $0 prod trackrat-production  # Uses prod environment and trackrat-production project"
    echo ""
    echo "Prerequisites:"
    echo "  - gcloud CLI installed and authenticated"
    echo "  - terraform CLI installed"
    echo "  - jq CLI installed"
    echo "  - Terraform state initialized in environments/ENVIRONMENT/"
    echo "  - Secret Manager secret 'trackcast-ENVIRONMENT-secrets' exists"
}

# Parse command line arguments
ENVIRONMENT=${1:-dev}
PROJECT_ID=${2:-trackrat-${ENVIRONMENT}}

# Validate arguments
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_usage
    exit 0
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid environment. Must be one of: dev, staging, prod"
    show_usage
    exit 1
fi

print_info "Starting database secrets update for environment: $ENVIRONMENT"
print_info "Using GCP Project ID: $PROJECT_ID"

# Check prerequisites
print_info "Checking prerequisites..."

# Check if required tools are installed
for tool in gcloud terraform jq; do
    if ! command -v $tool &> /dev/null; then
        print_error "$tool is not installed or not in PATH"
        exit 1
    fi
done

# Check if terraform directory exists
TERRAFORM_DIR="environments/${ENVIRONMENT}"
if [[ ! -d "$TERRAFORM_DIR" ]]; then
    print_error "Terraform directory not found: $TERRAFORM_DIR"
    print_error "Make sure you're running this script from the infra/ directory"
    exit 1
fi

# Check if we're in the correct directory
if [[ ! -f "main.tf" || ! -d "modules" ]]; then
    print_error "This script must be run from the infra/ directory"
    exit 1
fi

print_success "Prerequisites check passed"

# Change to terraform directory
cd "$TERRAFORM_DIR"

# Check if terraform is initialized
if [[ ! -d ".terraform" ]]; then
    print_error "Terraform not initialized in $TERRAFORM_DIR"
    print_error "Run 'terraform init' first"
    exit 1
fi

print_info "Retrieving database connection details from Terraform outputs..."

# Get Terraform outputs
print_info "Getting database private IP..."
if ! DB_HOST=$(terraform output -raw database_private_ip 2>/dev/null); then
    print_error "Failed to get database private IP from Terraform outputs"
    print_error "Make sure the database module is deployed and outputs are available"
    exit 1
fi

print_info "Getting database name..."
if ! DB_NAME=$(terraform output -raw database_name 2>/dev/null); then
    print_error "Failed to get database name from Terraform outputs"
    exit 1
fi

print_info "Getting database user name..."
if ! DB_USER=$(terraform output -raw database_user_name 2>/dev/null); then
    print_error "Failed to get database user name from Terraform outputs"
    exit 1
fi

print_info "Getting database password secret ID..."
if ! DB_PASSWORD_SECRET=$(terraform output -raw database_password_secret_id 2>/dev/null); then
    print_error "Failed to get database password secret ID from Terraform outputs"
    exit 1
fi

print_success "Retrieved all database connection details"
print_info "Database Host: $DB_HOST"
print_info "Database Name: $DB_NAME"
print_info "Database User: $DB_USER"
print_info "Password Secret: $DB_PASSWORD_SECRET"

# Retrieve database password from Secret Manager
print_info "Retrieving database password from Secret Manager..."
if ! DB_PASSWORD=$(gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET" --project="$PROJECT_ID" 2>/dev/null); then
    print_error "Failed to retrieve database password from Secret Manager"
    print_error "Make sure the secret '$DB_PASSWORD_SECRET' exists in project '$PROJECT_ID'"
    exit 1
fi

print_success "Retrieved database password"

# Construct database URL
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"
print_info "Constructed database URL: postgresql://${DB_USER}:***@${DB_HOST}:5432/${DB_NAME}"

# Get application secrets name
APP_SECRETS_NAME="trackcast-${ENVIRONMENT}-secrets"
print_info "Updating application secrets: $APP_SECRETS_NAME"

# Get existing secret content
print_info "Retrieving existing secret content..."
if ! EXISTING_SECRET=$(gcloud secrets versions access latest --secret="$APP_SECRETS_NAME" --project="$PROJECT_ID" 2>/dev/null); then
    print_error "Failed to retrieve existing secret content from '$APP_SECRETS_NAME'"
    print_error "Make sure the secret exists in project '$PROJECT_ID'"
    exit 1
fi

# Validate that existing secret is valid JSON
if ! echo "$EXISTING_SECRET" | jq empty 2>/dev/null; then
    print_error "Existing secret content is not valid JSON"
    exit 1
fi

print_success "Retrieved existing secret content"

# Update database_url in the secret
print_info "Updating database_url in secret..."
if ! UPDATED_SECRET=$(echo "$EXISTING_SECRET" | jq --arg db_url "$DATABASE_URL" '.database_url = $db_url'); then
    print_error "Failed to update secret content with new database URL"
    exit 1
fi

# Validate updated secret is valid JSON
if ! echo "$UPDATED_SECRET" | jq empty 2>/dev/null; then
    print_error "Updated secret content is not valid JSON"
    exit 1
fi

print_success "Updated secret content prepared"

# Show what will be updated (without exposing the password)
print_info "Secret update preview:"
echo "$UPDATED_SECRET" | jq --arg db_url "postgresql://${DB_USER}:***@${DB_HOST}:5432/${DB_NAME}" '.database_url = $db_url'

# Confirm before updating (unless in CI)
if [[ -z "$CI" && -z "$SKIP_CONFIRMATION" ]]; then
    print_warning "This will update the database_url in Secret Manager."
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Update cancelled by user"
        exit 0
    fi
fi

# Update Secret Manager
print_info "Updating Secret Manager..."
if ! echo "$UPDATED_SECRET" | gcloud secrets versions add "$APP_SECRETS_NAME" --data-file=- --project="$PROJECT_ID" 2>/dev/null; then
    print_error "Failed to update Secret Manager with new database URL"
    exit 1
fi

print_success "Database URL updated in Secret Manager"

# Verify the update
print_info "Verifying secret update..."
if ! VERIFICATION_SECRET=$(gcloud secrets versions access latest --secret="$APP_SECRETS_NAME" --project="$PROJECT_ID" 2>/dev/null); then
    print_warning "Could not verify secret update"
else
    if echo "$VERIFICATION_SECRET" | jq -e '.database_url' > /dev/null 2>&1; then
        print_success "Secret update verified successfully"
    else
        print_warning "Could not verify database_url field in updated secret"
    fi
fi

print_success "Database secrets update completed successfully!"
print_info "Cloud Run services will use the updated database URL on next deployment"

# Return to original directory
cd - > /dev/null

exit 0