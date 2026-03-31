package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Response from /api/v2/trains/{trainId} endpoint
 * The API returns only a "train" object that contains all the data including data_freshness
 */
@JsonClass(generateAdapter = true)
data class TrainDetailsResponse(
    @Json(name = "train") val train: TrainDetailV2
)