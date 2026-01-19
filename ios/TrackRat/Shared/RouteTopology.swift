import Foundation
import CoreLocation

/// Defines a transit line as an ordered sequence of station codes.
/// Used for rendering static route topology on the map.
struct RouteLine: Identifiable {
    let id: String
    let name: String
    let dataSource: String  // "NJT", "AMTRAK", "PATH", "PATCO"
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

    static let allRoutes: [RouteLine] = njtRoutes + amtrakRoutes + pathRoutes + patcoRoutes

    // MARK: - NJ Transit Routes

    static let njtRoutes: [RouteLine] = [
        // Northeast Corridor (main line from NY to Trenton)
        RouteLine(
            id: "njt-nec",
            name: "Northeast Corridor",
            dataSource: "NJT",
            stationCodes: ["NY", "SE", "NP", "EZ", "NZ", "LI", "RH", "MP", "MU", "ED", "NB", "JA", "PJ", "HL", "TR"]
        ),

        // North Jersey Coast Line
        RouteLine(
            id: "njt-njcl",
            name: "North Jersey Coast Line",
            dataSource: "NJT",
            stationCodes: ["NY", "SE", "NP", "EZ", "RH", "AV", "WB", "PE", "CH", "AM", "HZ", "MI", "RB", "LS", "MK", "LB", "EL", "AH", "AP", "BB", "BS", "LA", "SQ", "PP", "BH"]
        ),

        // Morris & Essex Line (Morristown)
        RouteLine(
            id: "njt-me-morristown",
            name: "Morris & Essex (Morristown)",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "NP", "ND", "BU", "EO", "OG", "HI", "MT", "SO", "MW", "MB", "RT", "ST", "CM", "MA", "CN", "MR", "MX", "DV", "TB", "HV", "HP", "NT", "OL", "HQ"]
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

        // Main/Bergen County Line
        RouteLine(
            id: "njt-main-bergen",
            name: "Main/Bergen County Line",
            dataSource: "NJT",
            stationCodes: ["HB", "SE", "KG", "LN", "DL", "PS", "IF", "RN", "HW", "RS", "GK", "RW", "UF", "WK", "AZ", "RY", "17", "MZ", "SF"]
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
            stationCodes: ["NY", "NP", "TR", "PH", "PAO", "EXT", "DOW", "COT", "PKB", "LNC", "HAR"]
        ),

        // Silver Service / Carolinian (NEC to Southeast)
        RouteLine(
            id: "amtrak-southeast",
            name: "Silver Service / Carolinian",
            dataSource: "AMTRAK",
            stationCodes: ["WS", "ALX", "RVR", "PTB", "RMT", "WLN", "SEL", "RGH", "CAR", "DNC", "GRB", "HPT", "SAL", "CLT"]
        ),

        // Silver Meteor / Star (to Florida)
        RouteLine(
            id: "amtrak-florida",
            name: "Silver Meteor / Star",
            dataSource: "AMTRAK",
            stationCodes: ["CLT", "SPB", "GVL", "TOC", "GAI", "ATL", "JES", "SAV", "CHS", "KTR", "FLO", "DIL", "JAX", "PAL", "DLD", "SAN", "WPK", "ORL", "KIS", "LKL", "WTH", "TPA"]
        ),

        // Silver Meteor (Miami branch)
        RouteLine(
            id: "amtrak-miami",
            name: "Silver Meteor (Miami)",
            dataSource: "AMTRAK",
            stationCodes: ["JAX", "PAL", "DLD", "SAN", "WPK", "ORL", "KIS", "WPB", "DLB", "FTL", "HLW", "MIA"]
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
