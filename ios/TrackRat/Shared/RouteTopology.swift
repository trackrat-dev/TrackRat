import Foundation
import CoreLocation

/// Defines a transit line as an ordered sequence of station codes.
/// Used for rendering static route topology on the map.
struct RouteLine: Identifiable {
    let id: String
    let name: String
    let dataSource: String  // "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY", "MBTA"
    let stationCodes: [String]

    /// Human-readable terminal stations, e.g. "New York Penn → Trenton".
    var terminalSubtitle: String? {
        guard let first = stationCodes.first,
              let last = stationCodes.last,
              first != last else { return nil }
        return "\(Stations.displayName(for: first)) – \(Stations.displayName(for: last))"
    }

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

    static let allRoutes: [RouteLine] = njtRoutes + amtrakRoutes + pathRoutes + patcoRoutes + lirrRoutes + mnrRoutes + subwayRoutes + wmataRoutes + bartRoutes + mbtaRoutes + septaRegionalRailRoutes + septaMetroRoutes

    // MARK: - Congestion Map Base Layer

    /// Route topology lines to draw as the white base network on the congestion map for the
    /// user's selected data sources.
    ///
    /// The full network is always drawn (issue #1602). Otherwise a low-frequency system like
    /// Amtrak renders as a handful of scattered congestion segments floating over an empty map,
    /// with no connecting track between them. Live congestion segments are painted on top of
    /// this base layer. This matches the always-on base layer already used by the route-status
    /// map and the system-detail screen.
    static func congestionMapBaseRoutes(selectedDataSources: Set<String>) -> [RouteLine] {
        allRoutes.filter { selectedDataSources.contains($0.dataSource) }
    }

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
            stationCodes: ["SF", "XG", "TC", "RM", "MD", "CW", "CB", "OS", "PO"]
        ),

        // Pascack Valley Line
        RouteLine(
            id: "njt-pascack",
            name: "Pascack Valley Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "WR", "TE", "EX", "AS", "NH", "RG", "OD", "EN", "WW", "HD", "WL", "PV", "ZM", "PQ", "NN", "SV"]
        ),

        // Atlantic City Line
        RouteLine(
            id: "njt-atlc",
            name: "Atlantic City Line",
            dataSource: "NJT",
            stationCodes: ["PH", "PN", "CY", "LW", "AO", "HN", "EH", "AB", "AC"]
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
            stationCodes: ["BOS", "BBY", "PVD", "KIN", "WLY", "NLC", "OSB", "NHV", "BRP", "STM", "NRO", "NY", "NP", "MP", "NB", "PJ", "TR", "CWH", "PHN", "PH", "WI", "BL", "BA", "WS"]
        ),

        // Keystone Service (NY to Harrisburg)
        RouteLine(
            id: "amtrak-keystone",
            name: "Keystone Service",
            dataSource: "AMTRAK",
            stationCodes: ["NY", "NP", "MP", "NB", "PJ", "TR", "CWH", "PHN", "PH", "PAO", "EXT", "DOW", "COT", "PAR", "LNC", "HAR"]
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
            stationCodes: ["NY", "YNY", "CRT", "POU", "RHI", "HUD", "SDY", "ALB", "SYR", "ROC", "BUF"]
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
            name: "Journal Square - 33rd Street via Hoboken",
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

        // Port Washington Branch — Penn Station terminus
        RouteLine(
            id: "lirr-port-washington",
            name: "Port Washington Branch",
            dataSource: "LIRR",
            stationCodes: ["NY", "WDD", "LSSM", "FLS", "LMHL", "BDY", "ADL", "BSD", "DGL", "LLNK", "GNK", "MHT", "PDM", "PWS"]
        ),

        // Port Washington Branch — Grand Central Terminal terminus (via East Side Access)
        RouteLine(
            id: "lirr-port-washington-gct",
            name: "Port Washington Branch",
            dataSource: "LIRR",
            stationCodes: ["GCT", "WDD", "LSSM", "FLS", "LMHL", "BDY", "ADL", "BSD", "DGL", "LLNK", "GNK", "MHT", "PDM", "PWS"]
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

        // Grand Central Madison extension (includes Forest Hills & Kew Gardens stops)
        RouteLine(
            id: "lirr-grand-central",
            name: "Grand Central Madison",
            dataSource: "LIRR",
            stationCodes: ["GCT", "FHL", "KGN", "JAM"]
        ),

        // Belmont Park (seasonal service via Hempstead Branch)
        RouteLine(
            id: "lirr-belmont-park",
            name: "Belmont Park",
            dataSource: "LIRR",
            stationCodes: ["NY", "WDD", "FHL", "KGN", "JAM", "QVG", "BRS", "EMT"]
        ),

        // Greenport Service (eastern extension via Ronkonkoma Branch)
        RouteLine(
            id: "lirr-greenport",
            name: "Greenport Service",
            dataSource: "LIRR",
            stationCodes: ["NY", "WDD", "FHL", "KGN", "JAM", "MAV", "LMIN", "CPL", "WBY", "LHVL", "BPG", "LFMD", "PLN", "WYD", "DPK", "BWD", "CI", "RON", "MFD", "YPK", "RHD", "MAK", "SHD", "GPT"]
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

    // MARK: - NYC Subway Routes

    static let subwayRoutes: [RouteLine] = [
        RouteLine(
            id: "subway-1",
            name: "1 Broadway - 7 Avenue Local",
            dataSource: "SUBWAY",
            stationCodes: ["S142", "S139", "S138", "S137", "S136", "S135", "S134", "S133", "S132", "S131", "S130", "S129", "S128", "S127", "S126", "S125", "S124", "S123", "S122", "S121", "S120", "S119", "S118", "S117", "S116", "S115", "S114", "S113", "S112", "S111", "S110", "S109", "S108", "S107", "S106", "S104", "S103", "S101"]
        ),

        RouteLine(
            id: "subway-2",
            name: "2 7 Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["S247", "S246", "S245", "S244", "S243", "S242", "S241", "S239", "S238", "S237", "S236", "S235", "S234", "S233", "S232", "S231", "S230", "S229", "S228", "S137", "S136", "S135", "S134", "S133", "S132", "S131", "S130", "S129", "S128", "S127", "S126", "S125", "S124", "S123", "S122", "S121", "S120", "S227", "S226", "S225", "S224", "S222", "S221", "S220", "S219", "S218", "S217", "S216", "S215", "S214", "S213", "S212", "S211", "S210", "S209", "S208", "S207", "S206", "S205", "S204", "S201"]
        ),

        RouteLine(
            id: "subway-3",
            name: "3 7 Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["S257", "S256", "S255", "S254", "S253", "S252", "S251", "S250", "S249", "S248", "S239", "S238", "S237", "S236", "S235", "S234", "S233", "S232", "S231", "S230", "S229", "S228", "S137", "S132", "S128", "S127", "S123", "S120", "S227", "S226", "S225", "S224", "S302", "S301"]
        ),

        RouteLine(
            id: "subway-4",
            name: "4 Lexington Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["S257", "S256", "S255", "S254", "S253", "S252", "S251", "S250", "S249", "S248", "S239", "S238", "S237", "S236", "S235", "S234", "S423", "S420", "S419", "S418", "S640", "S639", "S638", "S637", "S636", "S635", "S634", "S633", "S632", "S631", "S630", "S629", "S628", "S627", "S626", "S625", "S624", "S623", "S622", "S621", "S416", "S415", "S414", "S413", "S412", "S411", "S410", "S409", "S408", "S407", "S406", "S405", "S402", "S401"]
        ),

        // Rush-hour Brooklyn extension: 5 trains run on 2-line tracks to Flatbush Av during peak hours
        RouteLine(
            id: "subway-5",
            name: "5 Lexington Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["S247", "S246", "S245", "S244", "S243", "S242", "S241", "S239", "S238", "S237", "S236", "S235", "S234", "S423", "S420", "S419", "S418", "S640", "S639", "S638", "S637", "S636", "S635", "S634", "S633", "S632", "S631", "S630", "S629", "S628", "S627", "S626", "S621", "S416", "S222", "S221", "S220", "S219", "S218", "S217", "S216", "S215", "S214", "S213", "S505", "S504", "S503", "S502", "S501"]
        ),

        RouteLine(
            id: "subway-6",
            name: "6 Lexington Avenue Local",
            dataSource: "SUBWAY",
            stationCodes: ["S640", "S639", "S638", "S637", "S636", "S635", "S634", "S633", "S632", "S631", "S630", "S629", "S628", "S627", "S626", "S625", "S624", "S623", "S622", "S621", "S619", "S618", "S617", "S616", "S615", "S614", "S613", "S612", "S611", "S610", "S609", "S608", "S607", "S606", "S604", "S603", "S602", "S601"]
        ),

        RouteLine(
            id: "subway-6x",
            name: "6X Pelham Bay Park Express",
            dataSource: "SUBWAY",
            stationCodes: ["S640", "S639", "S638", "S637", "S636", "S635", "S634", "S633", "S632", "S631", "S630", "S629", "S628", "S627", "S626", "S625", "S624", "S623", "S622", "S621", "S619", "S613", "S608", "S607", "S606", "S604", "S603", "S602", "S601"]
        ),

        RouteLine(
            id: "subway-7",
            name: "7 Flushing Local",
            dataSource: "SUBWAY",
            stationCodes: ["S726", "S725", "S724", "S723", "S721", "S720", "S719", "S718", "S716", "S715", "S714", "S713", "S712", "S711", "S710", "S709", "S708", "S707", "S706", "S705", "S702", "S701"]
        ),

        RouteLine(
            id: "subway-7x",
            name: "7X Flushing Express",
            dataSource: "SUBWAY",
            stationCodes: ["S726", "S725", "S724", "S723", "S721", "S720", "S719", "S718", "S716", "S715", "S714", "S713", "S712", "S711", "S710", "S707", "S702", "S701"]
        ),

        RouteLine(
            id: "subway-a",
            name: "A 8 Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["SH11", "SH10", "SH09", "SH08", "SH07", "SH06", "SH04", "SH03", "SH02", "SH01", "SA61", "SA60", "SA59", "SA57", "SA55", "SA54", "SA53", "SA52", "SA51", "SA50", "SA49", "SA48", "SA47", "SA46", "SA45", "SA44", "SA43", "SA42", "SA41", "SA40", "SA38", "SA36", "SA34", "SA33", "SA32", "SA31", "SA30", "SA28", "SA27", "SA25", "SA24", "SA22", "SA21", "SA20", "SA19", "SA18", "SA17", "SA16", "SA15", "SA14", "SA12", "SA11", "SA10", "SA09", "SA07", "SA06", "SA05", "SA03", "SA02"]
        ),

        RouteLine(
            id: "subway-b",
            name: "B 6 Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["SD40", "SD39", "SD35", "SD31", "SD28", "SD26", "SD25", "SD24", "SR30", "SD22", "SD21", "SD20", "SD17", "SD16", "SD15", "SD14", "SA24", "SA22", "SA21", "SA20", "SA19", "SA18", "SA17", "SA16", "SA15", "SA14", "SD13", "SD12", "SD11", "SD10", "SD09", "SD08", "SD07", "SD06", "SD05", "SD04", "SD03"]
        ),

        RouteLine(
            id: "subway-c",
            name: "C 8 Avenue Local",
            dataSource: "SUBWAY",
            stationCodes: ["SA55", "SA54", "SA53", "SA52", "SA51", "SA50", "SA49", "SA48", "SA47", "SA46", "SA45", "SA44", "SA43", "SA42", "SA41", "SA40", "SA38", "SA36", "SA34", "SA33", "SA32", "SA31", "SA30", "SA28", "SA27", "SA25", "SA24", "SA22", "SA21", "SA20", "SA19", "SA18", "SA17", "SA16", "SA15", "SA14", "SA12", "SA11", "SA10", "SA09"]
        ),

        RouteLine(
            id: "subway-d",
            name: "D 6 Avenue Express",
            dataSource: "SUBWAY",
            stationCodes: ["SD43", "SB23", "SB22", "SB21", "SB20", "SB19", "SB18", "SB17", "SB16", "SB15", "SB14", "SB13", "SB12", "SR36", "SR35", "SR34", "SR33", "SR32", "SR31", "SR30", "SD22", "SD21", "SD20", "SD17", "SD16", "SD15", "SD14", "SA24", "SA15", "SD13", "SD12", "SD11", "SD10", "SD09", "SD08", "SD07", "SD06", "SD05", "SD04", "SD03", "SD01"]
        ),

        RouteLine(
            id: "subway-e",
            name: "E 8 Avenue Local",
            dataSource: "SUBWAY",
            stationCodes: ["SE01", "SA34", "SA33", "SA32", "SA31", "SA30", "SA28", "SA27", "SA25", "SD14", "SF12", "SF11", "SF09", "SG21", "SG20", "SG19", "SG18", "SG16", "SG15", "SG14", "SG13", "SG12", "SG11", "SG10", "SG09", "SG08", "SF07", "SF06", "SF05", "SG07", "SG06", "SG05"]
        ),

        RouteLine(
            id: "subway-f",
            name: "F Queens Blvd Express/6 Av Local",
            dataSource: "SUBWAY",
            stationCodes: ["SD43", "SD42", "SF39", "SF38", "SF36", "SF35", "SF34", "SF33", "SF32", "SF31", "SF30", "SF29", "SF27", "SF26", "SF25", "SF24", "SF23", "SF22", "SF21", "SF20", "SA41", "SF18", "SF16", "SF15", "SF14", "SD21", "SD20", "SD19", "SD18", "SD17", "SD16", "SD15", "SB10", "SB08", "SB06", "SB04", "SG20", "SG19", "SG18", "SG16", "SG15", "SG14", "SG13", "SG12", "SG11", "SG10", "SG09", "SG08", "SF07", "SF06", "SF05", "SF04", "SF03", "SF02", "SF01"]
        ),

        RouteLine(
            id: "subway-fx",
            name: "FX Brooklyn F Express",
            dataSource: "SUBWAY",
            stationCodes: ["SD43", "SD42", "SF39", "SF38", "SF36", "SF35", "SF34", "SF33", "SF32", "SF31", "SF30", "SF29", "SF27", "SF24", "SA41", "SF18", "SF16", "SF15", "SF14", "SD21", "SD20", "SD19", "SD18", "SD17", "SD16", "SD15", "SF12", "SF11", "SF09", "SG21", "SG14", "SG08", "SF07", "SF06", "SF05", "SF04", "SF03", "SF02", "SF01"]
        ),

        RouteLine(
            id: "subway-fs",
            name: "S Franklin Avenue Shuttle",
            dataSource: "SUBWAY",
            stationCodes: ["SD26", "SS04", "SS03", "SS01"]
        ),

        RouteLine(
            id: "subway-g",
            name: "G Brooklyn-Queens Crosstown",
            dataSource: "SUBWAY",
            stationCodes: ["SF27", "SF26", "SF25", "SF24", "SF23", "SF22", "SF21", "SF20", "SA42", "SG36", "SG35", "SG34", "SG33", "SG32", "SG31", "SG30", "SG29", "SG28", "SG26", "SG24", "SG22"]
        ),

        RouteLine(
            id: "subway-gs",
            name: "S 42 St Shuttle",
            dataSource: "SUBWAY",
            stationCodes: ["S901", "S902"]
        ),

        RouteLine(
            id: "subway-h",
            name: "S Rockaway Park Shuttle",
            dataSource: "SUBWAY",
            stationCodes: ["SH15", "SH14", "SH13", "SH12", "SH04"]
        ),

        RouteLine(
            id: "subway-j",
            name: "J Nassau St Local",
            dataSource: "SUBWAY",
            stationCodes: ["SM23", "SM22", "SM21", "SM20", "SM19", "SM18", "SM16", "SM14", "SM13", "SM12", "SM11", "SJ31", "SJ30", "SJ29", "SJ28", "SJ27", "SJ24", "SJ23", "SJ22", "SJ21", "SJ20", "SJ19", "SJ17", "SJ16", "SJ15", "SJ14", "SJ13", "SJ12", "SG06", "SG05"]
        ),

        RouteLine(
            id: "subway-l",
            name: "L 14 St-Canarsie Local",
            dataSource: "SUBWAY",
            stationCodes: ["SL29", "SL28", "SL27", "SL26", "SL25", "SL24", "SL22", "SL21", "SL20", "SL19", "SL17", "SL16", "SL15", "SL14", "SL13", "SL12", "SL11", "SL10", "SL08", "SL06", "SL05", "SL03", "SL02", "SL01"]
        ),

        RouteLine(
            id: "subway-m",
            name: "M Queens Blvd Local/6 Av Local",
            dataSource: "SUBWAY",
            stationCodes: ["SM01", "SM04", "SM05", "SM06", "SM08", "SM09", "SM10", "SM11", "SM12", "SM13", "SM14", "SM16", "SM18", "SD21", "SD20", "SD19", "SD18", "SD17", "SD16", "SD15", "SD14"]
        ),

        RouteLine(
            id: "subway-n",
            name: "N Broadway Local",
            dataSource: "SUBWAY",
            stationCodes: ["SD43", "SN10", "SN09", "SN08", "SN07", "SN06", "SN05", "SN04", "SN03", "SN02", "SR41", "SR40", "SR39", "SR36", "SR35", "SR34", "SR33", "SR32", "SR31", "SR30", "SR29", "SR28", "SR27", "SR26", "SR25", "SR24", "SR23", "SR22", "SR21", "SR20", "SR19", "SR18", "SR17", "SR16", "SR15", "SR14", "SR13", "SR11", "SR09", "SR08", "SR06", "SR05", "SR04", "SR03", "SR01"]
        ),

        RouteLine(
            id: "subway-q",
            name: "Q Broadway Express",
            dataSource: "SUBWAY",
            stationCodes: ["SD43", "SD42", "SD41", "SD40", "SD39", "SD38", "SD37", "SD35", "SD34", "SD33", "SD32", "SD31", "SD30", "SD29", "SD28", "SD27", "SD26", "SD25", "SD24", "SR30", "SQ01", "SR22", "SR21", "SR20", "SR19", "SR18", "SR17", "SR16", "SR15", "SR14", "SB08", "SQ03", "SQ04", "SQ05"]
        ),

        RouteLine(
            id: "subway-r",
            name: "R Broadway Local",
            dataSource: "SUBWAY",
            stationCodes: ["SR45", "SR44", "SR43", "SR42", "SR41", "SR40", "SR39", "SR36", "SR35", "SR34", "SR33", "SR32", "SR31", "SR30", "SR29", "SR28", "SR27", "SR26", "SR25", "SR24", "SR23", "SR22", "SR21", "SR20", "SR19", "SR18", "SR17", "SR16", "SR15", "SR14", "SR13", "SR11", "SG21", "SG20", "SG19", "SG18", "SG16", "SG15", "SG14", "SG13", "SG12", "SG11", "SG10", "SG09", "SG08"]
        ),

        RouteLine(
            id: "subway-w",
            name: "W Broadway Local",
            dataSource: "SUBWAY",
            stationCodes: ["SN10", "SN09", "SN08", "SN07", "SN06", "SN05", "SN04", "SN03", "SN02", "SR41", "SR40", "SR39", "SR36", "SR35", "SR34", "SR33", "SR32", "SR31", "SR30", "SR29", "SR28", "SR27", "SR26", "SR25", "SR24", "SR23", "SR22", "SR21", "SR20", "SR19", "SR18", "SR17", "SR16", "SR15", "SR14", "SR13", "SR11", "SR09", "SR08", "SR06", "SR05", "SR04", "SR03", "SR01"]
        ),

        RouteLine(
            id: "subway-si",
            name: "SIR Staten Island Railway",
            dataSource: "SUBWAY",
            stationCodes: ["SS09", "SS11", "SS13", "SS14", "SS15", "SS16", "SS17", "SS18", "SS19", "SS20", "SS21", "SS22", "SS23", "SS24", "SS25", "SS26", "SS27", "SS28", "SS29", "SS30", "SS31"]
        ),

        RouteLine(
            id: "subway-z",
            name: "Z Nassau St Express",
            dataSource: "SUBWAY",
            stationCodes: ["SM23", "SM22", "SM21", "SM20", "SM19", "SM18", "SM16", "SM11", "SJ30", "SJ28", "SJ27", "SJ24", "SJ23", "SJ21", "SJ20", "SJ17", "SJ15", "SJ14", "SJ12", "SG06", "SG05"]
        ),

    ]

    // MARK: - WMATA (DC Metro) Routes

    static let wmataRoutes: [RouteLine] = [
        RouteLine(
            id: "wmata-red",
            name: "Red Line",
            dataSource: "WMATA",
            stationCodes: ["A15", "A14", "A13", "A12", "A11", "A10", "A09", "A08", "A07", "A06", "A05", "A04", "A03", "A02", "A01", "B35", "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11"]
        ),
        RouteLine(
            id: "wmata-orange",
            name: "Orange Line",
            dataSource: "WMATA",
            stationCodes: ["K08", "K07", "K06", "K05", "K04", "K03", "K02", "K01", "C05", "C04", "C03", "C02", "C01", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13"]
        ),
        RouteLine(
            id: "wmata-silver",
            name: "Silver Line",
            dataSource: "WMATA",
            stationCodes: ["N12", "N11", "N10", "N09", "N08", "N07", "N06", "N04", "N03", "N02", "N01", "K05", "K04", "K03", "K02", "K01", "C05", "C04", "C03", "C02", "C01", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "G01", "G02", "G03", "G04", "G05"]
        ),
        RouteLine(
            id: "wmata-blue",
            name: "Blue Line",
            dataSource: "WMATA",
            stationCodes: ["J03", "J02", "C13", "C12", "C11", "C10", "C09", "C08", "C07", "C06", "C05", "C04", "C03", "C02", "C01", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "G01", "G02", "G03", "G04", "G05"]
        ),
        RouteLine(
            id: "wmata-yellow",
            name: "Yellow Line",
            dataSource: "WMATA",
            stationCodes: ["C15", "C14", "C13", "C12", "C11", "C10", "C09", "C08", "C07", "F03", "F02", "F01", "E01", "E02", "E03", "E04", "E05", "E06"]
        ),
        RouteLine(
            id: "wmata-green",
            name: "Green Line",
            dataSource: "WMATA",
            stationCodes: ["F11", "F10", "F09", "F08", "F07", "F06", "F05", "F04", "F03", "F02", "F01", "E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10"]
        ),
    ]

    // MARK: - BART Routes

    static let bartRoutes: [RouteLine] = [
        RouteLine(
            id: "bart-red",
            name: "Richmond - SFO/Millbrae",
            dataSource: "BART",
            stationCodes: ["BART_RICH", "BART_DELN", "BART_PLZA", "BART_NBRK", "BART_DBRK", "BART_ASHB", "BART_MCAR", "BART_19TH", "BART_12TH", "BART_WOAK", "BART_EMBR", "BART_MONT", "BART_POWL", "BART_CIVC", "BART_16TH", "BART_24TH", "BART_GLEN", "BART_BALB", "BART_DALY", "BART_COLM", "BART_SSAN", "BART_SBRN", "BART_MLBR", "BART_SFIA"]
        ),
        RouteLine(
            id: "bart-orange",
            name: "Berryessa - Richmond",
            dataSource: "BART",
            stationCodes: ["BART_BERY", "BART_MLPT", "BART_WARM", "BART_FRMT", "BART_UCTY", "BART_SHAY", "BART_HAYW", "BART_BAYF", "BART_SANL", "BART_COLS", "BART_FTVL", "BART_LAKE", "BART_12TH", "BART_19TH", "BART_MCAR", "BART_ASHB", "BART_DBRK", "BART_NBRK", "BART_PLZA", "BART_DELN", "BART_RICH"]
        ),
        RouteLine(
            id: "bart-yellow",
            name: "Antioch - SFO/Millbrae",
            dataSource: "BART",
            stationCodes: ["BART_ANTC", "BART_PCTR", "BART_PITT", "BART_NCON", "BART_CONC", "BART_PHIL", "BART_WCRK", "BART_LAFY", "BART_ORIN", "BART_ROCK", "BART_MCAR", "BART_19TH", "BART_12TH", "BART_WOAK", "BART_EMBR", "BART_MONT", "BART_POWL", "BART_CIVC", "BART_16TH", "BART_24TH", "BART_GLEN", "BART_BALB", "BART_DALY", "BART_COLM", "BART_SSAN", "BART_SBRN", "BART_MLBR", "BART_SFIA"]
        ),
        RouteLine(
            id: "bart-green",
            name: "Berryessa - Daly City",
            dataSource: "BART",
            stationCodes: ["BART_BERY", "BART_MLPT", "BART_WARM", "BART_FRMT", "BART_UCTY", "BART_SHAY", "BART_HAYW", "BART_BAYF", "BART_SANL", "BART_COLS", "BART_FTVL", "BART_LAKE", "BART_WOAK", "BART_EMBR", "BART_MONT", "BART_POWL", "BART_CIVC", "BART_16TH", "BART_24TH", "BART_GLEN", "BART_BALB", "BART_DALY"]
        ),
        RouteLine(
            id: "bart-blue",
            name: "Dublin/Pleasanton - Daly City",
            dataSource: "BART",
            stationCodes: ["BART_DUBL", "BART_WDUB", "BART_CAST", "BART_BAYF", "BART_SANL", "BART_COLS", "BART_FTVL", "BART_LAKE", "BART_12TH", "BART_19TH", "BART_MCAR", "BART_WOAK", "BART_EMBR", "BART_MONT", "BART_POWL", "BART_CIVC", "BART_16TH", "BART_24TH", "BART_GLEN", "BART_BALB", "BART_DALY"]
        ),
        RouteLine(
            id: "bart-oak",
            name: "Oakland Airport - Coliseum",
            dataSource: "BART",
            stationCodes: ["BART_COLS", "BART_OAKL"]
        ),
    ]

    // MARK: - MBTA Commuter Rail Routes

    static let mbtaRoutes: [RouteLine] = [
        RouteLine(
            id: "mbta-fairmount",
            name: "Fairmount Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BNMK", "BUPH", "BFCG", "BTLB", "BMRT", "BBHA", "BFMT", "BRDV"]
        ),

        RouteLine(
            id: "mbta-fitchburg",
            name: "Fitchburg Line",
            dataSource: "MBTA",
            stationCodes: ["BNST", "BPOR", "BBMT", "BWAV", "BWTH", "BBNR", "BKGN", "BHST", "BSLH", "BLIN", "BCON", "BWCN", "BSAC", "BLIT", "BAYE", "BSHR", "BNLM", "BFIT", "BWAC"]
        ),

        RouteLine(
            id: "mbta-foxboro",
            name: "Foxboro Event Service",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BDCC", "BFOX"]
        ),

        RouteLine(
            id: "mbta-franklin",
            name: "Franklin/Foxboro Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BRUG", "BFHL", "BHPK", "BRDV", "BEND", "BDCC", "BISL", "BNWD", "BNWC", "BWDG", "BPLM", "BWAL", "BNFK", "BFRK", "BFPK"]
        ),

        RouteLine(
            id: "mbta-greenbush",
            name: "Greenbush Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BJFK", "BQNC", "BBRN", "BWLE", "BEWY", "BWHI", "BNAN", "BCOH", "BNSC", "BGRB"]
        ),

        RouteLine(
            id: "mbta-haverhill",
            name: "Haverhill Line",
            dataSource: "MBTA",
            stationCodes: ["BNST", "BMAL", "BOKG", "BWYH", "BMCP", "BMHG", "BGNW", "BWAK", "BRDG", "BNWI", "BBVL", "BAND", "BLAW", "BBRD", "BHAV"]
        ),

        RouteLine(
            id: "mbta-kingston",
            name: "Kingston Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BJFK", "BQNC", "BBRN", "BSWY", "BABI", "BWHT", "BHAN", "BHLX", "BKNG", "BPLY"]
        ),

        RouteLine(
            id: "mbta-lowell",
            name: "Lowell Line",
            dataSource: "MBTA",
            stationCodes: ["BNST", "BWMF", "BWDM", "BWNC", "BMSH", "BAWB", "BWLM", "BNBL", "BLOW"]
        ),

        RouteLine(
            id: "mbta-needham",
            name: "Needham Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BRUG", "BFHL", "BRSV", "BBLV", "BHLD", "BWRX", "BHRS", "BNJN", "BNDC", "BNDH"]
        ),

        RouteLine(
            id: "mbta-newbedford",
            name: "Fall River/New Bedford Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BJFK", "BQNC", "BBRN", "BHLR", "BMTL", "BBRO", "BCMP", "BBDG", "BMID", "BETN", "BFTW", "BFRD", "BCST", "BNBD"]
        ),

        RouteLine(
            id: "mbta-middleborough",
            name: "Middleborough/Lakeville Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BJFK", "BQNC", "BBRN", "BHLR", "BMTL", "BBRO", "BCMP", "BBDG", "BLKV", "BMID"]
        ),

        RouteLine(
            id: "mbta-newburyport",
            name: "Newburyport Branch",
            dataSource: "MBTA",
            stationCodes: ["BNST", "BCHE", "BRWK", "BLNI", "BSWP", "BSLM", "BBEV", "BNBV", "BHWN", "BIPS", "BROW", "BNBP"]
        ),

        RouteLine(
            id: "mbta-rockport",
            name: "Rockport Branch",
            dataSource: "MBTA",
            stationCodes: ["BNST", "BCHE", "BRWK", "BLNI", "BSWP", "BSLM", "BBEV", "BMTS", "BPRC", "BBFM", "BMCH", "BWGL", "BGLO", "BRPT"]
        ),

        RouteLine(
            id: "mbta-providence",
            name: "Providence/Stoughton Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BRUG", "BFHL", "BHPK", "BRDV", "RTE", "BCJN", "BSHA", "BMAN", "BATT", "BSAT", "BPCF", "PVD", "BTFG", "BWKF"]
        ),

        RouteLine(
            id: "mbta-stoughton",
            name: "Stoughton Branch",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BRUG", "BFHL", "BHPK", "BRDV", "RTE", "BCJN", "BCNC", "BSTO"]
        ),

        RouteLine(
            id: "mbta-worcester",
            name: "Framingham/Worcester Line",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBY", "BLDN", "BBLN", "BNVL", "BWNT", "BAUB", "BWFM", "BWHL", "BWSQ", "BNTC", "BWNA", "BFRM", "BASH", "BSBO", "BWSB", "BGRF", "WOR"]
        ),

        RouteLine(
            id: "mbta-capeflyer",
            name: "CapeFLYER",
            dataSource: "MBTA",
            stationCodes: ["BOS", "BBRN", "BBRO", "BLKV", "BWRV", "BBZB", "BBNE", "BHYN"]
        ),
    ]

    // MARK: - SEPTA Regional Rail Routes

    static let septaRegionalRailRoutes: [RouteLine] = [
        RouteLine(
            id: "SEPTA-AIR",
            name: "Airport Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90401", "SEPR90402", "SEPR90403", "SEPR90404", "SEPR90405", "SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-CHE",
            name: "Chestnut Hill East Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90009", "SEPR90712", "SEPR90713", "SEPR90714", "SEPR90715", "SEPR90716", "SEPR90717", "SEPR90718", "SEPR90719", "SEPR90720"]
        ),
        RouteLine(
            id: "SEPTA-CHW",
            name: "Chestnut Hill West Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90801", "SEPR90802", "SEPR90803", "SEPR90804", "SEPR90805", "SEPR90806", "SEPR90807", "SEPR90808", "SEPR90809", "SEPR90810", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-CYN",
            name: "Cynwyd Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90001", "SEPR90002", "SEPR90003", "SEPR90004", "SEPR90005"]
        ),
        RouteLine(
            id: "SEPTA-FOX",
            name: "Fox Chase Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90009", "SEPR90811", "SEPR90812", "SEPR90813", "SEPR90814", "SEPR90815"]
        ),
        RouteLine(
            id: "SEPTA-LAN",
            name: "Lansdale/Doylestown Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90008", "SEPR90009", "SEPR90407", "SEPR90408", "SEPR90409", "SEPR90410", "SEPR90411", "SEPR90523", "SEPR90524", "SEPR90525", "SEPR90526", "SEPR90527", "SEPR90528", "SEPR90529", "SEPR90530", "SEPR90531", "SEPR90539", "SEPR90532", "SEPR90533", "SEPR90534", "SEPR90535", "SEPR90536", "SEPR90537", "SEPR90538"]
        ),
        RouteLine(
            id: "SEPTA-MED",
            name: "Media/Wawa Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90300", "SEPR90301", "SEPR90302", "SEPR90303", "SEPR90304", "SEPR90305", "SEPR90306", "SEPR90307", "SEPR90308", "SEPR90309", "SEPR90310", "SEPR90311", "SEPR90312", "SEPR90313", "SEPR90314", "SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-NOR",
            name: "Manayunk/Norristown Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90008", "SEPR90218", "SEPR90219", "SEPR90220", "SEPR90221", "SEPR90222", "SEPR90223", "SEPR90224", "SEPR90225", "SEPR90226", "SEPR90227", "SEPR90228"]
        ),
        RouteLine(
            id: "SEPTA-PAO",
            name: "Paoli/Thorndale Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90501", "SEPR90502", "SEPR90503", "SEPR90504", "SEPR90505", "SEPR90506", "SEPR90507", "SEPR90508", "SEPR90509", "SEPR90510", "SEPR90511", "SEPR90512", "SEPR90513", "SEPR90514", "SEPR90515", "SEPR90516", "SEPR90517", "SEPR90518", "SEPR90519", "SEPR90520", "SEPR90521", "SEPR90522", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-TRE",
            name: "Trenton Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90701", "SEPR90702", "SEPR90703", "SEPR90704", "SEPR90705", "SEPR90706", "SEPR90707", "SEPR90708", "SEPR90709", "SEPR90710", "SEPR90711", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-WAR",
            name: "Warminster Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90009", "SEPR90407", "SEPR90408", "SEPR90409", "SEPR90410", "SEPR90411", "SEPR90412", "SEPR90413", "SEPR90414", "SEPR90415", "SEPR90416", "SEPR90417"]
        ),
        RouteLine(
            id: "SEPTA-WIL",
            name: "Wilmington/Newark Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90201", "SEPR90202", "SEPR90203", "SEPR90204", "SEPR90205", "SEPR90206", "SEPR90207", "SEPR90208", "SEPR90209", "SEPR90210", "SEPR90211", "SEPR90212", "SEPR90213", "SEPR90214", "SEPR90215", "SEPR90216", "SEPR90217", "SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007"]
        ),
        RouteLine(
            id: "SEPTA-WTR",
            name: "West Trenton Line",
            dataSource: "SEPTA_RR",
            stationCodes: ["SEPR90406", "SEPR90004", "SEPR90005", "SEPR90006", "SEPR90007", "SEPR90407", "SEPR90408", "SEPR90409", "SEPR90410", "SEPR90315", "SEPR90316", "SEPR90317", "SEPR90318", "SEPR90319", "SEPR90320", "SEPR90321", "SEPR90322", "SEPR90323", "SEPR90324", "SEPR90325", "SEPR90326", "SEPR90327"]
        )
    ]

    // MARK: - SEPTA Metro Routes

    static let septaMetroRoutes: [RouteLine] = [
        RouteLine(
            id: "SEPTA-B1",
            name: "Broad Street Line Local",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM20965", "SEPM33027", "SEPM1272", "SEPM1273", "SEPM1274", "SEPM140", "SEPM142", "SEPM2439", "SEPM1276", "SEPM1277", "SEPM20966", "SEPM1278", "SEPM1279", "SEPM1280", "SEPM33029", "SEPM1282", "SEPM1283", "SEPM1284", "SEPM1285", "SEPM1286", "SEPM20967", "SEPM152"]
        ),
        RouteLine(
            id: "SEPTA-B2",
            name: "Broad Street Line Express",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM20965", "SEPM82", "SEPM140", "SEPM20966", "SEPM1279", "SEPM1280", "SEPM1281", "SEPM1282", "SEPM152"]
        ),
        RouteLine(
            id: "SEPTA-B3",
            name: "Broad-Ridge Spur",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM20965", "SEPM82", "SEPM140", "SEPM2439", "SEPM20966", "SEPM1278", "SEPM2440", "SEPM2457"]
        ),
        RouteLine(
            id: "SEPTA-D1",
            name: "Route 101",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM15497", "SEPM15319", "SEPM18597", "SEPM1938", "SEPM18598", "SEPM18599", "SEPM15322", "SEPM1939", "SEPM18600", "SEPM18601", "SEPM1940", "SEPM15349", "SEPM18602", "SEPM16402", "SEPM18603", "SEPM18604", "SEPM18605", "SEPM30607", "SEPM18606", "SEPM15355", "SEPM18614", "SEPM1943", "SEPM18607", "SEPM1944", "SEPM20024", "SEPM15358", "SEPM18608", "SEPM1946", "SEPM18609", "SEPM18610", "SEPM15379", "SEPM18611", "SEPM18612", "SEPM18613", "SEPM1947"]
        ),
        RouteLine(
            id: "SEPTA-D2",
            name: "Route 102",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM15497", "SEPM15319", "SEPM18597", "SEPM1938", "SEPM18598", "SEPM18599", "SEPM15322", "SEPM1939", "SEPM18600", "SEPM18601", "SEPM1940", "SEPM15325", "SEPM15326", "SEPM15327", "SEPM15328", "SEPM1959", "SEPM15329", "SEPM15330", "SEPM18636", "SEPM12048", "SEPM10011", "SEPM1961", "SEPM4726", "SEPM15333", "SEPM2099", "SEPM20431"]
        ),
        RouteLine(
            id: "SEPTA-G1",
            name: "63rd-Girard to Richmond-Westmorelnd",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM341", "SEPM12196", "SEPM20979", "SEPM20981", "SEPM20982", "SEPM12218", "SEPM20983", "SEPM20984", "SEPM650", "SEPM25779", "SEPM20986", "SEPM20988", "SEPM20989", "SEPM20991", "SEPM31540", "SEPM24038", "SEPM31347", "SEPM23992", "SEPM481", "SEPM342", "SEPM20993", "SEPM20994", "SEPM20995", "SEPM20996", "SEPM20998", "SEPM20999", "SEPM21001", "SEPM21002", "SEPM343", "SEPM21005", "SEPM21006", "SEPM21008", "SEPM30290", "SEPM21009", "SEPM21010", "SEPM30791", "SEPM21014", "SEPM21016", "SEPM21017", "SEPM21018", "SEPM21019", "SEPM21021", "SEPM21022", "SEPM30291", "SEPM21025", "SEPM344", "SEPM21026", "SEPM21027", "SEPM21028", "SEPM30550", "SEPM21030", "SEPM21032", "SEPM21033", "SEPM21035", "SEPM21037", "SEPM21038", "SEPM345", "SEPM21040", "SEPM21041", "SEPM21042", "SEPM21481", "SEPM21044"]
        ),
        RouteLine(
            id: "SEPTA-L1",
            name: "Market-Frankford Line All Stops",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM416", "SEPM2446", "SEPM2447", "SEPM2448", "SEPM2449", "SEPM2450", "SEPM2451", "SEPM2452", "SEPM2453", "SEPM21532", "SEPM1392", "SEPM2455", "SEPM2456", "SEPM2457", "SEPM2458", "SEPM428", "SEPM2459", "SEPM353", "SEPM2460", "SEPM2461", "SEPM2462", "SEPM797", "SEPM60", "SEPM2463", "SEPM838", "SEPM2464", "SEPM217", "SEPM61"]
        ),
        RouteLine(
            id: "SEPTA-M1",
            name: "Norristown High Speed Line Local",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM416", "SEPM1917", "SEPM1918", "SEPM1919", "SEPM1908", "SEPM1921", "SEPM30519", "SEPM1923", "SEPM1924", "SEPM1925", "SEPM1902", "SEPM1927", "SEPM1900", "SEPM1929", "SEPM1930", "SEPM1931", "SEPM1932", "SEPM1895", "SEPM1934", "SEPM1935", "SEPM1892", "SEPM30520"]
        ),
        RouteLine(
            id: "SEPTA-T1",
            name: "13th St to 63rd-Malvern/Overbrook",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM31294", "SEPM20610", "SEPM20611", "SEPM20612", "SEPM20613", "SEPM20614", "SEPM20615", "SEPM15271", "SEPM20616", "SEPM20617", "SEPM20618", "SEPM20619", "SEPM20622", "SEPM20623", "SEPM20624", "SEPM20625", "SEPM20626", "SEPM20627", "SEPM277", "SEPM20628", "SEPM20630", "SEPM20631", "SEPM20632", "SEPM20633", "SEPM20634", "SEPM20635", "SEPM21422", "SEPM21423", "SEPM21424", "SEPM279", "SEPM20636", "SEPM20638", "SEPM32722", "SEPM20639", "SEPM20640", "SEPM20641", "SEPM20642", "SEPM20643", "SEPM20645", "SEPM20646", "SEPM31140", "SEPM283"]
        ),
        RouteLine(
            id: "SEPTA-T2",
            name: "Route 34",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM20932", "SEPM20704", "SEPM599", "SEPM20859", "SEPM20860", "SEPM20861", "SEPM20862", "SEPM20863", "SEPM20864", "SEPM20865", "SEPM20866", "SEPM20867", "SEPM20868", "SEPM20869", "SEPM600", "SEPM20870", "SEPM20871", "SEPM20872", "SEPM20873", "SEPM20874", "SEPM20875", "SEPM20876", "SEPM20804", "SEPM30820", "SEPM21457", "SEPM22127", "SEPM672", "SEPM22128", "SEPM22129", "SEPM21248", "SEPM20731", "SEPM20732", "SEPM20642", "SEPM20643", "SEPM20645", "SEPM20646", "SEPM31140", "SEPM283"]
        ),
        RouteLine(
            id: "SEPTA-T3",
            name: "Route 13",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM305", "SEPM32523", "SEPM20768", "SEPM20770", "SEPM20771", "SEPM20772", "SEPM20773", "SEPM20774", "SEPM20775", "SEPM20776", "SEPM20777", "SEPM20778", "SEPM20779", "SEPM20781", "SEPM20782", "SEPM20843", "SEPM319", "SEPM20785", "SEPM20784", "SEPM20786", "SEPM20787", "SEPM20788", "SEPM320", "SEPM20791", "SEPM20792", "SEPM20793", "SEPM20794", "SEPM20795", "SEPM20796", "SEPM20797", "SEPM321", "SEPM20789", "SEPM20790", "SEPM20799", "SEPM20800", "SEPM20801", "SEPM20802", "SEPM20804", "SEPM21456", "SEPM30820", "SEPM21457", "SEPM22127", "SEPM672", "SEPM22128", "SEPM22129", "SEPM21248", "SEPM20731", "SEPM20732", "SEPM20642", "SEPM20643", "SEPM20645", "SEPM20646", "SEPM31140", "SEPM283"]
        ),
        RouteLine(
            id: "SEPTA-T4",
            name: "Route 11",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM305", "SEPM24568", "SEPM20697", "SEPM20698", "SEPM20699", "SEPM20700", "SEPM20701", "SEPM20702", "SEPM20703", "SEPM20704", "SEPM20705", "SEPM20706", "SEPM20707", "SEPM20708", "SEPM20709", "SEPM20710", "SEPM20711", "SEPM20712", "SEPM20713", "SEPM20714", "SEPM20715", "SEPM20717", "SEPM20716", "SEPM20718", "SEPM20719", "SEPM20720", "SEPM20721", "SEPM20722", "SEPM21208", "SEPM20723", "SEPM20724", "SEPM20725", "SEPM297", "SEPM20726", "SEPM20958", "SEPM20727", "SEPM20728", "SEPM20729", "SEPM20804", "SEPM21456", "SEPM30820", "SEPM21457", "SEPM22127", "SEPM672", "SEPM22128", "SEPM22129", "SEPM21248", "SEPM20731", "SEPM20732", "SEPM20642", "SEPM20643", "SEPM20645", "SEPM20646", "SEPM31140", "SEPM283"]
        ),
        RouteLine(
            id: "SEPTA-T5",
            name: "Route 36",
            dataSource: "SEPTA_METRO",
            stationCodes: ["SEPM612", "SEPM605", "SEPM20927", "SEPM20929", "SEPM20931", "SEPM611", "SEPM20932", "SEPM20933", "SEPM20934", "SEPM20935", "SEPM20936", "SEPM20937", "SEPM20938", "SEPM20939", "SEPM20940", "SEPM20941", "SEPM20942", "SEPM20943", "SEPM20944", "SEPM20946", "SEPM20947", "SEPM20948", "SEPM20949", "SEPM20950", "SEPM20951", "SEPM20952", "SEPM20954", "SEPM20955", "SEPM20957", "SEPM20726", "SEPM20727", "SEPM20728", "SEPM20729", "SEPM20804", "SEPM21456", "SEPM30820", "SEPM21457", "SEPM22127", "SEPM672", "SEPM22128", "SEPM22129", "SEPM21248", "SEPM20731", "SEPM20732", "SEPM20642", "SEPM20643", "SEPM20645", "SEPM20646", "SEPM31140", "SEPM283"]
        )
    ]

    // MARK: - Station Expansion

    /// Returns all station codes (inclusive) between two stations on a matching route.
    /// Handles both forward and reverse direction. Returns nil if no route contains both stations.
    /// Picks the route with the fewest intermediate stations to avoid cross-route contamination
    /// (e.g., local stops inserted when following an express train).
    static func getIntermediateStations(from: String, to: String, dataSource: String) -> [String]? {
        var bestResult: [String]?
        var bestDistance = Int.max

        for route in allRoutes where route.dataSource == dataSource {
            guard let fromIndex = route.stationCodes.firstIndex(of: from),
                  let toIndex = route.stationCodes.firstIndex(of: to) else {
                continue
            }
            let distance = abs(toIndex - fromIndex)
            if distance < bestDistance {
                bestDistance = distance
                if fromIndex <= toIndex {
                    bestResult = Array(route.stationCodes[fromIndex...toIndex])
                } else {
                    bestResult = Array(route.stationCodes[toIndex...fromIndex].reversed())
                }
            }
        }
        return bestResult
    }

    /// Expands a list of station codes to include all intermediate stations from route topology.
    /// For each consecutive pair in the input, fills in any skipped stations.
    /// When a pair isn't on the same route, chains through known hub stations
    /// (e.g., LIRR Penn → Huntington bridges via Jamaica).
    static func expandStationCodes(_ stopCodes: [String], dataSource: String) -> [String] {
        guard stopCodes.count >= 2 else { return stopCodes }

        var expanded: [String] = []
        for i in 0..<(stopCodes.count - 1) {
            let from = stopCodes[i]
            let to = stopCodes[i + 1]
            let intermediates = getIntermediateStations(from: from, to: to, dataSource: dataSource)
                ?? intermediatesViaHub(from: from, to: to, dataSource: dataSource)
                ?? [from, to]

            if expanded.isEmpty {
                expanded.append(contentsOf: intermediates)
            } else {
                expanded.append(contentsOf: intermediates.dropFirst())
            }
        }
        return expanded
    }

    /// Bridges `from`→`to` by chaining through a hub station when no single route
    /// contains both. Returns nil if no hub connects them in two legs.
    /// Collapses overlapping trunk stations that appear in both legs beyond the hub.
    private static func intermediatesViaHub(from: String, to: String, dataSource: String) -> [String]? {
        for hub in hubStations(for: dataSource) where hub != from && hub != to {
            guard let leg1 = getIntermediateStations(from: from, to: hub, dataSource: dataSource),
                  let leg2 = getIntermediateStations(from: hub, to: to, dataSource: dataSource) else {
                continue
            }
            let tail = Array(leg2.dropFirst())
            var result = leg1
            for code in tail {
                if let existing = result.lastIndex(of: code) {
                    result = Array(result[...existing])
                } else {
                    result.append(code)
                }
            }
            return result
        }
        return nil
    }

    /// Hub stations where multiple branches converge. Used to bridge cross-branch
    /// station pairs whose path isn't on any single route in `allRoutes`.
    /// LIRR's branches all meet at Jamaica (except the Port Washington Branch,
    /// which already includes NY/GCT directly).
    private static func hubStations(for dataSource: String) -> [String] {
        switch dataSource {
        case "LIRR": return ["JAM"]
        default: return []
        }
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

    /// Finds all route lines that contain both station codes for a given data source.
    /// Returns routes where both stations appear (any direction).
    static func routesContaining(from: String, to: String, dataSource: String) -> [RouteLine] {
        let candidates = allRoutes.filter { $0.dataSource == dataSource }
        return candidates.filter { route in
            route.stationCodes.contains(from) && route.stationCodes.contains(to)
        }
    }

    /// Finds the route line that contains both station codes for a given data source.
    /// Returns the first matching route, preferring routes where both stations appear
    /// in the correct order (from before to).
    /// Expands via station equivalents for cross-platform transfers (e.g., G→L at Metropolitan Av).
    static func routeContaining(from: String, to: String, dataSource: String) -> RouteLine? {
        let candidates = allRoutes.filter { $0.dataSource == dataSource }

        // Try direct codes first, then expand via station equivalents
        let fromCodes = Stations.stationEquivalents[from] ?? [from]
        let toCodes = Stations.stationEquivalents[to] ?? [to]
        let codePairs = [(from, to)] + fromCodes.flatMap { f in toCodes.compactMap { t in
            (f == from && t == to) ? nil : (f, t)
        }}

        for (f, t) in codePairs {
            // Prefer a route where both stations exist and from appears before to
            for route in candidates {
                if let fromIdx = route.stationCodes.firstIndex(of: f),
                   let toIdx = route.stationCodes.firstIndex(of: t),
                   fromIdx < toIdx {
                    return route
                }
            }

            // Fall back to any route containing both stations (reverse direction)
            for route in candidates {
                if route.stationCodes.contains(f) && route.stationCodes.contains(t) {
                    return route
                }
            }
        }

        return nil
    }
}
