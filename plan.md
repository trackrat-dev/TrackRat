# Transit Transfers: Design Proposal

## Overview

Add implicit transfer support: when a user picks two stations with no direct service, the backend automatically finds 1-transfer connections using real-time departure data.

## Architecture

### New endpoint: `GET /api/v2/trips/search`

Single smart endpoint replaces the departures call on clients. Internally:
1. Checks for direct service (reuses existing `DepartureService.get_departures()`)
2. If direct trains exist → returns them as single-leg trips
3. If no direct trains → runs connection search and returns multi-leg options

**No changes to existing `/api/v2/trains/departures` endpoint.** It stays for backward compatibility and internal use by the trip search.

### Response shape

```python
class TripLeg(BaseModel):
    train_id: str
    journey_date: date
    line: LineInfo
    data_source: str
    boarding: StationInfo      # where you board
    alighting: StationInfo     # where you exit
    destination: str           # train's final destination (for display)
    observation_type: str
    is_cancelled: bool
    train_position: TrainPosition | None

class TransferInfo(BaseModel):
    from_station: StationInfo  # where you exit leg N
    to_station: StationInfo    # where you board leg N+1
    walk_minutes: int          # estimated walk time
    same_station: bool         # same physical station vs short walk

class TripOption(BaseModel):
    legs: list[TripLeg]
    transfers: list[TransferInfo]    # len = len(legs) - 1
    departure_time: datetime         # first leg boarding time
    arrival_time: datetime           # last leg alighting time
    total_duration_minutes: int
    is_direct: bool                  # single leg, no transfers

class TripSearchResponse(BaseModel):
    trips: list[TripOption]
    metadata: dict[str, Any]
```

For direct service, each `TripOption` has 1 leg and 0 transfers. Clients render this identically to current behavior — just mapping `TripLeg` fields to what they currently get from `TrainDeparture`.

### Scope limitation: 1 transfer max (2 legs)

This covers the vast majority of NYC-area trips. Multi-transfer can be added later. This simplifies the algorithm significantly — we're matching timetables at transfer points, not running graph search.

---

## Backend changes

### 1. Transfer point auto-generation

**New file:** `backend_v2/src/trackrat/config/transfer_points.py`

Uses `STATION_COORDINATES` to find station pairs within walking distance (~400m) across different transit systems. Also detects shared station codes (e.g., `NY` used by NJT, Amtrak, LIRR).

```python
@dataclass(frozen=True)
class TransferPoint:
    station_a: str           # station code in system A
    system_a: str            # data source (e.g., "NJT")
    station_b: str           # station code in system B
    system_b: str
    walk_meters: float       # 0 for same-station transfers
    walk_minutes: int        # estimated (walk_meters / 80m per minute, min 3)
    same_station: bool       # same physical station

TRANSFER_POINTS: tuple[TransferPoint, ...]  # auto-generated at import time
```

**Generation logic:**
1. Scan `ALL_ROUTES` to build `{station_code: set[data_source]}` mapping
2. Shared codes (same code, multiple systems) → `TransferPoint` with `walk_meters=0, same_station=True`
3. Existing `STATION_EQUIVALENCE_GROUPS` → same treatment
4. Coordinate proximity: for each pair of stations in different systems, compute haversine distance. If ≤ 400m → `TransferPoint` with estimated walk time
5. Deduplicate (A↔B and B↔A are the same transfer)

**Lookup indexes** (built at import time):
```python
# Given two systems, what transfer points connect them?
_TRANSFERS_BY_SYSTEM_PAIR: dict[tuple[str, str], list[TransferPoint]]

# Given a station, what transfers are available?
_TRANSFERS_BY_STATION: dict[str, list[TransferPoint]]

def get_transfer_points(system_a: str, system_b: str) -> list[TransferPoint]
def get_transfers_from_station(station_code: str) -> list[TransferPoint]
```

### 2. Trip search service

**New file:** `backend_v2/src/trackrat/services/trip_search.py`

```python
class TripSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.departure_service = DepartureService(db)

    async def search(
        self,
        from_station: str,
        to_station: str,
        date: date | None = None,
        time_from: time | None = None,
        time_to: time | None = None,
        data_sources: list[str] | None = None,
        hide_departed: bool = False,
        limit: int = 10,
    ) -> TripSearchResponse:
```

**Algorithm:**
1. Call `self.departure_service.get_departures(from_station, to_station, ...)` for direct trains
2. If results → wrap each `TrainDeparture` as a single-leg `TripOption`, return
3. If no results → find connections:
   a. Determine which systems serve `from_station` and `to_station` (scan `ALL_ROUTES`)
   b. For each system pair `(sys_from, sys_to)` where `sys_from ≠ sys_to`:
      - Get `transfer_points = get_transfer_points(sys_from, sys_to)`
      - For each transfer point:
        - Query departures: `from_station → transfer.station_a` (filtered to `sys_from`)
        - Query departures: `transfer.station_b → to_station` (filtered to `sys_to`)
        - Match connections: first leg arrival + transfer walk time ≤ second leg departure
        - Build `TripOption` for each valid pair
   c. Also check: can the same system serve both if we expand to equivalent stations? (handles cases where equivalence provides a direct route)
4. Sort by `departure_time`, then `total_duration_minutes`
5. Return top `limit` options

**Performance considerations:**
- Transfer point lookup is O(1) (pre-computed dict)
- Departure queries reuse the existing optimized SQL + caching
- Worst case for a 2-system transfer: ~2-4 departure queries (one per transfer point per direction)
- Typical case: 1-2 transfer points between any two systems
- Cache the trip search response the same way departures are cached (120s TTL)

### 3. API endpoint

**New route in:** `backend_v2/src/trackrat/api/trains.py` (or new file `trips.py`)

```python
@router.get("/api/v2/trips/search")
async def search_trips(
    from_station: str = Query(..., alias="from"),
    to_station: str = Query(..., alias="to"),
    date: date | None = None,
    time_from: time | None = None,
    time_to: time | None = None,
    hide_departed: bool = False,
    data_sources: str | None = None,
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
) -> TripSearchResponse:
```

Parameters mirror the existing departures endpoint for easy client migration.

---

## iOS changes

### Station picker: remove system filtering for destination

Currently, destination picker only shows stations from `appState.selectedSystems`. For transfers to work, the destination picker should show all stations (or at least stations reachable via transfer from the origin's systems).

**Simplest approach:** Keep system filtering for the origin station (user picks where they're starting from within their enabled systems). For the destination, show all stations — the backend will figure out if a transfer is needed.

**Files changed:**
- `ios/TrackRat/Views/Screens/DestinationPickerView.swift` — remove or relax `selectedSystems` filter

### TrainListView → TripListView migration

Replace the departures API call with the trip search call. The view needs to handle both single-leg and multi-leg results.

**Single-leg rendering:** Identical to current `TrainDeparture` rows. Same visual, just sourced from `TripOption.legs[0]`.

**Multi-leg rendering:** Show as a single card with:
- First leg departure time and station
- Transfer indicator (station name + walk time)
- Last leg arrival time and station
- Total duration
- Both line colors/names

**Files changed:**
- `ios/TrackRat/Views/Screens/TrainListView.swift` — new view model logic, updated row rendering
- `ios/TrackRat/Services/APIService.swift` — new `searchTrips()` method
- `ios/TrackRat/Models/V2APIModels.swift` — new response types (`TripOption`, `TripLeg`, `TransferInfo`)

### TrainDetailsView

When user taps a multi-leg trip, show both legs' stops with a transfer section between them. Single-leg trips show identical to current behavior.

**Files changed:**
- `ios/TrackRat/Views/Screens/TrainDetailsView.swift` — handle multi-leg display

### Out of scope (confirmed)
- Live Activity changes (stays single-train)
- Push notification changes

---

## Web changes

### Station picker

Web already shows all stations from all systems — no changes needed.

### TrainListPage

Same migration as iOS: call `/trips/search` instead of `/departures`. Handle multi-leg rendering.

**Files changed:**
- `webpage_v2/src/pages/TrainListPage.tsx` — updated API call, new trip row component
- `webpage_v2/src/services/api.ts` — new `searchTrips()` method
- `webpage_v2/src/types/` — new TypeScript types for trip response

### TrainDetailsPage

Handle multi-leg display.

**Files changed:**
- `webpage_v2/src/pages/TrainDetailsPage.tsx` — multi-leg stop list

---

## Implementation order

### Phase 1: Backend transfer infrastructure
1. `transfer_points.py` — auto-generate transfer map from coordinates + equivalences + shared codes
2. Tests for transfer point generation (verify known NYC-area transfer hubs are discovered)
3. `trip_search.py` — service with connection matching algorithm
4. Tests for trip search (direct service returns single-leg, cross-system returns multi-leg)
5. API endpoint + response models
6. API tests

### Phase 2: iOS client
7. New API models and service method
8. Destination picker: relax system filtering
9. TripListView: render both single-leg and multi-leg results
10. TripDetailsView: multi-leg stop display

### Phase 3: Web client
11. New TypeScript types and API method
12. TrainListPage: render both result types
13. TrainDetailsPage: multi-leg display

### Phase 4: Polish
14. Review auto-generated transfer points, tune distance threshold if needed
15. Add transfer walk time estimates based on real-world knowledge (override auto-calculated times for major hubs)
16. Edge cases: cancelled first leg, delayed connections

---

## Key design decisions recap

| Decision | Choice | Rationale |
|---|---|---|
| Where does composition live? | Backend | Complex logic, unified across clients |
| How does user trigger it? | Implicit | Backend handles direct vs transfer transparently |
| Transfer map source | Auto-generated from coordinates | Low maintenance, iterate from feedback |
| Max transfers | 1 (2 legs) | Covers NYC area, keeps algorithm simple |
| New endpoint vs modify existing | New `/trips/search` | No breaking changes to existing clients |
| Live Activity | Out of scope | Revisit after core transfer work |
| System filtering (iOS dest picker) | Relaxed for destination | Required for cross-system transfers |

---

## What this does NOT change

- Existing `/api/v2/trains/departures` endpoint (unchanged, backward compatible)
- TrainJourney / JourneyStop database models (no schema changes)
- Data collectors (no changes)
- Congestion/analytics endpoints (no changes)
- Live Activities (out of scope)
- Route alerts / notifications (no changes)
