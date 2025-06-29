# Train Arrival Time Tracking Design

## Overview

This document outlines the minimal design changes needed to track actual arrival times for NJ Transit trains using the `getTrainStopList` API. The design supports two primary use cases:

1. **Just-in-Time Updates**: Fetch fresh stop data when users request train details
2. **Post-Journey Validation**: Systematic collection of complete journey data for historical analysis

## Current State Analysis

### What We Already Track

**Train Table:**
- ✅ Scheduled departure from origin (`departure_time`)
- ✅ Track assignment/release times at origin
- ❌ No actual departure time (only track release time)
- ❌ No journey completion tracking

**TrainStop Table:**
- ✅ Scheduled time for each stop (`scheduled_time`)
- ✅ Actual departure time (`departure_time`) - partially populated
- ✅ Departed flag (`departed`)
- ❌ No actual arrival time tracking
- ❌ Actual times only populated for monitored stations

## Proposed Schema Changes

### 1. TrainStop Table Enhancement

Add one field to track actual arrival times:

```python
# In TrainStop model
actual_arrival_time = Column(DateTime, nullable=True)  # When train actually arrived at platform
```

This enables tracking scheduled vs actual for both arrival and departure at each stop.

### 2. Train Table Enhancements

Add minimal fields to track journey completion and stop data freshness:

```python
# In Train model
journey_completion_status = Column(String(20), nullable=True, index=True)  
# Values: 'in_progress', 'completed', 'terminated_early', 'lost_tracking'

journey_validated_at = Column(DateTime, nullable=True)
# When we last checked this train's full journey via getTrainStopList

next_validation_check = Column(DateTime, nullable=True, index=True)  
# When to check again if journey not complete

stops_last_updated = Column(DateTime, nullable=True, index=True)
# When we last fetched stop data from getTrainStopList API
```

## Implementation Design

### NJ Transit Collector Enhancement

Add the getTrainStopList method to the existing NJTransitCollector:

```python
class NJTransitCollector(BaseCollector):
    TRAIN_STOP_LIST_ENDPOINT = "getTrainStopList"
    
    def get_train_stops(self, train_id: str) -> Dict[str, Any]:
        """
        Get detailed stop information for a specific train.
        
        Args:
            train_id: NJ Transit train ID
            
        Returns:
            Dict containing train details and stop list
            
        Raises:
            APIError: If the API request fails
        """
        # Ensure we have a valid token
        if not self.token:
            self.token = self._get_token()
            
        url = f"{self.base_url}/{self.TRAIN_STOP_LIST_ENDPOINT}"
        files = {
            "token": (None, self.token),
            "train": (None, train_id)
        }
        
        try:
            response = requests.post(url, files=files, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Log the API call for monitoring
            logger.info(f"Fetched stop list for train {train_id}")
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch stops for train {train_id}: {str(e)}")
            raise APIError(f"Failed to fetch train stops: {str(e)}")
```

### Core Update Function

```python
def update_train_stops(nj_transit_id: str) -> bool:
    """
    Update train stops using NJ Transit getTrainStopList API.
    Returns True if journey is complete, False otherwise.
    """
    try:
        stops_data = nj_api.get_train_stops(nj_transit_id)
        journey_complete = True
        
        for stop_data in stops_data['STOPS']:
            # Find matching TrainStop record
            train_stop = db.query(TrainStop).filter(
                TrainStop.train_id == nj_transit_id,
                TrainStop.station_name == stop_data['STATIONNAME']
            ).first()
            
            if train_stop:
                # Update actual times - NEVER modify scheduled_time!
                if stop_data.get('TIME'):  # Actual arrival
                    train_stop.actual_arrival_time = parse_time(stop_data['TIME'])
                
                if stop_data.get('DEP_TIME'):  # Actual departure  
                    train_stop.departure_time = parse_time(stop_data['DEP_TIME'])
                
                train_stop.departed = (stop_data.get('DEPARTED') == 'YES')
                train_stop.stop_status = stop_data.get('STOP_STATUS', '')
                
                # Check if this stop is still pending
                if not train_stop.departed:
                    journey_complete = False
        
        db.commit()
        return journey_complete
        
    except Exception as e:
        logger.error(f"Failed to update stops for train {nj_transit_id}: {e}")
        return False
```

### Scenario 1: Just-in-Time Updates

Update the train detail API endpoint to fetch fresh stop data on demand:

```python
@router.get("/{train_id}", response_model=TrainResponse)
async def get_train(
    train_id: str,
    from_station_code: Optional[str] = None,
    train_repo: TrainRepository = Depends(get_train_repository),
    stop_repo: TrainStopRepository = Depends(get_train_stop_repository),
    nj_collector: NJTransitCollector = Depends(get_nj_transit_collector),
):
    """Get a specific train by its ID with fresh stop data if needed."""
    # Get the train from database
    train = train_repo.get_train_by_id(train_id)
    if not train:
        raise HTTPException(status_code=404, detail=f"Train with ID {train_id} not found")
    
    # Check if we need fresh stop data for NJ Transit trains
    if train.data_source == 'njtransit' and train.status in ['BOARDING', 'DEPARTED']:
        should_refresh = False
        
        # Determine if we need fresh data
        if not train.stops_last_updated:
            # Never fetched stop data
            should_refresh = True
        elif train.journey_completion_status == 'completed':
            # Journey already complete, no need to refresh
            should_refresh = False
        else:
            # Check if data is stale (>5 minutes old)
            minutes_since_update = (datetime.utcnow() - train.stops_last_updated).total_seconds() / 60
            if minutes_since_update > 5:
                should_refresh = True
        
        # Fetch fresh data if needed
        if should_refresh:
            try:
                is_complete = update_train_stops_just_in_time(
                    train, 
                    nj_collector,
                    train_repo,
                    stop_repo
                )
                
                # Update completion status
                if is_complete:
                    train.journey_completion_status = 'completed'
                    train.journey_validated_at = datetime.utcnow()
                
                # Reload train data after update
                train = train_repo.get_train_by_id(train_id)
                
            except Exception as e:
                # Log error but continue with stale data
                logger.warning(f"Failed to refresh stops for train {train_id}: {e}")
    
    # Enrich train with stop data and return
    enriched_train = _enrich_train_with_stops(train, stop_repo)
    return enriched_train

def update_train_stops_just_in_time(
    train: Train,
    nj_collector: NJTransitCollector,
    train_repo: TrainRepository,
    stop_repo: TrainStopRepository
) -> bool:
    """
    Update train stops on demand using NJ Transit getTrainStopList API.
    Returns True if journey is complete, False otherwise.
    """
    # Use existing update_train_stops logic but update the timestamp
    is_complete = update_train_stops(train.train_id, nj_collector, stop_repo)
    
    # Update the stops_last_updated timestamp
    train.stops_last_updated = datetime.utcnow()
    train_repo.update(train)
    
    return is_complete
```

### Scenario 2: Post-Journey Validation

```python
def validate_completed_journeys():
    """
    Called every 10-15 minutes by scheduler.
    Validates trains that should have completed their journey.
    """
    # Find NJ Transit trains that need validation
    now = datetime.utcnow()
    
    candidates = db.query(Train).filter(
        Train.data_source == 'njtransit',
        Train.status == 'DEPARTED',
        Train.journey_completion_status == None,  # Not yet validated
        Train.departure_time < now - timedelta(hours=1),  # Give time to complete
        or_(
            Train.next_validation_check == None,
            Train.next_validation_check < now
        )
    ).limit(10).all()  # Rate limit
    
    for train in candidates:
        is_complete = update_train_stops(train.train_id)
        
        if is_complete:
            train.journey_completion_status = 'completed'
            train.journey_validated_at = now
        else:
            # Check again later based on estimated completion
            estimated_completion = estimate_journey_completion(train)
            train.next_validation_check = estimated_completion + timedelta(minutes=15)
            train.journey_completion_status = 'in_progress'

def estimate_journey_completion(train: Train) -> datetime:
    """
    Estimate when a train will complete its journey based on current progress.
    """
    # Find the last scheduled stop
    last_stop = db.query(TrainStop).filter(
        TrainStop.train_id == train.train_id
    ).order_by(TrainStop.scheduled_time.desc()).first()
    
    if last_stop and last_stop.scheduled_time:
        # Add buffer for typical delays
        return last_stop.scheduled_time + timedelta(minutes=30)
    else:
        # Fallback: 4 hours from departure
        return train.departure_time + timedelta(hours=4)
```

## Key Design Principles

1. **Minimal Changes**: Only add essential fields for arrival tracking
2. **Data Preservation**: Never overwrite original scheduled times
3. **Rate Limiting**: Natural limits through selective tracking and batch sizes
4. **Graceful Degradation**: System continues to function even if API calls fail
5. **Progressive Enhancement**: Can start simple and add sophistication over time

## Benefits

This design enables:
- **Complete Journey Data**: Full scheduled vs actual times for every stop
- **Delay Propagation Analysis**: How delays evolve through a journey
- **Dwell Time Calculation**: Time between arrival and departure at each stop
- **Recovery Pattern Detection**: Where trains make up lost time
- **Real-time User Features**: Live tracking for trains users care about

## Migration SQL

```sql
-- Add actual arrival time to train stops
ALTER TABLE train_stops 
ADD COLUMN actual_arrival_time TIMESTAMP;

-- Add journey tracking to trains
ALTER TABLE trains
ADD COLUMN journey_completion_status VARCHAR(20),
ADD COLUMN journey_validated_at TIMESTAMP,
ADD COLUMN next_validation_check TIMESTAMP,
ADD COLUMN stops_last_updated TIMESTAMP;

-- Add indexes for efficient queries
CREATE INDEX idx_trains_journey_validation 
ON trains(data_source, journey_completion_status, next_validation_check)
WHERE data_source = 'njtransit';

CREATE INDEX idx_trains_stop_freshness
ON trains(data_source, status, stops_last_updated)
WHERE data_source = 'njtransit' AND status IN ('BOARDING', 'DEPARTED');
```

## NJ TRANSIT API

```
8. getTrainStopList
List train stops in JSON format by train ID.
curl -X 'POST' \
'https://testraildata.njtransit.com/api/TrainData/getTrainStopList' \
-H 'accept: text/plain' \
-H 'Content-Type: multipart/form-data' \
-F 'token=your token here' \
-F 'train=3846'
Result #1:
{
"TRAIN_ID": "3240",
"LINECODE": "NC",
"BACKCOLOR": "#009CDB",
"FORECOLOR": "white",
"SHADOWCOLOR": "black",
"DESTINATION": "Penn Station New York",
"TRANSFERAT": ""
,
"STOPS": [
{
"STATION_2CHAR": "LB",
"STATIONNAME": "Long Branch",
"TIME": "30-May-2024 10:52:30 AM",
"PICKUP": ""
,
"DROPOFF": ""
,
"DEPARTED": "YES",
"STOP_STATUS": "OnTime",
"DEP_TIME": "30-May-2024 10:53:30 AM",
"TIME_UTC_FORMAT": "30-May-2024 02:52:30 PM",
"STOP_LINES": []
},
{
"STATION_2CHAR": "LS",
"STATIONNAME": "Little Silver",
"TIME": "30-May-2024 11:00:07 AM",
"PICKUP": ""
,
"DROPOFF": ""
,
"DEPARTED": "YES",
"STOP_STATUS": "OnTime",
"DEP_TIME": "30-May-2024 11:01:00 AM",
"TIME_UTC_FORMAT": "30-May-2024 03:00:07 PM",
"STOP_LINES": []
},
...
```

## Additional Considerations

### Rate Limiting & Performance

1. **Request Deduplication**: If multiple users request the same train within the 5-minute window, they all get the cached data without additional API calls.

2. **Concurrent Request Handling**: Consider adding a lock or queue to prevent multiple simultaneous API calls for the same train:
   ```python
   # Simple in-memory lock approach
   train_update_locks = {}
   
   async def get_train_with_lock(train_id):
       lock_key = f"train_update_{train_id}"
       if lock_key in train_update_locks:
           # Another request is already updating this train
           await asyncio.sleep(1)  # Wait briefly
           return get_train_from_db(train_id)
       
       train_update_locks[lock_key] = True
       try:
           # Perform update
           update_train_stops(train_id)
       finally:
           del train_update_locks[lock_key]
   ```

3. **Graceful Degradation**: If the NJ Transit API is down or rate limited, serve stale data with a warning rather than failing the request.

### Edge Cases

1. **Trains That Never Complete**: Some trains might terminate early or be cancelled mid-journey. The post-journey validation should handle these by:
   - Setting `journey_completion_status = 'terminated_early'` if no progress after multiple checks
   - Stopping validation attempts after a reasonable timeout (e.g., 12 hours after scheduled completion)

2. **Train ID Reuse**: NJ Transit may reuse train IDs on different days. Always use the combination of `train_id` + `departure_time` for unique identification.

3. **API Response Validation**: The getTrainStopList API might return:
   - Empty stop lists (train not found)
   - Partial data (some stops missing)
   - Outdated data (cached on their end)

### Monitoring & Alerting

Track these metrics:
- API call frequency per train
- Cache hit/miss ratio
- API response times
- Failed update attempts
- Data staleness distribution

