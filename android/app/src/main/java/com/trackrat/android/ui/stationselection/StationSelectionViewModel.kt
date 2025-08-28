package com.trackrat.android.ui.stationselection

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
    private val repository: TrackRatRepository
) : ViewModel() {

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

    /**
     * Select origin station
     */
    fun selectOrigin(station: Station) {
        _selectedOrigin.value = station
    }

    /**
     * Select destination station
     */
    fun selectDestination(station: Station) {
        _selectedDestination.value = station
    }

    /**
     * Search stations by query
     */
    fun searchStations(query: String) {
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
    }
}