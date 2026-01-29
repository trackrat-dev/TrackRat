# NJT Cancellation Detection - Design Proposal

## Problem Statement

When NJ Transit cancels a train, the iOS app doesn't show it as cancelled. Instead, the train either:
1. Silently disappears from the departure list, or
2. Continues to show as "scheduled" with no indication it won't run

Users have no way to know a train was cancelled until they're at the station.

## Root Cause Analysis

### Current State

1. **NJT provides cancellation info in two places:**
   - `STATIONMSGS` array in `getDepartureVisionData` response (banner alerts)
   - `STOP_STATUS == "Cancelled"` for all stops in `getTrainStopList` response

2. **Backend only uses `getTrainSchedule`** (for discovery) and `getTrainStopList` (for journey details)
   - Neither of these surfaces the `STATIONMSGS` banner alerts
   - `STOP_STATUS` detection exists but only triggers after a journey is collected

3. **Cancelled trains disappear from train lists** before collection happens
   - A cancelled 6:17 PM train won't appear in the 6:00 PM API response
   - The system never knows it was cancelled vs. just not discovered yet

4. **Secondary bug:** When cancellation IS detected via STOP_STATUS, the code sets both `is_cancelled=True` AND `is_completed=True`, causing the train to be filtered out of departures anyway

## Design Goals

1. **Detect cancellations as early as possible** - before users are affected
2. **Show cancelled trains clearly** - don't hide them from departure lists
3. **Provide context** - show cancellation reason and alternatives when available
4. **Keep it simple** - minimal code changes, no new tables, foolproof logic
5. **Graceful degradation** - if parsing fails, don't break anything

## Proposed Solution

### Overview

Parse cancellation alerts from `STATIONMSGS` during the discovery/refresh cycle and mark affected journeys as cancelled. This catches cancellations early (often announced 30+ minutes before departure).

### Component 1: Add `getDepartureVisionData` API Method

Add a new client method to fetch departure vision data which includes STATIONMSGS:

```python
# collectors/njt/client.py

async def get_departure_vision_data(self, station_code: str) -> dict[str, Any]:
    """Get departure vision data including station messages/alerts.

    This endpoint includes STATIONMSGS with cancellation announcements.
    Used to detect cancelled trains before they disappear from schedules.
    """
    response = await self._make_request(
        "TrainData/getDepartureVisionData", {"station": station_code}
    )
    return response or {"STATION": {"ITEMS": [], "STATIONMSGS": []}}
```

### Component 2: Cancellation Alert Parser

Create a focused parser that extracts cancellation info from STATIONMSGS:

```python
# collectors/njt/cancellation_parser.py

import re
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CancellationAlert:
    """Parsed cancellation information from NJT station message."""
    train_id: str
    line_code: str | None  # e.g., "NEC", "NJCL", "M&E"
    scheduled_time: str | None  # e.g., "7:43 PM"
    reason: str | None  # e.g., "equipment availability"
    alternative_train_id: str | None  # e.g., "3883"
    raw_message: str

# Pattern to extract train cancellation info
# Examples:
#   "NEC train #3735, the 7:43 PM departure from PSNY... is cancelled due to equipment availability"
#   "NJCL train #3515, the 6:29 PM departure from PSNY... is cancelled"
CANCELLATION_PATTERN = re.compile(
    r"(?P<line>\w+)\s+train\s*#?(?P<train_id>\d+)"  # Line and train ID
    r".*?(?:the\s+)?(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM))?"  # Optional time
    r".*?(?:is|has been)\s+cancell?ed"  # Cancellation phrase
    r"(?:\s+due\s+to\s+(?P<reason>[^.]+))?"  # Optional reason
    r".*?(?:take\s+train\s*#?(?P<alt>\d+))?"  # Optional alternative
    , re.IGNORECASE | re.DOTALL
)

def parse_cancellation_alerts(station_messages: list[dict]) -> list[CancellationAlert]:
    """Parse STATIONMSGS array for cancellation alerts.

    Args:
        station_messages: List of message dicts from STATIONMSGS

    Returns:
        List of parsed CancellationAlert objects
    """
    alerts = []

    for msg in station_messages:
        msg_text = msg.get("MSG_TEXT", "")

        # Skip non-cancellation messages
        if "cancell" not in msg_text.lower():
            continue

        match = CANCELLATION_PATTERN.search(msg_text)
        if match:
            alerts.append(CancellationAlert(
                train_id=match.group("train_id"),
                line_code=_normalize_line_code(match.group("line")),
                scheduled_time=match.group("time"),
                reason=match.group("reason").strip() if match.group("reason") else None,
                alternative_train_id=match.group("alt"),
                raw_message=msg_text,
            ))
        else:
            # Log unparseable cancellation for monitoring
            logger.warning(
                "unparseable_cancellation_message",
                message=msg_text[:200],
            )

    return alerts

def _normalize_line_code(line: str | None) -> str | None:
    """Normalize line names to codes."""
    if not line:
        return None
    line = line.upper()
    mapping = {
        "NEC": "NE",
        "NJCL": "NC",
        "M&E": "ME",
        "MORRIS": "ME",
        "RARITAN": "RV",
        "BERGEN": "BL",
        "MAIN": "ML",
        "PASCACK": "PV",
        "MONTCLAIR": "MC",
        "GLADSTONE": "GL",
    }
    return mapping.get(line, line[:2])
```

### Component 3: Cancellation Detection Service

A simple service that checks for cancellations and marks journeys:

```python
# services/cancellation.py

class CancellationDetectionService:
    """Detects and marks cancelled NJT trains from station alerts."""

    def __init__(self, client: NJTransitClient):
        self.client = client

    async def check_and_mark_cancellations(
        self,
        session: AsyncSession,
        station_code: str = "NY"
    ) -> list[str]:
        """Check for cancellation alerts and mark affected journeys.

        Args:
            session: Database session
            station_code: Station to check for alerts (default: NY Penn)

        Returns:
            List of train IDs that were marked as cancelled
        """
        # Fetch departure vision data with STATIONMSGS
        response = await self.client.get_departure_vision_data(station_code)
        station_data = response.get("STATION", {})
        messages = station_data.get("STATIONMSGS", [])

        if not messages:
            return []

        # Parse cancellation alerts
        alerts = parse_cancellation_alerts(messages)

        if not alerts:
            return []

        logger.info(
            "cancellation_alerts_found",
            count=len(alerts),
            train_ids=[a.train_id for a in alerts],
        )

        # Mark affected journeys
        marked_trains = []
        today = now_et().date()

        for alert in alerts:
            # Find matching journey
            journey = await session.scalar(
                select(TrainJourney)
                .where(
                    TrainJourney.train_id == alert.train_id,
                    TrainJourney.journey_date == today,
                    TrainJourney.data_source == "NJT",
                )
            )

            if journey and not journey.is_cancelled:
                journey.is_cancelled = True
                journey.cancellation_reason = alert.reason
                journey.last_updated_at = now_et()
                marked_trains.append(alert.train_id)

                logger.info(
                    "journey_marked_cancelled",
                    train_id=alert.train_id,
                    reason=alert.reason,
                    alternative=alert.alternative_train_id,
                )

            # If no journey exists yet, create a minimal cancelled record
            # so it shows up in departures as cancelled
            elif not journey:
                # We need scheduled_departure to show in departures
                # Try to parse from alert, or skip if we can't
                if alert.scheduled_time:
                    sched_dep = _parse_alert_time(alert.scheduled_time, today)
                    if sched_dep:
                        new_journey = TrainJourney(
                            train_id=alert.train_id,
                            journey_date=today,
                            line_code=alert.line_code or "NE",
                            line_name="Northeast Corridor Line",  # Default
                            destination="Unknown",
                            origin_station_code=station_code,
                            terminal_station_code="TR",  # Default
                            scheduled_departure=sched_dep,
                            data_source="NJT",
                            observation_type="OBSERVED",
                            is_cancelled=True,
                            cancellation_reason=alert.reason,
                            first_seen_at=now_et(),
                            last_updated_at=now_et(),
                        )
                        session.add(new_journey)
                        marked_trains.append(alert.train_id)

                        logger.info(
                            "cancelled_journey_created",
                            train_id=alert.train_id,
                            scheduled_departure=sched_dep.isoformat(),
                        )

        await session.commit()
        return marked_trains
```

### Component 4: Database Schema Update

Add a `cancellation_reason` field to TrainJourney:

```python
# models/database.py - TrainJourney class

cancellation_reason = Column(String(255), nullable=True)
```

Migration:
```sql
ALTER TABLE train_journeys ADD COLUMN cancellation_reason VARCHAR(255);
```

### Component 5: Fix the `is_completed` Bug

Remove `is_completed = True` from the cancellation logic in journey.py:

```python
# collectors/njt/journey.py - line 1656-1659
# BEFORE:
if all(stop.STOP_STATUS == "Cancelled" for stop in stops_data):
    journey.is_cancelled = True
    journey.is_completed = True  # REMOVE THIS LINE
    return "CANCELLED"

# AFTER:
if all(stop.STOP_STATUS == "Cancelled" for stop in stops_data):
    journey.is_cancelled = True
    # Don't set is_completed - cancelled trains should remain visible
    return "CANCELLED"
```

### Component 6: Update API Response Models

Add `cancellation_reason` to the API response:

```python
# models/api.py - TrainDeparture class

cancellation_reason: str | None = Field(
    default=None,
    description="Reason for cancellation if train is cancelled"
)
```

### Component 7: Integrate with Existing Flow

Option A (Recommended): **Check during JIT refresh**

Add cancellation check to the departure service's `_ensure_fresh_station_data`:

```python
# services/departure.py - _ensure_fresh_station_data method

async def _ensure_fresh_station_data(self, ...):
    # Existing refresh logic...

    # Also check for cancellation alerts (lightweight, uses cached response)
    await self.cancellation_service.check_and_mark_cancellations(
        session, station_code
    )
```

Option B: **Separate scheduled job**

Add a scheduled job that runs every 5 minutes:

```python
# services/scheduler.py

scheduler.add_job(
    run_cancellation_check,
    "interval",
    minutes=5,
    id="njt_cancellation_check",
)
```

**Recommendation:** Option A is simpler and ensures cancellations are detected whenever users are actively checking departures. No additional scheduler complexity.

### Component 8: iOS Changes (Out of Scope for Backend)

The iOS app should:
1. Check `is_cancelled` field on departures
2. Display cancelled trains with strikethrough or "CANCELLED" badge
3. Show `cancellation_reason` if available
4. Keep cancelled trains in the list (don't filter them out)

## Implementation Order

1. **Add database migration** for `cancellation_reason` column
2. **Fix `is_completed` bug** in journey.py (1 line change)
3. **Add `get_departure_vision_data`** client method
4. **Add cancellation parser** module
5. **Add cancellation detection service**
6. **Integrate with departure service** (Option A)
7. **Update API response models**
8. **Add tests**

## Testing Strategy

### Unit Tests
- Cancellation parser with various message formats
- Edge cases (partial cancellations, reinstated trains, duplicate alerts)
- Malformed messages don't crash parser

### Integration Tests
- End-to-end: mock STATIONMSGS → journey marked cancelled
- Cancelled journey appears in departures with `is_cancelled=true`
- Creating new cancelled journey when none exists

### Manual Testing
- Verify against live NJT data during peak hours
- Check that real cancellation alerts are detected
- Confirm iOS displays cancelled trains correctly

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| NJT changes message format | Regex is flexible; log unparseable messages for monitoring |
| Alert parsing fails | Log warning, don't crash; continue with other alerts |
| False positive (wrong train marked) | Match on train_id + line_code + date |
| Performance impact | getDepartureVisionData is lightweight; cache response |
| Duplicate alerts | Idempotent marking (check if already cancelled) |

## Metrics to Track

- `cancellation_alerts_parsed` - Count of alerts successfully parsed
- `cancellation_alerts_failed` - Count of unparseable alerts
- `journeys_marked_cancelled` - Count of journeys marked via alerts
- `cancelled_journeys_created` - Count of new cancelled journeys created

## Future Enhancements

1. **Parse alternative train suggestions** - Show "Take train #3883 instead"
2. **Proactive notifications** - Push notification when a tracked train is cancelled
3. **Historical cancellation data** - Track cancellation patterns by line/time
4. **Delay alerts** - Same STATIONMSGS contains delay info (e.g., "up to 35 minutes late")

## Summary

This design adds cancellation detection with minimal code changes:
- 1 new client method (~15 lines)
- 1 new parser module (~80 lines)
- 1 new service (~100 lines)
- 1 bug fix (1 line removal)
- 1 migration (1 column)
- API model updates (~5 lines)

Total: ~200 lines of new code, focused and testable.
