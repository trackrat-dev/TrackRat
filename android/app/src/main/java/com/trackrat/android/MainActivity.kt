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
import com.trackrat.android.ui.advanced.AdvancedConfigScreen
import com.trackrat.android.ui.destinationselection.DestinationSelectionScreen
import com.trackrat.android.ui.favorites.FavoriteStationsScreen
import com.trackrat.android.ui.profile.ProfileScreen
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

    // Use MapContainerScreen as the root (matching iOS architecture)
    // MapContainerScreen will manage its own internal navigation within the bottom sheet
    com.trackrat.android.ui.map.MapContainerScreen(mainNavController = navController)
}