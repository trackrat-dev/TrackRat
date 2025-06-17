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

### Backend (TrackCast)
```bash
cd backend
pip install -e .
trackcast init-db
trackcast start-scheduler
```

### iOS App
```bash
cd ios
open TrackRat.xcodeproj
```

### Web App
```bash
cd webpage
python proxy.py  # Development only
open http://localhost:9998
```

## Production

Fully automated deployment via GitHub Actions to Google Cloud Run with:
- Docker containerization
- Terraform infrastructure
- Automated database migrations
- Health monitoring

## Documentation

- **Backend**: `backend/CLAUDE.md` - API development and deployment
- **iOS**: `ios/CLAUDE.md` - Native app and Live Activities
- **Web**: `webpage/CLAUDE.md` - Web application development
- **Infrastructure**: `infra/CLAUDE.md` - Terraform and GCP setup
- **Operations**: `OPERATORS_GUIDE.md` - Production monitoring and troubleshooting
