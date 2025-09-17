package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode
import java.time.ZonedDateTime

/**
 * Response from /api/v2/trains/departures endpoint
 */
@JsonClass(generateAdapter = true)
data class DeparturesResponse(
    @Json(name = "departures") val departures: List<DepartureV2>,
    @Json(name = "metadata") val metadata: DepartureMetadata
)

@JsonClass(generateAdapter = true)
data class SimpleStation(
    @Json(name = "code") val code: String,
    @Json(name = "name") @HtmlDecode val name: String
)

@JsonClass(generateAdapter = true)
data class DataFreshness(
    @Json(name = "last_updated") val lastUpdated: ZonedDateTime,
    @Json(name = "is_stale") val isStale: Boolean,
    @Json(name = "staleness_seconds") val stalenessSeconds: Int?
)

@JsonClass(generateAdapter = true)
data class DepartureMetadata(
    @Json(name = "from_station") val fromStation: SimpleStation,
    @Json(name = "to_station") val toStation: SimpleStation?,
    @Json(name = "count") val count: Int,
    @Json(name = "generated_at") val generatedAt: ZonedDateTime
)