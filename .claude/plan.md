# Design: Subway Feed Resilience + Planned Work Support

## Problem Summary

Two related data quality issues on the staging subway collector:

1. **Phantom scheduled trains during planned work** — TrackRat uses the "regular" GTFS static feed (`gtfs_subway.zip`) which never reflects weekend planned work. When the MTA suspends service (e.g., 7 train this Sunday), users see 50 SCHEDULED trains that don't actually exist.

2. **Transient feed failures cascade into data loss** — When one of the 8 GTFS-RT feeds fails transiently, the collector's full-replacement expiration logic expires all OBSERVED trains from that feed's routes, because it can't distinguish "feed failed" from "trains are gone." The next cycle rediscovers them, but there's a 4-minute gap.

## Proposed Changes

### Change 1: Switch to MTA supplemented GTFS static feed

**What:** Replace the regular subway GTFS URL with the supplemented version.

**Files:**
- `backend_v2/src/trackrat/services/gtfs.py:59` — change URL in `GTFS_FEED_URLS["SUBWAY"]`
- `backend_v2/src/trackrat/config/stations/subway.py:21` — change `SUBWAY_GTFS_STATIC_URL`

**From:** `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip`
**To:** `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip`

**Why this works:** The supplemented feed includes temporary service changes for the next 7 days (updated hourly by MTA). During planned work, trips that aren't running are simply absent from the feed, so TrackRat won't generate phantom SCHEDULED trains.

**Risk:** The S3 `gtfs_supplemented.zip` appears to be the subway-specific supplemented feed (separate from the full multi-modal `google_transit_supplemented.zip` on web.mta.info). The existing GTFS parser already filters by station code mapping, so even if it contained extra data, only mapped subway stations would be stored. Minimal risk.

**Download interval:** Currently 24 hours (`GTFS_DOWNLOAD_INTERVAL_HOURS = 24`). The supplemented feed is updated hourly by MTA, so planned work changes could be stale for up to 24 hours. This is still dramatically better than never showing planned work at all. If needed later, we can add a per-source interval override.

### Change 2: Per-feed success tracking to prevent incorrect expiration

**What:** Make `get_all_arrivals()` report which feeds succeeded, so the collector only expires trains whose feed was actually fetched successfully.

**File 1: `backend_v2/src/trackrat/collectors/subway/client.py`**

Change `get_all_arrivals()` return type from `list[SubwayArrival]` to `tuple[list[SubwayArrival], set[str]]` — the second element is the set of feed keys that returned data successfully.

```python
async def get_all_arrivals(self) -> tuple[list[SubwayArrival], set[str]]:
    tasks = [
        self._fetch_feed(key, url) for key, url in SUBWAY_GTFS_RT_FEED_URLS.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_arrivals: list[SubwayArrival] = []
    succeeded_feeds: set[str] = set()
    for i, result in enumerate(results):
        feed_key = list(SUBWAY_GTFS_RT_FEED_URLS.keys())[i]
        if isinstance(result, BaseException):
            logger.warning(f"Failed to fetch subway {feed_key} feed: {result}")
            all_arrivals.extend(self._cache.get(feed_key, []))
        else:
            if result:  # Only count as success if we got actual data
                succeeded_feeds.add(feed_key)
            all_arrivals.extend(result)

    logger.info(
        f"Fetched {len(all_arrivals)} total subway arrivals "
        f"({len(succeeded_feeds)}/{len(SUBWAY_GTFS_RT_FEED_URLS)} feeds OK)"
    )
    return sorted(all_arrivals, key=lambda a: a.arrival_time), succeeded_feeds
```

Also demote individual feed fetch failures from `logger.error` to `logger.warning` in `_fetch_feed()` (lines 251, 254) — a single feed failing is a warning, not an error. The overall collection failure is the error.

**File 2: `backend_v2/src/trackrat/collectors/subway/collector.py`**

In `collect()`, receive the succeeded_feeds set and use it to gate expiration:

```python
# Line ~112: unpack the tuple
arrivals, succeeded_feeds = await self.client.get_all_arrivals()
```

In the expiration loop (~line 166), skip trains whose route's feed didn't succeed:

```python
from trackrat.collectors.subway.client import _ROUTE_TO_FEED

for journey in stale_result.scalars():
    if journey.id in seen_journey_ids:
        continue
    # Don't expire trains whose feed failed this cycle
    route_feed = _ROUTE_TO_FEED.get(journey.line_code or "")
    if route_feed and route_feed not in succeeded_feeds:
        continue
    # ... existing expiration logic unchanged ...
```

This is the minimal change that prevents the cascade. If the NQRW feed fails, N/Q/R/W trains keep their OBSERVED status. Next successful cycle picks them up normally.

**File 3: Update callers of `get_all_arrivals()`**

`get_station_arrivals()` and `get_trip_stops()` in client.py call `get_all_arrivals()` — they need to unpack the tuple and discard the feeds set:

```python
async def get_station_arrivals(self, station_code: str) -> list[SubwayArrival]:
    all_arrivals, _ = await self.get_all_arrivals()
    return [a for a in all_arrivals if a.station_code == station_code]

async def get_trip_stops(self, trip_id: str) -> list[SubwayArrival]:
    all_arrivals, _ = await self.get_all_arrivals()
    trip_stops = [a for a in all_arrivals if a.trip_id == trip_id]
    return sorted(trip_stops, key=lambda a: a.arrival_time)
```

### What this does NOT change

- **No client persistence across cycles.** The collector still creates a new `SubwayClient` per 4-minute cycle. This is simple and the per-feed tracking makes it unnecessary.
- **No TripReplacementPeriod parsing.** This is a larger feature (parsing protobuf headers, suppressing SCHEDULED trains within the replacement window). The supplemented feed handles most of the same use case.
- **No Service Alerts consumption.** That's a separate feature for displaying user-facing disruption info.
- **No `is_assigned` filtering.** Including unassigned trips is the current design choice.

### Tests needed

1. **Test `get_all_arrivals` returns succeeded_feeds set** — mock two feeds (one succeeds, one raises), verify only the successful feed key is in the set.
2. **Test collector skips expiration for failed feeds** — set up a journey with a route whose feed failed, verify it's NOT expired.
3. **Test collector expires normally for succeeded feeds** — journey with a route whose feed succeeded and is missing from feed, verify it IS expired.
4. **Test GTFS feed URL updated** — verify `GTFS_FEED_URLS["SUBWAY"]` contains "supplemented".
