import Foundation
import CoreLocation
import MapKit

struct Stations {
    static func search(_ query: String) -> [String] {
        guard !query.isEmpty else { return [] }
        let q = query.lowercased()
        let prefixMatches = all.filter { $0.lowercased().hasPrefix(q) }
        let substringMatches = all.filter {
            !$0.lowercased().hasPrefix(q) && $0.lowercased().contains(q)
        }
        return Array((prefixMatches + substringMatches).prefix(12))
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

    /// Smart display name that handles both station codes and station names.
    /// - For codes (e.g., "NY", "MP"): Returns the full station name
    /// - For names (e.g., "New York Penn Station"): Returns shortened version
    static func displayName(for input: String) -> String {
        // First, check if input is a station code
        if let fullName = stationName(forCode: input) {
            return shortenedDisplayName(for: fullName)
        }
        // Otherwise, assume it's a station name and apply shortening
        return shortenedDisplayName(for: input)
    }

    /// Returns a shortened display name for UI (strips "Station", etc.)
    private static func shortenedDisplayName(for stationName: String) -> String {
        // First normalize the name to handle API inconsistencies
        let normalizedName = StationNameNormalizer.normalizedName(for: stationName)

        // Apply short display names for common stations
        switch normalizedName {
        case "New York Penn Station":
            return "New York Penn"
        case "Newark Penn Station":
            return "Newark Penn"
        case "Washington Union Station":
            return "Washington Union"
        default:
            return normalizedName
        }
    }

    // MARK: - Station to Train System Mapping

    /// Special overrides for stations that need manual mapping beyond what RouteTopology provides.
    /// Most stations are automatically derived from RouteTopology - only add overrides here for:
    /// - Stations with adjacent systems (e.g., NP has PATH adjacency)
    /// - Stations not on any RouteTopology route but belonging to a non-Amtrak system
    private static let stationSystemOverrides: [String: Set<String>] = [
        "NP": ["NJT", "AMTRAK", "PATH"],  // Newark Penn Station (PATH adjacent)
        // NJT stations not in RouteTopology
        "TS": ["NJT"],   // Secaucus Lower Lvl
        "GA": ["NJT"],   // Great Notch
        "MO": ["NJT"],   // Montclair-Boonton Line
        "SC": ["NJT"],   // Secaucus Concourse
        // LIRR stations not in RouteTopology
        "HPA": ["LIRR"],  // Hunterspoint Avenue
        "LIC": ["LIRR"],  // Long Island City
        "NHP": ["LIRR"],  // New Hyde Park
        "BRT": ["LIRR"],  // Belmont Park
        // Amtrak codes for shared Amtrak/MNR stations (used in stationEquivalents)
        "NRO": ["AMTRAK", "MNR"],  // New Rochelle (equiv: MNRC)
        "YNY": ["AMTRAK", "MNR"],  // Yonkers (equiv: MYON)
        "CRT": ["AMTRAK", "MNR"],  // Croton-Harmon (equiv: MCRH)
        "POU": ["AMTRAK", "MNR"],  // Poughkeepsie (equiv: MPOK)
        "STS": ["AMTRAK", "MNR"],  // New Haven-State St (equiv: MNSS)
        // Subway stations not in RouteTopology
        "SA63": ["SUBWAY"],  // 104 St (A)
        "SA64": ["SUBWAY"],  // 111 St (A)
        "SA65": ["SUBWAY"],  // Ozone Park-Lefferts Blvd
    ]

    /// Cached mapping of station codes to their systems, derived from RouteTopology.
    /// Computed once on first access for performance.
    private static let derivedStationSystems: [String: Set<String>] = {
        var mapping: [String: Set<String>] = [:]
        for route in RouteTopology.allRoutes {
            for code in route.stationCodes {
                mapping[code, default: []].insert(route.dataSource)
            }
        }
        return mapping
    }()

    /// Returns the raw system strings that serve a given station.
    /// Priority: 1) Explicit overrides, 2) Derived from RouteTopology, 3) Amtrak-only set
    /// Every station code must be explicitly accounted for. Unknown codes return empty
    /// so they surface as bugs rather than silently defaulting.
    static func systemStringsForStation(_ code: String) -> Set<String> {
        // Check explicit overrides first (for special cases like PATH adjacency)
        if let override = stationSystemOverrides[code] {
            return override
        }
        // Use RouteTopology-derived mapping
        if let derived = derivedStationSystems[code] {
            return derived
        }
        // Amtrak long-distance stations not in RouteTopology
        if amtrakOnlyStations.contains(code) {
            return ["AMTRAK"]
        }
        // Unknown station code — this is a bug. Add the code to the appropriate mapping.
        return []
    }

    /// Amtrak-only stations not present in any RouteTopology route.
    /// Explicitly listed so that unknown station codes surface as bugs rather than silently defaulting.
    private static let amtrakOnlyStations: Set<String> = [
        "ABE", "ACD", "ADM", "AKY", "ALC", "ALD", "ALI", "ALN", "ALP", "ALT", "ALY", "AMS", "ANA", "ARB",
        "ARC", "ARD", "ARK", "ARN", "AST", "ATN", "BAM", "BAR", "BAS", "BBK", "BCV", "BDT", "BEL", "BEN",
        "BER", "BFD", "BFX", "BHM", "BIX", "BKY", "BLF", "BMT", "BNC", "BNF", "BNG", "BNL", "BON", "BRA",
        "BRH", "BRK", "BRL", "BRO", "BTL", "BTN", "BUR", "BWE", "BYN", "CAM", "CBN", "CBR", "CBS", "CDL",
        "CEN", "CHM", "CHW", "CIC", "CIN", "CLA", "CLB", "CLF", "CLM", "CLN", "CLP", "CML", "CMO", "CNV",
        "COI", "COV", "COX", "CPN", "CRF", "CRN", "CRV", "CSN", "CTL", "CUM", "CUT", "CVS", "CWH", "CWT",
        "CYN", "DAN", "DAV", "DBP", "DDG", "DEM", "DER", "DET", "DFB", "DHM", "DLK", "DNK", "DOA", "DOV",
        "DQN", "DRD", "DRT", "DUN", "DVL", "DWT", "DYE", "EDG", "EDM", "EFG", "EKH", "ELK", "ELT", "ELY",
        "EPH", "ERI", "ESM", "ESX", "EVR", "EXR", "FAR", "FAY", "FBG", "FED", "FFV", "FLN", "FMD", "FMG",
        "FMT", "FNO", "FRA", "FRE", "FTC", "FTN", "GAC", "GBB", "GBO", "GCK", "GDL", "GFD", "GFK", "GGW",
        "GJT", "GLE", "GLM", "GLN", "GLP", "GLY", "GMS", "GNB", "GNS", "GRA", "GRI", "GRO", "GRR", "GSC",
        "GTA", "GUA", "GUF", "GUI", "GVB", "GWD", "HAE", "HAS", "HAY", "HAZ", "HBG", "HEM", "HER", "HFD",
        "HFY", "HGD", "HHL", "HIN", "HLD", "HLK", "HMD", "HMI", "HMW", "HNF", "HOL", "HOM", "HOP", "HSU",
        "HUD", "HUN", "HUT", "HVL", "IDP", "IND", "IRV", "JAN", "JEF", "JOL", "JSP", "JST", "JXN", "KAL",
        "KAN", "KEE", "KEL", "KFS", "KIL", "KKI", "KNC", "KNG", "KWD", "LAB", "LAF", "LAG", "LAJ", "LAK",
        "LAP", "LAU", "LBO", "LCH", "LCN", "LDB", "LEE", "LEW", "LFT", "LIB", "LMR", "LMY", "LNK", "LNS",
        "LOD", "LOR", "LPE", "LPS", "LRC", "LSE", "LSV", "LVS", "LVW", "LWA", "LYH", "MAC", "MAL", "MAT",
        "MAY", "MBY", "MCB", "MCD", "MCG", "MCK", "MDN", "MDS", "MDT", "MEI", "MHD", "MHL", "MID", "MIDPA",
        "MIN", "MJY", "MKA", "MKS", "MNG", "MOE", "MOT", "MPK", "MPR", "MRB", "MRC", "MRV", "MSA", "MSS",
        "MTP", "MTR", "MTZ", "MVN", "MVW", "MYS", "MYU", "NBN", "NBU", "NCR", "NDL", "NFK", "NFL", "NFS",
        "NHL", "NHT", "NIB", "NLS", "NOR", "NPN", "NPV", "NRG", "NRK", "OAC", "OCA", "OKC", "OKE", "OKJ",
        "OKL", "OLW", "ONA", "ORB", "ORC", "OSC", "OTM", "OTN", "OXN", "PAG", "PAK", "PBF", "PCT", "PHA",
        "PHN", "PIA", "PIC", "PIT", "PLB", "PLO", "PNT", "POG", "POH", "PON", "POR", "POS", "PRB", "PRC",
        "PRO", "PRV", "PSC", "PSN", "PTC", "PTH", "PUR", "PVL", "PXN", "QAN", "QCY", "RAT", "RDD", "RDW",
        "REN", "RHI", "RIC", "RIV", "RKV", "RLN", "RNK", "ROM", "ROY", "RPH", "RSP", "RSV", "RTE", "RTL",
        "RUD", "RUG", "RVM", "SAB", "SAF", "SAO", "SAR", "SBG", "SBY", "SCA", "SCC", "SCD", "SCH", "SDL",
        "SDY", "SEB", "SED", "SFA", "SFC", "SHR", "SIM", "SJM", "SKN", "SKT", "SKY", "SLQ", "SMC", "SMN",
        "SMT", "SNB", "SNC", "SND", "SNP", "SNS", "SOB", "SOL", "SOP", "SPG", "SPI", "SPL", "SPM", "SPT",
        "SSM", "STA", "STN", "STP", "STW", "SUI", "SVT", "SWB", "TAY", "TCA", "TCL", "THN", "THU",
        "TOH", "TOP", "TPL", "TRI", "TRM", "TUK", "TWO", "TXA", "TYR", "UCA", "VAC", "VAL", "VAN", "VEC",
        "VNC", "VRN", "VRV", "WAB", "WAH", "WAR", "WBG", "WBL", "WDB", "WDL", "WDO", "WEL", "WEM", "WEN",
        "WFD", "WGL", "WHL", "WIC", "WIH", "WIN", "WIP", "WLD", "WLO", "WMH", "WMN", "WND", "WNL", "WNM",
        "WNN", "WNR", "WOB", "WOR", "WPR", "WPS", "WPT", "WRJ", "WSB", "WSP", "WSS", "WTI", "WTN", "WTS",
        "WWD", "YAZ", "YEM", "YUM",
    ]

    // MARK: - Station Code Equivalence

    /// Returns true if two station codes refer to the same physical station.
    /// Handles cross-system equivalents (Amtrak/MNR) and subway complexes.
    static func areEquivalentStations(_ code1: String, _ code2: String) -> Bool {
        if code1 == code2 { return true }
        guard let group = stationEquivalents[code1] else { return false }
        return group.contains(code2)
    }
}

// MARK: - Default Map Region

extension MKCoordinateRegion {
    /// Default map region centered on Newark Penn Station with appropriate zoom level
    /// for viewing the NJ Transit network. Used as the consistent "home" view.
    static let newarkPennDefault = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644), // Newark Penn Station
        span: MKCoordinateSpan(latitudeDelta: 1.5, longitudeDelta: 1.5)
    )
}

