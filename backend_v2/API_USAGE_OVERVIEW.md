# TrackRat Backend V2 - API Usage Overview

## Overview

This document provides a comprehensive overview of all upstream API usage in TrackRat Backend V2, including scheduled tasks, user-triggered JIT (Just-In-Time) updates, and startup operations.

## Upstream APIs Used

### 1. NJ Transit APIs
- **Base URL**: `https://traindata.njtransit.com/`
- **Authentication**: Username/password credentials
- **Endpoints**:
  - `TrainData/getTrainSchedule19Rec` - Station departure boards
  - `TrainData/getTrainStopList` - Complete journey details

### 2. Amtrak API
- **Base URL**: `https://api-v3.amtraker.com/`
- **Authentication**: None (public API)
- **Endpoints**:
  - `v3/trains` - All active train data

## Scheduled API Usage

### 1. Discovery Tasks (Hourly + Startup)

#### NJ Transit Discovery
- **Trigger**: Every 60 minutes + immediate startup
- **API Used**: `POST /TrainData/getTrainSchedule19Rec`
- **Stations Polled**: NY, NP, PJ, TR, LB, PL, DN (7 stations)
- **Call Chain**:
  ```
  SchedulerService.run_njt_discovery()
  → TrainDiscoveryCollector.discover_station_trains()
  → NJTransitClient.get_train_schedule(station_code)
  → POST /TrainData/getTrainSchedule19Rec
  ```
- **Frequency**: 7 calls per hour + 7 calls at startup

#### Amtrak Discovery
- **Trigger**: Every 60 minutes + immediate startup
- **API Used**: `GET /v3/trains`
- **Call Chain**:
  ```
  SchedulerService.run_amtrak_discovery()
  → AmtrakDiscoveryCollector.discover_trains()
  → AmtrakClient.get_all_trains()
  → GET /v3/trains
  ```
- **Frequency**: 1 call per hour + 1 call at startup
- **Caching**: 60-second in-memory cache prevents duplicate calls

### 2. Journey Collection Tasks (Triggered by Discovery)

#### NJ Transit Batch Collection
- **Trigger**: 5 seconds after discovery completes
- **API Used**: `POST /TrainData/getTrainStopList`
- **Call Chain**:
  ```
  SchedulerService.schedule_njt_batch_collection()
  → SchedulerService.collect_njt_journeys_batch()
  → JourneyCollector.collect_journey(train_id, skip_enhancement=True)
  → JourneyCollector.collect_journey_details(session, journey, skip_enhancement=True)
  → NJTransitClient.get_train_stop_list(train_id)
  → POST /TrainData/getTrainStopList
  ```
- **Frequency**: 1 call per discovered train (~50-200 calls per batch)
- **Optimization**: Enhancement is skipped (no additional `getTrainSchedule19Rec` calls)

#### Amtrak Batch Collection
- **Trigger**: 5 seconds after discovery completes
- **API Used**: `GET /v3/trains` (cached)
- **Call Chain**:
  ```
  SchedulerService.schedule_amtrak_journey_collections()
  → SchedulerService.collect_all_amtrak_journeys_batch()
  → AmtrakClient.get_all_trains() [uses cached data]
  → GET /v3/trains (usually cached, 0 additional calls)
  ```
- **Frequency**: Usually 0 calls (reuses cached discovery data)

### 3. Periodic Update Tasks

#### Journey Update Check (Every 5 minutes)
- **Trigger**: Every 5 minutes
- **Function**: Schedules individual journey collections for stale data
- **API Calls**: Indirect - schedules other tasks that make API calls

#### Individual Journey Updates
- **Trigger**: Scheduled by journey update check
- **API Used**: `POST /TrainData/getTrainStopList`
- **Call Chain**:
  ```
  SchedulerService.collect_journey()
  → JourneyCollector.collect_single_journey()
  → JourneyCollector.collect_journey_details(session, journey, skip_enhancement=False)
  → NJTransitClient.get_train_stop_list(train_id)
  → POST /TrainData/getTrainStopList
  ```
- **Enhancement**: May also call `getTrainSchedule19Rec` if train is departing within 15 minutes

#### Live Activity Updates (Every minute)
- **Trigger**: Every minute
- **API Used**: May trigger JIT updates if data is stale
- **Call Chain**:
  ```
  SchedulerService.update_live_activities()
  → JustInTimeUpdateService.ensure_fresh_data() [if data >60 seconds old]
  → JourneyCollector.collect_journey_details(session, journey, skip_enhancement=False)
  → NJTransitClient.get_train_stop_list(train_id)
  → POST /TrainData/getTrainStopList
  ```
- **Enhancement**: May also call `getTrainSchedule19Rec` if train is departing within 15 minutes

## Just-In-Time (JIT) API Usage

### User-Triggered Train Details
- **Endpoint**: `GET /api/v2/trains/{train_id}`
- **Trigger**: User requests train details AND data is stale (>60 seconds) OR `refresh=true`
- **API Used**: Depends on train type

#### NJ Transit JIT Updates
- **Call Chain**:
  ```
  trains.get_train_details()
  → JustInTimeUpdateService.get_fresh_train()
  → JustInTimeUpdateService.ensure_fresh_data()
  → JourneyCollector.collect_journey_details(session, journey, skip_enhancement=False)
  → NJTransitClient.get_train_stop_list(train_id)
  → POST /TrainData/getTrainStopList
  ```
- **Enhancement**: May also call `getTrainSchedule19Rec` if:
  - Origin station is monitored (NY, NP, PJ, TR, LB, PL, DN)
  - Train hasn't departed from origin
  - Train is departing within 15 minutes

#### Amtrak JIT Updates
- **Call Chain**:
  ```
  trains.get_train_details()
  → JustInTimeUpdateService.get_fresh_train()
  → JustInTimeUpdateService.ensure_fresh_data()
  → AmtrakJourneyCollector.collect_journey_details()
  → AmtrakClient.get_all_trains()
  → GET /v3/trains
  ```
- **Frequency**: 1 call per JIT update (may use cache if <60 seconds old)

### Other API Endpoints
- **Departures**: `GET /api/v2/trains/departures` - No API calls (database only)
- **History**: `GET /api/v2/trains/{train_id}/history` - No API calls (historical data)

## Enhancement Logic Details

### Departure Board Enhancement
- **Purpose**: Get real-time track assignments from station departure boards
- **When Applied**:
  - **Scheduled batch collection**: NEVER (optimization)
  - **JIT updates**: Only when ALL conditions are met:
    - Origin station is monitored (NY, NP, PJ, TR, LB, PL, DN)
    - Train hasn't departed from origin station
    - Train is departing within 15 minutes
- **API Used**: `POST /TrainData/getTrainSchedule19Rec`

### Enhancement Call Chain
```
enhance_with_departure_board_data()
→ _is_monitored_station() [check if origin is monitored]
→ _is_departing_within_minutes() [check if departing within 15 minutes]
→ NJTransitClient.get_train_schedule(origin_station_code)
→ POST /TrainData/getTrainSchedule19Rec
```

## API Call Volume Estimates

### Per Hour (Scheduled Tasks)
- **NJ Transit Discovery**: 7 calls (`getTrainSchedule19Rec`)
- **Amtrak Discovery**: 1 call (`v3/trains`)
- **NJ Transit Journey Collection**: ~100-200 calls (`getTrainStopList`)
- **Amtrak Journey Collection**: ~0 calls (cached)
- **Periodic Updates**: ~10-30 calls (`getTrainStopList`)
- **Live Activity Updates**: ~5-15 calls (`getTrainStopList`)
- **Enhancement Calls**: ~0 calls (skipped in batch, minimal in periodic)

**Total Scheduled**: ~125-255 calls/hour

### Per User Request (JIT Updates)
- **NJ Transit Train Details**: 1-2 calls
  - 1 call to `getTrainStopList` (always)
  - 0-1 calls to `getTrainSchedule19Rec` (only if departing within 15 minutes)
- **Amtrak Train Details**: 1 call
  - 1 call to `v3/trains` (may use cache)

### Daily Estimates
- **Scheduled**: ~3,000-6,120 calls/day
- **JIT (user-triggered)**: ~100-1,000 calls/day (depends on user activity)
- **Total**: ~3,100-7,120 calls/day

## Key Optimizations

1. **Batch Collection Enhancement Skip**: Eliminates ~100-200 redundant API calls per batch
2. **15-Minute Departure Window**: Reduces enhancement calls by ~80-90%
3. **Amtrak Caching**: 60-second cache prevents duplicate calls
4. **Staleness Thresholds**: Only refreshes when data is >60 seconds old
5. **Sequential Processing**: Prevents database conflicts with minimal API impact

## Performance Characteristics

- **95% reduction** from V1 system (previously ~100,000+ calls/day)
- **Smart caching** prevents redundant API calls
- **Conditional enhancement** only when needed for departing trains
- **Batch processing** for efficiency
- **Graceful degradation** when APIs are unavailable

## Monitoring

- **Prometheus metrics** available at `/metrics`
- **Health checks** at `/health` include API connectivity status
- **Structured logging** for all API calls with timing and error details
- **API call tracing** with request/response logging for debugging