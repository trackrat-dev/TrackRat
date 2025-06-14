#!/bin/bash

# Setup script for Terraform backend Cloud Storage buckets
# This script creates the necessary storage buckets for Terraform state files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default project IDs (can be overridden)
DEV_PROJECT_ID=${DEV_PROJECT_ID:-"trackrat-dev"}
STAGING_PROJECT_ID=${STAGING_PROJECT_ID:-"trackrat-staging"}
PROD_PROJECT_ID=${PROD_PROJECT_ID:-"trackrat-prod"}

# Region for buckets
REGION=${REGION:-"us-east1"}

# Function to create a bucket if it doesn't exist
create_bucket() {
    local project_id=$1
    local bucket_name=$2
    local location=$3
    
    print_status "Creating bucket: $bucket_name in project: $project_id"
    
    # Check if bucket already exists
    if gsutil ls -b gs://$bucket_name &>/dev/null; then
        print_warning "Bucket $bucket_name already exists"
        return 0
    fi
    
    # Create the bucket
    gsutil mb -p $project_id -c STANDARD -l $location gs://$bucket_name
    
    # Enable versioning for state file safety
    gsutil versioning set on gs://$bucket_name
    
    # Set lifecycle policy to clean up old versions
    cat > /tmp/lifecycle.json << EOF
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 30,
        "isLive": false
      }
    }
  ]
}
EOF
    
    gsutil lifecycle set /tmp/lifecycle.json gs://$bucket_name
    rm /tmp/lifecycle.json
    
    print_status "Bucket $bucket_name created successfully"
}

# Function to setup backend for an environment
setup_environment() {
    local env=$1
    local project_id=$2
    
    print_status "Setting up backend for $env environment (project: $project_id)"
    
    # Set the current project
    gcloud config set project $project_id
    
    # Enable required APIs
    print_status "Enabling required APIs for $project_id"
    gcloud services enable storage.googleapis.com
    gcloud services enable cloudresourcemanager.googleapis.com
    
    # Create the backend bucket
    local bucket_name="$project_id-terraform-state"
    create_bucket $project_id $bucket_name $REGION
    
    # Create a terraform.tfvars file for the environment
    local tfvars_file="environments/$env/terraform.tfvars"
    print_status "Creating $tfvars_file"
    
    cat > $tfvars_file << EOF
# Terraform variables for $env environment
project_id = "$project_id"
region     = "$REGION"
zone       = "$REGION-b"
EOF
    
    print_status "Environment $env setup completed"
}

# Main execution
main() {
    print_status "Starting Terraform backend setup for TrackRat"
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if gsutil is available
    if ! command -v gsutil &> /dev/null; then
        print_error "gsutil is not available. Please install Google Cloud SDK."
        exit 1
    fi
    
    print_status "Using the following project IDs:"
    echo "  Dev: $DEV_PROJECT_ID"
    echo "  Staging: $STAGING_PROJECT_ID"
    echo "  Prod: $PROD_PROJECT_ID"
    echo ""
    
    # Setup each environment
    setup_environment "dev" $DEV_PROJECT_ID
    echo ""
    setup_environment "staging" $STAGING_PROJECT_ID
    echo ""
    setup_environment "prod" $PROD_PROJECT_ID
    echo ""
    
    print_status "Terraform backend setup completed successfully!"
    print_status "You can now initialize Terraform in each environment:"
    echo "  cd environments/dev && terraform init"
    echo "  cd environments/staging && terraform init"
    echo "  cd environments/prod && terraform init"
}

# Run the setup if this script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi