# TrackRat

**Open source, real-time train tracking for NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North!**

[![App Store](https://img.shields.io/badge/App_Store-Download-blue?logo=apple)](https://apps.apple.com/us/app/trackrat/id6746423610)
[![Web App](https://img.shields.io/badge/Web_App-Live-orange)](https://trackrat.net)
[![License](https://img.shields.io/badge/License-GPLv3-green.svg)](LICENSE)

TrackRat tracks trains across eleven transit systems in real time, predicts platform assignments, and forecasts delays — all from a unified interface. It runs on iOS, Android (NOT FINISHED), the web (NOT FINISHED), and the backend is written in Python.

## Supported Transit Systems

| System | Coverage | Data Source | Real-Time |
|--------|----------|-------------|-----------|
| NJ Transit | All rail lines | NJ Transit API | Yes |
| Amtrak | Northeast Corridor | Amtraker API | Yes |
| PATH | All 4 routes, 13 stations | RidePATH API | Yes |
| LIRR | All branches | MTA GTFS-RT | Yes |
| Metro-North | All branches | MTA GTFS-RT | Yes |
| NYC Subway | 36 routes, 472 stations | MTA GTFS-RT | Yes |
| WMATA (DC Metro) | All 6 lines, 98 stations | WMATA REST API | Yes |
| BART | All lines | BART GTFS-RT | Yes |
| MBTA | Commuter Rail | MBTA GTFS-RT | Yes |
| Metra | All lines (Chicago) | Metra GTFS-RT | Yes |
| PATCO | Lindenwold–15th St | GTFS Static | Schedule only |

## What It Does

- **Track Predictions** — Predict platform assignments at Penn Station and other terminals
- **Real-Time Tracking** — Live train status, delays, and journey progress across all systems
- **Delay Forecasting** — Delay and cancellation probability predictions
- **Live Activities** — Real-time iOS Lock Screen and Dynamic Island updates
- **Route Alerts** — Push notifications for delays, cancellations, and service changes on subscribed routes, with customizable schedules, thresholds, and per-type toggles
- **Service Alerts** — Planned work and service change notifications for Subway, LIRR, and Metro-North
- **Congestion Maps** — Live network congestion monitoring
- **1,500+ Stations** across the US

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources   │     │     Backend      │     │    Frontends    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • FastAPI        │────▶│ • iOS App       │
│ • Amtrak        │     │ • APScheduler    │     │ • Android App   │
│ • PATH / PATCO  │     │ • ML Predictions │     │ • Web App       │
│ • LIRR / MNR    │     │ • PostgreSQL     │     │ • Live Activity │
│ • NYC Subway    │     └─────────────────┘     └─────────────────┘
│ • WMATA (DC)    │             │
│ • BART / MBTA   │     ┌───────▼────────┐
│ • Metra         │     │   GCP Infra    │
└─────────────────┘     │ • GCE (MIG)   │
                        │ • PostgreSQL   │
                        │ • Monitoring   │
                        └────────────────┘
```

Each transit system uses a collection pattern suited to its data source:

- **NJ Transit / Amtrak** — Multi-phase pipeline: Schedule Generation → Discovery → Collection → JIT Updates → Validation
- **PATH** — Unified collector every 4 minutes via native API, discovers trains at all 13 stations
- **LIRR / Metro-North / BART / MBTA** — Unified GTFS-RT collector every 4 minutes with static schedule backfill
- **NYC Subway** — Unified GTFS-RT collector processing 8 feeds covering 36 routes and 472 stations
- **Metra** — Unified GTFS-RT collector every 4 minutes (Central Time, requires API token)
- **WMATA** — REST API collector every 3 minutes with synthetic train IDs and estimated stop times
- **PATCO** — GTFS static schedules (no real-time API available)

## Getting Started

### Backend (Python / FastAPI)

**Prerequisites:** Python 3.11+, [Poetry](https://python-poetry.org/), PostgreSQL 14+

```bash
cd backend_v2
poetry install

# Set up PostgreSQL
psql -U postgres -c "CREATE DATABASE trackratdb;"
psql -U postgres -c "CREATE USER trackratuser WITH PASSWORD 'password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;"

# Configure environment
cp .env.example .env
# Edit .env with your NJ Transit API token and database credentials

# Run migrations and start
poetry run alembic upgrade head
poetry run uvicorn trackrat.main:app --reload
```

### Web App (React / TypeScript)

**Prerequisites:** Node.js 18+

```bash
cd webpage_v2
npm install
npm run dev          # Dev server at http://localhost:3000
npm run build        # Production build
```

### iOS App (Swift / SwiftUI)

**Prerequisites:** macOS 14+, Xcode 15+, iOS 18.0+ deployment target

```bash
cd ios
open TrackRat.xcodeproj
# Build and run in Xcode (Cmd+R)
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRACKRAT_DATABASE_URL` | Yes | PostgreSQL connection string |
| `TRACKRAT_NJT_API_TOKEN` | Yes | NJ Transit API token ([register here](https://raildata.njtransit.com)) |
| `TRACKRAT_WMATA_API_KEY` | No | WMATA developer API key (for DC Metro) |
| `TRACKRAT_METRA_API_TOKEN` | No | Metra GTFS-RT API token (for Chicago) |
| `TRACKRAT_MBTA_API_KEY` | No | MBTA API key (optional, for higher rate limits) |
| `APNS_TEAM_ID` | No | Apple Developer Team ID (for Live Activities) |
| `APNS_KEY_ID` | No | Apple Push Notification key ID |
| `APNS_AUTH_KEY_PATH` | No | Path to `.p8` auth key file |

See `backend_v2/.env.example` for the full list.

## Project Structure

```
TrackRat/
├── backend_v2/          # Python FastAPI backend
│   ├── src/trackrat/
│   │   ├── api/         # API endpoints (FastAPI routers)
│   │   ├── collectors/  # Transit data collectors (njt, amtrak, path, lirr, mnr, subway, bart, mbta, metra, wmata)
│   │   ├── config/      # Station configs, route topology, platform mappings
│   │   ├── models/      # SQLAlchemy + Pydantic models
│   │   ├── services/    # Business logic, ML predictions, scheduling
│   │   └── main.py      # App entrypoint
│   └── tests/           # pytest tests
├── ios/                 # Swift/SwiftUI iOS app
│   └── TrackRat/
│       ├── Views/       # Screens, components, paywall
│       ├── Services/    # API, subscriptions, live activities
│       ├── Models/      # Data models
│       └── Shared/      # Cross-target shared code
├── android/             # Kotlin/Jetpack Compose Android app
├── webpage_v2/          # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/       # Route pages
│       ├── components/  # Shared UI components
│       └── store/       # Zustand state management
├── infra_v2/terraform/  # GCP backend infrastructure (Terraform)
└── infra_v2/terraform-webpage/  # GCP webpage infrastructure (Terraform)
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
npm test                             # Run all tests (Vitest)
npm run build                        # TypeScript compile + Vite build
```

## API

**Production:** `https://apiv2.trackrat.net/api/v2`

```
GET  /api/v2/trains/departures              # Departures for a route
GET  /api/v2/trains/{train_id}              # Train details with all stops
GET  /api/v2/routes/congestion              # Network congestion data
GET  /api/v2/predictions/track              # Platform predictions
GET  /api/v2/predictions/delay              # Delay/cancellation forecasts
POST /api/v2/devices/register              # Register device for push notifications
PUT  /api/v2/alerts/subscriptions          # Sync route alert subscriptions
GET  /api/v2/alerts/service                # MTA service alerts (planned work, delays)
GET  /api/v2/trips/search                  # Multi-leg trip search with transfers
POST /api/v2/feedback                      # Submit user feedback
GET  /admin/stats                           # Server usage statistics (HTML)
GET  /admin/stats.json                      # Server usage statistics (JSON)
GET  /health                                # Health check
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- Development setup
- How to add a new transit system
- Code standards and PR process

### Areas Where Help Is Wanted

- Adding new transit systems (SEPTA, NJ Light Rail, Caltrain, and beyond)
- Improving test coverage
- Android app development
- Web app features (maps, charts, offline improvements)
- Accessibility improvements

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

Copyright 2025-2026 Andrew Martin

## Links

- **iOS App:** [App Store](https://apps.apple.com/us/app/trackrat/id6746423610)
- **Web App:** [trackrat.net](https://trackrat.net)
- **Feedback:** [trackrat.nolt.io](https://trackrat.nolt.io)
- **YouTube:** [@TrackRat-App](https://www.youtube.com/@TrackRat-App/shorts)
- **Contact:** trackrat@andymartin.cc
