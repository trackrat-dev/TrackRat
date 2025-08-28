package com.trackrat.android.data.models

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Train(
    val trainNumber: String,
    val origin: String,
    val destination: String,
    val scheduledDeparture: String,
    val scheduledArrival: String,
    val status: String,
    val predictedTrack: String? = null // Nullable as it might not always be available
)