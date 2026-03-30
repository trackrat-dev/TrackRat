package com.trackrat.android.data.models

/**
 * Static station data for TrackRat
 * Matches the iOS app's supported stations exactly (synced with ios/TrackRat/Shared/Stations.swift)
 */
object Stations {

    /**
     * Main departure stations supported by the app
     * Matches iOS Stations.departureStations
     */
    val DEPARTURE_STATIONS = listOf(
        // Northeast Corridor
        Station("NY", "New York Penn Station"),
        Station("HB", "Hoboken"),
        Station("MP", "Metropark"),
        Station("PJ", "Princeton Junction"),
        Station("HL", "Hamilton"),
        Station("TR", "Trenton"),
        Station("LB", "Long Branch"),
        Station("PF", "Plainfield"),
        Station("DN", "Dunellen"),
        Station("RA", "Raritan"),
        Station("PH", "Philadelphia"),
        Station("WI", "Wilmington Station"),
        // Mid-Atlantic
        Station("BL", "Baltimore Station"),
        Station("WS", "Washington Union Station"),
        Station("RVR", "Richmond Staples Mill Road"),
        // Southeast hubs
        Station("CLT", "Charlotte"),
        Station("RGH", "Raleigh"),
        Station("SAV", "Savannah"),
        Station("JAX", "Jacksonville"),
        Station("ORL", "Orlando"),
        Station("TPA", "Tampa"),
        Station("MIA", "Miami"),
        Station("ATL", "Atlanta")
    )

    /**
     * All stations sorted alphabetically
     * Matches iOS Stations.all (complete list of ~144 stations)
     */
    val ALL_STATIONS = listOf(
        // Major Hub Stations
        Station("NY", "New York Penn Station"),
        Station("NP", "Newark Penn Station"),
        Station("HB", "Hoboken"),
        Station("SE", "Secaucus Upper Lvl"),
        Station("TS", "Secaucus Lower Lvl"),
        Station("SC", "Secaucus Concourse"),
        Station("TR", "Trenton"),
        Station("PH", "Philadelphia"),

        // Northeast Corridor Line
        Station("PJ", "Princeton Junction"),
        Station("PR", "Princeton"),
        Station("HL", "Hamilton"),
        Station("MP", "Metropark"),
        Station("NB", "New Brunswick"),
        Station("ED", "Edison"),
        Station("MU", "Metuchen"),
        Station("RH", "Rahway"),
        Station("LI", "Linden"),
        Station("EZ", "Elizabeth"),
        Station("NZ", "North Elizabeth"),
        Station("NA", "Newark Airport"),
        Station("ND", "Newark Broad Street"),

        // North Jersey Coast Line
        Station("WB", "Woodbridge"),
        Station("PE", "Perth Amboy"),
        Station("CH", "South Amboy"),
        Station("AM", "Aberdeen-Matawan"),
        Station("HZ", "Hazlet"),
        Station("MI", "Middletown"),
        Station("RB", "Red Bank"),
        Station("LS", "Little Silver"),
        Station("MK", "Monmouth Park"),
        Station("LB", "Long Branch"),
        Station("EL", "Elberon"),
        Station("AH", "Allenhurst"),
        Station("AP", "Asbury Park"),
        Station("BB", "Bradley Beach"),
        Station("BS", "Belmar"),
        Station("LA", "Spring Lake"),
        Station("SQ", "Manasquan"),
        Station("PP", "Point Pleasant Beach"),
        Station("BH", "Bay Head"),

        // Morris & Essex Lines
        Station("ST", "Summit"),
        Station("CM", "Chatham"),
        Station("MA", "Madison"),
        Station("CN", "Convent Station"),
        Station("MR", "Morristown"),
        Station("MX", "Morris Plains"),
        Station("DV", "Denville"),
        Station("DO", "Dover"),
        Station("TB", "Mount Tabor"),
        Station("HV", "Mount Arlington"),
        Station("HP", "Lake Hopatcong"),
        Station("NT", "Netcong"),
        Station("OL", "Mount Olive"),
        Station("HQ", "Hackettstown"),
        Station("MB", "Millburn"),
        Station("RT", "Short Hills"),
        Station("SO", "South Orange"),
        Station("MW", "Maplewood"),
        Station("OG", "Orange"),
        Station("EO", "East Orange"),
        Station("BU", "Brick Church"),
        Station("HI", "Highland Avenue"),
        Station("MV", "Mountain View"),

        // Gladstone Branch
        Station("MH", "Murray Hill"),
        Station("NV", "New Providence"),
        Station("BY", "Berkeley Heights"),
        Station("GI", "Gillette"),
        Station("SG", "Stirling"),
        Station("GO", "Millington"),
        Station("LY", "Lyons"),
        Station("BI", "Basking Ridge"),
        Station("BV", "Bernardsville"),
        Station("FH", "Far Hills"),
        Station("PC", "Peapack"),
        Station("GL", "Gladstone"),

        // Raritan Valley Line
        Station("US", "Union"),
        Station("RL", "Roselle Park"),
        Station("XC", "Cranford"),
        Station("GW", "Garwood"),
        Station("WF", "Westfield"),
        Station("FW", "Fanwood"),
        Station("NE", "Netherwood"),
        Station("PF", "Plainfield"),
        Station("DN", "Dunellen"),
        Station("BK", "Bound Brook"),
        Station("BW", "Bridgewater"),
        Station("SM", "Somerville"),
        Station("RA", "Raritan"),
        Station("HG", "High Bridge"),
        Station("AN", "Annandale"),
        Station("ON", "Lebanon"),
        Station("WH", "White House"),
        Station("OR", "North Branch"),

        // Main/Bergen County Lines
        Station("KG", "Kingsland"),
        Station("LN", "Lyndhurst"),
        Station("DL", "Delawanna"),
        Station("PS", "Passaic"),
        Station("IF", "Clifton"),
        Station("RN", "Paterson"),
        Station("HW", "Hawthorne"),
        Station("RS", "Glen Rock Main Line"),
        Station("GK", "Glen Rock Boro Hall"),
        Station("RW", "Ridgewood"),
        Station("UF", "Ho-Ho-Kus"),
        Station("WK", "Waldwick"),
        Station("AZ", "Allendale"),
        Station("RY", "Ramsey Main St"),
        Station("17", "Ramsey Route 17"),
        Station("MZ", "Mahwah"),
        Station("SF", "Suffern"),
        Station("BF", "Fair Lawn-Broadway"),
        Station("FZ", "Radburn Fair Lawn"),
        Station("GD", "Garfield"),
        Station("PL", "Plauderville"),
        Station("RF", "Rutherford"),
        Station("WM", "Wesmont"),

        // Montclair-Boonton Line
        Station("BM", "Bloomfield"),
        Station("GG", "Glen Ridge"),
        Station("MC", "Bay Street"),
        Station("WA", "Walnut Street"),
        Station("HS", "Montclair Heights"),
        Station("UV", "Montclair State U"),
        Station("UM", "Upper Montclair"),
        Station("MS", "Mountain Avenue"),
        Station("WG", "Watchung Avenue"),
        Station("WT", "Watsessing Avenue"),
        Station("FA", "Little Falls"),
        Station("23", "Wayne-Route 23"),
        Station("MT", "Mountain Station"),
        Station("BN", "Boonton"),
        Station("ML", "Mountain Lakes"),
        Station("LP", "Lincoln Park"),
        Station("TO", "Towaco"),
        Station("GA", "Great Notch"),

        // Pascack Valley Line
        Station("WR", "Wood Ridge"),
        Station("TE", "Teterboro"),
        Station("EX", "Essex Street"),
        Station("AS", "Anderson Street"),
        Station("NH", "New Bridge Landing"),
        Station("RG", "River Edge"),
        Station("OD", "Oradell"),
        Station("EN", "Emerson"),
        Station("WW", "Westwood"),
        Station("HD", "Hillsdale"),
        Station("WL", "Woodcliff Lake"),
        Station("PV", "Park Ridge"),
        Station("ZM", "Montvale"),
        Station("PQ", "Pearl River"),
        Station("NN", "Nanuet"),
        Station("SV", "Spring Valley"),

        // Port Jervis Line
        Station("XG", "Sloatsburg"),
        Station("TC", "Tuxedo"),
        Station("RM", "Harriman"),
        Station("MD", "Middletown NY"),
        Station("CW", "Salisbury Mills-Cornwall"),
        Station("CB", "Campbell Hall"),
        Station("OS", "Otisville"),
        Station("PO", "Port Jervis"),

        // Additional NJ Transit Stations
        Station("AV", "Avenel"),
        Station("JA", "Jersey Avenue"),

        // Pennsylvania Stations (Keystone Service)
        Station("MIDPA", "Middletown PA"),
        Station("ELT", "Elizabethtown"),
        Station("MJY", "Mount Joy"),
        Station("PKB", "Parkesburg"),
        Station("COT", "Coatesville"),
        Station("DOW", "Downingtown"),
        Station("EXT", "Exton"),
        Station("PAO", "Paoli"),

        // Amtrak Northeast Corridor
        Station("BOS", "Boston South"),
        Station("BBY", "Boston Back Bay"),
        Station("PVD", "Providence"),
        Station("KIN", "Kingston"),
        Station("WLY", "Westerly"),
        Station("NLC", "New London"),
        Station("OSB", "Old Saybrook"),
        Station("NHV", "New Haven"),
        Station("BRP", "Bridgeport"),
        Station("STM", "Stamford"),
        Station("BL", "Baltimore Station"),
        Station("BA", "BWI Thurgood Marshall Airport"),
        Station("WS", "Washington Union Station"),
        Station("WI", "Wilmington Station"),

        // Additional Amtrak Stations
        Station("HFD", "Hartford"),
        Station("MDN", "Meriden"),
        Station("WFD", "Wallingford"),
        Station("WNL", "Windsor Locks"),
        Station("SPG", "Springfield"),
        Station("CLA", "Claremont"),
        Station("DOV", "Dover NH"),
        Station("DHM", "Durham-UNH"),
        Station("EXR", "Exeter"),
        Station("NCR", "New Carrollton"),
        Station("ABE", "Aberdeen"),
        Station("ALX", "Alexandria"),
        Station("CVS", "Charlottesville"),
        Station("LOR", "Lorton"),
        Station("NFK", "Norfolk"),
        Station("RVM", "Richmond Main Street"),
        Station("RVR", "Richmond Staples Mill Road"),
        Station("RNK", "Roanoke"),
        Station("HAR", "Harrisburg"),
        Station("LNC", "Lancaster"),

        // Southeast Amtrak Stations (Silver Star/Meteor and Carolinian/Piedmont routes)
        Station("CLT", "Charlotte"),
        Station("RGH", "Raleigh"),
        Station("GRB", "Greensboro"),
        Station("DNC", "Durham"),
        Station("RMT", "Rocky Mount"),
        Station("WLN", "Wilson"),
        Station("CAR", "Cary"),
        Station("SOU", "Southern Pines"),
        Station("HPT", "High Point"),
        Station("SAL", "Salisbury"),
        Station("GAS", "Gastonia"),
        Station("HAM", "Hamlet"),
        Station("SEL", "Selma-Smithfield"),
        Station("PTB", "Petersburg"),
        Station("CHS", "Charleston"),
        Station("SPB", "Spartanburg"),
        Station("GVL", "Greenville"),
        Station("KTR", "Kingstree"),
        Station("FLO", "Florence"),
        Station("DIL", "Dillon"),
        Station("CSN", "Clemson"),
        Station("SAV", "Savannah"),
        Station("ATL", "Atlanta"),
        Station("JES", "Jesup"),
        Station("GAI", "Gainesville GA"),
        Station("TOC", "Toccoa"),
        Station("JAX", "Jacksonville"),
        Station("MIA", "Miami"),
        Station("ORL", "Orlando"),
        Station("TPA", "Tampa"),
        Station("FTL", "Fort Lauderdale"),
        Station("WPB", "West Palm Beach"),
        Station("KIS", "Kissimmee"),
        Station("LKL", "Lakeland"),
        Station("WPK", "Winter Park FL"),
        Station("DLD", "DeLand"),
        Station("SAN", "Sanford FL"),
        Station("HLW", "Hollywood FL"),
        Station("DLB", "Delray Beach"),
        Station("WLD", "Waldo"),
        Station("OCA", "Ocala"),
        Station("WTH", "Winter Haven"),
        Station("PAL", "Palatka"),
        Station("THU", "Thurmond")
    ).sortedBy { it.name }
    
    /**
     * Get a station by code
     */
    fun getStation(code: String): Station? {
        return ALL_STATIONS.find { it.code == code }
    }
    
    /**
     * Get station name by code
     */
    fun getStationName(code: String): String {
        return getStation(code)?.name ?: code
    }
    
    /**
     * Search stations by name or code
     */
    fun search(query: String): List<Station> {
        val lowerQuery = query.lowercase()
        return ALL_STATIONS.filter {
            it.code.lowercase().contains(lowerQuery) ||
            it.name.lowercase().contains(lowerQuery)
        }
    }
}