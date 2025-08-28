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
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StationSelectionScreen(
    viewModel: StationSelectionViewModel = hiltViewModel(),
    onNavigateToTrains: (originCode: String, destinationCode: String?) -> Unit,
    onNavigateToTrainDetail: (trainId: String) -> Unit
) {
    val departureStations by viewModel.departureStations.collectAsState()
    val allStations by viewModel.allStations.collectAsState()
    val searchResults by viewModel.searchResults.collectAsState()
    val selectedOrigin by viewModel.selectedOrigin.collectAsState()
    val selectedDestination by viewModel.selectedDestination.collectAsState()

    var destinationSearchText by remember { mutableStateOf("") }
    var showDestinationSearch by remember { mutableStateOf(false) }
    
    // Tab state for switching between station selection and train search
    var selectedTabIndex by remember { mutableStateOf(0) }
    var trainSearchText by remember { mutableStateOf("") }

    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            Column {
                TopAppBar(
                    title = { Text("TrackRat") },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
                
                TabRow(
                    selectedTabIndex = selectedTabIndex,
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                ) {
                    Tab(
                        selected = selectedTabIndex == 0,
                        onClick = { selectedTabIndex = 0 },
                        text = { Text("Stations") },
                        icon = { Icon(Icons.Default.Search, contentDescription = "Stations") }
                    )
                    Tab(
                        selected = selectedTabIndex == 1,
                        onClick = { selectedTabIndex = 1 },
                        text = { Text("Train Search") },
                        icon = { Icon(Icons.Default.Train, contentDescription = "Train Search") }
                    )
                }
            }
        }
    ) { paddingValues ->
        when (selectedTabIndex) {
            0 -> StationSelectionContent(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .padding(16.dp),
                departureStations = departureStations,
                searchResults = searchResults,
                selectedOrigin = selectedOrigin,
                selectedDestination = selectedDestination,
                destinationSearchText = destinationSearchText,
                showDestinationSearch = showDestinationSearch,
                onDestinationSearchTextChange = { 
                    destinationSearchText = it
                    viewModel.searchStations(it)
                },
                onOriginSelected = { station ->
                    viewModel.selectOrigin(station)
                    showDestinationSearch = true
                },
                onDestinationSelected = { station ->
                    viewModel.selectDestination(station)
                    destinationSearchText = station.name
                },
                onFindTrainsClicked = {
                    val origin = selectedOrigin
                    if (origin != null) {
                        onNavigateToTrains(
                            origin.code,
                            selectedDestination?.code
                        )
                    } else {
                        scope.launch {
                            snackbarHostState.showSnackbar("Please select a departure station")
                        }
                    }
                },
                viewModel = viewModel
            )
            1 -> TrainSearchContent(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .padding(16.dp),
                trainSearchText = trainSearchText,
                onTrainSearchTextChange = { trainSearchText = it },
                onSearchTrain = { 
                    if (trainSearchText.isNotBlank()) {
                        onNavigateToTrainDetail(trainSearchText.trim())
                    } else {
                        scope.launch {
                            snackbarHostState.showSnackbar("Please enter a train number")
                        }
                    }
                }
            )
        }
    }
}

@Composable
fun StationSelectionContent(
    modifier: Modifier = Modifier,
    departureStations: List<Station>,
    searchResults: List<Station>,
    selectedOrigin: Station?,
    selectedDestination: Station?,
    destinationSearchText: String,
    showDestinationSearch: Boolean,
    onDestinationSearchTextChange: (String) -> Unit,
    onOriginSelected: (Station) -> Unit,
    onDestinationSelected: (Station) -> Unit,
    onFindTrainsClicked: () -> Unit,
    viewModel: StationSelectionViewModel
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
            // Departure Station Selection
            Text(
                text = "Where are you departing from?",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(departureStations) { station ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                onOriginSelected(station)
                            },
                        colors = CardDefaults.cardColors(
                            containerColor = if (selectedOrigin == station) 
                                MaterialTheme.colorScheme.primaryContainer 
                            else 
                                MaterialTheme.colorScheme.surface
                        )
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = station.name,
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.Medium
                                )
                                Text(
                                    text = station.code,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            if (selectedOrigin == station) {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = "Selected",
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                }
            }

            // Destination Search (shown after origin is selected)
            if (selectedOrigin != null && showDestinationSearch) {
                Divider()
                
                Text(
                    text = "Where are you going? (Optional)",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                
                OutlinedTextField(
                    value = destinationSearchText,
                    onValueChange = onDestinationSearchTextChange,
                    label = { Text("Search destination") },
                    placeholder = { Text("Type station name...") },
                    leadingIcon = {
                        Icon(Icons.Default.Search, contentDescription = "Search")
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                
                // Search results
                if (searchResults.isNotEmpty()) {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(0.5f),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        items(searchResults) { station ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        onDestinationSelected(station)
                                    },
                                colors = CardDefaults.cardColors(
                                    containerColor = if (selectedDestination == station)
                                        MaterialTheme.colorScheme.secondaryContainer
                                    else
                                        MaterialTheme.colorScheme.surface
                                )
                            ) {
                                Text(
                                    text = "${station.name} (${station.code})",
                                    modifier = Modifier.padding(12.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Find Trains Button
            Button(
                onClick = onFindTrainsClicked,
                enabled = selectedOrigin != null,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFFF6600) // Orange like iOS app
                )
            ) {
                Text(
                    text = if (selectedDestination != null) 
                        "Find Trains to ${selectedDestination.name}"
                    else if (selectedOrigin != null)
                        "Show All Departures from ${selectedOrigin.name}"
                    else
                        "Select Departure Station",
                    modifier = Modifier.padding(vertical = 4.dp)
                )
            }
        }
    }

@Composable
fun TrainSearchContent(
    modifier: Modifier = Modifier,
    trainSearchText: String,
    onTrainSearchTextChange: (String) -> Unit,
    onSearchTrain: () -> Unit
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        // Header
        Text(
            text = "Search by Train Number",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold
        )
        
        // Search instruction
        Text(
            text = "Enter a train number to see its complete journey details and real-time status.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        // Search input
        OutlinedTextField(
            value = trainSearchText,
            onValueChange = onTrainSearchTextChange,
            label = { Text("Train number") },
            placeholder = { Text("e.g., 3265, 6621, A174") },
            leadingIcon = {
                Icon(Icons.Default.Train, contentDescription = "Train")
            },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        // Search button
        Button(
            onClick = onSearchTrain,
            enabled = trainSearchText.isNotBlank(),
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFFFF6600)
            )
        ) {
            Text(
                text = if (trainSearchText.isNotBlank()) 
                    "View Train ${trainSearchText.trim()}"
                else 
                    "Enter Train Number",
                modifier = Modifier.padding(vertical = 4.dp)
            )
        }
        
        Spacer(modifier = Modifier.weight(1f))
        
        // Help text
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.3f)
            )
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "💡 Tips",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "• NJ Transit trains: 1234, 6621, 3265",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = "• Amtrak trains: A174, A2169",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = "• Works with all active trains",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun StationSelectionScreenPreview() {
    StationSelectionScreen(
        onNavigateToTrains = { _, _ -> },
        onNavigateToTrainDetail = { _ -> }
    )
}
