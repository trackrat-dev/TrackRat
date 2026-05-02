import Foundation

/// Lookup of NYC subway lines (the colored letter/number bullets) by station code.
///
/// MTA's official line bullets are rendered as colored discs with a single character.
/// Internally, route IDs in `RouteTopology` use suffixes like `7X` (Flushing Express)
/// or `FS`/`GS`/`H` (shuttle variants). Riders see them on platforms as the base
/// bullet — `7`, `F`, or `S` — so we collapse those variants when building chips.
enum SubwayLines {

    /// Per-line bullet color, matching MTA's official branding (sourced from
    /// `scripts/generate_subway_data.py:OFFICIAL_ROUTE_COLORS`).
    static let lineColor: [String: String] = [
        "1": "#EE352E", "2": "#EE352E", "3": "#EE352E",
        "4": "#00933C", "5": "#00933C", "6": "#00933C",
        "7": "#B933AD",
        "A": "#0039A6", "C": "#0039A6", "E": "#0039A6",
        "B": "#FF6319", "D": "#FF6319", "F": "#FF6319", "M": "#FF6319",
        "G": "#6CBE45",
        "J": "#996633", "Z": "#996633",
        "L": "#A7A9AC",
        "N": "#FCCC0A", "Q": "#FCCC0A", "R": "#FCCC0A", "W": "#FCCC0A",
        "S": "#808183",
        "SI": "#1D2E86",
    ]

    /// Lines serving a station (or any platform in its complex), in MTA bullet order.
    /// Returns an empty array for non-subway codes or stations not on any route.
    static func lines(forStationCode code: String) -> [String] {
        return linesByCode[code] ?? []
    }

    /// Maps a `RouteTopology` subway route id to the bullet a rider sees.
    /// `subway-7x` → `7`, `subway-fs`/`subway-gs`/`subway-h` → `S`, `subway-si` → `SI`.
    /// Returns nil for non-subway ids.
    static func displayBullet(forRouteId routeId: String) -> String? {
        guard routeId.hasPrefix(routeIdPrefix) else { return nil }
        return displayBullet(forLineCode: String(routeId.dropFirst(routeIdPrefix.count)))
    }

    /// Maps a backend line code (e.g., `7X`, `FS`, `Q`) to the bullet a rider sees.
    /// Express variants collapse to their local bullet, shuttles all become `S`.
    /// Lowercase is accepted and uppercased.
    static func displayBullet(forLineCode rawCode: String) -> String {
        let raw = rawCode.uppercased()
        if raw == "FS" || raw == "GS" || raw == "H" { return "S" }
        if raw == "SI" { return "SI" }
        if raw.count == 2, raw.hasSuffix("X") { return String(raw.dropLast()) }
        return raw
    }

    // MARK: - Internal

    private static let routeIdPrefix = "subway-"

    /// Manual additions where MTA's GTFS static feed underreports service
    /// patterns that genuinely share a platform. Mirrors the backend's
    /// `MANUAL_STATION_ROUTE_ADDITIONS` in `scripts/generate_subway_data.py`.
    private static let manualLineAdditions: [String: Set<String>] = [
        // Canal St BMT Broadway bridge platform: shared by Q (always) and N
        // (via Manhattan Bridge during weekday daytime). GTFS only lists Q.
        "SQ01": ["N"],
    ]

    /// Built once at first access. For each station code in any subway route,
    /// the union of bullets from every route serving any platform in the station's
    /// complex (via `Stations.stationEquivalents`).
    static let linesByCode: [String: [String]] = {
        // Step 1: per-station bullets directly from route topology.
        var raw: [String: Set<String>] = [:]
        for route in RouteTopology.subwayRoutes {
            guard let bullet = displayBullet(forRouteId: route.id) else { continue }
            for code in route.stationCodes {
                raw[code, default: []].insert(bullet)
            }
        }
        for (code, extras) in manualLineAdditions {
            raw[code, default: []].formUnion(extras)
        }

        // Step 2: union across station complexes so any code in a complex returns
        // bullets for every platform. Rider thinks "transfer at 14 St-Union Sq" —
        // they don't care which platform code the API used.
        var result: [String: [String]] = [:]
        for (code, _) in raw {
            let group = Stations.stationEquivalents[code] ?? [code]
            var combined: Set<String> = []
            for member in group {
                combined.formUnion(raw[member] ?? [])
            }
            result[code] = sortBullets(combined)
        }
        return result
    }()

    /// MTA bullet sort: numerals (ascending), then letters (alphabetical), then
    /// `S` for shuttles, then `SI` for Staten Island Railway. Matches signage
    /// convention and the ordering used by `_format_route_suffix` in the generator.
    private static func sortBullets(_ bullets: Set<String>) -> [String] {
        return bullets.sorted { a, b in
            let aRank = sortRank(a)
            let bRank = sortRank(b)
            if aRank != bRank { return aRank < bRank }
            return a < b
        }
    }

    private static func sortRank(_ bullet: String) -> Int {
        if Int(bullet) != nil { return 0 }    // numerals first
        if bullet == "S" { return 2 }         // shuttles after letters
        if bullet == "SI" { return 3 }        // SIR last
        return 1                              // letter routes
    }
}
