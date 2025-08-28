package com.trackrat.android.services

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.trackrat.android.MainActivity
import com.trackrat.android.R
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.repository.TrackRatRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject

/**
 * Foreground service for tracking a train journey in real-time.
 * Updates every 30 seconds with latest train information.
 */
@AndroidEntryPoint
class TrainTrackingService : Service() {

    @Inject
    lateinit var repository: TrackRatRepository

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var updateJob: Job? = null
    
    private var currentTrainId: String? = null
    private var currentDate: String? = null

    companion object {
        const val CHANNEL_ID = "train_tracking_channel"
        const val NOTIFICATION_ID = 1001
        const val ACTION_START = "com.trackrat.android.action.START_TRACKING"
        const val ACTION_STOP = "com.trackrat.android.action.STOP_TRACKING"
        const val EXTRA_TRAIN_ID = "train_id"
        const val EXTRA_DATE = "date"
        const val EXTRA_FROM_STATION = "from_station"
        
        // Update interval - 30 seconds
        const val UPDATE_INTERVAL_MS = 30_000L

        // Static tracking state
        private val _isTracking = MutableStateFlow<String?>(null)
        val isTracking: StateFlow<String?> = _isTracking

        /**
         * Start tracking a train
         */
        fun startTracking(context: Context, trainId: String, date: String, fromStation: String? = null) {
            val intent = Intent(context, TrainTrackingService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_TRAIN_ID, trainId)
                putExtra(EXTRA_DATE, date)
                putExtra(EXTRA_FROM_STATION, fromStation)
            }
            context.startForegroundService(intent)
        }

        /**
         * Stop tracking the current train
         */
        fun stopTracking(context: Context) {
            val intent = Intent(context, TrainTrackingService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }

        /**
         * Check if a specific train is being tracked
         */
        fun isTrackingTrain(trainId: String): Boolean = _isTracking.value == trainId
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val trainId = intent.getStringExtra(EXTRA_TRAIN_ID)
                val date = intent.getStringExtra(EXTRA_DATE)
                
                if (trainId != null && date != null) {
                    startTracking(trainId, date)
                }
            }
            ACTION_STOP -> {
                stopTracking()
            }
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        updateJob?.cancel()
        serviceScope.cancel()
        _isTracking.value = null
        super.onDestroy()
    }

    private fun startTracking(trainId: String, date: String) {
        currentTrainId = trainId
        currentDate = date
        _isTracking.value = trainId

        // Start with a basic notification
        val notification = createNotification(
            title = "Loading train $trainId...",
            content = "Fetching journey information"
        )
        startForeground(NOTIFICATION_ID, notification)

        // Start the update loop
        updateJob?.cancel()
        updateJob = serviceScope.launch {
            while (isActive) {
                updateTrainStatus()
                delay(UPDATE_INTERVAL_MS)
            }
        }
    }

    private fun stopTracking() {
        updateJob?.cancel()
        _isTracking.value = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private suspend fun updateTrainStatus() {
        val trainId = currentTrainId ?: return
        val date = currentDate ?: return

        try {
            when (val result = repository.getTrainDetails(trainId, date, refresh = true)) {
                is com.trackrat.android.data.models.ApiResult.Success -> {
                    result.data.train?.let { train ->
                        updateNotification(train)
                    }
                }
                is com.trackrat.android.data.models.ApiResult.Error -> {
                    // Keep the last known good notification on error
                    result.exception.printStackTrace()
                }
                is com.trackrat.android.data.models.ApiResult.Loading -> {
                    // Ignore loading state in background updates
                }
            }
        } catch (e: Exception) {
            // Keep the last known good notification on error
            // This ensures the service doesn't crash on network issues
            e.printStackTrace()
        }
    }

    private fun updateNotification(train: TrainV2) {
        val title = buildString {
            append("Train ${train.trainNumber ?: train.trainId}")
            train.track?.let { append(" • Track $it") }
        }

        val content = buildString {
            // Use StatusV2 if available, fallback to regular status
            val status = train.statusV2?.enhancedStatus ?: train.status
            append(status)
            
            // Add progress information if available
            train.progress?.let { progress ->
                if (progress.stopsCompleted > 0) {
                    append(" • ${progress.stopsCompleted}/${progress.stopsTotal} stops")
                }
                progress.nextArrival?.minutesToArrival?.let { minutes ->
                    if (minutes > 0) {
                        append(" • Next in ${minutes}m")
                    }
                }
            }
        }

        val updatedNotification = createNotification(
            title = title,
            content = content,
            subText = "${train.originStationName} → ${train.terminalStationName}"
        )

        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, updatedNotification)
    }

    private fun createNotification(
        title: String,
        content: String,
        subText: String? = null
    ): android.app.Notification {
        // Intent to open the app when notification is tapped
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            currentTrainId?.let { putExtra(EXTRA_TRAIN_ID, it) }
        }
        
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Stop action
        val stopIntent = Intent(this, TrainTrackingService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(content)
            .setSubText(subText)
            .setSmallIcon(android.R.drawable.ic_menu_directions) // Use a train icon in production
            .setContentIntent(pendingIntent)
            .setOngoing(true) // Cannot be dismissed
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Stop Tracking",
                stopPendingIntent
            )
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Train Tracking",
                NotificationManager.IMPORTANCE_LOW // Low importance to avoid sound/vibration
            ).apply {
                description = "Real-time train journey tracking"
                setShowBadge(false)
            }

            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }
}