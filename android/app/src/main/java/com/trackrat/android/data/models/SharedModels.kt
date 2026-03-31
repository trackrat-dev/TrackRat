package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode
import java.time.ZonedDateTime

/**
 * Shared data models used across different API responses
 * This file consolidates duplicate models that were previously defined in multiple places
 */

@JsonClass(generateAdapter = true)
data class LineInfo(
    @Json(name = "code") val code: String?,
    @Json(name = "name") val name: String?,
    @Json(name = "color") val color: String?
)

@JsonClass(generateAdapter = true)
data class TrainPosition(
    @Json(name = "last_departed_station_code") val lastDepartedStationCode: String?,
    @Json(name = "at_station_code") val atStationCode: String?,
    @Json(name = "next_station_code") val nextStationCode: String?,
    @Json(name = "between_stations") val betweenStations: Boolean = false
)

// Data freshness model for DepartureV2 
@JsonClass(generateAdapter = true)
data class DepartureFreshness(
    @Json(name = "last_updated") val lastUpdated: ZonedDateTime,
    @Json(name = "age_seconds") val ageSeconds: Int,
    @Json(name = "update_count") val updateCount: Int,
    @Json(name = "collection_method") val collectionMethod: String?
)

@JsonClass(generateAdapter = true)
data class StationInfo(
    @Json(name = "code") val code: String,
    @Json(name = "name") @HtmlDecode val name: String
)

// Progress model for DepartureV2 and TrainV2
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