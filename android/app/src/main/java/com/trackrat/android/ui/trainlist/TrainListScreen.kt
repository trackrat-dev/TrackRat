package com.trackrat.android.ui.trainlist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Train
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.ui.components.ErrorContent
import com.trackrat.android.ui.components.TrainListSkeleton
import com.trackrat.android.utils.Constants
import com.trackrat.android.utils.HapticFeedbackHelper
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TrainListScreen(
    fromStation: String,
    toStation: String?,
    viewModel: TrainListViewModel = hiltViewModel(),
    onNavigateBack: () -> Unit,
    onTrainClicked: (String) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val pullToRefreshState = rememberPullToRefreshState()
    val hapticFeedback = LocalHapticFeedback.current
    val context = LocalContext.current

    // Load trains when screen opens
    LaunchedEffect(fromStation, toStation) {
        viewModel.loadTrains(fromStation, toStation)
    }
    
    // Handle pull to refresh
    if (pullToRefreshState.isRefreshing) {
        LaunchedEffect(true) {
            viewModel.refresh()
        }
    }
    
    LaunchedEffect(uiState.isRefreshing) {
        if (!uiState.isRefreshing) {
            pullToRefreshState.endRefresh()
            // Haptic feedback on refresh completion
            HapticFeedbackHelper.performRefreshHaptic(context, uiState.hapticFeedbackEnabled)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = if (toStation != null) 
                                "Trains to ${uiState.toStationName ?: toStation}"
                            else 
                                "All Departures",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "From ${uiState.fromStationName ?: fromStation}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { 
                        HapticFeedbackHelper.performLightHaptic(hapticFeedback, uiState.hapticFeedbackEnabled)
                        onNavigateBack() 
                    }) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { 
                        HapticFeedbackHelper.performMediumHaptic(hapticFeedback, uiState.hapticFeedbackEnabled)
                        viewModel.refresh() 
                    }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .nestedScroll(pullToRefreshState.nestedScrollConnection)
        ) {
            when {
                uiState.isLoading && uiState.trains.isEmpty() -> {
                    TrainListSkeleton()
                }
                
                uiState.error != null -> {
                    ErrorContent(
                        error = uiState.error,
                        canRetry = uiState.canRetry,
                        onRetryClick = { 
                            HapticFeedbackHelper.performMediumHaptic(hapticFeedback, uiState.hapticFeedbackEnabled)
                            viewModel.retry() 
                        },
                        hapticFeedbackEnabled = uiState.hapticFeedbackEnabled
                    )
                }
                
                uiState.trains.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                            modifier = Modifier.padding(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Train,
                                contentDescription = null,
                                modifier = Modifier.size(64.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = "No Trains Found",
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = "There are currently no trains scheduled for this route.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
                
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Last updated indicator
                        item {
                            if (uiState.lastUpdated > 0) {
                                Text(
                                    text = "Updated ${formatLastUpdated(uiState.lastUpdated)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(bottom = 8.dp)
                                )
                            }
                        }
                        
                        items(uiState.trains) { train ->
                            TrainCard(
                                train = train,
                                fromStation = fromStation,
                                viewModel = viewModel,
                                onClick = { 
                                    HapticFeedbackHelper.performLightHaptic(hapticFeedback, uiState.hapticFeedbackEnabled)
                                    onTrainClicked(train.trainId) 
                                }
                            )
                        }
                    }
                }
            }
            
            PullToRefreshContainer(
                modifier = Modifier.align(Alignment.TopCenter),
                state = pullToRefreshState,
            )
        }
    }
}

@Composable
fun TrainCard(
    train: TrainV2,
    fromStation: String,
    viewModel: TrainListViewModel,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            // Header: Train number, line, destination
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = "Train ${train.trainId}",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        if (!train.lineCode.isNullOrEmpty()) {
                            Surface(
                                shape = RoundedCornerShape(4.dp),
                                color = Color(Constants.BRAND_ORANGE).copy(alpha = 0.1f)
                            ) {
                                Text(
                                    text = train.lineCode,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color(Constants.BRAND_ORANGE),
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                        }
                    }
                    Text(
                        text = "to ${train.destination ?: train.terminalStationName}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                
                // Status indicator
                StatusChip(
                    status = viewModel.getTrainDisplayStatus(train),
                    isBoarding = viewModel.isTrainBoarding(train)
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Departure time and track info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Departure",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formatDepartureTime(train, fromStation),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium
                    )
                }

                if (!train.track.isNullOrEmpty()) {
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "Track",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = MaterialTheme.colorScheme.primaryContainer
                        ) {
                            Text(
                                text = train.track,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                            )
                        }
                    }
                } else if (train.prediction != null) {
                    // Show Owl prediction if available
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "Prediction",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(Constants.BRAND_ORANGE).copy(alpha = 0.1f)
                        ) {
                            Text(
                                text = "🦉 ${train.prediction.primaryPrediction}",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = Color(Constants.BRAND_ORANGE),
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                            )
                        }
                    }
                }
            }

            // Progress indicator if available
            train.progress?.let { progress ->
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = progress.journeyPercent / 100f,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(4.dp)),
                    color = Color(Constants.BRAND_ORANGE)
                )
                Text(
                    text = "${progress.stopsCompleted}/${progress.totalStops} stops • ${progress.minutesToArrival} min remaining",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }
    }
}

@Composable
fun StatusChip(
    status: String,
    isBoarding: Boolean
) {
    val (backgroundColor, textColor) = when {
        isBoarding -> Color(Constants.BRAND_ORANGE) to Color.White
        status.contains("DELAYED", ignoreCase = true) -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.onErrorContainer
        status.contains("CANCELLED", ignoreCase = true) -> MaterialTheme.colorScheme.error to MaterialTheme.colorScheme.onError
        status.contains("DEPARTED", ignoreCase = true) -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
        else -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
    }

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = backgroundColor
    ) {
        Text(
            text = status,
            style = MaterialTheme.typography.labelSmall,
            color = textColor,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            fontWeight = if (isBoarding) FontWeight.Bold else FontWeight.Normal
        )
    }
}

private fun formatDepartureTime(train: TrainV2, fromStation: String): String {
    return train.getScheduledDepartureTime(fromStation)?.format(
        DateTimeFormatter.ofPattern("h:mm a")
    ) ?: "N/A"
}

private fun formatLastUpdated(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    return when {
        diff < 60_000 -> "just now"
        diff < 3600_000 -> "${diff / 60_000} min ago"
        else -> "${diff / 3600_000} hr ago"
    }
}

@Preview(showBackground = true)
@Composable
fun TrainListScreenPreview() {
    TrainListScreen(
        fromStation = "NY",
        toStation = "NP",
        onNavigateBack = {},
        onTrainClicked = {}
    )
}