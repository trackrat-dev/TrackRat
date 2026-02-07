# CLAUDE.md

> Think carefully and implement the most concise solution that changes as little code as possible.

## Project Overview

TrackRat is an open-source transit tracking framework (Apache 2.0) with:
- **Backend**: Python (FastAPI + PostgreSQL + APScheduler) in `backend_v2/`
- **iOS**: Swift (SwiftUI + ActivityKit) in `ios/`
- **Web**: React (TypeScript + Vite + Tailwind) in `webpage_v2/` - See `webpage_v2/CLAUDE.md`
- **Infrastructure**: Terraform (Google Cloud Platform) in `infra_v2/`

Note: Android is in a separate private repository.

## USE SUB-AGENTS FOR CONTEXT OPTIMIZATION

### 1. Always use the file-analyzer sub-agent when asked to read files.
The file-analyzer agent is an expert in extracting and summarizing critical information from files, particularly log files and verbose outputs. It provides concise, actionable summaries that preserve essential information while dramatically reducing context usage.

### 2. Always use the code-analyzer sub-agent when asked to search code, analyze code, research bugs, or trace logic flow.

The code-analyzer agent is an expert in code analysis, logic tracing, and vulnerability detection. It provides concise, actionable summaries that preserve essential information while dramatically reducing context usage.

### 3. Always use the test-runner sub-agent to run tests and analyze the test results.

Using the test-runner agent ensures:

- Full test output is captured for debugging
- Main conversation stays clean and focused
- Context usage is optimized
- All issues are properly surfaced
- No approval dialogs interrupt the workflow

## Philosophy

### Error Handling

- **Fail fast** for critical configuration (missing text model)
- **Log and continue** for optional features (extraction model)
- **Graceful degradation** when external services unavailable
- **User-friendly messages** through resilience layer

### Testing

- Always use the test-runner agent to execute tests.
- Do not use mock services for anything ever.
- Do not move on to the next test until the current test is complete.
- If the test fails, consider checking if the test is structured correctly before deciding we need to refactor the codebase.
- Tests to be verbose so we can use them for debugging.

**Test Commands:**
```bash
# Backend
poetry run pytest                    # All tests
poetry run pytest --cov=trackrat    # With coverage
poetry run pytest tests/unit/        # Unit only

# iOS
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'

# Web
cd webpage_v2
npm run build                        # TypeScript compile + build check
# Note: No automated tests yet (MVP phase)
```

### Architecture Patterns

**Backend Data Collection (NJT/Amtrak - Multi-Phase):**
1. Schedule Generation (daily) - creates SCHEDULED records
2. Discovery (30min) - updates to OBSERVED when trains appear
3. Collection (15min) - fetches full journey details
4. JIT Updates (on-demand) - refreshes stale data (>60s)
5. Validation (hourly) - ensures coverage

**Backend Data Collection (PATH - Unified):**
- Single collector runs every 4 minutes using native RidePATH API
- Discovers trains at all 13 stations (not just terminus)
- Handles both discovery and journey updates in one pass
- Infers train origin from route when seen mid-journey

**Backend Data Collection (LIRR / Metro-North - Unified GTFS-RT):**
- Single unified collector per system runs every 4 minutes
- Uses MTA's official GTFS-RT feeds directly (not Transiter)
- Shared logic in `mta_common.py` (stop merging, departure inference, completion detection)
- GTFS static schedules backfill stops that GTFS-RT omits (e.g., origin terminals)

**Backend Data Collection (PATCO - Schedule-only):**
- Uses GTFS static schedules from SEPTA feed
- No real-time API available; times are scheduled only

**Key Design Principles:**
- Single Journey Record: One database row per train per day
- Horizontal Scaling: Database-coordinated scheduler with row-level locking
- API Response Caching: 15-minute pre-computed responses for congestion endpoints

**iOS Architecture:**
- MVVM embedded within view files (no separate ViewModel files)
- Singleton services pattern (`APIService.shared`, `LiveActivityService.shared`)
- `@StateObject AppState` for global state management
- NavigationPath for type-safe navigation

**Web Architecture:**
- React functional components with hooks (no classes)
- Zustand for global state management (simpler than Redux)
- localStorage for persistence (no backend user accounts)
- 30-second polling for real-time updates (no WebSocket)
- Mobile-first responsive design with Tailwind CSS


## Tone and Behavior

- Criticism is welcome. Please tell me when I am wrong or mistaken, or even when you think I might be wrong or mistaken.
- Please tell me if there is a better approach than the one I am taking.
- Please tell me if there is a relevant standard or convention that I appear to be unaware of.
- Be skeptical.
- Be concise.
- Short summaries are OK, but don't give an extended breakdown unless we are working through the details of a plan.
- Do not flatter, and do not give compliments unless I am specifically asking for your judgement.
- Occasional pleasantries are fine.
- Feel free to ask many questions. If you are in doubt of my intent, don't guess. Ask.

## Debugging UI Issues

When the user reports a UI bug with specific screen text or titles:

1. **ALWAYS search for the exact text first** before making assumptions about which file to edit
   - Use `Grep` to find where the text appears: `grep -r "exact text from user" ios/`
   - Multiple views may have similar functionality but different implementations

2. **Confirm the correct file** with the user if there's any ambiguity
   - Example: "Where would you like to leave from?" appears in TripSelectionView.swift
   - Example: "Where would you like to go?" appears in DestinationPickerView.swift
   - Don't assume based on similar code patterns or naming conventions

3. **Test hypotheses systematically**
   - If a fix works in one view but not another, they likely have different implementations
   - Don't continue trying variations in the wrong file
   - Re-verify you're editing the correct file when user reports the fix didn't work

4. **When user says "it's not working"**
   - Ask which specific screen/view they're testing on
   - Verify you're editing the file that corresponds to that screen
   - Search for the screen's title text to confirm the file

This prevents wasting time editing incorrect files when the user has given clear indicators (screen titles, specific text) about which view has the problem.

## Development Workflows

### Backend Development
```bash
cd backend_v2
poetry install
alembic upgrade head

# Run locally
poetry run uvicorn trackrat.main:app --reload

# Lint & type check
poetry run black . && poetry run ruff check . && poetry run mypy src/
# Or use: make lint
```

### iOS Development
```bash
cd ios
open TrackRat.xcodeproj
# Build: Cmd+B, Run: Cmd+R

# CLI build
xcodebuild -scheme TrackRat -sdk iphonesimulator build \
  -destination 'platform=iOS Simulator,name=iPhone 16'
```

### Web Development
```bash
cd webpage_v2
npm install
npm run dev          # Starts dev server at http://localhost:3000
npm run build        # TypeScript compile + Vite build
npm run preview      # Preview production build locally
```

**Deployment:** Automatic via GitHub Actions on push to `main`
- Workflow: `.github/workflows/deploy-webpage.yml`
- Output: Deployed to GitHub Pages at `https://bokonon1.github.io/TrackRat/`

### Infrastructure Management
```bash
cd infra_v2/terraform
terraform init
terraform workspace select staging  # or: production

# Deploy to staging
terraform plan -var="environment=staging"
terraform apply -var="environment=staging"

# Deploy to production
terraform workspace select production
terraform plan -var="environment=production"
terraform apply -var="environment=production"
```

**Deployment Triggers**: Push to `main` → staging, push to `production` → production.

## GCP Log Viewing (Cloud Environment)

The cloud environment has a read-only GCP service account (`roles/logging.viewer` on `trackrat-v2`). The SessionStart hook in `.claude/settings.json` writes `GCP_SA_KEY_JSON` to `/root/.config/gcloud/service-account.json`. This hook is required for authentication.

### Setup (once per session)

```bash
pip install google-cloud-logging 2>&1 | tail -3
pip install cffi cryptography --force-reinstall --target=/tmp/pylibs 2>&1 | tail -3
```

### Architecture

- **Staging & Production**: GCE instances via Managed Instance Groups (Docker Compose, not Cloud Run)
- **Hostnames**: `trackrat-staging-XXXX` / `trackrat-production-XXXX` (suffix is random, changes on instance recreation)
- **Resource type**: `gce_instance` (NOT `cloud_run_revision`)
- **Cloud Run services**: `feedback-notifier`, `train-follow-notifier` (auxiliary only)
- **Containers**: `trackrat-api` (FastAPI), PostgreSQL

### Log Structure

There are two log sources per GCE instance. **Always use `cos_containers` for app logs:**

| Source | Log name | Key fields | Content |
|--------|----------|------------|---------|
| **App logs** | `cos_containers` | `jsonPayload.event`, `.level`, `.logger`, `.message` | Structured application logs from trackrat-api |
| **Docker events** | (default/systemd) | `jsonPayload._HOSTNAME`, `.MESSAGE` | Container lifecycle noise (exec_create/die) — rarely useful |

### Query Logs (Helper Script)

Use `.claude/scripts/gcp-logs.py` — handles auth, hostname discovery, and structured log formatting:

```bash
# Recent staging app logs (default)
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py

# Production app logs
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --env production

# Errors only
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --errors

# Search for a pattern (searches event + message fields)
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --search "departure_cache"

# Save to file for file-analyzer sub-agent
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --output /tmp/logs.txt --limit 500

# Include raw Docker events (noisy, rarely needed)
PYTHONPATH=/tmp/pylibs:$PYTHONPATH python3 .claude/scripts/gcp-logs.py --raw
```

### Common Filters (for manual queries or --filter flag)

```python
# App logs (always use cos_containers for application-level logs)
'logName="projects/trackrat-v2/logs/cos_containers"'

# Discover instance by hostname prefix (prefixes are stable, suffixes change)
'jsonPayload._HOSTNAME=~"^trackrat-staging-"'
'jsonPayload._HOSTNAME=~"^trackrat-production-"'

# App-level errors/warnings (structured field, not severity)
'jsonPayload.level="error"'
'jsonPayload.level="warning"'

# Search app events or messages
'jsonPayload.event=~"departure_cache"'
'jsonPayload.message=~"some pattern"'

# Time range
'timestamp>="2025-01-01T00:00:00Z" AND timestamp<="2025-01-02T00:00:00Z"'

# Cloud Run auxiliary services
'resource.type="cloud_run_revision" AND resource.labels.service_name="train-follow-notifier"'
```

### Tips

- **Use the helper script first** — it handles hostname discovery and formats structured logs cleanly.
- **Use file-analyzer sub-agent** for large result sets — save with `--output` then pass to file-analyzer.
- `gcloud` CLI cannot be installed (blocked). grpc transport fails (SSL cert issues). Always use REST API.
- Staging and production logs share the same GCP project — always filter by instance.
- Service account JSON has literal `\n` in private_key — use `json.loads(content, strict=False)`.

## Key File Locations

- Backend services: `backend_v2/src/trackrat/services/`
- Backend API endpoints: `backend_v2/src/trackrat/api/`
- Backend models: `backend_v2/src/trackrat/models/`
- Backend collectors: `backend_v2/src/trackrat/collectors/` (njt, amtrak, path, lirr, mnr)
- Backend config: `backend_v2/src/trackrat/config/` (stations, route_topology, station_configs)
- Backend tests: `backend_v2/tests/`
- iOS views: `ios/TrackRat/Views/Screens/`, `ios/TrackRat/Views/Components/`
- iOS services: `ios/TrackRat/Services/`
- iOS models: `ios/TrackRat/Models/`
- iOS tests: `ios/TrackRatTests/`
- Web pages: `webpage_v2/src/pages/`
- Web components: `webpage_v2/src/components/`
- Web services: `webpage_v2/src/services/`
- Web store: `webpage_v2/src/store/appStore.ts`
- Test fixtures: `backend_v2/tests/fixtures/` (mock API responses)
- Infrastructure Terraform: `infra_v2/terraform/`
- Infrastructure Cloud Build: `infra_v2/cloudbuild*.yaml`

## Common API Endpoints

```
# Train Operations
/api/v2/trains/departures          # List departures for route
/api/v2/trains/{train_id}          # Train details with all stops
/api/v2/trains/{train_id}/history  # Historical train performance

# Route Analytics
/api/v2/routes/congestion          # Network congestion data (iOS only)
/api/v2/routes/history             # Historical route performance
/api/v2/routes/summary             # Natural language operations summary
/api/v2/routes/segments/{from}/{to}/trains  # Segment train details

# ML Predictions
/api/v2/predictions/track          # ML platform predictions (Web, iOS)
/api/v2/predictions/delay          # Delay/cancellation forecasts (iOS)
/api/v2/predictions/supported-stations  # Stations with ML predictions

# System Operations
/api/v2/live-activities/register   # iOS Live Activity registration
/api/v2/validation/status          # Validation system status
/api/v2/validation/results/{route}/{source}  # Route validation details
/health                            # Health check
/health/live                       # Kubernetes liveness probe
/health/ready                      # Kubernetes readiness probe
/scheduler/status                  # APScheduler job status
/metrics                           # Prometheus metrics
```

**API Environments:**
- Production: `https://apiv2.trackrat.net/api/v2`
- Staging: `https://staging.apiv2.trackrat.net/api/v2`
- Web uses: Production only
- iOS uses: Both (configurable)

## ABSOLUTE RULES:

- NO PARTIAL IMPLEMENTATION
- NO SIMPLIFICATION : no "//This is simplified stuff for now, complete implementation would blablabla"
- NO CODE DUPLICATION : check existing codebase to reuse functions and constants Read files before writing new functions. Use common sense function name to find them easily.
- NO DEAD CODE : either use or delete from codebase completely
- IMPLEMENT TEST FOR EVERY FUNCTIONS
- NO CHEATER TESTS : test must be accurate, reflect real usage and be designed to reveal flaws. No useless tests! Design tests to be verbose so we can use them for debuging.
- NO INCONSISTENT NAMING - read existing codebase naming patterns.
- NO OVER-ENGINEERING - Don't add unnecessary abstractions, factory patterns, or middleware when simple functions would work. Don't think "enterprise" when you need "working"
- NO MIXED CONCERNS - Don't put validation logic inside API handlers, database queries inside UI components, etc. instead of proper separation
- NO RESOURCE LEAKS - Don't forget to close database connections, clear timeouts, remove event listeners, or clean up file handles
