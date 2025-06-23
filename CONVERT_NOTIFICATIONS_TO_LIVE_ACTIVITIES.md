# Converting Local Notifications to Live Activity Push Updates

## Executive Summary

This document outlines the work needed to convert TrackRat's local notifications to Live Activity-based push updates, enabling notifications to work reliably when the iOS app is closed or terminated.

### Current State
- All notifications are **local only** and require the app to be running
- Notifications only work for actively tracked trains (Live Activities)
- When the app is closed, users receive **no notifications** about their tracked trains
- Infrastructure for Live Activity push updates already exists but is underutilized

### Proposed State
- Backend detects train events and sends Live Activity push updates
- Notifications work reliably even when the app is completely closed
- Same notification types, but delivered via Live Activity updates
- Better battery life and user experience

## Notifications to Convert

### 1. **Tracking Started Notification**
- **Current**: Local notification when Live Activity starts
- **Current Code**: `LiveActivityService.swift:826-844`
- **Trigger**: When user starts tracking a train
- **Action**: **REMOVE** - Redundant with Live Activity appearing

### 2. **Status Change Notifications**
- **Current**: Local notification for BOARDING, DELAYED, DEPARTED status changes
- **Current Code**: `LiveActivityService.swift:846-884`
- **Trigger**: When train status changes
- **Action**: **KEEP** as Live Activity alerts (already implemented)

### 3. **Stop Departure Notifications**
- **Current**: Local notification when train departs a stop
- **Current Code**: `LiveActivityService.swift:630-688`
- **Trigger**: When train departs any stop in user's journey
- **Action**: **CONVERT** to backend-triggered Live Activity push updates

### 4. **Approaching Stop Notifications**
- **Current**: Local notification when approaching a stop (≤3 minutes)
- **Current Code**: `LiveActivityService.swift:742-787`
- **Trigger**: When train is within 3 minutes of a stop
- **Action**: **CONVERT** to backend-triggered Live Activity push updates

## Implementation Plan

### Phase 1: iOS App Changes

#### 1.1 Remove Redundant Local Notifications

```swift
// In LiveActivityService.swift, remove or comment out:

// 1. Remove sendTrackingStartedNotification (lines 826-844)
// Delete entire function - redundant with Live Activity appearing

// 2. Remove local notification sending from stop departures
// In detectAndNotifyStopDepartures(), comment out:
// await sendStopDepartureNotification(...) 

// 3. Remove local notification sending from approaching stops  
// In detectAndNotifyApproachingStops(), comment out:
// await sendApproachingStopNotification(...)

// Keep the detection logic for local state tracking!
```

#### 1.2 Enhance Push Notification Handling

Update `TrackRatApp.swift` to handle new event types:

```swift
private func handleLiveActivityPushUpdate(_ userInfo: [AnyHashable: Any]) async {
    print("🔄 Processing Live Activity push update")
    
    // Extract event type and data
    guard let eventType = userInfo["event_type"] as? String else {
        // Fallback to existing train data update
        await handleTrainDataUpdate(userInfo)
        return
    }
    
    // Handle specific event types
    switch eventType {
    case "stop_departure":
        await handleStopDeparturePush(userInfo)
    case "approaching_stop":
        await handleApproachingStopPush(userInfo)
    case "train_update":
        await handleTrainDataUpdate(userInfo)
    default:
        print("⚠️ Unknown event type: \(eventType)")
    }
}

private func handleStopDeparturePush(_ userInfo: [AnyHashable: Any]) async {
    guard let eventData = userInfo["event_data"] as? [String: Any],
          let stationName = eventData["station"] as? String,
          let isOrigin = eventData["is_origin"] as? Bool,
          let stopsRemaining = eventData["stops_remaining"] as? Int else {
        print("❌ Invalid stop departure push data")
        return
    }
    
    // The Live Activity update will trigger the Dynamic Island alert
    // Just fetch and update the train data
    await LiveActivityService.shared.fetchAndUpdateTrain()
}

private func handleApproachingStopPush(_ userInfo: [AnyHashable: Any]) async {
    guard let eventData = userInfo["event_data"] as? [String: Any],
          let stationName = eventData["station"] as? String,
          let minutesAway = eventData["minutes_away"] as? Int,
          let isDestination = eventData["is_destination"] as? Bool else {
        print("❌ Invalid approaching stop push data")
        return
    }
    
    // The Live Activity update will trigger the Dynamic Island alert
    await LiveActivityService.shared.fetchAndUpdateTrain()
}
```

#### 1.3 Add New Alert Types to Live Activity

Update `LiveActivityService.swift` to add new alert types:

```swift
enum TrainAlertType {
    // Existing cases...
    case stopDeparture(station: String, isOrigin: Bool, stopsRemaining: Int)
    case approachingStop(station: String, minutes: Int, isDestination: Bool)
    
    var alertConfiguration: AlertConfiguration {
        switch self {
        // Existing cases...
        
        case .stopDeparture(let station, let isOrigin, let stopsRemaining):
            if isOrigin {
                return AlertConfiguration(
                    title: "Train Departed! 🚂",
                    body: "Left \(station) - Journey Started",
                    sound: .default
                )
            } else {
                return AlertConfiguration(
                    title: "Departed \(station) ✅",
                    body: "\(stopsRemaining) stop\(stopsRemaining == 1 ? "" : "s") to destination",
                    sound: .default
                )
            }
            
        case .approachingStop(let station, let minutes, let isDestination):
            if isDestination {
                return AlertConfiguration(
                    title: "Approaching Destination! 📍",
                    body: "Arriving at \(station) in ~\(minutes) minute\(minutes == 1 ? "" : "s")",
                    sound: .default
                )
            } else {
                return AlertConfiguration(
                    title: "Next Stop: \(station) 📍",
                    body: "Arriving in ~\(minutes) minute\(minutes == 1 ? "" : "s")",
                    sound: .default
                )
            }
        }
    }
    
    var isHighPriority: Bool {
        switch self {
        // Existing cases...
        case .stopDeparture(_, let isOrigin, _):
            return isOrigin
        case .approachingStop(_, _, let isDestination):
            return isDestination
        }
    }
}
```

### Phase 2: Backend Implementation

#### 2.1 Event Detection Logic

The backend needs to detect these events for trains with active Live Activities:

```python
# Pseudo-code for backend implementation

class LiveActivityEventDetector:
    def detect_stop_departures(self, train, previous_state, current_state):
        """Detect when a train departs from a stop"""
        events = []
        
        for stop in current_state.stops:
            prev_stop = find_stop(previous_state.stops, stop.station_name)
            
            # Check if stop just changed to departed
            if prev_stop and not prev_stop.departed and stop.departed:
                # Get active Live Activities for this train
                active_activities = get_active_live_activities(train.train_id)
                
                for activity in active_activities:
                    # Check if this stop is in user's journey
                    if is_stop_in_journey(stop, activity.origin, activity.destination):
                        events.append({
                            'type': 'stop_departure',
                            'activity_token': activity.push_token,
                            'device_token': activity.device_token,
                            'data': {
                                'station': stop.station_name,
                                'is_origin': stop.station_name == activity.origin,
                                'stops_remaining': count_remaining_stops(
                                    current_state.stops, 
                                    stop.station_name, 
                                    activity.destination
                                ),
                                'departed_at': stop.actual_departure_time
                            }
                        })
        
        return events
    
    def detect_approaching_stops(self, train, current_state):
        """Detect when train is approaching stops"""
        events = []
        current_time = datetime.now()
        
        for stop in current_state.stops:
            # Skip departed stops
            if stop.departed:
                continue
                
            # Calculate time to arrival
            time_to_arrival = stop.estimated_arrival - current_time
            minutes_away = int(time_to_arrival.total_seconds() / 60)
            
            # Check if within notification window (2-3 minutes)
            if 0 < minutes_away <= 3:
                active_activities = get_active_live_activities(train.train_id)
                
                for activity in active_activities:
                    # Check if we already sent this notification
                    notification_key = f"{train.train_id}-{stop.station_name}-approaching"
                    if not has_notification_been_sent(notification_key, activity.id):
                        if is_stop_in_journey(stop, activity.origin, activity.destination):
                            events.append({
                                'type': 'approaching_stop',
                                'activity_token': activity.push_token,
                                'device_token': activity.device_token,
                                'data': {
                                    'station': stop.station_name,
                                    'minutes_away': minutes_away,
                                    'is_destination': stop.station_name == activity.destination,
                                    'estimated_arrival': stop.estimated_arrival.isoformat()
                                }
                            })
                            mark_notification_sent(notification_key, activity.id)
        
        return events
```

#### 2.2 Push Notification Payload Structure

```json
{
  "aps": {
    "content-available": 1,
    "timestamp": 1234567890,
    "stale-date": 1234567950,
    "content-state": {
      // Regular Live Activity content state update
    },
    "alert": {
      // Optional: Dynamic Island alert
    }
  },
  "event_type": "stop_departure",
  "event_data": {
    "station": "Newark Penn",
    "is_origin": false,
    "stops_remaining": 2,
    "departed_at": "2024-01-20T10:30:00-05:00"
  }
}
```

#### 2.3 Backend API Endpoints

No new endpoints needed! The existing Live Activity token registration already links:
- Device tokens
- Live Activity push tokens  
- Train IDs
- Origin/destination pairs

### Phase 3: Testing Strategy

#### 3.1 Test Scenarios

1. **App Closed Testing**
   - Start tracking a train
   - Force quit the app
   - Verify notifications arrive for:
     - Stop departures
     - Approaching stops
     - Status changes

2. **Multiple Activities**
   - Ensure correct Live Activity receives updates
   - Verify notification deduplication works

3. **Edge Cases**
   - Train delays affecting approach times
   - Skipped stops
   - Service disruptions

#### 3.2 Backend Testing

```python
# Test event detection
def test_stop_departure_detection():
    previous_state = TrainState(stops=[
        Stop(name="Newark", departed=False),
        Stop(name="NY Penn", departed=False)
    ])
    
    current_state = TrainState(stops=[
        Stop(name="Newark", departed=True),
        Stop(name="NY Penn", departed=False)
    ])
    
    events = detector.detect_stop_departures(train, previous_state, current_state)
    assert len(events) == 1
    assert events[0]['data']['station'] == "Newark"
```

## Benefits of This Approach

### For Users
1. **Reliable Notifications**: Work even when app is closed
2. **Better Battery Life**: No background refresh needed
3. **Richer Experience**: Dynamic Island alerts for all events
4. **No Behavior Change**: Same notifications, just more reliable

### For Developers
1. **Simpler iOS Code**: Remove local notification logic
2. **Centralized Logic**: Backend controls notification timing
3. **Better Analytics**: Track notification delivery server-side
4. **Easier Maintenance**: One notification system instead of two

## Migration Plan

### Phase 1: Backend First (No iOS Changes)
1. Implement event detection logic
2. Start sending Live Activity push updates
3. iOS app continues sending local notifications (duplicates OK)

### Phase 2: iOS Cleanup
1. Deploy iOS update that removes local notifications
2. Relies entirely on backend push updates
3. Monitor for any missing notifications

### Phase 3: Enhancement
1. Add more intelligent event detection
2. Implement notification preferences
3. Add analytics and monitoring
