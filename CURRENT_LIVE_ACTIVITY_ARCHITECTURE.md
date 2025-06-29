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

### Backend-Generated Payload (Example from logs)
```json
{
  "aps": {
    "timestamp": 1751158747,
    "event": "update",
    "stale-date": 1751159647,
    "content-state": {
      "trainNumber": "7875",
      "statusV2": "EN_ROUTE",
      "statusLocation": null,
      "track": "7",
      "delayMinutes": 0,
      "currentLocation": "NY",
      "nextStop": null,
      "journeyProgress": 0.1,
      "destinationETA": "2025-06-28T21:09:24",
      "trackRatPrediction": null,
      "lastUpdated": 1751158747,
      "hasStatusChanged": false,
      "pushTimestamp": 1751158747
    }
  }
}
```

### Key Payload Fields

1. **Core Status Information**
   - `statusV2`: Enhanced status with conflict resolution (e.g., "EN_ROUTE", "BOARDING", "DEPARTED")
   - `statusLocation`: Human-readable location (e.g., "between New York and Newark")
   - `track`: Assigned track number
   - `delayMinutes`: Current delay in minutes

2. **Journey Progress**
   - `currentLocation`: Station code of last departed stop
   - `nextStop`: Next stop information (currently null in example)
   - `journeyProgress`: 0.0-1.0 progress (0.1 = 10%)
   - `destinationETA`: Estimated arrival time

3. **Metadata**
   - `hasStatusChanged`: Boolean flag for iOS haptic feedback
   - `pushTimestamp`: Unix timestamp for freshness checking
   - `alertMetadata`: Enhanced alert information (when alerts are triggered)

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

## Recent Architecture Improvements (2025-06-29)

### Issues Resolved

1. **✅ Duplicate Live Activity Updates**
   - **Problem**: System was sending two separate notifications within milliseconds
   - **Root Cause**: Parallel processing pipelines (status changes + stop events)
   - **Solution**: Unified event detection with single notification per update cycle

2. **✅ Data Quality Degradation**
   - **Problem**: Second notification overwrote good data with null/empty values
   - **Root Cause**: Stop events used raw Train objects instead of consolidated data
   - **Solution**: All notifications now use enhanced consolidated data exclusively

3. **✅ Architectural Redundancy**
   - **Problem**: Two separate processing flows with duplicate logic
   - **Root Cause**: LiveActivityEventDetector class operating independently
   - **Solution**: Integrated all event detection into TrainUpdateNotificationService

4. **✅ Inefficient Resource Usage**
   - **Problem**: Duplicate APNS calls and API requests
   - **Root Cause**: Separate processing of same train data
   - **Solution**: ~50% reduction in APNS calls through unified processing

### Key Architecture Changes

1. **Unified Event Detection Pipeline**
   - Single `_detect_all_events()` method handles both status and stop events
   - Uses consolidated train data with enhanced statusV2 and progress fields
   - Intelligent event prioritization ensures most important alert is sent

2. **Event Priority System**
   - BOARDING takes highest priority (urgent user action required)
   - Track assignment and approaching stops get high prominence
   - System prevents notification spam while ensuring critical alerts reach users

3. **Enhanced Stop Event Detection**
   - Uses consolidated progress data for accurate approaching stop detection
   - Leverages enhanced stop information for better departure detection
   - Built-in duplicate prevention with notification history tracking

4. **Simplified CLI Processing**
   - Removed separate stop event processing loop
   - All notifications flow through consolidated pipeline
   - Reduced code complexity and potential for inconsistencies

### Remaining Improvement Opportunities

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