package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode
import java.time.ZonedDateTime

/**
 * Actual train detail model matching the V2 API response structure
 */
@JsonClass(generateAdapter = true)
data class TrainDetailV2(
    @Json(name = "train_id") val trainId: String,
    @Json(name = "journey_date") val journeyDate: String,
    @Json(name = "line") val line: LineInfoV2,
    @Json(name = "route") val route: RouteInfoV2,
    @Json(name = "train_position") val trainPosition: TrainPositionV2?,
    @Json(name = "stops") val stops: List<StopDetail>,
    @Json(name = "data_freshness") val dataFreshness: DataFreshnessV2,
    @Json(name = "data_source") val dataSource: String,
    @Json(name = "raw_train_state") val rawTrainState: String?,
    @Json(name = "is_cancelled") val isCancelled: Boolean,
    @Json(name = "is_completed") val isCompleted: Boolean,
    @Json(name = "progress") val progress: ProgressV2?,
    @Json(name = "predicted_arrival") val predictedArrival: ZonedDateTime?
)

@JsonClass(generateAdapter = true)
data class LineInfoV2(
    @Json(name = "code") val code: String,
    @Json(name = "name") val name: String,
    @Json(name = "color") val color: String
)

@JsonClass(generateAdapter = true)
data class RouteInfoV2(
    @Json(name = "origin") @HtmlDecode val origin: String,
    @Json(name = "destination") @HtmlDecode val destination: String,
    @Json(name = "origin_code") val originCode: String,
    @Json(name = "destination_code") val destinationCode: String
)

@JsonClass(generateAdapter = true)
data class TrainPositionV2(
    @Json(name = "last_departed_station_code") val lastDepartedStationCode: String?,
    @Json(name = "at_station_code") val atStationCode: String?,
    @Json(name = "next_station_code") val nextStationCode: String?,
    @Json(name = "between_stations") val betweenStations: Boolean
)

@JsonClass(generateAdapter = true)
data class StopDetail(
    @Json(name = "station") val station: StationInfo,
    @Json(name = "stop_sequence") val stopSequence: Int,
    @Json(name = "scheduled_arrival") val scheduledArrival: ZonedDateTime?,
    @Json(name = "scheduled_departure") val scheduledDeparture: ZonedDateTime?,
    @Json(name = "updated_arrival") val updatedArrival: ZonedDateTime?,
    @Json(name = "updated_departure") val updatedDeparture: ZonedDateTime?,
    @Json(name = "actual_arrival") val actualArrival: ZonedDateTime?,
    @Json(name = "actual_departure") val actualDeparture: ZonedDateTime?,
    @Json(name = "track") val track: String?,
    @Json(name = "track_assigned_at") val trackAssignedAt: ZonedDateTime?,
    @Json(name = "raw_status") val rawStatus: RawStatus?,
    @Json(name = "has_departed_station") val hasDepartedStation: Boolean,
    @Json(name = "predicted_arrival") val predictedArrival: ZonedDateTime?,
    @Json(name = "predicted_arrival_samples") val predictedArrivalSamples: Int?
)

@JsonClass(generateAdapter = true)
data class StationInfo(
    @Json(name = "code") val code: String,
    @Json(name = "name") @HtmlDecode val name: String
)

@JsonClass(generateAdapter = true)
data class RawStatus(
    @Json(name = "amtrak_status") val amtrakStatus: String?,
    @Json(name = "njt_departed_flag") val njtDepartedFlag: String?
)

@JsonClass(generateAdapter = true)
data class DataFreshnessV2(
    @Json(name = "last_updated") val lastUpdated: String,
    @Json(name = "age_seconds") val ageSeconds: Int,
    @Json(name = "update_count") val updateCount: Int,
    @Json(name = "collection_method") val collectionMethod: String?
)

@JsonClass(generateAdapter = true)
data class ProgressV2(
    @Json(name = "stops_completed") val stopsCompleted: Int,
    @Json(name = "stops_total") val stopsTotal: Int,
    @Json(name = "journey_percent") val journeyPercent: Double,
    @Json(name = "minutes_to_arrival") val minutesToArrival: Int?,
    @Json(name = "last_departed") val lastDeparted: String?,
    @Json(name = "next_arrival") val nextArrival: String?
)