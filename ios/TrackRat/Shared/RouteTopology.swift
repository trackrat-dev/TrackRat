import Foundation
import CoreLocation

/// Defines a transit line as an ordered sequence of station codes.
/// Used for rendering static route topology on the map.
struct RouteLine: Identifiable {
    let id: String
    let name: String
    let dataSource: String  // "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR"
    let stationCodes: [String]

    /// Returns coordinate pairs for drawing polylines between consecutive stations.
    /// Only includes pairs where both stations have known coordinates.
    var coordinatePairs: [(CLLocationCoordinate2D, CLLocationCoordinate2D)] {
        var pairs: [(CLLocationCoordinate2D, CLLocationCoordinate2D)] = []
        for i in 0..<(stationCodes.count - 1) {
            let fromCode = stationCodes[i]
            let toCode = stationCodes[i + 1]
            if let fromCoord = Stations.getCoordinates(for: fromCode),
               let toCoord = Stations.getCoordinates(for: toCode) {
                pairs.append((fromCoord, toCoord))
            }
        }
        return pairs
    }
}

/// Static route topology definitions for all transit systems.
/// These are used to render the rail network on the map without requiring API calls.
struct RouteTopology {

    // MARK: - All Routes

    static let allRoutes: [RouteLine] = njtRoutes + amtrakRoutes + pathRoutes + patcoRoutes + lirrRoutes + mnrRoutes

    // MARK: - NJ Transit Routes

    static let njtRoutes: [RouteLine] = [
        // Northeast Corridor (main line from NY to Trenton)
        RouteLine(
            id: "njt-nec",
            name: "Northeast Corridor",
            dataSource: "NJT",
            stationCodes: ["NY", "SE", "NP", "NA", "NZ", "EZ", "LI", "RH", "MP", "MU", "ED", "NB", "JA", "PJ", "HL", "TR"]
        ),

        // North Jersey Coast Line
        RouteLine(
            id: "njt-njcl",
            name: "North Jersey Coast Line",
            dataSource: "NJT",
            stationCodes: ["NY", "SE", "NP", "NA", "NZ", "EZ", "LI", "RH", "AV", "WB", "PE", "CH", "AM", "HZ", "MI", "RB", "LS", "MK", "LB", "EL", "AH", "AP", "BB", "BS", "LA", "SQ", "PP", "BH"]
        ),

        // Morris & Essex Line (Morristown)
        RouteLine(
            id: "njt-me-morristown",
            name: "Morris & Essex (Morristown)",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "NP", "ND", "BU", "EO", "OG", "HI", "MT", "SO", "MW", "MB", "RT", "ST", "CM", "MA", "CN", "MR", "MX", "TB", "DV", "DO", "HV", "HP", "NT", "OL", "HQ"]
        ),

        // Gladstone Branch (diverges from Summit)
        RouteLine(
            id: "njt-gladstone",
            name: "Gladstone Branch",
            dataSource: "NJT",
            stationCodes: ["ST", "NV", "MH", "BY", "GI", "SG", "GO", "LY", "BI", "BV", "FH", "PC", "GL"]
        ),

        // Raritan Valley Line
        RouteLine(
            id: "njt-rvl",
            name: "Raritan Valley Line",
            dataSource: "NJT",
            stationCodes: ["NP", "EZ", "US", "RL", "XC", "GW", "WF", "FW", "NE", "PF", "DN", "BK", "BW", "SM", "RA", "OR", "WH", "ON", "AN", "HG"]
        ),

        // Montclair-Boonton Line
        RouteLine(
            id: "njt-mobo",
            name: "Montclair-Boonton Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "ND", "WT", "BM", "GG", "MC", "WA", "WG", "UM", "MS", "HS", "UV", "FA", "23", "MV", "LP", "TO", "BN", "ML", "DV"]
        ),

        // Main Line
        RouteLine(
            id: "njt-main",
            name: "Main Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "KG", "LN", "DL", "PS", "IF", "RN", "HW", "RS", "RW", "UF", "WK", "AZ", "RY", "17", "MZ", "SF"]
        ),

        // Bergen County Line
        RouteLine(
            id: "njt-bergen",
            name: "Bergen County Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "RF", "WM", "GD", "PL", "BF", "FZ", "GK", "RW", "UF", "WK", "AZ", "RY", "17", "MZ", "SF"]
        ),

        // Port Jervis Line (extends from Suffern)
        RouteLine(
            id: "njt-port-jervis",
            name: "Port Jervis Line",
            dataSource: "NJT",
            stationCodes: ["SF", "XG", "TC", "RM", "CW", "CB", "OS", "PO"]
        ),

        // Pascack Valley Line
        RouteLine(
            id: "njt-pascack",
            name: "Pascack Valley Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "WR", "TE", "EX", "AS", "NH", "RG", "OD", "EN", "WW", "HD", "WL", "PV", "ZM", "PQ", "NN", "SV"]
        ),

        // Atlantic City Line (simplified - main stops)
        RouteLine(
            id: "njt-atlc",
            name: "Atlantic City Line",
            dataSource: "NJT",
            stationCodes: ["PH", "TR"]  // Limited - add more if coordinates available
        ),

        // Princeton Branch (shuttle from Princeton Junction)
        RouteLine(
            id: "njt-princeton",
            name: "Princeton Branch",
            dataSource: "NJT",
            stationCodes: ["PJ", "PR"]
        )
    ]

    // MARK: - Amtrak Routes

    static let amtrakRoutes: [RouteLine] = [
        // Northeast Corridor (Boston to Washington)
        RouteLine(
            id: "amtrak-nec",
            name: "Northeast Corridor",
            dataSource: "AMTRAK",
            stationCodes: ["BOS", "BBY", "PVD", "KIN", "WLY", "NLC", "OSB", "NHV", "BRP", "STM", "NY", "NP", "TR", "PH", "WI", "BL", "BA", "WS"]
        ),

        // Keystone Service (NY to Harrisburg)
        RouteLine(
            id: "amtrak-keystone",
            name: "Keystone Service",
            dataSource: "AMTRAK",
            stationCodes: ["NY", "NP", "TR", "PH", "PAO", "EXT", "DOW", "COT", "PAR", "LNC", "HAR"]
        ),

        // Silver Service / Carolinian (NEC to Southeast)
        RouteLine(
            id: "amtrak-southeast",
            name: "Silver Service / Carolinian",
            dataSource: "AMTRAK",
            stationCodes: ["WS", "ALX", "RVR", "PTB", "RMT", "WLN", "SEL", "RGH", "CAR", "DNC", "GRB", "HPT", "SAL", "CLT"]
        ),

        // Crescent (Charlotte to Atlanta via Spartanburg/Greenville)
        RouteLine(
            id: "amtrak-crescent",
            name: "Crescent",
            dataSource: "AMTRAK",
            stationCodes: ["CLT", "GAS", "SPB", "GVL", "TOC", "GAI", "ATL"]
        ),

        // Silver Service (Selma to Dillon via Hamlet)
        RouteLine(
            id: "amtrak-silver-south",
            name: "Silver Service (South)",
            dataSource: "AMTRAK",
            stationCodes: ["SEL", "SOU", "HAM", "DIL"]
        ),

        // Coastal Route (Dillon to Jacksonville via Charleston/Savannah)
        RouteLine(
            id: "amtrak-coastal",
            name: "Silver Service (Coastal)",
            dataSource: "AMTRAK",
            stationCodes: ["DIL", "FLO", "KTR", "CHS", "SAV", "JES", "JAX"]
        ),

        // Silver Star (Jacksonville to Tampa)
        RouteLine(
            id: "amtrak-florida",
            name: "Silver Star (Tampa)",
            dataSource: "AMTRAK",
            stationCodes: ["JAX", "PAL", "DLD", "SAN", "WPK", "ORL", "KIS", "WTH", "LKL", "TPA"]
        ),

        // Silver Meteor (Jacksonville to Miami)
        RouteLine(
            id: "amtrak-miami",
            name: "Silver Meteor (Miami)",
            dataSource: "AMTRAK",
            stationCodes: ["JAX", "PAL", "DLD", "SAN", "WPK", "ORL", "KIS", "WPB", "DLB", "FTL", "HLW", "MIA"]
        ),

        // Nationwide long-distance routes
        // California Zephyr (Chicago - Emeryville)
        RouteLine(
            id: "amtrak-zephyr",
            name: "California Zephyr",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "OMA", "DEN", "SLC", "RNO", "TRU", "SAC", "EMY"]
        ),

        // Southwest Chief (Chicago - Los Angeles)
        RouteLine(
            id: "amtrak-chief",
            name: "Southwest Chief",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "KCY", "ABQ", "FLG", "LAX"]
        ),

        // Empire Builder (Chicago - Seattle/Portland)
        RouteLine(
            id: "amtrak-empire-builder",
            name: "Empire Builder",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "MKE", "MSP", "HAV", "GPK", "WFH", "SPK", "SEA"]
        ),

        // Coast Starlight (Seattle - Los Angeles)
        RouteLine(
            id: "amtrak-starlight",
            name: "Coast Starlight",
            dataSource: "AMTRAK",
            stationCodes: ["SEA", "TAC", "PDX", "SLM", "EUG", "SAC", "EMY", "SJC", "SLO", "SBA", "LAX"]
        ),

        // Sunset Limited (New Orleans - Los Angeles)
        RouteLine(
            id: "amtrak-sunset",
            name: "Sunset Limited",
            dataSource: "AMTRAK",
            stationCodes: ["NOL", "HOS", "SAS", "ELP", "TUS", "LAX"]
        ),

        // Texas Eagle (Chicago - San Antonio/Los Angeles)
        RouteLine(
            id: "amtrak-texas-eagle",
            name: "Texas Eagle",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "STL", "LRK", "DAL", "FTW", "AUS", "SAS"]
        ),

        // City of New Orleans (Chicago - New Orleans)
        RouteLine(
            id: "amtrak-city-nola",
            name: "City of New Orleans",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "MEM", "NOL"]
        ),

        // Capitol Limited (Chicago - Washington)
        RouteLine(
            id: "amtrak-capitol",
            name: "Capitol Limited",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "TOL", "CLE", "PGH", "WS"]
        ),

        // Lake Shore Limited (Chicago - New York/Boston)
        RouteLine(
            id: "amtrak-lakeshore",
            name: "Lake Shore Limited",
            dataSource: "AMTRAK",
            stationCodes: ["CHI", "TOL", "CLE", "BUF", "ALB", "NY"]
        ),

        // Pacific Surfliner (San Diego - San Luis Obispo)
        RouteLine(
            id: "amtrak-surfliner",
            name: "Pacific Surfliner",
            dataSource: "AMTRAK",
            stationCodes: ["OLT", "OSD", "SNA", "FUL", "LAX", "SBA", "SLO"]
        ),

        // Cascades (Eugene - Seattle - Vancouver)
        RouteLine(
            id: "amtrak-cascades",
            name: "Cascades",
            dataSource: "AMTRAK",
            stationCodes: ["EUG", "SLM", "PDX", "TAC", "SEA"]
        ),

        // Empire Service (New York - Albany - Buffalo)
        RouteLine(
            id: "amtrak-empire-service",
            name: "Empire Service",
            dataSource: "AMTRAK",
            stationCodes: ["NY", "ALB", "SYR", "ROC", "BUF"]
        )
    ]

    // MARK: - PATH Routes

    static let pathRoutes: [RouteLine] = [
        // Hoboken - 33rd Street
        RouteLine(
            id: "path-hob-33",
            name: "Hoboken - 33rd Street",
            dataSource: "PATH",
            stationCodes: ["PHO", "PCH", "P9S", "P14", "P23", "P33"]
        ),

        // Hoboken - World Trade Center
        RouteLine(
            id: "path-hob-wtc",
            name: "Hoboken - WTC",
            dataSource: "PATH",
            stationCodes: ["PHO", "PNP", "PEX", "PWC"]
        ),

        // Journal Square - 33rd Street
        RouteLine(
            id: "path-jsq-33",
            name: "Journal Square - 33rd Street",
            dataSource: "PATH",
            stationCodes: ["PJS", "PGR", "PNP", "PCH", "P9S", "P14", "P23", "P33"]
        ),

        // Newark - World Trade Center
        RouteLine(
            id: "path-nwk-wtc",
            name: "Newark - WTC",
            dataSource: "PATH",
            stationCodes: ["PNK", "PHR", "PJS", "PGR", "PEX", "PWC"]
        ),

        // Journal Square - 33rd Street via Hoboken
        RouteLine(
            id: "path-jsq-33-hob",
            name: "JSQ - 33rd via Hoboken",
            dataSource: "PATH",
            stationCodes: ["PJS", "PGR", "PNP", "PHO", "PCH", "P9S", "P14", "P23", "P33"]
        ),

        // Newark - Harrison Shuttle
        RouteLine(
            id: "path-nwk-har",
            name: "Newark - Harrison",
            dataSource: "PATH",
            stationCodes: ["PNK", "PHR"]
        )
    ]

    // MARK: - PATCO Route

    static let patcoRoutes: [RouteLine] = [
        // PATCO Speedline (Lindenwold to Center City Philadelphia)
        RouteLine(
            id: "patco-speedline",
            name: "PATCO Speedline",
            dataSource: "PATCO",
            stationCodes: ["LND", "ASD", "WCT", "HDF", "WMT", "CLD", "FRY", "BWY", "CTH", "FKS", "EMK", "NTL", "TWL", "FFL"]
        )
    ]

    // MARK: - LIRR Routes

    static let lirrRoutes: [RouteLine] = [
        // Main Line (Penn Station to Jamaica - trunk for most branches)
        RouteLine(
            id: "lirr-main-trunk",
            name: "Main Line (Trunk)",
            dataSource: "LIRR",
            stationCodes: ["NY", "WDD", "FHL", "KGN", "JAM"]
        ),

        // Babylon Branch
        RouteLine(
            id: "lirr-babylon",
            name: "Babylon Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "VSM", "LYN", "RVC", "BWN", "FPT", "MRK", "BMR", "WGH", "SFD", "MQA", "LMPK", "AVL", "CPG", "LHT", "BTA"]
        ),

        // Hempstead Branch
        RouteLine(
            id: "lirr-hempstead",
            name: "Hempstead Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "QVG", "LHOL", "FPK", "SMR", "NBD", "GCY", "LCLP", "HGN", "LHEM"]
        ),

        // Oyster Bay Branch
        RouteLine(
            id: "lirr-oyster-bay",
            name: "Oyster Bay Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "LMIN", "EWN", "ABT", "RSN", "LGVL", "GHD", "SCF", "GST", "GCV", "LVL", "OBY"]
        ),

        // Ronkonkoma Branch
        RouteLine(
            id: "lirr-ronkonkoma",
            name: "Ronkonkoma Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "LMIN", "CPL", "WBY", "LHVL", "BPG", "LFMD", "PLN", "WYD", "DPK", "BWD", "CI", "RON"]
        ),

        // Montauk Branch (main portion)
        RouteLine(
            id: "lirr-montauk",
            name: "Montauk Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "BSR", "ISP", "GRV", "ODL", "SVL", "PGE", "BPT", "MSY", "LSPK", "WHN", "HBY", "SHN", "BHN", "EHN", "AGT", "MTK"]
        ),

        // Long Beach Branch
        RouteLine(
            id: "lirr-long-beach",
            name: "Long Beach Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "VSM", "LYN", "CAV", "ERY", "ODE", "IPK", "LBH"]
        ),

        // Far Rockaway Branch
        RouteLine(
            id: "lirr-far-rockaway",
            name: "Far Rockaway Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "LLMR", "LTN", "ROS", "VSM", "GBN", "HWT", "WMR", "CHT", "LCE", "IWD", "LFRY"]
        ),

        // West Hempstead Branch
        RouteLine(
            id: "lirr-west-hempstead",
            name: "West Hempstead Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "LSAB", "VSM", "LWWD", "LMVN", "LLVW", "HGN", "WHD"]
        ),

        // Port Washington Branch (doesn't go through Jamaica)
        RouteLine(
            id: "lirr-port-washington",
            name: "Port Washington Branch",
            dataSource: "LIRR",
            stationCodes: ["NY", "WDD", "LSSM", "FLS", "LMHL", "BDY", "ADL", "BSD", "DGL", "LLNK", "GNK", "MHT", "PDM", "PWS"]
        ),

        // Port Jefferson Branch
        RouteLine(
            id: "lirr-port-jefferson",
            name: "Port Jefferson Branch",
            dataSource: "LIRR",
            stationCodes: ["JAM", "LMIN", "LHVL", "SYT", "CSH", "LHUN", "GWN", "NPT", "KPK", "LSTN", "LSJM", "LSBK", "PJN"]
        ),

        // Atlantic Branch (to Atlantic Terminal)
        RouteLine(
            id: "lirr-atlantic",
            name: "Atlantic Branch",
            dataSource: "LIRR",
            stationCodes: ["LAT", "NAV", "ENY", "JAM"]
        ),

        // Grand Central Madison extension
        RouteLine(
            id: "lirr-grand-central",
            name: "Grand Central Madison",
            dataSource: "LIRR",
            stationCodes: ["GCT", "JAM"]
        )
    ]

    // MARK: - Metro-North Routes

    static let mnrRoutes: [RouteLine] = [
        // Hudson Line
        RouteLine(
            id: "mnr-hudson",
            name: "Hudson Line",
            dataSource: "MNR",
            stationCodes: ["GCT", "M125", "MEYS", "MMRH", "MUNH", "MMBL", "MSDV", "MRVD", "MLUD", "MYON", "MGWD", "MGRY", "MHOH", "MDBF", "MARD", "MIRV", "MTTN", "MPHM", "MSCB", "MOSS", "MCRH", "MCRT", "MPKS", "MMAN", "MGAR", "MCSP", "MBRK", "MBCN", "MNHB", "MPOK"]
        ),

        // Harlem Line
        RouteLine(
            id: "mnr-harlem",
            name: "Harlem Line",
            dataSource: "MNR",
            stationCodes: ["GCT", "M125", "MMEL", "MTRM", "MFOR", "MBOG", "MWBG", "MWDL", "MWKF", "MMVW", "MFLT", "MBRX", "MTUC", "MCWD", "MSCD", "MHSD", "MWPL", "MNWP", "MVAL", "MMTP", "MHWT", "MPLV", "MCHP", "MMTK", "MBDH", "MKAT", "MGLD", "MPRD", "MCFL", "MBRS", "MSET", "MPAT", "MPAW", "MAPT", "MHVW", "MDVP", "MTMR", "MWAS"]
        ),

        // New Haven Line (main)
        RouteLine(
            id: "mnr-new-haven",
            name: "New Haven Line",
            dataSource: "MNR",
            stationCodes: ["GCT", "M125", "MMVE", "MPEL", "MNRC", "MLRM", "MMAM", "MHRR", "MRYE", "MPCH", "MGRN", "MCOC", "MRSD", "MODG", "MSTM", "MNOH", "MDAR", "MROW", "MSNW", "MENW", "MWPT", "MGRF", "MSPT", "MFFD", "MFBR", "MBGP", "MSTR", "MMIL", "MWHN", "MNHV", "MNSS"]
        ),

        // New Canaan Branch (includes New Haven trunk: GCT to Stamford junction)
        RouteLine(
            id: "mnr-new-canaan",
            name: "New Canaan Branch",
            dataSource: "MNR",
            stationCodes: [
                "GCT", "M125", "MMVE", "MPEL", "MNRC", "MLRM", "MMAM", "MHRR",
                "MRYE", "MPCH", "MGRN", "MCOC", "MRSD", "MODG",
                "MSTM", "MGLB", "MSPD", "MTMH", "MNCA"
            ]
        ),

        // Danbury Branch (includes New Haven trunk: GCT to South Norwalk junction)
        RouteLine(
            id: "mnr-danbury",
            name: "Danbury Branch",
            dataSource: "MNR",
            stationCodes: [
                "GCT", "M125", "MMVE", "MPEL", "MNRC", "MLRM", "MMAM", "MHRR",
                "MRYE", "MPCH", "MGRN", "MCOC", "MRSD", "MODG", "MSTM", "MNOH",
                "MDAR", "MROW",
                "MSNW", "MMR7", "MWIL", "MCAN", "MBVL", "MRED", "MBTH", "MDBY"
            ]
        ),

        // Waterbury Branch (includes New Haven trunk: GCT to Bridgeport junction)
        RouteLine(
            id: "mnr-waterbury",
            name: "Waterbury Branch",
            dataSource: "MNR",
            stationCodes: [
                "GCT", "M125", "MMVE", "MPEL", "MNRC", "MLRM", "MMAM", "MHRR",
                "MRYE", "MPCH", "MGRN", "MCOC", "MRSD", "MODG", "MSTM", "MNOH",
                "MDAR", "MROW", "MSNW", "MENW", "MWPT", "MGRF", "MSPT", "MFFD",
                "MFBR",
                "MBGP", "MSTR", "MDBS", "MANS", "MSYM", "MBCF", "MNAU", "MWTB"
            ]
        )
    ]

    // MARK: - Station Expansion

    /// Returns all station codes (inclusive) between two stations on a matching route.
    /// Handles both forward and reverse direction. Returns nil if no route contains both stations.
    static func getIntermediateStations(from: String, to: String, dataSource: String) -> [String]? {
        for route in allRoutes where route.dataSource == dataSource {
            guard let fromIndex = route.stationCodes.firstIndex(of: from),
                  let toIndex = route.stationCodes.firstIndex(of: to) else {
                continue
            }
            if fromIndex <= toIndex {
                return Array(route.stationCodes[fromIndex...toIndex])
            } else {
                return Array(route.stationCodes[toIndex...fromIndex].reversed())
            }
        }
        return nil
    }

    /// Expands a list of station codes to include all intermediate stations from route topology.
    /// For each consecutive pair in the input, fills in any skipped stations.
    static func expandStationCodes(_ stopCodes: [String], dataSource: String) -> [String] {
        guard stopCodes.count >= 2 else { return stopCodes }

        var expanded: [String] = []
        for i in 0..<(stopCodes.count - 1) {
            let intermediates = getIntermediateStations(
                from: stopCodes[i], to: stopCodes[i + 1], dataSource: dataSource
            ) ?? [stopCodes[i], stopCodes[i + 1]]

            if expanded.isEmpty {
                expanded.append(contentsOf: intermediates)
            } else {
                expanded.append(contentsOf: intermediates.dropFirst())
            }
        }
        return expanded
    }

    // MARK: - Unique Stations

    /// Returns all unique station codes across all routes (for station annotation rendering)
    static var allStationCodes: Set<String> {
        var codes = Set<String>()
        for route in allRoutes {
            codes.formUnion(route.stationCodes)
        }
        return codes
    }
}
