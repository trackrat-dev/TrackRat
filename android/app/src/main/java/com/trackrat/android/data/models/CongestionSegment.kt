package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Congestion data for a route segment between two stations
 * Used for visualizing route congestion on the map
 */
@JsonClass(generateAdapter = true)
data class CongestionSegment(
    @Json(name = "journey_id") val journeyId: String,
    @Json(name = "train_id") val trainId: String,
    @Json(name = "from_station") val fromStation: String,
    @Json(name = "to_station") val toStation: String,
    @Json(name = "from_station_name") val fromStationName: String,
    @Json(name = "to_station_name") val toStationName: String,
    @Json(name = "data_source") val dataSource: String,
    @Json(name = "congestion_factor") val congestionFactor: Double,
    @Json(name = "congestion_level") val congestionLevel: String,
    @Json(name = "average_delay_minutes") val averageDelayMinutes: Double,
    @Json(name = "baseline_minutes") val baselineMinutes: Double,
    @Json(name = "current_average_minutes") val currentAverageMinutes: Double,
    @Json(name = "sample_count") val sampleCount: Int,
    @Json(name = "cancellation_count") val cancellationCount: Int,
    @Json(name = "cancellation_rate") val cancellationRate: Double
)

/**
 * Response wrapper for congestion API endpoint
 */
@JsonClass(generateAdapter = true)
data class CongestionResponse(
    @Json(name = "individual_segments") val individualSegments: List<CongestionSegment>
)
