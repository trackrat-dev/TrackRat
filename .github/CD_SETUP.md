# Continuous Deployment Setup Guide

This guide explains how to set up the automated deployment pipeline for the TrackRat development environment.

## Prerequisites

1. **Google Cloud Project**: Ensure `trackrat-dev` project exists
2. **Terraform Infrastructure**: Base infrastructure should be deployed via `infra/environments/dev/`
3. **GitHub Repository**: Access to repository settings for secrets

## Service Account Setup

### 1. Create Service Account for GitHub Actions

```bash
# Set project
export PROJECT_ID="trackrat-dev"
gcloud config set project $PROJECT_ID

# Create service account
gcloud iam service-accounts create github-actions-cd \
    --display-name="GitHub Actions CD Service Account" \
    --description="Service account for automated deployments from GitHub Actions"

# Get service account email
export SA_EMAIL="github-actions-cd@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 2. Assign Required IAM Roles

```bash
# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.admin"

# Artifact Registry permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/artifactregistry.writer"

# Cloud Build permissions (for docker builds)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudbuild.builds.editor"

# Secret Manager permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

# IAM permissions (needed for service account impersonation)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"

# Terraform state bucket permissions
export STATE_BUCKET="${PROJECT_ID}-terraform-state"
gsutil iam ch serviceAccount:${SA_EMAIL}:objectAdmin gs://${STATE_BUCKET}

# Terraform deployment permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/editor"
```

### 3. Create and Download Service Account Key

```bash
# Create key file
gcloud iam service-accounts keys create ~/github-actions-key.json \
    --iam-account=$SA_EMAIL

# Display the key (copy this for GitHub secrets)
cat ~/github-actions-key.json

# Clean up local key file (security best practice)
rm ~/github-actions-key.json
```

## GitHub Secrets Configuration

### Required Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

1. **`GCP_SA_KEY`** (Required)
   - The full JSON content from the service account key file
   - Used for authenticating to Google Cloud

### Example Secret Values

```json
{
  "type": "service_account",
  "project_id": "trackrat-dev",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "github-actions-cd@trackrat-dev.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

## Secret Manager Setup

### Create Application Secrets

The application requires these secrets in Google Secret Manager:

```bash
# Create secret with placeholder values (update these with real values)
gcloud secrets create trackcast-dev-secrets \
    --data-file=<(echo '{
  "database_url": "postgresql://user:pass@host:5432/trackcast_dev",
  "nj_transit_api_key": "your-nj-transit-api-key",
  "amtrak_api_key": "your-amtrak-api-key"
}')

# Grant access to the Cloud Run service account
gcloud secrets add-iam-policy-binding trackcast-dev-secrets \
    --member="serviceAccount:trackcast-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Update Secret Values

```bash
# Update with real database URL
echo "postgresql://user:pass@host:5432/trackcast_dev" | \
gcloud secrets versions add trackcast-dev-secrets --data-file=-

# Or update the entire secret JSON:
gcloud secrets versions add trackcast-dev-secrets --data-file=secrets.json
```

## Cloud Run Service Account

### Create Service Account for Cloud Run

```bash
# Create service account for the running application
gcloud iam service-accounts create trackcast-dev-sa \
    --display-name="TrackCast Dev Service Account" \
    --description="Service account for TrackCast application in development"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:trackcast-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Grant Cloud SQL Client role (if using Cloud SQL)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:trackcast-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
```

## GitHub Environments

### Create Development Environment

1. Go to your repository settings
2. Navigate to "Environments"
3. Create a new environment called "development"
4. Optionally add environment-specific protection rules

## Verification Steps

### 1. Test GitHub Actions Authentication

Create a simple workflow to test authentication:

```yaml
name: Test GCP Auth
on: workflow_dispatch

jobs:
  test-auth:
    runs-on: ubuntu-latest
    steps:
    - uses: google-github-actions/auth@v2
      with:
        credentials_json: ${{ secrets.GCP_SA_KEY }}
    - uses: google-github-actions/setup-gcloud@v2
    - run: gcloud projects list
```

### 2. Test Terraform Access

```bash
# In infra/environments/dev/
terraform init
terraform plan
```

### 3. Test Secret Manager Access

```bash
gcloud secrets versions access latest --secret="trackcast-dev-secrets"
```

### 4. Test Cloud Run Deployment

```bash
# Manual deployment test
gcloud run deploy trackcast-test \
  --image=gcr.io/cloudrun/hello \
  --region=us-central1 \
  --allow-unauthenticated \
  --service-account=trackcast-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Verify service account has all required roles
2. **Secret Not Found**: Ensure Secret Manager secret exists and has correct name
3. **Docker Push Failed**: Check Artifact Registry permissions and repository exists
4. **Terraform State Lock**: Ensure service account has bucket permissions

### Debug Commands

```bash
# Check service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:github-actions-cd@${PROJECT_ID}.iam.gserviceaccount.com"

# List secrets
gcloud secrets list

# Check Cloud Run services
gcloud run services list --region=us-central1

# View Cloud Run logs
gcloud run services logs read trackcast-inference --region=us-central1
```

## Security Best Practices

1. **Least Privilege**: Only grant minimum required permissions
2. **Rotate Keys**: Regularly rotate service account keys
3. **Monitor Access**: Enable Cloud Audit Logs for service account usage
4. **Separate Environments**: Use different service accounts for different environments

## Next Steps

After setup is complete:

1. Push code to main branch to trigger deployment
2. Monitor GitHub Actions workflow execution
3. Verify application is running in Cloud Run
4. Check application logs for any startup errors
5. Test API endpoints to ensure functionality

## Monitoring Deployment Success

- **GitHub Actions**: Check workflow status in repository Actions tab
- **Cloud Run**: Monitor service health in GCP Console
- **Logs**: Check Cloud Run logs for application startup and errors
- **Health Check**: Verify `/health` endpoint returns success