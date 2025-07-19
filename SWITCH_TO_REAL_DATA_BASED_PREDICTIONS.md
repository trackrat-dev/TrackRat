# Switch to Real Data-Based Track Predictions

## Overview

This document outlines the implementation plan to replace the hard-coded track distributions in `StaticTrackDistributionService.swift` with dynamic, database-driven predictions that leverage the existing route history infrastructure.

## Background

### Current State
- **iOS App**: Uses `StaticTrackDistributionService.swift` with hard-coded track probabilities
- **Data Source**: Separate static distributions for NJ Transit vs Amtrak (based on train ID prefix)
- **Scope**: Only NY Penn Station departures
- **Problem**: Static data doesn't evolve with real-world changes

### Available Infrastructure (Post-Refactor)
The large refactor (commit `4b3dd1d`) introduced comprehensive route history tracking that **already calculates track usage statistics**:

- **Endpoint**: `/api/v2/routes/history`
- **Track Logic**: `_calculate_route_stats()` function computes `track_usage_at_origin` percentages
- **Data Filtering**: Built-in support for NJT vs AMTRAK data sources
- **Historical Window**: Configurable time periods (1-365 days)
- **Output Format**: `track_usage: dict[str, int]` (track → usage percentage)

### Key Files
- **Backend**: `/backend_v2/src/trackrat/api/routes.py` (contains track calculation logic)
- **iOS**: `/ios/TrackRat/Services/StaticTrackDistributionService.swift` (to be replaced)
- **Models**: `/ios/TrackRat/Models/Train.swift` (PredictionData struct)

## Implementation Plan: Option A (Recommended)

### Phase 1: Backend API Extension

#### 1.1 Extend Existing Route History Endpoint

**File**: `backend_v2/src/trackrat/api/routes.py`

Add support for station-wide track predictions by extending the existing `/api/v2/routes/history` endpoint:

```python
@router.get("/history", response_model=RouteHistoryResponse)
@handle_errors
async def get_route_history(
    from_station: str = Query(..., min_length=1, max_length=3, description="Origin station code"),
    to_station: str | None = Query(None, min_length=1, max_length=3, description="Destination station code (optional for predictions)"),
    data_source: str = Query(..., description="Data source (NJT or AMTRAK)"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    highlight_train: str | None = Query(None, description="Train ID to highlight"),
    aggregate_destinations: bool = Query(False, description="Aggregate track usage across all destinations for predictions"),
    db: AsyncSession = Depends(get_db),
) -> RouteHistoryResponse:
```

**Key Changes**:
1. Make `to_station` optional (allow `None`)
2. Add `aggregate_destinations` boolean parameter
3. Modify query logic to handle station-wide aggregation

#### 1.2 Modify Query Logic

When `aggregate_destinations=True` and `to_station=None`:

```python
# Query all journeys departing from the origin station (any destination)
stmt = (
    select(TrainJourney)
    .where(
        and_(
            TrainJourney.data_source == data_source,
            TrainJourney.journey_date >= start_date,
            TrainJourney.journey_date <= end_date,
            TrainJourney.origin_station_code == from_station,  # Focus on origin only
        )
    )
    .options(selectinload(TrainJourney.stops))
)

# Skip route filtering - include all journeys from this station
route_journeys = all_journeys  # Don't filter by destination
```

#### 1.3 Update Response Model (Optional)

**File**: `backend_v2/src/trackrat/models/api.py`

Consider adding a dedicated prediction response model for clarity:

```python
class TrackPredictionResponse(BaseModel):
    """Response for track prediction requests."""
    
    station_code: str
    data_source: str
    track_probabilities: dict[str, float] = Field(
        ..., description="Track number to probability mapping (0.0-1.0)"
    )
    historical_period_days: int
    total_trains_analyzed: int
    last_updated: datetime
```

### Phase 2: iOS Implementation

#### 2.1 Create New Dynamic Service

**File**: `ios/TrackRat/Services/DynamicTrackDistributionService.swift`

```swift
import Foundation

/// Dynamic track prediction service using real historical data
/// Replaces StaticTrackDistributionService with database-driven predictions
class DynamicTrackDistributionService {
    static let shared = DynamicTrackDistributionService()
    
    private init() {}
    
    /// Cache for prediction data to avoid repeated API calls
    private var predictionCache: [String: (data: PredictionData, timestamp: Date)] = [:]
    private let cacheValidityDuration: TimeInterval = 3600 // 1 hour
    
    /// Generate prediction data for a train using historical database analysis
    /// Returns nil for stations other than NY Penn Station
    func getPredictionData(for train: TrainV2) async -> PredictionData? {
        // Only provide predictions for NY Penn Station (code "NY")
        guard train.originStationCode == "NY" else {
            return nil
        }
        
        // Determine data source based on train ID
        let dataSource = train.trainId.uppercased().hasPrefix("A") ? "AMTRAK" : "NJT"
        let cacheKey = "\(train.originStationCode!)_\(dataSource)"
        
        // Check cache first
        if let cached = predictionCache[cacheKey],
           Date().timeIntervalSince(cached.timestamp) < cacheValidityDuration {
            return cached.data
        }
        
        do {
            // Call route history API with aggregation enabled
            let routeResponse = try await APIService.shared.getRouteHistory(
                fromStation: train.originStationCode!,
                toStation: nil, // No specific destination
                dataSource: dataSource,
                days: 30,
                highlightTrain: nil,
                aggregateDestinations: true
            )
            
            // Convert integer percentages to double probabilities
            let trackProbabilities = routeResponse.aggregateStats.trackUsageAtOrigin.mapValues { percentage in
                Double(percentage) / 100.0
            }
            
            let predictionData = PredictionData(trackProbabilities: trackProbabilities)
            
            // Cache the result
            predictionCache[cacheKey] = (predictionData, Date())
            
            return predictionData
            
        } catch {
            print("Failed to fetch dynamic track predictions: \(error)")
            
            // Fallback to static predictions
            return getStaticFallbackPredictions(for: train)
        }
    }
    
    /// Check if predictions should be shown for a given train
    func shouldShowPredictions(for train: TrainV2) -> Bool {
        return train.originStationCode == "NY" && train.track == nil
    }
    
    /// Generate adjusted prediction data that excludes occupied tracks
    func getAdjustedPredictionData(for train: TrainV2, excludingOccupiedTracks: Bool = true) async -> PredictionData? {
        guard var predictionData = await getPredictionData(for: train) else {
            return nil
        }
        
        // Apply occupied track exclusion if enabled
        if excludingOccupiedTracks {
            do {
                let occupiedTracks = try await TrackOccupancyService.shared.getOccupiedTracks(for: "NY")
                
                guard var trackProbabilities = predictionData.trackProbabilities else {
                    return predictionData
                }
                
                // Zero out occupied tracks
                for track in occupiedTracks {
                    if let platformGroup = findPlatformGroup(for: track, in: trackProbabilities) {
                        trackProbabilities[platformGroup] = 0.0
                    }
                }
                
                // Renormalize probabilities
                let totalProbability = trackProbabilities.values.reduce(0, +)
                if totalProbability > 0 {
                    for (track, probability) in trackProbabilities {
                        trackProbabilities[track] = probability / totalProbability
                    }
                }
                
                return PredictionData(trackProbabilities: trackProbabilities)
                
            } catch {
                print("Failed to fetch occupied tracks for adjustment: \(error)")
                return predictionData
            }
        }
        
        return predictionData
    }
    
    /// Fallback to static predictions if API fails
    private func getStaticFallbackPredictions(for train: TrainV2) -> PredictionData? {
        return StaticTrackDistributionService.shared.getPredictionData(for: train)
    }
    
    /// Map individual tracks to platform groups for NY Penn Station
    private func findPlatformGroup(for track: String, in probabilities: [String: Double]) -> String? {
        return probabilities.keys.contains(track) ? track : nil
    }
    
    /// Clear prediction cache (useful for testing or forced refresh)
    func clearCache() {
        predictionCache.removeAll()
    }
}
```

#### 2.2 Update APIService

**File**: `ios/TrackRat/Services/APIService.swift`

Add method to call the route history endpoint with prediction parameters:

```swift
func getRouteHistory(
    fromStation: String,
    toStation: String? = nil,
    dataSource: String,
    days: Int = 30,
    highlightTrain: String? = nil,
    aggregateDestinations: Bool = false
) async throws -> RouteHistoryResponse {
    var components = URLComponents(string: "\(baseURL)/routes/history")!
    
    var queryItems = [
        URLQueryItem(name: "from_station", value: fromStation),
        URLQueryItem(name: "data_source", value: dataSource),
        URLQueryItem(name: "days", value: String(days)),
        URLQueryItem(name: "aggregate_destinations", value: String(aggregateDestinations))
    ]
    
    if let toStation = toStation {
        queryItems.append(URLQueryItem(name: "to_station", value: toStation))
    }
    
    if let highlightTrain = highlightTrain {
        queryItems.append(URLQueryItem(name: "highlight_train", value: highlightTrain))
    }
    
    components.queryItems = queryItems
    
    guard let url = components.url else {
        throw APIError.invalidURL
    }
    
    let (data, _) = try await urlSession.data(from: url)
    return try jsonDecoder.decode(RouteHistoryResponse.self, from: data)
}
```

#### 2.3 Update Response Models

**File**: `ios/TrackRat/Models/Train.swift`

Ensure `RouteHistoryResponse` and related models exist (they should from the refactor):

```swift
struct RouteHistoryResponse: Codable {
    let route: HistoricalRouteInfo
    let aggregateStats: AggregateStats
    let highlightedTrain: HighlightedTrain?
    
    enum CodingKeys: String, CodingKey {
        case route
        case aggregateStats = "aggregate_stats"
        case highlightedTrain = "highlighted_train"
    }
}

struct AggregateStats: Codable {
    let onTimePercentage: Double
    let averageDelayMinutes: Double
    let cancellationRate: Double
    let delayBreakdown: DelayBreakdown
    let trackUsageAtOrigin: [String: Int]
    
    enum CodingKeys: String, CodingKey {
        case onTimePercentage = "on_time_percentage"
        case averageDelayMinutes = "average_delay_minutes"
        case cancellationRate = "cancellation_rate"
        case delayBreakdown = "delay_breakdown"
        case trackUsageAtOrigin = "track_usage_at_origin"
    }
}
```

### Phase 3: Integration and Migration

#### 3.1 Update Train Views

**Files**: 
- `ios/TrackRat/Views/Screens/TrainListView.swift`
- `ios/TrackRat/Views/Screens/TrainDetailsView.swift`

Replace references to `StaticTrackDistributionService` with `DynamicTrackDistributionService`:

```swift
// Old
let predictionData = StaticTrackDistributionService.shared.getPredictionData(for: train)

// New  
let predictionData = await DynamicTrackDistributionService.shared.getPredictionData(for: train)
```

**Note**: This requires making the calling functions `async` and handling the await properly.

#### 3.2 Maintain Backward Compatibility

Keep `StaticTrackDistributionService.swift` as a fallback during the transition:

1. First deploy backend changes
2. Test API endpoint thoroughly
3. Deploy iOS changes with fallback enabled
4. Monitor for any issues
5. Remove static service after confidence is established

### Phase 4: Testing and Validation

#### 4.1 Backend Testing

**Test Cases**:
1. Station-wide aggregation works correctly
2. Data source filtering (NJT vs AMTRAK) produces different results
3. Historical window parameter affects results appropriately
4. Track percentages sum to 100% (or close to it)
5. Edge cases (no historical data, single track usage, etc.)

**Manual Testing**:
```bash
# Test NY Penn Station NJT predictions
curl "http://localhost:8000/api/v2/routes/history?from_station=NY&data_source=NJT&aggregate_destinations=true&days=30"

# Test NY Penn Station Amtrak predictions  
curl "http://localhost:8000/api/v2/routes/history?from_station=NY&data_source=AMTRAK&aggregate_destinations=true&days=30"
```

#### 4.2 iOS Testing

**Test Cases**:
1. Dynamic predictions load correctly for NJT trains
2. Dynamic predictions load correctly for Amtrak trains
3. Fallback to static predictions works when API fails
4. Caching reduces redundant API calls
5. Occupied track exclusion still functions properly
6. UI shows appropriate confidence levels

**Test Data Comparison**:
Compare dynamic predictions against current static distributions to ensure reasonableness:

```swift
// Print both for comparison during testing
let staticData = StaticTrackDistributionService.shared.getPredictionData(for: train)
let dynamicData = await DynamicTrackDistributionService.shared.getPredictionData(for: train)

print("Static predictions: \(staticData?.trackProbabilities ?? [:])")
print("Dynamic predictions: \(dynamicData?.trackProbabilities ?? [:])")
```

#### 4.3 Data Quality Validation

**Sanity Checks**:
1. Track numbers should be valid for NY Penn Station (1-21)
2. Probabilities should be reasonable (no single track >50% for diverse services)
3. Amtrak should favor higher-numbered tracks (14, 15, etc.)
4. NJT should have more diverse distribution across mid-range tracks

## Edge Cases and Error Handling

### 1. Insufficient Historical Data
**Scenario**: New station or recent service changes
**Solution**: Fallback to static predictions with warning log

### 2. API Failure
**Scenario**: Network issues or backend downtime
**Solution**: Use cached data if available, then fallback to static predictions

### 3. Malformed Response
**Scenario**: API returns unexpected data structure
**Solution**: Log error details and fallback to static predictions

### 4. Zero Track Assignments
**Scenario**: Historical period with no track data
**Solution**: Extend historical window or fallback to static data

### 5. Cache Invalidation
**Scenario**: Need to refresh predictions for testing
**Solution**: Provide cache clearing mechanism in debug builds

## Performance Considerations

### 1. API Call Frequency
- **Cache predictions** for 1 hour to reduce API load
- **Batch requests** when multiple trains need predictions
- **Background refresh** to update cache before needed

### 2. Response Time
- Current route history endpoint should respond in <200ms
- Consider adding database indexes if performance degrades
- Monitor API response times in production

### 3. Memory Usage
- Cache size should be minimal (few KB per station/data source)
- Clear old cache entries automatically
- Avoid caching when memory warnings occur

## Configuration and Rollout

### Environment Variables
```bash
# Backend configuration
TRACK_PREDICTION_DEFAULT_DAYS=30
TRACK_PREDICTION_CACHE_TTL=3600

# Feature flags (optional)
ENABLE_DYNAMIC_PREDICTIONS=true
ENABLE_PREDICTION_FALLBACK=true
```

### Feature Flags
Consider implementing feature flags for gradual rollout:

```swift
struct FeatureFlags {
    static let enableDynamicPredictions = true
    static let enablePredictionFallback = true
    static let logPredictionComparisons = false // Debug only
}
```

### Deployment Strategy
1. **Week 1**: Deploy backend changes, test endpoint manually
2. **Week 2**: Deploy iOS changes with feature flag disabled
3. **Week 3**: Enable feature flag for beta users
4. **Week 4**: Enable for all users, monitor performance
5. **Week 5**: Remove static service if stable

## Monitoring and Metrics

### Backend Metrics
- Track prediction API call frequency
- Response times for prediction requests
- Error rates and failure modes
- Track coverage (percentage of trains with historical track data)

### iOS Metrics
- Prediction cache hit rate
- Fallback usage frequency
- API call patterns and errors

### Business Metrics
- Prediction accuracy comparison (static vs dynamic)
- User engagement with track predictions
- Complaint rates about incorrect predictions

## Success Criteria

### Technical Success
- ✅ API responds in <200ms for prediction requests
- ✅ Cache hit rate >80% during normal usage
- ✅ Fallback success rate >95% when API fails
- ✅ No increase in crash rates or memory issues

### Data Quality Success  
- ✅ Dynamic predictions show realistic track distributions
- ✅ Amtrak vs NJT predictions differ appropriately
- ✅ Track usage reflects known operational patterns
- ✅ Predictions update automatically with new data

### User Experience Success
- ✅ No noticeable delay in prediction display
- ✅ Predictions remain accurate or improve vs static
- ✅ No user-reported issues with missing predictions
- ✅ Smooth transition with no disruption to existing features

## Future Enhancements

### Short Term (Next 3 months)
1. **Extend to other stations** beyond NY Penn Station
2. **Time-based predictions** (rush hour vs off-peak patterns)
3. **Confidence intervals** based on historical data volume

### Medium Term (Next 6 months)
1. **Real-time adjustments** based on current track occupancy
2. **Train-specific patterns** (some trains consistently use certain tracks)
3. **Weather and disruption factors** in predictions

### Long Term (Next year)
1. **Machine learning models** for more sophisticated predictions
2. **Cross-station prediction** (if train uses track X at station A, predict track Y at station B)
3. **User feedback integration** (learn from prediction accuracy reports)

## Rollback Plan

If issues arise, rollback can be executed at multiple levels:

### Level 1: Feature Flag Disable
```swift
// Instant rollback via code change
struct FeatureFlags {
    static let enableDynamicPredictions = false // Forces fallback to static
}
```

### Level 2: API Endpoint Disable
- Modify backend to return empty results
- iOS will automatically fallback to static predictions

### Level 3: Full Revert
- Revert iOS changes to use only `StaticTrackDistributionService`
- Remove backend endpoint modifications
- Return to previous stable state

## Documentation Updates

After implementation, update:

1. **CLAUDE.md files**: Document the new prediction system
2. **API documentation**: Include prediction endpoint details  
3. **iOS architecture docs**: Update service layer descriptions
4. **README files**: Note the switch from static to dynamic predictions

## Conclusion

This implementation leverages the existing route history infrastructure to provide dynamic, database-driven track predictions with minimal code changes. The approach is designed to be:

- **Safe**: Comprehensive fallback mechanisms
- **Performant**: Caching and optimized API calls
- **Maintainable**: Builds on existing, tested infrastructure
- **Extensible**: Foundation for future ML-based enhancements

The key insight is that the hard work of track usage calculation is already done in the route history system - we just need to expose it in a prediction-friendly way.