package com.trackrat.android.data.repository;

import com.trackrat.android.data.api.TrackRatApiService;
import com.trackrat.android.data.models.ApiResult;
import com.trackrat.android.data.models.DeparturesResponse;
import com.trackrat.android.data.models.TrainDetailsResponse;
import com.trackrat.android.data.models.TrainV2;
import kotlinx.coroutines.flow.Flow;
import javax.inject.Inject;
import javax.inject.Singleton;

/**
 * Repository for accessing train data from the TrackRat API
 * Uses ApiResult for robust error handling and recovery
 */
@javax.inject.Singleton()
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000Z\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\b\u0007\u0018\u0000 \"2\u00020\u0001:\u0001\"B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J8\u0010\u0005\u001a\b\u0012\u0004\u0012\u0002H\u00070\u0006\"\u0004\b\u0000\u0010\u00072\u001c\u0010\b\u001a\u0018\b\u0001\u0012\n\u0012\b\u0012\u0004\u0012\u0002H\u00070\n\u0012\u0006\u0012\u0004\u0018\u00010\u00010\tH\u0082@\u00a2\u0006\u0002\u0010\u000bJ2\u0010\f\u001a\b\u0012\u0004\u0012\u00020\r0\u00062\u0006\u0010\u000e\u001a\u00020\u000f2\n\b\u0002\u0010\u0010\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u0012H\u0086@\u00a2\u0006\u0002\u0010\u0013J0\u0010\u0014\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\r0\u00060\u00152\u0006\u0010\u000e\u001a\u00020\u000f2\n\b\u0002\u0010\u0010\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u0012J.\u0010\u0016\u001a\b\u0012\u0004\u0012\u00020\u00170\u00062\u0006\u0010\u0018\u001a\u00020\u000f2\u0006\u0010\u0019\u001a\u00020\u000f2\b\b\u0002\u0010\u001a\u001a\u00020\u001bH\u0086@\u00a2\u0006\u0002\u0010\u001cJ(\u0010\u001d\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u001e0\u00062\u0006\u0010\u001f\u001a\u00020\u000f2\b\b\u0002\u0010 \u001a\u00020\u000fH\u0086@\u00a2\u0006\u0002\u0010!R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000\u00a8\u0006#"}, d2 = {"Lcom/trackrat/android/data/repository/TrackRatRepository;", "", "apiService", "Lcom/trackrat/android/data/api/TrackRatApiService;", "(Lcom/trackrat/android/data/api/TrackRatApiService;)V", "executeWithRetry", "Lcom/trackrat/android/data/models/ApiResult;", "T", "action", "Lkotlin/Function1;", "Lkotlin/coroutines/Continuation;", "(Lkotlin/jvm/functions/Function1;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getDepartures", "Lcom/trackrat/android/data/models/DeparturesResponse;", "from", "", "to", "limit", "", "(Ljava/lang/String;Ljava/lang/String;ILkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getDeparturesFlow", "Lkotlinx/coroutines/flow/Flow;", "getTrainDetails", "Lcom/trackrat/android/data/models/TrainDetailsResponse;", "trainId", "date", "refresh", "", "(Ljava/lang/String;Ljava/lang/String;ZLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "searchByTrainNumber", "Lcom/trackrat/android/data/models/TrainV2;", "trainNumber", "fromStation", "(Ljava/lang/String;Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "Companion", "app_debug"})
public final class TrackRatRepository {
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.api.TrackRatApiService apiService = null;
    private static final int MAX_RETRIES = 3;
    private static final long INITIAL_RETRY_DELAY = 1000L;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.data.repository.TrackRatRepository.Companion Companion = null;
    
    @javax.inject.Inject()
    public TrackRatRepository(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.api.TrackRatApiService apiService) {
        super();
    }
    
    /**
     * Get departures between stations with error handling and retry logic
     * @param from Origin station code (e.g., "NY", "NP")
     * @param to Optional destination station code
     * @param limit Maximum number of results
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getDepartures(@org.jetbrains.annotations.NotNull()
    java.lang.String from, @org.jetbrains.annotations.Nullable()
    java.lang.String to, int limit, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.ApiResult<com.trackrat.android.data.models.DeparturesResponse>> $completion) {
        return null;
    }
    
    /**
     * Get train details with error handling and retry logic
     * @param trainId Train ID (can be numeric or alphanumeric)
     * @param date Journey date in YYYY-MM-DD format
     * @param refresh Force refresh from API
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object getTrainDetails(@org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @org.jetbrains.annotations.NotNull()
    java.lang.String date, boolean refresh, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.ApiResult<com.trackrat.android.data.models.TrainDetailsResponse>> $completion) {
        return null;
    }
    
    /**
     * Get departures as Flow for reactive UI updates
     */
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.Flow<com.trackrat.android.data.models.ApiResult<com.trackrat.android.data.models.DeparturesResponse>> getDeparturesFlow(@org.jetbrains.annotations.NotNull()
    java.lang.String from, @org.jetbrains.annotations.Nullable()
    java.lang.String to, int limit) {
        return null;
    }
    
    /**
     * Search for trains by train number with improved efficiency
     * Uses targeted search instead of loading all departures
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object searchByTrainNumber(@org.jetbrains.annotations.NotNull()
    java.lang.String trainNumber, @org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.ApiResult<com.trackrat.android.data.models.TrainV2>> $completion) {
        return null;
    }
    
    /**
     * Execute API call with exponential backoff retry logic
     */
    private final <T extends java.lang.Object>java.lang.Object executeWithRetry(kotlin.jvm.functions.Function1<? super kotlin.coroutines.Continuation<? super T>, ? extends java.lang.Object> action, kotlin.coroutines.Continuation<? super com.trackrat.android.data.models.ApiResult<? extends T>> $completion) {
        return null;
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0018\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\t\n\u0000\n\u0002\u0010\b\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0082T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0006X\u0082T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\u0007"}, d2 = {"Lcom/trackrat/android/data/repository/TrackRatRepository$Companion;", "", "()V", "INITIAL_RETRY_DELAY", "", "MAX_RETRIES", "", "app_debug"})
    public static final class Companion {
        
        private Companion() {
            super();
        }
    }
}