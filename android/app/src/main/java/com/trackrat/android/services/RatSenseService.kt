package com.trackrat.android.services

import com.trackrat.android.data.preferences.UserPreferencesRepository
import kotlinx.coroutines.flow.first
import java.time.ZoneId
import java.time.ZonedDateTime
import javax.inject.Inject
import javax.inject.Singleton

/**
 * RatSense AI Service - Intelligent journey suggestions
 * Matches iOS RatSenseService functionality
 *
 * Provides context-aware journey suggestions based on:
 * - Time of day (morning/evening commute detection)
 * - Home/work station learning
 * - Recent trip context (within 20 minutes)
 * - Return journey prediction (2-8 hours after tracking started)
 */
@Singleton
class RatSenseService @Inject constructor(
    private val preferences: UserPreferencesRepository
) {

    data class JourneySuggestion(
        val from: String,
        val to: String,
        val reason: String,
        val confidence: SuggestionConfidence
    )

    enum class SuggestionConfidence {
        HIGH,   // 80%+ - Based on established patterns
        MEDIUM, // 50-79% - Likely based on context
        LOW     // <50% - Weak signal
    }

    private companion object {
        const val EASTERN_ZONE = "America/New_York"
        const val MORNING_START_HOUR = 5
        const val MORNING_END_HOUR = 9
        const val EVENING_START_HOUR = 13 // 1pm
        const val EVENING_END_HOUR = 20 // 8pm
        const val RECENT_CONTEXT_MINUTES = 20
        const val RETURN_TRIP_MIN_HOURS = 2
        const val RETURN_TRIP_MAX_HOURS = 8
    }

    /**
     * Get AI-powered journey suggestions based on current context
     * Returns a list of suggestions ordered by confidence
     */
    suspend fun getSuggestions(): List<JourneySuggestion> {
        val prefs = preferences.userPreferencesFlow.first()
        val suggestions = mutableListOf<JourneySuggestion>()
        val now = ZonedDateTime.now(ZoneId.of(EASTERN_ZONE))
        val currentHour = now.hour

        // 1. Recent context suggestion (highest priority)
        // If user viewed a route within last 20 minutes, suggest it again
        prefs.recentTripFrom?.let { from ->
            prefs.recentTripTo?.let { to ->
                val recentTripAge = System.currentTimeMillis() - prefs.recentTripTime
                val recentTripMinutes = recentTripAge / (1000 * 60)

                if (recentTripMinutes < RECENT_CONTEXT_MINUTES) {
                    suggestions.add(
                        JourneySuggestion(
                            from = from,
                            to = to,
                            reason = "You searched this ${recentTripMinutes}m ago",
                            confidence = SuggestionConfidence.HIGH
                        )
                    )
                }
            }
        }

        // 2. Return journey suggestion
        // If user started tracking 2-8 hours ago, suggest return trip
        prefs.lastTrackingFrom?.let { from ->
            prefs.lastTrackingTo?.let { to ->
                val trackingAge = System.currentTimeMillis() - prefs.lastTrackingTime
                val trackingHours = trackingAge / (1000 * 60 * 60)

                if (trackingHours in RETURN_TRIP_MIN_HOURS..RETURN_TRIP_MAX_HOURS) {
                    suggestions.add(
                        JourneySuggestion(
                            from = to,  // Reverse direction
                            to = from,
                            reason = "Return trip from your ${from}→${to} journey",
                            confidence = SuggestionConfidence.HIGH
                        )
                    )
                }
            }
        }

        // 3. Commute detection (morning: home→work, evening: work→home)
        val isMorningCommute = currentHour in MORNING_START_HOUR until MORNING_END_HOUR
        val isEveningCommute = currentHour in EVENING_START_HOUR until EVENING_END_HOUR

        if (isMorningCommute && prefs.homeStation != null && prefs.workStation != null) {
            suggestions.add(
                JourneySuggestion(
                    from = prefs.homeStation,
                    to = prefs.workStation,
                    reason = "Morning commute to work",
                    confidence = SuggestionConfidence.MEDIUM
                )
            )
        } else if (isEveningCommute && prefs.homeStation != null && prefs.workStation != null) {
            suggestions.add(
                JourneySuggestion(
                    from = prefs.workStation,
                    to = prefs.homeStation,
                    reason = "Evening commute home",
                    confidence = SuggestionConfidence.MEDIUM
                )
            )
        }

        // Remove duplicates (prioritize earlier suggestions which have higher confidence)
        return suggestions.distinctBy { "${it.from}-${it.to}" }
    }

    /**
     * Check if we should show RatSense suggestions
     * Returns true if there's at least one high/medium confidence suggestion
     */
    suspend fun hasSuggestions(): Boolean {
        val suggestions = getSuggestions()
        return suggestions.any {
            it.confidence == SuggestionConfidence.HIGH ||
            it.confidence == SuggestionConfidence.MEDIUM
        }
    }
}
