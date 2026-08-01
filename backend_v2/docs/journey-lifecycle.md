# Journey Lifecycle & Data Semantics

The reference for how a `train_journeys` row and its `journey_stops` behave
over a train's run: which flags exist, who sets and clears them, what the
provider time fields actually mean, and the invariants that past incidents
taught us. **Read this before touching any collector, the JIT service, or
any consumer of `updated_arrival`/`updated_departure`.**

Almost every recurring production bug in this system (issues #1115, #1329,
#1487–#1508) came from violating one of the rules below.

## 1. The journey state machine

`observation_type`: `SCHEDULED` (created by schedule generation before the
train exists in a real-time feed) → `OBSERVED` (promoted when real-time data
first arrives). Promotion is one-way by design.

Lifecycle flags — each one **blocks refresh paths**, so each must have at
least one automatic writer that can clear it (see the invariant below):

| Flag | Meaning | Set by | Cleared by | Blocks |
|---|---|---|---|---|
| `is_expired` | Row abandoned (feed lost the train / sustained mismatch) | 3-strike not-found / sustained-mismatch backstops in collectors | NJT: discovery reactivation (`reactivated_expired_train`). Amtrak: reobservation via JIT refresh, or the batch requeue of expired rows (#1500). SEPTA: a valid nonempty feed snapshot or successful JIT refresh reobserves omission-expired journeys. | JIT (`needs_refresh`), background collection candidacy |
| `is_completed` | Run finished | Terminal-arrival detection; completion-on-expiry backstops; Amtrak `trainState == "Terminated"` | Nothing (final state) | JIT, batch collection, Live Activity updates end |
| `is_cancelled` | Run annulled | NJT: API `STOP_STATUS` (all stops or terminal cancelled). Amtrak: `trainState == "Cancelled"` | Amtrak: reobservation. **NJT: nothing — known one-way door, issue #1498** | JIT, all scheduler NJT update queries, discovery fuzzy re-match |
| `api_error_count` | Strike counter toward expiry | Incremented on not-found / mismatch | Reset on any successful fetch/reobservation (all collectors and paths that use it) | ≥3 triggers the expiry backstops |

**Invariant (the #1489 rule): any flag that blocks refresh must have an
automatic writer that can clear it.** A flag with no clearer is a one-way
door: one transient feed gap or data glitch strands the row for its lifetime
— users see frozen or "Cancelled" data while the train runs. This exact
shape shipped four times (#1115, #1489, #1498, #1500) before it was named.
When adding a new gate to `JustInTimeUpdateService.needs_refresh` or a new
scheduler candidate filter, identify the clearer first.

SEPTA omission strikes are reconciled only from a successfully fetched,
nonempty whole-system snapshot. HTTP, network, and protobuf failures and
globally empty snapshots are not evidence that every active trip disappeared.
Feed presence is recorded before per-trip enrichment so a local processing
failure cannot turn a trip that was visibly present into an omission strike.

Known open gaps: the NJT `is_cancelled` clearer (#1498) and the NJT
silent-cancellation *setter* — `JourneyCollector._reconcile_unobserved_trains`
is dead code that nothing schedules (#1497).

## 2. NJT `TIME` / `DEP_TIME` field semantics (the inversion)

`JourneyStop.updated_arrival` / `updated_departure` are **raw passthroughs**
of NJT's `TIME` / `DEP_TIME` fields, whose meaning depends on stop position
(established by direct API testing; see `normalize_njt_stop_times` in
`collectors/njt/journey.py`):

| Stop position | `TIME` → `updated_arrival` | `DEP_TIME` → `updated_departure` |
|---|---|---|
| **Origin** | original schedule (immutable) | **live departure estimate — moves with delays** |
| **Intermediate** | **live arrival estimate — moves with delays** | original schedule (immutable) |
| **Terminal** | **live arrival estimate** | usually absent; when present it can be a **later turnaround departure** (#1492) |

`SCHED_DEP_DATE` / `SCHED_ARR_DATE` are the immutable schedule everywhere —
always prefer them for schedule-to-schedule comparisons (#1496: comparing
the origin's live `DEP_TIME` against a stored schedule falsely expired every
train delayed >10 min before departure).

### Consumer rules

1. **Never read `updated_arrival`/`updated_departure` raw for NJT.** Route
   through `utils/train.effective_njt_updated_times(stop, data_source,
   is_terminal)` — it applies `max()` at intermediate stops (surfacing the
   live estimate) and skips it at the terminal (where the `max()` would
   promote the turnaround time and inflate the arrival).
2. **Terminal detection must be conservative.** Use
   `utils/train.terminal_stop_index()` — positional detection is only
   trusted when every stop is sequenced AND the last stop matches
   `terminal_station_code`. Partially collected journeys keep the `max()`.
3. **In SQL**, the twin is
   `GREATEST(updated_departure, updated_arrival)` guarded by
   `data_source = 'NJT' AND both IS NOT NULL` (see the congestion
   `stop_pairs` CTE, #1503). Segment from-stops are never terminals when
   consumers filter `to_station IS NOT NULL`, so no terminal exemption is
   needed there.
4. The **arrival side is safe**: `updated_arrival or updated_departure` is
   correct for NJT at both intermediate and terminal stops.
5. Non-NJT providers carry genuine live estimates in both fields — the
   helper passes them through unchanged; never apply the `max()` manually.

This family shipped as a bug **five separate times** (#1268 `/trains/{id}`,
#1487/#1492 terminal inflation, #1503 congestion, #1504 Live Activities,
#1505 departure boards) precisely because inline copies of the correction
existed. If you find yourself writing `max(updated_...)` inline, stop and
use the helper.

## 3. `journey_date` convention

`journey_date` is the **service date of the train's origin departure**, not
the date any code happened to run:

- NJT discovery derives it from `SCHED_DEP_DATE` at the discovered station.
- NJT schedule generation derives each train's date from its **earliest**
  departure across all stations in the 27-hour window (#1499 — stamping the
  run date created a zombie duplicate for every after-midnight departure;
  per-item dates would split cross-midnight trains into two rows).
- Amtrak derives it from the first *surviving* feed stop's `schDep` —
  imperfect mid-run because the feed trims passed stations (see §4).
- Queries over active NJT trains must use a yesterday-inclusive window
  (`journey_date >= today - 1`), never `== today`: after-midnight legs of a
  cross-midnight run carry the prior service date.

## 4. Amtrak feed semantics

- **The Amtraker feed trims already-passed stations.** Any "first stop" /
  "lowest sequence" heuristic sees a *future* stop mid-run. Durable signals
  live on the journey row instead: `journey.actual_departure` is recorded
  **write-once, keyed to the origin stop** while that stop is still in the
  feed (#1501), and gates the expiry backstop (`_has_departed_origin`).
- **Stop deletion is guarded**: stops absent from the feed are deleted only
  when they carry no recorded reality (`has_departed_station = False`, no
  actuals) — pattern-scheduler template stops for unserved stations are
  still cleaned up; passed stops with recorded actuals are preserved
  (#1502).
- **Sequencing**: surviving feed stops are numbered starting *after* the
  preserved stops' max sequence, so trimming never collides sequences.
  `stops_count` is recounted from the DB, not `len(feed stops)`.
- **Two stop-sync paths, one contract**: `_convert_to_journey`
  (discovery/batch — new rows, SCHEDULED promotion, and expired-row requeue)
  and `collect_journey_details` (JIT / Live Activity refresh). Both must
  carry the three protections above; the #1500 requeue is what first routed
  mid-run rows through `_convert_to_journey`.
- Known residual: Amtrak train numbers recur daily and long-haul instances
  run concurrently; the per-number dedup can refresh a row from the other
  physical instance around midnight. Bounded (no permanent corruption after
  #1500's hardening) but not yet solved.

## 5. Partial-collection states

Until full collection, NJT rows carry `stop_sequence = NULL` placeholder
stops and a **placeholder** `terminal_station_code` (the discovery/schedule
station). Rules:

- Positional logic (last stop = terminal, top-2 = terminal/penultimate) is
  only valid on fully sequenced journeys — decline otherwise
  (`terminal_stop_index` posture; completion-on-expiry does the same).
- Postgres orders NULLs **FIRST** under `ORDER BY ... DESC`; always add
  `.nulls_last()` when sorting by `stop_sequence` descending (#1506).

## 6. Scheduler task failure handling

Freshness-wrapped tasks (`run_with_freshness_check`) must **re-raise** after
logging a failure (#1507, and the retention_cleanup precedent). Swallowing
the exception stamps `last_successful_run`, which both masks the failure
from monitoring and skips the retry as "still fresh". The wrapper handles a
raising task correctly (rollback, `task_execution_failed`, no timestamp).

## 7. Testing gotchas

- **Postgres vs SQLite divergence**: some collector unit tests run on
  SQLite, which orders NULLs LAST on DESC — the opposite of Postgres. Bugs
  in NULL-sequence handling are structurally invisible on SQLite; write
  such tests against the Postgres `db_session` fixture.
- **Anchor test times relative to `now_et()`** when exercising the full
  update path: absolute times-of-day (e.g. `replace(hour=7)`) fall into the
  past depending on when the suite runs, and departure inference /
  completion logic legitimately fires on past times.
- Unit tests expect PostgreSQL on port 5434
  (`postgresql+asyncpg://trackratuser:password@localhost:5434/trackratdb_test`),
  matching CI. NJT test fixtures (`tests/fixtures/njt_api_responses.py`)
  default `SCHED_DEP_DATE = None`, so tests exercise the DEP_TIME fallback
  unless they opt in via `sched_dep_date=`.
