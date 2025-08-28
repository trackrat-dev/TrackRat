package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import java.time.ZonedDateTime

/**
 * Real-time journey progress information
 */
@JsonClass(generateAdapter = true)
data class Progress(
    @Json(name = "stops_completed") val stopsCompleted: Int,
    @Json(name = "stops_total") val stopsTotal: Int,
    @Json(name = "journey_percent") val journeyPercent: Float,
    @Json(name = "last_departed") val lastDeparted: DepartedStation?,
    @Json(name = "next_arrival") val nextArrival: NextArrival?
)

@JsonClass(generateAdapter = true)
data class DepartedStation(
    @Json(name = "station_code") val stationCode: String,
    @Json(name = "station_name") val stationName: String,
    @Json(name = "departed_at") val departedAt: ZonedDateTime?,
    @Json(name = "delay_minutes") val delayMinutes: Int?
)

@JsonClass(generateAdapter = true)
data class NextArrival(
    @Json(name = "station_code") val stationCode: String,
    @Json(name = "station_name") val stationName: String,
    @Json(name = "estimated_time") val estimatedTime: ZonedDateTime?,
    @Json(name = "minutes_to_arrival") val minutesToArrival: Int?
)