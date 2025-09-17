package com.trackrat.android.data.models

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class StopTime(
    val stationId: String,
    val stationName: String,
    val scheduledArrival: String?,
    val predictedArrival: String?,
    val scheduledDeparture: String?,
    val predictedDeparture: String?,
    val track: String?,
    val isCurrent: Boolean // Indicates if this is the current or next stop
)