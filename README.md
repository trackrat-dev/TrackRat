# TrackRat

Real-time train tracking system with ML-powered track predictions for NJ Transit and Amtrak.

## Features

- **Multi-Platform**: Native iOS app with Live Activities + responsive web app
- **Track Predictions**: ML models predict platform assignments with confidence levels
- **Real-Time Updates**: Live train status, delays, and journey progress
- **Multi-Station Support**: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- **Smart Consolidation**: Merges duplicate trains across data sources
- **Transit Analytics**: Real-time congestion monitoring and historical route performance
- **Journey Tracking**: Segment-by-segment transit time analysis and delay attribution

## Architecture

```
Data Sources → Cloud Run (API + Analytics) → iOS App + Web App
(NJ Transit/Amtrak)    (SQLite + ML Models)    (Live Activities)
                              ↓
                    Transit Time Analytics
                   (Congestion + Performance)
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

### Local Development

Run components individually for development:

```bash
# Backend V2
cd backend_v2
poetry install
poetry run uvicorn trackrat.main:app --reload

# iOS App
cd ios
open TrackRat.xcodeproj
```

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

## Development Tools

### Development Commands

```bash
# Run tests and linting
make test                            # Run all tests
make lint                            # Run linting checks  
make clean                           # Clean build artifacts

# Backend commands
make backend-test                    # Run backend tests
make backend-migrate                 # Run database migrations

# Infrastructure commands  
make infra-plan                      # Plan infrastructure changes
make infra-validate                  # Validate Terraform configuration

# Setup
make setup                           # Setup development environment
```
