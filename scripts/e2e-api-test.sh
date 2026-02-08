#!/usr/bin/env bash
# e2e-api-test.sh - End-to-end API validation mimicking iOS app behavior
#
# Tests ~22 routes across NJT, Amtrak, PATH, LIRR, and Metro-North by
# replicating the exact API call sequence the iOS app makes:
#   1. Fetch departures for a route
#   2. Fetch train detail (with predictions) for the first active train
#   3. Fetch track + delay predictions at ML-enabled stations
#
# Usage: ./scripts/e2e-api-test.sh [base_url]
#   base_url defaults to https://staging.apiv2.trackrat.net

set -euo pipefail

BASE="${1:-https://staging.apiv2.trackrat.net}"
API="$BASE/api/v2"
TODAY=$(date +%Y-%m-%d)
PASS=0
FAIL=0
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

pass() { printf "  ${GREEN}PASS${NC} %s\n" "$1"; PASS=$((PASS + 1)); }
fail() { printf "  ${RED}FAIL${NC} %s\n" "$1"; FAIL=$((FAIL + 1)); }
fail_v() { printf "  ${RED}FAIL${NC} %s\n       %s\n" "$1" "$2"; FAIL=$((FAIL + 1)); }

# Fetch URL, write body to $TMPDIR/resp.json, print HTTP status code (000 on timeout/error)
api() { curl -s -o "$TMPDIR/resp.json" -w "%{http_code}" --max-time 15 "$1" 2>/dev/null || echo "000"; }

# --- Preflight ---

command -v jq >/dev/null 2>&1 || { echo "jq is required"; exit 1; }

echo -e "${BOLD}TrackRat E2E API Test${NC}"
echo -e "Target: $BASE"
echo -e "Date:   $TODAY\n"

echo -e "${BOLD}Health check...${NC}"
code=$(api "$BASE/health")
if [[ "$code" != "200" ]]; then
  echo -e "${RED}Health check failed (HTTP $code). Aborting.${NC}"
  exit 1
fi
status=$(jq -r '.status' "$TMPDIR/resp.json")
env=$(jq -r '.environment // "unknown"' "$TMPDIR/resp.json")
echo -e "Status: $status | Environment: $env\n"

# --- Routes ---
# Format: "label|from|to|data_source|ml_station (empty if none)"

ROUTES=(
  # NJ Transit
  "NJT NEC|NY|TR|NJT|NY"
  "NJT NJCL|NY|LB|NJT|NY"
  "NJT Morris & Essex|HB|DV|NJT|HB"
  "NJT Raritan Valley|NP|HG|NJT|NP"
  "NJT Main Line|HB|SF|NJT|HB"
  # Amtrak
  "Amtrak NEC|NY|WS|AMTRAK|NY"
  "Amtrak Keystone|PH|HAR|AMTRAK|PH"
  "Amtrak Empire|NY|ALB|AMTRAK|NY"
  "Amtrak Acela|NY|BOS|AMTRAK|NY"
  "Amtrak NEC Short|NY|PH|AMTRAK|NY"
  # PATH
  "PATH HOB-33|PHO|P33|PATH|"
  "PATH NWK-WTC|PNK|PWC|PATH|"
  # LIRR
  "LIRR Babylon|JAM|BTA|LIRR|JAM"
  "LIRR Ronkonkoma|JAM|RON|LIRR|JAM"
  "LIRR Port Washington|NY|PWS|LIRR|"
  "LIRR Long Beach|JAM|LBH|LIRR|JAM"
  "LIRR Hempstead|JAM|LHEM|LIRR|JAM"
  # Metro-North
  "MNR Hudson|GCT|MPOK|MNR|GCT"
  "MNR Harlem|GCT|MWAS|MNR|GCT"
  "MNR New Haven|GCT|MSTM|MNR|GCT"
  "MNR New Haven Full|GCT|MNSS|MNR|GCT"
  "MNR Hudson Short|GCT|MCRN|MNR|GCT"
)

# --- Test loop ---

for route in "${ROUTES[@]}"; do
  IFS='|' read -r label from to source ml <<< "$route"
  echo -e "${YELLOW}--- $label ($from -> $to) ---${NC}"

  # 1. DEPARTURES (iOS: fetchDepartures)
  code=$(api "$API/trains/departures?from=$from&to=$to&limit=50&hide_departed=true&data_sources=$source")
  if [[ "$code" != "200" ]]; then
    fail "Departures: HTTP $code"
    echo ""
    continue
  fi
  cp "$TMPDIR/resp.json" "$TMPDIR/dep.json"

  count=$(jq '.departures | length' "$TMPDIR/dep.json")
  if [[ "$count" -eq 0 ]]; then
    fail "Departures: 0 trains"
    echo ""
    continue
  fi
  pass "Departures: $count trains"

  # Both SCHEDULED and OBSERVED must be present
  sched=$(jq '[.departures[] | select(.observation_type == "SCHEDULED")] | length' "$TMPDIR/dep.json")
  obs=$(jq '[.departures[] | select(.observation_type == "OBSERVED")] | length' "$TMPDIR/dep.json")
  if [[ "$sched" -eq 0 ]]; then
    fail "No SCHEDULED trains ($obs observed, 0 scheduled)"
  elif [[ "$obs" -eq 0 ]]; then
    fail "No OBSERVED trains ($sched scheduled, 0 observed)"
  else
    pass "Mix: $sched scheduled + $obs observed"
  fi

  # Required fields on every departure
  bad=$(jq '[.departures[] | select(
    .train_id == null or .data_source == null or
    .departure.scheduled_time == null or
    .line.color == null or .line.code == null
  )] | length' "$TMPDIR/dep.json")
  if [[ "$bad" -gt 0 ]]; then
    sample=$(jq -c '[.departures[] | select(
      .train_id == null or .data_source == null or
      .departure.scheduled_time == null or
      .line.color == null or .line.code == null
    )][0] | {train_id, data_source, line: .line.code, color: .line.color, time: .departure.scheduled_time}' "$TMPDIR/dep.json")
    fail_v "$bad departures missing required fields" "$sample"
  else
    pass "Required fields present"
  fi

  # Line color hex format
  bad=$(jq '[.departures[].line.color // "" | select(. != "" and (test("^#[0-9A-Fa-f]{6}$") | not))] | length' "$TMPDIR/dep.json")
  if [[ "$bad" -gt 0 ]]; then
    sample=$(jq -r '[.departures[].line.color // "" | select(. != "" and (test("^#[0-9A-Fa-f]{6}$") | not))][0]' "$TMPDIR/dep.json")
    fail_v "Invalid line color on $bad departures" "Got: $sample"
  else
    pass "Line colors valid"
  fi

  # Data source matches expected
  wrong=$(jq --arg s "$source" '[.departures[] | select(.data_source != $s)] | length' "$TMPDIR/dep.json")
  if [[ "$wrong" -gt 0 ]]; then
    got=$(jq -r --arg s "$source" '[.departures[] | select(.data_source != $s) | .data_source] | unique | join(", ")' "$TMPDIR/dep.json")
    fail_v "$wrong departures have wrong data_source" "Expected: $source, got: $got"
  else
    pass "Data source: $source"
  fi

  # 2. TRAIN DETAIL (iOS: fetchTrainDetails with include_predictions=true)
  train_id=$(jq -r '[.departures[] | select(.is_cancelled != true)][0].train_id // empty' "$TMPDIR/dep.json")
  j_date=$(jq -r '[.departures[] | select(.is_cancelled != true)][0].journey_date // empty' "$TMPDIR/dep.json" | cut -dT -f1)

  if [[ -z "$train_id" ]]; then
    fail "All trains cancelled - cannot test detail"
    echo ""
    continue
  fi

  code=$(api "$API/trains/${train_id}?date=${j_date}&include_predictions=true&from_station=${from}&data_source=${source}")
  if [[ "$code" != "200" ]]; then
    fail "Detail ($train_id): HTTP $code"
    echo ""
    continue
  fi
  cp "$TMPDIR/resp.json" "$TMPDIR/detail.json"

  stops=$(jq '.train.stops | length' "$TMPDIR/detail.json")
  if [[ "$stops" -lt 2 ]]; then
    fail "Train $train_id: $stops stops (need >=2)"
  else
    pass "Train $train_id: $stops stops"
  fi

  bad=$(jq '[.train.stops[] | select(
    .station.code == null or
    (.scheduled_departure == null and .scheduled_arrival == null)
  )] | length' "$TMPDIR/detail.json")
  if [[ "$bad" -gt 0 ]]; then
    fail "Train $train_id: $bad stops missing station code or times"
  else
    pass "Train $train_id: stops valid"
  fi

  has_route=$(jq '.train.route | (.origin_code != null and .destination_code != null)' "$TMPDIR/detail.json")
  if [[ "$has_route" != "true" ]]; then
    fail "Train $train_id: missing route codes"
  else
    pass "Train $train_id: route present"
  fi

  # 3. PREDICTIONS (iOS: inline predictions + standalone endpoints, ML stations only)
  if [[ -n "$ml" ]]; then
    # Track prediction
    code=$(api "$API/predictions/track?station_code=${ml}&train_id=${train_id}&journey_date=${j_date}")
    if [[ "$code" == "200" ]]; then
      primary=$(jq -r '.primary_prediction // "null"' "$TMPDIR/resp.json")
      conf=$(jq '.confidence // 0' "$TMPDIR/resp.json")
      plats=$(jq '.platform_probabilities | length' "$TMPDIR/resp.json")
      if [[ "$plats" -gt 0 && "$primary" != "null" ]]; then
        pass "Track prediction: $primary (conf: $conf, $plats platforms)"
      else
        fail "Track prediction: empty response"
      fi
    elif [[ "$code" == "404" || "$code" == "400" ]]; then
      pass "Track prediction: N/A ($code)"
    else
      fail "Track prediction: HTTP $code"
    fi

    # Delay prediction
    code=$(api "$API/predictions/delay?train_id=${train_id}&station_code=${ml}&journey_date=${j_date}")
    if [[ "$code" == "200" ]]; then
      samples=$(jq '.sample_count // 0' "$TMPDIR/resp.json")
      on_time=$(jq '.delay_probabilities.on_time // 0' "$TMPDIR/resp.json")
      if jq -e '.sample_count > 0' "$TMPDIR/resp.json" >/dev/null 2>&1; then
        pass "Delay prediction: $samples samples, on-time: $on_time"
      else
        fail "Delay prediction: 0 samples"
      fi
    elif [[ "$code" == "404" || "$code" == "400" ]]; then
      pass "Delay prediction: N/A ($code)"
    else
      fail "Delay prediction: HTTP $code"
    fi
  fi

  echo ""
done

# --- Summary ---

echo -e "${BOLD}========== SUMMARY ==========${NC}"
total=$((PASS + FAIL))
echo -e "  ${GREEN}PASS${NC}: $PASS"
echo -e "  ${RED}FAIL${NC}: $FAIL"
echo -e "  Total: $total checks across ${#ROUTES[@]} routes"

if [[ "$FAIL" -gt 0 ]]; then
  echo -e "\n${RED}FAILED${NC}"
  exit 1
else
  echo -e "\n${GREEN}ALL PASSED${NC}"
fi
