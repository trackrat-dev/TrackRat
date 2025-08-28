package com.trackrat.android.utils

/**
 * Application-wide constants to avoid magic numbers
 */
object Constants {
    
    // Network & API
    const val DEFAULT_API_LIMIT = 50
    const val SEARCH_API_LIMIT = 100
    
    // Timing
    const val AUTO_REFRESH_INTERVAL_MS = 30_000L // 30 seconds
    const val LOADING_SKELETON_SHIMMER_DURATION_MS = 1000L // 1 second
    const val HAPTIC_FEEDBACK_DURATION_MS = 50L
    
    // Retry Logic  
    const val MAX_RETRY_ATTEMPTS = 3
    const val INITIAL_RETRY_DELAY_MS = 1000L // 1 second
    
    // UI Dimensions
    const val CARD_ELEVATION_DP = 4
    const val BORDER_RADIUS_SMALL_DP = 4
    const val BORDER_RADIUS_MEDIUM_DP = 8
    const val BORDER_RADIUS_LARGE_DP = 12
    const val PADDING_SMALL_DP = 8
    const val PADDING_MEDIUM_DP = 16
    const val PADDING_LARGE_DP = 24
    const val MIN_TOUCH_TARGET_DP = 48
    
    // Status Types
    object TrainStatus {
        const val BOARDING = "BOARDING"
        const val ALL_ABOARD = "ALL ABOARD"
        const val DEPARTED = "DEPARTED"
        const val DELAYED = "DELAYED"
        const val CANCELLED = "CANCELLED"
        const val ON_TIME = "ON TIME"
    }
    
    // Station Codes
    object StationCodes {
        const val NEW_YORK_PENN = "NY"
        const val NEWARK_PENN = "NP"
        const val TRENTON = "TR"
        const val PRINCETON_JUNCTION = "PJ"
        const val METROPARK = "MP"
    }
    
    // Station Names
    object StationNames {
        const val NEW_YORK_PENN = "New York Penn"
        const val NEWARK_PENN = "Newark Penn" 
        const val TRENTON = "Trenton"
        const val PRINCETON_JUNCTION = "Princeton Junction"
        const val METROPARK = "Metropark"
    }
    
    // Colors (Material3 Orange Theme)
    const val BRAND_ORANGE = 0xFFFF6600
    const val BRAND_ORANGE_LIGHT = 0xFFFF8833
    const val BRAND_ORANGE_DARK = 0xFFCC5200
    
    // Loading States
    const val SHIMMER_COUNT_TRAIN_LIST = 8
    const val SHIMMER_COUNT_TRAIN_DETAIL_STOPS = 12
    
    // Date/Time Formats
    const val DATE_FORMAT_API = "yyyy-MM-dd"
    const val TIME_FORMAT_DISPLAY = "h:mm a"
    const val DATETIME_FORMAT_ISO = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"
}

/**
 * Helper function to get station name from code
 */
fun getStationName(code: String): String {
    return when (code) {
        Constants.StationCodes.NEW_YORK_PENN -> Constants.StationNames.NEW_YORK_PENN
        Constants.StationCodes.NEWARK_PENN -> Constants.StationNames.NEWARK_PENN
        Constants.StationCodes.TRENTON -> Constants.StationNames.TRENTON
        Constants.StationCodes.PRINCETON_JUNCTION -> Constants.StationNames.PRINCETON_JUNCTION
        Constants.StationCodes.METROPARK -> Constants.StationNames.METROPARK
        else -> code
    }
}