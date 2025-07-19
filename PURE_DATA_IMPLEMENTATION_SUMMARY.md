# Pure Data API Implementation Summary

## Overview
Successfully implemented a pure data approach to resolve the asymmetry between Amtrak and NJ Transit train status handling. The backend now provides objective facts while the iOS client performs context-aware status calculations based on the user's specific journey.

## Problem Solved
**Before**: Amtrak trains showed "BOARDING" when at any station, even before reaching the user's origin station, while NJ Transit trains behaved differently.

**After**: Both Amtrak and NJ Transit trains use the same pure data approach, with iOS calculating context-aware status based on the user's actual journey (origin → destination).

## Backend Changes

### API Models (`trackrat/models/api.py`)
- **Removed context-dependent fields**: `departed`, `status`, `status_details`
- **Added objective fields**:
  - `updated_arrival` / `updated_departure` - Projected times with delays
  - `raw_status` - Contains `amtrak_status` and `njt_departed_flag`
  - `has_departed_station` - Boolean fact about departure
- **Added train position tracking**:
  - `last_departed_station_code`
  - `at_station_code` 
  - `next_station_code`

### Database Schema (`trackrat/models/database.py`)
- **Updated JourneyStop model** with new fields:
  - `updated_arrival`, `updated_departure`
  - `raw_amtrak_status`, `raw_njt_departed_flag`
  - `has_departed_station`
- **Applied migration**: `20250716_1200-add_updated_times_and_raw_status_fields.py`

### Data Collection
#### Amtrak Collector (`trackrat/collectors/amtrak/journey.py`)
- **Fixed core asymmetry**: `has_departed_station = (amtrak_stop.status == "Departed")` 
- **Critical change**: "Station" status no longer marks trains as departed
- **Added raw data**: `raw_amtrak_status = amtrak_stop.status`

#### NJ Transit Collector (`trackrat/collectors/njt/journey.py`)
- **Objective departure tracking**: `has_departed_station = stop_data.DEPARTED == "YES"`
- **Raw flag preservation**: `raw_njt_departed_flag = stop_data.DEPARTED`

### API Endpoints (`trackrat/api/trains.py`)
- **Removed status interpretation logic**
- **Added train position calculation** using objective departure data
- **Updated response format** to include `updated_*` fields and raw status

### Services (`trackrat/services/departure.py`)
- **Eliminated context-dependent status calculations**
- **Added `_calculate_train_position`** method for objective position tracking
- **Simplified logic** by removing status interpretation

## iOS Changes

### Models (`ios/TrackRat/Models/TrainV2.swift`)
- **Added `JourneyContext`** struct for user's origin-destination context
- **Implemented context-aware methods**:
  - `calculateStatus(fromStationCode:)` - Status based on user's journey
  - `isBoarding(fromStationCode:)` - Boarding only at user's origin
  - `calculateJourneyProgress(from:to:)` - Progress for user's segment
- **Updated `StopV2`** model to use new backend fields:
  - `hasDepartedStation` instead of `departed`
  - `updatedArrival`/`updatedDeparture` for projected times
  - `rawStatus` containing Amtrak/NJT specific data

### UI Components
#### TrainListView (`ios/TrackRat/Views/Screens/TrainListView.swift`)
- **Updated `TrainCard`** to use `train.isBoarding(fromStationCode:)`
- **Fixed `StatusV2Badge`** to use context-aware status calculation
- **Eliminated false boarding indicators** for irrelevant stations

#### TrainDetailsView (`ios/TrackRat/Views/Screens/TrainDetailsView.swift`)
- **Context-aware status checks** throughout the UI
- **Updated Live Activity conditions** to use journey context
- **Enhanced boarding detection** specific to user's origin

### Services
#### LiveActivityService (`ios/TrackRat/Services/LiveActivityService.swift`)
- **Context-aware Live Activities**: Uses `JourneyContext` for accurate status
- **Immediate start capability**: Activities start when user begins tracking
- **Journey-specific progress**: Tracks user's origin-destination segment only
- **Updated helper methods** to use `hasDepartedStation` field

## Key Technical Improvements

### 1. Separation of Concerns
- **Backend**: Provides objective, factual data
- **iOS Client**: Interprets data based on user's journey context
- **Result**: Eliminates backend guesswork about user intent

### 2. Unified Data Model
- **Same logic for all data sources**: Amtrak and NJ Transit handled identically
- **Objective departure tracking**: Based on actual API responses
- **Consistent field naming**: `has_departed_station` across all sources

### 3. Enhanced Live Activities
- **User-specific tracking**: Only relevant to actual journey
- **Immediate activation**: Start tracking as soon as user follows train
- **Accurate notifications**: Boarding alerts only when at user's origin

## Benefits Achieved

### For Users
- **Consistent train behavior** across all data sources
- **Accurate boarding notifications** only when relevant
- **Immediate Live Activity tracking** when following trains
- **Better journey visualization** focused on user's actual trip

### For Developers
- **Simpler backend logic** with no context guessing
- **Centralized interpretation** in iOS client with full journey context
- **Easier debugging** with objective data fields
- **Better maintainability** through clear separation of concerns

## Database Migration
```sql
-- Added new objective fields
ALTER TABLE journey_stops ADD COLUMN updated_arrival TIMESTAMP;
ALTER TABLE journey_stops ADD COLUMN updated_departure TIMESTAMP;
ALTER TABLE journey_stops ADD COLUMN raw_amtrak_status TEXT;
ALTER TABLE journey_stops ADD COLUMN raw_njt_departed_flag TEXT;
ALTER TABLE journey_stops ADD COLUMN has_departed_station BOOLEAN;

-- Removed context-dependent fields
ALTER TABLE journey_stops DROP COLUMN departed;
ALTER TABLE journey_stops DROP COLUMN status;
ALTER TABLE journey_stops DROP COLUMN status_details;
```

## API Response Format Changes

### Before (Context-Dependent)
```json
{
  "station_code": "NY",
  "departed": true,  // ❌ Context-dependent
  "status": "DEPARTED"  // ❌ Interpreted
}
```

### After (Pure Data)
```json
{
  "station_code": "NY", 
  "has_departed_station": true,  // ✅ Objective fact
  "raw_status": {  // ✅ Raw source data
    "amtrak_status": "Departed",
    "njt_departed_flag": "YES"
  },
  "updated_arrival": "2025-07-16T14:30:00-04:00"  // ✅ Projected time
}
```

## Backwards Compatibility
- **Removed entirely** as requested to keep code simple
- **All users updated simultaneously** for both backend and iOS
- **Clean implementation** without legacy support complexity

## Testing Status
- ✅ **Core implementation complete**
- ✅ **iOS integration working**
- ✅ **Live Activities enhanced**
- 🔄 **Backend tests need updating** (in progress)

## Future Considerations
1. **WebSocket support** for real-time updates using pure data approach
2. **GraphQL endpoints** optimized for client-side context calculations  
3. **Additional transit systems** using same pure data pattern
4. **ML model training** enhanced by objective departure data

---

*Implementation completed on 2025-07-16*
*Resolves asymmetry issue between Amtrak and NJ Transit train status handling*