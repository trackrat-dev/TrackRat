# PATH Real-Time Tracking Implementation Design

## Executive Summary

This document proposes implementing real-time tracking for PATH trains using the **native PATH RidePATH API** (`ridepath.json`). This API provides real-time arrival predictions at ALL 13 stations, enabling full intermediate stop tracking similar to NJT and Amtrak.

**Key discovery**: The Transiter API (used for discovery) only exposes terminus data, but the native PATH API provides arrivals at every station along each route.

---

## API Analysis

### Native PATH API: `ridepath.json`

**URL**: `https://www.panynj.gov/bin/portauthority/ridepath.json`

**What it provides**:
```json
{
  "results": [
    {
      "consideredStation": "JSQ",
      "destinations": [
        {
          "label": "ToNY",
          "messages": [
            {
              "headSign": "World Trade Center",
              "arrivalTimeMessage": "4 min",
              "lastUpdated": "2026-01-19T07:36:57.674251-05:00",
              "lineColor": "D93A30"
            }
          ]
        }
      ]
    }
  ]
}
```

**Coverage**:
- All 13 PATH stations
- Both directions (ToNY, ToNJ)
- Real-time arrival predictions ("X min")
- Line color for route identification
- Last updated timestamp

### Tracking Trains Across Stations

The same train appears at multiple stations with progressive arrival times:

```
World Trade Center bound train:
  JSQ (Journal Sq)    in  4 min
  GRV (Grove St)      in  9 min  (+5 min from JSQ)
  EXP (Exchange Pl)   in 11 min  (+2 min from GRV)
  ...
```

By correlating headsign + arrival time progression, we can identify the same train at each station.

### Comparison: Transiter vs Native API

| Feature | Transiter | Native PATH API |
|---------|-----------|-----------------|
| Stations with data | Terminus only | All 13 stations |
| Intermediate stops | No | Yes |
| Trip ID | Yes (ephemeral) | No |
| Headsign | Yes | Yes |
| Real-time updates | Yes | Yes |
| Arrival format | Unix timestamp | "X min" string |

**Recommendation**: Use native PATH API for journey updates, keep Transiter for discovery (creates journeys with GTFS stop sequences).

---

## Architecture

### Data Flow

```
                    ┌─────────────────────────────────┐
                    │  PATH Discovery (Transiter)     │
                    │  - Creates TrainJourney records │
                    │  - Populates stops from GTFS    │
                    │  - Runs every 30 min            │
                    └─────────────┬───────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │  PATH Journey Collection        │
                    │  (Native ridepath.json API)     │
                    │  - Updates stop arrival times   │
                    │  - Tracks train progression     │
                    │  - Runs every 1-2 min           │
                    └─────────────────────────────────┘
```

### New Components

1. **`collectors/path/ridepath_client.py`** - Client for native PATH API
2. **`collectors/path/journey.py`** - Journey collector using native API
3. **Updates to `services/jit.py`** - PATH collector support
4. **Updates to `services/scheduler.py`** - PATH collection job

---

## Detailed Design

### 1. RidePATH API Client

```python
# collectors/path/ridepath_client.py

from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx

class PathArrival(BaseModel):
    """Single arrival from RidePATH API."""
    station_code: str          # Internal code (JSQ, GRV, etc.)
    headsign: str              # "World Trade Center", "33rd Street", etc.
    direction: str             # "ToNY" or "ToNJ"
    minutes_away: int          # Parsed from "X min"
    arrival_time: datetime     # Computed: now + minutes_away
    line_color: str            # Hex color(s)
    last_updated: datetime     # When PATH last updated this prediction

class RidePathClient:
    """Client for native PATH RidePATH API."""

    BASE_URL = "https://www.panynj.gov/bin/portauthority/ridepath.json"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def get_all_arrivals(self) -> list[PathArrival]:
        """Fetch arrivals from all PATH stations.

        Returns:
            List of PathArrival objects for all stations/directions
        """
        async with self._get_client() as client:
            response = await client.get(self.BASE_URL)
            response.raise_for_status()
            data = response.json()

        arrivals = []
        now = datetime.now()

        for result in data.get("results", []):
            station_code = self._map_station_code(result.get("consideredStation"))
            if not station_code:
                continue

            for dest_group in result.get("destinations", []):
                direction = dest_group.get("label", "")

                for msg in dest_group.get("messages", []):
                    minutes = self._parse_minutes(msg.get("arrivalTimeMessage", ""))
                    if minutes is None:
                        continue

                    arrivals.append(PathArrival(
                        station_code=station_code,
                        headsign=msg.get("headSign", "Unknown"),
                        direction=direction,
                        minutes_away=minutes,
                        arrival_time=now + timedelta(minutes=minutes),
                        line_color=msg.get("lineColor", ""),
                        last_updated=self._parse_timestamp(msg.get("lastUpdated")),
                    ))

        return arrivals

    def _parse_minutes(self, msg: str) -> int | None:
        """Parse '14 min' -> 14."""
        if "min" in msg:
            try:
                return int(msg.replace("min", "").strip())
            except ValueError:
                pass
        return None

    def _map_station_code(self, api_code: str) -> str | None:
        """Map API station code (NWK) to internal code (PNK)."""
        # Mapping: API uses short codes, we use P-prefixed codes
        mapping = {
            "NWK": "PNK", "HAR": "PHR", "JSQ": "PJS", "GRV": "PGR",
            "NEW": "PNP", "EXP": "PEX", "WTC": "PWC", "HOB": "PHO",
            "CHR": "PCH", "09S": "P9S", "14S": "P14", "23S": "P23",
            "33S": "P33",
        }
        return mapping.get(api_code)
```

### 2. PATH Journey Collector

```python
# collectors/path/journey.py

class PathJourneyCollector(BaseJourneyCollector):
    """Updates PATH journeys with real-time data from RidePATH API."""

    def __init__(self, client: RidePathClient | None = None):
        self.client = client or RidePathClient()
        self._owns_client = client is None

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Update a single journey with real-time arrival data.

        Strategy:
        1. Fetch all arrivals from RidePATH API
        2. Find arrivals matching this journey's route/destination
        3. Match arrivals to journey stops by station
        4. Update actual_arrival times
        """
        if journey.is_completed or journey.is_cancelled:
            return

        try:
            # Get all current arrivals
            all_arrivals = await self.client.get_all_arrivals()

            # Filter to this journey's destination
            journey_headsign = self._normalize_headsign(journey.destination)
            matching = [a for a in all_arrivals
                       if self._normalize_headsign(a.headsign) == journey_headsign]

            # Get journey stops
            stops = await self._get_journey_stops(session, journey)

            # Match arrivals to stops and update
            await self._update_stops_from_arrivals(session, journey, stops, matching)

            journey.last_updated_at = now_et()
            journey.update_count = (journey.update_count or 0) + 1
            journey.api_error_count = 0

        except Exception as e:
            logger.error("path_journey_update_failed",
                        train_id=journey.train_id, error=str(e))
            journey.api_error_count = (journey.api_error_count or 0) + 1
            journey.last_updated_at = now_et()

            if journey.api_error_count >= 2:
                journey.is_expired = True

        await session.flush()

    async def _update_stops_from_arrivals(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops: list[JourneyStop],
        arrivals: list[PathArrival],
    ) -> None:
        """Match arrivals to stops and update actual times.

        Matching strategy:
        1. For each stop, find arrival at that station
        2. If multiple trains to same destination, use closest arrival
           that hasn't passed yet
        3. Update actual_arrival with predicted time
        4. Mark departed if arrival time has passed
        """
        now = now_et()
        arrivals_by_station = {}

        for arrival in arrivals:
            key = arrival.station_code
            # Keep the soonest arrival for each station
            if key not in arrivals_by_station or arrival.minutes_away < arrivals_by_station[key].minutes_away:
                arrivals_by_station[key] = arrival

        # Track furthest departed stop for sequential inference
        max_departed_sequence = 0

        for stop in stops:
            arrival = arrivals_by_station.get(stop.station_code)

            if arrival:
                # Update arrival time prediction
                stop.actual_arrival = arrival.arrival_time
                stop.updated_arrival = arrival.arrival_time

                # Check if train has passed this stop
                if arrival.arrival_time <= now:
                    stop.has_departed_station = True
                    stop.actual_departure = arrival.arrival_time
                    stop.departure_source = "time_inference"
                    max_departed_sequence = max(max_departed_sequence, stop.stop_sequence or 0)

            elif stop.stop_sequence and stop.stop_sequence < max_departed_sequence:
                # Sequential inference: if later stops are departed, this one must be too
                if not stop.has_departed_station:
                    stop.has_departed_station = True
                    stop.actual_departure = stop.scheduled_departure or stop.scheduled_arrival
                    stop.departure_source = "sequential_inference"

        # Check journey completion
        terminal_stop = stops[-1] if stops else None
        if terminal_stop and terminal_stop.has_departed_station:
            journey.is_completed = True
            journey.actual_arrival = terminal_stop.actual_arrival

        # Run transit analysis
        await self._analyze_segments(session, journey, stops)

    async def collect_active_journeys(self, session: AsyncSession) -> dict[str, Any]:
        """Batch update all active PATH journeys.

        More efficient than individual updates since we fetch
        all arrivals once and match to multiple journeys.
        """
        today = now_et().date()

        # Get all active PATH journeys
        journeys = await session.scalars(
            select(TrainJourney)
            .where(
                TrainJourney.data_source == "PATH",
                TrainJourney.journey_date == today,
                TrainJourney.is_completed == False,
                TrainJourney.is_expired == False,
                TrainJourney.is_cancelled == False,
            )
        )
        journeys = list(journeys.all())

        if not journeys:
            return {"data_source": "PATH", "journeys_processed": 0}

        # Fetch all arrivals once
        try:
            all_arrivals = await self.client.get_all_arrivals()
        except Exception as e:
            logger.error("path_batch_fetch_failed", error=str(e))
            return {"data_source": "PATH", "error": str(e)}

        # Group arrivals by normalized headsign
        arrivals_by_headsign = {}
        for arrival in all_arrivals:
            key = self._normalize_headsign(arrival.headsign)
            if key not in arrivals_by_headsign:
                arrivals_by_headsign[key] = []
            arrivals_by_headsign[key].append(arrival)

        # Update each journey
        updated = 0
        completed = 0
        errors = 0

        for journey in journeys:
            try:
                journey_headsign = self._normalize_headsign(journey.destination)
                matching = arrivals_by_headsign.get(journey_headsign, [])

                stops = await self._get_journey_stops(session, journey)
                await self._update_stops_from_arrivals(session, journey, stops, matching)

                journey.last_updated_at = now_et()
                journey.update_count = (journey.update_count or 0) + 1

                if journey.is_completed:
                    completed += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error("path_journey_batch_update_failed",
                           train_id=journey.train_id, error=str(e))
                errors += 1

        await session.commit()

        return {
            "data_source": "PATH",
            "journeys_processed": len(journeys),
            "updated": updated,
            "completed": completed,
            "errors": errors,
            "arrivals_fetched": len(all_arrivals),
        }

    def _normalize_headsign(self, headsign: str) -> str:
        """Normalize headsign for matching.

        Handles variations like:
        - "World Trade Center" vs "WTC"
        - "33rd Street" vs "33rd Street via Hoboken"
        """
        if not headsign:
            return ""

        h = headsign.lower().strip()

        # Normalize common variations
        if "world trade" in h or h == "wtc":
            return "world_trade_center"
        if "33rd" in h or "33 st" in h:
            return "33rd_street"
        if "hoboken" in h:
            return "hoboken"
        if "newark" in h:
            return "newark"
        if "journal" in h:
            return "journal_square"

        return h.replace(" ", "_")
```

### 3. Train Matching Challenge

The native PATH API doesn't have trip IDs. To identify which API arrival corresponds to which database journey, we use:

1. **Headsign matching**: Journey destination → API headsign
2. **Timing correlation**: Scheduled departure time + expected travel time ≈ API arrival time
3. **Stop sequence**: Train at earlier stops should show arrivals sooner

For most cases, **headsign matching + soonest arrival** is sufficient because:
- PATH runs frequent service (every 5-10 minutes)
- We care about the NEXT train to each destination
- Multiple journeys to same destination are handled by taking the soonest

### 4. JIT Service Integration

```python
# services/jit.py - additions

class JustInTimeUpdateService:
    def __init__(self, njt_client: NJTransitClient | None = None):
        self._njt_collector: JourneyCollector | None = None
        self._amtrak_collector: AmtrakJourneyCollector | None = None
        self._path_collector: PathJourneyCollector | None = None  # NEW

    @property
    def path_collector(self) -> PathJourneyCollector:
        if self._path_collector is None:
            from trackrat.collectors.path.journey import PathJourneyCollector
            self._path_collector = PathJourneyCollector()
        return self._path_collector

    async def get_collector_for_journey(
        self, journey: TrainJourney
    ) -> JourneyCollector | AmtrakJourneyCollector | PathJourneyCollector:
        if journey.data_source == "NJT":
            return self.njt_collector
        elif journey.data_source == "AMTRAK":
            return self.amtrak_collector
        elif journey.data_source == "PATH":
            return self.path_collector
        else:
            raise ValueError(f"Unknown data source: {journey.data_source}")
```

### 5. Scheduler Integration

```python
# services/scheduler.py - additions

def _setup_jobs(self) -> None:
    # ... existing jobs ...

    # PATH journey collection - every 2 minutes
    # More frequent than NJT (15 min) because PATH runs more frequently
    self.scheduler.add_job(
        self.run_path_journey_collection,
        trigger=IntervalTrigger(minutes=2),
        id="path_journey_collection",
        name="PATH Journey Collection",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

async def run_path_journey_collection(self) -> None:
    """Update active PATH journeys with real-time data."""
    logger.info("scheduler.path_journey_collection.started")

    async with get_session() as db:
        safe_interval = calculate_safe_interval(2)

        async def do_collection():
            collector = PathJourneyCollector()
            try:
                return await collector.collect_active_journeys(db)
            finally:
                await collector.client.close()

        result = await run_with_freshness_check(
            db=db,
            task_name="path_journey_collection",
            minimum_interval_seconds=safe_interval,
            task_func=do_collection,
        )

    if result:
        logger.info("scheduler.path_journey_collection.completed", **result)
```

---

## Station Code Mapping

The native PATH API uses different station codes than our internal system:

| API Code | Internal Code | Station Name |
|----------|---------------|--------------|
| NWK | PNK | Newark |
| HAR | PHR | Harrison |
| JSQ | PJS | Journal Square |
| GRV | PGR | Grove Street |
| NEW | PNP | Newport |
| EXP | PEX | Exchange Place |
| WTC | PWC | World Trade Center |
| HOB | PHO | Hoboken |
| CHR | PCH | Christopher Street |
| 09S | P9S | 9th Street |
| 14S | P14 | 14th Street |
| 23S | P23 | 23rd Street |
| 33S | P33 | 33rd Street |

This mapping goes in `config/stations.py`:

```python
PATH_API_TO_INTERNAL_MAP = {
    "NWK": "PNK", "HAR": "PHR", "JSQ": "PJS", "GRV": "PGR",
    "NEW": "PNP", "EXP": "PEX", "WTC": "PWC", "HOB": "PHO",
    "CHR": "PCH", "09S": "P9S", "14S": "P14", "23S": "P23",
    "33S": "P33",
}
```

---

## What This Enables

### Real-Time Tracking

| Feature | Before | After |
|---------|--------|-------|
| Arrival time at each stop | Scheduled only | Real-time predictions |
| Delay detection | Not possible | Yes (compare to schedule) |
| Train position | Not tracked | Inferred from arrivals |
| Completion detection | Time-based guess | Based on actual arrivals |

### Congestion Map

With actual arrival times at intermediate stops:
- Segment-level congestion (JSQ→GRV, GRV→EXP, etc.)
- Route-level aggregation
- Delay hotspot identification

### Recent Departures Stats

- On-time percentage per station/route
- Average delay by time of day
- Historical trend analysis

---

## Implementation Order

1. **Phase 1: RidePATH Client** (~100 lines)
   - Create `collectors/path/ridepath_client.py`
   - Implement `get_all_arrivals()`
   - Add station code mapping

2. **Phase 2: Journey Collector** (~250 lines)
   - Create `collectors/path/journey.py`
   - Implement `collect_journey_details()`
   - Implement `collect_active_journeys()`
   - Add headsign normalization

3. **Phase 3: Integration** (~50 lines)
   - Update `services/jit.py` with PATH support
   - Update `services/scheduler.py` with collection job
   - Add station mapping to `config/stations.py`

4. **Phase 4: Testing** (~150 lines)
   - Unit tests for RidePATH client
   - Unit tests for journey collector
   - Integration test with real API

---

## File Summary

| File | Action | Lines (Est.) |
|------|--------|-------------|
| `collectors/path/ridepath_client.py` | Create | ~100 |
| `collectors/path/journey.py` | Create | ~250 |
| `services/jit.py` | Modify | +15 |
| `services/scheduler.py` | Modify | +25 |
| `config/stations.py` | Modify | +15 |
| `tests/unit/collectors/test_path_journey.py` | Create | ~150 |

**Total estimated changes**: ~555 lines

---

## Remaining Questions

1. **Polling frequency**: 2 minutes seems reasonable. Should we go faster (1 min) for better granularity?

2. **Train matching**: If multiple trains have the same headsign, we take the soonest. Should we try to correlate by scheduled departure time?

3. **Transit analysis**: Run after each update, or batch at the end of collection?

4. **Error handling**: If the RidePATH API is unavailable, should we fall back to Transiter for terminus-only data?
