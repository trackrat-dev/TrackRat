# Live Activity Push Notification Improvements

## Current Implementation Review

The implementation successfully converts local notifications to push-based Live Activity updates. However, there are several iOS best practices and improvements that should be implemented:

## 1. Live Activity Content State Improvements

### Add Stale Date Support
```swift
// In LiveActivityService.swift - updateActivity method
let staleDate = Date().addingTimeInterval(15 * 60) // 15 minutes from now

let activityContent = ActivityContent(
    state: newState,
    staleDate: staleDate,
    relevanceScore: relevanceScore
)
```

### Implement Dismissal Policy
```swift
// When ending activities
await activity.end(
    finalContent, 
    dismissalPolicy: .after(Date().addingTimeInterval(30)) // Keep for 30 seconds
)
```

## 2. Push Notification Payload Improvements

### Backend Changes Needed

#### Add Stale Date to Payload
```python
# In push_notification.py - _create_live_activity_payload
payload = {
    "aps": {
        "timestamp": int(time.time()),
        "event": "update",
        "stale-date": int(time.time() + 900),  # 15 minutes from now
        "content-state": {
            # ... existing content
        }
    }
}
```

#### Add Dismissal Policy Support
```python
# For ending activities
if event_type == "journey_complete":
    payload["aps"]["event"] = "end"
    payload["aps"]["dismissal-date"] = int(time.time() + 30)  # Dismiss after 30 seconds
```

## 3. Enhanced Alert Types

### iOS Implementation
```swift
// Add journey completion alert
case journeyComplete(station: String, onTime: Bool)

// In alertConfiguration
case .journeyComplete(let station, let onTime):
    return AlertConfiguration(
        title: "Journey Complete! 🎉",
        body: onTime ? "Arrived at \(station) on time" : "Arrived at \(station)",
        sound: .default
    )
```

### Backend Implementation
```python
AlertType.JOURNEY_COMPLETE = "journey_complete"
```

## 4. Activity Push Type Declaration

### Update Info.plist
```xml
<key>NSSupportsLiveActivitiesFrequentUpdates</key>
<true/>
<key>UIBackgroundModes</key>
<array>
    <string>fetch</string>
    <string>remote-notification</string>
    <string>processing</string>
</array>
```

## 5. Improved Error Handling

### iOS Changes
```swift
// In handleLiveActivityPushUpdate
private func handleLiveActivityPushUpdate(_ userInfo: [AnyHashable: Any]) async {
    print("🔄 Processing Live Activity push update")
    
    // Validate push token matches current activity
    if let pushToken = userInfo["push_token"] as? String,
       let currentActivity = LiveActivityService.shared.currentActivity {
        let currentToken = currentActivity.pushToken
        if pushToken != currentToken {
            print("⚠️ Push token mismatch, ignoring update")
            return
        }
    }
    
    // Continue with existing logic...
}
```

## 6. Background Update Optimization

### Add Batch Processing
```swift
// In LiveActivityService
private var pendingUpdates: [(train: Train, alertType: TrainAlertType?)] = []
private let updateDebouncer = Timer.publish(every: 1.0, on: .main, in: .common)

func queueUpdate(train: Train, alertType: TrainAlertType? = nil) {
    pendingUpdates.append((train, alertType))
}

private func processPendingUpdates() async {
    guard !pendingUpdates.isEmpty else { return }
    
    // Process the most recent update
    let update = pendingUpdates.last!
    pendingUpdates.removeAll()
    
    await updateActivity(with: update.train, alertType: update.alertType)
}
```

## 7. Push Token Management

### Improved Token Storage
```swift
// In LiveActivityService
func storePushToken(_ token: Data, for activity: Activity<TrainActivityAttributes>) {
    let tokenString = token.map { String(format: "%02x", $0) }.joined()
    
    // Store with activity ID for better tracking
    UserDefaults.standard.set([
        "token": tokenString,
        "activityId": activity.id,
        "timestamp": Date().timeIntervalSince1970
    ], forKey: "LiveActivity_\(activity.id)")
}
```

## 8. Content State Validation

### Add Comprehensive Validation
```swift
func validateContentState(_ state: TrainActivityContentState) throws {
    // Existing validation...
    
    // Add journey progress validation
    if state.journeyProgress < 0 || state.journeyProgress > 100 {
        throw ValidationError.invalidJourneyProgress
    }
    
    // Validate next stop info
    if let nextStop = state.nextStop {
        if nextStop.minutesAway < 0 {
            throw ValidationError.invalidMinutesAway
        }
    }
    
    // Validate status consistency
    if state.status == "ARRIVED" && state.journeyProgress < 100 {
        throw ValidationError.inconsistentStatus
    }
}
```

## 9. Priority-Based Update Queue

### Backend Implementation
```python
class PriorityUpdateQueue:
    def __init__(self):
        self.high_priority = []  # Track assignments, boarding
        self.medium_priority = []  # Stop departures, approaching
        self.low_priority = []  # Status changes, delays
    
    async def process_updates(self):
        # Process high priority first
        for update in self.high_priority:
            await self._send_update(update)
        
        # Then medium and low
        # ... implementation
```

## 10. Monitoring and Analytics

### Add Metrics Collection
```swift
// iOS - Track notification delivery
struct NotificationMetrics {
    static func recordDelivery(type: String, success: Bool) {
        // Log to backend for monitoring
        Task {
            await APIService.shared.logMetric(
                event: "notification_delivered",
                properties: [
                    "type": type,
                    "success": success,
                    "timestamp": Date().timeIntervalSince1970
                ]
            )
        }
    }
}
```

### Backend Metrics
```python
# Add to push_notification.py
async def log_notification_metric(
    event_type: str,
    success: bool,
    train_id: str,
    error: Optional[str] = None
):
    metric_data = {
        "event_type": event_type,
        "success": success,
        "train_id": train_id,
        "timestamp": datetime.utcnow(),
        "error": error
    }
    # Log to monitoring system
```

## 11. Testing Improvements

### Add Push Notification Testing
```swift
// Debug menu in app
struct PushNotificationDebugView: View {
    var body: some View {
        VStack {
            Button("Test Stop Departure") {
                simulatePushNotification(type: .stopDeparture)
            }
            
            Button("Test Approaching Stop") {
                simulatePushNotification(type: .approachingStop)
            }
            
            Button("Test Journey Complete") {
                simulatePushNotification(type: .journeyComplete)
            }
        }
    }
    
    func simulatePushNotification(type: NotificationType) {
        // Simulate push payload
        let payload = createTestPayload(for: type)
        Task {
            await TrackRatApp.shared.handleLiveActivityPushUpdate(payload)
        }
    }
}
```

## 12. Migration Strategy

### Phased Rollout
1. **Phase 1**: Deploy backend with new push system (keep old local notifications)
2. **Phase 2**: iOS update with improved handling (gracefully handle both)
3. **Phase 3**: Remove local notification code after verification
4. **Phase 4**: Add advanced features (journey complete, etc.)

### Feature Flags
```swift
struct FeatureFlags {
    static let useRemoteNotifications = true
    static let enableJourneyCompleteAlert = false
    static let enableBatchUpdates = false
}
```

## Summary of Key Improvements

1. **Stale Date Support**: Prevents outdated Live Activities
2. **Dismissal Policies**: Clean up completed journeys
3. **Token Validation**: Ensures updates go to correct activity
4. **Batch Processing**: Reduces battery impact
5. **Priority Queue**: Ensures important updates arrive first
6. **Metrics & Monitoring**: Track delivery success
7. **Journey Completion**: New notification type for arrivals
8. **Content Validation**: Prevents invalid states
9. **Debug Tools**: Easier testing and verification
10. **Phased Migration**: Safe rollout strategy

These improvements will ensure the system follows iOS best practices and provides a robust, reliable notification experience even when the app is terminated.