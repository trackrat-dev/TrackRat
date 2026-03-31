package com.trackrat.android.data.models

import com.squareup.moshi.JsonClass

/**
 * Simple station model
 */
@JsonClass(generateAdapter = true)
data class Station(
    val code: String,
    val name: String
) {
    // Display name for UI
    val displayName: String
        get() = name.ifEmpty { code }
}