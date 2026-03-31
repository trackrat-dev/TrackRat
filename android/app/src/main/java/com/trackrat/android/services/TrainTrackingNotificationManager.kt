package com.trackrat.android.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.widget.RemoteViews
import androidx.core.app.NotificationCompat
import com.trackrat.android.MainActivity
import com.trackrat.android.R
import com.trackrat.android.data.models.TrainDetailV2
import com.trackrat.android.data.models.StatusV2
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TrainTrackingNotificationManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val CHANNEL_ID = "train_tracking_channel"
        private const val CHANNEL_NAME = "Train Tracking"
        private const val CHANNEL_DESCRIPTION = "Ongoing notifications for train tracking"
    }

    fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val importance = NotificationManager.IMPORTANCE_LOW // Low importance for ongoing notifications
            val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance).apply {
                description = CHANNEL_DESCRIPTION
                setShowBadge(false)
                setSound(null, null) // No sound for ongoing notifications
            }

            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun buildInitialNotification(
        trainId: String,
        origin: String,
        destination: String
    ): Notification {
        val contentIntent = createContentIntent()
        val stopIntent = createStopIntent()

        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_train)
            .setContentTitle("🚂 Train $trainId")
            .setContentText("$origin → $destination")
            .setStyle(NotificationCompat.BigTextStyle()
                .bigText("Loading train information...\n$origin → $destination"))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true) // Cannot be dismissed
            .setContentIntent(contentIntent)
            .addAction(R.drawable.ic_stop, "Stop Tracking", stopIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    fun buildTrackingNotification(
        train: TrainDetailV2,
        originCode: String,
        destinationCode: String
    ): Notification {
        val contentIntent = createContentIntent()
        val stopIntent = createStopIntent()

        // Get origin and destination names
        val originName = train.stops.find { it.station.code == originCode }?.station?.name ?: originCode
        val destinationName = train.stops.find { it.station.code == destinationCode }?.station?.name ?: destinationCode

        // Calculate journey progress
        val progress = calculateJourneyProgress(train, originCode, destinationCode)

        // Get current status
        val status = train.rawTrainState ?: ""
        val isBoarding = status.contains("BOARDING", ignoreCase = true) ||
                        status.contains("ALL ABOARD", ignoreCase = true)

        // Find next stop
        val nextStop = findNextStop(train, originCode, destinationCode)
        val track = train.stops.find { it.station.code == originCode }?.track

        // Build expanded content
        val expandedText = buildExpandedText(train, progress, nextStop, track, status)

        // Build collapsed content
        val collapsedText = buildCollapsedText(train, nextStop, destinationName)

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_train)
            .setContentTitle("🚂 Train ${train.trainId} → $destinationName")
            .setContentText(collapsedText)
            .setStyle(NotificationCompat.BigTextStyle()
                .bigText(expandedText))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setContentIntent(contentIntent)
            .addAction(R.drawable.ic_stop, "Stop Tracking", stopIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)

        // Add progress bar if available
        progress?.let { (current, total, percent) ->
            if (total > 0) {
                builder.setProgress(100, percent.toInt(), false)
            }
        }

        // Change color if boarding
        if (isBoarding) {
            builder.setColor(0xFFFF6600.toInt()) // Orange for boarding
        }

        return builder.build()
    }

    private fun buildExpandedText(
        train: TrainDetailV2,
        progress: Triple<Int, Int, Float>?,
        nextStop: String?,
        track: String?,
        status: String
    ): String {
        val lines = mutableListOf<String>()

        // Status and track
        lines.add("Status: $status${track?.let { " • Track $it" } ?: ""}")

        // Next stop info
        nextStop?.let {
            val nextStopInfo = findNextStopDetails(train, it)
            val minutesAway = calculateMinutesToStop(nextStopInfo)
            lines.add("Next: $it${minutesAway?.let { min -> " ($min min)" } ?: ""}")
        }

        // Progress info
        progress?.let { (current, total, percent) ->
            val progressBar = createProgressBar(percent)
            lines.add("Progress: $current/$total stops • ${percent.toInt()}%")
            lines.add(progressBar)
        }

        // Delay info is not available in TrainDetailV2
        // Could be added in future if needed

        return lines.joinToString("\n")
    }

    private fun buildCollapsedText(
        train: TrainDetailV2,
        nextStop: String?,
        destination: String
    ): String {
        return nextStop?.let {
            val nextStopInfo = findNextStopDetails(train, it)
            val minutesAway = calculateMinutesToStop(nextStopInfo)
            "$it${minutesAway?.let { min -> " in $min min" } ?: ""}"
        } ?: "En route to $destination"
    }

    private fun calculateJourneyProgress(
        train: TrainDetailV2,
        originCode: String,
        destinationCode: String
    ): Triple<Int, Int, Float>? {
        val stops = train.stops
        val originIndex = stops.indexOfFirst { it.station.code == originCode }
        val destinationIndex = stops.indexOfFirst { it.station.code == destinationCode }

        if (originIndex == -1 || destinationIndex == -1 || originIndex >= destinationIndex) {
            return null
        }

        val journeyStops = stops.subList(originIndex, destinationIndex + 1)
        val completedStops = journeyStops.count { it.hasDepartedStation }
        val totalStops = journeyStops.size

        val percentComplete = if (totalStops > 0) {
            (completedStops.toFloat() / totalStops.toFloat()) * 100f
        } else {
            0f
        }

        return Triple(completedStops, totalStops, percentComplete)
    }

    private fun findNextStop(
        train: TrainDetailV2,
        originCode: String,
        destinationCode: String
    ): String? {
        val stops = train.stops
        val originIndex = stops.indexOfFirst { it.station.code == originCode }
        val destinationIndex = stops.indexOfFirst { it.station.code == destinationCode }

        if (originIndex == -1 || destinationIndex == -1 || originIndex >= destinationIndex) {
            return null
        }

        // Find the next stop that hasn't departed within our journey segment
        for (i in originIndex..destinationIndex) {
            if (!stops[i].hasDepartedStation) {
                return stops[i].station.name
            }
        }

        return null
    }

    private fun findNextStopDetails(train: TrainDetailV2, stopName: String): com.trackrat.android.data.models.StopDetail? {
        return train.stops.find { it.station.name == stopName }
    }

    private fun calculateMinutesToStop(stop: com.trackrat.android.data.models.StopDetail?): Int? {
        stop?.scheduledArrival?.let { arrival ->
            val now = java.time.ZonedDateTime.now(java.time.ZoneId.of("America/New_York"))
            val minutes = java.time.Duration.between(now, arrival).toMinutes()
            return if (minutes > 0) minutes.toInt() else null
        }
        return null
    }

    private fun createProgressBar(percent: Float): String {
        val totalLength = 20
        val filledLength = ((percent / 100f) * totalLength).toInt()
        val filled = "▓".repeat(filledLength.coerceAtLeast(0))
        val empty = "░".repeat((totalLength - filledLength).coerceAtLeast(0))
        return "$filled$empty"
    }

    private fun createContentIntent(): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        return PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun createStopIntent(): PendingIntent {
        val intent = Intent(context, TrainTrackingService::class.java).apply {
            action = TrainTrackingService.ACTION_STOP_TRACKING
        }
        return PendingIntent.getService(
            context,
            1,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}