# Current Live Activity Architecture Analysis

## Overview

The TrackRat Live Activity system consists of a unified push notification infrastructure that keeps users informed about their train journey in real-time. The system leverages Apple's Live Activities feature to display persistent updates on the Lock Screen and Dynamic Island, with backend-driven push notifications providing timely alerts through a single, integrated notification pipeline.

## Architecture Components

### Backend (Python/FastAPI)

#### Key Services

1. **APNSPushService** (`push_notification.py`)
   - JWT-based authentication with APNS
   - Manages both regular push notifications and Live Activity updates
   - Environment-aware (production vs sandbox)
   - Automatic token refresh every 55 minutes

2. **TrainUpdateNotificationService** (`push_notification.py`)
   - **Unified event detection**: Detects both status changes and stop events in one pass
   - **Event prioritization**: Intelligently selects highest priority alert to send
   - **Consolidated data processing**: Uses enhanced train data with statusV2 and progress fields
   - **Single notification flow**: Sends exactly one update per processing cycle
   - **State tracking**: Maintains both train state and stop history for change detection
   - **Duplicate prevention**: Built-in notification history to prevent alert spam

#### Database Models

- **DeviceToken**: Stores regular push notification tokens
- **LiveActivityToken**: Stores Live Activity-specific push tokens with train associations
- Both linked via foreign key relationship for coordinated notifications

### iOS (Swift/SwiftUI)

#### Key Components

1. **LiveActivityService** (`LiveActivityService.swift`)
   - Singleton managing Live Activity lifecycle
   - Background refresh every 30 seconds
   - Push token registration with backend
   - Haptic feedback based on alert metadata
   - Auto-end logic for completed journeys

2. **TrainActivityAttributes** (`LiveActivityModels.swift`)
   - Static attributes: train number, route, origin/destination
   - Dynamic ContentState with real-time updates

3. **LiveActivityWidget** (`LiveActivityWidget.swift`)
   - Lock Screen and Dynamic Island UI
   - Compact, expanded, and minimal layouts
   - Journey progress visualization

## Data Flow

### 1. Live Activity Creation
```
User starts tracking → iOS creates Live Activity → Push token generated → Token sent to backend
```

### 2. Unified Update Cycle
```
Backend polls APIs (60-120s) → Consolidated data processing → Unified event detection → Event prioritization → Single APNS payload → iOS updates Live Activity
```

### 3. Unified Event Detection & Alert Flow
```
Status changes + Stop events detected together → Priority algorithm selects top event → Single notification with complete data → Haptic feedback based on priority
```

## Payload Structure

### Enhanced Live Activity Payload (Fixed Format)

The backend now generates enriched payloads with properly structured data that matches iOS expectations exactly:

```json
{
  "aps": {
    "timestamp": 1751158747,
    "event": "update",
    "stale-date": 1751159647,
    "content-state": {
      "trainNumber": "A2205",
      "statusV2": "EN_ROUTE",
      "statusLocation": "between Baltimore Penn Station and Wilmington",
      "track": "13",
      "delayMinutes": 0,
      "currentLocation": {
        "departed": {
          "from": "Baltimore Penn Station",
          "minutesAgo": 5
        }
      },
      "nextStop": {
        "stationName": "Wilmington",
        "estimatedArrival": "2025-06-29T13:15:00",
        "scheduledArrival": "2025-06-29T13:15:00",
        "isDelayed": false,
        "delayMinutes": 0,
        "isDestination": false,
        "minutesAway": 19
      },
      "journeyProgress": 0.43,
      "destinationETA": "2025-06-29T14:30:00",
      "trackRatPrediction": {
        "topTrack": "13",
        "confidence": 0.85,
        "alternativeTracks": ["4", "7"]
      },
      "lastUpdated": 1751158747,
      "hasStatusChanged": false,
      "pushTimestamp": 1751158747
    }
  }
}
```

### Fixed Payload Issues

**Previous Issues (Causing Frozen Progress Wheel):**
- ❌ `currentLocation` was a simple string ("BA") 
- ❌ `nextStop` was frequently null
- ❌ `destinationETA` had incorrect dates
- ❌ Missing rich data structures for UI rendering

**Current Fixes (2025-06-29):**
- ✅ `currentLocation` is now a properly structured Swift enum dictionary
- ✅ `nextStop` contains complete station information with timing
- ✅ `destinationETA` uses correct dates from final stop
- ✅ All fields match iOS model expectations exactly

### Field-by-Field Analysis

| Field | Format | iOS Usage | Backend Source | Notes |
|-------|---------|-----------|---------------|-------|
| `trainNumber` | `string` | Train identification in UI | `train_id` | ✅ Working |
| `statusV2` | `string` | Status display and color | `status_v2.current` | ✅ Working |
| `statusLocation` | `string?` | Enhanced status description | `status_v2.location` | ✅ Working |
| `track` | `string?` | Track display | `track_assignment.track` | ✅ Working |
| `delayMinutes` | `int` | Delay indicator | `delay_minutes` | ✅ Working |
| **`currentLocation`** | `enum dict` | Location display text | **Enhanced from progress** | ✅ **FIXED** |
| **`nextStop`** | `object?` | Next stop display | **Enhanced from progress** | ✅ **FIXED** |
| `journeyProgress` | `double` (0-1) | Progress bar | `progress.journey_percent / 100` | ✅ Working |
| **`destinationETA`** | `ISO8601 string` | Arrival countdown | **Final stop estimated_arrival** | ✅ **FIXED** |
| `trackRatPrediction` | `object?` | Track predictions | `prediction_data` | ✅ Working |

### CurrentLocation Structure

The `currentLocation` field now uses Swift's automatic enum Codable format:

```json
// Boarding at station
{
  "boarding": {
    "station": "New York Penn Station"
  }
}

// Departed from station
{
  "departed": {
    "from": "Baltimore Penn Station", 
    "minutesAgo": 5
  }
}

// En route between stations
{
  "enRoute": {
    "between": "Baltimore Penn Station",
    "and": "Wilmington"
  }
}

// Approaching station
{
  "approaching": {
    "station": "Wilmington",
    "minutesAway": 3
  }
}

// Not departed yet
{
  "notDeparted": {
    "departureTime": "2025-06-29T12:00:00"
  }
}

// Arrived (simple string)
"arrived"
```

### NextStop Structure

The `nextStop` field provides complete station information:

```json
{
  "stationName": "Wilmington",
  "estimatedArrival": "2025-06-29T13:15:00",
  "scheduledArrival": "2025-06-29T13:15:00", 
  "isDelayed": false,
  "delayMinutes": 0,
  "isDestination": false,
  "minutesAway": 19
}
```

### Data Enrichment Process

The backend now includes a comprehensive data enrichment pipeline in `_enrich_state_for_live_activity()`:

1. **`_create_current_location_dict()`**: Transforms status_v2 and progress data into Swift-compatible enum format
2. **`_create_next_stop_dict()`**: Builds complete next stop information from progress.next_arrival
3. **`_format_destination_eta()`**: Extracts final destination ETA from consolidated stops
4. **`_get_station_name_from_code()`**: Converts station codes to human-readable names

## Root Cause Analysis: Frozen Progress Wheel Issue

### Problem Identified (June 29, 2025)

**Symptom**: Live Activities would sometimes show a frozen progress wheel with hidden text, resolved only by opening the main iOS app.

**Root Cause**: Backend was sending incomplete/incorrectly formatted data in APNS notifications that didn't match iOS Live Activity model expectations.

### Specific Issues Found

1. **Data Structure Mismatch**:
   - Backend sent `currentLocation` as simple string ("BA") 
   - iOS expected complex enum dictionary with type and associated values
   - Caused Live Activity UI components to fail rendering

2. **Missing Critical Fields**:
   - `nextStop` frequently null due to incorrect field extraction
   - `destinationETA` had wrong dates (2025-06-22 vs 2025-06-29)
   - Progress wheel couldn't display without next stop information

3. **Field Name Mismatches**:
   - Backend created `next_stop` but iOS expected `next_stop_info`  
   - Backend created `track_prediction` but iOS expected `trackrat_prediction`
   - Field mismatches caused silent failures in Live Activity updates

### Fix Implementation

**Backend Changes** (`push_notification.py`):
- Added `_enrich_state_for_live_activity()` method for proper data transformation
- Fixed `_create_current_location_dict()` to generate Swift-compatible enum format
- Enhanced `_create_next_stop_dict()` to build complete station information
- Corrected field naming to match iOS expectations exactly

**Result**: Live Activities now receive complete, properly formatted data that matches iOS model definitions, eliminating frozen progress wheels and enabling full UI functionality.

### Key Lessons Learned

1. **Data Format Synchronization is Critical**: Backend and frontend must agree on exact data structures, especially for real-time updates
2. **Swift Enum Codable Format**: When working with Swift enums, backend must send data in the specific format Swift's automatic Codable implementation expects
3. **Field Naming Consistency**: Even small naming differences (`next_stop` vs `next_stop_info`) can cause silent failures
4. **Comprehensive Testing**: Live Activity payloads need thorough testing with actual iOS decoding, not just JSON validation
5. **Rich Data is Essential**: UI components fail gracefully but poorly when missing expected data structures

## Alert Conditions & Event Prioritization

The unified system detects all events simultaneously and prioritizes them to send only the most important alert. Event priority order (highest to lowest):

### 1. **Boarding** (AlertType.BOARDING) - **HIGHEST PRIORITY**
- **Condition**: Status changes to include "BOARDING"
- **Relevance Score**: 100.0 (maximum)
- **Priority**: urgent
- **Haptic**: Yes
- **Message**: "Time to Board! 🚆 Track X - All Aboard!"

### 2. **Track Assignment** (AlertType.TRACK_ASSIGNED)
- **Condition**: Track changes from null/empty to assigned value
- **Relevance Score**: 95.0
- **Priority**: high
- **Haptic**: Yes
- **Message**: "Track Assigned! 🚋 Track X - Get Ready to Board"

### 3. **Approaching Stop** (AlertType.APPROACHING_STOP)
- **Condition**: Within 3 minutes of next stop (from consolidated progress data)
- **Relevance Score**: 90.0
- **Priority**: high
- **Haptic**: Yes
- **Message**: "Approaching Stop 📍 Next stop coming up"

### 4. **Departure** (AlertType.DEPARTED)
- **Condition**: Status changes to "DEPARTED"
- **Relevance Score**: 88.0
- **Priority**: high
- **Haptic**: Yes
- **Message**: "Journey Started 🛤️ Train X has departed"

### 5. **Stop Departure** (AlertType.STOP_DEPARTURE)
- **Condition**: Train departs from intermediate stops (detected via consolidated stops data)
- **Relevance Score**: 85.0
- **Priority**: high
- **Haptic**: Yes
- **Message**: "Stop Departure 🚂 Train departed [Station]"

### 6. **Delay Update** (AlertType.DELAY_UPDATE)
- **Condition**: Delay changes by ≥5 minutes
- **Relevance Score**: 60-75 (based on severity)
- **Priority**: medium/low
- **Haptic**: Only for delays ≥15 minutes
- **Message**: "Delay Update ⏰ Train X now Y minutes delayed"

### 7. **Status Change** (AlertType.STATUS_CHANGE) - **LOWEST PRIORITY**
- **Condition**: Significant status changes (DELAYED, CANCELLED)
- **Relevance Score**: 70.0
- **Priority**: medium
- **Haptic**: No
- **Message**: "Status Update 📢 Train X status has changed"

## iOS Update Handling

### 1. Live Activity Updates
- **Automatic**: iOS handles APNS Live Activity updates natively
- **Manual Refresh**: Background fetch every 30 seconds via `fetchAndUpdateTrain()`
- **Relevance Scoring**: Backend provides scores (0-100) for Dynamic Island prominence

### 2. Haptic Feedback
The iOS app provides haptic feedback based on:
- **Backend Metadata**: When `requiresHapticFeedback` is true
- **Priority Mapping**:
  - urgent → heavy impact
  - high → medium impact
  - medium → light impact
  - low → soft impact
- **Status Changes**: Success haptic for boarding/departure, warning for delays

### 3. Auto-End Logic
Live Activities automatically end when:
- Journey progress reaches 100% AND train is marked as arrived
- Train departed over 1 hour ago with 100% progress
- No updates for extended period (stale data)
- User manually ends tracking

## Remaining Improvement Opportunities

1. **Enhanced Alert Context**
   - Add station names and specific timing to alert messages
   - Better utilization of statusLocation field for contextual information
   - Customizable alert preferences per user

2. **Advanced Progress Tracking**
   - GPS-based position verification for accuracy
   - Predictive ETA based on historical performance
   - Intermediate milestone notifications (25%, 50%, 75% journey completion)

3. **Optimized Background Processing**
   - Reduce iOS 30-second polling when push notifications are reliable
   - Implement push notification acknowledgment system
   - Smart battery optimization based on notification delivery success

## Security & Privacy Considerations

1. **Token Management**
   - Push tokens properly associated with devices
   - Tokens expire and are cleaned up when Live Activities end
   - No user identification in payloads

2. **Data Minimization**
   - Only essential journey data in payloads
   - No personal information transmitted
   - Local storage only for active journeys

## Monitoring & Debugging

### Backend Logging
- Comprehensive logging at each stage of notification process
- APNS response tracking
- Alert type and relevance score logging

### iOS Debugging
- `LiveActivityDebugView` for testing states
- Console logging for update lifecycle
- Push notification delivery tracking

## Conclusion

The Live Activity architecture has been significantly improved with the unified notification system, eliminating duplicate updates and ensuring consistent data quality. The system now provides a more efficient and reliable foundation for real-time train tracking with sophisticated alert capabilities.

### Current Strengths (Post-Unification)
- **Single notification per update**: Eliminates duplicate APNS calls and user confusion
- **Consistent data quality**: All updates use enhanced consolidated data exclusively
- **Intelligent event prioritization**: Most important alerts reach users prominently
- **Efficient resource usage**: ~50% reduction in APNS calls and backend processing
- **Comprehensive event detection**: Unified system catches all status and stop events
- **Reliable push notification delivery**: JWT authentication with proper error handling
- **Rich journey progress tracking**: Enhanced progress data from train consolidation

### Resolved Issues
- ✅ Duplicate Live Activity updates eliminated
- ✅ Data quality degradation fixed  
- ✅ Architectural redundancy removed
- ✅ Resource efficiency improved
- ✅ Notification spam prevented

### Future Enhancement Opportunities
- Enhanced contextual alert messages with station names and timing
- GPS-based position verification for accuracy improvements
- Advanced battery optimization based on push notification reliability
- Customizable user alert preferences
- Predictive ETAs using historical performance data

The unified architecture successfully balances real-time updates with system efficiency while providing a premium user experience through Live Activities and Dynamic Island integration. The system is now better positioned for future enhancements and maintains the sophisticated alert capabilities users expect.
