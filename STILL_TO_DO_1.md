# MTA Collector Remaining Work

## Context

The core fix (departure status, journey metadata, completion detection) was committed in `e1d6643`. These are lower-priority follow-ups identified during that investigation.

## 1. MNR Route Filtering — Skip

**What it looked like:** Querying `route=MNR_HUDSON` and `route=MNR_HARLEM` returned identical results.

**What we found:** The departures endpoint has no `route` parameter — it never did. FastAPI silently ignores unknown query params. Filtering works by station pair (`from`/`to`), which implicitly selects the correct MNR line since each line serves distinct stations. The iOS app uses station pairs, not routes.

**Verdict:** Not a bug. Working as designed. No action needed.

## 2. MTA `trainStatus` Protobuf Field — Low Priority

**What it is:** Field 2 in the `MtaRailroadStopTimeUpdate` extension message. Currently defined in `mta_extensions.py` but never extracted. Only `track` (field 1) is parsed.

**What we don't know:** What values this field contains in practice. No public MTA documentation confirms the value set. It could be "ON TIME", "LATE", etc., or it could be empty/unused.

**What it would take:** ~10 lines — add `extract_mta_train_status()` following the existing `extract_mta_track()` pattern, log the values on staging for a few collection cycles, then decide if they're useful.

**Verdict:** Low ROI. The time-based departure inference already covers what this field would likely provide. Worth a quick exploratory extraction if someone is already touching `mta_extensions.py`, but not worth a dedicated effort.

## 3. JIT Trip Matching Improvement — Medium Priority

**The problem:** When a user views a single MNR/LIRR train detail, JIT fires (data is >60s stale between 4-min collection cycles) and uses station-overlap matching to find the right trip in the GTFS-RT feed. Two trains on the same branch share identical station sets, so the "best overlap" heuristic could pick the wrong train.

**Practical risk:** Low-to-moderate. Cross-branch matches are fine (different stations). Same-branch wrong matches are possible but mitigated by: completed trains are excluded from JIT, and trains that dropped from the feed produce no match (so no data corruption).

**Recommended fix:** Reverse the `_generate_train_id` mapping. For LIRR, `L181` came from `trip_id` with `_181` as the 3rd segment — search for a trip whose `trip_id.split("_")[2] == "181"`. For MNR, `M987342` came from `trip_id` `2987342` — search for a trip whose `trip_id` ends with `987342`. Direct match eliminates ambiguity. Fall back to station overlap only if no direct match found.

**What it would take:** ~15 lines per collector in `collect_journey_details`. Add a `_match_trip_id(train_id)` helper that reverses the ID generation, try direct match first, fall back to station overlap.

**Verdict:** Worth doing eventually. The fix is small and eliminates a real (if uncommon) source of incorrect data on train detail views. Good candidate for next time someone is working on MTA collectors.
