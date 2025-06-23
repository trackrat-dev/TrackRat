  1. Normal Push Notifications (Non-Live Activity)

  The app generates several types of standard push notifications that appear even when no Live Activity is running:

  Tracking Started Notification

  - Trigger: When user starts tracking a train via Live Activity
  - Content: "🚆 Now Tracking Train [number]" with route info
  - Purpose: Confirms Live Activity has started
  - Code: LiveActivityService.swift:826-844

  Status Change Notifications

  - Triggers: Major status changes (BOARDING, DELAYED, DEPARTED/EN_ROUTE)
  - Content: Status-specific messages with train number and destination
  - Examples:
    - "🚪 Train X is Boarding!"
    - "⏰ Train X Delayed"
    - "🚆 Train X Departed"
  - Code: LiveActivityService.swift:846-884

  Stop Departure Notifications

  - Trigger: When train departs any stop in user's journey
  - Content:
    - Origin departure: "🚂 Your train just left [station]"
    - Intermediate stops: "✅ Departed [station] - X stops remaining"
  - Includes: Next stop info and ETA
  - Code: LiveActivityService.swift:630-688

  Approaching Stop Notifications

  - Trigger: Within 3 minutes of arriving at any stop
  - Content:
    - Destination: "📍 Approaching Your Destination!"
    - Other stops: "📍 Approaching [station]"
  - Timing: Only sent once per stop, tracks sent notifications
  - Code: LiveActivityService.swift:742-787

  2. Live Activity Update Mechanisms

  Live Activities are updated through multiple mechanisms:

  Local Updates (Primary)

  - 30-second timer: Regular polling while app is active
  - Background refresh: Uses BGAppRefreshTask for background updates
  - Manual refresh: Pull-to-refresh or user-triggered updates
  - Code: LiveActivityService.swift:399-502

  Push Token Registration

  - Live Activity tokens: Registered separately from device tokens
  - Backend registration: Attempts to register with server but continues locally if fails
  - Dual token system: Both device token and Live Activity token
  - Code: LiveActivityService.swift:335-361

  Remote Push Updates (Secondary)

  - Silent push: Can trigger Live Activity updates
  - Payload: Contains live_activity_update: true flag
  - Processing: Fetches latest train data and updates activity
  - Code: TrackRatApp.swift:128-173

  3. Dynamic Island Implementation

  The Dynamic Island has three distinct views:

  Minimal View (When multiple activities are active)

  - Content: Just train icon (🚋)
  - Size: 32pt max width
  - Purpose: Minimal presence when other activities dominate

  Compact View (Default state)

  - Leading: Train icon (12pt)
  - Trailing: Priority display (67pt max):
    a. Track number if ≤3 chars ("T5")
    b. Next stop time if track unavailable
    c. Journey progress percentage as fallback
  - Smart prioritization: Shows most relevant info

  Expanded View (When tapped)

  - Leading section: Train number, track, status
  - Trailing section: Next stop details with time
  - Bottom section: Full journey progress bar with ETA
  - Interactive: Taps open app to train details

  4. Live Activity Content Updates

  Each update includes:

  Dynamic Island Alerts

  Special alerts trigger expanded Dynamic Island temporarily:
  - Track Assignment: "Track Assigned! 🚋" (highest priority)
  - Boarding: "Time to Board! 🚆"
  - Departure: "Train Departed 🛤️"
  - Approaching: "Approaching [station] 🎯"
  - Delays: "Delay Update ⏰" (only for 10+ minute changes)
  - Code: LiveActivityService.swift:8-83

  Relevance Scoring

  Updates include relevance scores (0-100) for system prioritization:
  - 100: Boarding status
  - 90: Track assigned
  - 85: Approaching station
  - 80: Recently departed
  - Base 50: Plus bonuses for progress and delays
  - Code: LiveActivityService.swift:105-140

  5. Haptic Feedback

  Haptic feedback accompanies important events:
  - Heavy impact: Track assignment, boarding
  - Medium impact: Departure, approaching
  - Light impact: Other updates, stop departures
  - Notification feedback: Success/warning for status changes

  6. Auto-End Logic

  Live Activities automatically end when:
  - Journey reaches 100% completion
  - Train arrives at destination
  - Train departed >1 hour past destination ETA
  - User manually stops tracking
  - Code: LiveActivityService.swift:920-939

  7. Permissions & Configuration

  Required Permissions

  - Push Notifications (optional but recommended)
  - Live Activities (required for tracking)
  - Background App Refresh (for updates)

  Info.plist Settings

  NSSupportsLiveActivities: true
  NSSupportsLiveActivitiesFrequentUpdates: true

  Entitlements

  - Push notifications capability
  - Background modes (fetch, remote notifications)

  8. State Management

  The LiveActivityService maintains:
  - Current activity reference
  - Last known status/stops/track
  - Sent notification tracking (prevents duplicates)
  - Update timers
  - Journey progress calculations

  9. Data Validation

  Extensive validation ensures reliability:
  - Train data completeness checks
  - Station code validation
  - Journey progress bounds (0-1)
  - ETA reasonableness (-1hr to +24hrs)
  - Dynamic Island text length limits
  - Code: LiveActivityService.swift:995-1067

  10. Lock Screen Widget

  The Lock Screen widget shows:
  - Train number and route
  - Current status badge
  - Track assignment (if available)
  - Journey progress bar with position indicator
  - Current location and next stop
  - TrackRat predictions
  - Real-time countdown timers

  This implementation provides a comprehensive, user-friendly experience that keeps passengers informed throughout their journey with appropriate
  notifications, live updates, and visual feedback.
