# Transit Time Tracking & Delay Prediction System Design

## Overview

This document outlines the design for implementing transit time tracking and delay prediction capabilities in TrackRat's backend V2. The system leverages recent train performance on the same routes to predict delays and arrival times, avoiding arbitrary propagation factors in favor of real-world data.

## Core Principle: Learn from Recent Similar Trains

Instead of using abstract delay propagation models, we analyze trains that recently traveled the same route. Since all trains share the same physical tracks, recent trains provide highly relevant insights into current conditions.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Data Collection │────▶│ Transit Analysis│────▶│ Prediction API  │
│ (Existing)      │     │ Service         │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ journey_stops   │     │ segment_times   │     │ Recent train    │
│ (actual times)  │     │ dwell_times     │     │ performance     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Phase 1: Transit Time Foundation (Week 1-2)

### 1.1 Database Schema

```sql
-- Alembic migration: add_transit_time_tables

-- Track transit times between consecutive stations
CREATE TABLE segment_transit_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES train_journeys(id),
    from_station_code VARCHAR(2) NOT NULL,
    to_station_code VARCHAR(2) NOT NULL,
    data_source VARCHAR(10) NOT NULL, -- 'NJT' or 'AMTRAK'
    line_code VARCHAR(2),
    
    -- Timing data
    scheduled_minutes INTEGER NOT NULL,
    actual_minutes INTEGER NOT NULL,
    delay_minutes INTEGER NOT NULL, -- actual - scheduled
    
    -- Context for analysis
    departure_time DATETIME NOT NULL, -- When train left from_station
    hour_of_day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Indexes for efficient querying
    INDEX idx_segment_lookup (from_station_code, to_station_code, data_source, departure_time),
    INDEX idx_recent_segments (from_station_code, to_station_code, created_at DESC)
);

-- Track station dwell times (time spent at stations)
CREATE TABLE station_dwell_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES train_journeys(id),
    station_code VARCHAR(2) NOT NULL,
    data_source VARCHAR(10) NOT NULL,
    line_code VARCHAR(2),
    
    -- Timing data
    scheduled_minutes INTEGER, -- Can be NULL for unscheduled stops
    actual_minutes INTEGER NOT NULL,
    excess_dwell_minutes INTEGER NOT NULL, -- actual - scheduled (or actual if no schedule)
    
    -- Station type flags
    is_origin BOOLEAN DEFAULT FALSE NOT NULL,
    is_terminal BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- Context
    arrival_time DATETIME,
    departure_time DATETIME NOT NULL,
    hour_of_day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    INDEX idx_station_dwell (station_code, data_source, departure_time),
    INDEX idx_recent_dwell (station_code, created_at DESC)
);

-- Journey progress snapshots for real-time tracking
CREATE TABLE journey_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES train_journeys(id),
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Current position
    last_departed_station VARCHAR(2),
    next_station VARCHAR(2),
    
    -- Progress metrics
    stops_completed INTEGER NOT NULL,
    stops_total INTEGER NOT NULL,
    journey_percent FLOAT NOT NULL,
    
    -- Delay tracking
    initial_delay_minutes INTEGER DEFAULT 0 NOT NULL, -- Delay at origin
    cumulative_transit_delay INTEGER DEFAULT 0 NOT NULL, -- Sum of segment delays
    cumulative_dwell_delay INTEGER DEFAULT 0 NOT NULL, -- Sum of excess dwell times
    total_delay_minutes INTEGER NOT NULL, -- Current total delay
    
    -- Predictions (when available)
    predicted_arrival DATETIME,
    prediction_confidence FLOAT,
    prediction_based_on TEXT, -- JSON array of train_ids used for prediction
    
    INDEX idx_journey_progress (journey_id, captured_at DESC)
);
```

### 1.2 Transit Analysis Service

```python
# trackrat/services/transit_analyzer.py

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.models.transit import SegmentTransitTime, StationDwellTime

logger = get_logger(__name__)


class TransitAnalyzer:
    """Analyzes transit times and station dwell times from journey data."""
    
    async def analyze_journey(self, db: AsyncSession, journey: TrainJourney) -> None:
        """Analyze and store transit metrics for a completed journey."""
        
        stops = sorted(journey.stops, key=lambda s: s.stop_sequence)
        if len(stops) < 2:
            return
        
        # Analyze segment transit times
        await self._analyze_segments(db, journey, stops)
        
        # Analyze station dwell times
        await self._analyze_dwell_times(db, journey, stops)
        
        # Update journey progress
        await self._update_journey_progress(db, journey, stops)
    
    async def _analyze_segments(
        self, db: AsyncSession, journey: TrainJourney, stops: List[JourneyStop]
    ) -> None:
        """Calculate and store transit times between consecutive stations."""
        
        for i in range(len(stops) - 1):
            current_stop = stops[i]
            next_stop = stops[i + 1]
            
            # Skip if we don't have actual times
            if not (current_stop.actual_departure and next_stop.actual_arrival):
                continue
            
            # Calculate scheduled transit time
            scheduled_minutes = None
            if current_stop.scheduled_departure and next_stop.scheduled_arrival:
                scheduled_delta = next_stop.scheduled_arrival - current_stop.scheduled_departure
                scheduled_minutes = int(scheduled_delta.total_seconds() / 60)
            
            # Calculate actual transit time
            actual_delta = next_stop.actual_arrival - current_stop.actual_departure
            actual_minutes = int(actual_delta.total_seconds() / 60)
            
            # Skip invalid times (negative or unreasonably long)
            if actual_minutes <= 0 or actual_minutes > 300:
                logger.warning(
                    "invalid_transit_time",
                    journey_id=journey.id,
                    segment=f"{current_stop.station_code}-{next_stop.station_code}",
                    minutes=actual_minutes
                )
                continue
            
            # Create segment record
            segment = SegmentTransitTime(
                journey_id=journey.id,
                from_station_code=current_stop.station_code,
                to_station_code=next_stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_minutes or actual_minutes,
                actual_minutes=actual_minutes,
                delay_minutes=actual_minutes - (scheduled_minutes or actual_minutes),
                departure_time=current_stop.actual_departure,
                hour_of_day=current_stop.actual_departure.hour,
                day_of_week=current_stop.actual_departure.weekday()
            )
            
            db.add(segment)
    
    async def _analyze_dwell_times(
        self, db: AsyncSession, journey: TrainJourney, stops: List[JourneyStop]
    ) -> None:
        """Calculate and store station dwell times."""
        
        for i, stop in enumerate(stops):
            # For origin station, only departure time matters
            if i == 0:
                if stop.actual_departure and stop.scheduled_departure:
                    delay = int((stop.actual_departure - stop.scheduled_departure).total_seconds() / 60)
                    
                    dwell = StationDwellTime(
                        journey_id=journey.id,
                        station_code=stop.station_code,
                        data_source=journey.data_source,
                        line_code=journey.line_code,
                        scheduled_minutes=0,
                        actual_minutes=delay if delay > 0 else 0,
                        excess_dwell_minutes=delay,
                        is_origin=True,
                        departure_time=stop.actual_departure,
                        hour_of_day=stop.actual_departure.hour,
                        day_of_week=stop.actual_departure.weekday()
                    )
                    db.add(dwell)
                continue
            
            # For other stations, calculate dwell time
            if not (stop.actual_arrival and stop.actual_departure):
                continue
            
            actual_dwell = int((stop.actual_departure - stop.actual_arrival).total_seconds() / 60)
            
            # Calculate scheduled dwell if available
            scheduled_dwell = None
            if stop.scheduled_arrival and stop.scheduled_departure:
                scheduled_dwell = int((stop.scheduled_departure - stop.scheduled_arrival).total_seconds() / 60)
            
            excess_dwell = actual_dwell - (scheduled_dwell or 0)
            
            dwell = StationDwellTime(
                journey_id=journey.id,
                station_code=stop.station_code,
                data_source=journey.data_source,
                line_code=journey.line_code,
                scheduled_minutes=scheduled_dwell,
                actual_minutes=actual_dwell,
                excess_dwell_minutes=excess_dwell,
                is_terminal=(i == len(stops) - 1),
                arrival_time=stop.actual_arrival,
                departure_time=stop.actual_departure,
                hour_of_day=stop.actual_departure.hour,
                day_of_week=stop.actual_departure.weekday()
            )
            db.add(dwell)
```

### 1.3 Integration Points

Integrate TransitAnalyzer into existing collectors:

```python
# In trackrat/collectors/njt/journey.py and amtrak/journey.py
# After journey collection completes:

if journey.has_complete_journey and journey.actual_departure:
    analyzer = TransitAnalyzer()
    await analyzer.analyze_journey(db, journey)
```

## Phase 2: Progress Tracking & Predictions (Week 3-4)

### 2.1 Recent Train Performance Service

```python
# trackrat/services/recent_trains.py

class RecentTrainAnalyzer:
    """Analyzes recent trains on the same route for predictions."""
    
    async def get_recent_similar_trains(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
        hours_back: int = 6,
        limit: int = 10
    ) -> List[TrainJourney]:
        """Get recent trains that traveled the same route."""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Find journeys containing both stations in correct order
        stmt = (
            select(TrainJourney)
            .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                TrainJourney.data_source == data_source,
                TrainJourney.actual_departure.isnot(None),
                TrainJourney.last_updated_at > cutoff_time
            )
            .options(selectinload(TrainJourney.stops))
            .order_by(TrainJourney.actual_departure.desc())
            .distinct()
        )
        
        result = await db.execute(stmt)
        all_journeys = result.scalars().all()
        
        # Filter to journeys with our route
        similar_trains = []
        for journey in all_journeys:
            from_idx = to_idx = None
            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_idx = stop.stop_sequence
                elif stop.station_code == to_station:
                    to_idx = stop.stop_sequence
            
            if from_idx is not None and to_idx is not None and from_idx < to_idx:
                similar_trains.append(journey)
                if len(similar_trains) >= limit:
                    break
        
        return similar_trains
    
    async def get_recent_segment_performance(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str,
        data_source: str,
        hours_back: int = 4
    ) -> Dict[str, float]:
        """Get recent performance metrics for a specific segment."""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        stmt = (
            select(SegmentTransitTime)
            .where(
                SegmentTransitTime.from_station_code == from_station,
                SegmentTransitTime.to_station_code == to_station,
                SegmentTransitTime.data_source == data_source,
                SegmentTransitTime.departure_time > cutoff_time
            )
            .order_by(SegmentTransitTime.departure_time.desc())
            .limit(20)
        )
        
        result = await db.execute(stmt)
        recent_segments = result.scalars().all()
        
        if not recent_segments:
            return None
        
        transit_times = [s.actual_minutes for s in recent_segments]
        delays = [s.delay_minutes for s in recent_segments]
        
        return {
            'avg_transit_minutes': sum(transit_times) / len(transit_times),
            'avg_delay_minutes': sum(delays) / len(delays),
            'sample_count': len(recent_segments),
            'latest_transit_minutes': transit_times[0] if transit_times else None
        }
```

### 2.2 Prediction Service

```python
# trackrat/services/predictions/journey_predictor.py

class JourneyPredictor:
    """Predicts arrival times based on recent similar trains."""
    
    def __init__(self):
        self.recent_trains = RecentTrainAnalyzer()
    
    async def predict_arrival(
        self,
        db: AsyncSession,
        journey: TrainJourney,
        target_station: str
    ) -> PredictionResult:
        """Predict arrival time at target station based on recent trains."""
        
        # Find current position
        current_position = self._get_current_position(journey)
        if not current_position:
            return None
        
        # Get recent similar trains
        similar_trains = await self.recent_trains.get_recent_similar_trains(
            db,
            current_position['next_station'],
            target_station,
            journey.data_source,
            hours_back=6
        )
        
        if not similar_trains:
            return self._fallback_prediction(journey, target_station)
        
        # Calculate expected time based on recent trains
        segment_times = []
        for train in similar_trains[:5]:  # Use up to 5 most recent
            time_taken = self._calculate_segment_time(
                train,
                current_position['next_station'],
                target_station
            )
            if time_taken:
                segment_times.append(time_taken)
        
        if not segment_times:
            return self._fallback_prediction(journey, target_station)
        
        # Use median for robustness against outliers
        median_time = sorted(segment_times)[len(segment_times) // 2]
        
        # Calculate prediction
        predicted_arrival = datetime.utcnow() + timedelta(minutes=median_time)
        
        # Calculate confidence based on consistency
        if len(segment_times) >= 3:
            std_dev = self._calculate_std_dev(segment_times)
            # High confidence if times are consistent (low std dev)
            confidence = max(0.5, min(0.95, 1.0 - (std_dev / median_time)))
        else:
            confidence = 0.6  # Lower confidence with fewer samples
        
        return PredictionResult(
            journey_id=journey.id,
            target_station=target_station,
            predicted_arrival=predicted_arrival,
            confidence_score=confidence,
            based_on_trains=[t.train_id for t in similar_trains[:5]],
            method='recent_similar_trains'
        )
```

### 2.3 API Enhancement

Update existing train endpoints to include progress and predictions:

```python
# In trackrat/api/trains.py

@router.get("/api/v2/trains/{train_id}")
async def get_train_details(
    train_id: str,
    date: Optional[date] = None,
    refresh: bool = False,
    include_predictions: bool = True,
    db: AsyncSession = Depends(get_db)
) -> TrainDetailsResponse:
    """Get train details with progress and predictions."""
    
    # ... existing code ...
    
    # Add progress information
    if journey and journey.stops:
        progress = calculate_journey_progress(journey)
        response.progress = progress
    
    # Add predictions if requested
    if include_predictions and journey:
        predictor = JourneyPredictor()
        
        # Predict arrival at destination
        if destination_stop:
            prediction = await predictor.predict_arrival(
                db, journey, destination_stop.station_code
            )
            if prediction:
                response.predicted_arrival = prediction.predicted_arrival
                response.arrival_confidence = prediction.confidence_score
    
    return response
```

## Phase 3: Route Visualization & Congestion (Week 5-6)

### 3.1 Congestion Calculation Service

```python
# trackrat/services/congestion.py

class CongestionAnalyzer:
    """Analyzes route congestion based on recent segment performance."""
    
    async def get_network_congestion(
        self,
        db: AsyncSession,
        time_window_hours: int = 3
    ) -> List[SegmentCongestion]:
        """Get congestion data for all active segments."""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # Get all recent segment times
        stmt = (
            select(SegmentTransitTime)
            .where(SegmentTransitTime.departure_time > cutoff_time)
            .order_by(SegmentTransitTime.departure_time.desc())
        )
        
        result = await db.execute(stmt)
        recent_segments = result.scalars().all()
        
        # Group by segment and calculate congestion
        segment_groups = {}
        for segment in recent_segments:
            key = (
                segment.from_station_code,
                segment.to_station_code,
                segment.data_source
            )
            if key not in segment_groups:
                segment_groups[key] = []
            segment_groups[key].append(segment)
        
        congestion_data = []
        for (from_station, to_station, data_source), segments in segment_groups.items():
            if len(segments) < 2:
                continue
            
            # Get baseline (use scheduled time or historical average)
            baseline_minutes = segments[0].scheduled_minutes
            if not baseline_minutes:
                # Use median of recent times as baseline
                baseline_minutes = sorted(s.actual_minutes for s in segments)[len(segments) // 2]
            
            # Calculate current congestion
            recent_times = [s.actual_minutes for s in segments[:5]]
            current_avg = sum(recent_times) / len(recent_times)
            congestion_factor = current_avg / baseline_minutes
            
            # Determine congestion level
            if congestion_factor <= 1.1:
                level = 'normal'
                color = '#00ff00'  # Green
            elif congestion_factor <= 1.25:
                level = 'moderate'
                color = '#ffff00'  # Yellow
            elif congestion_factor <= 1.5:
                level = 'heavy'
                color = '#ff8800'  # Orange
            else:
                level = 'severe'
                color = '#ff0000'  # Red
            
            congestion_data.append(SegmentCongestion(
                from_station=from_station,
                to_station=to_station,
                data_source=data_source,
                congestion_factor=congestion_factor,
                congestion_level=level,
                color=color,
                avg_transit_minutes=current_avg,
                baseline_minutes=baseline_minutes,
                sample_count=len(recent_times),
                last_updated=segments[0].departure_time
            ))
        
        return congestion_data
```

### 3.2 Congestion API Endpoint

```python
# In trackrat/api/routes.py

@router.get("/api/v2/routes/congestion")
async def get_route_congestion(
    time_window_hours: int = 3,
    data_source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> CongestionMapResponse:
    """Get current congestion levels for all route segments."""
    
    analyzer = CongestionAnalyzer()
    congestion_data = await analyzer.get_network_congestion(db, time_window_hours)
    
    # Filter by data source if specified
    if data_source:
        congestion_data = [c for c in congestion_data if c.data_source == data_source]
    
    # Add station coordinates for mapping
    for segment in congestion_data:
        segment.from_station_coords = get_station_coordinates(segment.from_station)
        segment.to_station_coords = get_station_coordinates(segment.to_station)
    
    return CongestionMapResponse(
        segments=congestion_data,
        generated_at=datetime.utcnow(),
        time_window_hours=time_window_hours,
        metadata={
            'total_segments': len(congestion_data),
            'congestion_levels': {
                'normal': len([s for s in congestion_data if s.congestion_level == 'normal']),
                'moderate': len([s for s in congestion_data if s.congestion_level == 'moderate']),
                'heavy': len([s for s in congestion_data if s.congestion_level == 'heavy']),
                'severe': len([s for s in congestion_data if s.congestion_level == 'severe'])
            }
        }
    )
```

### 3.3 Station Coordinates

Add to `trackrat/config/stations.py`:

```python
STATION_COORDINATES = {
    'NY': {'lat': 40.7505, 'lon': -73.9934},  # NY Penn
    'NP': {'lat': 40.7348, 'lon': -74.1644},  # Newark Penn
    'TR': {'lat': 40.2206, 'lon': -74.7597},  # Trenton
    'PJ': {'lat': 40.3170, 'lon': -74.6225},  # Princeton Junction
    'MP': {'lat': 40.5686, 'lon': -74.3284},  # Metropark
    'PH': {'lat': 39.9566, 'lon': -75.1820},  # Philadelphia
    'WI': {'lat': 39.7391, 'lon': -75.5516},  # Wilmington
    'BA': {'lat': 39.3076, 'lon': -76.6159},  # BWI Airport
    'BL': {'lat': 39.3072, 'lon': -76.6200},  # Baltimore
    'WS': {'lat': 38.8977, 'lon': -77.0063},  # Washington Union
    # Add more stations as needed
}
```

## Implementation Notes

### Data Collection Integration

1. **Minimal Changes to Existing Collectors**
   - Add TransitAnalyzer call after journey collection
   - No changes to API calls or core logic

2. **Backward Compatibility**
   - All new fields are in separate tables
   - Existing API responses unchanged unless new fields requested

3. **Performance Considerations**
   - Indexes on all lookup fields
   - Limit lookback windows to recent data
   - Use SQLite's efficient query planner

### Testing Strategy

1. **Unit Tests**
   ```python
   # tests/unit/test_transit_analyzer.py
   # Test segment calculation logic
   # Test invalid data handling
   ```

2. **Integration Tests**
   ```python
   # tests/integration/test_predictions.py
   # Test with real journey data
   # Test prediction accuracy
   ```

3. **Performance Tests**
   - Measure query times with realistic data volumes
   - Ensure API response times remain <100ms

### Deployment Steps

1. **Database Migration**
   ```bash
   alembic revision -m "Add transit time tracking tables"
   # Edit generated migration file
   alembic upgrade head
   ```

2. **Code Deployment**
   - Deploy new services
   - Enable TransitAnalyzer in collectors
   - Deploy API enhancements

3. **Backfill Historical Data** (Optional)
   ```python
   # scripts/backfill_transit_times.py
   # Process existing journey data to populate transit times
   ```

## Success Metrics

1. **Data Quality**
   - >90% of segments have transit time data
   - <5% invalid transit times filtered out

2. **Prediction Accuracy**
   - Median prediction error <5 minutes
   - 80% of predictions within 10 minutes

3. **API Performance**
   - Congestion endpoint <200ms response time
   - Prediction calculation <50ms

## Future Enhancements (Beyond Phase 3)

1. **Machine Learning Models**
   - Train models on segment performance patterns
   - Include weather and event data

2. **Real-time Updates**
   - WebSocket support for live congestion updates
   - Push notifications for delay predictions

3. **Advanced Analytics**
   - Identify chronic delay patterns
   - Suggest optimal travel times