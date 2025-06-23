# TrackRat Notifications & Live Activity Update Plan

## Overview

This document describes the comprehensive push notification and Live Activity update system implemented for TrackRat, enabling real-time train notifications that work even when the iOS app is completely terminated.

## Architecture Summary

The system consists of three main components:

1. **iOS App**: Enhanced Live Activities with Dynamic Island support and push notification registration
2. **Backend Service**: APNS push notification service with dual notification delivery
3. **Database Infrastructure**: Token storage and relationship management

## What Has Been Implemented

### 🍎 iOS App Enhancements

#### Dynamic Island & Live Activities
- **Enhanced Live Activity Creation**: 
  - Added `staleDate` (2-minute freshness window)
  - Implemented relevance scoring (0-100 based on train status)
  - Enabled `pushType: .token` for server-driven updates
  
- **AlertConfiguration System**:
  - `TrainAlertType` enum with 6 alert types
  - Dynamic Island expansion triggers for track assignments, boarding, departures
  - Context-specific alert messages with emojis
  - Enhanced haptic feedback (heavy for track/boarding, medium for departures)

- **Smart Change Detection**:
  - Track assignment detection (highest priority)
  - Boarding status changes
  - Train departure detection  
  - Approaching destination alerts (within 5 minutes)
  - Significant delay changes (≥5 minutes)

#### Push Notification Infrastructure
- **Device Token Registration**:
  - Automatic APNS registration on app launch
  - Device token storage in AppDelegate
  - Backend registration via `/api/device-tokens/`
  
- **Live Activity Token Linking**:
  - Device token automatically linked to Live Activity tokens
  - Enables dual notification delivery (Live Activity + regular notifications)
  - Silent push notification handling for background updates

### 🖥️ Backend Service Enhancements

#### Database Models & Migration
```sql
-- New tables added via migration system
CREATE TABLE device_tokens (
    id SERIAL PRIMARY KEY,
    device_token VARCHAR(255) NOT NULL UNIQUE,
    platform VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE live_activity_tokens (
    id SERIAL PRIMARY KEY,
    push_token VARCHAR(255) NOT NULL,
    train_id VARCHAR(20) NOT NULL,
    device_token_id INTEGER REFERENCES device_tokens(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_notification_sent TIMESTAMP,
    last_update_sent TIMESTAMP,
    activity_started_at TIMESTAMP,
    activity_ended_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_token_train UNIQUE (push_token, train_id)
);
```

#### API Endpoints
- **`POST /api/device-tokens/`**: Register device for push notifications
- **`POST /api/live-activities/register`**: Register Live Activity with optional device linking
- **`GET /api/live-activities/active`**: Get all active Live Activities
- **`DELETE /api/live-activities/{token_id}`**: Deactivate Live Activity

#### APNS Push Notification Service
```python
class APNSPushService:
    async def send_train_notifications(
        live_activity_token: LiveActivityToken,
        train_data: Dict[str, Any],
        alert_type: Optional[AlertType] = None
    ) -> Dict[str, bool]:
        # Sends BOTH Live Activity update AND regular notification
```

**Dual Notification System**:
- **Live Activity Updates**: Update widget content + trigger Dynamic Island expansions
- **Regular Notifications**: Show notification banners that work when app is terminated
- **Silent Updates**: Keep Live Activity data fresh without notification spam

**Alert Types Implemented**:
1. `TRACK_ASSIGNED`: "Track Assigned! 🚋" - Track 13 - Get Ready to Board
2. `BOARDING`: "Time to Board! 🚆" - Track 13 - All Aboard!
3. `DEPARTED`: "Train Departed 🛤️" - Left Station - Journey Started
4. `APPROACHING`: "Approaching Stop 🎯" - Arriving in 3 minutes
5. `DELAY_UPDATE`: "Delay Update ⏰" - Now 10 minutes behind schedule
6. `STATUS_CHANGE`: "Status Update 📢" - Train status changed

#### Integration with Data Collection
- **Automated Processing**: Train data collection triggers notification checks
- **Smart Filtering**: Only processes trains with active Live Activities
- **Rate Limiting**: 100ms minimum interval between APNS requests
- **Error Handling**: Graceful degradation when notifications fail

## Current Status

### ✅ What Works Now (In Development)
1. **Complete iOS Implementation**: All code changes deployed
2. **Backend Infrastructure**: Database models, API endpoints, push service
3. **Dual Notification System**: Both Live Activity and regular notifications
4. **Smart Change Detection**: Tracks all significant train events
5. **Token Management**: Device and Live Activity token registration/linking
6. **Database Migration**: Automated table creation

### ✅ What Should Work With Production Deployment
1. **Notifications When App Terminated**: All train alerts delivered via server push
2. **Dynamic Island Expansions**: Track assignments, boarding, departures trigger expansions
3. **Live Activity Updates**: Real-time train data updates every 60-120 seconds
4. **Regular Notification Banners**: Traditional iOS notifications for all events
5. **Battery Efficient**: No background processing in app, all server-driven

### ✅ What Is Now Ready for Production 
1. **APNS Configuration**: Production Apple Push Notification setup complete with Auth Key
2. **APNS HTTP/2 Client**: Real implementation with JWT authentication and error handling
3. **Database Migration**: Runs automatically on backend startup via `trackcast update-schema`

## Activation Checklist

### 1. Production APNS Setup ✅ COMPLETED
```bash
# ✅ COMPLETED - Auth Key method configured:
✓ Team ID: D5RZZ55J9R
✓ Key ID: 4WC3F645FR  
✓ Auth Key: AuthKey_4WC3F645FR.p8
✓ Bundle ID: net.trackrat.TrackRat
✓ JWT token generation working
```

### 2. Backend Deployment ✅ READY
```bash
# ✅ Database migration: Runs automatically on startup
# ✅ Environment variables: Configured in Dockerfile
# ✅ APNS endpoints: /api/device-tokens/, /api/live-activities/register

# Ready to deploy with configured environment:
APNS_TEAM_ID=D5RZZ55J9R
APNS_KEY_ID=4WC3F645FR
APNS_AUTH_KEY_PATH=/app/certs/AuthKey_4WC3F645FR.p8
APNS_BUNDLE_ID=net.trackrat.TrackRat
TRACKCAST_ENV=dev  # or "prod" for production
```

### 3. iOS App Deployment
- Deploy iOS app with notification enhancements
- Ensure push notification capability is enabled in App Store Connect
- Test Live Activity creation and device token registration

### 4. APNS HTTP/2 Client Implementation ✅ COMPLETED
The production APNS HTTP/2 client has been implemented with full features:

```python
# ✅ IMPLEMENTED in trackcast/services/push_notification.py
class APNSPushService:
    ✅ JWT authentication with auto-refresh
    ✅ HTTP/2 client with proper APNS headers
    ✅ Environment-based endpoint selection (sandbox/production)
    ✅ Error handling for all APNS response codes (200, 400, 403, 410)
    ✅ Rate limiting (100ms between requests)
    ✅ Mock mode fallback when certificates missing
    ✅ Certificate-based authentication alternative
```

## Expected User Experience

### When App is Active/Backgrounded (Current + Enhanced)
- ✅ All existing local notifications continue to work
- ✅ Enhanced Live Activities with Dynamic Island expansions
- ✅ Improved haptic feedback for different events
- ✅ Real-time progress tracking and journey visualization

### When App is Completely Terminated (New Capability)
- ✅ **Track Assignment**: "Track Assigned! 🚋" notification + Dynamic Island expansion
- ✅ **Boarding Alerts**: "Time to Board! 🚆" notification + Dynamic Island expansion  
- ✅ **Departure Notifications**: "Train Departed 🛤️" notification + Dynamic Island expansion
- ✅ **Approaching Destination**: "Approaching Stop 🎯" notification + Dynamic Island expansion
- ✅ **Delay Updates**: "Delay Update ⏰" notification when delays change significantly
- ✅ **Live Activity Updates**: Widget stays current with latest train data

### Dynamic Island Behavior
- **Compact View**: Shows train number and current status
- **Expanded View**: Full journey progress with next stop information
- **Alert Expansions**: Automatic expansion for track assignments, boarding, departures
- **App Icon Display**: TrackRat icon visible during active Live Activities

## Performance & Reliability

### Rate Limiting
- **APNS Requests**: 100ms minimum interval between requests
- **Batch Processing**: Multiple notifications grouped per data collection cycle
- **Error Recovery**: Failed notifications don't block subsequent updates

### Database Efficiency
- **Eager Loading**: Device relationships loaded with Live Activity tokens
- **Active Filtering**: Only processes trains with active Live Activities  
- **Timestamp Tracking**: Last notification times prevent duplicate alerts

### Battery Impact
- **No Background Processing**: iOS app does zero background work
- **Server-Driven**: All updates originate from backend data collection
- **Smart Filtering**: Only sends notifications for significant changes

## Known Limitations

### Current Implementation Gaps
1. ~~**Mock APNS Client**: Logs payloads but doesn't send to Apple servers~~ ✅ RESOLVED
2. **Certificate Management**: No automated certificate renewal (Auth Keys don't expire)
3. **Notification Deduplication**: May send duplicate alerts in edge cases
4. **User Preferences**: No per-user notification type filtering

### iOS Platform Constraints
1. **APNS Delivery**: Apple controls delivery timing and reliability
2. **Device Limits**: iOS may throttle notifications from single app
3. **Live Activity Limits**: Maximum 8 concurrent Live Activities per device
4. **Background Restrictions**: Cannot guarantee notification timing

## Future Roadmap

### Phase 1: Production Deployment (Immediate)
- [x] Implement actual APNS HTTP/2 client with certificates
- [x] Deploy backend changes to production (ready - just needs deployment)
- [x] Run database migrations (automatic on startup)
- [ ] Deploy iOS app with notification features
- [ ] Monitor notification delivery rates and errors

### Phase 2: Enhanced Features (Short Term)
- [ ] **Interactive Notifications**: Quick actions from notification banners
  ```swift
  // Add notification categories for "View Train", "End Tracking"
  let viewAction = UNNotificationAction(identifier: "VIEW_TRAIN", title: "View Train")
  let endAction = UNNotificationAction(identifier: "END_TRACKING", title: "Stop Tracking")
  ```

- [ ] **User Preferences**: Notification type filtering per user
  ```python
  # Add user_preferences table
  CREATE TABLE user_notification_preferences (
      device_token_id INTEGER REFERENCES device_tokens(id),
      track_assignments BOOLEAN DEFAULT TRUE,
      boarding_alerts BOOLEAN DEFAULT TRUE,
      departure_alerts BOOLEAN DEFAULT TRUE,
      delay_updates BOOLEAN DEFAULT TRUE
  );
  ```

- [ ] **Notification Grouping**: Group multiple train notifications
- [ ] **Rich Notifications**: Include train route maps or photos

### Phase 3: Advanced Features (Medium Term)
- [ ] **WebSocket Integration**: Real-time updates without polling
- [ ] **Machine Learning**: Predict optimal notification timing
- [ ] **Geographic Awareness**: Location-based notification filtering
- [ ] **Multi-Device Sync**: Coordinate notifications across devices

### Phase 4: Platform Expansion (Long Term)  
- [ ] **Apple Watch**: Companion app with notification mirroring
- [ ] **Android Support**: Cross-platform notification system
- [ ] **Web Push**: Browser-based notifications for web app
- [ ] **CarPlay Integration**: In-car notification display

## Monitoring & Metrics

### Key Metrics to Track
1. **Notification Delivery Rate**: % of notifications successfully sent to APNS
2. **Live Activity Update Success**: % of Live Activity updates delivered
3. **User Engagement**: Tap-through rates on notifications
4. **Error Rates**: Failed registrations, expired tokens, APNS errors
5. **Performance**: Notification processing latency, database query times

### Recommended Dashboards
```python
# Add to existing metrics system
NOTIFICATION_DELIVERY_RATE = Counter('notifications_delivered_total', ['type', 'status'])
LIVE_ACTIVITY_UPDATE_RATE = Counter('live_activity_updates_total', ['status'])
NOTIFICATION_PROCESSING_TIME = Histogram('notification_processing_seconds')
APNS_ERROR_RATE = Counter('apns_errors_total', ['error_type'])
```

### Health Checks
- **Device Token Registration**: Verify new tokens can be stored
- **Live Activity Creation**: Test end-to-end Live Activity flow
- **APNS Connectivity**: Validate certificates and connection to Apple
- **Database Performance**: Monitor notification query performance

## Security Considerations

### Token Security
- **Device Tokens**: Treated as sensitive data, limited access
- **APNS Certificates**: Secure storage, regular rotation
- **Database Encryption**: Consider encrypting push tokens at rest

### Privacy Protection
- **No User Tracking**: System only stores device tokens, no personal data
- **Token Expiration**: Automatic cleanup of expired/inactive tokens
- **Opt-out Support**: Users can disable notifications in iOS settings

### Rate Limiting Protection
- **Per-Device Limits**: Prevent notification spam to individual devices
- **System-Wide Limits**: Protect against APNS quota exhaustion
- **Backoff Strategy**: Exponential backoff for failed deliveries

## Conclusion

The TrackRat notification system provides a comprehensive solution for real-time train updates that work regardless of app state. The implementation balances rich functionality with battery efficiency, leveraging server-side intelligence to deliver the right notifications at the right time.

Key benefits:
- **Zero Background Processing**: No battery drain from iOS app
- **Rich Interactions**: Dynamic Island expansions and haptic feedback
- **Reliable Delivery**: Server-driven push notifications work when app is terminated
- **Smart Filtering**: Only sends notifications for significant events
- **Scalable Architecture**: Supports thousands of concurrent Live Activities

The system is ready for production deployment pending APNS certificate configuration and represents a significant enhancement to the TrackRat user experience.