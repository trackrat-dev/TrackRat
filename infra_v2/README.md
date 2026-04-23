# TrackRat V2 Infrastructure

Simplified GCP infrastructure using Managed Instance Groups with Container-Optimized OS, persistent disks, and HTTPS load balancing.

## Architecture

```
                                    ┌─────────────────────────────┐
                                    │      Cloud Build            │
                                    │  (CI/CD Pipelines)          │
                                    └──────────────┬──────────────┘
                                                   │
                                                   ▼
┌─────────────┐    ┌─────────────────────────────────────────────────────────┐
│   Client    │    │                    Google Cloud Platform                 │
│  (HTTPS)    │    │  ┌─────────────────────────────────────────────────┐    │
└──────┬──────┘    │  │              Global Load Balancer               │    │
       │           │  │  • Managed SSL Certificate                      │    │
       │           │  │  • HTTP→HTTPS Redirect                          │    │
       └──────────▶│  └─────────────────────┬───────────────────────────┘    │
                   │                        │                                 │
                   │                        ▼                                 │
                   │  ┌─────────────────────────────────────────────────┐    │
                   │  │         Managed Instance Group (MIG)            │    │
                   │  │  • Container-Optimized OS                       │    │
                   │  │  • Spot VMs (cost savings)                      │    │
                   │  │  • Auto-healing with health checks              │    │
                   │  │  ┌───────────────────────────────────────────┐  │    │
                   │  │  │  Docker Compose                           │  │    │
                   │  │  │  ├── PostgreSQL Container                 │  │    │
                   │  │  │  └── TrackRat API Container               │  │    │
                   │  │  └───────────────────────────────────────────┘  │    │
                   │  └─────────────────────┬───────────────────────────┘    │
                   │                        │                                 │
                   │                        ▼                                 │
                   │  ┌─────────────────────────────────────────────────┐    │
                   │  │           Persistent SSD Disk                   │    │
                   │  │  • PostgreSQL data (/mnt/disks/data/pgdata)    │    │
                   │  │  • Application logs                             │    │
                   │  │  • Daily snapshots (35-day retention)           │    │
                   │  └─────────────────────────────────────────────────┘    │
                   │                                                          │
                   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
                   │  │Secret Manager│  │  Artifact    │  │  GCS Deploy  │   │
                   │  │  (8 secrets) │  │  Registry    │  │    Bucket    │   │
                   │  └──────────────┘  └──────────────┘  └──────────────┘   │
                   └──────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required Secrets (create manually before terraform apply)

```bash
# Create secrets in Secret Manager
gcloud secrets create trackrat-db-password --data-file=-
gcloud secrets create trackrat-njt-api-token --data-file=-
gcloud secrets create trackrat-apns-team-id --data-file=-
gcloud secrets create trackrat-apns-key-id --data-file=-
gcloud secrets create trackrat-apns-bundle-id --data-file=-
gcloud secrets create trackrat-apns-auth-key --data-file=-
gcloud secrets create trackrat-wmata-api-key --data-file=-
gcloud secrets create trackrat-metra-api-token --data-file=-
```

### Terraform State Bucket

```bash
# Create state bucket (one-time setup)
gsutil mb -l us-east4 gs://trackrat-v2-terraform-state
gsutil versioning set on gs://trackrat-v2-terraform-state
```

## Environments

| Environment | Domain | Workspace | Branch Trigger |
|-------------|--------|-----------|----------------|
| Staging | staging.apiv2.trackrat.net | staging | main |
| Production | apiv2.trackrat.net | production | production |

## Deployment

### Terraform (Infrastructure Changes)

```bash
cd terraform

# Initialize and select workspace
terraform init
terraform workspace select staging  # or: terraform workspace new staging

# Plan and apply
terraform plan -var="environment=staging"
terraform apply -var="environment=staging"

# Production
terraform workspace select production
terraform plan -var="environment=production"
terraform apply -var="environment=production"
```

### Application Deployment (via Cloud Build)

Deployments are triggered automatically:
- **Push to `main`** → Staging deployment (clones production disk for testing)
- **Push to `production`** → Production deployment (scales down staging after success)

Manual trigger:
```bash
# Staging
gcloud builds submit --config=cloudbuild-staging.yaml .

# Production
gcloud builds submit --config=cloudbuild.yaml .
```

## Key Configuration

### Variables (terraform/variables.tf)

| Variable | Default | Description |
|----------|---------|-------------|
| `project_id` | trackrat-v2 | GCP project |
| `region` | us-east4 | GCP region |
| `zone` | us-east4-a | GCP zone |
| `machine_type` | t2d-standard-2 | VM machine type |
| `disk_size_gb` | 20 | Persistent disk size |
| `snapshot_retention_days` | 35 | Snapshot retention period |

**Note:** Staging uses spot VMs for cost savings; production uses on-demand VMs for stability.

### Outputs

```bash
terraform output load_balancer_ip    # IP for DNS configuration
terraform output api_url             # HTTPS API endpoint
terraform output artifact_registry_url  # Docker registry URL
```

## Operations

### SSH Access (IAP Tunnel Only)

```bash
# Find instance name
gcloud compute instances list --filter="name~trackrat"

# SSH via IAP
gcloud compute ssh INSTANCE_NAME --zone=us-east4-a --tunnel-through-iap
```

### View Logs

```bash
# Startup script logs (on instance)
sudo cat /var/log/startup.log

# Container logs (on instance)
cd /mnt/disks/data/compose
/mnt/disks/data/bin/docker-compose logs -f

# Cloud Logging
gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=INSTANCE_ID" --limit=50
```

### Disk Management

```bash
# List snapshots
gcloud compute snapshots list --filter="sourceDisk~trackrat"

# Create manual snapshot
gcloud compute snapshots create manual-backup-$(date +%Y%m%d) \
  --source-disk=trackrat-production-data \
  --source-disk-zone=us-east4-a

# Restore from snapshot (requires stopping MIG first)
gcloud compute instance-groups managed resize trackrat-production-mig --size=0 --zone=us-east4-a
gcloud compute disks delete trackrat-production-data --zone=us-east4-a
gcloud compute disks create trackrat-production-data \
  --source-snapshot=SNAPSHOT_NAME \
  --zone=us-east4-a \
  --type=pd-ssd
gcloud compute instance-groups managed resize trackrat-production-mig --size=1 --zone=us-east4-a
```

### Force Instance Replacement

```bash
# Rolling restart (pulls latest image)
gcloud compute instance-groups managed rolling-action restart \
  trackrat-staging-mig --zone=us-east4-a

# Replace instance (recreates from template)
gcloud compute instance-groups managed rolling-action replace \
  trackrat-staging-mig --zone=us-east4-a
```

## Cloud Build Pipelines

### cloudbuild-staging.yaml
1. Waits for any Terraform builds to complete
2. Stops staging MIG (scale to 0)
3. Clones production disk to staging (if production exists)
4. Builds and pushes Docker image
5. Uploads docker-compose.yml to GCS
6. Starts staging MIG (scale to 1)

### cloudbuild.yaml (Production)
1. Waits for any Terraform builds to complete
2. Builds and pushes Docker image
3. Uploads docker-compose.yml to GCS
4. Rolling restart of production MIG
5. Scales down staging to 0 (cost savings)

### cloudbuild-terraform.yaml
1. Initializes Terraform
2. Selects workspace based on environment
3. Plans changes
4. Applies changes automatically

## Cloud Functions

### feedback_notifier (Cloud Function)
Sends user feedback to Slack via webhook.

**Trigger**: Pub/Sub message from application logs
**Secret Required**: `slack-feedback-webhook`

```bash
# Deploy function
cd functions/feedback_notifier
gcloud functions deploy feedback-notifier \
  --runtime=python311 \
  --trigger-topic=user-feedback \
  --entry-point=notify_feedback
```

### train-follow-notifier (Cloud Run)
Sends push notifications when followed trains have status updates.

Deployed as a Cloud Run service, triggered by Pub/Sub messages from the backend.

## Cost Optimization

- **Spot VMs**: ~60-70% cost reduction vs on-demand
- **Staging auto-shutdown**: Scales to 0 after production deploy
- **Single instance**: No redundancy, but auto-healing handles failures
- **30-day artifact cleanup**: Prevents registry bloat
- **Regional resources**: All in us-east4 to minimize egress

## Troubleshooting

### Instance Won't Start
```bash
# Check serial port output
gcloud compute instances get-serial-port-output INSTANCE_NAME --zone=us-east4-a

# Common issues:
# - Disk still attached to old instance (wait or force detach)
# - Secret access denied (check IAM)
# - Docker image pull failed (check Artifact Registry permissions)
```

### Health Check Failing
```bash
# SSH to instance and check
curl http://localhost:8000/health/live

# Check container status
cd /mnt/disks/data/compose
/mnt/disks/data/bin/docker-compose ps
/mnt/disks/data/bin/docker-compose logs api
```

### Disk Not Mounting
```bash
# Check disk attachment
lsblk
ls -la /dev/disk/by-id/

# Check mount
mountpoint /mnt/disks/data
cat /var/log/startup.log | grep -i disk
```

## File Structure

```
infra_v2/
├── README.md                    # This file
├── cloudbuild.yaml              # Production deployment pipeline
├── cloudbuild-staging.yaml      # Staging deployment pipeline
├── cloudbuild-terraform.yaml    # Terraform automation
├── cloudbuild-webpage.yaml      # Webpage production deployment
├── cloudbuild-webpage-staging.yaml  # Webpage staging deployment
├── functions/
│   ├── feedback_notifier/       # Slack notification function
│   │   ├── main.py
│   │   └── requirements.txt
│   └── train_follow_notifier/   # Train follow push notification service
├── terraform-webpage/
│   └── main.tf                  # Standalone webpage infrastructure (GCS, CDN)
└── terraform/
    ├── main.tf                  # Provider and backend config
    ├── variables.tf             # Input variables
    ├── outputs.tf               # Output values
    ├── apis.tf                  # GCP API enablement
    ├── compute.tf               # Instance template, MIG, health check
    ├── network.tf               # Firewall rules
    ├── loadbalancer.tf          # HTTPS LB, SSL cert, forwarding rules
    ├── storage.tf               # Artifact Registry, persistent disk, GCS
    ├── secrets.tf               # Secret Manager refs, IAM, service account
    ├── metrics.tf               # Custom metrics and dashboards
    ├── monitoring.tf            # Alerting policies and notification channels
    └── backup.tf                # Snapshot schedule and policy
```
