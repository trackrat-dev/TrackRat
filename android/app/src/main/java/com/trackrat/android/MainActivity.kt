package com.trackrat.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.trackrat.android.navigation.TrackRatDestinations
import com.trackrat.android.navigation.createTrackRatNavigator
import com.trackrat.android.navigation.getDestinationSelectionArgs
import com.trackrat.android.navigation.getTrainDetailArgs
import com.trackrat.android.navigation.getTrainListArgs
import com.trackrat.android.ui.destinationselection.DestinationSelectionScreen
import com.trackrat.android.ui.stationselection.StationSelectionScreen
import com.trackrat.android.ui.trainlist.TrainListScreen
import com.trackrat.android.ui.traindetail.TrainDetailScreen
import com.trackrat.android.ui.theme.TrackRatTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TrackRatTheme {
                // A surface container using the 'background' color from the theme
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    TrackRatAppNavHost()
                }
            }
        }
    }
}

@Composable
fun TrackRatAppNavHost() {
    val navController = rememberNavController()
    val navigator = navController.createTrackRatNavigator()

    NavHost(
        navController = navController, 
        startDestination = TrackRatDestinations.StationSelection.route
    ) {
        // Station Selection Screen
        composable(TrackRatDestinations.StationSelection.route) {
            StationSelectionScreen(
                onNavigateToDestination = { originCode ->
                    navigator.navigateToDestinationSelection(originCode)
                },
                onNavigateToTrainDetail = { trainId ->
                    navigator.navigateToTrainDetail(trainId)
                }
            )
        }
        
        // Destination Selection Screen
        composable(
            route = TrackRatDestinations.DestinationSelection.route,
            arguments = TrackRatDestinations.DestinationSelection.arguments
        ) { backStackEntry ->
            val args = backStackEntry.getDestinationSelectionArgs()
            DestinationSelectionScreen(
                originStation = args.originStation,
                onNavigateBack = {
                    navigator.navigateBack()
                },
                onNavigateToTrains = { destinationCode ->
                    navigator.navigateToTrainList(args.originStation, destinationCode)
                }
            )
        }
        
        // Train List Screen (with type-safe arguments)
        composable(
            route = TrackRatDestinations.TrainList.route,
            arguments = TrackRatDestinations.TrainList.arguments
        ) { backStackEntry ->
            val args = backStackEntry.getTrainListArgs()
            TrainListScreen(
                fromStation = args.fromStation,
                toStation = args.toStation,
                onNavigateBack = { 
                    navigator.navigateBack()
                },
                onTrainClicked = { trainId ->
                    navigator.navigateToTrainDetail(trainId)
                }
            )
        }
        
        // Train Detail Screen (with type-safe arguments)
        composable(
            route = TrackRatDestinations.TrainDetail.route,
            arguments = TrackRatDestinations.TrainDetail.arguments
        ) { backStackEntry ->
            val args = backStackEntry.getTrainDetailArgs()
            TrainDetailScreen(
                trainId = args.trainId,
                date = args.date,
                onNavigateBack = { 
                    navigator.navigateBack()
                }
            )
        }
    }
}