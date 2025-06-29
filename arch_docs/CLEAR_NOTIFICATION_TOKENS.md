# Clearing Notification Tokens from TrackRat System

## Backend Database Cleanup

### 1. Connect to Your Database

First, connect to your PostgreSQL database. If using Cloud SQL:

```bash
# Local connection
psql -h localhost -U your_username -d trackcast

# Cloud SQL connection
gcloud sql connect trackcast-instance --user=postgres --database=trackcast
```

### 2. Clear All Notification Tokens

Run these SQL commands to clear all notification-related data:

```sql
-- First, check what data exists
SELECT COUNT(*) FROM device_tokens;
SELECT COUNT(*) FROM live_activity_tokens;

-- Clear Live Activity tokens (this is the main table for Live Activities)
DELETE FROM live_activity_tokens;

-- Clear device tokens
DELETE FROM device_tokens;

-- Verify cleanup
SELECT COUNT(*) FROM device_tokens;
SELECT COUNT(*) FROM live_activity_tokens;

-- Optional: Reset auto-increment IDs if desired
ALTER SEQUENCE device_tokens_id_seq RESTART WITH 1;
ALTER SEQUENCE live_activity_tokens_id_seq RESTART WITH 1;
```

### 3. Alternative: Soft Reset (Mark as Inactive)

If you want to preserve history but deactivate all tokens:

```sql
-- Deactivate all Live Activity tokens
UPDATE live_activity_tokens SET is_active = false;

-- You can also add a deactivated timestamp if the column exists
UPDATE live_activity_tokens 
SET is_active = false, 
    updated_at = CURRENT_TIMESTAMP;
```

## iOS App Cleanup

### 1. End All Active Live Activities

Add this temporary function to your iOS app (e.g., in a debug menu):

```swift
// Add to LiveActivityService.swift
@MainActor
func endAllActivities() async {
    print("🧹 Ending all active Live Activities...")
    
    // End current tracked activity
    if let activity = currentActivity {
        await endActivity()
    }
    
    // End any other activities that might be running
    for activity in Activity<TrainActivityAttributes>.activities {
        let finalState = TrainActivityContentState(
            statusV2: "ENDED",
            statusLocation: nil,
            track: activity.attributes.track,
            delayMinutes: nil,
            currentLocation: .notDeparted,
            nextStop: nil,
            journeyProgress: 1.0,
            destinationETA: nil,
            trackRatPrediction: nil,
            lastUpdated: Date(),
            hasStatusChanged: false
        )
        
        let finalContent = ActivityContent(
            state: finalState,
            staleDate: Date()
        )
        
        await activity.end(finalContent, dismissalPolicy: .immediate)
    }
    
    // Clear stored state
    currentActivity = nil
    isActivityActive = false
    lastKnownState = nil
    lastKnownStops = []
    
    print("✅ All Live Activities ended")
}
```

### 2. Clear iOS UserDefaults (Optional)

If you store any token data in UserDefaults:

```swift
// Add to debug menu or settings
func clearStoredTokens() {
    // Clear any stored device token
    UserDefaults.standard.removeObject(forKey: "deviceToken")
    
    // Clear any Live Activity related data
    let defaults = UserDefaults.standard
    let keys = defaults.dictionaryRepresentation().keys
    
    for key in keys where key.starts(with: "LiveActivity_") {
        defaults.removeObject(forKey: key)
    }
    
    defaults.synchronize()
    print("✅ Cleared all stored tokens from UserDefaults")
}
```

### 3. Re-register for Push Notifications

Force re-registration:

```swift
// In TrackRatApp or AppDelegate
func reregisterForNotifications() {
    UIApplication.shared.unregisterForRemoteNotifications()
    
    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
        UIApplication.shared.registerForRemoteNotifications()
    }
}
```

## Backend CLI Commands

### Option 1: Create a CLI Command

Add this to `trackcast/cli.py`:

```python
@cli.command()
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def clear_notification_tokens(confirm):
    """Clear all notification tokens from the database."""
    if not confirm:
        click.confirm(
            "⚠️  This will delete ALL device and Live Activity tokens. Continue?", 
            abort=True
        )
    
    logger.info("🧹 Clearing all notification tokens...")
    
    with get_db_session() as session:
        try:
            # Count tokens before deletion
            device_count = session.query(DeviceToken).count()
            live_activity_count = session.query(LiveActivityToken).count()
            
            logger.info(f"Found {device_count} device tokens and {live_activity_count} Live Activity tokens")
            
            # Delete all tokens
            session.query(LiveActivityToken).delete()
            session.query(DeviceToken).delete()
            
            session.commit()
            
            logger.info("✅ Successfully cleared all notification tokens")
            click.echo(f"Deleted {device_count} device tokens and {live_activity_count} Live Activity tokens")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Failed to clear tokens: {e}")
            click.echo(f"Error: {e}", err=True)
            raise
```

Then run:
```bash
trackcast clear-notification-tokens --confirm
```

### Option 2: Use Python Script

Create a standalone script:

```python
#!/usr/bin/env python3
"""Clear all notification tokens from TrackRat database."""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add trackcast to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trackcast.db.models import DeviceToken, LiveActivityToken
from trackcast.config import settings

def clear_tokens():
    """Clear all notification tokens."""
    engine = create_engine(settings.database.url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Count tokens
        device_count = session.query(DeviceToken).count()
        live_count = session.query(LiveActivityToken).count()
        
        print(f"Found {device_count} device tokens and {live_count} Live Activity tokens")
        
        # Confirm
        response = input("Delete all tokens? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled")
            return
        
        # Delete
        session.query(LiveActivityToken).delete()
        session.query(DeviceToken).delete()
        session.commit()
        
        print(f"✅ Deleted {device_count} device tokens and {live_count} Live Activity tokens")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    clear_tokens()
```

## Complete Reset Procedure

### 1. Stop All Services
```bash
# Stop the scheduler/data collector
# (depends on your deployment method)
```

### 2. Clear Backend Tokens
```bash
# Using SQL
psql -d trackcast -c "DELETE FROM live_activity_tokens; DELETE FROM device_tokens;"

# Or using CLI command if you added it
trackcast clear-notification-tokens --confirm
```

### 3. Clear iOS App Data
1. Open the app
2. End all active Live Activities (use debug function above)
3. Delete and reinstall the app (nuclear option)
   - OR clear app data in Settings > General > iPhone Storage > TrackRat

### 4. Restart Services
```bash
# Start the scheduler/data collector again
trackcast start-scheduler
```

### 5. Test Fresh Registration
1. Start tracking a train in the iOS app
2. Verify new token is registered:

```sql
-- Check new registrations
SELECT * FROM live_activity_tokens ORDER BY created_at DESC LIMIT 5;
```

## Monitoring Token Registration

Add this query to monitor token registration:

```sql
-- View recent token registrations
SELECT 
    lat.id,
    lat.train_id,
    lat.push_token,
    lat.is_active,
    lat.created_at,
    lat.last_update_sent,
    dt.device_token
FROM live_activity_tokens lat
LEFT JOIN device_tokens dt ON lat.device_id = dt.id
ORDER BY lat.created_at DESC
LIMIT 10;
```

## Debugging Tips

1. **Check APNS Environment**: Make sure backend APNS environment matches iOS build
   - Development builds → Sandbox APNS
   - TestFlight/App Store → Production APNS

2. **Verify Token Format**: Push tokens should be 64+ character hex strings

3. **Monitor Logs**: Watch backend logs during registration:
   ```bash
   tail -f trackcast.log | grep -E "(Live Activity|Device token|APNS)"
   ```

4. **Test Registration**: After clearing, start one Live Activity and verify:
   - Token appears in database
   - Backend can send updates to it
   - iOS receives the updates

This complete reset ensures you start with a clean slate for notification tokens.