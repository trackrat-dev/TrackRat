package com.trackrat.android.data.models;

import com.squareup.moshi.JsonClass;

@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\"\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0007\n\u0002\u0010\u000b\n\u0002\b\u0016\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001BO\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\b\u0010\u0005\u001a\u0004\u0018\u00010\u0003\u0012\b\u0010\u0006\u001a\u0004\u0018\u00010\u0003\u0012\b\u0010\u0007\u001a\u0004\u0018\u00010\u0003\u0012\b\u0010\b\u001a\u0004\u0018\u00010\u0003\u0012\b\u0010\t\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\n\u001a\u00020\u000b\u00a2\u0006\u0002\u0010\fJ\t\u0010\u0016\u001a\u00020\u0003H\u00c6\u0003J\t\u0010\u0017\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010\u0018\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010\u0019\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010\u001a\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010\u001b\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010\u001c\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010\u001d\u001a\u00020\u000bH\u00c6\u0003Jc\u0010\u001e\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00032\n\b\u0002\u0010\u0005\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\u0006\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\t\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\n\u001a\u00020\u000bH\u00c6\u0001J\u0013\u0010\u001f\u001a\u00020\u000b2\b\u0010 \u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010!\u001a\u00020\"H\u00d6\u0001J\t\u0010#\u001a\u00020\u0003H\u00d6\u0001R\u0011\u0010\n\u001a\u00020\u000b\u00a2\u0006\b\n\u0000\u001a\u0004\b\n\u0010\rR\u0013\u0010\u0006\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000fR\u0013\u0010\b\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\u000fR\u0013\u0010\u0005\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u000fR\u0013\u0010\u0007\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u000fR\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0013\u0010\u000fR\u0011\u0010\u0004\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u000fR\u0013\u0010\t\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u000f\u00a8\u0006$"}, d2 = {"Lcom/trackrat/android/data/models/StopTime;", "", "stationId", "", "stationName", "scheduledArrival", "predictedArrival", "scheduledDeparture", "predictedDeparture", "track", "isCurrent", "", "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Z)V", "()Z", "getPredictedArrival", "()Ljava/lang/String;", "getPredictedDeparture", "getScheduledArrival", "getScheduledDeparture", "getStationId", "getStationName", "getTrack", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "copy", "equals", "other", "hashCode", "", "toString", "app_debug"})
public final class StopTime {
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationId = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationName = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String scheduledArrival = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String predictedArrival = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String scheduledDeparture = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String predictedDeparture = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String track = null;
    private final boolean isCurrent = false;
    
    public StopTime(@org.jetbrains.annotations.NotNull()
    java.lang.String stationId, @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @org.jetbrains.annotations.Nullable()
    java.lang.String scheduledArrival, @org.jetbrains.annotations.Nullable()
    java.lang.String predictedArrival, @org.jetbrains.annotations.Nullable()
    java.lang.String scheduledDeparture, @org.jetbrains.annotations.Nullable()
    java.lang.String predictedDeparture, @org.jetbrains.annotations.Nullable()
    java.lang.String track, boolean isCurrent) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStationId() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStationName() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getScheduledArrival() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getPredictedArrival() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getScheduledDeparture() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getPredictedDeparture() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getTrack() {
        return null;
    }
    
    public final boolean isCurrent() {
        return false;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component1() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component2() {
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
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component6() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component7() {
        return null;
    }
    
    public final boolean component8() {
        return false;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.StopTime copy(@org.jetbrains.annotations.NotNull()
    java.lang.String stationId, @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @org.jetbrains.annotations.Nullable()
    java.lang.String scheduledArrival, @org.jetbrains.annotations.Nullable()
    java.lang.String predictedArrival, @org.jetbrains.annotations.Nullable()
    java.lang.String scheduledDeparture, @org.jetbrains.annotations.Nullable()
    java.lang.String predictedDeparture, @org.jetbrains.annotations.Nullable()
    java.lang.String track, boolean isCurrent) {
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