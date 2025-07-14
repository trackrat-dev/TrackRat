# TrackRat

Real-time train tracking system with ML-powered track predictions for NJ Transit and Amtrak.

## Features

- **Multi-Platform**: Native iOS app with Live Activities + responsive web app
- **Track Predictions**: ML models predict platform assignments with confidence levels
- **Real-Time Updates**: Live train status, delays, and journey progress
- **Multi-Station Support**: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- **Smart Consolidation**: Merges duplicate trains across data sources

## Architecture

```
Data Sources → Cloud Run (API + ML) → iOS App + Web App
(NJ Transit/Amtrak)   (PostgreSQL)    (Live Activities)
```

## Quick Start

### Backend V2
```bash
cd backend_v2
poetry install
poetry run alembic upgrade head
poetry run uvicorn trackrat.main:app --reload
```

### iOS App
```bash
cd ios
open TrackRat.xcodeproj
```

## Development

### Local Development Deployment

Deploy your local changes to the development environment:

```bash
# Full deployment (infrastructure + application)
./deploy-dev.sh

# Quick deployment (skip tests and Terraform)
make deploy-dev-quick

# Check deployment status
make status-dev
```

See [Deployment Tools](#deployment-tools) section for more details.

## Production

Fully automated deployment via GitHub Actions to Google Cloud Run with:
- Docker containerization
- Terraform infrastructure
- Automated database migrations
- Health monitoring

## Documentation

- **Backend V2**: `backend_v2/CLAUDE.md` - Simplified V2 API development
- **iOS**: `ios/CLAUDE.md` - Native app and Live Activities
- **Infrastructure**: `infra/CLAUDE.md` - Terraform and GCP setup
- **Project Guide**: `CLAUDE.md` - Comprehensive project overview

## Deployment Tools

### Quick Commands

```bash
make deploy-dev         # Full deployment (infrastructure + application)
make deploy-dev-quick   # Quick app deployment (skip tests & Terraform)
make deploy-dev-infra   # Infrastructure only
make deploy-dev-docker  # Docker only
make status-dev         # Check environment status
make logs-dev           # View recent logs
```

### Deployment Script Options

The `deploy-dev.sh` script provides flexible deployment options:

```bash
./deploy-dev.sh [OPTIONS]
  --skip-tests          Skip running tests
  --skip-terraform      Skip Terraform apply (only update Cloud Run)
  --skip-docker         Skip Docker build (only run Terraform)
  --terraform-only      Only apply Terraform changes
  --docker-only         Only build/deploy Docker images
  --auto-approve        Skip confirmation prompts
  --dry-run             Show what would be done without executing
```

### Configuration

Deployment settings are stored in `.deploy/`:
- `dev.env` - Development environment configuration
- `deploy.config` - Default deployment settings
