package com.trackrat.android.ui.map

import android.net.Uri
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.google.android.gms.maps.model.MapStyleOptions
import com.google.maps.android.compose.*
import com.trackrat.android.R
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
    deepLinkUri: Uri? = null,
    viewModel: MapContainerViewModel = androidx.lifecycle.viewmodel.compose.viewModel()
) {
    // Navigation controller for content within the bottom sheet
    val sheetNavController = rememberNavController()

    // Handle deep link navigation
    LaunchedEffect(deepLinkUri) {
        deepLinkUri?.let { uri ->
            when (uri.host) {
                "train" -> {
                    // Extract train number from path: trackrat://train/3515
                    val trainNumber = uri.pathSegments.firstOrNull()
                    if (trainNumber != null) {
                        val today = LocalDate.now().toString()
                        sheetNavController.navigate("train_details/$trainNumber/$today")
                    }
                }
                "journey" -> {
                    // Extract from/to parameters: trackrat://journey?from=NY&to=TR
                    val fromStation = uri.getQueryParameter("from")
                    val toStation = uri.getQueryParameter("to")
                    if (fromStation != null && toStation != null) {
                        // Set the route visualization
                        viewModel.setSelectedRoute(fromStation, toStation)
                        // Navigate to train list
                        sheetNavController.navigate("train_list/$fromStation/$toStation")
                    }
                }
            }
        }
    }

    // Observe sheet position from ViewModel
    val sheetPosition by viewModel.sheetPosition.collectAsState()

    // Observe selected route, congestion data, and selected segment
    val selectedRoute by viewModel.selectedRoute.collectAsState()
    val congestionPolylines by viewModel.congestionPolylines.collectAsState()
    val selectedSegmentId by viewModel.selectedSegmentId.collectAsState()

    // Load congestion data on initial composition
    LaunchedEffect(Unit) {
        viewModel.loadCongestionData()
    }

    // Dark mode styling
    val context = LocalContext.current
    val isDarkMode = isSystemInDarkTheme()
    val mapProperties = remember(isDarkMode) {
        MapProperties(
            mapStyleOptions = if (isDarkMode) {
                MapStyleOptions.loadRawResourceStyle(context, R.raw.dark_map_style)
            } else {
                null
            }
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        // Background: Google Maps
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = viewModel.cameraPositionState,
            properties = mapProperties,
            uiSettings = MapUiSettings(
                zoomControlsEnabled = false,
                compassEnabled = false,
                myLocationButtonEnabled = false,
                mapToolbarEnabled = false
            ),
            onMapClick = { latLng ->
                // Detect taps on congestion polylines
                viewModel.cameraPositionState.projection?.let { projection ->
                    val tappedSegment = PolylineHitDetector.findTappedSegment(
                        tapLatLng = latLng,
                        segments = congestionPolylines,
                        projection = projection,
                        tolerancePx = 30f // Matching iOS 30pt tolerance
                    )
                    viewModel.selectSegment(tappedSegment)
                }
            }
        ) {
            // Render congestion polylines (below route highlight)
            congestionPolylines.forEach { polyline ->
                // Create unique ID for this polyline
                val polylineId = "${polyline.fromLatLng.latitude},${polyline.fromLatLng.longitude}-${polyline.toLatLng.latitude},${polyline.toLatLng.longitude}"
                val isSelected = selectedSegmentId == polylineId

                Polyline(
                    points = listOf(polyline.fromLatLng, polyline.toLatLng),
                    color = if (isSelected)
                        androidx.compose.ui.graphics.Color(0xFF007AFF) // iOS blue for selected
                    else
                        polyline.color, // Normal congestion color
                    width = if (isSelected) 9f else polyline.width, // Thicker when selected
                    zIndex = if (isSelected) 15f else 5f // Higher z-index when selected
                )
            }

            // Render selected route polyline (above congestion)
            selectedRoute?.let { route ->
                Polyline(
                    points = listOf(route.fromLatLng, route.toLatLng),
                    color = androidx.compose.ui.graphics.Color(0xFF007AFF), // iOS blue
                    width = 7f,
                    zIndex = 10f // Above congestion overlays
                )
            }
        }

        // Foreground: Draggable bottom sheet with navigation
        DraggableBottomSheet(
            position = sheetPosition,
            onPositionChange = { newPosition ->
                viewModel.updateSheetPosition(newPosition)
            },
            isScrollable = true  // Enable gesture coordination with scrollable content
        ) {
            // Navigation content within sheet
            NavHost(
                navController = sheetNavController,
                startDestination = "station_selection"
            ) {
                // Station Selection (home screen)
                composable("station_selection") {
                    StationSelectionScreen(
                        mapViewModel = viewModel, // Pass shared ViewModel
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
                            // Navigate to profile using main nav controller (full-screen overlay)
                            mainNavController.navigate("profile")
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
                        mapViewModel = viewModel, // Pass shared ViewModel
                        onNavigateBack = {
                            sheetNavController.popBackStack()
                        },
                        onNavigateToTrains = { destinationCode ->
                            destinationCode?.let { destination ->
                                // Set route polyline when destination is selected
                                viewModel.setSelectedRoute(fromStation, destination)
                                // Navigate to train list
                                sheetNavController.navigate("train_list/$fromStation/$destination")
                            }
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
