import Foundation
import CoreLocation

struct Stations {
    static let all: [String] = [
        // NJ Transit stations (corrected codes to match API)
        "New York Penn Station", "Newark Penn Station", "Secaucus Upper Lvl",
        "Metropark", "New Brunswick", "Princeton Junction", "Trenton", "Hamilton",
        "Newark Airport",
        "Elizabeth", "Linden", "Rahway", "Metuchen", "Edison", "Iselin",
        "Jersey Avenue", "North Elizabeth",
        
        // Missing Keystone Service stations (PA)
        "Middletown", "Elizabethtown", "Mount Joy", "Lancaster", "Parkesburg", "Coatesville",
        "Downingtown", "Exton", "Paoli",
        
        // Amtrak stations (Northeast Corridor and beyond) - Updated with new stations
        "Boston South", "Boston Back Bay", "Providence", "New Haven", "Bridgeport",
        "Stamford", "Hartford", "Meriden", "New London", "Old Saybrook", "Wallingford", 
        "Windsor Locks", "Springfield", "Claremont", "Dover", "Durham-UNH", "Exeter",
        "Philadelphia", "Baltimore Station", "Washington Union Station", "BWI Thurgood Marshall Airport",
        "Wilmington Station", "New Carrollton", "Aberdeen", "Alexandria", "Charlottesville",
        "Lorton", "Norfolk", "Richmond Main Street", "Roanoke", "Harrisburg", "Lancaster",
        "Kingston", "Westerly"
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
        "Parkesburg": "PKB",
        "Coatesville": "COT",
        "Downingtown": "DOW",
        "Exton": "EXT",
        "Paoli": "PAO",
        
        // Amtrak stations (corrected with updated codes to match backend)
        "Boston South": "BOS",
        "Boston Back Bay": "BBY",
        "Providence": "PVD",
        "New Haven": "NHV",
        "Bridgeport": "BRP",
        "Stamford": "STM",
        "Hartford": "HFD",
        "Meriden": "MDN",
        "New London": "NLC",
        "Old Saybrook": "OSB",
        "Wallingford": "WFD",
        "Windsor Locks": "WNL",
        "Springfield": "SPG",
        "Claremont": "CLA",
        "Dover": "DOV",
        "Durham-UNH": "DHM",
        "Exeter": "EXR",
        "Philadelphia": "PH",
        "Baltimore Station": "BL",
        "Washington Union Station": "WS",
        "BWI Thurgood Marshall Airport": "BA",
        "Wilmington Station": "WI",
        "New Carrollton": "NCR",
        "Aberdeen": "ABE",
        "Alexandria": "ALX",
        "Charlottesville": "CVS",
        "Lorton": "LOR",
        "Norfolk": "NFK",
        "Richmond Main Street": "RVR",
        "Roanoke": "RNK",
        "Harrisburg": "HAR",
        "Lancaster": "LNC",
        "Kingston": "KIN",
        "Westerly": "WLY"
    ]
    
    // Station coordinates for mapping - synced with backend_v2/src/trackrat/config/stations.py
    static let stationCoordinates: [String: CLLocationCoordinate2D] = [
        // Core NJ Transit/Amtrak stations - Updated GPS coordinates
        "NY": CLLocationCoordinate2D(latitude: 40.7506, longitude: -73.9939),   // New York Penn Station - Updated GPS
        "NP": CLLocationCoordinate2D(latitude: 40.7347, longitude: -74.1644),   // Newark Penn Station - Updated GPS
        "TR": CLLocationCoordinate2D(latitude: 40.218518, longitude: -74.753923), // Trenton Transit Center - Updated GPS
        "HL": CLLocationCoordinate2D(latitude: 40.2547, longitude: -74.7036),   // Hamilton
        "PJ": CLLocationCoordinate2D(latitude: 40.3167, longitude: -74.6233),   // Princeton Junction - Updated GPS
        "MP": CLLocationCoordinate2D(latitude: 40.5378, longitude: -74.3562),   // Metropark - Updated GPS
        "NA": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.1608),   // Newark Airport
        "NB": CLLocationCoordinate2D(latitude: 40.4862, longitude: -74.4518),   // New Brunswick
        "SE": CLLocationCoordinate2D(latitude: 40.7612, longitude: -74.0758),   // Secaucus Junction - Updated GPS
        "PH": CLLocationCoordinate2D(latitude: 39.9570, longitude: -75.1820),   // Philadelphia 30th Street Station - Updated GPS
        "WI": CLLocationCoordinate2D(latitude: 39.7369, longitude: -75.5522),   // Wilmington - Updated GPS
        "BA": CLLocationCoordinate2D(latitude: 39.1896, longitude: -76.6934),   // BWI Airport Rail Station - Updated GPS
        "BL": CLLocationCoordinate2D(latitude: 39.3081, longitude: -76.6175),   // Baltimore Penn Station - Updated GPS
        "WS": CLLocationCoordinate2D(latitude: 38.8973, longitude: -77.0064),   // Washington Union Station - Updated GPS
        "BOS": CLLocationCoordinate2D(latitude: 42.3520, longitude: -71.0552),  // Boston South Station - Updated GPS
        "BBY": CLLocationCoordinate2D(latitude: 42.3473, longitude: -71.0764),  // Boston Back Bay - Updated GPS
        
        // Additional Amtrak stations with GPS coordinates
        "BRP": CLLocationCoordinate2D(latitude: 41.1767, longitude: -73.1874),  // Bridgeport, CT
        "HFD": CLLocationCoordinate2D(latitude: 41.7678, longitude: -72.6821),  // Hartford, CT
        "MDN": CLLocationCoordinate2D(latitude: 41.5390, longitude: -72.8012),  // Meriden, CT
        "NHV": CLLocationCoordinate2D(latitude: 41.2987, longitude: -72.9259),  // New Haven, CT
        "NLC": CLLocationCoordinate2D(latitude: 41.3543, longitude: -72.0939),  // New London, CT
        "OSB": CLLocationCoordinate2D(latitude: 41.3005, longitude: -72.3760),  // Old Saybrook, CT
        "STM": CLLocationCoordinate2D(latitude: 41.0462, longitude: -73.5427),  // Stamford, CT
        "WFD": CLLocationCoordinate2D(latitude: 41.4571, longitude: -72.8254),  // Wallingford, CT
        "WNL": CLLocationCoordinate2D(latitude: 41.9272, longitude: -72.6286),  // Windsor Locks, CT
        "ABE": CLLocationCoordinate2D(latitude: 39.5095, longitude: -76.1630),  // Aberdeen, MD
        "NCR": CLLocationCoordinate2D(latitude: 38.9533, longitude: -76.8644),  // New Carrollton, MD
        "SPG": CLLocationCoordinate2D(latitude: 42.1060, longitude: -72.5936),  // Springfield, MA
        "CLA": CLLocationCoordinate2D(latitude: 43.3688, longitude: -72.3793),  // Claremont, NH
        "DOV": CLLocationCoordinate2D(latitude: 43.1979, longitude: -70.8737),  // Dover, NH
        "DHM": CLLocationCoordinate2D(latitude: 43.1340, longitude: -70.9267),  // Durham-UNH, NH
        "EXR": CLLocationCoordinate2D(latitude: 42.9809, longitude: -70.9478),  // Exeter, NH
        "HAR": CLLocationCoordinate2D(latitude: 40.2616, longitude: -76.8782),  // Harrisburg, PA
        "LNC": CLLocationCoordinate2D(latitude: 40.0538, longitude: -76.3076),  // Lancaster, PA
        "KIN": CLLocationCoordinate2D(latitude: 41.4885, longitude: -71.5204),  // Kingston, RI
        "PVD": CLLocationCoordinate2D(latitude: 41.8256, longitude: -71.4160),  // Providence, RI
        "WLY": CLLocationCoordinate2D(latitude: 41.3770, longitude: -71.8307),  // Westerly, RI
        "ALX": CLLocationCoordinate2D(latitude: 38.8062, longitude: -77.0626),  // Alexandria, VA
        "CVS": CLLocationCoordinate2D(latitude: 38.0320, longitude: -78.4921),  // Charlottesville, VA
        "LOR": CLLocationCoordinate2D(latitude: 38.7060, longitude: -77.2214),  // Lorton, VA
        "NFK": CLLocationCoordinate2D(latitude: 36.8583, longitude: -76.2876),  // Norfolk, VA
        "RVR": CLLocationCoordinate2D(latitude: 37.6143, longitude: -77.4966),  // Richmond Main Street, VA
        "RNK": CLLocationCoordinate2D(latitude: 37.3077, longitude: -79.9803),  // Roanoke, VA
        //"PL": CLLocationCoordinate2D(latitude: 40.6140, longitude: -74.1647),   // Plainfield
        //"LB": CLLocationCoordinate2D(latitude: 40.0849, longitude: -74.1990),   // Long Branch
        "JA": CLLocationCoordinate2D(latitude: 40.4769, longitude: -74.4674),   // Jersey Avenue
        "US": CLLocationCoordinate2D(latitude: 40.6973, longitude: -74.1647),   // Union Station
        "AZ": CLLocationCoordinate2D(latitude: 40.7127, longitude: -74.1634),   // Newark Airport (estimate)
        "RY": CLLocationCoordinate2D(latitude: 40.6039, longitude: -74.2723),   // Rahway
        "LA": CLLocationCoordinate2D(latitude: 40.6140, longitude: -74.1647),   // Plainfield (estimate)
        "SQ": CLLocationCoordinate2D(latitude: 40.5849, longitude: -74.1990),   // Long Branch (estimate)
        //"HB": CLLocationCoordinate2D(latitude: 40.734843, longitude: -74.028043), // Hoboken Terminal - Updated GPS
        //"RA": CLLocationCoordinate2D(latitude: 40.5682, longitude: -74.6290),   // Raritan
        
        // Additional NJT stations for complete map coverage - Updated GPS
        "ED": CLLocationCoordinate2D(latitude: 40.5177, longitude: -74.4075),   // Edison - Updated GPS
        "MU": CLLocationCoordinate2D(latitude: 40.5378, longitude: -74.3562),   // Metuchen - Updated GPS
        "RH": CLLocationCoordinate2D(latitude: 40.6039, longitude: -74.2723),   // Rahway - Updated GPS
        "LI": CLLocationCoordinate2D(latitude: 40.629487, longitude: -74.251772), // Linden - Updated GPS
        "EL": CLLocationCoordinate2D(latitude: 40.667859, longitude: -74.215171), // Elizabeth - Updated GPS
        "EZ": CLLocationCoordinate2D(latitude: 40.667859, longitude: -74.215171), // Elizabeth - Updated GPS
        "NZ": CLLocationCoordinate2D(latitude: 40.6968, longitude: -74.1733),   // North Elizabeth
       
        /* 
        // Bergen County Line (Main Line) - New GPS coordinates
        "LY": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Lyndhurst
        "DL": CLLocationCoordinate2D(latitude: 40.8180, longitude: -74.1370),   // Delawanna
        "PA": CLLocationCoordinate2D(latitude: 40.8570, longitude: -74.1294),   // Passaic
        "CL": CLLocationCoordinate2D(latitude: 40.8584, longitude: -74.1637),   // Clifton
        "PT": CLLocationCoordinate2D(latitude: 40.9166, longitude: -74.1710),   // Paterson
        "HT": CLLocationCoordinate2D(latitude: 40.9494, longitude: -74.1527),   // Hawthorne
        "GR": CLLocationCoordinate2D(latitude: 40.9633, longitude: -74.1269),   // Glen Rock
        "RW": CLLocationCoordinate2D(latitude: 40.9808, longitude: -74.1168),   // Ridgewood
        "HH": CLLocationCoordinate2D(latitude: 40.9956, longitude: -74.1115),   // Ho-Ho-Kus
        "WA": CLLocationCoordinate2D(latitude: 41.0108, longitude: -74.1267),   // Waldwick
        "AL": CLLocationCoordinate2D(latitude: 41.0312, longitude: -74.1306),   // Allendale
        "RM": CLLocationCoordinate2D(latitude: 41.0571, longitude: -74.1413),   // Ramsey
        "R17": CLLocationCoordinate2D(latitude: 41.0615, longitude: -74.1456),  // Ramsey-Route 17
        "MH": CLLocationCoordinate2D(latitude: 41.0886, longitude: -74.1438),   // Mahwah
        "SF": CLLocationCoordinate2D(latitude: 41.1144, longitude: -74.1496),   // Suffern, NY
        
        // Bergen County Line (Ridgewood Branch)
        "RT": CLLocationCoordinate2D(latitude: 40.8267, longitude: -74.1069),   // Rutherford
        "WE": CLLocationCoordinate2D(latitude: 40.8356, longitude: -74.0989),   // Wesmont
        "GA": CLLocationCoordinate2D(latitude: 40.8815, longitude: -74.1133),   // Garfield
        "PLD": CLLocationCoordinate2D(latitude: 40.8879, longitude: -74.1202),  // Plauderville
        "BW": CLLocationCoordinate2D(latitude: 40.9188, longitude: -74.1316),   // Broadway (Fair Lawn)
        "RB": CLLocationCoordinate2D(latitude: 40.9405, longitude: -74.1320),   // Radburn
        "GB": CLLocationCoordinate2D(latitude: 40.9595, longitude: -74.1329),   // Glen Rock–Boro Hall
        
        // Pascack Valley Line
        "WR": CLLocationCoordinate2D(latitude: 40.8449, longitude: -74.0883),   // Wood-Ridge
        "TB": CLLocationCoordinate2D(latitude: 40.8602, longitude: -74.0639),   // Teterboro
        "ES": CLLocationCoordinate2D(latitude: 40.8836, longitude: -74.0436),   // Essex Street
        "AN": CLLocationCoordinate2D(latitude: 40.8944, longitude: -74.0447),   // Anderson Street
        "NBL": CLLocationCoordinate2D(latitude: 40.9079, longitude: -74.0384),  // New Bridge Landing
        "RE": CLLocationCoordinate2D(latitude: 40.9264, longitude: -74.0413),   // River Edge
        "OR": CLLocationCoordinate2D(latitude: 40.9545, longitude: -74.0369),   // Oradell
        "EM": CLLocationCoordinate2D(latitude: 40.9758, longitude: -74.0281),   // Emerson
        "WW": CLLocationCoordinate2D(latitude: 40.9909, longitude: -74.0336),   // Westwood
        "WL": CLLocationCoordinate2D(latitude: 41.0230, longitude: -74.0569),   // Woodcliff Lake
        "PR": CLLocationCoordinate2D(latitude: 41.0375, longitude: -74.0406),   // Park Ridge
        "MV": CLLocationCoordinate2D(latitude: 41.0521, longitude: -74.0372),   // Montvale
        "PER": CLLocationCoordinate2D(latitude: 41.0595, longitude: -74.0197),  // Pearl River, NY
        "NU": CLLocationCoordinate2D(latitude: 41.0869, longitude: -74.0130),   // Nanuet, NY
        "SV": CLLocationCoordinate2D(latitude: 41.1130, longitude: -74.0436),   // Spring Valley, NY
        
        // Port Jervis Line (from Suffern)
        "SL": CLLocationCoordinate2D(latitude: 41.1568, longitude: -74.1937),   // Sloatsburg, NY
        "TX": CLLocationCoordinate2D(latitude: 41.1970, longitude: -74.1885),   // Tuxedo, NY
        "HR": CLLocationCoordinate2D(latitude: 41.3098, longitude: -74.1526),   // Harriman, NY
        "SM": CLLocationCoordinate2D(latitude: 41.4426, longitude: -74.1351),   // Salisbury Mills–Cornwall, NY
        "CH": CLLocationCoordinate2D(latitude: 41.4446, longitude: -74.2452),   // Campbell Hall, NY
        "MD": CLLocationCoordinate2D(latitude: 41.4459, longitude: -74.4222),   // Middletown, NY
        "OT": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville, NY
        "PJV": CLLocationCoordinate2D(latitude: 41.3746, longitude: -74.6927),  // Port Jervis, NY
        
        // Morris & Essex Line / Gladstone Branch - Updated GPS
        "ML": CLLocationCoordinate2D(latitude: 40.725667, longitude: -74.303694), // Millburn
        "ST": CLLocationCoordinate2D(latitude: 40.7099, longitude: -74.3546),   // Summit
        "ND": CLLocationCoordinate2D(latitude: 40.7418, longitude: -74.1698),   // Newark Broad Street
        "DV": CLLocationCoordinate2D(latitude: 40.8837, longitude: -74.4753),   // Denville
        "PE": CLLocationCoordinate2D(latitude: 40.7052, longitude: -74.6550),   // Peapack
        
        // Montclair-Boonton Line - Updated GPS
        "MHT": CLLocationCoordinate2D(latitude: 40.857538, longitude: -74.202493), // Montclair Heights
        "MS": CLLocationCoordinate2D(latitude: 40.8695, longitude: -74.1975),   // Montclair State University
        "DO": CLLocationCoordinate2D(latitude: 40.883417, longitude: -74.555884), // Dover
        "BO": CLLocationCoordinate2D(latitude: 40.903378, longitude: -74.407733)  // Boonton
        */
    ]
    
    // Supported departure stations
    static let departureStations: [(name: String, code: String)] = [
        ("New York Penn Station", "NY"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR"),
        ("Philadelphia", "PH"),
        ("Wilmington Station", "WI")
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
        
        // Handle NJ Transit destinations with -SEC suffix, emojis, and HTML entities
        if normalized.contains("-sec") || normalized.contains("✈") || normalized.contains("&#9992") {
            let cleaned = normalized
                .replacingOccurrences(of: " -sec", with: "")
                .replacingOccurrences(of: "-sec", with: "")
                .replacingOccurrences(of: " ✈", with: "")
                .replacingOccurrences(of: "✈", with: "")
                .replacingOccurrences(of: " &#9992", with: "")
                .replacingOccurrences(of: "&#9992", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            
            // If we cleaned something, try again with the cleaned string
            if cleaned != normalized {
                // Capitalize first letter of each word for the recursive call
                let capitalized = cleaned.split(separator: " ")
                    .map { $0.prefix(1).uppercased() + $0.dropFirst() }
                    .joined(separator: " ")
                
                if let code = getStationCode(capitalized) {
                    return code
                }
            }
        }
        
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
    
    static func getCoordinates(for code: String) -> CLLocationCoordinate2D? {
        return stationCoordinates[code]
    }
}
