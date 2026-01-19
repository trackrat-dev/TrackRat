# Transit System Integrations

This document describes the architecture for integrating transit systems into TrackRat, covering the four currently supported systems and providing guidance for adding new ones.

## Overview

TrackRat supports multiple transit systems through a unified data model while accommodating the unique characteristics of each system's data source. The architecture handles three primary integration patterns:

| Pattern | Systems | Characteristics |
|---------|---------|-----------------|
| **Real-time + Discovery/Journey** | NJ Transit, Amtrak | Two-phase collection with separate discovery and journey detail collectors |
| **Real-time + Unified Collection** | PATH | Single-phase collector handles both discovery and updates |
| **Schedule-only (GTFS)** | PATCO | No real-time API; served directly from GTFS static schedules |

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL DATA SOURCES                          │
├─────────────────────────────────────────────────────────────────────────┤
│  NJ Transit API    Amtraker API    Transiter API    GTFS Static Feeds   │
│    (XML/Auth)       (JSON/No Auth)  (JSON/No Auth)    (Schedule Data)   │
└────────┬─────────────────┬──────────────┬──────────────────┬────────────┘
         │                 │              │                  │
         v                 v              v                  v
┌─────────────────────────────────────────────────────────────────────────┐
│                              COLLECTORS                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  NJTClient          AmtrakClient    PathClient        GTFSService       │
│  NJTDiscovery       AmtrakDiscovery PathCollector     (direct service)  │
│  NJTJourney         AmtrakJourney                                       │
└────────┬─────────────────┬──────────────┬──────────────────┬────────────┘
         │                 │              │                  │
         └────────────────┬┴──────────────┴──────────────────┘
                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED DATA MODEL                               │
├─────────────────────────────────────────────────────────────────────────┤
│  TrainJourney (one per train per day)                                   │
│  JourneyStop (one per station per journey)                              │
│  JourneySnapshot (status snapshots for history)                         │
└────────────────────────────────────────────────────────────────────────┘
                          │
                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                           UNIFIED API                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  TrainDeparture, TrainDetails (consistent response regardless of source)│
│  data_source field: "NJT" | "AMTRAK" | "PATH" | "PATCO"                │
│  observation_type: "OBSERVED" (real-time) | "SCHEDULED" (GTFS only)    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## System 1: NJ Transit (Real-time with Discovery/Journey Pattern)

**Reference implementation for proprietary real-time APIs with rich data.**

### Data Source

| Property | Value |
|----------|-------|
| API Endpoint | `https://raildata.njtransit.com/api/TrainData` |
| Format | XML responses |
| Authentication | API token required (`TRACKRAT_NJT_API_TOKEN`) |
| Rate Limits | Reasonable for production use |

### Collector Architecture

```
collectors/njt/
├── client.py      # API client with XML parsing
├── discovery.py   # Discovers active trains at hub stations
└── journey.py     # Fetches complete journey details
```

**Discovery Collector** (`discovery.py`):
- Polls 7 major hub stations (NY, NP, PJ, TR, LB, PL, DN)
- Uses `getDepartureVisionData` API method
- Returns list of discovered train IDs
- Runs every 30 minutes via scheduler

**Journey Collector** (`journey.py`):
- Fetches complete stop lists via `getTrainStopList`
- Creates/updates `TrainJourney` and `JourneyStop` records
- Handles track assignments, departure flags, actual times
- Implements `collect_journey_details()` for JIT refresh

### Key Implementation Details

```python
# Discovery pattern - collect train IDs from hub stations
class NJTDiscoveryCollector(BaseDiscoveryCollector):
    async def discover_trains(self) -> list[str]:
        train_ids = []
        for station in DISCOVERY_STATIONS:
            response = await self.client.get_departure_vision_data(station)
            train_ids.extend(self._parse_train_ids(response))
        return list(set(train_ids))

# Journey pattern - fetch complete journey for each train
class NJTJourneyCollector(BaseJourneyCollector):
    async def collect_journey(self, train_id: str) -> TrainJourney | None:
        response = await self.client.get_train_stop_list(train_id)
        return self._convert_to_journey(response)

    # JIT refresh method - called by JustInTimeUpdateService
    async def collect_journey_details(self, session: AsyncSession, journey: TrainJourney):
        # Re-fetch and update existing journey
        ...
```

### Station Code Handling
- NJ Transit uses 2-character codes directly (e.g., "NY", "NP", "TR")
- No mapping required - codes are used as-is in TrackRat

### Quirks and Edge Cases
1. **Track sanitization**: Raw track values may have trailing spaces or invalid characters
2. **Departed flag staleness**: `DEPARTED=YES` can be stale for future trains - override based on scheduled time
3. **Empty ITEMS array**: Low-traffic stations return empty arrays - handle gracefully

---

## System 2: Amtrak (Real-time with Discovery/Journey Pattern)

**Reference implementation for public JSON APIs.**

### Data Source

| Property | Value |
|----------|-------|
| API Endpoint | `https://api-v3.amtraker.com/v3/trains` |
| Format | JSON responses |
| Authentication | None required |
| Rate Limits | Fair use expected |

### Collector Architecture

```
collectors/amtrak/
├── client.py      # API client with caching
├── discovery.py   # Discovers trains at NEC hub stations
└── journey.py     # Processes journey details from same API data
```

**Key Differences from NJ Transit:**
- Single API call returns all active trains with complete stop lists
- 30-second client-side cache to reduce API calls
- Train IDs prefixed with "A" internally (e.g., "A2150" for train 2150)

### Station Code Mapping

Amtrak uses different station codes than TrackRat's internal codes:

```python
# config/stations.py
AMTRAK_TO_INTERNAL_STATION_MAP = {
    "NYP": "NY",   # New York Penn Station
    "NWK": "NP",   # Newark Penn
    "TRE": "TR",   # Trenton
    "PHL": "PH",   # Philadelphia
    "WAS": "WS",   # Washington Union Station
    # ... more mappings
}
```

### Time Handling
- Amtrak provides ISO 8601 times with timezone offset
- Normalized to Eastern Time for consistency with NJ Transit

### Pattern Scheduler
- Analyzes 22 days of historical data to predict schedules
- Creates `SCHEDULED` records that get upgraded to `OBSERVED` when real-time data appears
- Uses `MIN_OCCURRENCES=2` and `TIME_VARIANCE_THRESHOLD=35` minutes

---

## System 3: PATH (Real-time with Unified Collection Pattern)

**Reference implementation for modern GTFS-RT style APIs.**

### Data Source

| Property | Value |
|----------|-------|
| Primary API | RidePATH API (`https://www.panynj.gov/bin/portauthority/ridepath.json`) |
| Backup API | Transiter (`https://demo.transiter.dev/systems/us-ny-path`) |
| Format | JSON responses |
| Authentication | None required |

### Collector Architecture

```
collectors/path/
├── client.py           # Transiter API client
├── ridepath_client.py  # Native RidePATH API client
└── collector.py        # Unified discovery + update collector
```

**Unified Pattern** (simpler than Discovery/Journey):
- Single `collect()` method handles both discovery and updates
- One API call serves both purposes
- Runs every 4 minutes via scheduler

```python
class PathCollector:
    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        # Single API call
        arrivals = await self.client.get_all_arrivals()

        # Phase 1: Discovery - create new journeys
        discovery_stats = await self._discover_trains(session, arrivals)

        # Phase 2: Updates - refresh existing journeys
        update_stats = await self._update_journeys(session, arrivals)

        return {**discovery_stats, **update_stats}
```

### Train ID Generation

PATH doesn't provide stable train IDs, so we generate deterministic IDs:

```python
def _generate_path_train_id(origin_station: str, headsign: str, departure_time: datetime) -> str:
    dest_short = headsign[:10].replace(" ", "").lower()
    ts = int(departure_time.timestamp())
    return f"PATH_{origin_station}_{dest_short}_{ts}"
```

### Route Configuration

Routes and stop sequences are statically configured:

```python
# config/stations.py
PATH_ROUTES = {
    "859": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "860": ("HOB-WTC", "Hoboken - World Trade Center", "#65c100"),
    "861": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
    "862": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    # ...
}

PATH_ROUTE_STOPS = {
    "859": ["PHO", "PCH", "P9S", "P14", "P23", "P33"],
    "860": ["PHO", "PNP", "PEX", "PWC"],
    # ...
}
```

### Station Code Mapping

PATH requires multiple mappings for different API sources:

```python
# Transiter API stop IDs → Internal codes
PATH_TRANSITER_TO_INTERNAL_MAP = {
    "26730": "PHO",  # Hoboken
    "26734": "PWC",  # World Trade Center
    # ...
}

# RidePATH API codes → Internal codes
PATH_RIDEPATH_API_TO_INTERNAL_MAP = {
    "HOB": "PHO",    # Hoboken
    "WTC": "PWC",    # World Trade Center
    # ...
}

# GTFS stop names → Internal codes (for schedule data)
PATH_GTFS_NAME_TO_INTERNAL_MAP = {
    "hoboken": "PHO",
    "world trade center": "PWC",
    # ...
}
```

### Headsign Handling

PATH trains use headsigns (e.g., "33rd Street", "World Trade Center") instead of line codes:

```python
HEADSIGN_TO_STATION_MAP = {
    "world trade": "PWC",
    "hoboken": "PHO",
    "33rd": "P33",
    "journal square": "PJS",
    # ...
}

HEADSIGN_TO_LINE_INFO = {
    "hoboken": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "world trade center": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    # ...
}
```

---

## System 4: PATCO (Schedule-only via GTFS)

**Reference implementation for systems with no real-time API.**

### Data Source

| Property | Value |
|----------|-------|
| GTFS Feed | `https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/13562/PATCO_GTFS.zip` |
| Format | Standard GTFS static feed |
| Real-time | Not available |

### Architecture

PATCO has no collector - it's served directly by the `GTFSService`:

```python
# services/gtfs.py
class GTFSService:
    async def get_departures_for_station(
        self,
        db: AsyncSession,
        station_code: str,
        data_sources: list[str],  # Includes "PATCO"
        ...
    ) -> list[TrainDeparture]:
        # Query GTFS tables directly
        # Return TrainDeparture API models (not TrainJourney records)
```

### Key Characteristics

1. **No TrainJourney records**: PATCO trains exist only in GTFS tables
2. **observation_type="SCHEDULED"**: All PATCO trains are schedule-based
3. **No JIT refresh**: GTFS data is refreshed daily, not per-request
4. **Direct API models**: Returns `TrainDeparture` models, not database entities

### Station Configuration

```python
PATCO_GTFS_STOP_TO_INTERNAL_MAP = {
    "1": "LND",   # Lindenwold
    "2": "ASD",   # Ashland
    # ... through "14": "FFL" (15-16th and Locust)
}

PATCO_ROUTES = {
    "2": ("PATCO", "PATCO Speedline", "#BC0035"),
}

PATCO_ROUTE_STOPS = [
    "LND", "ASD", "WCT", "HDF", "WMT", "CLD", "FRY",
    "BWY", "CTH", "FKS", "EMK", "NTL", "TWL", "FFL"
]
```

---

## JIT (Just-In-Time) Refresh System

The JIT service provides on-demand data refresh for real-time systems:

```python
# services/jit.py
class JustInTimeUpdateService:
    async def get_collector_for_journey(self, journey: TrainJourney):
        if journey.data_source == "NJT":
            return self.njt_collector
        elif journey.data_source == "AMTRAK":
            return self.amtrak_collector
        elif journey.data_source == "PATH":
            return self.path_collector
        else:
            raise ValueError(f"Unknown data source: {journey.data_source}")

    async def ensure_fresh_data(self, train_id: str, date: date) -> TrainJourney | None:
        journey = await self._get_journey(train_id, date)
        if not journey:
            return None

        if self.needs_refresh(journey):
            collector = await self.get_collector_for_journey(journey)
            await collector.collect_journey_details(session, journey)

        return journey
```

**Staleness threshold**: 60 seconds (configurable via `data_staleness_seconds`)

**PATCO handling**: Since PATCO has no collector, JIT calls would raise `ValueError`. This is handled gracefully - PATCO data is served directly from GTFS without JIT.

---

## Adding a New Transit System

### Step 1: Evaluate the Data Source

Answer these questions:

| Question | Impact on Architecture |
|----------|------------------------|
| Is there a real-time API? | Determines if you need collectors or GTFS-only |
| What format? (JSON/XML/GTFS-RT) | Affects client implementation |
| Authentication required? | Token management in settings |
| Rate limits? | Affects refresh intervals |
| GTFS static feed available? | Enables schedule-based fallback |
| Are train IDs stable? | Affects ID generation strategy |

### Step 2: Choose Integration Pattern

**Pattern A: Real-time with Discovery/Journey** (like NJ Transit, Amtrak)
- Use when: Rich API with separate endpoints for discovery and details
- Pros: Fine-grained control, efficient polling
- Cons: More complex, multiple collectors

**Pattern B: Real-time with Unified Collection** (like PATH)
- Use when: Single API returns both discovery and detail data
- Pros: Simpler, fewer moving parts
- Cons: May fetch more data than needed

**Pattern C: Schedule-only via GTFS** (like PATCO)
- Use when: No real-time API exists
- Pros: Simple, reliable
- Cons: No actual arrival times or delays

### Step 3: Configure Stations and Routes

Add to `config/stations.py`:

```python
# Station names
STATION_NAMES.update({
    "XYZ": "New System Station Name",
    # ...
})

# Station coordinates (for map)
STATION_COORDINATES.update({
    "XYZ": {"lat": 40.1234, "lon": -74.5678},
    # ...
})

# If external API uses different codes
XYZ_TO_INTERNAL_STATION_MAP = {
    "EXTERNAL_CODE": "XYZ",
    # ...
}

# Route definitions
XYZ_ROUTES = {
    "route_id": ("line_code", "Route Name", "#HexColor"),
    # ...
}

# Route stop sequences
XYZ_ROUTE_STOPS = {
    "route_id": ["STATION1", "STATION2", "STATION3"],
    # ...
}
```

### Step 4: Implement Collectors (for real-time systems)

Create collector directory:

```
collectors/xyz/
├── __init__.py
├── client.py      # API communication
├── discovery.py   # Train discovery (Pattern A only)
├── journey.py     # Journey collection (Pattern A only)
└── collector.py   # Unified collector (Pattern B only)
```

**Client template:**

```python
# collectors/xyz/client.py
from trackrat.collectors.base import BaseClient

class XYZClient(BaseClient):
    def __init__(self, timeout: float = 30.0):
        self.base_url = "https://api.example.com"
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._cache: dict = {}
        self._cache_ttl = 30  # seconds

    async def get_train_data(self, *args, **kwargs):
        # Implement API calls
        pass

    async def close(self):
        if self._session:
            await self._session.aclose()
```

**Collector template (Pattern B):**

```python
# collectors/xyz/collector.py
class XYZCollector:
    def __init__(self, client: XYZClient | None = None):
        self.client = client or XYZClient()

    async def run(self) -> dict[str, Any]:
        async with get_session() as session:
            return await self.collect(session)

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        # Fetch data from API
        data = await self.client.get_train_data()

        # Phase 1: Discovery
        discovery_stats = await self._discover_trains(session, data)

        # Phase 2: Updates
        update_stats = await self._update_journeys(session, data)

        return {**discovery_stats, **update_stats}

    async def collect_journey_details(self, session: AsyncSession, journey: TrainJourney):
        # JIT refresh implementation
        pass
```

### Step 5: Register with JIT Service

Add to `services/jit.py`:

```python
async def get_collector_for_journey(self, journey: TrainJourney):
    if journey.data_source == "NJT":
        return self.njt_collector
    elif journey.data_source == "AMTRAK":
        return self.amtrak_collector
    elif journey.data_source == "PATH":
        return self.path_collector
    elif journey.data_source == "XYZ":
        return self.xyz_collector  # Add new system
    else:
        raise ValueError(f"Unknown data source: {journey.data_source}")
```

### Step 6: Register with Scheduler

Add to `services/scheduler.py`:

```python
# Pattern A: Separate discovery and journey tasks
scheduler.add_job(
    run_xyz_discovery,
    "interval",
    minutes=30,
    id="xyz_discovery",
)

scheduler.add_job(
    run_xyz_journey_collection,
    "interval",
    minutes=15,
    id="xyz_journey_collection",
)

# Pattern B: Single unified task
scheduler.add_job(
    run_xyz_collection,
    "interval",
    minutes=4,
    id="xyz_collection",
)
```

### Step 7: Update Departure Service

Add data source handling in `services/departure.py`:

```python
# Ensure the new data source is included in queries
data_sources = ["NJT", "AMTRAK", "PATH", "PATCO", "XYZ"]
```

### Step 8: Add GTFS Stop Mapping (if using GTFS)

Update `map_gtfs_stop_to_station_code()` in `config/stations.py`:

```python
def map_gtfs_stop_to_station_code(gtfs_stop_id: str, gtfs_stop_name: str, data_source: str):
    if data_source == "XYZ":
        return XYZ_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
    # ... existing mappings
```

---

## iOS Integration Checklist

After adding a backend integration, update the iOS app:

### 1. Add to TrainSystem enum

```swift
// ios/TrackRat/Models/TrainSystem.swift
enum TrainSystem: String, CaseIterable, Codable {
    case njt = "NJT"
    case amtrak = "AMTRAK"
    case path = "PATH"
    case patco = "PATCO"
    case xyz = "XYZ"  // Add new system

    var displayName: String {
        switch self {
        case .xyz: return "XYZ Transit"
        // ...
        }
    }

    var iconName: String {
        switch self {
        case .xyz: return "tram.fill"
        // ...
        }
    }

    var brandColor: Color {
        switch self {
        case .xyz: return Color(hex: "HexColor")
        // ...
        }
    }
}
```

### 2. Add station mappings

```swift
// ios/TrackRat/Shared/Stations.swift
static let stationSystemStrings: [String: [String]] = [
    "XYZ": ["XYZ"],  // XYZ station belongs to XYZ system
    // ...
]
```

### 3. Add route topology (for map)

```swift
// ios/TrackRat/Shared/RouteTopology.swift
static let routes: [Route] = [
    Route(
        id: "xyz_main",
        name: "XYZ Main Line",
        color: "#HexColor",
        dataSource: "XYZ",
        coordinates: [
            Coordinate(lat: 40.1234, lon: -74.5678),
            // ...
        ]
    ),
    // ...
]
```

### 4. Update AdvancedConfigurationView

Add toggle for enabling the new system in settings.

---

## Testing Checklist

For any new integration:

- [ ] Client connects and parses API responses correctly
- [ ] Discovery finds expected trains at hub stations
- [ ] Journey collection creates valid `TrainJourney` records
- [ ] All stops have correct station codes and times
- [ ] JIT refresh updates existing journeys without duplicates
- [ ] GTFS mapping works for schedule fallback (if applicable)
- [ ] iOS displays system with correct branding
- [ ] Station filter correctly includes/excludes new system

---

## Common Pitfalls

1. **Train ID instability**: Some APIs change train IDs mid-journey. Generate stable IDs from route + time.

2. **Timezone handling**: Store all times as Eastern Time. Convert on ingestion.

3. **Stop ordering**: Some APIs return stops out of sequence. Sort by stop_sequence or scheduled time.

4. **Duplicate journeys**: Use upsert logic with appropriate deduplication keys.

5. **API outages**: Design for graceful degradation to GTFS schedules.

6. **Multi-system stations**: Newark Penn (NP) serves NJT, Amtrak, and PATH - physical locations differ.

7. **Headsign variations**: "World Trade Center", "WTC", "World Trade" should all map to the same destination.

8. **Cache invalidation**: Be careful with client-side caching - stale data causes incorrect departure times.
