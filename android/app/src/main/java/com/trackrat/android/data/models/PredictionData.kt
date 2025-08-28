package com.trackrat.android.data.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Owl system track prediction with confidence levels
 */
@JsonClass(generateAdapter = true)
data class PredictionData(
    @Json(name = "primary_prediction") val primaryPrediction: String?,
    @Json(name = "confidence") val confidence: Float,
    @Json(name = "top_3") val top3: List<String>,
    @Json(name = "platform_probabilities") val platformProbabilities: Map<String, Float>
) {
    /**
     * Get confidence level category
     */
    val confidenceLevel: ConfidenceLevel
        get() = when {
            confidence >= 0.8f -> ConfidenceLevel.HIGH
            confidence >= 0.5f -> ConfidenceLevel.MEDIUM
            else -> ConfidenceLevel.LOW
        }
    
    /**
     * Get display text for confidence
     */
    val confidenceText: String
        get() = "${(confidence * 100).toInt()}% confidence"
}

enum class ConfidenceLevel {
    HIGH,    // >= 80% - green
    MEDIUM,  // 50-79% - yellow
    LOW      // < 50% - red
}