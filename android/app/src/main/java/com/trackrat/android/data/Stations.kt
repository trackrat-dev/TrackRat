package com.trackrat.android.data

import com.google.android.gms.maps.model.LatLng

/**
 * Station data synchronized with iOS Stations.swift and backend stations.py
 * Provides station codes, names, and GPS coordinates for mapping
 */
object Stations {

    data class Station(
        val code: String,
        val name: String,
        val latLng: LatLng
    )

    // Core NJ Transit and Amtrak stations with GPS coordinates
    private val stationMap = mapOf(
        // Major Hub Stations
        "NY" to Station("NY", "New York Penn Station", LatLng(40.7506, -73.9939)),
        "NP" to Station("NP", "Newark Penn Station", LatLng(40.7347, -74.1644)),
        "HB" to Station("HB", "Hoboken", LatLng(40.734843, -74.028043)),
        "TR" to Station("TR", "Trenton", LatLng(40.218518, -74.753923)),
        "PH" to Station("PH", "Philadelphia", LatLng(39.9570, -75.1820)),

        // Northeast Corridor Line
        "PJ" to Station("PJ", "Princeton Junction", LatLng(40.3167, -74.6233)),
        "HL" to Station("HL", "Hamilton", LatLng(40.2547, -74.7036)),
        "MP" to Station("MP", "Metropark", LatLng(40.5378, -74.3562)),
        "NB" to Station("NB", "New Brunswick", LatLng(40.4862, -74.4518)),
        "SE" to Station("SE", "Secaucus Junction", LatLng(40.7612, -74.0758)),
        "ED" to Station("ED", "Edison", LatLng(40.5177, -74.4075)),
        "MU" to Station("MU", "Metuchen", LatLng(40.5378, -74.3562)),
        "EZ" to Station("EZ", "Elizabeth", LatLng(40.667859, -74.215171)),
        "NZ" to Station("NZ", "North Elizabeth", LatLng(40.680341475, -74.2061729014)),
        "LI" to Station("LI", "Linden", LatLng(40.629487, -74.251772)),
        "RH" to Station("RH", "Rahway", LatLng(40.6039, -74.2723)),
        "NA" to Station("NA", "Newark Airport", LatLng(40.7044941, -74.1909959)),
        "ND" to Station("ND", "Newark Broad Street", LatLng(40.7418, -74.1698)),

        // North Jersey Coast Line
        "WB" to Station("WB", "Woodbridge", LatLng(40.5559, -74.2780)),
        "PE" to Station("PE", "Perth Amboy", LatLng(40.509372, -74.27381259)),
        "CH" to Station("CH", "South Amboy", LatLng(40.48490168, -74.2804993)),
        "AM" to Station("AM", "Aberdeen-Matawan", LatLng(40.419773943, -74.22209923)),
        "HZ" to Station("HZ", "Hazlet", LatLng(40.41515409, -74.190629424)),
        "MI" to Station("MI", "Middletown NJ", LatLng(40.39082051, -74.116794)),
        "RB" to Station("RB", "Red Bank", LatLng(40.348271404, -74.074151249)),
        "LS" to Station("LS", "Little Silver", LatLng(40.32654188, -74.040546829)),
        "MK" to Station("MK", "Monmouth Park", LatLng(40.3086, -74.0253)),
        "LB" to Station("LB", "Long Branch", LatLng(40.2970, -73.9883)),
        "EL" to Station("EL", "Elberon", LatLng(40.265251, -73.997479)),
        "AH" to Station("AH", "Allenhurst", LatLng(40.2301, -74.0063)),
        "AP" to Station("AP", "Asbury Park", LatLng(40.2202, -74.0120)),
        "BB" to Station("BB", "Bradley Beach", LatLng(40.1929, -74.0218)),
        "BS" to Station("BS", "Belmar", LatLng(40.1784, -74.0276)),
        "LA" to Station("LA", "Spring Lake", LatLng(40.1530, -74.0340)),
        "SQ" to Station("SQ", "Manasquan", LatLng(40.1057, -74.0500)),
        "PP" to Station("PP", "Point Pleasant Beach", LatLng(40.0928885, -74.048128)),
        "BH" to Station("BH", "Bay Head", LatLng(40.0771313, -74.046189485)),

        // Morris & Essex Lines
        "ST" to Station("ST", "Summit", LatLng(40.716664548, -74.3576803)),
        "CM" to Station("CM", "Chatham", LatLng(40.740191597, -74.384824495)),
        "MA" to Station("MA", "Madison", LatLng(40.757040225, -74.415224486)),
        "CN" to Station("CN", "Convent Station", LatLng(40.778934247, -74.4433639138)),
        "MR" to Station("MR", "Morristown", LatLng(40.7971792932, -74.474198069)),
        "MX" to Station("MX", "Morris Plains", LatLng(40.828603425, -74.4782465138)),
        "DV" to Station("DV", "Denville", LatLng(40.8837, -74.4753)),
        "DO" to Station("DO", "Dover", LatLng(40.88350334976419, -74.55552377794903)),
        "MB" to Station("MB", "Millburn", LatLng(40.7256749, -74.3036915)),
        "RT" to Station("RT", "Short Hills", LatLng(40.725183794, -74.323772644)),
        "SO" to Station("SO", "South Orange", LatLng(40.74598917, -74.260345)),
        "MW" to Station("MW", "Maplewood", LatLng(40.731052531, -74.275368)),
        "OG" to Station("OG", "Orange", LatLng(40.771899, -74.2331103)),
        "EO" to Station("EO", "East Orange", LatLng(40.76089825, -74.2107669)),
        "BU" to Station("BU", "Brick Church", LatLng(40.765656, -74.21909888)),
        "HI" to Station("HI", "Highland Avenue", LatLng(40.7668668, -74.24370939)),
        "MV" to Station("MV", "Mountain View", LatLng(40.913900511412734, -74.26769562647546)),

        // Raritan Valley Line
        "US" to Station("US", "Union", LatLng(40.683542211, -74.23800686)),
        "RL" to Station("RL", "Roselle Park", LatLng(40.6642, -74.2687)),
        "XC" to Station("XC", "Cranford", LatLng(40.6559, -74.3004)),
        "GW" to Station("GW", "Garwood", LatLng(40.65255335, -74.325004422)),
        "WF" to Station("WF", "Westfield", LatLng(40.64944139, -74.34758901)),
        "FW" to Station("FW", "Fanwood", LatLng(40.64061996, -74.384423727)),
        "NE" to Station("NE", "Netherwood", LatLng(40.62921816688, -74.403226634)),
        "PF" to Station("PF", "Plainfield", LatLng(40.6140, -74.4147)),
        "DN" to Station("DN", "Dunellen", LatLng(40.5892, -74.4719)),
        "BK" to Station("BK", "Bound Brook", LatLng(40.5612539, -74.53021426)),
        "BW" to Station("BW", "Bridgewater", LatLng(40.561009, -74.55175689)),
        "SM" to Station("SM", "Somerville", LatLng(40.56608, -74.6138659)),
        "RA" to Station("RA", "Raritan", LatLng(40.57091522, -74.6344244)),

        // Main/Bergen County Lines
        "KG" to Station("KG", "Kingsland", LatLng(40.8123, -74.1246)),
        "PS" to Station("PS", "Passaic", LatLng(40.8494377, -74.133866768)),
        "IF" to Station("IF", "Clifton", LatLng(40.867912098, -74.15326859)),
        "RN" to Station("RN", "Paterson", LatLng(40.9166, -74.1710)),
        "HW" to Station("HW", "Hawthorne", LatLng(40.942528946, -74.152399138)),
        "RS" to Station("RS", "Glen Rock Main Line", LatLng(40.9808, -74.1168)),
        "RW" to Station("RW", "Ridgewood", LatLng(40.9808, -74.1168)),
        "UF" to Station("UF", "Ho-Ho-Kus", LatLng(40.9956, -74.1115)),
        "WK" to Station("WK", "Waldwick", LatLng(41.0108, -74.1267)),
        "AZ" to Station("AZ", "Allendale", LatLng(41.0308516, -74.13104499)),
        "RY" to Station("RY", "Ramsey Main St", LatLng(41.0571, -74.1413)),
        "17" to Station("17", "Ramsey Route 17", LatLng(41.0615, -74.1456)),
        "MZ" to Station("MZ", "Mahwah", LatLng(41.0886, -74.1438)),
        "SF" to Station("SF", "Suffern", LatLng(41.1144, -74.1496)),

        // Port Jervis Line
        "XG" to Station("XG", "Sloatsburg", LatLng(41.1568, -74.1937)),
        "TC" to Station("TC", "Tuxedo", LatLng(41.1970, -74.1885)),
        "RM" to Station("RM", "Harriman", LatLng(41.3098, -74.1526)),
        "MD" to Station("MD", "Middletown NY", LatLng(41.4459, -74.4222)),
        "CW" to Station("CW", "Salisbury Mills-Cornwall", LatLng(41.436533265, -74.101601729)),
        "CB" to Station("CB", "Campbell Hall", LatLng(41.4446, -74.2452)),
        "OS" to Station("OS", "Otisville", LatLng(41.4783, -74.5336)),
        "PO" to Station("PO", "Port Jervis", LatLng(41.3753, -74.6897)),

        // Amtrak Northeast Corridor
        "WI" to Station("WI", "Wilmington Station", LatLng(39.7369, -75.5522)),
        "BA" to Station("BA", "BWI Thurgood Marshall Airport", LatLng(39.1896, -76.6934)),
        "BL" to Station("BL", "Baltimore Station", LatLng(39.3081, -76.6175)),
        "WS" to Station("WS", "Washington Union Station", LatLng(38.8973, -77.0064)),
        "BOS" to Station("BOS", "Boston South", LatLng(42.3520, -71.0552)),
        "BBY" to Station("BBY", "Boston Back Bay", LatLng(42.3473, -71.0764)),
        "PVD" to Station("PVD", "Providence", LatLng(41.8256, -71.4160)),
        "NHV" to Station("NHV", "New Haven", LatLng(41.2987, -72.9259)),
        "BRP" to Station("BRP", "Bridgeport", LatLng(41.1767, -73.1874)),
        "STM" to Station("STM", "Stamford", LatLng(41.0462, -73.5427)),

        // Additional major Amtrak stations
        "HAR" to Station("HAR", "Harrisburg", LatLng(40.2616, -76.8782)),
        "LNC" to Station("LNC", "Lancaster", LatLng(40.0538, -76.3076)),
        "RVR" to Station("RVR", "Richmond Staples Mill Road", LatLng(37.61741, -77.49755)),

        // Southeast Amtrak stations
        "CLT" to Station("CLT", "Charlotte", LatLng(35.2411460876465, -80.8236389160156)),
        "RGH" to Station("RGH", "Raleigh", LatLng(35.7795, -78.6382)),
        "SAV" to Station("SAV", "Savannah", LatLng(32.0835, -81.0998)),
        "JAX" to Station("JAX", "Jacksonville", LatLng(30.3665771484375, -81.7246017456055)),
        "ORL" to Station("ORL", "Orlando", LatLng(28.5256938934326, -81.3817443847656)),
        "TPA" to Station("TPA", "Tampa", LatLng(27.9506, -82.4572)),
        "MIA" to Station("MIA", "Miami", LatLng(25.8498477935791, -80.2580718994141)),
        "ATL" to Station("ATL", "Atlanta", LatLng(33.7995643615723, -84.3917846679688))
    )

    // Default map region centered on Newark Penn Station
    val DEFAULT_REGION = MapRegion(
        center = LatLng(40.7348, -74.1644), // Newark Penn Station
        zoom = 9.5f // Approximately 1.5° span equivalent
    )

    /**
     * Get station by code
     */
    fun getStation(code: String): Station? = stationMap[code]

    /**
     * Get coordinates for a station code
     */
    fun getCoordinates(code: String): LatLng? = stationMap[code]?.latLng

    /**
     * Get station name for a code
     */
    fun getStationName(code: String): String? = stationMap[code]?.name

    /**
     * Get all stations as a list
     */
    fun getAllStations(): List<Station> = stationMap.values.toList()

    /**
     * Search stations by name (case-insensitive)
     */
    fun search(query: String): List<Station> {
        if (query.isEmpty()) return emptyList()
        val lowercased = query.lowercase()
        return stationMap.values
            .filter { it.name.lowercase().contains(lowercased) }
            .take(8)
    }

    /**
     * Primary departure stations for quick access
     */
    val DEPARTURE_STATIONS = listOf(
        "NY", "HB", "MP", "PJ", "HL", "TR", "LB", "PF", "DN", "RA",
        "PH", "WI", "BL", "WS", "RVR", "CLT", "RGH", "SAV", "JAX",
        "ORL", "TPA", "MIA", "ATL"
    )
}

/**
 * Map region data class for defining map viewport
 */
data class MapRegion(
    val center: LatLng,
    val zoom: Float
)
