package com.trackrat.android.ui.map

import android.graphics.Point
import com.google.android.gms.maps.Projection
import com.google.android.gms.maps.model.LatLng
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * Utility for detecting taps on polyline segments using screen coordinates.
 *
 * Uses screen-space calculations (not lat/lng) for accurate tap detection
 * because Mercator projection distorts distances non-linearly.
 *
 * Matching iOS implementation from CongestionMapView.swift lines 567-621
 */
object PolylineHitDetector {

    /**
     * Find the congestion polyline segment that was tapped
     *
     * @param tapLatLng The tap location in map coordinates
     * @param segments List of polyline segments to check
     * @param projection Google Maps projection for coordinate conversion
     * @param tolerancePx Tap tolerance in screen pixels (default: 30pt matching iOS)
     * @return The tapped segment, or null if no segment within tolerance
     */
    fun findTappedSegment(
        tapLatLng: LatLng,
        segments: List<CongestionPolyline>,
        projection: Projection,
        tolerancePx: Float = 30f
    ): CongestionPolyline? {
        // Convert tap to screen coordinates (critical for accuracy)
        val tapPoint = projection.toScreenLocation(tapLatLng)

        var closestSegment: CongestionPolyline? = null
        var minDistance = Float.MAX_VALUE

        for (segment in segments) {
            // Convert segment endpoints to screen coordinates
            val segmentStart = projection.toScreenLocation(segment.fromLatLng)
            val segmentEnd = projection.toScreenLocation(segment.toLatLng)

            // Calculate distance from tap to segment in screen space
            val distance = pointToSegmentDistance(
                point = tapPoint,
                segmentStart = segmentStart,
                segmentEnd = segmentEnd
            )

            // Track closest segment within tolerance
            if (distance <= tolerancePx && distance < minDistance) {
                closestSegment = segment
                minDistance = distance
            }
        }

        return closestSegment
    }

    /**
     * Calculate the minimum distance from a point to a line segment
     * Uses point-to-line-segment formula in screen coordinates
     *
     * @param point The tap point in screen coordinates
     * @param segmentStart The segment start point in screen coordinates
     * @param segmentEnd The segment end point in screen coordinates
     * @return Distance in screen pixels
     */
    private fun pointToSegmentDistance(
        point: Point,
        segmentStart: Point,
        segmentEnd: Point
    ): Float {
        // Vector from segment start to end
        val dx = segmentEnd.x - segmentStart.x
        val dy = segmentEnd.y - segmentStart.y

        // If segment is actually a point, return distance to that point
        if (dx == 0 && dy == 0) {
            return pointToPointDistance(point, segmentStart)
        }

        // Calculate projection of point onto line segment
        // t = 0 means closest point is segmentStart
        // t = 1 means closest point is segmentEnd
        // 0 < t < 1 means closest point is somewhere along the segment
        val lengthSquared = (dx * dx + dy * dy).toFloat()
        val t = max(
            0f,
            min(
                1f,
                ((point.x - segmentStart.x) * dx + (point.y - segmentStart.y) * dy).toFloat() / lengthSquared
            )
        )

        // Calculate the closest point on the segment
        val closestX = segmentStart.x + t * dx
        val closestY = segmentStart.y + t * dy

        // Return distance from tap to closest point
        val distX = point.x - closestX
        val distY = point.y - closestY
        return hypot(distX, distY)
    }

    /**
     * Calculate distance between two points
     */
    private fun pointToPointDistance(p1: Point, p2: Point): Float {
        val dx = (p1.x - p2.x).toFloat()
        val dy = (p1.y - p2.y).toFloat()
        return hypot(dx, dy)
    }
}
