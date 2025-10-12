package com.trackrat.android.ui.map

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.google.android.gms.maps.model.MapStyleOptions
import com.google.maps.android.compose.*
import com.trackrat.android.ui.components.BottomSheetPosition
import com.trackrat.android.ui.components.DraggableBottomSheet
import com.trackrat.android.ui.destinationselection.DestinationSelectionScreen
import com.trackrat.android.ui.stationselection.StationSelectionScreen
import com.trackrat.android.ui.trainlist.TrainListScreen
import com.trackrat.android.ui.traindetail.TrainDetailScreen
import java.time.LocalDate

/**
 * Main container screen combining map + bottom sheet + navigation
 * Matches iOS MapContainerView architecture
 *
 * Layout structure:
 * - Background: Google Maps (always visible)
 * - Foreground: Draggable bottom sheet with navigation content
 *
 * The sheet contains a NavHost with all app screens:
 * - StationSelectionScreen (home)
 * - DestinationSelectionScreen
 * - TrainListScreen
 * - TrainDetailScreen
 */
@Composable
fun MapContainerScreen(
    mainNavController: NavHostController,
    viewModel: MapContainerViewModel = hiltViewModel()
) {
    // Navigation controller for content within the bottom sheet
    val sheetNavController = rememberNavController()

    // Observe sheet position from ViewModel
    val sheetPosition by viewModel.sheetPosition.collectAsState()

    Box(modifier = Modifier.fillMaxSize()) {
        // Background: Google Maps
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = viewModel.cameraPositionState,
            uiSettings = MapUiSettings(
                zoomControlsEnabled = false,
                compassEnabled = false,
                myLocationButtonEnabled = false,
                mapToolbarEnabled = false
            )
            // TODO: Add dark map style
            // TODO: Add polylines for routes
            // TODO: Add station markers
            // TODO: Add congestion overlays
        )

        // Foreground: Draggable bottom sheet with navigation
        DraggableBottomSheet(
            position = sheetPosition,
            onPositionChange = { newPosition ->
                viewModel.updateSheetPosition(newPosition)
            }
        ) {
            // Navigation content within sheet
            NavHost(
                navController = sheetNavController,
                startDestination = "station_selection"
            ) {
                // Station Selection (home screen)
                composable("station_selection") {
                    StationSelectionScreen(
                        onNavigateToDestination = { fromStation ->
                            // Navigate to destination picker
                            sheetNavController.navigate("destination_selection/$fromStation")
                        },
                        onNavigateToTrainDetail = { trainId ->
                            // Navigate to train details by ID
                            val today = LocalDate.now().toString()
                            sheetNavController.navigate("train_details/$trainId/$today")
                        },
                        onNavigateToProfile = {
                            // TODO: Navigate to profile (can add later)
                        }
                    )
                }

                // Destination Selection
                composable(
                    route = "destination_selection/{from}",
                    arguments = listOf(
                        navArgument("from") { type = NavType.StringType }
                    )
                ) { backStackEntry ->
                    val fromStation = backStackEntry.arguments?.getString("from") ?: ""
                    DestinationSelectionScreen(
                        originStation = fromStation,
                        onNavigateBack = {
                            sheetNavController.popBackStack()
                        },
                        onNavigateToTrains = { destinationCode ->
                            // Navigate to train list
                            sheetNavController.navigate("train_list/$fromStation/$destinationCode")
                        }
                    )
                }

                // Train List
                composable(
                    route = "train_list/{from}/{to}",
                    arguments = listOf(
                        navArgument("from") { type = NavType.StringType },
                        navArgument("to") { type = NavType.StringType }
                    )
                ) { backStackEntry ->
                    val fromStation = backStackEntry.arguments?.getString("from") ?: ""
                    val toStation = backStackEntry.arguments?.getString("to") ?: ""
                    TrainListScreen(
                        fromStation = fromStation,
                        toStation = toStation,
                        onNavigateBack = {
                            sheetNavController.popBackStack()
                        },
                        onTrainClicked = { trainId ->
                            // Navigate to train details
                            val today = LocalDate.now().toString()
                            sheetNavController.navigate(
                                "train_details/$trainId/$today?from=$fromStation&to=$toStation"
                            )
                        }
                    )
                }

                // Train Details
                composable(
                    route = "train_details/{trainId}/{date}?from={from}&to={to}",
                    arguments = listOf(
                        navArgument("trainId") { type = NavType.StringType },
                        navArgument("date") { type = NavType.StringType },
                        navArgument("from") {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        navArgument("to") {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        }
                    )
                ) { backStackEntry ->
                    val trainId = backStackEntry.arguments?.getString("trainId") ?: ""
                    val date = backStackEntry.arguments?.getString("date") ?: LocalDate.now().toString()
                    val originCode = backStackEntry.arguments?.getString("from")
                    val destinationCode = backStackEntry.arguments?.getString("to")

                    TrainDetailScreen(
                        trainId = trainId,
                        date = date,
                        originCode = originCode,
                        destinationCode = destinationCode,
                        onNavigateBack = {
                            sheetNavController.popBackStack()
                        }
                    )
                }
            }
        }
    }
}
