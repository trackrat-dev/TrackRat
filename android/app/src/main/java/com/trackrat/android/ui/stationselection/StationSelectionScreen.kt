package com.trackrat.android.ui.stationselection

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Train
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.data.models.Station
import com.trackrat.android.ui.components.GlassmorphicCard
import com.trackrat.android.ui.components.GlassmorphicCardElevated
import com.trackrat.android.ui.components.GlassmorphicSearchCard
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StationSelectionScreen(
    viewModel: StationSelectionViewModel = hiltViewModel(),
    onNavigateToTrains: (originCode: String, destinationCode: String?) -> Unit,
    onNavigateToTrainDetail: (trainId: String) -> Unit
) {
    val departureStations by viewModel.departureStations.collectAsState()
    val selectedOrigin by viewModel.selectedOrigin.collectAsState()
    var searchText by remember { mutableStateOf("") }

    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    // Check if search text looks like a train number
    val isTrainSearch = searchText.isNotBlank() && (
        searchText.all { it.isDigit() } || // NJT trains (all digits)
        searchText.startsWith("A", ignoreCase = true) // Amtrak trains
    )

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        modifier = Modifier.background(MaterialTheme.colorScheme.background)
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(paddingValues)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Header
            Text(
                text = "Where would you like to leave from?",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onBackground
            )
            
            // Search bar
            GlassmorphicSearchCard(
                modifier = Modifier.fillMaxWidth()
            ) {
                OutlinedTextField(
                    value = searchText,
                    onValueChange = { 
                        searchText = it
                        if (!isTrainSearch) {
                            viewModel.searchStations(it)
                        }
                    },
                    placeholder = { 
                        Text(
                            "Search stations or train number",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f)
                        ) 
                    },
                    leadingIcon = { 
                        Icon(
                            Icons.Default.Search, 
                            contentDescription = "Search",
                            tint = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                        ) 
                    },
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = Color.Transparent,
                        focusedContainerColor = Color.Transparent,
                        unfocusedBorderColor = Color.Transparent,
                        focusedBorderColor = Color.Transparent,
                        unfocusedTextColor = MaterialTheme.colorScheme.onBackground,
                        focusedTextColor = MaterialTheme.colorScheme.onBackground
                    ),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            // Train search result or station list
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // If searching for train, show train search card
                if (isTrainSearch) {
                    item {
                        GlassmorphicCardElevated(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { 
                                    onNavigateToTrainDetail(searchText.trim()) 
                                }
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "Train ${searchText.trim()}",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onBackground
                                    )
                                    Text(
                                        text = if (searchText.startsWith("A", ignoreCase = true)) 
                                            "Amtrak Train" 
                                        else 
                                            "NJ Transit Train",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                                    )
                                }
                                Icon(
                                    Icons.Default.Train,
                                    contentDescription = "Train",
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                } else {
                    // Show station list
                    items(departureStations) { station ->
                        GlassmorphicCard(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { 
                                    viewModel.selectOrigin(station)
                                    // Navigate directly to destination selection
                                    onNavigateToTrains(station.code, null)
                                }
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = station.name,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Medium,
                                        color = MaterialTheme.colorScheme.onBackground
                                    )
                                    Text(
                                        text = station.code,
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                                    )
                                }
                                if (selectedOrigin == station) {
                                    Icon(
                                        Icons.Default.Check,
                                        contentDescription = "Selected",
                                        tint = MaterialTheme.colorScheme.primary
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// Simplified station selection - old complex content functions removed

@Preview(showBackground = true)
@Composable
fun StationSelectionScreenPreview() {
    StationSelectionScreen(
        onNavigateToTrains = { _, _ -> },
        onNavigateToTrainDetail = { _ -> }
    )
}
