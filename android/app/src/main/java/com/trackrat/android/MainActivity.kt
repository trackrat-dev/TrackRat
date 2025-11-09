package com.trackrat.android

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
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
import java.time.LocalDate

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private var deepLinkUri by mutableStateOf<Uri?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Handle deep link from intent
        handleDeepLink(intent)

        setContent {
            TrackRatTheme {
                // A surface container using the 'background' color from the theme
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    TrackRatAppNavHost(deepLinkUri = deepLinkUri)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent) {
        if (intent.action == Intent.ACTION_VIEW) {
            deepLinkUri = intent.data
        }
    }
}

@Composable
fun TrackRatAppNavHost(deepLinkUri: Uri? = null) {
    val navController = rememberNavController()
    val navigator = navController.createTrackRatNavigator()

    NavHost(
        navController = navController,
        startDestination = "map_container"
    ) {
        // Map container as root (with embedded sheet navigation)
        composable("map_container") {
            com.trackrat.android.ui.map.MapContainerScreen(
                mainNavController = navController,
                deepLinkUri = deepLinkUri
            )
        }

        // Profile screen (full-screen overlay)
        composable(TrackRatDestinations.Profile.route) {
            ProfileScreen(navigator = navigator)
        }

        // Favorite Stations screen (full-screen overlay)
        composable(TrackRatDestinations.FavoriteStations.route) {
            FavoriteStationsScreen(navigator = navigator)
        }

        // Advanced Configuration screen (full-screen overlay)
        composable(TrackRatDestinations.AdvancedConfig.route) {
            AdvancedConfigScreen(navigator = navigator)
        }
    }
}