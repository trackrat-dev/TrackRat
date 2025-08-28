package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Enhanced status with conflict resolution and location info
 */
@JsonClass(generateAdapter = true)
data class StatusV2(
    @Json(name = "status") val status: String,
    @Json(name = "enhanced_status") val enhancedStatus: String,
    @Json(name = "location") val location: String?,
    @Json(name = "last_update") val lastUpdate: String?
)