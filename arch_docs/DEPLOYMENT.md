# TrackCast Cloud Run Deployment Guide

This guide covers the TrackCast system deployed on Google Cloud Platform using Cloud Run architecture with fully automated CI/CD.

## Overview

The TrackCast system is deployed as a cloud-native application with the following characteristics:

- **Serverless**: Auto-scaling Cloud Run services
- **Automated CI/CD**: GitHub Actions handles build, test, and deployment
- **Cloud SQL**: Managed PostgreSQL database
- **Secret Manager**: Secure credential storage
- **Multi-environment**: Separate dev, staging, and production deployments
- **Health monitoring**: Comprehensive monitoring and alerting

## Deployment Architecture

### Cloud Run Services

**API Service (`trackrat-api-{env}`):**
- REST API for train data and predictions
- Auto-scales from 0 to configurable max instances
- Health checks and monitoring built-in
- Connected to Cloud SQL via VPC connector

**Scheduler Service (`trackrat-scheduler-{env}`):**
- Periodic data collection from NJ Transit and Amtrak APIs
- Triggered by Cloud Scheduler at regular intervals
- Processes data and generates track predictions
- Handles feature engineering and model updates

### Supporting Infrastructure

- **Cloud SQL**: Managed PostgreSQL database
- **Secret Manager**: API keys and database credentials
- **VPC**: Private networking for secure database access
- **Artifact Registry**: Container image storage
- **Cloud Scheduler**: Automated task scheduling

## Automated Deployment Process

### GitHub Actions CI/CD

The system deploys automatically via GitHub Actions on every push to the `main` branch:

**Workflow Steps:**
1. **Build**: Docker images built and pushed to Artifact Registry
2. **Infrastructure**: Terraform applies any infrastructure changes
3. **Deploy**: Cloud Run services updated with new images
4. **Migrate**: Database migrations run via Cloud Run jobs
5. **Test**: Health checks and API endpoint verification
6. **Monitor**: Deployment status reporting

**Triggered by:**
- Push to `main` branch
- Changes to `backend/**` or `infra/**` paths
- Manual workflow dispatch

### Manual Deployment (Emergency)

If GitHub Actions is unavailable:

```bash
# 1. Build and push image
cd backend
docker build -t us-central1-docker.pkg.dev/PROJECT_ID/REPO/SERVICE:latest .
docker push us-central1-docker.pkg.dev/PROJECT_ID/REPO/SERVICE:latest

# 2. Deploy via Terraform
cd ../infra/environments/prod
terraform apply -var="api_image_url=IMAGE_URL"

# 3. Run database migrations
gcloud run jobs create temp-migrate \
  --image=IMAGE_URL \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args=init-db
gcloud run jobs execute temp-migrate --region=us-central1 --wait
gcloud run jobs delete temp-migrate --region=us-central1 --quiet
```

## Environment Configuration

### Development Environment
- **Project**: `trackrat-dev`
- **Region**: `us-central1`
- **Services**: 
  - API: `trackrat-api-dev`
  - Scheduler: `trackrat-scheduler-dev`
- **Database**: `trackcast-dev-sql`
- **Secrets**: `trackrat-dev-secrets`

### Production Environment
- **Project**: `trackrat-prod`
- **Region**: `us-central1`
- **Services**:
  - API: `trackrat-api-prod`
  - Scheduler: `trackrat-scheduler-prod`
- **Database**: `trackcast-prod-sql`
- **Secrets**: `trackrat-prod-secrets`
- **Custom Domain**: `api.trackrat.com` (configurable)

### Service Configuration

**API Service:**
```yaml
CPU: 1-2 vCPUs
Memory: 1-2 GB
Concurrency: 100 requests
Min Instances: 0 (dev), 1 (prod)
Max Instances: 10
Request Timeout: 60 seconds
```

**Scheduler Service:**
```yaml
CPU: 1 vCPU
Memory: 1 GB
Concurrency: 1 (single execution)
Min Instances: 0
Max Instances: 1
Request Timeout: 300 seconds
```

## Service URLs and Health Checks

### Development URLs
- **API**: https://trackrat-api-dev-[hash].a.run.app
- **Health**: https://trackrat-api-dev-[hash].a.run.app/health
- **API Docs**: https://trackrat-api-dev-[hash].a.run.app/docs

### Production URLs
- **API**: https://trackrat-api-prod-[hash].a.run.app
- **Health**: https://trackrat-api-prod-[hash].a.run.app/health
- **API Docs**: https://trackrat-api-prod-[hash].a.run.app/docs

### Health Check Response
```json
{
  "status": "healthy",
  "timestamp": 1703123456.789,
  "checks": {
    "database": {"status": "healthy", "message": "Connected"},
    "models": {"status": "healthy", "message": "7 models loaded"},
    "environment": {"status": "healthy", "message": "All configs loaded"}
  }
}
```

## Configuration Management

### Environment Variables

Set via Terraform and Cloud Run:

```yaml
# Non-sensitive configuration
environment_variables:
  APP_ENV: "production"
  GIN_MODE: "release"
  TRACKCAST_ENV: "prod"
  LOG_LEVEL: "INFO"

# Sensitive configuration (from Secret Manager)
secret_environment_variables:
  DATABASE_URL: "trackrat-prod-secrets:latest"
  NJT_USERNAME: "trackrat-prod-secrets:latest"
  NJT_PASSWORD: "trackrat-prod-secrets:latest"
```

### Secret Manager Configuration

Secrets are automatically created by Terraform and need to be populated:

```bash
# Update application secrets
echo '{
  "database_url": "postgresql://user:pass@host:5432/trackcast",
  "nj_transit_api_key": "your-nj-transit-key",
  "amtrak_api_key": "your-amtrak-key"
}' | gcloud secrets versions add trackrat-prod-secrets --data-file=-

# Verify secret versions
gcloud secrets versions list trackrat-prod-secrets
```

### Infrastructure Deployment

Infrastructure is deployed automatically via GitHub Actions, but can be deployed manually:

```bash
# Deploy infrastructure only
cd infra/environments/prod
terraform init
terraform plan
terraform apply

# Deploy with specific image
terraform apply -var="api_image_url=us-central1-docker.pkg.dev/PROJECT/IMAGE:TAG"
```

## Data Operations

### Automated Data Collection

The scheduler service automatically:
- Collects data from NJ Transit and Amtrak APIs every 1-2 minutes
- Processes features and generates track predictions
- Updates the database with fresh train information
- Maintains data quality and handles API failures

### Manual Data Operations

```bash
# Trigger immediate data collection
gcloud scheduler jobs run invoke-trackrat-scheduler-prod --location=us-central1

# Run database migrations
gcloud run jobs create migrate-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args=init-db

# Clear old data
gcloud run jobs create cleanup-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="process-features --clear --time-range START_TIME END_TIME"

# Train new prediction models
gcloud run jobs create train-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="train-model --all-stations"
```

### Model Management

**Model Storage**: Models are built into the container image for Cloud Run deployment.

**Model Updates**:
1. Train new models using historical data
2. Update model files in the repository
3. Commit changes to trigger automatic deployment
4. New models are deployed with the next application update

**Model Training**:
```bash
# Train models for all stations
trackcast train-model --all-stations

# Train for specific station
trackcast train-model --station NY

# View training outputs
ls models/  # Model files and visualizations
```

## Monitoring and Observability

### Cloud Run Monitoring

**Service Metrics** (via Google Cloud Console):
- Request count and latency
- Error rates and response codes
- Instance scaling and CPU utilization
- Memory usage and network traffic

**Access Dashboards**:
- **Cloud Run**: https://console.cloud.google.com/run?project=PROJECT_ID
- **Cloud SQL**: https://console.cloud.google.com/sql?project=PROJECT_ID
- **Cloud Scheduler**: https://console.cloud.google.com/cloudscheduler?project=PROJECT_ID
- **Logs**: https://console.cloud.google.com/logs?project=PROJECT_ID

### Application Monitoring

```bash
# View service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=trackrat-api-prod" --limit=50

# Monitor error rates
gcloud logging read "resource.labels.service_name=trackrat-api-prod AND severity>=ERROR" --limit=20

# Check API performance
curl -w "@/dev/stdout" -o /dev/null -s "https://SERVICE_URL/api/trains/?limit=1"
```

### Data Quality Monitoring

```bash
# Check recent data collection
curl "https://SERVICE_URL/api/trains/?limit=10&sort_by=last_update&sort_order=desc"

# Verify station coverage
curl "https://SERVICE_URL/api/stops/"

# Monitor prediction quality
curl "https://SERVICE_URL/api/trains/123/prediction"
```

### Alerting

**Recommended Alerts**:
- Service health check failures
- High error rates (>5%)
- Response latency spikes (>2 seconds)
- Database connection failures
- Scheduler job failures
- No recent data updates (>1 hour)

## Security

### Built-in Security Features

✅ **Container Security**:
- Non-root user execution
- Minimal Python base image
- No sensitive data in images
- Dependency vulnerability scanning

✅ **Network Security**:
- VPC-based networking
- Private database connectivity
- HTTPS-only endpoints
- IAM-based access control

✅ **Secret Management**:
- Google Secret Manager integration
- Automatic secret rotation support
- No secrets in environment variables
- Least-privilege service accounts

### Security Operations

```bash
# Verify IAM permissions
gcloud projects get-iam-policy PROJECT_ID

# Check service account permissions
gcloud run services get-iam-policy trackrat-api-prod --region=us-central1

# Monitor security events
gcloud logging read "protoPayload.authenticationInfo.principalEmail AND severity>=WARNING" --limit=20

# Update secrets
gcloud secrets versions add trackrat-prod-secrets --data-file=new-secrets.json
```

### Security Best Practices

1. **Regular Updates**: Automatic via CI/CD pipeline
2. **Secret Rotation**: Rotate API keys quarterly
3. **Access Review**: Review IAM permissions monthly
4. **Monitoring**: Monitor for unusual access patterns
5. **Backups**: Maintain secure database backups

## Troubleshooting

### Common Issues

#### 1. Service Not Responding

```bash
# Check service status
gcloud run services describe trackrat-api-prod --region=us-central1

# View recent logs
gcloud logging read "resource.labels.service_name=trackrat-api-prod" --limit=20

# Test health endpoint
curl -v https://SERVICE_URL/health
```

**Solutions:**
- Verify database connectivity in Secret Manager
- Check CPU/Memory limits
- Ensure latest image is deployed
- Review VPC connector configuration

#### 2. Database Connection Issues

```bash
# Check database instance status
gcloud sql instances describe INSTANCE_NAME

# Test database connectivity
gcloud sql connect INSTANCE_NAME --user=trackcast

# Verify VPC connector
gcloud compute networks vpc-access connectors list --region=us-central1
```

**Solutions:**
- Verify database credentials in Secret Manager
- Check Cloud SQL authorization and networking
- Ensure VPC connector is operational
- Review firewall rules

#### 3. No Recent Data

```bash
# Check scheduler job status
gcloud scheduler jobs list --location=us-central1

# View scheduler execution history
gcloud logging read "resource.type=cloud_scheduler_job" --limit=10

# Manually trigger collection
gcloud scheduler jobs run invoke-trackrat-scheduler-prod --location=us-central1
```

**Solutions:**
- Verify API credentials in Secret Manager
- Check external API availability (NJ Transit, Amtrak)
- Review scheduler service logs
- Ensure scheduler service is deployed

#### 4. Deployment Issues

```bash
# Check GitHub Actions status
# Visit: https://github.com/USER/TrackRat/actions

# View Terraform state
cd infra/environments/prod
terraform show

# Check image availability
gcloud artifacts docker images list --repository=REPO_NAME --location=us-central1
```

**Solutions:**
- Review GitHub Actions logs for build failures
- Verify Terraform configuration
- Check Artifact Registry permissions
- Ensure all required secrets are configured

### Performance Optimization

#### Resource Scaling

```bash
# Adjust CPU/Memory allocation
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --cpu=2 \
  --memory=4Gi

# Configure concurrency
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --concurrency=200

# Set instance scaling
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=10
```

#### Database Performance

```bash
# Monitor database metrics
gcloud sql operations list --instance=INSTANCE_NAME

# Scale database if needed
gcloud sql instances patch INSTANCE_NAME \
  --tier=db-standard-2

# Enable performance insights
gcloud sql instances patch INSTANCE_NAME \
  --insights-config-query-insights-enabled
```

#### Cost Optimization

- **Right-size resources**: Monitor actual CPU/Memory usage
- **Optimize scaling**: Set appropriate min/max instances
- **Request efficiency**: Implement caching where appropriate
- **Database tier**: Use appropriate Cloud SQL tier for workload

## Backup and Recovery

### Automated Backups

**Database Backups**:
- Cloud SQL automatic backups (daily)
- Point-in-time recovery enabled
- 7-day backup retention (configurable)

**Configuration Backups**:
- Terraform state in Cloud Storage (versioned)
- Container images in Artifact Registry
- Secrets in Secret Manager (versioned)

### Recovery Procedures

```bash
# List available database backups
gcloud sql backups list --instance=INSTANCE_NAME

# Restore from backup
gcloud sql backups restore BACKUP_ID --restore-instance=INSTANCE_NAME

# Rollback to previous image
gcloud run services update trackrat-api-prod \
  --image=us-central1-docker.pkg.dev/PROJECT/REPO:PREVIOUS_TAG \
  --region=us-central1
```

**Disaster Recovery**:
- RTO (Recovery Time Objective): ~15 minutes
- RPO (Recovery Point Objective): ~5 minutes
- Full infrastructure can be rebuilt from Terraform
- Application can be redeployed from any git commit

## Additional Resources

### Documentation
- **Operations Guide**: `/OPERATORS_GUIDE.md` - Comprehensive operational procedures
- **Infrastructure Guide**: `/infra/CLAUDE.md` - Terraform and infrastructure details
- **API Documentation**: Available at `https://SERVICE_URL/docs`

### Monitoring Dashboards
- **Cloud Run Console**: https://console.cloud.google.com/run
- **Cloud SQL Console**: https://console.cloud.google.com/sql
- **GitHub Actions**: https://github.com/USER/TrackRat/actions
- **Cloud Logging**: https://console.cloud.google.com/logs

### Support
- **Health Checks**: Monitor service health endpoints
- **Logs**: Use Cloud Logging for troubleshooting
- **Metrics**: Cloud Monitoring for performance data
- **Alerts**: Set up alerts for critical issues

---

*For detailed operational procedures, see `/OPERATORS_GUIDE.md`. For infrastructure details, see `/infra/CLAUDE.md`.*