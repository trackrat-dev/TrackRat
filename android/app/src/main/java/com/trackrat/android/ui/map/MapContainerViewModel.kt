package com.trackrat.android.ui.map

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.CameraPositionState
import com.trackrat.android.data.MapRegion
import com.trackrat.android.data.Stations
import com.trackrat.android.ui.components.BottomSheetPosition
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max

/**
 * ViewModel for MapContainerScreen
 * Manages map camera position, sheet position, and region calculations
 * Matches iOS MapContainerViewModel logic
 */
@HiltViewModel
class MapContainerViewModel @Inject constructor() : ViewModel() {

    // Sheet position state
    private val _sheetPosition = MutableStateFlow(BottomSheetPosition.MEDIUM)
    val sheetPosition: StateFlow<BottomSheetPosition> = _sheetPosition.asStateFlow()

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
     * Animate map to show route between two stations
     * Matching iOS calculateRegionForRoute logic
     *
     * @param from Origin station coordinates
     * @param to Destination station coordinates
     */
    fun animateToRoute(from: LatLng, to: LatLng) {
        viewModelScope.launch {
            val region = calculateRegionForRoute(from, to, _sheetPosition.value)

            // Animate camera to new position
            cameraPositionState.animate(
                update = com.google.android.gms.maps.CameraUpdateFactory.newLatLngZoom(
                    region.center,
                    region.zoom
                ),
                durationMs = 250
            )
        }
    }

    /**
     * Reset map to default Newark Penn Station view
     */
    fun resetToDefaultView() {
        viewModelScope.launch {
            cameraPositionState.animate(
                update = com.google.android.gms.maps.CameraUpdateFactory.newLatLngZoom(
                    Stations.DEFAULT_REGION.center,
                    Stations.DEFAULT_REGION.zoom
                ),
                durationMs = 250
            )
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
}
