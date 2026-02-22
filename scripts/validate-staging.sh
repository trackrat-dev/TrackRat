#!/usr/bin/env bash
# validate-staging.sh - Unified staging validation
#
# Runs all three validation steps in order, short-circuiting on failure:
#   1. Deployment health check (verify-deployment.sh)
#   2. E2E API tests (e2e-api-test.sh)
#   3. Backend error log check (gcp-logs.py)
#
# Automatically installs Python dependencies for step 3 if missing.
#
# Usage: ./scripts/validate-staging.sh [base_url] [--no-wait] [--no-random] [--skip-logs]
#   base_url     defaults to https://staging.apiv2.trackrat.net
#   --no-wait    skip the stabilization sleep in step 1
#   --no-random  skip random route generation in step 2
#   --skip-logs  skip the GCP log check (step 3)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_URL="https://staging.apiv2.trackrat.net"
NO_WAIT=false
NO_RANDOM=false
SKIP_LOGS=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-wait)   NO_WAIT=true; shift ;;
    --no-random) NO_RANDOM=true; shift ;;
    --skip-logs) SKIP_LOGS=true; shift ;;
    --help|-h)
      echo "Usage: $0 [base_url] [--no-wait] [--no-random] [--skip-logs]"
      exit 0
      ;;
    *) BASE_URL="$1"; shift ;;
  esac
done

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

step_pass() { echo -e "\n${GREEN}✅ Step $1 passed${NC}\n"; }
step_fail() { echo -e "\n${RED}❌ Step $1 failed${NC}\n"; exit 1; }

# ---------- Step 1: Deployment health ----------

echo -e "${BOLD}===== Step 1/3: Deployment Health =====${NC}"

verify_args=("$BASE_URL")
[[ "$NO_WAIT" == "true" ]] && verify_args+=("--no-wait")

if bash "$SCRIPT_DIR/verify-deployment.sh" "${verify_args[@]}"; then
  step_pass "1 (health)"
else
  step_fail "1 (health)"
fi

# ---------- Step 2: E2E API tests ----------

echo -e "${BOLD}===== Step 2/3: E2E API Tests =====${NC}"

e2e_args=("$BASE_URL")
[[ "$NO_RANDOM" == "true" ]] && e2e_args+=("--no-random")

if bash "$SCRIPT_DIR/e2e-api-test.sh" "${e2e_args[@]}"; then
  step_pass "2 (E2E)"
else
  step_fail "2 (E2E)"
fi

# ---------- Step 3: Backend error logs ----------

if [[ "$SKIP_LOGS" == "true" ]]; then
  echo -e "${BOLD}===== Step 3/3: Backend Logs (skipped) =====${NC}\n"
else
  echo -e "${BOLD}===== Step 3/3: Backend Error Logs =====${NC}"

  # Auto-install Python dependencies if missing
  if ! python3 -c "import google.oauth2.service_account" 2>/dev/null; then
    echo "Installing google-cloud-logging..."
    pip install google-cloud-logging 2>&1 | tail -3
  fi

  pylibs_dir="/tmp/pylibs"
  if ! PYTHONPATH="$pylibs_dir:${PYTHONPATH:-}" python3 -c "import cryptography" 2>/dev/null; then
    echo "Installing cffi + cryptography to $pylibs_dir..."
    pip install cffi cryptography --force-reinstall --target="$pylibs_dir" 2>&1 | tail -3
  fi

  env_flag="staging"
  if [[ "$BASE_URL" == *"production"* || "$BASE_URL" == "https://apiv2.trackrat.net"* ]]; then
    env_flag="production"
  fi

  if PYTHONPATH="$pylibs_dir:${PYTHONPATH:-}" python3 "$REPO_ROOT/.claude/scripts/gcp-logs.py" --env "$env_flag" --errors; then
    step_pass "3 (logs)"
  else
    step_fail "3 (logs)"
  fi
fi

# ---------- Summary ----------

echo -e "${GREEN}${BOLD}All staging validation steps passed.${NC}"
