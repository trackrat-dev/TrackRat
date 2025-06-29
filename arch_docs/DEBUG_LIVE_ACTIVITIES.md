# Debugging Live Activities

## 1. Backend Debug Logging

Add this to `push_notification.py` after line 277:

```python
# Debug logging for Live Activity payload
logger.info(f"🔍 Live Activity Payload Debug:")
logger.info(f"  Push Token: {live_activity_token.push_token[:12]}...")
logger.info(f"  Train ID: {train_data.get('train_id')}")
logger.info(f"  Content State: {json.dumps(payload['aps']['content-state'], indent=2)}")
```

## 2. iOS Debug Logging

In `TrackRatApp.swift`, add after line 163:

```swift
print("📱 Raw push notification payload:")
print(userInfo)

// Try to extract and print content-state
if let aps = userInfo["aps"] as? [String: Any],
   let contentState = aps["content-state"] as? [String: Any] {
    print("📱 Content-state received:")
    for (key, value) in contentState {
        print("  \(key): \(value)")
    }
}
```

## 3. Test Push Notification

Create a test endpoint to send a push notification:

```python
@router.post("/test-live-activity/{train_id}")
async def test_live_activity(train_id: str, db: Session = Depends(get_db)):
    """Test Live Activity update for a specific train."""
    
    # Get active Live Activity token
    token = db.query(LiveActivityToken).filter(
        LiveActivityToken.train_id == train_id,
        LiveActivityToken.is_active == True
    ).first()
    
    if not token:
        raise HTTPException(404, "No active Live Activity found")
    
    # Create test data
    test_data = {
        "train_id": train_id,
        "status_v2": "BOARDING",
        "track": "12",
        "delay_minutes": 0,
        "journey_percent": 50,
        "has_status_changed": True,
    }
    
    # Send update
    push_service = APNSPushService()
    success = await push_service.send_live_activity_update(
        token.push_token,
        test_data,
        AlertType.BOARDING
    )
    
    return {"success": success, "token_preview": token.push_token[:12]}
```

## 4. Common Issues to Check

### A. Push Token Format
- iOS sends push token as hex string
- Backend should store and use it as-is
- Check token length (should be 64+ characters)

### B. Bundle ID Configuration
- Backend must use: `net.trackrat.TrackRat.push-type.liveactivity`
- Check APNS_BUNDLE_ID environment variable

### C. APNS Environment
- Development: `api.sandbox.push.apple.com`
- Production: `api.push.apple.com`
- Must match iOS build type

### D. Database Issues
Check if Live Activity tokens are being saved:
```sql
SELECT * FROM live_activity_tokens 
WHERE train_id = 'YOUR_TRAIN_ID' 
AND is_active = true;
```

## 5. Manual APNS Test

Test APNS directly with curl:

```bash
# For JWT auth
curl -v \
  -H "authorization: bearer YOUR_JWT_TOKEN" \
  -H "apns-topic: net.trackrat.TrackRat.push-type.liveactivity" \
  -H "apns-push-type: liveactivity" \
  -H "apns-priority: 10" \
  -H "content-type: application/json" \
  -d '{
    "aps": {
      "timestamp": 1234567890,
      "event": "update",
      "content-state": {
        "trainNumber": "TEST123",
        "statusV2": "BOARDING",
        "track": "12",
        "delayMinutes": 0,
        "journeyProgress": 0.5,
        "lastUpdated": 1234567890,
        "hasStatusChanged": true
      }
    }
  }' \
  https://api.sandbox.push.apple.com/3/device/YOUR_PUSH_TOKEN
```

## 6. iOS ContentState Validation

In `LiveActivityService.swift`, add validation logging:

```swift
func validateContentState(_ state: TrainActivityContentState) throws {
    print("🔍 Validating ContentState:")
    print("  trainNumber: \(state.trainNumber)")
    print("  statusV2: \(state.statusV2)")
    print("  track: \(state.track ?? "nil")")
    print("  journeyProgress: \(state.journeyProgress)")
    print("  lastUpdated: \(state.lastUpdated)")
    
    // Existing validation...
}
```

## 7. Check Activity Updates

Monitor if updates are received in `LiveActivityService.swift`:

```swift
Task {
    for await update in activity.contentUpdates {
        print("📱 Live Activity content update received!")
        print("  New state: \(update)")
    }
}
```

## Expected Flow

1. iOS app starts Live Activity → Gets push token
2. iOS registers token with backend → `/live-activities/register`
3. Backend stores token in database
4. When train updates, backend sends push to token
5. iOS receives push → Updates Live Activity display

## Troubleshooting Checklist

- [ ] Live Activity push token is being obtained in iOS
- [ ] Token is successfully registered with backend
- [ ] Backend can find active tokens for train
- [ ] APNS configuration is correct (auth key, bundle ID)
- [ ] Push payload has correct structure (camelCase fields)
- [ ] iOS receives push notification
- [ ] ContentState can be parsed successfully
- [ ] Live Activity UI updates with new data