package com.trackrat.android.ui.stationselection

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.Station
import com.trackrat.android.data.models.Stations
import com.trackrat.android.data.repository.TrackRatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

/**
 * ViewModel for station selection screens
 */
@HiltViewModel
class StationSelectionViewModel @Inject constructor(
    private val repository: TrackRatRepository,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {
    
    companion object {
        // SavedState keys for state restoration
        private const val KEY_SELECTED_ORIGIN = "selected_origin_code"
        private const val KEY_SELECTED_DESTINATION = "selected_destination_code"
        private const val KEY_SEARCH_QUERY = "search_query"
    }

    // Departure stations (main 5 stations)
    private val _departureStations = MutableStateFlow(Stations.DEPARTURE_STATIONS)
    val departureStations: StateFlow<List<Station>> = _departureStations.asStateFlow()

    // All stations (for destination selection)
    private val _allStations = MutableStateFlow(Stations.ALL_STATIONS)
    val allStations: StateFlow<List<Station>> = _allStations.asStateFlow()

    // Search results
    private val _searchResults = MutableStateFlow<List<Station>>(emptyList())
    val searchResults: StateFlow<List<Station>> = _searchResults.asStateFlow()

    // Selected stations
    private val _selectedOrigin = MutableStateFlow<Station?>(null)
    val selectedOrigin: StateFlow<Station?> = _selectedOrigin.asStateFlow()

    private val _selectedDestination = MutableStateFlow<Station?>(null)
    val selectedDestination: StateFlow<Station?> = _selectedDestination.asStateFlow()

    init {
        // Restore state from SavedStateHandle if available
        restoreState()
    }
    
    /**
     * Select origin station
     */
    fun selectOrigin(station: Station) {
        _selectedOrigin.value = station
        savedStateHandle[KEY_SELECTED_ORIGIN] = station.code
    }

    /**
     * Select destination station
     */
    fun selectDestination(station: Station) {
        _selectedDestination.value = station
        savedStateHandle[KEY_SELECTED_DESTINATION] = station.code
    }

    /**
     * Search stations by query
     */
    fun searchStations(query: String) {
        savedStateHandle[KEY_SEARCH_QUERY] = query
        _searchResults.value = if (query.isBlank()) {
            emptyList()
        } else {
            Stations.search(query)
        }
    }
    
    /**
     * Clear selections
     */
    fun clearSelections() {
        _selectedOrigin.value = null
        _selectedDestination.value = null
        _searchResults.value = emptyList()
        
        // Clear saved state
        savedStateHandle.remove<String>(KEY_SELECTED_ORIGIN)
        savedStateHandle.remove<String>(KEY_SELECTED_DESTINATION)
        savedStateHandle.remove<String>(KEY_SEARCH_QUERY)
    }
    
    /**
     * Restore state from SavedStateHandle
     */
    private fun restoreState() {
        val originCode = savedStateHandle.get<String>(KEY_SELECTED_ORIGIN)
        val destinationCode = savedStateHandle.get<String>(KEY_SELECTED_DESTINATION)
        val searchQuery = savedStateHandle.get<String>(KEY_SEARCH_QUERY)
        
        // Restore selected origin
        originCode?.let { code ->
            val station = Stations.ALL_STATIONS.find { it.code == code }
            _selectedOrigin.value = station
        }
        
        // Restore selected destination
        destinationCode?.let { code ->
            val station = Stations.ALL_STATIONS.find { it.code == code }
            _selectedDestination.value = station
        }
        
        // Restore search query and results
        searchQuery?.let { query ->
            if (query.isNotBlank()) {
                _searchResults.value = Stations.search(query)
            }
        }
    }
}