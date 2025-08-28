package com.trackrat.android.ui.destinationselection

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.data.models.Station
import com.trackrat.android.ui.components.GlassmorphicCard
import com.trackrat.android.ui.components.GlassmorphicSearchCard
import com.trackrat.android.ui.stationselection.StationSelectionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DestinationSelectionScreen(
    originStation: String,
    viewModel: StationSelectionViewModel = hiltViewModel(),
    onNavigateBack: () -> Unit,
    onNavigateToTrains: (destinationCode: String?) -> Unit
) {
    val allStations by viewModel.allStations.collectAsState()
    val searchResults by viewModel.searchResults.collectAsState()
    val selectedDestination by viewModel.selectedDestination.collectAsState()
    var searchText by remember { mutableStateOf("") }

    // Filter out origin station from available destinations
    val availableStations = remember(allStations, originStation) {
        allStations.filter { it.code != originStation }
    }
    
    val filteredResults = remember(searchResults, originStation) {
        searchResults.filter { it.code != originStation }
    }

    Scaffold(
        modifier = Modifier.background(MaterialTheme.colorScheme.background),
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "Where would you like to go?",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onBackground
                        )
                        Text(
                            text = "from $originStation",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.8f)
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            Icons.Default.ArrowBack,
                            contentDescription = "Back",
                            tint = MaterialTheme.colorScheme.onBackground
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(paddingValues)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Search bar
            GlassmorphicSearchCard(
                modifier = Modifier.fillMaxWidth()
            ) {
                OutlinedTextField(
                    value = searchText,
                    onValueChange = { 
                        searchText = it
                        viewModel.searchStations(it)
                    },
                    placeholder = { 
                        Text(
                            "Search destinations...",
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

            // Show all departures button
            Button(
                onClick = { onNavigateToTrains(null) },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary
                )
            ) {
                Text(
                    text = "Show All Departures from $originStation",
                    modifier = Modifier.padding(vertical = 4.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            }

            // Station list
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                val stationsToShow = if (searchText.isNotBlank()) filteredResults else availableStations
                
                items(stationsToShow) { station ->
                    GlassmorphicCard(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { 
                                viewModel.selectDestination(station)
                                onNavigateToTrains(station.code)
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
                            if (selectedDestination == station) {
                                Icon(
                                    Icons.Default.Check,
                                    contentDescription = "Selected",
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                }
                
                // Show message if no stations found in search
                if (searchText.isNotBlank() && filteredResults.isEmpty()) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No stations found matching \"$searchText\"",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun DestinationSelectionScreenPreview() {
    DestinationSelectionScreen(
        originStation = "NY",
        onNavigateBack = {},
        onNavigateToTrains = {}
    )
}