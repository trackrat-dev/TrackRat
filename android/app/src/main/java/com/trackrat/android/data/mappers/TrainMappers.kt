package com.trackrat.android.data.mappers

import com.trackrat.android.data.models.DepartureV2
import com.trackrat.android.data.models.StatusV2
import com.trackrat.android.data.models.TrainV2
import java.time.ZonedDateTime

/**
 * Utility functions for converting between different train data models
 * This centralizes mapping logic that was previously scattered across ViewModels
 */
object TrainMappers {
    
    /**
     * Convert DepartureV2 from API to TrainV2 for UI compatibility
     * Originally from TrainListViewModel.convertDepartureToTrain()
     */
    fun departureToTrain(departure: DepartureV2, fromStationCode: String): TrainV2 {
        return TrainV2(
            trainId = departure.trainId,
            trainNumber = departure.trainId, // Use trainId as trainNumber
            lineCode = departure.line.code,
            lineName = departure.line.name ?: departure.line.code ?: "Unknown",
            direction = null, // Not available in DepartureV2
            originStationCode = departure.departure.code,
            originStationName = departure.departure.name,
            terminalStationCode = departure.arrival.code,
            terminalStationName = departure.arrival.name,
            destination = departure.destination ?: departure.arrival.name,
            scheduledDeparture = departure.departure.scheduledTime 
                ?: departure.departure.updatedTime 
                ?: departure.departure.actualTime 
                ?: ZonedDateTime.now(),
            scheduledArrival = departure.arrival.scheduledTime,
            status = if (departure.isCancelled) "CANCELLED" else "ON TIME", // Simple status
            statusV2 = departure.departure.actualTime?.let {
                StatusV2(
                    status = if (departure.isCancelled) "CANCELLED" else "ON TIME",
                    enhancedStatus = if (departure.isCancelled) "Cancelled" else "On Time",
                    location = departure.trainPosition?.let { pos ->
                        when {
                            pos.atStationCode != null -> "At ${pos.atStationCode}"
                            pos.betweenStations -> "Between ${pos.lastDepartedStationCode} and ${pos.nextStationCode}"
                            else -> null
                        }
                    },
                    lastUpdate = departure.dataFreshness.lastUpdated.toString()
                )
            },
            progress = departure.progress,
            track = departure.departure.track,
            trackChange = false,
            stops = emptyList(), // No stops data in departure response
            dataSource = departure.dataSource,
            isCancelled = departure.isCancelled,
            isCompleted = false, // Not known from departure
            prediction = null // No prediction data in DepartureV2
        )
    }
    
    /**
     * Get display-friendly status string for a TrainV2
     * Prefers statusV2 when available, falls back to basic status
     */
    fun getDisplayStatus(train: TrainV2): String {
        return train.statusV2?.enhancedStatus ?: train.status
    }
    
    /**
     * Check if a train is in boarding state
     */
    fun isBoarding(train: TrainV2): Boolean {
        val status = train.statusV2?.status ?: train.status
        return status.equals("BOARDING", ignoreCase = true) || 
               status.equals("ALL ABOARD", ignoreCase = true)
    }
}