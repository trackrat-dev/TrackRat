import Foundation

struct Stations {
    static let all: [String] = [
        // NJ Transit stations (corrected codes to match API)
        "New York Penn Station", "Newark Penn Station", "Secaucus Upper Lvl", "Woodbridge",
        "Metropark", "New Brunswick", "Princeton Junction", "Trenton", "Hamilton",
        "Morristown", "Madison", "Summit", "Millburn", "Short Hills", "Newark Airport",
        "Elizabeth", "Linden", "Rahway", "Metuchen", "Edison", "Iselin", "Perth Amboy",
        "South Amboy", "Aberdeen-Matawan", "Hazlet", "Red Bank", "Little Silver", "Monmouth Park",
        "Long Branch", "Asbury Park", "Bradley Beach", "Belmar", "Spring Lake", "Manasquan",
        "Point Pleasant Beach", "Bay Head", "Montclair State University", "Montclair Heights",
        "Upper Montclair", "Mountain Avenue", "Orange", "East Orange", "Brick Church",
        "Newark Broad Street", "Bloomfield", "Watsessing", "Walnut Street", "Glen Ridge",
        "Ridgewood", "Ho-Ho-Kus", "Waldwick", "Allendale", "Ramsey Route 17", "Ramsey Main Street",
        "Mahwah", "Suffern", "Sloatsburg", "Tuxedo", "Harriman", "Goshen", "Campbell Hall",
        "Salisbury Mills-Cornwall", "New Hampton", "Middletown NJ", "Otisville", "Port Jervis",
        "Denville", "Mount Tabor", "Parsippany", "Boonton", "Mountain Lakes", "Convent Station",
        "Chatham", "New Providence", "Murray Hill", "Berkeley Heights",
        "Gillette", "Stirling", "Millington", "Lyons", "Basking Ridge", "Bernardsville",
        "Far Hills", "Peapack", "Gladstone", "Annandale", "Lebanon", "White House",
        "North Branch", "Raritan", "Somerville", "Bound Brook", "Dunellen", "Plainfield",
        "Netherwood", "Fanwood", "Westfield", "Garwood", "Cranford", "Roselle Park",
        "Union", "Jersey Avenue", "Avenel", "Highland Avenue", "Mountain Station", "North Elizabeth",
        "Bay Street", "Watchung Avenue", "Watsessing Avenue",
        
        // Missing Keystone Service stations (PA)
        "Middletown", "Elizabethtown", "Mount Joy", "Lancaster", "Parkesburg", "Coatesville",
        "Downingtown", "Exton", "Paoli",
        
        // Amtrak stations (Northeast Corridor and beyond)
        "Boston South", "Boston Back Bay", "Providence", "New Haven", "Bridgeport",
        "Stamford", "New Rochelle", "Yonkers", "Croton-Harmon", "Poughkeepsie", "Rhinecliff",
        "Hudson", "Albany-Rensselaer", "Schenectady", "Amsterdam", "Utica", "Rome", "Syracuse",
        "Rochester", "Buffalo-Depew", "Buffalo Exchange Street", "Niagara Falls",
        "Philadelphia", "Baltimore Station", "Washington Union Station", "BWI Thurgood Marshall Airport",
        "Wilmington Station", "New Carrollton Station",
        "Aberdeen", "Alexandria", "Fredericksburg", "Richmond Staples Mill",
        "Richmond Main Street", "Petersburg", "Rocky Mount", "Wilson", "Selma-Smithfield",
        "Raleigh", "Cary", "Southern Pines", "Hamlet", "Fayetteville", "Dillon", "Florence",
        "Kingstree", "Charleston", "Columbia", "Camden", "Denmark", "Savannah", "Jesup",
        "Jacksonville", "Palatka", "DeLand", "Winter Park", "Orlando", "Kissimmee",
        "Lakeland", "Tampa", "Sebring", "Okeechobee", "West Palm Beach", "Delray Beach",
        "Deerfield Beach", "Fort Lauderdale", "Hollywood", "Hallandale Beach", "Aventura",
        "Miami", "Hialeah Market", "Miami Airport", "Toronto Union", "Pittsburgh", "New Orleans", "Norfolk", "Roanoke"
    ].sorted()
    
    // Station name to code mapping
    static let stationCodes: [String: String] = [
        // NJ Transit stations
        "New York Penn Station": "NY",
        "Newark Penn Station": "NP",
        "Secaucus Upper Lvl": "SE",
        "Woodbridge": "WDB",
        "Metropark": "MP",
        "New Brunswick": "NB",
        "Princeton Junction": "PJ",
        "Trenton": "TR",
        "Trenton Transit Center": "TR",
        "Hamilton": "HL",
        "Morristown": "MOR",
        "Madison": "MAD",
        "Summit": "ST",
        "Millburn": "MB",
        "Short Hills": "RT",
        "Newark Airport": "NA",
        "Elizabeth": "EZ",
        "Linden": "LI",
        "Rahway": "RH",
        "Metuchen": "MU",
        "Edison": "ED",
        "Iselin": "ISE",
        "Perth Amboy": "PAM",
        "South Amboy": "SAM",
        "Aberdeen-Matawan": "ABM",
        "Hazlet": "HAZ",
        "Red Bank": "RBK",
        "Little Silver": "LIS",
        "Monmouth Park": "MPK",
        "Long Branch": "LBR",
        "Asbury Park": "ASB",
        "Bradley Beach": "BRB",
        "Belmar": "BEL",
        "Spring Lake": "SPL",
        "Manasquan": "MAN",
        "Point Pleasant Beach": "PPB",
        "Bay Head": "BAY",
        "Montclair State University": "MSU",
        "Montclair Heights": "MCH",
        "Upper Montclair": "UMC",
        "Mountain Avenue": "MVA",
        "Orange": "OG",
        "East Orange": "EOR",
        "Brick Church": "BU",
        "Newark Broad Street": "ND",
        "Bloomfield": "BLO",
        "Watsessing": "WAT",
        "Walnut Street": "WNS",
        "Glen Ridge": "GLR",
        "Ridgewood": "RID",
        "Ho-Ho-Kus": "HHK",
        "Waldwick": "WAL",
        "Allendale": "ALL",
        "Ramsey Route 17": "RR17",
        "Ramsey Main Street": "RMS",
        "Mahwah": "MAH",
        "Suffern": "SUF",
        "Sloatsburg": "SLO",
        "Tuxedo": "TUX",
        "Harriman": "HAR",
        "Goshen": "GOS",
        "Campbell Hall": "CAM",
        "Salisbury Mills-Cornwall": "SMC",
        "New Hampton": "NHA",
        "Middletown NJ": "MTN",
        "Otisville": "OTI",
        "Port Jervis": "PJE",
        "Denville": "DEN",
        "Mount Tabor": "MTA",
        "Parsippany": "PAR",
        "Boonton": "BOO",
        "Mountain Lakes": "MLA",
        "Convent Station": "CON",
        "Chatham": "CHA",
        "New Providence": "NPR",
        "Murray Hill": "MUR",
        "Berkeley Heights": "BER",
        "Gillette": "GIL",
        "Stirling": "STI",
        "Millington": "MIL2",
        "Lyons": "LYO",
        "Basking Ridge": "BAS",
        "Bernardsville": "BER2",
        "Far Hills": "FAR",
        "Peapack": "PEA",
        "Gladstone": "GLA",
        "Annandale": "ANN",
        "Lebanon": "LEB",
        "White House": "WHI",
        "North Branch": "NBR",
        "Raritan": "RAR",
        "Somerville": "SOM",
        "Bound Brook": "BBK",
        "Dunellen": "DUN",
        "Plainfield": "PLA",
        "Netherwood": "NET",
        "Fanwood": "FAN",
        "Westfield": "WES",
        "Garwood": "GAR",
        "Cranford": "CRA",
        "Roselle Park": "ROP",
        "Union": "US",
        "Jersey Avenue": "JA",
        "Avenel": "AV",
        "Highland Avenue": "HI",
        "Mountain Station": "MT",
        "North Elizabeth": "NZ",
        "Bay Street": "MC",
        "Watchung Avenue": "WG",
        "Watsessing Avenue": "WT",
        
        // Missing Keystone Service stations (PA)
        "Middletown": "MIDPA",
        "Elizabethtown": "ELT",
        "Mount Joy": "MJY",
        "Lancaster": "LNC",
        "Parkesburg": "PKB",
        "Coatesville": "COT",
        "Downingtown": "DOW",
        "Exton": "EXT",
        "Paoli": "PAO",
        
        // Amtrak stations (corrected)
        "Boston South": "BOS",
        "Boston Back Bay": "BBY",
        "Providence": "PVD",
        "New Haven": "NHV",
        "Bridgeport": "BRP",
        "Stamford": "STM",
        "New Rochelle": "NRO",
        "Yonkers": "YNY",
        "Croton-Harmon": "CRT",
        "Poughkeepsie": "POU",
        "Rhinecliff": "RHI",
        "Hudson": "HUD",
        "Albany-Rensselaer": "ALB",
        "Schenectady": "SCH",
        "Amsterdam": "AMS",
        "Utica": "UTS",
        "Rome": "ROM",
        "Syracuse": "SYR",
        "Rochester": "ROC",
        "Buffalo-Depew": "BUF",
        "Buffalo Exchange Street": "BFX",
        "Niagara Falls": "NFL",
        "Philadelphia": "PH",
        "Baltimore Station": "BL",
        "Washington Union Station": "WS",
        "BWI Thurgood Marshall Airport": "BA",
        "Wilmington Station": "WI",
        "New Carrollton Station": "NC",
        "Aberdeen": "ABE",
        "Alexandria": "AXA",
        "Fredericksburg": "FRB",
        "Richmond Staples Mill": "RSM",
        "Richmond Main Street": "RVM",
        "Petersburg": "PTB",
        "Rocky Mount": "RMT",
        "Wilson": "WIL2",
        "Selma-Smithfield": "SSM",
        "Raleigh": "RAL",
        "Cary": "CAR",
        "Southern Pines": "SPN",
        "Hamlet": "HAM2",
        "Fayetteville": "FAY",
        "Dillon": "DIL",
        "Florence": "FLO",
        "Kingstree": "KTR",
        "Charleston": "CHS",
        "Columbia": "COL",
        "Camden": "CAM2",
        "Denmark": "DEN2",
        "Savannah": "SAV",
        "Jesup": "JES",
        "Jacksonville": "JAX",
        "Palatka": "PAL",
        "DeLand": "DEL",
        "Winter Park": "WPK",
        "Orlando": "ORL",
        "Kissimmee": "KIS",
        "Lakeland": "LAK",
        "Tampa": "TPA",
        "Sebring": "SEB",
        "Okeechobee": "OKE",
        "West Palm Beach": "WPB",
        "Delray Beach": "DRB",
        "Deerfield Beach": "DFB",
        "Fort Lauderdale": "FTL",
        "Hollywood": "HOL",
        "Hallandale Beach": "HLB",
        "Aventura": "AVE",
        "Miami": "MIA",
        "Hialeah Market": "HIA",
        "Miami Airport": "MIP",
        "Toronto Union": "TOR",
        "Pittsburgh": "PIT",
        "New Orleans": "NOL",
        "Norfolk": "NFK",
        "Roanoke": "ROA"
    ]
    
    // Supported departure stations
    static let departureStations: [(name: String, code: String)] = [
        ("New York Penn Station", "NY"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR")
    ]
    
    // Popular destination stations - kept in sync with departure stations
    static var popularDestinations: [(name: String, code: String)] {
        return departureStations
    }
    
    static func search(_ query: String) -> [String] {
        guard !query.isEmpty else { return [] }
        let lowercased = query.lowercased()
        return all.filter { $0.lowercased().contains(lowercased) }
            .prefix(8)
            .map { $0 }
    }
    
    static func getStationCode(_ stationName: String) -> String? {
        // First try exact match
        if let code = stationCodes[stationName] {
            return code
        }
        
        // Try common variations for ambiguous names
        let normalized = stationName.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        switch normalized {
        case "new york":
            return "NY"
        case "newark":
            return "NP"  // Default to Newark Penn Station
        case "trenton":
            return "TR"
        case "princeton":
            return "PJ"  // Princeton Junction is more common than Princeton
        case "philadelphia":
            return "PH"
        case "washington":
            return "WS"  // Washington Union Station
        case "baltimore":
            return "BL"
        case "boston":
            return "BOS"  // Boston South Station
        default:
            break
        }
        
        // Try partial matching for "Penn Station" destinations
        if normalized.contains("penn") {
            if normalized.contains("new york") || normalized.contains("ny") {
                return "NY"
            } else if normalized.contains("newark") {
                return "NP"
            }
        }
        
        // Try partial matching - find station names that contain the search term
        for (fullName, code) in stationCodes {
            if fullName.lowercased().contains(normalized) {
                return code
            }
        }
        
        return nil
    }
}
