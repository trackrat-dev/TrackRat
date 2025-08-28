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

    NavHost(navController = navController, startDestination = "station_selection") {
        composable("station_selection") {
            StationSelectionScreen(
                onNavigateToTrains = { originCode, destinationCode ->
                    if (destinationCode != null) {
                        navController.navigate("train_list/$originCode/$destinationCode")
                    } else {
                        navController.navigate("train_list/$originCode")
                    }
                },
                onNavigateToTrainDetail = { trainId ->
                    navController.navigate("train_detail/$trainId")
                }
            )
        }
        
        composable("train_list/{fromStation}") { backStackEntry ->
            val fromStation = backStackEntry.arguments?.getString("fromStation") ?: ""
            TrainListScreen(
                fromStation = fromStation,
                toStation = null,
                onNavigateBack = { 
                    navController.popBackStack() 
                },
                onTrainClicked = { trainId ->
                    navController.navigate("train_detail/$trainId")
                }
            )
        }
        
        composable("train_list/{fromStation}/{toStation}") { backStackEntry ->
            val fromStation = backStackEntry.arguments?.getString("fromStation") ?: ""
            val toStation = backStackEntry.arguments?.getString("toStation")
            TrainListScreen(
                fromStation = fromStation,
                toStation = toStation,
                onNavigateBack = { 
                    navController.popBackStack() 
                },
                onTrainClicked = { trainId ->
                    navController.navigate("train_detail/$trainId")
                }
            )
        }
        
        composable("train_detail/{trainId}") { backStackEntry ->
            val trainId = backStackEntry.arguments?.getString("trainId") ?: ""
            TrainDetailScreen(
                trainId = trainId,
                onNavigateBack = { 
                    navController.popBackStack() 
                }
            )
        }
    }
}