import Foundation

extension Stations {
    // Supported departure stations - Updated to match backend
    static let departureStations: [(name: String, code: String)] = [
        // Northeast Corridor
        ("New York Penn Station", "NY"),
        ("Hoboken", "HB"),
        // PATH
        ("World Trade Center", "PWC"),
        ("33rd Street", "P33"),
        ("Journal Square", "PJS"),
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
        ("Springfield, MA", "SPG"),
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
        ("Huntington LIRR", "LHUN"),
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

        // MBTA Commuter Rail hubs
        ("Boston South", "BOS"),
        ("North Station", "BNST"),
        ("Boston Back Bay", "BBY"),
        ("Worcester Union", "WOR"),
        ("Providence", "PVD"),
        ("Braintree", "BBRN"),
        ("Lowell", "BLOW"),
        ("Haverhill MBTA", "BHAV"),
        ("Newburyport", "BNBP"),
        ("Fitchburg", "BFIT"),

        // NYC Subway hubs
        ("Times Sq-42 St", "S127"),
        ("14 St-Union Sq", "S635"),
        ("Atlantic Av-Barclays Ctr", "S235"),
        ("Fulton St (2/3/4/5/A/C/J/Z)", "S229"),
        ("34 St-Herald Sq", "SD17"),
        ("Jay St-MetroTech", "SA41"),
        ("125 St", "S116"),
        ("Jackson Hts-Roosevelt Av", "S710"),
        ("Flushing-Main St", "S701"),
        ("59 St-Columbus Circle", "S125"),
        // WMATA (DC Metro) - key hub stations
        ("Metro Center", "A01"),
        ("Gallery Pl-Chinatown", "B01"),
        ("Union Station", "B03"),
        ("L'Enfant Plaza", "D03"),
        ("Pentagon", "C07"),
        ("Rosslyn", "C05"),
        ("Shady Grove", "A15"),
        ("Glenmont", "B11"),
        ("Vienna/Fairfax-GMU", "K08"),
        ("New Carrollton", "D13"),
        ("Franconia-Springfield", "J03"),
        ("Huntington", "C15"),
        ("Greenbelt", "E10"),
        ("Branch Ave", "F11"),
        ("Ashburn", "N12"),
        ("Downtown Largo", "G05")
    ]
}
