package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode
import java.time.ZonedDateTime

/**
 * Enhanced train model with V2 API fields
 */
@JsonClass(generateAdapter = true)
data class TrainV2(
    @Json(name = "train_id") val trainId: String,
    @Json(name = "train_number") val trainNumber: String?,
    @Json(name = "line_code") val lineCode: String?,
    @Json(name = "line_name") val lineName: String?,
    @Json(name = "direction") val direction: String?,
    @Json(name = "origin_station_code") val originStationCode: String,
    @Json(name = "origin_station_name") @HtmlDecode val originStationName: String,
    @Json(name = "terminal_station_code") val terminalStationCode: String,
    @Json(name = "terminal_station_name") @HtmlDecode val terminalStationName: String,
    @Json(name = "destination") @HtmlDecode val destination: String?,
    @Json(name = "scheduled_departure") val scheduledDeparture: ZonedDateTime,
    @Json(name = "scheduled_arrival") val scheduledArrival: ZonedDateTime?,
    @Json(name = "status") val status: String,
    @Json(name = "status_v2") val statusV2: StatusV2?,
    @Json(name = "progress") val progress: Progress?,
    @Json(name = "track") val track: String?,
    @Json(name = "track_change") val trackChange: Boolean = false,
    @Json(name = "stops") val stops: List<Stop>?,
    @Json(name = "data_source") val dataSource: String,
    @Json(name = "is_cancelled") val isCancelled: Boolean = false,
    @Json(name = "is_completed") val isCompleted: Boolean = false,
    @Json(name = "prediction") val prediction: PredictionData?
) {
    /**
     * Get the scheduled departure time from a specific station
     */
    fun getScheduledDepartureTime(fromStationCode: String): ZonedDateTime? {
        // If it's the origin, use the main scheduled departure
        if (fromStationCode == originStationCode) {
            return scheduledDeparture
        }
        // Otherwise, find the stop and get its scheduled departure
        return stops?.find { it.stationCode == fromStationCode }?.scheduledDeparture
    }
    
    /**
     * Get a display-friendly status string
     */
    val displayStatus: String
        get() = statusV2?.enhancedStatus ?: status

    /**
     * Check if train has departed from a specific station
     * Mirrors iOS TrainV2.hasTrainDepartedFromStation()
     */
    private fun hasTrainDepartedFromStation(stationCode: String): Boolean {
        return stops?.find { it.stationCode == stationCode }?.hasDepartedStation ?: false
    }

    /**
     * Check if train has already departed from the specified station
     * Mirrors iOS TrainV2.hasAlreadyDeparted(fromStationCode:)
     *
     * Priority order (matching iOS):
     * 1. Use stop's hasDepartedStation flag (most accurate)
     * 2. Check actual departure time from stop data
     * 3. Check scheduled time + 1 minute buffer
     * 4. Return false if no data (safe default - keep train in list)
     */
    fun hasAlreadyDeparted(fromStationCode: String): Boolean {
        val now = ZonedDateTime.now(java.time.ZoneId.of("America/New_York"))

        // First priority: Use existing stop data method (most accurate)
        if (hasTrainDepartedFromStation(fromStationCode)) {
            return true
        }

        // Second priority: Check actual departure time from stop data
        val stop = stops?.find { it.stationCode == fromStationCode }
        if (stop != null) {
            stop.actualDeparture?.let { actualDeparture ->
                return actualDeparture.isBefore(now)
            }
        }

        // Third priority: Check scheduled time with buffer for delays
        val scheduledDeparture = getScheduledDepartureTime(fromStationCode)
        if (scheduledDeparture != null) {
            // Allow 1 minute past scheduled time for delays/late boarding (matching iOS)
            val departureWithBuffer = scheduledDeparture.plusMinutes(1)
            return departureWithBuffer.isBefore(now)
        }

        // If no departure time available, don't filter out (safe default)
        return false
    }
}