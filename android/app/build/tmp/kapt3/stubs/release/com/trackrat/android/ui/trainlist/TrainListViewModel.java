package com.trackrat.android.ui.trainlist;

import androidx.lifecycle.ViewModel;
import com.trackrat.android.data.models.ApiException;
import com.trackrat.android.data.models.ApiResult;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.data.preferences.UserPreferencesRepository;
import com.trackrat.android.data.repository.TrackRatRepository;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

/**
 * ViewModel for the train list screen with robust error handling
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000L\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\b\b\u0007\u0018\u0000  2\u00020\u0001:\u0002 !B\u0017\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u00a2\u0006\u0002\u0010\u0006J \u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00132\b\u0010\u0014\u001a\u0004\u0018\u00010\u0013H\u0082@\u00a2\u0006\u0002\u0010\u0015J\u000e\u0010\u0016\u001a\u00020\u00132\u0006\u0010\u0017\u001a\u00020\u0018J\u000e\u0010\u0019\u001a\u00020\u001a2\u0006\u0010\u0017\u001a\u00020\u0018J\u0018\u0010\u001b\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00132\b\u0010\u0014\u001a\u0004\u0018\u00010\u0013J\b\u0010\u001c\u001a\u00020\u0011H\u0014J\u0006\u0010\u001d\u001a\u00020\u0011J\u0006\u0010\u001e\u001a\u00020\u0011J\u001a\u0010\u001f\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00132\b\u0010\u0014\u001a\u0004\u0018\u00010\u0013H\u0002R\u0014\u0010\u0007\u001a\b\u0012\u0004\u0012\u00020\t0\bX\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0010\u0010\n\u001a\u0004\u0018\u00010\u000bX\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0017\u0010\f\u001a\b\u0012\u0004\u0012\u00020\t0\r\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000f\u00a8\u0006\""}, d2 = {"Lcom/trackrat/android/ui/trainlist/TrainListViewModel;", "Landroidx/lifecycle/ViewModel;", "repository", "Lcom/trackrat/android/data/repository/TrackRatRepository;", "preferencesRepository", "Lcom/trackrat/android/data/preferences/UserPreferencesRepository;", "(Lcom/trackrat/android/data/repository/TrackRatRepository;Lcom/trackrat/android/data/preferences/UserPreferencesRepository;)V", "_uiState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/trackrat/android/ui/trainlist/TrainListViewModel$UiState;", "autoRefreshJob", "Lkotlinx/coroutines/Job;", "uiState", "Lkotlinx/coroutines/flow/StateFlow;", "getUiState", "()Lkotlinx/coroutines/flow/StateFlow;", "fetchTrains", "", "fromStation", "", "toStation", "(Ljava/lang/String;Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "getTrainDisplayStatus", "train", "Lcom/trackrat/android/data/models/TrainV2;", "isTrainBoarding", "", "loadTrains", "onCleared", "refresh", "retry", "startAutoRefresh", "Companion", "UiState", "app_release"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class TrainListViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.repository.TrackRatRepository repository = null;
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.preferences.UserPreferencesRepository preferencesRepository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.trackrat.android.ui.trainlist.TrainListViewModel.UiState> _uiState = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.ui.trainlist.TrainListViewModel.UiState> uiState = null;
    @org.jetbrains.annotations.Nullable()
    private kotlinx.coroutines.Job autoRefreshJob;
    private static final long AUTO_REFRESH_INTERVAL_MS = 30000L;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.ui.trainlist.TrainListViewModel.Companion Companion = null;
    
    @javax.inject.Inject()
    public TrainListViewModel(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.repository.TrackRatRepository repository, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.preferences.UserPreferencesRepository preferencesRepository) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.ui.trainlist.TrainListViewModel.UiState> getUiState() {
        return null;
    }
    
    /**
     * Load trains between stations with improved error handling
     */
    public final void loadTrains(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.Nullable()
    java.lang.String toStation) {
    }
    
    /**
     * Manual refresh (pull-to-refresh)
     */
    public final void refresh() {
    }
    
    /**
     * Retry failed request
     */
    public final void retry() {
    }
    
    /**
     * Fetch trains from API with structured error handling
     */
    private final java.lang.Object fetchTrains(java.lang.String fromStation, java.lang.String toStation, kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Start lifecycle-aware auto-refresh timer
     */
    private final void startAutoRefresh(java.lang.String fromStation, java.lang.String toStation) {
    }
    
    /**
     * Stop auto-refresh when ViewModel is cleared
     */
    @java.lang.Override()
    protected void onCleared() {
    }
    
    /**
     * Get display status for a train (uses statusV2 if available)
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
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u0012\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\t\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0082T\u00a2\u0006\u0002\n\u0000\u00a8\u0006\u0005"}, d2 = {"Lcom/trackrat/android/ui/trainlist/TrainListViewModel$Companion;", "", "()V", "AUTO_REFRESH_INTERVAL_MS", "", "app_release"})
    public static final class Companion {
        
        private Companion() {
            super();
        }
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000:\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\t\n\u0002\b#\n\u0002\u0010\b\n\u0002\b\u0002\b\u0086\b\u0018\u00002\u00020\u0001B\u008d\u0001\u0012\u000e\b\u0002\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003\u0012\b\b\u0002\u0010\u0005\u001a\u00020\u0006\u0012\b\b\u0002\u0010\u0007\u001a\u00020\u0006\u0012\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\t\u0012\n\b\u0002\u0010\n\u001a\u0004\u0018\u00010\u000b\u0012\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\u000b\u0012\n\b\u0002\u0010\r\u001a\u0004\u0018\u00010\u000b\u0012\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000b\u0012\b\b\u0002\u0010\u000f\u001a\u00020\u0010\u0012\b\b\u0002\u0010\u0011\u001a\u00020\u0006\u0012\b\b\u0002\u0010\u0012\u001a\u00020\u0006\u0012\b\b\u0002\u0010\u0013\u001a\u00020\u0006\u00a2\u0006\u0002\u0010\u0014J\u000f\u0010$\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003H\u00c6\u0003J\t\u0010%\u001a\u00020\u0006H\u00c6\u0003J\t\u0010&\u001a\u00020\u0006H\u00c6\u0003J\t\u0010\'\u001a\u00020\u0006H\u00c6\u0003J\t\u0010(\u001a\u00020\u0006H\u00c6\u0003J\t\u0010)\u001a\u00020\u0006H\u00c6\u0003J\u000b\u0010*\u001a\u0004\u0018\u00010\tH\u00c6\u0003J\u000b\u0010+\u001a\u0004\u0018\u00010\u000bH\u00c6\u0003J\u000b\u0010,\u001a\u0004\u0018\u00010\u000bH\u00c6\u0003J\u000b\u0010-\u001a\u0004\u0018\u00010\u000bH\u00c6\u0003J\u000b\u0010.\u001a\u0004\u0018\u00010\u000bH\u00c6\u0003J\t\u0010/\u001a\u00020\u0010H\u00c6\u0003J\u0091\u0001\u00100\u001a\u00020\u00002\u000e\b\u0002\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\u00062\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\t2\n\b\u0002\u0010\n\u001a\u0004\u0018\u00010\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\u000b2\n\b\u0002\u0010\r\u001a\u0004\u0018\u00010\u000b2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000b2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00062\b\b\u0002\u0010\u0012\u001a\u00020\u00062\b\b\u0002\u0010\u0013\u001a\u00020\u0006H\u00c6\u0001J\u0013\u00101\u001a\u00020\u00062\b\u00102\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u00103\u001a\u000204H\u00d6\u0001J\t\u00105\u001a\u00020\u000bH\u00d6\u0001R\u0011\u0010\u0012\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u0016R\u0011\u0010\u0011\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0017\u0010\u0016R\u0013\u0010\b\u001a\u0004\u0018\u00010\t\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0018\u0010\u0019R\u0013\u0010\n\u001a\u0004\u0018\u00010\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001a\u0010\u001bR\u0013\u0010\f\u001a\u0004\u0018\u00010\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001c\u0010\u001bR\u0011\u0010\u0013\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001d\u0010\u0016R\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0005\u0010\u0016R\u0011\u0010\u0007\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\u0016R\u0011\u0010\u000f\u001a\u00020\u0010\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001e\u0010\u001fR\u0013\u0010\r\u001a\u0004\u0018\u00010\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b \u0010\u001bR\u0013\u0010\u000e\u001a\u0004\u0018\u00010\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b!\u0010\u001bR\u0017\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\"\u0010#\u00a8\u00066"}, d2 = {"Lcom/trackrat/android/ui/trainlist/TrainListViewModel$UiState;", "", "trains", "", "Lcom/trackrat/android/data/models/TrainV2;", "isLoading", "", "isRefreshing", "error", "Lcom/trackrat/android/data/models/ApiException;", "fromStationCode", "", "fromStationName", "toStationCode", "toStationName", "lastUpdated", "", "canRetry", "autoRefreshEnabled", "hapticFeedbackEnabled", "(Ljava/util/List;ZZLcom/trackrat/android/data/models/ApiException;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;JZZZ)V", "getAutoRefreshEnabled", "()Z", "getCanRetry", "getError", "()Lcom/trackrat/android/data/models/ApiException;", "getFromStationCode", "()Ljava/lang/String;", "getFromStationName", "getHapticFeedbackEnabled", "getLastUpdated", "()J", "getToStationCode", "getToStationName", "getTrains", "()Ljava/util/List;", "component1", "component10", "component11", "component12", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "component9", "copy", "equals", "other", "hashCode", "", "toString", "app_release"})
    public static final class UiState {
        @org.jetbrains.annotations.NotNull()
        private final java.util.List<com.trackrat.android.data.models.TrainV2> trains = null;
        private final boolean isLoading = false;
        private final boolean isRefreshing = false;
        @org.jetbrains.annotations.Nullable()
        private final com.trackrat.android.data.models.ApiException error = null;
        @org.jetbrains.annotations.Nullable()
        private final java.lang.String fromStationCode = null;
        @org.jetbrains.annotations.Nullable()
        private final java.lang.String fromStationName = null;
        @org.jetbrains.annotations.Nullable()
        private final java.lang.String toStationCode = null;
        @org.jetbrains.annotations.Nullable()
        private final java.lang.String toStationName = null;
        private final long lastUpdated = 0L;
        private final boolean canRetry = false;
        private final boolean autoRefreshEnabled = false;
        private final boolean hapticFeedbackEnabled = false;
        
        public UiState(@org.jetbrains.annotations.NotNull()
        java.util.List<com.trackrat.android.data.models.TrainV2> trains, boolean isLoading, boolean isRefreshing, @org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.ApiException error, @org.jetbrains.annotations.Nullable()
        java.lang.String fromStationCode, @org.jetbrains.annotations.Nullable()
        java.lang.String fromStationName, @org.jetbrains.annotations.Nullable()
        java.lang.String toStationCode, @org.jetbrains.annotations.Nullable()
        java.lang.String toStationName, long lastUpdated, boolean canRetry, boolean autoRefreshEnabled, boolean hapticFeedbackEnabled) {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.util.List<com.trackrat.android.data.models.TrainV2> getTrains() {
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
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String getFromStationCode() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String getFromStationName() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String getToStationCode() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String getToStationName() {
            return null;
        }
        
        public final long getLastUpdated() {
            return 0L;
        }
        
        public final boolean getCanRetry() {
            return false;
        }
        
        public final boolean getAutoRefreshEnabled() {
            return false;
        }
        
        public final boolean getHapticFeedbackEnabled() {
            return false;
        }
        
        public UiState() {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final java.util.List<com.trackrat.android.data.models.TrainV2> component1() {
            return null;
        }
        
        public final boolean component10() {
            return false;
        }
        
        public final boolean component11() {
            return false;
        }
        
        public final boolean component12() {
            return false;
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
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String component5() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String component6() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String component7() {
            return null;
        }
        
        @org.jetbrains.annotations.Nullable()
        public final java.lang.String component8() {
            return null;
        }
        
        public final long component9() {
            return 0L;
        }
        
        @org.jetbrains.annotations.NotNull()
        public final com.trackrat.android.ui.trainlist.TrainListViewModel.UiState copy(@org.jetbrains.annotations.NotNull()
        java.util.List<com.trackrat.android.data.models.TrainV2> trains, boolean isLoading, boolean isRefreshing, @org.jetbrains.annotations.Nullable()
        com.trackrat.android.data.models.ApiException error, @org.jetbrains.annotations.Nullable()
        java.lang.String fromStationCode, @org.jetbrains.annotations.Nullable()
        java.lang.String fromStationName, @org.jetbrains.annotations.Nullable()
        java.lang.String toStationCode, @org.jetbrains.annotations.Nullable()
        java.lang.String toStationName, long lastUpdated, boolean canRetry, boolean autoRefreshEnabled, boolean hapticFeedbackEnabled) {
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