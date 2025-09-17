package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.trackrat.android.data.api.HtmlDecode

/**
 * Enhanced status with conflict resolution and location info
 */
@JsonClass(generateAdapter = true)
data class StatusV2(
    @Json(name = "status") val status: String,
    @Json(name = "enhanced_status") @HtmlDecode val enhancedStatus: String,
    @Json(name = "location") @HtmlDecode val location: String?,
    @Json(name = "last_update") val lastUpdate: String?
)