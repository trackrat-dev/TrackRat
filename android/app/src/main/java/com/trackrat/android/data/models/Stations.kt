package com.trackrat.android.data.models

/**
 * Static station data for TrackRat
 * Matches the iOS app's supported stations
 */
object Stations {
    
    /**
     * Main departure stations supported by the app
     */
    val DEPARTURE_STATIONS = listOf(
        Station("NY", "New York Penn Station"),
        Station("NP", "Newark Penn Station"),
        Station("TR", "Trenton Transit Center"),
        Station("PJ", "Princeton Junction"),
        Station("MP", "Metropark")
    )
    
    /**
     * All stations (for destination selection)
     * This is a subset - the full list can be expanded as needed
     */
    val ALL_STATIONS = DEPARTURE_STATIONS + listOf(
        // Additional NJ Transit stations
        Station("SE", "Secaucus Junction"),
        Station("HB", "Hoboken"),
        Station("NA", "Newark Airport"),
        Station("EZ", "Elizabeth"),
        Station("LI", "Linden"),
        Station("RH", "Rahway"),
        Station("WD", "Woodbridge"),
        Station("NB", "New Brunswick"),
        Station("ED", "Edison"),
        Station("MT", "Metuchen"),
        Station("PL", "Plainfield"),
        Station("WF", "Westfield"),
        Station("CR", "Cranford"),
        Station("SV", "Summit"),
        Station("MS", "Madison"),
        Station("MV", "Morristown"),
        
        // Major Amtrak stations
        Station("PHL", "Philadelphia 30th Street"),
        Station("WAS", "Washington Union Station"),
        Station("BOS", "Boston South Station"),
        Station("BAL", "Baltimore Penn Station"),
        Station("STM", "Stamford"),
        Station("NHV", "New Haven Union Station")
    )
    
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