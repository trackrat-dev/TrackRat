package com.trackrat.android.utils

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat.startActivity

/**
 * Service for sharing train information via deep links
 * Matches iOS ShareService functionality
 */
object ShareService {

    /**
     * Share a train with others via deep link
     *
     * @param context Android context
     * @param trainNumber Train number (e.g., "3515", "A2121")
     */
    fun shareTrain(context: Context, trainNumber: String) {
        val deepLink = "trackrat://train/$trainNumber"
        val shareText = "Check out Train $trainNumber on TrackRat: $deepLink"

        val sendIntent = Intent().apply {
            action = Intent.ACTION_SEND
            putExtra(Intent.EXTRA_TEXT, shareText)
            type = "text/plain"
        }

        val shareIntent = Intent.createChooser(sendIntent, "Share Train $trainNumber")
        shareIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(shareIntent)
    }

    /**
     * Share a journey with others via deep link
     *
     * @param context Android context
     * @param fromStation Origin station code
     * @param toStation Destination station code
     */
    fun shareJourney(context: Context, fromStation: String, toStation: String) {
        val deepLink = "trackrat://journey?from=$fromStation&to=$toStation"
        val shareText = "Check out trains from $fromStation to $toStation on TrackRat: $deepLink"

        val sendIntent = Intent().apply {
            action = Intent.ACTION_SEND
            putExtra(Intent.EXTRA_TEXT, shareText)
            type = "text/plain"
        }

        val shareIntent = Intent.createChooser(sendIntent, "Share Journey")
        shareIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(shareIntent)
    }
}
