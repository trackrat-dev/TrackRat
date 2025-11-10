package com.trackrat.android.navigation

import androidx.navigation.NamedNavArgument
import androidx.navigation.NavType
import androidx.navigation.navArgument

/**
 * Type-safe navigation destinations for TrackRat app
 * This prevents runtime errors from typos in route strings
 */
sealed class TrackRatDestinations(
    val route: String,
    val arguments: List<NamedNavArgument> = emptyList()
) {
    /**
     * Station selection screen - app entry point
     */
    data object StationSelection : TrackRatDestinations("station_selection")
    
    /**
     * Destination selection screen - choose where to go from origin
     */
    data object DestinationSelection : TrackRatDestinations(
        route = "destination_selection/{originStation}",
        arguments = listOf(
            navArgument("originStation") {
                type = NavType.StringType
                nullable = false
            }
        )
    ) {
        /**
         * Create route with origin parameter
         */
        fun createRoute(originStation: String): String {
            return "destination_selection/$originStation"
        }
    }
    
    /**
     * Train list screen with optional destination
     * Shows departures from origin station
     */
    data object TrainList : TrackRatDestinations(
        route = "train_list/{fromStation}?toStation={toStation}",
        arguments = listOf(
            navArgument("fromStation") {
                type = NavType.StringType
                nullable = false
            },
            navArgument("toStation") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            }
        )
    ) {
        /**
         * Create route with parameters
         */
        fun createRoute(fromStation: String, toStation: String? = null): String {
            return if (toStation != null) {
                "train_list/$fromStation?toStation=$toStation"
            } else {
                "train_list/$fromStation"
            }
        }
    }
    
    /**
     * Train detail screen showing journey information
     */
    data object TrainDetail : TrackRatDestinations(
        route = "train_detail/{trainId}?date={date}&originCode={originCode}&destinationCode={destinationCode}",
        arguments = listOf(
            navArgument("trainId") {
                type = NavType.StringType
                nullable = false
            },
            navArgument("date") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            },
            navArgument("originCode") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            },
            navArgument("destinationCode") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            }
        )
    ) {
        /**
         * Create route with parameters
         */
        fun createRoute(
            trainId: String,
            date: String? = null,
            originCode: String? = null,
            destinationCode: String? = null
        ): String {
            val params = mutableListOf<String>()
            date?.let { params.add("date=$it") }
            originCode?.let { params.add("originCode=$it") }
            destinationCode?.let { params.add("destinationCode=$it") }

            return if (params.isNotEmpty()) {
                "train_detail/$trainId?${params.joinToString("&")}"
            } else {
                "train_detail/$trainId"
            }
        }
    }

    /**
     * Profile screen - settings and support
     */
    data object Profile : TrackRatDestinations("profile")

    /**
     * Favorite Stations screen
     */
    data object FavoriteStations : TrackRatDestinations("favorite_stations")

    /**
     * Advanced Configuration screen - server switching
     */
    data object AdvancedConfig : TrackRatDestinations("advanced_config")
}

/**
 * Extension functions for type-safe argument extraction
 */
object NavigationArgs {
    /**
     * Extract typed arguments for DestinationSelection destination
     */
    data class DestinationSelectionArgs(
        val originStation: String
    )
    
    /**
     * Extract typed arguments for TrainList destination
     */
    data class TrainListArgs(
        val fromStation: String,
        val toStation: String?
    )
    
    /**
     * Extract typed arguments for TrainDetail destination
     */
    data class TrainDetailArgs(
        val trainId: String,
        val date: String?,
        val originCode: String?,
        val destinationCode: String?
    )
}