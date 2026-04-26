import Foundation
import CoreLocation
import MapKit

struct Stations {
    /// Default cap on station search results — enough for a typical scrollable list
    /// without overwhelming the picker. Callers that classify results into multiple
    /// buckets (e.g., `searchGrouped`) may oversample with a higher `limit`.
    static let defaultSearchLimit = 12

    static func search(_ query: String, limit: Int = defaultSearchLimit) -> [String] {
        guard !query.isEmpty else { return [] }
        let q = query.lowercased()
        let prefixMatches = all.filter { $0.lowercased().hasPrefix(q) }
        let substringMatches = all.filter {
            !$0.lowercased().hasPrefix(q) && $0.lowercased().contains(q)
        }
        return Array((prefixMatches + substringMatches).prefix(limit))
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
            return "PR"  // Princeton (Dinky); Princeton Junction is "PJ"
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
        // MBTA stations shared with Amtrak (both systems serve these)
        "BOS": ["AMTRAK", "MBTA"],   // South Station
        "BBY": ["AMTRAK", "MBTA"],   // Back Bay
        "PVD": ["AMTRAK", "MBTA"],   // Providence
        "RTE": ["AMTRAK", "MBTA"],   // Route 128
        "WOR": ["AMTRAK", "MBTA"],   // Worcester
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
        // Metra stations not in RouteTopology
        if metraStations.contains(code) {
            return ["METRA"]
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

    /// Metra (Chicago) stations not present in any RouteTopology route.
    private static let metraStations: Set<String> = [
        "103RD-BEV", "103RD-UP", "107TH-BEV", "107TH-UP", "111TH-BEV", "111TH-UP", "115TH-BEV", "119TH-BEV",
        "123RD-BEV", "143RD-SWS", "147TH-UP", "153RD-SWS", "179TH-SWS", "18TH-UP", "211TH-UP", "27TH-UP",
        "35TH", "47TH-UP", "51ST-53RD", "55-56-57TH", "59TH-UP", "63RD-UP", "75TH-UP", "79TH-SC",
        "79TH-UP", "83RD-SC", "83RD-UP", "87TH-SC", "87TH-UP", "91ST-BEV", "91ST-UP", "93RD-SC",
        "95TH-BEV", "95TH-UP", "99TH-BEV", "ANTIOCH", "ARLINGTNHT", "ARLINGTNPK", "ASHBURN", "ASHLAND",
        "AURORA", "BARRINGTON", "BARTLETT", "BELLWOOD", "BELMONT", "BENSENVIL", "BERKELEY", "BERWYN",
        "BIGTIMBER", "BLUEISLAND", "BNWESTERN", "BRAESIDE", "BRAINERD", "BROOKFIELD", "BRYNMAWR", "BUFFGROVE",
        "BURROAK", "CALUMET", "CARY", "CENTRALST", "CHICRIDGE", "CICERO", "CLARNDNHIL", "CLYBOURN",
        "COLLEGEAVE", "CONGRESSPK", "CRYSTAL", "CUMBERLAND", "CUS", "DEERFIELD", "DEEROAD", "DESPLAINES",
        "EDGEBROOK", "EDISONPK", "ELBURN", "ELGIN", "ELMHURST", "ELMWOODPK", "EVANSTON", "FAIRVIEWDG",
        "FLOSSMOOR", "FORESTGLEN", "FOXLAKE", "FOXRG", "FRANKLIN", "FRANKLINPK", "FTSHERIDAN", "GALEWOOD",
        "GENEVA", "GLADSTONEP", "GLENCOE", "GLENELLYN", "GLENVIEW", "GOLF", "GRAND-CIC", "GRAYLAND",
        "GRAYSLAKE", "GRESHAM", "GRTLAKES", "HALSTED", "HANOVERP", "HANSONPK", "HARLEM", "HARVARD",
        "HARVEY", "HAZELCREST", "HEALY", "HICKORYCRK", "HIGHLANDPK", "HIGHLANDS", "HIGHWOOD", "HINSDALE",
        "HOLLYWOOD", "HOMEWOOD", "HUBARDWOOD", "INDIANHILL", "INGLESIDE", "IRVINGPK", "ITASCA", "IVANHOE",
        "JEFFERSONP", "JOLIET", "KEDZIE", "KENILWORTH", "KENOSHA", "KENSINGTN", "LAFOX", "LAGRANGE",
        "LAKEBLUFF", "LAKECOOKRD", "LAKEFRST", "LAKEVILLA", "LARAWAY", "LAVERGNE", "LEMONT", "LIBERTYVIL",
        "LISLE", "LKFOREST", "LOCKPORT", "LOMBARD", "LONGLAKE", "LONGWOOD", "LSS", "MAINST",
        "MAINST-DG", "MANHATTAN", "MANNHEIM", "MARS", "MATTESON", "MAYFAIR", "MAYWOOD", "MCCORMICK",
        "MCHENRY", "MEDINAH", "MELROSEPK", "MIDLOTHIAN", "MILLENNIUM", "MOKENA", "MONTCLARE", "MORTONGRV",
        "MTPROSPECT", "MUNDELEIN", "MUSEUM", "NAPERVILLE", "NATIONALS", "NBROOK", "NCHICAGO", "NCSGRAYSLK",
        "NEWLENOX", "NGLENVIEW", "NORWOODP", "OAKFOREST", "OAKLAWN", "OAKPARK", "OHARE", "OLYMPIA",
        "OTC", "PALATINE", "PALOSHTS", "PALOSPARK", "PARKRIDGE", "PETERSON", "PINGREE", "PRAIRCROSS",
        "PRAIRIEST", "PRAIRIEVW", "PRAIRIEXNG", "PROSPECTHG", "RACINE", "RAVENSWOOD", "RAVINIA", "RAVINIAPK",
        "RICHTON", "RIVERDALE", "RIVERGROVE", "RIVERSIDE", "RIVRFOREST", "ROBBINS", "ROGERPK", "ROMEOVILLE",
        "ROSELLE", "ROSEMONT", "ROUNDLAKE", "ROUNDLKBCH", "ROUTE59", "SCHAUM", "SCHILLERPK", "SOUTHSHORE",
        "STATEST", "STEWARTRID", "STONEAVE", "STONYISLND", "SUMMIT", "TINLEY80TH", "TINLEYPARK", "UNIVERSITY",
        "VANBUREN", "VERMONT", "VERNON", "VILLAPARK", "WASHHGTS", "WAUKEGAN", "WCHICAGO", "WESTERNAVE",
        "WESTMONT", "WESTSPRING", "WHEATON", "WHEELING", "WHINSDALE", "WILLOWSPRN", "WILMETTE", "WINDSORPK",
        "WINFIELD", "WINNETKA", "WINTHROP", "WOODDALE", "WOODSTOCK", "WORTH", "WPULLMAN", "WRIGHTWOOD",
        "ZION",
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

    /// Returns a new region adjusted so the intended area is visible in the top half
    /// of the screen, accounting for a bottom sheet covering ~50% of the display.
    /// Shifts center southward by half the latitude span and doubles the latitude span
    /// so the original extent occupies the visible top portion above the sheet.
    func adjustedForBottomSheet() -> MKCoordinateRegion {
        MKCoordinateRegion(
            center: CLLocationCoordinate2D(
                latitude: center.latitude - span.latitudeDelta / 2,
                longitude: center.longitude
            ),
            span: MKCoordinateSpan(
                latitudeDelta: span.latitudeDelta * 2,
                longitudeDelta: span.longitudeDelta
            )
        )
    }
}

