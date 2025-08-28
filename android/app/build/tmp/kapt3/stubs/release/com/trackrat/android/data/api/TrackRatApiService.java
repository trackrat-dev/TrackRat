package com.trackrat.android.data.api;

import com.trackrat.android.data.models.DeparturesResponse;
import com.trackrat.android.data.models.TrainDetailsResponse;
import retrofit2.http.GET;
import retrofit2.http.Path;
import retrofit2.http.Query;
import java.time.LocalDate;

@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00000\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000b\n\u0002\b\u0002\bf\u0018\u00002\u00020\u0001J.\u0010\u0002\u001a\u00020\u00032\b\b\u0001\u0010\u0004\u001a\u00020\u00052\n\b\u0003\u0010\u0006\u001a\u0004\u0018\u00010\u00052\b\b\u0003\u0010\u0007\u001a\u00020\bH\u00a7@\u00a2\u0006\u0002\u0010\tJ,\u0010\n\u001a\u00020\u000b2\b\b\u0001\u0010\f\u001a\u00020\u00052\b\b\u0001\u0010\r\u001a\u00020\u00052\b\b\u0003\u0010\u000e\u001a\u00020\u000fH\u00a7@\u00a2\u0006\u0002\u0010\u0010\u00a8\u0006\u0011"}, d2 = {"Lcom/trackrat/android/data/api/TrackRatApiService;", "", "getDepartures", "Lcom/trackrat/android/data/models/DeparturesResponse;", "from", "", "to", "limit", "", "(Ljava/lang/String;Ljava/lang/String;ILkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getTrainDetails", "Lcom/trackrat/android/data/models/TrainDetailsResponse;", "trainId", "date", "refresh", "", "(Ljava/lang/String;Ljava/lang/String;ZLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_release"})
public abstract interface TrackRatApiService {
    
    /**
     * Get train departures between stations
     * @param from Departure station code (e.g., "NY", "NP")
     * @param to Optional arrival station code
     * @param limit Maximum number of results (default 50, max 100)
     */
    @retrofit2.http.GET(value = "trains/departures")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getDepartures(@retrofit2.http.Query(value = "from")
    @org.jetbrains.annotations.NotNull()
    java.lang.String from, @retrofit2.http.Query(value = "to")
    @org.jetbrains.annotations.Nullable()
    java.lang.String to, @retrofit2.http.Query(value = "limit")
    int limit, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.DeparturesResponse> $completion);
    
    /**
     * Get detailed information about a specific train
     * @param trainId Train ID (can be numeric or alphanumeric like "A174")
     * @param date Journey date in YYYY-MM-DD format
     * @param refresh Force refresh from API if true
     */
    @retrofit2.http.GET(value = "trains/{trainId}")
    @org.jetbrains.annotations.Nullable()
    public abstract java.lang.Object getTrainDetails(@retrofit2.http.Path(value = "trainId")
    @org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @retrofit2.http.Query(value = "date")
    @org.jetbrains.annotations.NotNull()
    java.lang.String date, @retrofit2.http.Query(value = "refresh")
    boolean refresh, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.TrainDetailsResponse> $completion);
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 3, xi = 48)
    public static final class DefaultImpls {
    }
}