package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Individual journey segment - mirrors backend IndividualJourneySegment.
 * Used for visualizing per-train congestion on the map.
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
    @Json(name = "scheduled_departure") val scheduledDeparture: String,
    @Json(name = "actual_departure") val actualDeparture: String,
    @Json(name = "scheduled_arrival") val scheduledArrival: String,
    @Json(name = "actual_arrival") val actualArrival: String,
    @Json(name = "scheduled_minutes") val scheduledMinutes: Double,
    @Json(name = "actual_minutes") val actualMinutes: Double,
    @Json(name = "delay_minutes") val delayMinutes: Double,
    @Json(name = "congestion_factor") val congestionFactor: Double,
    @Json(name = "congestion_level") val congestionLevel: String,
    @Json(name = "is_cancelled") val isCancelled: Boolean,
    @Json(name = "journey_date") val journeyDate: String
)

/**
 * Aggregated congestion data for a route segment - mirrors backend SegmentCongestion.
 * Represents rolled-up statistics across multiple trains on a segment.
 */
@JsonClass(generateAdapter = true)
data class AggregatedSegment(
    @Json(name = "from_station") val fromStation: String,
    @Json(name = "to_station") val toStation: String,
    @Json(name = "from_station_name") val fromStationName: String,
    @Json(name = "to_station_name") val toStationName: String,
    @Json(name = "data_source") val dataSource: String,
    @Json(name = "congestion_level") val congestionLevel: String,
    @Json(name = "congestion_factor") val congestionFactor: Double,
    @Json(name = "average_delay_minutes") val averageDelayMinutes: Double,
    @Json(name = "sample_count") val sampleCount: Int,
    @Json(name = "baseline_minutes") val baselineMinutes: Double,
    @Json(name = "current_average_minutes") val currentAverageMinutes: Double,
    @Json(name = "cancellation_count") val cancellationCount: Int,
    @Json(name = "cancellation_rate") val cancellationRate: Double,
    @Json(name = "train_count") val trainCount: Int?,
    @Json(name = "baseline_train_count") val baselineTrainCount: Double?,
    @Json(name = "frequency_factor") val frequencyFactor: Double?,
    @Json(name = "frequency_level") val frequencyLevel: String?
)

/**
 * Response wrapper for congestion map endpoint - mirrors backend CongestionMapResponse.
 */
@JsonClass(generateAdapter = true)
data class CongestionResponse(
    @Json(name = "individual_segments") val individualSegments: List<CongestionSegment>,
    @Json(name = "aggregated_segments") val aggregatedSegments: List<AggregatedSegment>
)
