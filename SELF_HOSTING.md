# Self-Hosting TrackRat

This guide covers how to deploy TrackRat for your own use.

## Architecture Overview

TrackRat consists of:
- **Backend API** (Python/FastAPI) - Collects train data and serves API
- **PostgreSQL Database** - Stores train schedules and predictions
- **iOS App** (optional) - Mobile client with Live Activities
- **Web App** (optional) - Browser-based client

## Required Credentials

| Secret | Required | Description | How to Obtain |
|--------|----------|-------------|---------------|
| NJ Transit API Token | Yes | Access to train data | [njtransit.com/developer](https://www.njtransit.com/developer) |
| Database Password | Yes | PostgreSQL access | Generate a strong password |
| APNS Team ID | No* | Apple Developer Team ID | Apple Developer account |
| APNS Key ID | No* | Push notification key ID | Apple Developer > Keys |
| APNS Auth Key (.p8) | No* | Push notification private key | Apple Developer > Keys |

*APNS credentials are only needed for iOS push notifications. The app works without them - Live Activities will still function locally on the device.

## Quick Start (Local Docker)

1. **Clone and configure:**
   ```bash
   cd backend_v2
   cp .env.example .env
   # Edit .env and set TRACKRAT_NJT_API_TOKEN
   ```

2. **Start services:**
   ```bash
   cp docker-compose.example.yml docker-compose.yml
   docker-compose up -d
   ```

3. **Verify:**
   ```bash
   curl http://localhost:8000/health
   ```

The API will be available at `http://localhost:8000`.

## GCP Deployment

TrackRat includes Terraform configuration for Google Cloud Platform.

### Prerequisites

- GCP project with billing enabled
- `gcloud` CLI authenticated
- Terraform installed

### 1. Create Secrets

Create secrets in Secret Manager before running Terraform:

```bash
# Required
echo -n "your-db-password" | gcloud secrets create trackrat-db-password --data-file=-
echo -n "your-njt-token" | gcloud secrets create trackrat-njt-api-token --data-file=-

# Optional (for iOS push notifications)
echo -n "YOUR_TEAM_ID" | gcloud secrets create trackrat-apns-team-id --data-file=-
echo -n "YOUR_KEY_ID" | gcloud secrets create trackrat-apns-key-id --data-file=-
echo -n "YOUR_BUNDLE_ID" | gcloud secrets create trackrat-apns-bundle-id --data-file=-
cat /path/to/AuthKey_XXXXXX.p8 | gcloud secrets create trackrat-apns-auth-key --data-file=-
```

### 2. Configure Terraform

```bash
cd infra_v2/terraform

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
project_id  = "your-gcp-project-id"
environment = "staging"  # or "production"
domain      = "api.yourdomain.com"
EOF
```

### 3. Deploy

```bash
terraform init
terraform workspace new staging  # or: terraform workspace select staging
terraform plan
terraform apply
```

## iOS App Setup

1. **Copy export options:**
   ```bash
   cp ios/ExportOptions.plist.example ios/ExportOptions.plist
   # Edit and set your Team ID
   ```

2. **Open in Xcode:**
   ```bash
   open ios/TrackRat.xcodeproj
   ```

3. **Configure signing:** Update the Team and Bundle ID in project settings.

4. **Update API URL:** Edit `ios/TrackRat/Services/StorageService.swift` to point to your backend.

## Environment Variables Reference

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TRACKRAT_DATABASE_URL` | Yes | - | PostgreSQL connection URL |
| `TRACKRAT_NJT_API_TOKEN` | Yes | - | NJ Transit API token |
| `TRACKRAT_ENVIRONMENT` | No | development | Environment name |
| `TRACKRAT_LOG_LEVEL` | No | INFO | Logging level |
| `TRACKRAT_CORS_ALLOWED_ORIGINS` | No | localhost | Comma-separated origins |
| `APNS_TEAM_ID` | No | - | Apple Developer Team ID |
| `APNS_KEY_ID` | No | - | APNS auth key ID |
| `APNS_AUTH_KEY_PATH` | No | - | Path to .p8 key file |
| `APNS_BUNDLE_ID` | No | net.trackrat.TrackRat | iOS app bundle ID |
| `APNS_ENVIRONMENT` | No | dev | `dev` for sandbox, `prod` for production |

### GCP Secrets

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `trackrat-db-password` | Yes | PostgreSQL password |
| `trackrat-njt-api-token` | Yes | NJ Transit API token |
| `trackrat-apns-team-id` | No | Apple Team ID |
| `trackrat-apns-key-id` | No | APNS key ID |
| `trackrat-apns-bundle-id` | No | iOS bundle ID |
| `trackrat-apns-auth-key` | No | Contents of .p8 file |

## Troubleshooting

### No train data appearing

1. Check NJT API token is valid
2. Verify database connection
3. Check logs: `docker-compose logs api`

### Push notifications not working

1. Verify all APNS credentials are set
2. Check APNS environment matches (dev/prod)
3. Ensure .p8 key file is readable

### Database connection issues

1. Verify `TRACKRAT_DATABASE_URL` format: `postgresql+asyncpg://user:pass@host:5432/db`
2. Check database is accessible from API container
3. Run migrations: `alembic upgrade head`
