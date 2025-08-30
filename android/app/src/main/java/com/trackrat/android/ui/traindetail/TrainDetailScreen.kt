package com.trackrat.android.ui.traindetail

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Train
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.DirectionsRailway
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.data.models.StopDetail
import com.trackrat.android.data.models.TrainDetailV2
import com.trackrat.android.ui.trainlist.Tuple4
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TrainDetailScreen(
    trainId: String,
    date: String? = null,
    viewModel: TrainDetailViewModel = hiltViewModel(),
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val pullToRefreshState = rememberPullToRefreshState()

    // Load train details when screen opens
    LaunchedEffect(trainId, date) {
        viewModel.loadTrainDetails(trainId, date)
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
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "Train $trainId",
                            style = MaterialTheme.typography.titleMedium
                        )
                        uiState.train?.let { train ->
                            Text(
                                text = "${train.route.origin} → ${train.route.destination}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
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
                uiState.isLoading && uiState.train == null -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            CircularProgressIndicator(
                                color = Color(0xFFFF6600)
                            )
                            Text("Loading train details...")
                        }
                    }
                }
                
                uiState.error != null -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                            modifier = Modifier.padding(32.dp)
                        ) {
                            Text(
                                text = "Error Loading Train",
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.error
                            )
                            Text(
                                text = uiState.error?.message ?: "Unknown error occurred",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center
                            )
                            Button(
                                onClick = { viewModel.refresh() },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = Color(0xFFFF6600)
                                )
                            ) {
                                Text("Try Again")
                            }
                        }
                    }
                }
                
                uiState.train == null -> {
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
                                text = "Train Not Found",
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = "This train may not be running today or the information is not available.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
                
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        uiState.train?.let { train ->
                            // Train header info
                            item {
                                TrainHeaderCard(
                                    train = train,
                                    viewModel = viewModel
                                )
                            }
                            
                            // Track Predictions section (replacing Journey Progress)
                            item {
                                TrackPredictionsCard(train)
                            }
                            
                            // Journey stops
                            item {
                                Text(
                                    text = "Journey Stops",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(vertical = 8.dp)
                                )
                            }
                            
                            val stops = train.stops
                            if (stops.isNotEmpty()) {
                                items(stops) { stop ->
                                    StopCard(
                                        stop = stop,
                                        isOrigin = stop.station.code == train.route.originCode,
                                        isTerminal = stop.station.code == train.route.destinationCode
                                    )
                                }
                            }
                            
                            // Last updated
                            item {
                                if (uiState.lastUpdated > 0) {
                                    Text(
                                        text = "Updated ${formatLastUpdated(uiState.lastUpdated)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(top = 16.dp),
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
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
fun TrainHeaderCard(
    train: TrainDetailV2,
    viewModel: TrainDetailViewModel
) {
    val isTracking by viewModel.isTrackingTrain.collectAsState()
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Train ID and Line
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Train ${train.trainId}",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )
                    // Train number not available in TrainDetailV2
                }
                
                // Status
                StatusChip(
                    status = viewModel.getTrainDisplayStatus(train),
                    isBoarding = viewModel.isTrainBoarding(train)
                )
            }
            
            // Line and destination
            if (train.line.code.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = Color(0xFFFF6600).copy(alpha = 0.1f)
                    ) {
                        Text(
                            text = train.line.code,
                            style = MaterialTheme.typography.labelMedium,
                            color = Color(0xFFFF6600),
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                        )
                    }
                    Text(
                        text = train.line.name,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            
            // Track and prediction
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // Track info - get from first stop if available
                val firstStopTrack = train.stops.firstOrNull()?.track
                if (!firstStopTrack.isNullOrEmpty()) {
                    Column {
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
                                text = firstStopTrack,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                            )
                        }
                    }
                }
                
                // Owl prediction not available in TrainDetailV2
                /* train.prediction?.let { prediction ->
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "Owl Prediction",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        PredictionChipDetailed(prediction = prediction)
                    }
                } */
            }
            
            // Tracking button
            Button(
                onClick = { viewModel.toggleTracking() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isTracking) Color.Gray else Color(0xFFFF6600)
                )
            ) {
                Icon(
                    imageVector = if (isTracking) Icons.Default.Circle else Icons.Default.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (isTracking) "Stop Tracking" else "Track This Train",
                    style = MaterialTheme.typography.labelLarge
                )
            }
        }
    }
}

@Composable
fun TrackPredictionsCard(train: TrainDetailV2) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header with icon
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.DirectionsRailway,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = Color(0xFFFF6600)
                )
                Text(
                    text = "Track Predictions",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            // Track assignment information
            val stopsWithTracks = train.stops.filter { !it.track.isNullOrEmpty() }
            
            if (stopsWithTracks.isNotEmpty()) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    stopsWithTracks.forEach { stop ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    text = stop.station.name,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Medium
                                )
                                val displayTime = stop.scheduledDeparture ?: stop.scheduledArrival
                                displayTime?.let { time ->
                                    Text(
                                        text = formatTime(time.toString()),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            
                            // Track badge
                            stop.track?.let { track ->
                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = Color(0xFFFF6600).copy(alpha = 0.2f)
                                ) {
                                    Text(
                                        text = "Track $track",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFFFF6600),
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            } else {
                // No track predictions available
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 16.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Track assignments not yet available",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            
            // Note about predictions
            if (stopsWithTracks.isEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Track assignments will appear here when available",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}

@Composable
fun StopCard(
    stop: StopDetail,
    isOrigin: Boolean = false,
    isTerminal: Boolean = false
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        colors = CardDefaults.cardColors(
            containerColor = when {
                isOrigin -> Color(0xFFFF6600).copy(alpha = 0.1f)
                isTerminal -> MaterialTheme.colorScheme.secondaryContainer
                else -> MaterialTheme.colorScheme.surface
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Stop indicator
            Icon(
                imageVector = Icons.Default.Circle,
                contentDescription = null,
                modifier = Modifier.size(12.dp),
                tint = when {
                    isOrigin -> Color(0xFFFF6600)
                    isTerminal -> MaterialTheme.colorScheme.secondary
                    else -> MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                }
            )
            
            // Station info
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stop.station.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = if (isOrigin || isTerminal) FontWeight.Bold else FontWeight.Normal
                )
                Text(
                    text = stop.station.code,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            // Time info
            Column(horizontalAlignment = Alignment.End) {
                // Departure time
                stop.scheduledDeparture?.let { scheduledDep ->
                    Text(
                        text = scheduledDep.format(DateTimeFormatter.ofPattern("h:mm a")),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                }
                
                // Arrival time (if different from departure)
                stop.scheduledArrival?.let { scheduledArr ->
                    if (stop.scheduledDeparture == null || scheduledArr != stop.scheduledDeparture) {
                        Text(
                            text = "arr ${scheduledArr.format(DateTimeFormatter.ofPattern("h:mm a"))}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                
                // Track if available
                if (!stop.track.isNullOrEmpty()) {
                    Text(
                        text = "Track ${stop.track}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFFF6600),
                        fontWeight = FontWeight.Medium
                    )
                }
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
        isBoarding -> Color(0xFFFF6600) to Color.White
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

@Composable
fun PredictionChipDetailed(
    prediction: com.trackrat.android.data.models.PredictionData
) {
    // Get confidence-based styling (confidence is 0.0-1.0 float)
    val (backgroundColor, textColor, fontWeight, confidenceIcon) = when {
        prediction.confidence >= 0.8f -> {
            // High confidence: Bold with checkmark
            Tuple4(
                Color(0xFFFF6600),
                Color.White,
                FontWeight.Bold,
                "✓"
            )
        }
        prediction.confidence >= 0.5f -> {
            // Medium confidence: Normal styling  
            Tuple4(
                Color(0xFFFF6600).copy(alpha = 0.15f),
                Color(0xFFFF6600),
                FontWeight.Medium,
                ""
            )
        }
        else -> {
            // Low confidence: Gray with question mark
            Tuple4(
                MaterialTheme.colorScheme.surfaceVariant,
                MaterialTheme.colorScheme.onSurfaceVariant,
                FontWeight.Normal,
                "?"
            )
        }
    }

    Column(horizontalAlignment = Alignment.End) {
        // Prediction chip
        Surface(
            shape = RoundedCornerShape(8.dp),
            color = backgroundColor
        ) {
            Text(
                text = "🦉 ${prediction.primaryPrediction}$confidenceIcon",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = fontWeight,
                color = textColor,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
            )
        }
        
        // Confidence percentage
        Text(
            text = prediction.confidenceText,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp)
        )
    }
}


private fun formatTime(timeString: String): String {
    // Extract time portion if it's an ISO string, otherwise return as-is
    return try {
        if (timeString.contains("T")) {
            // ISO format: extract HH:mm
            val timePart = timeString.substringAfter("T").substringBefore("-")
            timePart.substring(0, 5) // Get HH:mm
        } else {
            timeString
        }
    } catch (e: Exception) {
        timeString
    }
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
fun TrainDetailScreenPreview() {
    TrainDetailScreen(
        trainId = "1234",
        onNavigateBack = {}
    )
}