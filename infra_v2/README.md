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
                   │  │          Persistent Disk (pd-balanced)          │    │
                   │  │  • PostgreSQL data (/mnt/disks/data/pgdata)    │    │
                   │  │  • Application logs                             │    │
                   │  │  • Daily snapshots (7-day retention)            │    │
                   │  └─────────────────────────────────────────────────┘    │
                   │                                                          │
                   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
                   │  │Secret Manager│  │  Artifact    │  │  GCS Deploy  │   │
                   │  │  (8 secrets) │  │  Registry    │  │    Bucket    │   │
                   │  └──────────────┘  └──────────────┘  └──────────────┘   │
                   └──────────────────────────────────────────────────────────┘
```

> **Load-balancer consolidation (July 2026):** the diagram above shows the historical per-environment layout. In **production**, the dedicated API load balancer has been torn down (`consolidate_api_lb = true` in `terraform/variables.tf`): `apiv2.trackrat.net` is now host-routed through the consolidated **webpage** LB defined in `terraform-webpage/main.tf`, which fronts both `trackrat.net` (GCS bucket backend) and the API (`trackrat-production-backend`). Staging keeps its own dedicated API LB. The staging *webpage* LB was also decommissioned — `gs://trackrat-webpage-staging` is bucket-only and `staging.trackrat.net` no longer resolves to it. Cutover procedure: `infra_v2/RUNBOOK-lb-consolidation.md`.

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

The Cloud Functions need two additional secrets (not referenced by `terraform/secrets.tf`): `slack-feedback-webhook` and `github-feedback-token` (used by `feedback_notifier` to create GitHub issues — see Cloud Functions below).

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

### Webpage Deployment

The React webpage (`webpage_v2/`) deploys separately from the API via its own Cloud Build triggers (defined in `terraform-webpage/`):
- **Push to `main`** (with `webpage_v2/` changes) → `trackrat-webpage-staging` trigger → `gs://trackrat-webpage-staging` (bucket-only — the staging webpage LB was decommissioned and `staging.trackrat.net` no longer points at it)
- **Push to `production`** (with `webpage_v2/` changes) → `trackrat-webpage-production` trigger → `gs://trackrat-webpage-production` (`trackrat.net` / `www.trackrat.net`)

Manual deploy from the repo root:
```bash
./scripts/deploy-webpage.sh [staging|production] [--bucket=<name>] [--dry-run]
```
`--bucket` overrides the destination bucket (with or without the `gs://` prefix) while keeping the environment's API URL — useful for pre-populating a new bucket during a migration.

## Key Configuration

### Variables (terraform/variables.tf)

| Variable | Default | Description |
|----------|---------|-------------|
| `project_id` | trackrat-v2 | GCP project |
| `region` | us-east4 | GCP region |
| `zone` | us-east4-a | GCP zone |
| `machine_type` | t2d-standard-2 | VM machine type (Tau/AMD, dedicated cores; reverted from e2-custom after latency regression) |
| `disk_size_gb` | 40 | Persistent disk size |
| `snapshot_retention_days` | 7 | Snapshot retention period |
| `domain` | "" (per-environment default) | API domain (`apiv2.trackrat.net` / `staging.apiv2.trackrat.net`) |
| `consolidate_api_lb` | true | Production cutover switch: tears down the dedicated API frontend; `apiv2.trackrat.net` rides the consolidated webpage LB. No effect on staging. See `RUNBOOK-lb-consolidation.md` |
| `alert_email` | trackrat@andymartin.cc | Email for uptime monitoring alerts |

**Note:** Staging uses spot VMs for cost savings; production uses on-demand VMs for stability.

### Outputs

```bash
terraform output load_balancer_ip    # IP for DNS configuration (staging only; production returns "consolidated-into-webpage-lb")
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
  --type=pd-balanced
gcloud compute instance-groups managed resize trackrat-production-mig --size=1 --zone=us-east4-a
```

### Shrinking / retyping the data disk (destructive — production first)

GCP persistent disks **cannot be shrunk in place**, and a snapshot can only be
restored to a disk **≥** the source size — so reducing the data disk (e.g. 60GB →
40GB) or changing its type (`pd-ssd` → `pd-balanced`, immutable) requires a manual
copy-out / recreate / copy-back that preserves the canonical disk name. Only
`pgdata` holds irreplaceable state; the startup script rebuilds `bin/`, `compose/`,
`.env`, `.docker`, and `logs/` on every boot.

**Order matters: migrate production before staging.** Staging's disk is cloned from
a production snapshot on every deploy (`cloudbuild-staging.yaml`), and you cannot
create a 40GB disk from a 60GB snapshot. Once production is at 40GB, staging inherits
the new **size** automatically on its next deploy (the clone passes no `--size`).
The clone's **type**, however, is hardcoded (`--type=pd-balanced` in
`cloudbuild-staging.yaml`), so that line must be kept in sync with the disk type
in `storage.tf` — otherwise staging keeps recreating a disk of the old type and
never matches production.

**Terraform sequencing:** perform the manual migration to the *exact* target
(size + type + same name) **before** merging the matching `variables.tf` /
`storage.tf` change. Otherwise the next `cloudbuild-terraform` apply sees a `size`
decrease / `type` change and destroys+recreates the live database volume. After the
manual migration, the merged config matches reality and `terraform plan` is a no-op
for the disk.

```bash
ZONE=us-east4-a
DISK=trackrat-production-data
MIG=trackrat-production-mig
BUCKET=trackrat-v2-deploy-production

# 1. Safety snapshot (in addition to the daily auto-snapshot)
gcloud compute snapshots create ${DISK}-premigrate-$(date +%Y%m%d) \
  --source-disk=$DISK --source-disk-zone=$ZONE

# 2. Quiesce Postgres cleanly on the running instance (start of downtime)
#    SSH to the instance, then:
#    cd /mnt/disks/data/compose && /mnt/disks/data/bin/docker-compose stop

# 3. Detach the disk from production FIRST by scaling the MIG down.
#    A disk that is still attached read-write to the prod VM cannot be
#    attached to the utility VM, so this must happen before step 4.
gcloud compute instance-groups managed resize $MIG --size=0 --zone=$ZONE

# 4. Copy pgdata off the old disk via a temporary utility VM (Debian, same
#    zone). Attach $DISK (now free), mount it, and stage to GCS
#    (~26GB -> ~15GB compressed):
#    tar -C /mnt/disks/data -cf - pgdata | gzip | \
#      gsutil cp - gs://$BUCKET/pgdata-migrate.tgz
#    Then detach $DISK from the utility VM.

# 5. Delete the old disk and recreate it with the SAME name at the new size/type
gcloud compute disks delete $DISK --zone=$ZONE --quiet
gcloud compute disks create $DISK --size=40 --type=pd-balanced --zone=$ZONE

# 6. Restore pgdata onto the new disk via the same utility VM:
#    attach $DISK, mkfs.ext4 <dev>, mount, then:
#    gsutil cp gs://$BUCKET/pgdata-migrate.tgz - | tar -C /mnt/new -xzf - ; sync
#    Detach $DISK, then delete the utility VM.

# 7. Bring the MIG back up; startup script sees populated pgdata (no reformat)
gcloud compute instance-groups managed resize $MIG --size=1 --zone=$ZONE
# Verify: curl https://apiv2.trackrat.net/health/ready

# 8. Merge the matching variables.tf (disk_size_gb=40), storage.tf
#    (type="pd-balanced"), and cloudbuild-staging.yaml (--type=pd-balanced)
#    changes; terraform plan should show no disk changes.
#    A subsequent terraform apply re-attaches the snapshot schedule if needed.
```

**Backout:** as long as the pre-migration snapshot exists (manual snapshots are
not auto-deleted; policy snapshots follow `snapshot_retention_days`, default 7),
recreate `$DISK` from it at the original pre-migration size/type (e.g.
`--size=60 --type=pd-ssd` for the 2026-07 migration) and scale the MIG back up.

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
Sends user feedback to Slack via webhook **and creates a GitHub issue** in `trackrat-dev/TrackRat` (label `user-feedback`) for each submission.

**Trigger**: Pub/Sub message from application logs
**Secrets Required**: `slack-feedback-webhook`, `github-feedback-token`

```bash
# Deploy function
cd functions/feedback_notifier
gcloud functions deploy feedback-notifier \
  --runtime=python311 \
  --trigger-topic=user-feedback \
  --entry-point=notify_feedback
```

### train_follow_notifier (Cloud Function)
Posts a Slack message when a user follows a train (same Pub/Sub → Slack-webhook pattern as `feedback_notifier`). It does **not** send push notifications — train push updates are handled by the backend's Live Activity scheduler job.

**Trigger**: Pub/Sub message from application logs
**Secret Required**: Slack webhook

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
├── RUNBOOK-lb-consolidation.md  # API→webpage LB consolidation cutover runbook
├── cloudbuild.yaml              # Production deployment pipeline
├── cloudbuild-staging.yaml      # Staging deployment pipeline
├── cloudbuild-terraform.yaml    # Terraform automation
├── cloudbuild-webpage.yaml      # Webpage production deployment
├── cloudbuild-webpage-staging.yaml  # Webpage staging deployment
├── functions/
│   ├── feedback_notifier/       # Slack notification function
│   │   ├── main.py
│   │   └── requirements.txt
│   └── train_follow_notifier/   # Train-follow Slack notification function
├── terraform-webpage/
│   └── main.tf                  # Webpage hosting: production LB (also fronts apiv2.trackrat.net post-consolidation), SSL certs, CDN, Cloud Build triggers; staging is bucket-only
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
