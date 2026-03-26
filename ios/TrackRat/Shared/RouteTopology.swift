import Foundation
import CoreLocation

/// Defines a transit line as an ordered sequence of station codes.
/// Used for rendering static route topology on the map.
struct RouteLine: Identifiable {
    let id: String
    let name: String
    let dataSource: String  // "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"
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

    static let allRoutes: [RouteLine] = njtRoutes + amtrakRoutes + pathRoutes + patcoRoutes + lirrRoutes + mnrRoutes + subwayRoutes + bartRoutes

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
