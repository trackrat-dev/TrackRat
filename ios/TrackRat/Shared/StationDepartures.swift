import Foundation

extension Stations {
    // Supported departure stations - Updated to match backend
    static let departureStations: [(name: String, code: String)] = [
        // Northeast Corridor
        ("New York Penn Station", "NY"),
        ("Hoboken", "HB"),
        // PATH
        ("Hoboken PATH", "PHO"),
        ("World Trade Center", "PWC"),
        ("33rd Street", "P33"),
        ("Journal Square", "PJS"),
        ("Newark PATH", "PNK"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR"),
        ("Long Branch", "LB"),
        ("Plainfield", "PF"),  // Changed from PL to PF
        ("Dunellen", "DN"),
        ("Raritan", "RA"),
        ("Philadelphia", "PH"),
        ("Wilmington DE", "WI"),
        // Mid-Atlantic
        ("Baltimore Station", "BL"),
        ("Washington Union Station", "WS"),
        ("Richmond Staples Mill Road", "RVR"),
        // New England
        ("Springfield", "SPG"),
        // Southeast hubs
        ("Charlotte", "CLT"),
        ("Raleigh", "RGH"),
        ("Savannah", "SAV"),
        ("Jacksonville", "JAX"),
        ("Orlando", "ORL"),
        ("Tampa", "TPA"),
        ("Miami", "MIA"),
        ("Atlanta", "ATL"),
        // LIRR hubs
        ("Jamaica", "JAM"),
        ("Atlantic Terminal", "LAT"),
        ("Grand Central Terminal", "GCT"),
        ("Hicksville", "LHVL"),
        ("Ronkonkoma", "RON"),
        ("Babylon", "BTA"),
        ("Huntington", "LHUN"),
        ("Port Washington", "PWS"),
        ("Long Beach", "LBH"),
        // MNR hubs
        ("Harlem-125th Street", "M125"),
        ("Poughkeepsie", "MPOK"),
        ("Wassaic", "MWAS"),
        ("New Haven", "MNHV"),
        ("Stamford", "MSTM"),
        ("White Plains", "MWPL"),
        ("Croton-Harmon", "MCRH"),

        // NYC Subway hubs
        ("Times Sq-42 St (1/2/3)", "S127"),
        ("14 St-Union Sq (4/5/6)", "S635"),
        ("Atlantic Av-Barclays Ctr (2/3/4)", "S235"),
        ("Fulton St (2/3)", "S229"),
        ("34 St-Herald Sq (B/D/F/M)", "SD17"),
        ("Jay St-MetroTech (A/C/F)", "SA41"),
        ("125 St (1)", "S116"),
        ("Jackson Hts-Roosevelt Av", "SG14"),
        ("Flushing-Main St", "S701"),
        ("59 St-Columbus Circle (1/2)", "S125")
    ]
    
    // Popular destination stations - kept in sync with departure stations
    static var popularDestinations: [(name: String, code: String)] {
        return departureStations
    }
}
