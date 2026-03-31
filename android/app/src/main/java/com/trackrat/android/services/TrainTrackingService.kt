package com.trackrat.android.services

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.trackrat.android.MainActivity
import com.trackrat.android.R
import com.trackrat.android.data.models.TrainDetailV2
import com.trackrat.android.data.repository.TrackRatRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import javax.inject.Inject

@AndroidEntryPoint
class TrainTrackingService : Service() {

    @Inject lateinit var repository: TrackRatRepository
    @Inject lateinit var trackingStateRepository: TrackingStateRepository
    @Inject lateinit var notificationManager: TrainTrackingNotificationManager

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var updateJob: Job? = null

    companion object {
        const val NOTIFICATION_ID = 1001
        const val UPDATE_INTERVAL_MS = 30_000L // 30 seconds
        const val ACTION_STOP_TRACKING = "com.trackrat.android.STOP_TRACKING"

        private const val EXTRA_TRAIN_ID = "train_id"
        private const val EXTRA_ORIGIN_CODE = "origin_code"
        private const val EXTRA_DESTINATION_CODE = "destination_code"
        private const val EXTRA_ORIGIN_NAME = "origin_name"
        private const val EXTRA_DESTINATION_NAME = "destination_name"

        fun startTracking(
            context: Context,
            trainId: String,
            originCode: String,
            destinationCode: String,
            originName: String,
            destinationName: String
        ) {
            val intent = Intent(context, TrainTrackingService::class.java).apply {
                putExtra(EXTRA_TRAIN_ID, trainId)
                putExtra(EXTRA_ORIGIN_CODE, originCode)
                putExtra(EXTRA_DESTINATION_CODE, destinationCode)
                putExtra(EXTRA_ORIGIN_NAME, originName)
                putExtra(EXTRA_DESTINATION_NAME, destinationName)
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stopTracking(context: Context) {
            val intent = Intent(context, TrainTrackingService::class.java).apply {
                action = ACTION_STOP_TRACKING
            }
            context.startService(intent)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        notificationManager.createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP_TRACKING -> {
                stopTracking()
                return START_NOT_STICKY
            }
        }

        val trainId = intent?.getStringExtra(EXTRA_TRAIN_ID) ?: run {
            stopSelf()
            return START_NOT_STICKY
        }

        val originCode = intent.getStringExtra(EXTRA_ORIGIN_CODE) ?: run {
            stopSelf()
            return START_NOT_STICKY
        }

        val destinationCode = intent.getStringExtra(EXTRA_DESTINATION_CODE) ?: run {
            stopSelf()
            return START_NOT_STICKY
        }

        val originName = intent.getStringExtra(EXTRA_ORIGIN_NAME) ?: ""
        val destinationName = intent.getStringExtra(EXTRA_DESTINATION_NAME) ?: ""

        // Start in foreground immediately with initial notification
        val initialNotification = notificationManager.buildInitialNotification(
            trainId = trainId,
            origin = originName,
            destination = destinationName
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, initialNotification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, initialNotification)
        }

        // Save tracking state
        serviceScope.launch {
            trackingStateRepository.setTracking(
                trainId = trainId,
                originCode = originCode,
                destinationCode = destinationCode,
                originName = originName,
                destinationName = destinationName
            )
        }

        // Start periodic updates
        startPeriodicUpdates(trainId, originCode, destinationCode)

        return START_STICKY
    }

    private fun startPeriodicUpdates(trainId: String, originCode: String, destinationCode: String) {
        updateJob?.cancel()
        updateJob = serviceScope.launch {
            while (isActive) {
                updateTrainStatus(trainId, originCode, destinationCode)

                // Schedule next update using AlarmManager for battery efficiency
                scheduleNextUpdate()
                delay(UPDATE_INTERVAL_MS)
            }
        }
    }

    private suspend fun updateTrainStatus(trainId: String, originCode: String, destinationCode: String) {
        try {
            // Fetch train details with current date
            val currentDate = java.time.LocalDate.now().toString()
            when (val result = repository.getTrainDetails(trainId, date = currentDate, refresh = true)) {
                is com.trackrat.android.data.models.ApiResult.Success -> {
                    val train = result.data.train

                    // Check if journey is complete or should stop
                    if (shouldStopTracking(train, destinationCode)) {
                        withContext(Dispatchers.Main) {
                            stopTracking()
                        }
                        return
                    }

                    // Update notification with new train data
                    val notification = notificationManager.buildTrackingNotification(
                        train = train,
                        originCode = originCode,
                        destinationCode = destinationCode
                    )

                    val androidNotificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    androidNotificationManager.notify(NOTIFICATION_ID, notification)

                    // Update state
                    trackingStateRepository.updateLastTrainData(train)
                }
                is com.trackrat.android.data.models.ApiResult.Error -> {
                    println("Error fetching train details: ${result.exception.message}")
                }
                is com.trackrat.android.data.models.ApiResult.Loading -> {
                    // Shouldn't happen
                }
            }
        } catch (e: Exception) {
            println("Error updating train status: ${e.message}")
        }
    }

    private fun shouldStopTracking(train: TrainDetailV2, destinationCode: String): Boolean {
        // Check if train has arrived at destination
        val destinationStop = train.stops.find { it.station.code == destinationCode }
        if (destinationStop != null && destinationStop.hasDepartedStation) {
            return true // Journey complete
        }

        // Check if train status indicates completion
        val status = train.rawTrainState ?: ""
        if (status.contains("ARRIVED", ignoreCase = true) &&
            status.contains(destinationCode, ignoreCase = true)) {
            return true
        }

        // TrainDetailV2 doesn't have progress field
        // Check if all stops have been completed for journey
        val originIndex = train.stops.indexOfFirst { !it.hasDepartedStation }
        val destIndex = train.stops.indexOfLast { it.station.code == destinationCode }
        if (originIndex == -1 || originIndex > destIndex) {
            return true // All stops completed or past destination
        }

        return false
    }

    private fun scheduleNextUpdate() {
        // Using AlarmManager for battery-efficient scheduling
        val alarmManager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val updateIntent = Intent(this, TrainUpdateReceiver::class.java)
        val pendingIntent = PendingIntent.getBroadcast(
            this,
            0,
            updateIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val triggerTime = SystemClock.elapsedRealtime() + UPDATE_INTERVAL_MS

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                triggerTime,
                pendingIntent
            )
        } else {
            alarmManager.setExact(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                triggerTime,
                pendingIntent
            )
        }
    }

    private fun stopTracking() {
        // Cancel updates
        updateJob?.cancel()

        // Clear tracking state
        serviceScope.launch {
            trackingStateRepository.clearTracking()
        }

        // Stop service
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
    }
}