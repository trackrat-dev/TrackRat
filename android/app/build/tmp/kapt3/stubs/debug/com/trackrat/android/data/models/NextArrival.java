package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0010\n\u0002\u0010\u000b\n\u0002\b\u0004\b\u0087\b\u0018\u00002\u00020\u0001B1\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0003\u0012\n\b\u0001\u0010\u0005\u001a\u0004\u0018\u00010\u0006\u0012\n\b\u0001\u0010\u0007\u001a\u0004\u0018\u00010\b\u00a2\u0006\u0002\u0010\tJ\t\u0010\u0012\u001a\u00020\u0003H\u00c6\u0003J\t\u0010\u0013\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010\u0014\u001a\u0004\u0018\u00010\u0006H\u00c6\u0003J\u0010\u0010\u0015\u001a\u0004\u0018\u00010\bH\u00c6\u0003\u00a2\u0006\u0002\u0010\rJ:\u0010\u0016\u001a\u00020\u00002\b\b\u0003\u0010\u0002\u001a\u00020\u00032\b\b\u0003\u0010\u0004\u001a\u00020\u00032\n\b\u0003\u0010\u0005\u001a\u0004\u0018\u00010\u00062\n\b\u0003\u0010\u0007\u001a\u0004\u0018\u00010\bH\u00c6\u0001\u00a2\u0006\u0002\u0010\u0017J\u0013\u0010\u0018\u001a\u00020\u00192\b\u0010\u001a\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010\u001b\u001a\u00020\bH\u00d6\u0001J\t\u0010\u001c\u001a\u00020\u0003H\u00d6\u0001R\u0013\u0010\u0005\u001a\u0004\u0018\u00010\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0015\u0010\u0007\u001a\u0004\u0018\u00010\b\u00a2\u0006\n\n\u0002\u0010\u000e\u001a\u0004\b\f\u0010\rR\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u0011\u0010\u0004\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u0010\u00a8\u0006\u001d"}, d2 = {"Lcom/trackrat/android/data/models/NextArrival;", "", "stationCode", "", "stationName", "estimatedTime", "Ljava/time/ZonedDateTime;", "minutesToArrival", "", "(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZonedDateTime;Ljava/lang/Integer;)V", "getEstimatedTime", "()Ljava/time/ZonedDateTime;", "getMinutesToArrival", "()Ljava/lang/Integer;", "Ljava/lang/Integer;", "getStationCode", "()Ljava/lang/String;", "getStationName", "component1", "component2", "component3", "component4", "copy", "(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZonedDateTime;Ljava/lang/Integer;)Lcom/trackrat/android/data/models/NextArrival;", "equals", "", "other", "hashCode", "toString", "app_debug"})
public final class NextArrival {
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationCode = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationName = null;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime estimatedTime = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.Integer minutesToArrival = null;
    
    public NextArrival(@com.squareup.moshi.Json(name = "station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationCode, @com.squareup.moshi.Json(name = "station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @com.squareup.moshi.Json(name = "estimated_time")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime estimatedTime, @com.squareup.moshi.Json(name = "minutes_to_arrival")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer minutesToArrival) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStationCode() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStationName() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getEstimatedTime() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Integer getMinutesToArrival() {
        return null;
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
    public final java.time.ZonedDateTime component3() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Integer component4() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.NextArrival copy(@com.squareup.moshi.Json(name = "station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationCode, @com.squareup.moshi.Json(name = "station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @com.squareup.moshi.Json(name = "estimated_time")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime estimatedTime, @com.squareup.moshi.Json(name = "minutes_to_arrival")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer minutesToArrival) {
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