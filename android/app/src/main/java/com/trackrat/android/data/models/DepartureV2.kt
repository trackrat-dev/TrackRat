package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode
import java.time.ZonedDateTime

/**
 * Individual departure from the V2 API
 */
@JsonClass(generateAdapter = true)
data class DepartureV2(
    @Json(name = "train_id") val trainId: String,
    @Json(name = "line") val line: LineInfo,
    @Json(name = "destination") @HtmlDecode val destination: String?,
    @Json(name = "departure") val departure: StationTime,
    @Json(name = "arrival") val arrival: StationTime,
    @Json(name = "train_position") val trainPosition: TrainPosition?,
    @Json(name = "data_freshness") val dataFreshness: DepartureFreshness,
    @Json(name = "data_source") val dataSource: String,
    @Json(name = "is_cancelled") val isCancelled: Boolean = false,
    @Json(name = "progress") val progress: Progress?,
    @Json(name = "predicted_arrival") val predictedArrival: ZonedDateTime?
)

@JsonClass(generateAdapter = true)
data class LineInfo(
    @Json(name = "code") val code: String?,
    @Json(name = "name") val name: String?,
    @Json(name = "color") val color: String?
)

@JsonClass(generateAdapter = true)
data class StationTime(
    @Json(name = "code") val code: String,
    @Json(name = "name") @HtmlDecode val name: String,
    @Json(name = "scheduled_time") val scheduledTime: ZonedDateTime?,
    @Json(name = "updated_time") val updatedTime: ZonedDateTime?,
    @Json(name = "actual_time") val actualTime: ZonedDateTime?,
    @Json(name = "track") val track: String?
)

@JsonClass(generateAdapter = true)
data class TrainPosition(
    @Json(name = "last_departed_station_code") val lastDepartedStationCode: String?,
    @Json(name = "at_station_code") val atStationCode: String?,
    @Json(name = "next_station_code") val nextStationCode: String?,
    @Json(name = "between_stations") val betweenStations: Boolean = false
)

@JsonClass(generateAdapter = true)
data class DepartureFreshness(
    @Json(name = "last_updated") val lastUpdated: ZonedDateTime,
    @Json(name = "age_seconds") val ageSeconds: Int,
    @Json(name = "update_count") val updateCount: Int,
    @Json(name = "collection_method") val collectionMethod: String?
)

