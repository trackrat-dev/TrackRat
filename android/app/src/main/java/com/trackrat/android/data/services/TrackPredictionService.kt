package com.trackrat.android.data.services

import android.util.Log
import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.data.models.PlatformPrediction
import com.trackrat.android.data.models.TrainDetailV2
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Service providing ML-based track probability predictions for NY Penn Station
 * Matches iOS StaticTrackDistributionService functionality
 */
@Singleton
class TrackPredictionService @Inject constructor(
    private val apiService: TrackRatApiService
) {

    companion object {
        private const val TAG = "TrackPredictionService"
        private const val NY_PENN_STATION_CODE = "NY"
    }

    /**
     * Check if predictions should be shown for a given train
     * Predictions are only available for:
     * 1. Trains departing from NY Penn Station
     * 2. Trains without a track assigned yet
     */
    fun shouldShowPredictions(train: TrainDetailV2): Boolean {
        val isNYPenn = train.route.originCode == NY_PENN_STATION_CODE
        val noTrackAssigned = train.stops.firstOrNull()?.track.isNullOrEmpty()

        Log.d(TAG, "shouldShowPredictions: origin=${train.route.originCode}, hasTrack=${!noTrackAssigned}")

        return isNYPenn && noTrackAssigned
    }

    /**
     * Get ML-based track prediction for a train
     * Returns platform probabilities that can be grouped and displayed
     *
     * @param train The train to get predictions for
     * @return Map of platform names to probabilities, or null if not available
     */
    suspend fun getPredictionData(train: TrainDetailV2): Map<String, Double>? {
        Log.d(TAG, "🔍 Getting predictions for train ${train.trainId}")
        Log.d(TAG, "   - Origin: ${train.route.originCode}")

        // Only support NY Penn Station
        if (train.route.originCode != NY_PENN_STATION_CODE) {
            Log.d(TAG, "❌ Not NY Penn - no predictions")
            return null
        }

        // Don't show predictions if track already assigned
        val firstStopTrack = train.stops.firstOrNull()?.track
        if (!firstStopTrack.isNullOrEmpty()) {
            Log.d(TAG, "❌ Track already assigned: $firstStopTrack - no predictions")
            return null
        }

        return try {
            // Format journey date for API
            val dateFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")
            val journeyDate = train.stops.firstOrNull()?.scheduledDeparture?.format(dateFormatter)
                ?: train.journeyDate

            Log.d(TAG, "📡 Calling API for predictions...")
            Log.d(TAG, "   - Station: ${train.route.originCode}")
            Log.d(TAG, "   - Train ID: ${train.trainId}")
            Log.d(TAG, "   - Journey Date: $journeyDate")

            // Call ML platform prediction endpoint
            val platformPrediction = apiService.getPlatformPrediction(
                stationCode = train.route.originCode,
                trainId = train.trainId,
                journeyDate = journeyDate
            )

            Log.d(TAG, "✅ API returned platform predictions")
            Log.d(TAG, "   - Primary: ${platformPrediction.primaryPrediction}")
            Log.d(TAG, "   - Confidence: ${platformPrediction.confidence}")
            Log.d(TAG, "   - Top 3: ${platformPrediction.top3}")

            // Convert platform predictions to track probabilities
            val trackProbabilities = platformPrediction.convertToTrackProbabilities()

            // Group tracks back into platforms for display
            val platformProbabilities = groupTracksByPlatform(trackProbabilities)

            Log.d(TAG, "🎯 Converted to ${platformProbabilities.size} platform probabilities")
            platformProbabilities.entries.sortedByDescending { it.value }.take(3).forEach { (platform, prob) ->
                Log.d(TAG, "   - Platform $platform: ${String.format("%.1f%%", prob * 100)}")
            }

            platformProbabilities

        } catch (e: Exception) {
            Log.e(TAG, "❌ ML platform prediction failed:", e)
            Log.e(TAG, "   Error: ${e.message}")
            // If API fails, don't show predictions
            null
        }
    }

    /**
     * Groups individual track probabilities by shared platforms
     * Platforms that share the same physical location are combined
     */
    private fun groupTracksByPlatform(trackProbabilities: Map<String, Double>): Map<String, Double> {
        val platformGroups = mapOf(
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

        val platformProbabilities = mutableMapOf<String, Double>()

        for ((platformName, tracks) in platformGroups) {
            val totalProbability = tracks.mapNotNull { trackProbabilities[it] }.sum()
            if (totalProbability > 0) {
                platformProbabilities[platformName] = totalProbability
            }
        }

        return platformProbabilities
    }
}
