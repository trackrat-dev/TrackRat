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

/**
 * Platform prediction response from ML API endpoint
 * Contains platform-level probabilities that need to be converted to track probabilities
 */
@JsonClass(generateAdapter = true)
data class PlatformPrediction(
    @Json(name = "primary_prediction") val primaryPrediction: String,
    @Json(name = "confidence") val confidence: Float,
    @Json(name = "top_3") val top3: List<String>,
    @Json(name = "platform_probabilities") val platformProbabilities: Map<String, Float>
) {
    /**
     * Convert platform probabilities to track probabilities
     * Each platform maps to specific tracks (e.g., "1 & 2" -> tracks 1 and 2)
     */
    fun convertToTrackProbabilities(): Map<String, Double> {
        val trackProbabilities = mutableMapOf<String, Double>()

        // Platform to tracks mapping
        val platformToTracks = mapOf(
            "1 & 2" to listOf("1", "2"),
            "3 & 4" to listOf("3", "4"),
            "5 & 6" to listOf("5", "6"),
            "7 & 8" to listOf("7", "8"),
            "9 & 10" to listOf("9", "10"),
            "11 & 12" to listOf("11", "12"),
            "13 & 14" to listOf("13", "14"),
            "15 & 16" to listOf("15", "16"),
            "17" to listOf("17"),
            "18 & 19" to listOf("18", "19"),
            "20 & 21" to listOf("20", "21")
        )

        // For each platform probability, distribute to its tracks
        for ((platform, probability) in platformProbabilities) {
            val tracks = platformToTracks[platform] ?: continue
            // Distribute probability equally among tracks in the platform
            val trackProb = probability.toDouble() / tracks.size
            tracks.forEach { track ->
                trackProbabilities[track] = trackProb
            }
        }

        return trackProbabilities
    }
}