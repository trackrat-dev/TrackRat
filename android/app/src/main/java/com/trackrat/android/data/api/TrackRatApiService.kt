package com.trackrat.android.data.api

import com.trackrat.android.data.models.DeparturesResponse
import com.trackrat.android.data.models.TrainDetailsResponse
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query
import java.time.LocalDate

interface TrackRatApiService {

    /**
     * Get train departures between stations
     * @param from Departure station code (e.g., "NY", "NP")
     * @param to Optional arrival station code
     * @param limit Maximum number of results (default 50, max 100)
     */
    @GET("trains/departures")
    suspend fun getDepartures(
        @Query("from") from: String,
        @Query("to") to: String? = null,
        @Query("limit") limit: Int = 50
    ): DeparturesResponse

    /**
     * Get detailed information about a specific train
     * @param trainId Train ID (can be numeric or alphanumeric like "A174")
     * @param date Journey date in YYYY-MM-DD format
     * @param refresh Force refresh from API if true
     */
    @GET("trains/{trainId}")
    suspend fun getTrainDetails(
        @Path("trainId") trainId: String,
        @Query("date") date: String,
        @Query("refresh") refresh: Boolean = false
    ): TrainDetailsResponse

    /**
     * Health check endpoint
     * Returns backend server status
     */
    @GET("../health")  // Go up one level from /api/v2 to /health
    suspend fun getHealth(): Map<String, String>
}