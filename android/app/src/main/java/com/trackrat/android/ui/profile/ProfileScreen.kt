package com.trackrat.android.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.navigation.TrackRatNavigator
import com.trackrat.android.ui.profile.components.ProfileActionRow
import com.trackrat.android.ui.profile.components.ProfileSectionCard

/**
 * Profile screen showing settings and support options
 * Matches iOS MyProfileView design
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    viewModel: ProfileViewModel = hiltViewModel(),
    navigator: TrackRatNavigator
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Profile",
                        fontWeight = FontWeight.SemiBold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navigator.navigateBack() }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Support Section
            item {
                ProfileSectionCard(title = "Support") {
                    ProfileActionRow(
                        icon = Icons.Default.Info,
                        text = "Report Issues",
                        subtitle = "Send new ideas too!",
                        isExternalLink = true,
                        onClick = { viewModel.openSignalLink() }
                    )
                }
            }

            // Community Section
            item {
                ProfileSectionCard(title = "Community") {
                    ProfileActionRow(
                        icon = Icons.Default.PlayArrow,
                        text = "YouTube Channel",
                        isExternalLink = true,
                        onClick = { viewModel.openYouTube() }
                    )
                    ProfileActionRow(
                        icon = Icons.Default.Favorite,
                        text = "Instagram",
                        isExternalLink = true,
                        onClick = { viewModel.openInstagram() }
                    )
                }
            }

            // Settings Section
            item {
                ProfileSectionCard(title = "Settings") {
                    ProfileActionRow(
                        icon = Icons.Default.Star,
                        text = "Edit Favorite Stations",
                        isExternalLink = false,
                        onClick = {
                            navigator.navigateToFavoriteStations()
                        }
                    )

                    // Advanced Configuration (available to all users, not just debug builds)
                    ProfileActionRow(
                        icon = Icons.Default.Settings,
                        text = "Advanced Configuration",
                        subtitle = uiState.currentEnvironment?.name,
                        isExternalLink = false,
                        onClick = {
                            navigator.navigateToAdvancedConfig()
                        }
                    )
                }
            }
        }
    }
}
