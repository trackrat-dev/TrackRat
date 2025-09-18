package com.trackrat.android.services

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class TrainUpdateReceiver : BroadcastReceiver() {

    @Inject
    lateinit var trackingStateRepository: TrackingStateRepository

    private val receiverScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onReceive(context: Context, intent: Intent) {
        // Check if we're still tracking
        receiverScope.launch {
            val trackingState = trackingStateRepository.getTrackingState()

            if (trackingState != null && !trackingStateRepository.isStale()) {
                // Trigger service to update
                val serviceIntent = Intent(context, TrainTrackingService::class.java).apply {
                    putExtra("UPDATE_REQUEST", true)
                }
                context.startService(serviceIntent)
            }
        }
    }
}