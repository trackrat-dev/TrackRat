# TrackRat Operations Guide

This guide provides comprehensive operational procedures for the deployed TrackRat system running on Google Cloud Platform with Cloud Run architecture.

## System Overview

TrackRat is a fully automated train tracking and prediction system with the following architecture:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │     │   Cloud Run     │     │   Frontends     │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • API Service   │────▶│ • iOS App       │
│ • Amtrak APIs   │     │ • Scheduler     │     │ • Web App       │
│                 │     │ • Collector     │     │ • Live Activity │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                        ┌───────▼────────┐
                        │   PostgreSQL   │
                        │   (Cloud SQL)  │
                        └────────────────┘
```

### Key Components

- **API Service**: REST API for train data and predictions (`trackrat-api-{env}`)
- **Scheduler Service**: Periodic data collection and processing (`trackrat-scheduler-{env}`)
- **Cloud Scheduler**: Triggers scheduler service at regular intervals
- **Cloud SQL**: PostgreSQL database for all data storage
- **Secret Manager**: Secure storage for API keys and database credentials
- **Artifact Registry**: Container image storage

## Automated Operations

### What Runs Automatically

✅ **CI/CD Pipeline**: On every push to `main` branch:
1. Builds Docker images and pushes to Artifact Registry
2. Deploys infrastructure changes via Terraform
3. Updates Cloud Run services with new images
4. Runs database migrations via temporary Cloud Run jobs
5. Performs health checks and API endpoint testing

✅ **Data Collection**: Cloud Scheduler automatically triggers:
- Data collection from NJ Transit and Amtrak APIs
- Feature processing and track predictions
- Database updates every 1-2 minutes

✅ **Auto-scaling**: Cloud Run automatically scales based on:
- Request volume (API service)
- Scheduled workloads (Scheduler service)
- Resource utilization

✅ **Health Monitoring**: Built-in health checks:
- Startup probes ensure services are ready
- Liveness probes restart unhealthy instances
- GitHub workflow validates deployment health

## Deployment Process

### Automatic Deployment

The system deploys automatically via GitHub Actions:

1. **Trigger**: Push to `main` branch or manual workflow dispatch
2. **Build**: Docker image built and tagged with commit SHA
3. **Infrastructure**: Terraform applies any infrastructure changes
4. **Deploy**: Cloud Run services updated with new image
5. **Migrate**: Database migrations run automatically
6. **Verify**: Health checks and API endpoint testing

### Manual Deployment (if needed)

If you need to deploy manually:

```bash
# 1. Build and push image
cd backend
docker build -t us-central1-docker.pkg.dev/PROJECT_ID/REPO/SERVICE:latest .
docker push us-central1-docker.pkg.dev/PROJECT_ID/REPO/SERVICE:latest

# 2. Deploy infrastructure
cd ../infra/environments/dev  # or staging/prod
terraform init
terraform plan -var="api_image_url=IMAGE_URL"
terraform apply

# 3. Run migrations
gcloud run jobs create temp-migrate \
  --image=IMAGE_URL \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=SECRET_NAME:latest \
  --command=trackcast --args=init-db
gcloud run jobs execute temp-migrate --region=us-central1 --wait
gcloud run jobs delete temp-migrate --region=us-central1 --quiet
```

## Monitoring and Observability

TrackRat provides comprehensive monitoring through:
- Health endpoints for real-time status
- Prometheus metrics for detailed tracking
- Cloud Monitoring dashboards for visual insights
- Automatic model accuracy tracking

### Service URLs

**Development:**
- API: https://trackrat-api-dev-[hash].a.run.app
- Health: https://trackrat-api-dev-[hash].a.run.app/health

**Production:**
- API: https://trackrat-api-prod-[hash].a.run.app
- Health: https://trackrat-api-prod-[hash].a.run.app/health

### Key Health Endpoints

```bash
# Overall system health
curl https://SERVICE_URL/health

# API endpoints status
curl https://SERVICE_URL/api/trains/?limit=1
curl https://SERVICE_URL/api/stops/

# Example healthy response
{
  "status": "healthy",
  "database": {
    "connected": true,
    "latency_ms": 2.5
  },
  "data_freshness": {
    "latest_train": "2025-06-01T20:30:00",
    "minutes_ago": 2
  },
  "processing_metrics": {
    "trains_last_hour": 156,
    "trains_last_24h": 3421,
    "by_source": {
      "njtransit": 2845,
      "amtrak": 576
    }
  },
  "quality_metrics": {
    "track_assignment_rate": 0.78,
    "prediction_rate": 0.92,
    "accuracy_last_24h": 0.85
  }
}
```

### Monitoring Dashboards

Access via Google Cloud Console:

1. **Cloud Run Services**: 
   - https://console.cloud.google.com/run?project=PROJECT_ID
   - View service metrics, logs, and scaling

2. **Cloud SQL Database**:
   - https://console.cloud.google.com/sql?project=PROJECT_ID
   - Monitor database performance and connections

3. **Cloud Scheduler Jobs**:
   - https://console.cloud.google.com/cloudscheduler?project=PROJECT_ID
   - View job execution history and success rates

4. **Secret Manager**:
   - https://console.cloud.google.com/security/secret-manager?project=PROJECT_ID
   - Manage API keys and database credentials

5. **Cloud Monitoring Dashboards**:
   - https://console.cloud.google.com/monitoring/dashboards?project=PROJECT_ID
   - Access custom dashboards created by Terraform:
     - **Executive Dashboard**: System health score, daily trains processed, API uptime
     - **Operations Dashboard**: Service latency, error rates, database performance
     - **Business KPIs Dashboard**: Train processing volume, API usage patterns
     - **Troubleshooting Dashboard**: Error logs, performance bottlenecks

### Prometheus Metrics

The API service exposes Prometheus metrics at `/metrics`:

```bash
# View raw metrics
curl https://SERVICE_URL/metrics

# Key metrics to monitor:
# - model_prediction_accuracy: Track prediction accuracy by station
# - trains_processed_total: Total trains processed
# - track_prediction_confidence_ratio: Confidence score distribution
# - nj_transit_fetch_success_total: API success rate
# - model_inference_time_seconds: Model performance
```

### Log Analysis

```bash
# View API service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=trackrat-api-dev" --limit=50 --format=json

# View scheduler service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=trackrat-scheduler-dev" --limit=50 --format=json

# Filter by error level
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=20
```

## Configuration Management

### Environment Variables

Key configuration is managed via Cloud Run environment variables:

```yaml
# Set via Terraform
environment_variables = {
  APP_ENV = "production"
  GIN_MODE = "release"
  TRACKCAST_ENV = "prod"
}

# Secrets (from Secret Manager)
secret_environment_variables = {
  DATABASE_URL = "trackrat-prod-secrets:latest"
  NJT_USERNAME = "trackrat-prod-secrets:latest"  
  NJT_PASSWORD = "trackrat-prod-secrets:latest"
}
```

### Secret Management

Secrets are automatically created by Terraform but need to be populated:

```bash
# Update application secrets
gcloud secrets versions add trackrat-prod-secrets --data-file=secrets.json

# Example secrets.json format:
{
  "database_url": "postgresql://user:pass@host:5432/trackcast",
  "nj_transit_api_key": "your-nj-transit-key",
  "amtrak_api_key": "your-amtrak-key"
}

# View secret versions
gcloud secrets versions list trackrat-prod-secrets
```

### Configuration Updates

To update application configuration:

1. **Environment Variables**: Update Terraform variables and apply
2. **Secrets**: Update Secret Manager versions (auto-loaded)
3. **Application Code**: Push changes to trigger automatic deployment

## Data Operations

### Data Collection Status

Check data collection status:

```bash
# View recent trains collected
curl "https://SERVICE_URL/api/trains/?limit=10&sort_by=last_update&sort_order=desc"

# Check data sources
curl "https://SERVICE_URL/api/trains/?data_source=njtransit&limit=5"
curl "https://SERVICE_URL/api/trains/?data_source=amtrak&limit=5"

# Monitor scheduler job execution
gcloud scheduler jobs describe invoke-trackrat-scheduler-prod --location=us-central1
```

### Database Operations

```bash
# Run database migrations
gcloud run jobs create migrate-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args=init-db

# Clear old data (if needed)
gcloud run jobs create cleanup-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="process-features --clear --time-range 2025-01-01T00:00:00 2025-01-31T23:59:59"

# Train new models
gcloud run jobs create train-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="train-model --all-stations"
```

### Prediction Management

The `generate-predictions` command now supports advanced filtering for both generating and clearing predictions:

```bash
# Generate predictions for all trains needing them
gcloud run jobs create predict-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions"

# Generate predictions for future trains only
gcloud run jobs create predict-future-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --future"

# Clear and regenerate predictions for future trains (recommended for fresh predictions)
gcloud run jobs create refresh-predictions-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --clear --future"

# Generate predictions for specific train
gcloud run jobs create predict-train-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --train-id 7001"

# Generate predictions for trains in a time range
gcloud run jobs create predict-range-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --time-range 2025-06-17T10:00:00 2025-06-17T18:00:00"

# Clear all predictions
gcloud run jobs create clear-predictions-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --clear"

# Clear predictions for specific train
gcloud run jobs create clear-train-$(date +%s) \
  --image=LATEST_IMAGE \
  --region=us-central1 \
  --set-secrets=DATABASE_URL=trackrat-prod-secrets:latest \
  --command=trackcast --args="generate-predictions --clear --train-id 7001"
```

**Available Filtering Options:**
- `--train-id TEXT`: Filter to a specific train ID
- `--time-range START END`: Filter to trains within a time range (ISO format)
- `--future`: Filter to trains with future departure times
- `--clear`: Clear predictions instead of generating them

**Important Notes:**
- Only one filtering option can be used at a time
- All filters work with both generation (`--clear` omitted) and clearing (`--clear` included) modes
- Use `--future` flag to continuously refresh predictions for upcoming trains without affecting historical data
- Time range format: `YYYY-MM-DDTHH:MM:SS` (ISO 8601)

### Data Quality Monitoring

Monitor data quality via API endpoints:

```bash
# Check for recent data updates
curl "https://SERVICE_URL/api/trains/?departure_time_after=$(date -d '1 hour ago' -Iseconds)"

# Verify station coverage
curl "https://SERVICE_URL/api/stops/"

# Check prediction quality
curl "https://SERVICE_URL/api/trains/123/prediction"
```

### Model Accuracy Monitoring

The system automatically tracks prediction accuracy when actual tracks are assigned:

```bash
# View current accuracy metrics
curl https://SERVICE_URL/metrics | grep model_prediction_accuracy

# Check accuracy via health endpoint
curl https://SERVICE_URL/health | jq '.quality_metrics.accuracy_last_24h'

# Monitor accuracy trends in Cloud Monitoring
# Executive Dashboard > Prediction Accuracy Trends widget
```

**Accuracy Tracking Process:**
1. When a train's actual track is assigned, the system compares it with the predicted track
2. Accuracy is recorded as 1.0 (correct) or 0.0 (incorrect) by station
3. Metrics are exposed via Prometheus and displayed in dashboards
4. Alerts can be configured for accuracy drops below thresholds

**Response to Low Accuracy:**
- Check for API data quality issues
- Review recent system changes
- Consider retraining models with recent data
- Verify station-specific patterns haven't changed

## Troubleshooting

### Common Issues

#### 1. Service Not Responding

```bash
# Check service status
gcloud run services describe trackrat-api-prod --region=us-central1

# View recent logs
gcloud logging read "resource.labels.service_name=trackrat-api-prod" --limit=20

# Check health endpoint
curl -v https://SERVICE_URL/health
```

**Solutions:**
- Verify database connectivity
- Check secret configuration
- Review resource limits (CPU/Memory)
- Ensure latest image deployed

#### 2. Service Startup Failures

```bash
# Check startup logs
gcloud logging read "resource.labels.service_name=trackrat-api-prod AND textPayload:'Starting'" --limit=50

# Monitor startup probe status
gcloud run services describe trackrat-api-prod --region=us-central1 --format="value(spec.template.spec.containers[0].startupProbe)"

# Check model loading logs
gcloud logging read "resource.labels.service_name=trackrat-api-prod AND textPayload:'Loading model'" --limit=20
```

**Solutions:**
- Allow adequate startup time (10 minutes for ML models)
- Verify model files are included in Docker image
- Check memory allocation during model loading
- Review startup probe configuration:
  - Initial delay: 30 seconds
  - Period: 15 seconds  
  - Failure threshold: 40 attempts
- Consider increasing memory allocation for model loading

#### 3. Database Connection Issues

```bash
# Test database connectivity
gcloud sql connect INSTANCE_NAME --user=trackcast

# Check Cloud SQL status
gcloud sql instances describe INSTANCE_NAME

# Verify VPC connector
gcloud compute networks vpc-access connectors list --region=us-central1
```

**Solutions:**
- Verify database credentials in Secret Manager
- Check VPC connectivity
- Ensure database instance is running
- Review firewall rules

#### 4. No Recent Data

```bash
# Check scheduler job status
gcloud scheduler jobs list --location=us-central1

# View scheduler execution history
gcloud logging read "resource.type=cloud_scheduler_job" --limit=10

# Manually trigger data collection
gcloud scheduler jobs run invoke-trackrat-scheduler-prod --location=us-central1
```

**Solutions:**
- Verify API credentials in Secret Manager
- Check external API availability
- Review scheduler configuration
- Examine scheduler service logs

#### 5. High Error Rates

```bash
# Check error logs
gcloud logging read "resource.labels.service_name=trackrat-api-prod AND severity>=ERROR" --limit=20

# Monitor service metrics
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
```

**Solutions:**
- Review application logs for specific errors
- Check resource allocation (CPU/Memory limits)
- Verify external API status
- Consider scaling adjustments

### Performance Optimization

#### Resource Scaling

```bash
# Update CPU/Memory allocation
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --cpu=2 \
  --memory=4Gi

# Adjust concurrency
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --concurrency=200

# Set min/max instances
gcloud run services update trackrat-api-prod \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=10
```

#### Database Performance

```bash
# Monitor database metrics
gcloud sql operations list --instance=INSTANCE_NAME

# Analyze slow queries
gcloud sql instances patch INSTANCE_NAME \
  --database-flags=log_min_duration_statement=1000

# Scale database if needed
gcloud sql instances patch INSTANCE_NAME \
  --tier=db-standard-2
```

## Security Operations

### Access Control

Verify IAM permissions:

```bash
# Check service account permissions
gcloud projects get-iam-policy PROJECT_ID

# Verify Cloud Run invoker permissions
gcloud run services get-iam-policy trackrat-api-prod --region=us-central1

# Check Secret Manager access
gcloud secrets get-iam-policy trackrat-prod-secrets
```

### Security Monitoring

```bash
# Check for failed authentication attempts
gcloud logging read "protoPayload.authenticationInfo.principalEmail AND severity>=WARNING" --limit=20

# Monitor unusual access patterns
gcloud logging read "resource.type=cloud_run_revision AND httpRequest.status>=400" --limit=20

# Review VPC firewall logs
gcloud logging read "resource.type=gce_firewall_rule" --limit=20
```

### Security Updates

1. **Container Images**: Automatically updated via CI/CD
2. **Base OS**: Cloud Run handles OS patching
3. **Dependencies**: Monitor GitHub Dependabot alerts
4. **Secrets Rotation**: Rotate API keys periodically

## Backup and Recovery

### Database Backups

Cloud SQL provides automatic backups:

```bash
# List available backups
gcloud sql backups list --instance=INSTANCE_NAME

# Create manual backup
gcloud sql backups create --instance=INSTANCE_NAME --description="Manual backup $(date)"

# Restore from backup
gcloud sql backups restore BACKUP_ID --restore-instance=INSTANCE_NAME
```

### Configuration Backup

Critical configurations are stored in:
- **Terraform State**: In Cloud Storage (versioned)
- **Secret Manager**: Versions maintained automatically
- **Container Images**: In Artifact Registry with retention policy

### Disaster Recovery

**Recovery Time Objective (RTO)**: ~15 minutes
**Recovery Point Objective (RPO)**: ~5 minutes

**Recovery Procedure:**
1. Verify database backups are available
2. Re-deploy infrastructure via Terraform
3. Restore database from latest backup if needed
4. Deploy latest application image
5. Verify all services are healthy

## Maintenance

### Routine Maintenance

**Weekly:**
- Review service logs for errors
- Check data collection rates
- Monitor prediction accuracy
- Review resource utilization

**Monthly:**
- Rotate API credentials
- Review and clean old container images
- Update ML models with new data
- Performance optimization review

**Quarterly:**
- Security review and updates
- Capacity planning review
- Disaster recovery testing
- Documentation updates

### Planned Maintenance

For planned maintenance:

1. **Schedule**: Announce maintenance window
2. **Prepare**: Test changes in staging environment
3. **Execute**: Deploy during low-traffic periods
4. **Verify**: Run comprehensive health checks
5. **Monitor**: Watch for issues in following hours

## Cost Optimization

### Resource Monitoring

```bash
# View Cloud Run costs
gcloud billing budgets list --billing-account=BILLING_ACCOUNT

# Monitor resource usage
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"

# Check Cloud SQL costs
gcloud sql instances describe INSTANCE_NAME --format="value(settings.pricingPlan,settings.tier)"
```

### Cost Optimization Tips

1. **Right-size Resources**: Monitor CPU/Memory usage and adjust
2. **Instance Scaling**: Set appropriate min/max instances
3. **Request Timeout**: Optimize timeout values
4. **Database Scaling**: Use appropriate Cloud SQL tier
5. **Image Cleanup**: Artifact Registry retention policies

## Contact and Escalation

### System Status

- **Health Dashboard**: Check service health endpoints
- **GitHub Actions**: Monitor deployment status
- **Google Cloud Console**: View service metrics and logs

### Emergency Response

For critical issues:

1. **Immediate**: Check service health and logs
2. **Database**: Verify Cloud SQL status and connectivity
3. **Traffic**: Check if external APIs are responding
4. **Rollback**: Deploy previous working version if needed
5. **Escalate**: Contact team leads if issue persists

### Support Resources

- **Documentation**: This guide and CLAUDE.md files
- **Logs**: Cloud Logging for detailed troubleshooting
- **Monitoring**: Cloud Monitoring for metrics and alerts
- **Community**: GitHub issues for feature requests and bugs

---

*This guide covers the operational aspects of the TrackRat system. For development and deployment procedures, see the individual CLAUDE.md files in each component directory.*