package com.trackrat.android.data.models

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Journey(
    val id: String,
    val trainNumber: String,
    val origin: String,
    val destination: String,
    val currentStatus: String,
    val stopTimes: List<StopTime> // List of stops along the journey
)