package com.trackrat.android.ui.map

import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.CameraPositionState
import com.trackrat.android.data.MapRegion
import com.trackrat.android.data.Stations
import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.ui.components.BottomSheetPosition
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max

/**
 * Data class for selected route polyline
 */
data class SelectedRoute(
    val fromStation: String,
    val toStation: String,
    val fromLatLng: LatLng,
    val toLatLng: LatLng
)

/**
 * Data class for rendered congestion segment polyline
 */
data class CongestionPolyline(
    val fromLatLng: LatLng,
    val toLatLng: LatLng,
    val congestionFactor: Double,
    val color: Color,
    val width: Float
)

/**
 * ViewModel for MapContainerScreen
 * Manages map camera position, sheet position, and region calculations
 * Matches iOS MapContainerViewModel logic
 */
@HiltViewModel
class MapContainerViewModel @Inject constructor(
    private val apiService: TrackRatApiService
) : ViewModel() {

    // Sheet position state
    private val _sheetPosition = MutableStateFlow(BottomSheetPosition.MEDIUM)
    val sheetPosition: StateFlow<BottomSheetPosition> = _sheetPosition.asStateFlow()

    // Selected route state
    private val _selectedRoute = MutableStateFlow<SelectedRoute?>(null)
    val selectedRoute: StateFlow<SelectedRoute?> = _selectedRoute.asStateFlow()

    // Congestion polylines state
    private val _congestionPolylines = MutableStateFlow<List<CongestionPolyline>>(emptyList())
    val congestionPolylines: StateFlow<List<CongestionPolyline>> = _congestionPolylines.asStateFlow()

    // Selected segment state (for tap-to-highlight)
    private val _selectedSegmentId = MutableStateFlow<String?>(null)
    val selectedSegmentId: StateFlow<String?> = _selectedSegmentId.asStateFlow()

    // Camera position state (initialized to Newark Penn Station default)
    var cameraPositionState by mutableStateOf(
        CameraPositionState(
            position = CameraPosition.fromLatLngZoom(
                Stations.DEFAULT_REGION.center,
                Stations.DEFAULT_REGION.zoom
            )
        )
    )
        private set

    /**
     * Update sheet position and adjust map center accordingly
     */
    fun updateSheetPosition(position: BottomSheetPosition) {
        _sheetPosition.value = position
        // Adjust map center for new sheet position if needed
        // This will be implemented when we add route selection
    }

    /**
     * Set selected route and animate map to show the route
     */
    fun setSelectedRoute(fromStationCode: String, toStationCode: String) {
        val fromCoords = Stations.getCoordinates(fromStationCode)
        val toCoords = Stations.getCoordinates(toStationCode)

        if (fromCoords != null && toCoords != null) {
            _selectedRoute.value = SelectedRoute(
                fromStation = fromStationCode,
                toStation = toStationCode,
                fromLatLng = fromCoords,
                toLatLng = toCoords
            )
            animateToRoute(fromCoords, toCoords)
        }
    }

    /**
     * Clear the selected route polyline
     */
    fun clearSelectedRoute() {
        _selectedRoute.value = null
        _selectedSegmentId.value = null // Also clear segment selection
    }

    /**
     * Select a congestion segment for highlighting
     * @param segment The segment to highlight, or null to clear selection
     */
    fun selectSegment(segment: CongestionPolyline?) {
        _selectedSegmentId.value = segment?.let {
            // Create unique ID from coordinates
            "${it.fromLatLng.latitude},${it.fromLatLng.longitude}-${it.toLatLng.latitude},${it.toLatLng.longitude}"
        }
    }

    /**
     * Animate map to show route between two stations
     * Matching iOS calculateRegionForRoute logic
     *
     * @param from Origin station coordinates
     * @param to Destination station coordinates
     */
    fun animateToRoute(from: LatLng, to: LatLng) {
        viewModelScope.launch {
            val region = calculateRegionForRoute(from, to, _sheetPosition.value)
            try {
                cameraPositionState.animate(
                    update = com.google.android.gms.maps.CameraUpdateFactory.newLatLngZoom(
                        region.center,
                        region.zoom
                    ),
                    durationMs = 250
                )
            } catch (_: Exception) {
                // User interrupted animation - expected when dragging map during animation
            }
        }
    }

    /**
     * Reset map to default Newark Penn Station view
     */
    fun resetToDefaultView() {
        viewModelScope.launch {
            try {
                cameraPositionState.animate(
                    update = com.google.android.gms.maps.CameraUpdateFactory.newLatLngZoom(
                        Stations.DEFAULT_REGION.center,
                        Stations.DEFAULT_REGION.zoom
                    ),
                    durationMs = 250
                )
            } catch (_: Exception) {
                // User interrupted animation - expected when dragging map during animation
            }
        }
    }

    /**
     * Calculate map region for route between two stations
     * Matches iOS MapContainerView.calculateRegionForRoute logic
     *
     * Key features:
     * - 2x padding multiplier for span
     * - Minimum 0.3° span to prevent over-zooming
     * - Zoom-aware latitude offset based on sheet position
     *
     * @param from Origin coordinates
     * @param to Destination coordinates
     * @param sheetPosition Current sheet position
     * @return MapRegion with center and zoom
     */
    private fun calculateRegionForRoute(
        from: LatLng,
        to: LatLng,
        sheetPosition: BottomSheetPosition
    ): MapRegion {
        // Calculate center point
        val centerLat = (from.latitude + to.latitude) / 2
        val centerLng = (from.longitude + to.longitude) / 2

        // Calculate span with 2x padding (matching iOS)
        val latDelta = abs(from.latitude - to.latitude) * 2.0
        val lngDelta = abs(from.longitude - to.longitude) * 2.0

        // Use larger of the two deltas, with minimum of 0.3°
        val span = max(max(latDelta, lngDelta), 0.3)

        // Calculate zoom-aware offset (matching iOS logic from lines 484-502)
        val offset = calculateZoomAwareOffset(sheetPosition, span)

        // Adjust center latitude (shift south to keep content visible above sheet)
        val adjustedCenter = LatLng(centerLat + offset, centerLng)

        // Convert span to Google Maps zoom level
        val zoom = getZoomForSpan(span)

        return MapRegion(
            center = adjustedCenter,
            zoom = zoom
        )
    }

    /**
     * Calculate zoom-aware offset for map center
     * Matches iOS MapContainerView.calculateZoomAwareOffset (lines 484-502)
     *
     * Base offsets (southward adjustment to keep route visible):
     * - MEDIUM (50% visible): -0.10 latitude (~7 miles south)
     * - EXPANDED (100% visible): -0.38 latitude (~25 miles south)
     *
     * Scale factor: Larger zooms get proportionally larger offsets (up to 3x)
     *
     * @param position Sheet position
     * @param span Map span in degrees
     * @return Latitude offset in degrees
     */
    private fun calculateZoomAwareOffset(
        position: BottomSheetPosition,
        span: Double
    ): Double {
        val baseOffset = when (position) {
            BottomSheetPosition.MEDIUM -> -0.10
            BottomSheetPosition.EXPANDED -> -0.38
        }

        // Scale factor based on zoom level
        val scaleFactor = max(1.0, span / 0.3).coerceAtMost(3.0)

        return baseOffset * scaleFactor
    }

    /**
     * Convert coordinate span to Google Maps zoom level
     * Google Maps uses discrete zoom levels (3-21) vs. iOS span (degrees)
     *
     * Approximate conversions:
     * - Zoom 10 ≈ 0.3° span
     * - Zoom 8 ≈ 1.2° span
     * - Zoom 6 ≈ 4.8° span
     *
     * Formula: zoom = 10 - log2(span / 0.3)
     *
     * @param span Coordinate span in degrees
     * @return Google Maps zoom level (6-15)
     */
    private fun getZoomForSpan(span: Double): Float {
        // Base zoom 10 for 0.3° span, adjust logarithmically
        val zoom = 10 - (ln(span / 0.3) / ln(2.0))
        return zoom.toFloat().coerceIn(6f, 15f)
    }

    /**
     * Load congestion data from API and convert to polylines
     * Automatically refreshes every 5 minutes
     */
    fun loadCongestionData() {
        viewModelScope.launch {
            try {
                Log.d(TAG, "Loading congestion data...")
                val response = apiService.getCongestionData(
                    timeWindowHours = 3,
                    maxPerSegment = 200
                )

                Log.d(TAG, "Received ${response.individualSegments.size} total segments from API")

                // Track matching statistics
                var matchedSegments = 0
                var missingFromStations = mutableSetOf<String>()
                var missingToStations = mutableSetOf<String>()

                // Convert API segments to polylines with coordinates
                val polylines = response.individualSegments.mapNotNull { segment ->
                    val fromCoords = Stations.getCoordinates(segment.fromStation)
                    val toCoords = Stations.getCoordinates(segment.toStation)

                    if (fromCoords != null && toCoords != null) {
                        matchedSegments++
                        CongestionPolyline(
                            fromLatLng = fromCoords,
                            toLatLng = toCoords,
                            congestionFactor = segment.congestionFactor,
                            color = getCongestionColor(segment.congestionFactor),
                            width = getCongestionWidth(segment.congestionFactor)
                        )
                    } else {
                        // Track missing stations for debugging
                        if (fromCoords == null) missingFromStations.add(segment.fromStation)
                        if (toCoords == null) missingToStations.add(segment.toStation)
                        null // Skip segments with unknown station codes
                    }
                }

                _congestionPolylines.value = polylines

                Log.d(TAG, "Successfully matched $matchedSegments segments with coordinates")
                Log.d(TAG, "Created ${polylines.size} polylines for rendering")

                if (missingFromStations.isNotEmpty() || missingToStations.isNotEmpty()) {
                    Log.w(TAG, "Missing station coordinates - From: ${missingFromStations.size} stations, To: ${missingToStations.size} stations")
                    Log.w(TAG, "Missing from stations: ${missingFromStations.sorted().take(10)}")
                    Log.w(TAG, "Missing to stations: ${missingToStations.sorted().take(10)}")
                }

                // Schedule next refresh in 5 minutes
                delay(300_000) // 5 minutes
                loadCongestionData() // Recursive call for continuous refresh
            } catch (e: Exception) {
                Log.e(TAG, "Error loading congestion data", e)
                // Log error but don't crash - map still works without congestion
                _congestionPolylines.value = emptyList()
            }
        }
    }

    companion object {
        private const val TAG = "MapViewModel"
    }

    /**
     * Get color for congestion level
     * Matching iOS color scheme
     */
    private fun getCongestionColor(factor: Double): Color = when {
        factor < 1.05 -> Color(0xFF34C759)  // Green - normal
        factor < 1.25 -> Color(0xFFFFCC00)  // Yellow - slight delay
        factor < 2.0 -> Color(0xFFFF9500)   // Orange - moderate delay
        else -> Color(0xFFFF3B30)           // Red - severe delay
    }

    /**
     * Get polyline width based on congestion factor
     * Range from 5pt (normal) to 11pt (severe)
     */
    private fun getCongestionWidth(factor: Double): Float {
        return (5.0 + (factor - 1.0) * 6.0).coerceIn(5.0, 11.0).toFloat()
    }
}
