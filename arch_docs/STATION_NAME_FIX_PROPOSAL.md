# Station Name and Code Fix Proposal

## Problem Analysis

After reviewing the TrackRat iOS app's `Stations.swift` file, the backend's `station_mapping.py`, and the actual API response data, there are significant discrepancies between what the iOS app expects and what the backend API is actually returning.

## Key Issues Identified

### 1. **Missing Station Codes in iOS App**

The API is returning many station codes that the iOS app doesn't recognize:

**Keystone Service (PA) Stations:**
- `HAR` (Harrisburg) ✅ - Present in iOS
- `MID` (Middletown) ❌ - **Missing in iOS** 
- `ELT` (Elizabethtown) ❌ - **Missing in iOS**
- `MJY` (Mount Joy) ❌ - **Missing in iOS**
- `LNC` (Lancaster) ❌ - **Missing in iOS** 
- `PAR` (Parkesburg) ❌ - **Missing in iOS**
- `COT` (Coatesville) ❌ - **Missing in iOS**
- `DOW` (Downingtown) ❌ - **Missing in iOS**
- `EXT` (Exton) ❌ - **Missing in iOS**
- `PAO` (Paoli) ❌ - **Missing in iOS**

**NJ Transit Stations with Wrong Codes:**
- `SE` (Secaucus Upper Lvl) ✅ - Correct in iOS
- `ND` (Newark Broad Street) ❌ - iOS has `NBS`
- `BU` (Brick Church) ❌ - iOS has `BRC`
- `OG` (Orange) ❌ - iOS has `ORA`
- `SO` (South Orange) ✅ - iOS has `SO` but backend expects `SO`
- `MW` (Maplewood) ❌ - iOS has `MW` but backend shows `MW` in API
- `MB` (Millburn) ❌ - iOS has `MIL` but API shows `MB`
- `RT` (Short Hills) ❌ - iOS has `SHI` but API shows `RT`
- `ST` (Summit) ❌ - iOS has `SUM` but API shows `ST`

**Additional Missing Stations:**
- `HL` (Hamilton) ❌ - iOS has `HA` (there's a translation rule in backend)
- `NA` (Newark Airport) ❌ - iOS has `EWR`
- `RH` (Rahway) ❌ - iOS has `RAH`
- `EZ` (Elizabeth) ❌ - iOS has `ELZ`
- `LI` (Linden) ✅ - Correct in iOS
- `MP` (Metropark) ✅ - Correct in iOS
- `MU` (Metuchen) ❌ - iOS has `MET`
- `ED` (Edison) ❌ - iOS has `EDI`
- `NB` (New Brunswick) ✅ - Correct in iOS
- `PJ` (Princeton Junction) ✅ - Correct in iOS
- `TR` (Trenton) ✅ - Correct in iOS

### 2. **Inconsistencies in Backend**

The backend `station_mapping.py` claims to be "in sync with TrackRat/Models/Stations.swift" but clearly isn't. The actual API is returning different codes than what's defined in either file.

### 3. **Frontend-to-Database Translation Issues**

The backend has a translation mechanism (`FRONTEND_TO_DB_CODE`) but it only handles Hamilton (`HA` → `HL`). Many more translations are needed.

## Proposed Solution

### Phase 1: Immediate iOS App Updates

Update `TrackRat/Models/Stations.swift` to include all station codes actually being returned by the API:

```swift
// Station name to code mapping (updated)
static let stationCodes: [String: String] = [
    // NJ Transit stations (corrected codes)
    "New York Penn Station": "NY",
    "Newark Penn Station": "NP", 
    "Secaucus Upper Lvl": "SE",
    "Newark Broad Street": "ND",        // Changed from "NBS"
    "Brick Church": "BU",               // Changed from "BRC"
    "Orange": "OG",                     // Changed from "ORA"
    "South Orange": "SO",               // Confirmed correct
    "Maplewood": "MW",                  // Confirmed correct
    "Millburn": "MB",                   // Changed from "MIL"
    "Short Hills": "RT",                // Changed from "SHI"
    "Summit": "ST",                     // Changed from "SUM"
    "Hamilton": "HL",                   // Changed from "HA"
    "Newark Airport": "NA",             // Changed from "EWR"
    "Rahway": "RH",                     // Changed from "RAH"
    "Elizabeth": "EZ",                  // Changed from "ELZ"
    "Linden": "LI",                     // Confirmed correct
    "Metropark": "MP",                  // Confirmed correct
    "Metuchen": "MU",                   // Changed from "MET"
    "Edison": "ED",                     // Changed from "EDI"
    "New Brunswick": "NB",              // Confirmed correct
    "Princeton Junction": "PJ",         // Confirmed correct
    "Trenton": "TR",                    // Confirmed correct
    
    // Add missing Keystone Service stations
    "Middletown": "MID",
    "Elizabethtown": "ELT", 
    "Mount Joy": "MJY",
    "Lancaster": "LNC",
    "Parkesburg": "PAR",
    "Coatesville": "COT",
    "Downingtown": "DOW",
    "Exton": "EXT",
    "Paoli": "PAO",
    
    // Add missing other stations from API response
    "Jersey Avenue": "JA",
    "Avenel": "AV",
    "Perth Amboy": "PE",
    "South Amboy": "CH",
    "Aberdeen-Matawan": "AM",
    "Hazlet": "HZ",
    "Middletown NJ": "MI",
    "Red Bank": "RB", 
    "Little Silver": "LS",
    "Long Branch": "LB",
    "Bay Head": "BH",
    "Point Pleasant Beach": "PP",
    "Manasquan": "SQ",
    "Spring Lake": "LA",
    "Belmar": "BS",
    "Bradley Beach": "BB",
    "Asbury Park": "AP",
    "Allenhurst": "AH",
    "Elberon": "EL",
    "Chatham": "CM",
    "Madison": "MA",
    "Convent Station": "CN",
    "Morristown": "MR",
    "Morris Plains": "MX",
    "Mount Tabor": "TB",
    "Denville": "DV",
    "Dover": "DO",
    "Montclair State U": "UV",
    "Montclair Heights": "HS",
    "Upper Montclair": "UM",
    "Walnut Street": "WA",
    "Watchung Avenue": "WG",
    "Bay Street": "MC",
    "Glen Ridge": "GG",
    "Bloomfield": "BM",
    "Watsessing Avenue": "WT",
    "East Orange": "EO",
    "Highland Avenue": "HI",
    "Mountain Station": "MT",
    "North Elizabeth": "NZ",
    "Annandale": "AN",
    "Lebanon": "ON",
    "White House": "WH",
    "North Branch": "OR",
    "Raritan": "RA",
    "Somerville": "SM",
    "Bridgewater": "BW",
    "Bound Brook": "BK",
    "Dunellen": "DN",
    "Plainfield": "PF",
    "Netherwood": "NE",
    "Fanwood": "FW",
    "Westfield": "WF",
    "Garwood": "GW",
    "Cranford": "XC",
    "Roselle Park": "RL",
    "Union": "US",
    "High Bridge": "HG",
    
    // Amtrak stations (confirmed correct)
    "Philadelphia": "PH",
    "Baltimore Station": "BL",
    "Washington Station": "WS",
    "BWI Thurgood Marshall Airport": "BA",
    "Wilmington Station": "WI",
    "New Carrollton Station": "NC",
    // ... keep existing Amtrak stations
]
```

### Phase 2: Backend Synchronization

1. **Update `station_mapping.py`** to reflect the actual codes being used by the API
2. **Expand `FRONTEND_TO_DB_CODE`** translation table to handle any remaining discrepancies
3. **Add validation** to ensure the backend stays in sync with iOS

### Phase 3: Enhanced Station Support

1. **Add all missing stations** to the iOS station list from the API response
2. **Update `departureStations`** array if any of the new stations should be supported as departure points
3. **Test thoroughly** with the corrected station codes

## Implementation Priority

### High Priority (Breaks existing functionality)
- Fix core NJ Transit station codes (ND, BU, OG, RT, ST, HL, NA, RH, EZ, MU, ED)
- Add essential journey stations (JA, AV, PE, CH, etc.)

### Medium Priority (Enables new features)  
- Add all Keystone Service stations (MID, ELT, MJY, LNC, PAR, COT, DOW, EXT, PAO)
- Add remaining NJ Coast Line stations

### Low Priority (Nice to have)
- Add all remaining stations from API for completeness
- Implement proper station search/filtering

## Testing Strategy

1. **Update iOS station codes** first
2. **Test origin/destination selection** with corrected codes
3. **Verify API calls** return expected train data
4. **Test journey planning** between newly supported stations
5. **Validate Live Activities** work with new station codes

## Backward Compatibility

This change should be **mostly backward compatible** since:
- The API endpoints haven't changed
- Most core stations (NY, NP, TR, PJ, MP) are correct
- Only station internal codes are being corrected

However, any **hardcoded station codes** in the iOS app will need to be updated.

## Files to Modify

### iOS App
- `TrackRat/Models/Stations.swift` - Update `stationCodes` dictionary and `all` array

### Backend (if needed)
- `trackcast/services/station_mapping.py` - Sync with actual API codes
- `config/dev.yaml` and `config/test.yaml` - Verify station configurations

## Example API Queries After Fix

```swift
// These should work after the fix:
APIService.shared.fetchTrains(fromStationCode: "NY", toStationCode: "HAR") // NY to Harrisburg
APIService.shared.fetchTrains(fromStationCode: "PH", toStationCode: "ELT") // Philly to Elizabethtown  
APIService.shared.fetchTrains(fromStationCode: "ND", toStationCode: "ST")  // Newark Broad to Summit
```

This comprehensive fix will ensure the iOS app can properly query and display all stations currently supported by the TrackRat backend API.