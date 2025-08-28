package com.trackrat.android.services;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import androidx.core.app.NotificationCompat;
import com.trackrat.android.MainActivity;
import com.trackrat.android.R;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.data.repository.TrackRatRepository;
import dagger.hilt.android.AndroidEntryPoint;
import kotlinx.coroutines.*;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

/**
 * Foreground service for tracking a train journey in real-time.
 * Updates every 30 seconds with latest train information.
 */
@dagger.hilt.android.AndroidEntryPoint()
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000T\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\b\n\u0002\b\b\n\u0002\u0018\u0002\n\u0002\b\u0004\b\u0007\u0018\u0000 *2\u00020\u0001:\u0001*B\u0005\u00a2\u0006\u0002\u0010\u0002J$\u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00042\u0006\u0010\u0013\u001a\u00020\u00042\n\b\u0002\u0010\u0014\u001a\u0004\u0018\u00010\u0004H\u0002J\b\u0010\u0015\u001a\u00020\u0016H\u0002J\u0014\u0010\u0017\u001a\u0004\u0018\u00010\u00182\b\u0010\u0019\u001a\u0004\u0018\u00010\u001aH\u0016J\b\u0010\u001b\u001a\u00020\u0016H\u0016J\b\u0010\u001c\u001a\u00020\u0016H\u0016J\"\u0010\u001d\u001a\u00020\u001e2\b\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\u0006\u0010\u001f\u001a\u00020\u001e2\u0006\u0010 \u001a\u00020\u001eH\u0016J\u0018\u0010!\u001a\u00020\u00162\u0006\u0010\"\u001a\u00020\u00042\u0006\u0010#\u001a\u00020\u0004H\u0002J\b\u0010$\u001a\u00020\u0016H\u0002J\u0010\u0010%\u001a\u00020\u00162\u0006\u0010&\u001a\u00020\'H\u0002J\u000e\u0010(\u001a\u00020\u0016H\u0082@\u00a2\u0006\u0002\u0010)R\u0010\u0010\u0003\u001a\u0004\u0018\u00010\u0004X\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u0010\u0010\u0005\u001a\u0004\u0018\u00010\u0004X\u0082\u000e\u00a2\u0006\u0002\n\u0000R\u001e\u0010\u0006\u001a\u00020\u00078\u0006@\u0006X\u0087.\u00a2\u0006\u000e\n\u0000\u001a\u0004\b\b\u0010\t\"\u0004\b\n\u0010\u000bR\u000e\u0010\f\u001a\u00020\rX\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0010\u0010\u000e\u001a\u0004\u0018\u00010\u000fX\u0082\u000e\u00a2\u0006\u0002\n\u0000\u00a8\u0006+"}, d2 = {"Lcom/trackrat/android/services/TrainTrackingService;", "Landroid/app/Service;", "()V", "currentDate", "", "currentTrainId", "repository", "Lcom/trackrat/android/data/repository/TrackRatRepository;", "getRepository", "()Lcom/trackrat/android/data/repository/TrackRatRepository;", "setRepository", "(Lcom/trackrat/android/data/repository/TrackRatRepository;)V", "serviceScope", "Lkotlinx/coroutines/CoroutineScope;", "updateJob", "Lkotlinx/coroutines/Job;", "createNotification", "Landroid/app/Notification;", "title", "content", "subText", "createNotificationChannel", "", "onBind", "Landroid/os/IBinder;", "intent", "Landroid/content/Intent;", "onCreate", "onDestroy", "onStartCommand", "", "flags", "startId", "startTracking", "trainId", "date", "stopTracking", "updateNotification", "train", "Lcom/trackrat/android/data/models/TrainV2;", "updateTrainStatus", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "Companion", "app_debug"})
public final class TrainTrackingService extends android.app.Service {
    @javax.inject.Inject()
    public com.trackrat.android.data.repository.TrackRatRepository repository;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.CoroutineScope serviceScope = null;
    @org.jetbrains.annotations.Nullable()
    private kotlinx.coroutines.Job updateJob;
    @org.jetbrains.annotations.Nullable()
    private java.lang.String currentTrainId;
    @org.jetbrains.annotations.Nullable()
    private java.lang.String currentDate;
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String CHANNEL_ID = "train_tracking_channel";
    public static final int NOTIFICATION_ID = 1001;
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String ACTION_START = "com.trackrat.android.action.START_TRACKING";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String ACTION_STOP = "com.trackrat.android.action.STOP_TRACKING";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String EXTRA_TRAIN_ID = "train_id";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String EXTRA_DATE = "date";
    @org.jetbrains.annotations.NotNull()
    public static final java.lang.String EXTRA_FROM_STATION = "from_station";
    public static final long UPDATE_INTERVAL_MS = 30000L;
    @org.jetbrains.annotations.NotNull()
    private static final kotlinx.coroutines.flow.MutableStateFlow<java.lang.String> _isTracking = null;
    @org.jetbrains.annotations.NotNull()
    private static final kotlinx.coroutines.flow.StateFlow<java.lang.String> isTracking = null;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.services.TrainTrackingService.Companion Companion = null;
    
    public TrainTrackingService() {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.repository.TrackRatRepository getRepository() {
        return null;
    }
    
    public final void setRepository(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.repository.TrackRatRepository p0) {
    }
    
    @java.lang.Override()
    public void onCreate() {
    }
    
    @java.lang.Override()
    public int onStartCommand(@org.jetbrains.annotations.Nullable()
    android.content.Intent intent, int flags, int startId) {
        return 0;
    }
    
    @java.lang.Override()
    @org.jetbrains.annotations.Nullable()
    public android.os.IBinder onBind(@org.jetbrains.annotations.Nullable()
    android.content.Intent intent) {
        return null;
    }
    
    @java.lang.Override()
    public void onDestroy() {
    }
    
    private final void startTracking(java.lang.String trainId, java.lang.String date) {
    }
    
    private final void stopTracking() {
    }
    
    private final java.lang.Object updateTrainStatus(kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    private final void updateNotification(com.trackrat.android.data.models.TrainV2 train) {
    }
    
    private final android.app.Notification createNotification(java.lang.String title, java.lang.String content, java.lang.String subText) {
        return null;
    }
    
    private final void createNotificationChannel() {
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000D\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0006\n\u0002\u0010\b\n\u0000\n\u0002\u0010\t\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002J\u000e\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0004J*\u0010\u0016\u001a\u00020\u00172\u0006\u0010\u0018\u001a\u00020\u00192\u0006\u0010\u0015\u001a\u00020\u00042\u0006\u0010\u001a\u001a\u00020\u00042\n\b\u0002\u0010\u001b\u001a\u0004\u0018\u00010\u0004J\u000e\u0010\u001c\u001a\u00020\u00172\u0006\u0010\u0018\u001a\u00020\u0019R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\t\u001a\u00020\u0004X\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u000bX\u0086T\u00a2\u0006\u0002\n\u0000R\u000e\u0010\f\u001a\u00020\rX\u0086T\u00a2\u0006\u0002\n\u0000R\u0016\u0010\u000e\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00040\u000fX\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0019\u0010\u0010\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00040\u0011\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\u0012\u00a8\u0006\u001d"}, d2 = {"Lcom/trackrat/android/services/TrainTrackingService$Companion;", "", "()V", "ACTION_START", "", "ACTION_STOP", "CHANNEL_ID", "EXTRA_DATE", "EXTRA_FROM_STATION", "EXTRA_TRAIN_ID", "NOTIFICATION_ID", "", "UPDATE_INTERVAL_MS", "", "_isTracking", "Lkotlinx/coroutines/flow/MutableStateFlow;", "isTracking", "Lkotlinx/coroutines/flow/StateFlow;", "()Lkotlinx/coroutines/flow/StateFlow;", "isTrackingTrain", "", "trainId", "startTracking", "", "context", "Landroid/content/Context;", "date", "fromStation", "stopTracking", "app_debug"})
    public static final class Companion {
        
        private Companion() {
            super();
        }
        
        @org.jetbrains.annotations.NotNull()
        public final kotlinx.coroutines.flow.StateFlow<java.lang.String> isTracking() {
            return null;
        }
        
        /**
         * Start tracking a train
         */
        public final void startTracking(@org.jetbrains.annotations.NotNull()
        android.content.Context context, @org.jetbrains.annotations.NotNull()
        java.lang.String trainId, @org.jetbrains.annotations.NotNull()
        java.lang.String date, @org.jetbrains.annotations.Nullable()
        java.lang.String fromStation) {
        }
        
        /**
         * Stop tracking the current train
         */
        public final void stopTracking(@org.jetbrains.annotations.NotNull()
        android.content.Context context) {
        }
        
        /**
         * Check if a specific train is being tracked
         */
        public final boolean isTrackingTrain(@org.jetbrains.annotations.NotNull()
        java.lang.String trainId) {
            return false;
        }
    }
}