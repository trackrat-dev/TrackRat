package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Response from /api/v2/trains/{trainId} endpoint
 */
@JsonClass(generateAdapter = true)
data class TrainDetailsResponse(
    @Json(name = "train") val train: TrainV2,
    @Json(name = "freshness") val freshness: DataFreshness
)