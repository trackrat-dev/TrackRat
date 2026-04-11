# Contributing to TrackRat

Thanks for your interest in contributing! TrackRat is an open-source transit tracking framework, and we welcome contributions of all kinds.

## Code of Conduct

Be respectful, constructive, and welcoming. We're building something for commuters — keep it focused and productive.

## Development Setup

### Backend (Python / FastAPI)

```bash
cd backend_v2
poetry install
cp .env.example .env
# Edit .env with your credentials

# Start PostgreSQL (Docker)
docker run -d --name trackrat-postgres \
  -e POSTGRES_DB=trackratdb \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 postgres:15

# Create user and run migrations
psql -h localhost -U postgres -d trackratdb -c \
  "CREATE USER trackratuser WITH PASSWORD 'password'; GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;"
poetry run alembic upgrade head

# Start dev server
poetry run uvicorn trackrat.main:app --reload

# Lint and type check
poetry run black . && poetry run ruff check . && poetry run mypy src/
```

### Web App (React / TypeScript)

```bash
cd webpage_v2
npm install
npm run dev        # http://localhost:3000
npm run build      # Type check + build
```

### iOS App (Swift / SwiftUI)

```bash
cd ios
open TrackRat.xcodeproj
# Build: Cmd+B, Run: Cmd+R
```

## How to Contribute

1. **Fork** the repository
2. **Create a branch** from `main` (`git checkout -b feature/your-feature`)
3. **Make your changes** with tests
4. **Run linting and tests** (see commands above)
5. **Submit a pull request** with a clear description

### PR Guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Update documentation if behavior changes
- Run the linter before submitting

## Adding a New Transit System

This is one of the most impactful contributions you can make. Each transit system is a self-contained collector that feeds into the shared data pipeline.

### Overview

Collectors live in `backend_v2/src/trackrat/collectors/`. Each system has its own directory:

```
collectors/
├── njt/          # NJ Transit (multi-phase: schedule + discovery + collection)
├── amtrak/       # Amtrak (multi-phase)
├── path/         # PATH (unified collector)
├── lirr/         # LIRR (GTFS-RT)
├── mnr/          # Metro-North (GTFS-RT)
├── subway/       # NYC Subway (GTFS-RT, 8 feeds)
├── bart/         # BART (GTFS-RT)
├── mbta/         # MBTA Commuter Rail (GTFS-RT)
├── metra/        # Metra (GTFS-RT, requires API token)
├── wmata/        # WMATA/DC Metro (REST API)
├── base.py            # Abstract base classes for collectors
├── service_alerts.py  # MTA + NJT service alerts collector
├── mta_common.py      # Shared MTA logic (stop merging, departure inference)
└── mta_extensions.py  # MTA extension utilities
# Note: PATCO uses GTFS static schedules via services/gtfs.py (no dedicated collector)
```

### Steps

1. **Create a collector directory** — `collectors/your_system/`
2. **Implement the collector** — Fetch data from the transit API and produce `TrainJourney` and `JourneyStop` records
3. **Add station configuration** — Add station codes and names to `config/stations/`
4. **Register with the scheduler** — Add collection jobs to the scheduler service
5. **Add tests** — Unit tests with real API response fixtures in `tests/fixtures/`
6. **Update station data** — Add stations to the web app's `data/stations.ts` and iOS station lists

### Collector Patterns

Choose the pattern that fits your data source:

- **Multi-phase** (NJT/Amtrak): Schedule generation → discovery → collection → JIT updates. Best for APIs that separate schedule and real-time data.
- **Unified** (PATH): Single collector that handles both discovery and updates in one pass. Best for APIs that return complete train state.
- **GTFS-RT** (LIRR/MNR/Subway): Uses MTA's GTFS-Realtime feeds with static schedule backfill via shared `mta_common.py`. Best for systems that publish standard GTFS feeds.
- **Static** (PATCO): GTFS static schedules only. For systems without a real-time API.

### Key Models

```python
# backend_v2/src/trackrat/models/journey.py
class TrainJourney:
    train_id: str
    journey_date: date
    data_source: str          # "NJT", "AMTRAK", "PATH", etc.
    observation_type: str     # "OBSERVED" or "SCHEDULED"
    # ... stops, times, status

class JourneyStop:
    station_code: str
    stop_sequence: int
    scheduled_departure: datetime
    actual_departure: datetime | None
    track: str | None
```

Open an issue first if you're planning to add a new system — we'll help you get started and avoid duplicate work.

## Code Standards

- **Python**: Type hints required. Format with `black`, lint with `ruff`, type-check with `mypy`.
- **TypeScript**: Strict mode. All components are functional with hooks.
- **Swift**: SwiftUI with MVVM pattern.
- **Testing**: No mocking of services. Use real fixtures. Tests should be verbose for debugging.
- **Naming**: Follow existing patterns in the codebase.

## Where Help Is Wanted

- **New transit systems** — SEPTA, NJ Light Rail, NJ Bus, and beyond
- **Test coverage** — Especially for collectors and services
- **Web app features** — PWA improvements, accessibility, data visualization
- **Documentation** — API docs, architecture guides, onboarding improvements
- **Bug reports** — File issues with reproduction steps

## Questions?

- Open a [GitHub issue](https://github.com/trackrat-dev/TrackRat/issues) for bugs or feature requests
- Email [trackrat@andymartin.cc](mailto:trackrat@andymartin.cc) for other inquiries
- Submit ideas at [trackrat.nolt.io](https://trackrat.nolt.io)
