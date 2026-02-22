---
allowed-tools: Bash, Read, Task
---

# Validate Staging

Run the unified staging validation script which performs health checks, E2E API tests, and backend error log analysis in sequence. Auto-installs Python dependencies if missing.

## Usage
```
/testing:validate-staging [flags]
```

Flags (all optional, pass via $ARGUMENTS):
- `--no-wait` — skip 30s stabilization sleep (use when deployment isn't fresh)
- `--no-random` — skip Phase 2 random route generation in E2E tests
- `--skip-logs` — skip GCP error log check (useful when no GCP credentials)
- A URL as first positional arg to target a different environment (default: staging)

Examples:
- `/testing:validate-staging` — full validation against staging
- `/testing:validate-staging --no-wait --no-random` — fast: health + fixed routes only
- `/testing:validate-staging https://apiv2.trackrat.net` — validate production

## Instructions

### 1. Run the unified script

```bash
bash scripts/validate-staging.sh $ARGUMENTS
```

The script handles everything:
- Step 1: `scripts/verify-deployment.sh` (health, scheduler, metrics)
- Step 2: `scripts/e2e-api-test.sh` (E2E API tests across all providers)
- Step 3: `.claude/scripts/gcp-logs.py --errors` (backend error logs)
- Auto-installs `google-cloud-logging`, `cffi`, `cryptography` if missing

### 2. Report Results

**All steps pass:**
```
All 3 staging validation steps passed.
```

**A step fails:**
Report which step failed and the relevant output. If E2E fails, suggest:
```
Correlate with logs: /testing:validate-staging --skip-logs is not needed;
the log check runs automatically. Check the route and timestamp from the
failure output against the error logs shown in Step 3.
```

## Error Handling

- Script not found → `❌ scripts/validate-staging.sh not found. Are you in the repo root?`
- Health check fails → Step 1 aborts; staging may be down or deploying
- E2E fails → Step 2 aborts; check failed routes in output
- Log check fails → Likely missing GCP credentials; suggest `--skip-logs`
