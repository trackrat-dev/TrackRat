package com.trackrat.android.ui.traindetail;

import android.app.Application;
import androidx.lifecycle.AndroidViewModel;
import com.trackrat.android.data.models.ApiException;
import com.trackrat.android.data.models.ApiResult;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.data.repository.TrackRatRepository;
import com.trackrat.android.services.TrainTrackingService;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import kotlinx.coroutines.flow.SharingStarted;
import java.time.LocalDate;
import javax.inject.Inject;

/**
 * ViewModel for the train detail screen with robust error handling
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000L\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u000b\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\n\b\u0007\u0018\u0000 %2\u00020\u0001:\u0002%&B\u0017\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u00a2\u0006\u0002\u0010\u0006J\u001e\u0010\u0015\u001a\u00020\u00162\u0006\u0010\u0017\u001a\u00020\r2\u0006\u0010\u0018\u001a\u00020\rH\u0082@\u00a2\u0006\u0002\u0010\u0019J\b\u0010\u001a\u001a\u00020\rH\u0002J\u000e\u0010\u001b\u001a\u00020\r2\u0006\u0010\u001c\u001a\u00020\u001dJ\u000e\u0010\u001e\u001a\u00020\u00112\u0006\u0010\u001c\u001a\u00020\u001dJ\u001a\u0010\u001f\u001a\u00020\u00162\u0006\u0010\u0017\u001a\u00020\r2\n\b\u0002\u0010\u0018\u001a\u0004\u0018\u00010\rJ\b\u0010 \u001a\u00020\u0016H\u0014J\u0006\u0010!\u001a\u00020\u0016J\u0006\u0010\"\u001a\u00020\u0016J\u0018\u0010#\u001a\u00020\u00162\u0006\u0010\u0017\u001a\u00020\r2\u0006\u0010\u0018\u001a\u00020\rH\u0002J\u0006\u0010$\u001a\u00020\u0016R\u0014\u0010\u0007\u001a\b\u0012\u0004\u0012\u00020\t0\bX\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0010\u0010\n\u001a\u0004\u0018\u00010\u000bX\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u0010\u0010\f\u001a\u0004\u0018\u00010\rX\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u0010\u0010\u000e\u001a\u0004\u0018\u00010\rX\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u0017\u0010\u000f\u001a\b\u0012\u0004\u0012\u00020\u00110\u0010\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0012R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0017\u0010\u0013\u001a\b\u0012\u0004\u0012\u00020\t0\u0010\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0012\u00a8\u0006\'"}, d2 = {"Lcom/trackrat/android/ui/traindetail/TrainDetailViewModel;", "Landroidx/lifecycle/AndroidViewModel;", "application", "Landroid/app/Application;", "repository", "Lcom/trackrat/android/data/repository/TrackRatRepository;", "(Landroid/app/Application;Lcom/trackrat/android/data/repository/TrackRatRepository;)V", "_uiState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/trackrat/android/ui/traindetail/TrainDetailViewModel$UiState;", "autoRefreshJob", "Lkotlinx/coroutines/Job;", "currentDate", "", "currentTrainId", "isTrackingTrain", "Lkotlinx/coroutines/flow/StateFlow;", "", "()Lkotlinx/coroutines/flow/StateFlow;", "uiState", "getUiState", "fetchTrainDetails", "", "trainId", "date", "(Ljava/lang/String;Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getCurrentDateString", "getTrainDisplayStatus", "train", "Lcom/trackrat/android/data/models/TrainV2;", "isTrainBoarding", "loadTrainDetails", "onCleared", "refresh", "retry", "startAutoRefresh", "toggleTracking", "Companion", "UiState", "app_release"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class TrainDetailViewModel extends androidx.lifecycle.AndroidViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.repository.TrackRatRepository repository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.trackrat.android.ui.traindetail.TrainDetailViewModel.UiState> _uiState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.ui.traindetail.TrainDetailViewModel.UiState> uiState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<java.lang.Boolean> isTrackingTrain = null;
    @org.jetbrains.annotations.Nullable()
    private kotlinx.coroutines.Job autoRefreshJob;
    @org.jetbrains.annotations.Nullable()
    private java.lang.String currentTrainId;
    @org.jetbrains.annotations.Nullable()
    private java.lang.String currentDate;
    private static final long AUTO_REFRESH_INTERVAL_MS = 30000L;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.ui.traindetail.TrainDetailViewModel.Companion Companion = null;
    
    @javax.inject.Inject()
    public TrainDetailViewModel(@org.jetbrains.annotations.NotNull()
    android.app.Application application, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.repository.TrackRatRepository repository) {
        super(null);
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.ui.traindetail.TrainDetailViewModel.UiState> getUiState() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<java.lang.Boolean> isTrackingTrain() {
        return null;
    }
    
    /**
     * Load train details with improved error handling
     */
    public final void loadTrainDetails(@org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @org.jetbrains.annotations.Nullable()
    java.lang.String date) {
    }
    
    /**
     * Manual refresh
     */
    public final void refresh() {
    }
    
    /**
     * Retry failed request
     */
    public final void retry() {
    }
    
    /**
     * Fetch train details from API with structured error handling
     */
    private final java.lang.Object fetchTrainDetails(java.lang.String trainId, java.lang.String date, kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Start lifecycle-aware auto-refresh timer
     */
    private final void startAutoRefresh(java.lang.String trainId, java.lang.String date) {
    }
    
    /**
     * Get current date as string in API format
     */
    private final java.lang.String getCurrentDateString() {
        return null;
    }
    
    /**
     * Toggle train tracking on/off
     */
    public final void toggleTracking() {
    }
    
    /**
     * Stop auto-refresh when ViewModel is cleared
     */
    @java.lang.Override()
    protected void onCleared() {
    }
    
    /**
     * Get display status for the train (uses statusV2 if available)
     */
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getTrainDisplayStatus(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.TrainV2 train) {
        return null;
    }
    
    /**
     * Check if a train is boarding
     */
    public final boolean isTrainBoarding(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.TrainV2 train) {
        return false;
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0012\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\t\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0082T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\u0005"}, d2 = {"Lcom/trackrat/android/ui/traindetail/TrainDetailViewModel$Companion;", "", "()V", "AUTO_REFRESH_INTERVAL_MS", "", "app_release"})
    public static final class Companion {
        
        private Companion() {
            super();
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00002\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\t\n\u0002\b\u0014\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0086\b\u0018\u00002\u00020\u0001BE\u0012\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0002\u0010\u0004\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u0006\u001a\u00020\u0005\u0012\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\b\u0012\b\b\u0002\u0010\t\u001a\u00020\n\u0012\b\b\u0002\u0010\u000b\u001a\u00020\u0005\u00a2\u0006\u0002\u0010\fJ\u000b\u0010\u0015\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010\u0016\u001a\u00020\u0005H\u00c6\u0003J\t\u0010\u0017\u001a\u00020\u0005H\u00c6\u0003J\u000b\u0010\u0018\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\t\u0010\u0019\u001a\u00020\nH\u00c6\u0003J\t\u0010\u001a\u001a\u00020\u0005H\u00c6\u0003JI\u0010\u001b\u001a\u00020\u00002\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00052\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\b2\b\b\u0002\u0010\t\u001a\u00020\n2\b\b\u0002\u0010\u000b\u001a\u00020\u0005H\u00c6\u0001J\u0013\u0010\u001c\u001a\u00020\u00052\b\u0010\u001d\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010\u001e\u001a\u00020\u001fH\u00d6\u0001J\t\u0010 \u001a\u00020!H\u00d6\u0001R\u0011\u0010\u000b\u001a\u00020\u0005\u00a2\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u0013\u0010\u0007\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u0011\u0010\u0004\u001a\u00020\u0005\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0004\u0010\u000eR\u0011\u0010\u0006\u001a\u00020\u0005\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0006\u0010\u000eR\u0011\u0010\t\u001a\u00020\n\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u0012R\u0013\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0013\u0010\u0014\u00a8\u0006\""}, d2 = {"Lcom/trackrat/android/ui/traindetail/TrainDetailViewModel$UiState;", "", "train", "Lcom/trackrat/android/data/models/TrainV2;", "isLoading", "", "isRefreshing", "error", "Lcom/trackrat/android/data/models/ApiException;", "lastUpdated", "", "canRetry", "(Lcom/trackrat/android/data/models/TrainV2;ZZLcom/trackrat/android/data/models/ApiException;JZ)V", "getCanRetry", "()Z", "getError", "()Lcom/trackrat/android/data/models/ApiException;", "getLastUpdated", "()J", "getTrain", "()Lcom/trackrat/android/data/models/TrainV2;", "component1", "component2", "component3", "component4", "component5", "component6", "copy", "equals", "other", "hashCode", "", "toString", "", "app_release"})
    public static final class UiState {
        @org.jetbrains.annotations.Nullable()
        private final com.trackrat.android.data.models.TrainV2 train = null;
        private final boolean isLoading = false;
        private final boolean isRefreshing = false;
        @org.jetbrains.annotations.Nullable()
        private final com.trackrat.android.data.models.ApiException error = null;
        private final long lastUpdated = 0L;
        private final boolean canRetry = false;
        
        public UiState(@org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.TrainV2 train, boolean isLoading, boolean isRefreshing, @org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.ApiException error, long lastUpdated, boolean canRetry) {
            super();
        }
        
        @org.jetbrains.annotations.Nullable()
        public final com.trackrat.android.data.models.TrainV2 getTrain() {
            return null;
        }
        
        public final boolean isLoading() {
            return false;
        }
        
        public final boolean isRefreshing() {
            return false;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final com.trackrat.android.data.models.ApiException getError() {
            return null;
        }
        
        public final long getLastUpdated() {
            return 0L;
        }
        
        public final boolean getCanRetry() {
            return false;
        }
        
        public UiState() {
            super();
        }
        
        @org.jetbrains.annotations.Nullable()
        public final com.trackrat.android.data.models.TrainV2 component1() {
            return null;
        }
        
        public final boolean component2() {
            return false;
        }
        
        public final boolean component3() {
            return false;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final com.trackrat.android.data.models.ApiException component4() {
            return null;
        }
        
        public final long component5() {
            return 0L;
        }
        
        public final boolean component6() {
            return false;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.ui.traindetail.TrainDetailViewModel.UiState copy(@org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.TrainV2 train, boolean isLoading, boolean isRefreshing, @org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.ApiException error, long lastUpdated, boolean canRetry) {
            return null;
        }
        
        @java.lang.Override()
        public boolean equals(@org.jetbrains.annotations.Nullable()
        java.lang.Object other) {
            return false;
        }
        
        @java.lang.Override()
        public int hashCode() {
            return 0;
        }
        
        @java.lang.Override()
        @org.jetbrains.annotations.NotNull()
        public java.lang.String toString() {
            return null;
        }
    }
}