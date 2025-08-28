package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import java.time.ZonedDateTime

/**
 * Stop information within a train journey
 */
@JsonClass(generateAdapter = true)
data class Stop(
    @Json(name = "station_code") val stationCode: String,
    @Json(name = "station_name") val stationName: String,
    @Json(name = "stop_sequence") val stopSequence: Int,
    @Json(name = "scheduled_arrival") val scheduledArrival: ZonedDateTime?,
    @Json(name = "scheduled_departure") val scheduledDeparture: ZonedDateTime?,
    @Json(name = "actual_arrival") val actualArrival: ZonedDateTime?,
    @Json(name = "actual_departure") val actualDeparture: ZonedDateTime?,
    @Json(name = "has_departed_station") val hasDepartedStation: Boolean = false,
    @Json(name = "departure_source") val departureSource: String?,
    @Json(name = "track") val track: String?,
    @Json(name = "status") val status: String?
) {
    /**
     * Get display time for this stop (actual if available, otherwise scheduled)
     */
    val displayDepartureTime: ZonedDateTime?
        get() = actualDeparture ?: scheduledDeparture
    
    val displayArrivalTime: ZonedDateTime?
        get() = actualArrival ?: scheduledArrival
}