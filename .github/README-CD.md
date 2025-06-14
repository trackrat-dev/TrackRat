# TrackRat Continuous Deployment

This directory contains the GitHub Actions workflows and configuration for automated deployment of TrackRat to the development environment.

## Overview

The CD system automatically deploys changes to the development environment when:
- All tests pass on the `main` branch
- Changes are made to backend code or infrastructure

## Workflows

### 1. Infrastructure Deployment (`terraform-cd-dev.yml`)
- **Triggers**: Changes to `infra/**` on main branch
- **Purpose**: Deploys Terraform infrastructure changes to dev environment
- **Runs**: After Terraform CI passes
- **Deployment**: Fully automated, no manual approval required

### 2. Application Deployment (`deploy-dev.yml`)
- **Triggers**: Changes to `backend/**` on main branch
- **Purpose**: Builds and deploys application to Cloud Run
- **Runs**: After Backend Tests and Docker Build Test pass
- **Deployment**: Fully automated, no manual approval required

### 3. CD Setup Test (`test-cd-setup.yml`)
- **Triggers**: Manual workflow dispatch
- **Purpose**: Validates CD configuration and permissions
- **Tests**: Authentication, Terraform, Docker, Secret Manager access

## Setup Instructions

### Quick Setup
1. Run the automated setup script:
   ```bash
   ./.github/setup-cd.sh
   ```

2. Add the generated service account key to GitHub secrets as `GCP_SA_KEY`

3. Update Secret Manager with real application secrets

### Manual Setup
See [CD_SETUP.md](CD_SETUP.md) for detailed manual setup instructions.

## Security Configuration

### GitHub Secrets Required
- `GCP_SA_KEY`: Service account key for Google Cloud authentication

### Google Cloud Resources
- **Service Accounts**:
  - `github-actions-cd@trackrat-dev.iam.gserviceaccount.com` (for deployments)
  - `trackcast-dev-sa@trackrat-dev.iam.gserviceaccount.com` (for running application)
- **Secret Manager**: `trackcast-dev-secrets` with application credentials
- **Artifact Registry**: `trackcast-inference-dev` repository

## Deployment Process

### Infrastructure Changes
1. Change Terraform files in `infra/**`
2. Push to main branch
3. Terraform CI validates changes
4. Infrastructure deployment runs automatically
5. Changes applied to dev environment

### Application Changes
1. Change backend code in `backend/**`
2. Push to main branch
3. Backend tests and Docker build run
4. Application deployment runs automatically:
   - Builds Docker image
   - Pushes to Artifact Registry
   - Runs database migrations
   - Deploys to Cloud Run
   - Performs health checks

## Monitoring Deployments

### GitHub Actions
- View workflow runs in the "Actions" tab
- Check deployment status and logs
- Review step-by-step execution

### Google Cloud Console
- **Cloud Run**: Monitor service health and logs
- **Artifact Registry**: View pushed container images
- **Secret Manager**: Verify secret access

### Health Checks
All deployments include automated health checks:
- Service startup verification
- API endpoint testing
- Database connectivity validation

## Troubleshooting

### Common Issues

#### 1. Authentication Failed
```
Error: google: could not find default credentials
```
**Solution**: Verify `GCP_SA_KEY` secret is correctly set in GitHub.

#### 2. Permission Denied
```
Error: User does not have permission to access the repository
```
**Solution**: Check service account IAM roles and permissions.

#### 3. Docker Push Failed
```
Error: unauthorized: authentication required
```
**Solution**: Ensure Artifact Registry exists and service account has writer permissions.

#### 4. Cloud Run Deployment Failed
```
Error: revision is not ready and cannot serve traffic
```
**Solution**: Check Cloud Run logs for application startup errors.

#### 5. Secret Manager Access Denied
```
Error: Permission denied on secret
```
**Solution**: Verify service account has Secret Manager access and secret exists.

### Debug Commands

```bash
# Test authentication
gcloud auth list

# Check service account permissions
gcloud projects get-iam-policy trackrat-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:github-actions-cd@trackrat-dev.iam.gserviceaccount.com"

# View Cloud Run service
gcloud run services describe trackcast-inference --region=us-central1

# Check secret access
gcloud secrets versions access latest --secret="trackcast-dev-secrets"

# View logs
gcloud run services logs read trackcast-inference --region=us-central1
```

## Validation

### Test Your Setup
Run the CD setup test workflow manually:
1. Go to Actions tab in GitHub
2. Select "Test CD Setup" workflow
3. Click "Run workflow"
4. Choose test type (auth, terraform, docker, full)
5. Review results

### Validation Checklist
- [ ] Service accounts created with correct permissions
- [ ] GitHub secret `GCP_SA_KEY` configured
- [ ] Secret Manager secret exists with application credentials
- [ ] Artifact Registry repository exists
- [ ] Required APIs enabled in GCP project
- [ ] Terraform state bucket accessible
- [ ] Cloud Run service account configured

## Workflow Triggers

### Automatic Triggers
- **Push to main**: Triggers deployment if tests pass
- **Workflow completion**: Infrastructure deployment after Terraform CI
- **Path filtering**: Only runs when relevant files change

### Manual Triggers
- **test-cd-setup.yml**: Manual testing of CD configuration
- **Workflow dispatch**: Available on all deployment workflows

## Environment Variables

### Infrastructure Deployment
- `TF_VERSION`: Terraform version to use
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key

### Application Deployment
- `PROJECT_ID`: GCP project ID (trackrat-dev)
- `REGION`: GCP region (us-central1)
- `SERVICE_NAME`: Cloud Run service name
- `REPOSITORY`: Artifact Registry repository name

## Security Best Practices

1. **Least Privilege**: Service accounts have minimum required permissions
2. **Secure Secrets**: All sensitive data stored in Secret Manager
3. **No Hardcoded Credentials**: All authentication via service account keys
4. **Audit Logging**: All deployments logged and auditable
5. **Environment Isolation**: Dev environment completely separate

## Limitations

### Current Scope
- **Development environment only**: No staging or production deployment
- **No manual approval gates**: Fully automated deployment
- **Basic rollback**: Manual rollback via Cloud Run console
- **Limited monitoring**: Basic health checks only

### Future Enhancements
- Multi-environment promotion pipeline
- Blue/green deployments
- Advanced monitoring and alerting
- Automated rollback on failure
- Performance testing integration

## Support

For issues with the CD system:
1. Check workflow logs in GitHub Actions
2. Review [CD_SETUP.md](CD_SETUP.md) for configuration details
3. Use the test workflow to validate setup
4. Check Google Cloud Console for resource status

## Files

- `terraform-cd-dev.yml`: Infrastructure deployment workflow
- `deploy-dev.yml`: Application deployment workflow
- `test-cd-setup.yml`: CD setup validation workflow
- `CD_SETUP.md`: Detailed setup instructions
- `setup-cd.sh`: Automated setup script
- `README-CD.md`: This file