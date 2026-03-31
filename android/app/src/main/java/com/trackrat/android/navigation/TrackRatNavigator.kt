package com.trackrat.android.navigation

import androidx.navigation.NavController
import androidx.navigation.NavBackStackEntry

/**
 * Type-safe navigation helper for TrackRat app
 * Provides convenient methods for navigation with compile-time safety
 */
class TrackRatNavigator(private val navController: NavController) {
    
    /**
     * Navigate to station selection screen
     */
    fun navigateToStationSelection() {
        navController.navigate(TrackRatDestinations.StationSelection.route) {
            // Clear the back stack to prevent going back to train screens
            popUpTo(TrackRatDestinations.StationSelection.route) {
                inclusive = true
            }
        }
    }
    
    /**
     * Navigate to destination selection screen
     */
    fun navigateToDestinationSelection(originStation: String) {
        val route = TrackRatDestinations.DestinationSelection.createRoute(originStation)
        navController.navigate(route)
    }
    
    /**
     * Navigate to train list screen
     */
    fun navigateToTrainList(fromStation: String, toStation: String? = null) {
        val route = TrackRatDestinations.TrainList.createRoute(fromStation, toStation)
        navController.navigate(route)
    }
    
    /**
     * Navigate to train detail screen
     */
    fun navigateToTrainDetail(
        trainId: String,
        date: String? = null,
        originCode: String? = null,
        destinationCode: String? = null
    ) {
        val route = TrackRatDestinations.TrainDetail.createRoute(trainId, date, originCode, destinationCode)
        navController.navigate(route)
    }

    /**
     * Navigate to profile screen
     */
    fun navigateToProfile() {
        navController.navigate(TrackRatDestinations.Profile.route)
    }

    /**
     * Navigate to favorite stations screen
     */
    fun navigateToFavoriteStations() {
        navController.navigate(TrackRatDestinations.FavoriteStations.route)
    }

    /**
     * Navigate to advanced configuration screen
     */
    fun navigateToAdvancedConfig() {
        navController.navigate(TrackRatDestinations.AdvancedConfig.route)
    }

    /**
     * Navigate back to the previous screen
     */
    fun navigateBack(): Boolean {
        return navController.popBackStack()
    }
    
    /**
     * Navigate back to a specific destination
     */
    fun navigateBackTo(destination: TrackRatDestinations, inclusive: Boolean = false): Boolean {
        return navController.popBackStack(destination.route, inclusive)
    }
}

/**
 * Extension functions for extracting typed arguments from NavBackStackEntry
 */
fun NavBackStackEntry.getDestinationSelectionArgs(): NavigationArgs.DestinationSelectionArgs {
    val originStation = arguments?.getString("originStation") 
        ?: throw IllegalArgumentException("originStation argument is required")
    
    return NavigationArgs.DestinationSelectionArgs(
        originStation = originStation
    )
}

fun NavBackStackEntry.getTrainListArgs(): NavigationArgs.TrainListArgs {
    val fromStation = arguments?.getString("fromStation") 
        ?: throw IllegalArgumentException("fromStation argument is required")
    val toStation = arguments?.getString("toStation")
    
    return NavigationArgs.TrainListArgs(
        fromStation = fromStation,
        toStation = toStation
    )
}

fun NavBackStackEntry.getTrainDetailArgs(): NavigationArgs.TrainDetailArgs {
    val trainId = arguments?.getString("trainId")
        ?: throw IllegalArgumentException("trainId argument is required")
    val date = arguments?.getString("date")
    val originCode = arguments?.getString("originCode")
    val destinationCode = arguments?.getString("destinationCode")

    return NavigationArgs.TrainDetailArgs(
        trainId = trainId,
        date = date,
        originCode = originCode,
        destinationCode = destinationCode
    )
}

/**
 * Compose-friendly extension for creating navigator
 */
fun NavController.createTrackRatNavigator(): TrackRatNavigator {
    return TrackRatNavigator(this)
}