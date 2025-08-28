package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

/**
 * Enhanced train model with V2 API fields
 */
@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000J\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\n\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b:\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B\u00fd\u0001\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0001\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0001\u0010\u0005\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0001\u0010\u0006\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0001\u0010\u0007\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0001\u0010\b\u001a\u00020\u0003\u0012\b\b\u0001\u0010\t\u001a\u00020\u0003\u0012\b\b\u0001\u0010\n\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u000b\u001a\u00020\u0003\u0012\n\b\u0001\u0010\f\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0001\u0010\r\u001a\u00020\u000e\u0012\n\b\u0001\u0010\u000f\u001a\u0004\u0018\u00010\u000e\u0012\b\b\u0001\u0010\u0010\u001a\u00020\u0003\u0012\n\b\u0001\u0010\u0011\u001a\u0004\u0018\u00010\u0012\u0012\n\b\u0001\u0010\u0013\u001a\u0004\u0018\u00010\u0014\u0012\n\b\u0001\u0010\u0015\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0003\u0010\u0016\u001a\u00020\u0017\u0012\u0010\b\u0001\u0010\u0018\u001a\n\u0012\u0004\u0012\u00020\u001a\u0018\u00010\u0019\u0012\b\b\u0001\u0010\u001b\u001a\u00020\u0003\u0012\b\b\u0003\u0010\u001c\u001a\u00020\u0017\u0012\b\b\u0003\u0010\u001d\u001a\u00020\u0017\u0012\n\b\u0001\u0010\u001e\u001a\u0004\u0018\u00010\u001f\u00a2\u0006\u0002\u0010 J\t\u0010>\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010?\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010@\u001a\u00020\u000eH\u00c6\u0003J\u000b\u0010A\u001a\u0004\u0018\u00010\u000eH\u00c6\u0003J\t\u0010B\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010C\u001a\u0004\u0018\u00010\u0012H\u00c6\u0003J\u000b\u0010D\u001a\u0004\u0018\u00010\u0014H\u00c6\u0003J\u000b\u0010E\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010F\u001a\u00020\u0017H\u00c6\u0003J\u0011\u0010G\u001a\n\u0012\u0004\u0012\u00020\u001a\u0018\u00010\u0019H\u00c6\u0003J\t\u0010H\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010I\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010J\u001a\u00020\u0017H\u00c6\u0003J\t\u0010K\u001a\u00020\u0017H\u00c6\u0003J\u000b\u0010L\u001a\u0004\u0018\u00010\u001fH\u00c6\u0003J\u000b\u0010M\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010N\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010O\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010P\u001a\u00020\u0003H\u00c6\u0003J\t\u0010Q\u001a\u00020\u0003H\u00c6\u0003J\t\u0010R\u001a\u00020\u0003H\u00c6\u0003J\t\u0010S\u001a\u00020\u0003H\u00c6\u0003J\u0081\u0002\u0010T\u001a\u00020\u00002\b\b\u0003\u0010\u0002\u001a\u00020\u00032\n\b\u0003\u0010\u0004\u001a\u0004\u0018\u00010\u00032\n\b\u0003\u0010\u0005\u001a\u0004\u0018\u00010\u00032\n\b\u0003\u0010\u0006\u001a\u0004\u0018\u00010\u00032\n\b\u0003\u0010\u0007\u001a\u0004\u0018\u00010\u00032\b\b\u0003\u0010\b\u001a\u00020\u00032\b\b\u0003\u0010\t\u001a\u00020\u00032\b\b\u0003\u0010\n\u001a\u00020\u00032\b\b\u0003\u0010\u000b\u001a\u00020\u00032\n\b\u0003\u0010\f\u001a\u0004\u0018\u00010\u00032\b\b\u0003\u0010\r\u001a\u00020\u000e2\n\b\u0003\u0010\u000f\u001a\u0004\u0018\u00010\u000e2\b\b\u0003\u0010\u0010\u001a\u00020\u00032\n\b\u0003\u0010\u0011\u001a\u0004\u0018\u00010\u00122\n\b\u0003\u0010\u0013\u001a\u0004\u0018\u00010\u00142\n\b\u0003\u0010\u0015\u001a\u0004\u0018\u00010\u00032\b\b\u0003\u0010\u0016\u001a\u00020\u00172\u0010\b\u0003\u0010\u0018\u001a\n\u0012\u0004\u0012\u00020\u001a\u0018\u00010\u00192\b\b\u0003\u0010\u001b\u001a\u00020\u00032\b\b\u0003\u0010\u001c\u001a\u00020\u00172\b\b\u0003\u0010\u001d\u001a\u00020\u00172\n\b\u0003\u0010\u001e\u001a\u0004\u0018\u00010\u001fH\u00c6\u0001J\u0013\u0010U\u001a\u00020\u00172\b\u0010V\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\u0010\u0010W\u001a\u0004\u0018\u00010\u000e2\u0006\u0010X\u001a\u00020\u0003J\t\u0010Y\u001a\u00020ZH\u00d6\u0001J\t\u0010[\u001a\u00020\u0003H\u00d6\u0001R\u0011\u0010\u001b\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b!\u0010\"R\u0013\u0010\f\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b#\u0010\"R\u0013\u0010\u0007\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b$\u0010\"R\u0011\u0010%\u001a\u00020\u00038F\u00a2\u0006\u0006\u001a\u0004\b&\u0010\"R\u0011\u0010\u001c\u001a\u00020\u0017\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001c\u0010\'R\u0011\u0010\u001d\u001a\u00020\u0017\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001d\u0010\'R\u0013\u0010\u0005\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b(\u0010\"R\u0013\u0010\u0006\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b)\u0010\"R\u0011\u0010\b\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b*\u0010\"R\u0011\u0010\t\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b+\u0010\"R\u0013\u0010\u001e\u001a\u0004\u0018\u00010\u001f\u00a2\u0006\b\n\u0000\u001a\u0004\b,\u0010-R\u0013\u0010\u0013\u001a\u0004\u0018\u00010\u0014\u00a2\u0006\b\n\u0000\u001a\u0004\b.\u0010/R\u0013\u0010\u000f\u001a\u0004\u0018\u00010\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b0\u00101R\u0011\u0010\r\u001a\u00020\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b2\u00101R\u0011\u0010\u0010\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b3\u0010\"R\u0013\u0010\u0011\u001a\u0004\u0018\u00010\u0012\u00a2\u0006\b\n\u0000\u001a\u0004\b4\u00105R\u0019\u0010\u0018\u001a\n\u0012\u0004\u0012\u00020\u001a\u0018\u00010\u0019\u00a2\u0006\b\n\u0000\u001a\u0004\b6\u00107R\u0011\u0010\n\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b8\u0010\"R\u0011\u0010\u000b\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b9\u0010\"R\u0013\u0010\u0015\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b:\u0010\"R\u0011\u0010\u0016\u001a\u00020\u0017\u00a2\u0006\b\n\u0000\u001a\u0004\b;\u0010\'R\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b<\u0010\"R\u0013\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b=\u0010\"\u00a8\u0006\\"}, d2 = {"Lcom/trackrat/android/data/models/TrainV2;", "", "trainId", "", "trainNumber", "lineCode", "lineName", "direction", "originStationCode", "originStationName", "terminalStationCode", "terminalStationName", "destination", "scheduledDeparture", "Ljava/time/ZonedDateTime;", "scheduledArrival", "status", "statusV2", "Lcom/trackrat/android/data/models/StatusV2;", "progress", "Lcom/trackrat/android/data/models/Progress;", "track", "trackChange", "", "stops", "", "Lcom/trackrat/android/data/models/Stop;", "dataSource", "isCancelled", "isCompleted", "prediction", "Lcom/trackrat/android/data/models/PredictionData;", "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/time/ZonedDateTime;Ljava/time/ZonedDateTime;Ljava/lang/String;Lcom/trackrat/android/data/models/StatusV2;Lcom/trackrat/android/data/models/Progress;Ljava/lang/String;ZLjava/util/List;Ljava/lang/String;ZZLcom/trackrat/android/data/models/PredictionData;)V", "getDataSource", "()Ljava/lang/String;", "getDestination", "getDirection", "displayStatus", "getDisplayStatus", "()Z", "getLineCode", "getLineName", "getOriginStationCode", "getOriginStationName", "getPrediction", "()Lcom/trackrat/android/data/models/PredictionData;", "getProgress", "()Lcom/trackrat/android/data/models/Progress;", "getScheduledArrival", "()Ljava/time/ZonedDateTime;", "getScheduledDeparture", "getStatus", "getStatusV2", "()Lcom/trackrat/android/data/models/StatusV2;", "getStops", "()Ljava/util/List;", "getTerminalStationCode", "getTerminalStationName", "getTrack", "getTrackChange", "getTrainId", "getTrainNumber", "component1", "component10", "component11", "component12", "component13", "component14", "component15", "component16", "component17", "component18", "component19", "component2", "component20", "component21", "component22", "component3", "component4", "component5", "component6", "component7", "component8", "component9", "copy", "equals", "other", "getScheduledDepartureTime", "fromStationCode", "hashCode", "", "toString", "app_release"})
public final class TrainV2 {
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String trainId = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String trainNumber = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String lineCode = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String lineName = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String direction = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String originStationCode = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String originStationName = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String terminalStationCode = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String terminalStationName = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String destination = null;
    @org.jetbrains.annotations.NotNull()
    private final java.time.ZonedDateTime scheduledDeparture = null;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime scheduledArrival = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String status = null;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.StatusV2 statusV2 = null;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.Progress progress = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String track = null;
    private final boolean trackChange = false;
    @org.jetbrains.annotations.Nullable()
    private final java.util.List<com.trackrat.android.data.models.Stop> stops = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String dataSource = null;
    private final boolean isCancelled = false;
    private final boolean isCompleted = false;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.PredictionData prediction = null;
    
    public TrainV2(@com.squareup.moshi.Json(name = "train_id")
    @org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @com.squareup.moshi.Json(name = "train_number")
    @org.jetbrains.annotations.Nullable()
    java.lang.String trainNumber, @com.squareup.moshi.Json(name = "line_code")
    @org.jetbrains.annotations.Nullable()
    java.lang.String lineCode, @com.squareup.moshi.Json(name = "line_name")
    @org.jetbrains.annotations.Nullable()
    java.lang.String lineName, @com.squareup.moshi.Json(name = "direction")
    @org.jetbrains.annotations.Nullable()
    java.lang.String direction, @com.squareup.moshi.Json(name = "origin_station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String originStationCode, @com.squareup.moshi.Json(name = "origin_station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String originStationName, @com.squareup.moshi.Json(name = "terminal_station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String terminalStationCode, @com.squareup.moshi.Json(name = "terminal_station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String terminalStationName, @com.squareup.moshi.Json(name = "destination")
    @org.jetbrains.annotations.Nullable()
    java.lang.String destination, @com.squareup.moshi.Json(name = "scheduled_departure")
    @org.jetbrains.annotations.NotNull()
    java.time.ZonedDateTime scheduledDeparture, @com.squareup.moshi.Json(name = "scheduled_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledArrival, @com.squareup.moshi.Json(name = "status")
    @org.jetbrains.annotations.NotNull()
    java.lang.String status, @com.squareup.moshi.Json(name = "status_v2")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.StatusV2 statusV2, @com.squareup.moshi.Json(name = "progress")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.Progress progress, @com.squareup.moshi.Json(name = "track")
    @org.jetbrains.annotations.Nullable()
    java.lang.String track, @com.squareup.moshi.Json(name = "track_change")
    boolean trackChange, @com.squareup.moshi.Json(name = "stops")
    @org.jetbrains.annotations.Nullable()
    java.util.List<com.trackrat.android.data.models.Stop> stops, @com.squareup.moshi.Json(name = "data_source")
    @org.jetbrains.annotations.NotNull()
    java.lang.String dataSource, @com.squareup.moshi.Json(name = "is_cancelled")
    boolean isCancelled, @com.squareup.moshi.Json(name = "is_completed")
    boolean isCompleted, @com.squareup.moshi.Json(name = "prediction")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.PredictionData prediction) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getTrainId() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getTrainNumber() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getLineCode() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getLineName() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getDirection() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getOriginStationCode() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getOriginStationName() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getTerminalStationCode() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getTerminalStationName() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getDestination() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.time.ZonedDateTime getScheduledDeparture() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getScheduledArrival() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStatus() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.StatusV2 getStatusV2() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.Progress getProgress() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getTrack() {
        return null;
    }
    
    public final boolean getTrackChange() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.util.List<com.trackrat.android.data.models.Stop> getStops() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getDataSource() {
        return null;
    }
    
    public final boolean isCancelled() {
        return false;
    }
    
    public final boolean isCompleted() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.PredictionData getPrediction() {
        return null;
    }
    
    /**
     * Get the scheduled departure time from a specific station
     */
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getScheduledDepartureTime(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStationCode) {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getDisplayStatus() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component1() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component10() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.time.ZonedDateTime component11() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime component12() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component13() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.StatusV2 component14() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.Progress component15() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component16() {
        return null;
    }
    
    public final boolean component17() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.util.List<com.trackrat.android.data.models.Stop> component18() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component19() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component2() {
        return null;
    }
    
    public final boolean component20() {
        return false;
    }
    
    public final boolean component21() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.PredictionData component22() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component3() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component4() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component5() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component6() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component7() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component8() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component9() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.TrainV2 copy(@com.squareup.moshi.Json(name = "train_id")
    @org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @com.squareup.moshi.Json(name = "train_number")
    @org.jetbrains.annotations.Nullable()
    java.lang.String trainNumber, @com.squareup.moshi.Json(name = "line_code")
    @org.jetbrains.annotations.Nullable()
    java.lang.String lineCode, @com.squareup.moshi.Json(name = "line_name")
    @org.jetbrains.annotations.Nullable()
    java.lang.String lineName, @com.squareup.moshi.Json(name = "direction")
    @org.jetbrains.annotations.Nullable()
    java.lang.String direction, @com.squareup.moshi.Json(name = "origin_station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String originStationCode, @com.squareup.moshi.Json(name = "origin_station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String originStationName, @com.squareup.moshi.Json(name = "terminal_station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String terminalStationCode, @com.squareup.moshi.Json(name = "terminal_station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String terminalStationName, @com.squareup.moshi.Json(name = "destination")
    @org.jetbrains.annotations.Nullable()
    java.lang.String destination, @com.squareup.moshi.Json(name = "scheduled_departure")
    @org.jetbrains.annotations.NotNull()
    java.time.ZonedDateTime scheduledDeparture, @com.squareup.moshi.Json(name = "scheduled_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledArrival, @com.squareup.moshi.Json(name = "status")
    @org.jetbrains.annotations.NotNull()
    java.lang.String status, @com.squareup.moshi.Json(name = "status_v2")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.StatusV2 statusV2, @com.squareup.moshi.Json(name = "progress")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.Progress progress, @com.squareup.moshi.Json(name = "track")
    @org.jetbrains.annotations.Nullable()
    java.lang.String track, @com.squareup.moshi.Json(name = "track_change")
    boolean trackChange, @com.squareup.moshi.Json(name = "stops")
    @org.jetbrains.annotations.Nullable()
    java.util.List<com.trackrat.android.data.models.Stop> stops, @com.squareup.moshi.Json(name = "data_source")
    @org.jetbrains.annotations.NotNull()
    java.lang.String dataSource, @com.squareup.moshi.Json(name = "is_cancelled")
    boolean isCancelled, @com.squareup.moshi.Json(name = "is_completed")
    boolean isCompleted, @com.squareup.moshi.Json(name = "prediction")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.PredictionData prediction) {
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