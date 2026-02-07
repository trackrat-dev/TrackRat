# TrackRat

An open-source transit tracking framework with ML-powered track predictions. Currently supports NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North.

Built primarily through AI-assisted development ("vibe coding").

[![App Store](https://img.shields.io/badge/App_Store-Download-blue?logo=apple)](https://apps.apple.com/us/app/trackrat/id6746423610)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

## What It Does

- **Track Predictions**: ML models predict platform assignments at Penn Station and other terminals
- **Real-Time Updates**: Live train status, delays, and journey progress
- **Multi-Transit Coverage**: NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North in one place
- **Delay Forecasting**: ML-powered delay and cancellation probability predictions
- **Live Activities**: Real-time iOS Lock Screen and Dynamic Island updates
- **Congestion Maps**: Live network congestion monitoring
- **Trip Statistics**: Commute history with on-time percentage and time saved metrics
- **1,000+ Stations** across the Northeast Corridor

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources   │     │     Backend     │     │    Frontends    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • FastAPI       │────▶│ • iOS App       │
│ • Amtrak        │     │ • APScheduler   │     │ • Web App       │
│ • PATH          │     │ • ML Predictions│     │ • Live Activity │
│ • PATCO         │     │ • PostgreSQL    │     └─────────────────┘
│ • LIRR          │     └─────────────────┘
│ • Metro-North   │             │
└─────────────────┘     ┌───────▼────────┐
                        │   GCP Infra    │
                        │ • Cloud Run    │
                        │ • Cloud SQL    │
                        │ • Monitoring   │
                        └────────────────┘
```

### Data Collection Patterns

Each transit system uses an architecture suited to its data source:

- **NJ Transit / Amtrak**: Multi-phase pipeline — Schedule Generation (daily) → Discovery (30min) → Collection (15min) → JIT Updates (on-demand) → Validation (hourly)
- **PATH**: Single unified collector every 4 minutes via native RidePATH API, discovers trains at all 13 stations
- **PATCO**: GTFS static schedules (no real-time API available)
- **LIRR / Metro-North**: Unified collector every 4 minutes via MTA GTFS-RT feeds, with static schedule backfill

### Adding a New Transit System

The framework is designed to be extensible. Each transit system is a self-contained collector that feeds into the shared data pipeline. If you're interested in adding a new system, open an issue and we'll help you get started.

## Getting Started

### Backend (Python/FastAPI)

**Prerequisites**: Python 3.11+, Poetry, PostgreSQL 14+

```bash
cd backend_v2
poetry install

# Set up PostgreSQL
psql -U postgres -c "CREATE DATABASE trackratdb;"
psql -U postgres -c "CREATE USER trackratuser WITH PASSWORD 'password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;"

# Configure environment
cp .env.example .env
# Edit .env — see Environment Variables below

# Run migrations and start server
poetry run alembic upgrade head
poetry run uvicorn trackrat.main:app --reload
```

### iOS App (Swift/SwiftUI)

**Prerequisites**: macOS 14+, Xcode 15+, iOS 17.0+ deployment target

```bash
cd ios
open TrackRat.xcodeproj
# Build and run in Xcode (Cmd+R)
```

For local APNS testing, copy your auth key:
```bash
cp /path/to/AuthKey.p8 certs/apns_auth_key.p8
# Add APNS_* variables to backend .env
```

### Web App (React/TypeScript)

**Prerequisites**: Node.js 18+

```bash
cd webpage_v2
npm install
npm run dev          # Dev server at http://localhost:3000
npm run build        # Production build
```

### Environment Variables

The backend requires a `.env` file. Copy `.env.example` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `TRACKRAT_NJT_API_TOKEN` | Yes | NJ Transit API token |
| `TRACKRAT_CORS_ALLOWED_ORIGINS` | No | Comma-separated allowed origins |
| `APNS_KEY_ID` | No | Apple Push Notification key ID (for Live Activities) |
| `APNS_TEAM_ID` | No | Apple Developer Team ID |
| `APNS_AUTH_KEY_PATH` | No | Path to .p8 auth key file |

## Project Structure

```
TrackRat/
├── backend_v2/          # Python FastAPI backend
│   ├── src/trackrat/
│   │   ├── api/         # API endpoints (FastAPI routers)
│   │   ├── collectors/  # Transit data collectors (njt, amtrak, path, lirr, mnr)
│   │   ├── config/      # Station configs, route topology
│   │   ├── models/      # SQLAlchemy + Pydantic models
│   │   ├── services/    # Business logic, ML predictions, scheduling
│   │   └── main.py      # App entrypoint
│   └── tests/           # pytest tests
├── ios/                 # Swift/SwiftUI iOS app
│   └── TrackRat/
│       ├── Views/       # Screens and components
│       ├── Services/    # API, subscriptions, live activities
│       └── Models/      # Data models
├── webpage_v2/          # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/       # Route pages
│       ├── components/  # Shared UI components
│       └── store/       # Zustand state management
├── trackrat.net/        # Landing page (static HTML)
├── infra_v2/terraform/  # GCP infrastructure (Terraform)
├── board-meetings/      # Public governance records
└── CEO.md               # Strategic direction
```

## Running Tests

```bash
# Backend
cd backend_v2
poetry run pytest                    # All tests
poetry run pytest --cov=trackrat     # With coverage
poetry run pytest tests/unit/        # Unit only

# iOS
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'

# Web
cd webpage_v2
npm run build                        # TypeScript compile + build check
```

## Deployment

### Infrastructure (GCP)

Managed with Terraform across staging and production environments:
- **Cloud Run**: Auto-scaling containerized backend
- **Cloud SQL**: PostgreSQL 17 with private networking
- **Secret Manager**: Secure credential storage
- **Cloud Monitoring**: Dashboards and alerts

```bash
cd infra_v2/terraform
terraform init
terraform workspace select staging   # or: production
terraform plan -var="environment=staging"
terraform apply -var="environment=staging"
```

**Deployment triggers**: Push to `main` → staging, push to `production` → production.

**Web app**: Deployed automatically to GitHub Pages via GitHub Actions on push to `main`.

## API

Production: `https://apiv2.trackrat.net/api/v2`

Key endpoints:
```
GET  /api/v2/trains/departures              # Departures for a route
GET  /api/v2/trains/{train_id}              # Train details with all stops
GET  /api/v2/routes/congestion              # Network congestion data
GET  /api/v2/predictions/track              # ML platform predictions
GET  /api/v2/predictions/delay              # Delay/cancellation forecasts
GET  /health                                # Health check
```

## Contributing

We welcome contributions. Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes with tests
4. Run linting and tests (`make lint && make test`)
5. Submit a pull request

See open issues for good starting points.

### Areas Where Help Is Wanted

- Adding new transit systems (SEPTA, MTA Subway, and beyond)
- Improving test coverage
- Web app PWA features
- Accessibility improvements

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

Copyright 2025 Andrew Martin

## Links

- **App Store**: [Download TrackRat](https://apps.apple.com/us/app/trackrat/id6746423610)
- **Web App**: [bokonon1.github.io/TrackRat](https://bokonon1.github.io/TrackRat/)
- **Landing Page**: [trackrat.net](https://trackrat.net)
- **Feedback**: [trackrat.nolt.io](https://trackrat.nolt.io)
- **YouTube**: [@TrackRat-App](https://www.youtube.com/@TrackRat-App/shorts)
- **Contact**: trackrat@andymartin.cc
