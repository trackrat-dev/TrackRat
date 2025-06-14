#!/bin/bash

# TrackRat CD Setup Script
# This script sets up the service accounts and permissions needed for continuous deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="trackrat-dev"
GITHUB_SA_NAME="github-actions-cd"
CLOUDRUN_SA_NAME="trackcast-dev-sa"
SECRET_NAME="trackcast-dev-secrets"
REGION="us-central1"

echo -e "${BLUE}🚀 Setting up TrackRat Continuous Deployment${NC}"
echo -e "${BLUE}Project: ${PROJECT_ID}${NC}"
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
    echo -e "${RED}❌ Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
    exit 1
fi

# Set project
echo -e "${YELLOW}📋 Setting project to ${PROJECT_ID}...${NC}"
gcloud config set project $PROJECT_ID

# Create GitHub Actions service account
echo -e "${YELLOW}👤 Creating GitHub Actions service account...${NC}"
if gcloud iam service-accounts describe ${GITHUB_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Service account ${GITHUB_SA_NAME} already exists${NC}"
else
    gcloud iam service-accounts create $GITHUB_SA_NAME \
        --display-name="GitHub Actions CD Service Account" \
        --description="Service account for automated deployments from GitHub Actions"
    echo -e "${GREEN}✅ Created service account ${GITHUB_SA_NAME}${NC}"
fi

# Create Cloud Run service account
echo -e "${YELLOW}👤 Creating Cloud Run service account...${NC}"
if gcloud iam service-accounts describe ${CLOUDRUN_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Service account ${CLOUDRUN_SA_NAME} already exists${NC}"
else
    gcloud iam service-accounts create $CLOUDRUN_SA_NAME \
        --display-name="TrackCast Dev Service Account" \
        --description="Service account for TrackCast application in development"
    echo -e "${GREEN}✅ Created service account ${CLOUDRUN_SA_NAME}${NC}"
fi

# Assign roles to GitHub Actions service account
echo -e "${YELLOW}🔐 Assigning roles to GitHub Actions service account...${NC}"
GITHUB_SA_EMAIL="${GITHUB_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

declare -a roles=(
    "roles/run.admin"
    "roles/artifactregistry.writer"
    "roles/cloudbuild.builds.editor"
    "roles/secretmanager.secretAccessor"
    "roles/iam.serviceAccountUser"
    "roles/editor"
)

for role in "${roles[@]}"; do
    echo -e "  Assigning ${role}..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${GITHUB_SA_EMAIL}" \
        --role="$role" \
        --quiet
done

# Assign bucket permissions for Terraform state
echo -e "${YELLOW}🗂️ Assigning Terraform state bucket permissions...${NC}"
STATE_BUCKET="${PROJECT_ID}-terraform-state"
if gsutil ls "gs://${STATE_BUCKET}" > /dev/null 2>&1; then
    gsutil iam ch serviceAccount:${GITHUB_SA_EMAIL}:objectAdmin gs://${STATE_BUCKET}
    echo -e "${GREEN}✅ Granted bucket permissions${NC}"
else
    echo -e "${YELLOW}⚠️ Terraform state bucket ${STATE_BUCKET} not found. You may need to run Terraform setup first.${NC}"
fi

# Assign roles to Cloud Run service account
echo -e "${YELLOW}🔐 Assigning roles to Cloud Run service account...${NC}"
CLOUDRUN_SA_EMAIL="${CLOUDRUN_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

declare -a cloudrun_roles=(
    "roles/secretmanager.secretAccessor"
    "roles/cloudsql.client"
)

for role in "${cloudrun_roles[@]}"; do
    echo -e "  Assigning ${role}..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
        --role="$role" \
        --quiet
done

# Create Secret Manager secret
echo -e "${YELLOW}🔒 Creating Secret Manager secret...${NC}"
if gcloud secrets describe $SECRET_NAME > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Secret ${SECRET_NAME} already exists${NC}"
else
    # Create secret with placeholder values
    gcloud secrets create $SECRET_NAME \
        --data-file=<(cat << EOF
{
  "DATABASE_URL": "postgresql://user:password@host:5432/trackcast_dev",
  "NJT_USERNAME": "your-nj-transit-username",
  "NJT_PASSWORD": "your-nj-transit-password"
}
EOF
)
    echo -e "${GREEN}✅ Created secret ${SECRET_NAME} with placeholder values${NC}"
    echo -e "${YELLOW}⚠️ Remember to update the secret with real values!${NC}"
fi

# Grant secret access to Cloud Run service account
gcloud secrets add-iam-policy-binding $SECRET_NAME \
    --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet

# Generate service account key
echo -e "${YELLOW}🔑 Generating service account key for GitHub...${NC}"
KEY_FILE="github-actions-key.json"
gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$GITHUB_SA_EMAIL

echo ""
echo -e "${GREEN}✅ Setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo -e "1. ${YELLOW}Add the following secret to your GitHub repository:${NC}"
echo -e "   Secret name: ${GREEN}GCP_SA_KEY${NC}"
echo -e "   Secret value: Contents of ${KEY_FILE}"
echo ""
echo -e "2. ${YELLOW}Update the Secret Manager secret with real values:${NC}"
echo -e "   ${BLUE}gcloud secrets versions add ${SECRET_NAME} --data-file=your-secrets.json${NC}"
echo ""
echo -e "3. ${YELLOW}Enable required APIs (if not already enabled):${NC}"
echo -e "   ${BLUE}gcloud services enable run.googleapis.com${NC}"
echo -e "   ${BLUE}gcloud services enable artifactregistry.googleapis.com${NC}"
echo -e "   ${BLUE}gcloud services enable cloudbuild.googleapis.com${NC}"
echo -e "   ${BLUE}gcloud services enable secretmanager.googleapis.com${NC}"
echo ""
echo -e "${RED}🔒 Security reminder: Delete the key file after adding it to GitHub:${NC}"
echo -e "   ${BLUE}rm ${KEY_FILE}${NC}"
echo ""

# Display the key file content for easy copying
echo -e "${YELLOW}📄 Service account key file content (copy this to GitHub):${NC}"
echo -e "${BLUE}================== START OF KEY ==================${NC}"
cat $KEY_FILE
echo -e "${BLUE}=================== END OF KEY ====================${NC}"
echo ""
echo -e "${RED}⚠️ This key provides access to your GCP project. Keep it secure!${NC}"