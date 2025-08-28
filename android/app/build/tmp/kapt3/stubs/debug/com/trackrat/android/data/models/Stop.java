package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

/**
 * Stop information within a train journey
 */
@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0002\b(\b\u0087\b\u0018\u00002\u00020\u0001B\u0081\u0001\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0005\u001a\u00020\u0006\u0012\n\b\u0001\u0010\u0007\u001a\u0004\u0018\u00010\b\u0012\n\b\u0001\u0010\t\u001a\u0004\u0018\u00010\b\u0012\n\b\u0001\u0010\n\u001a\u0004\u0018\u00010\b\u0012\n\b\u0001\u0010\u000b\u001a\u0004\u0018\u00010\b\u0012\b\b\u0003\u0010\f\u001a\u00020\r\u0012\n\b\u0001\u0010\u000e\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0001\u0010\u000f\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0001\u0010\u0010\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\u0002\u0010\u0011J\t\u0010%\u001a\u00020\u0003H\u00c6\u0003J\u000b\u0010&\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u000b\u0010\'\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010(\u001a\u00020\u0003H\u00c6\u0003J\t\u0010)\u001a\u00020\u0006H\u00c6\u0003J\u000b\u0010*\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\u000b\u0010+\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\u000b\u0010,\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\u000b\u0010-\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\t\u0010.\u001a\u00020\rH\u00c6\u0003J\u000b\u0010/\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\u0085\u0001\u00100\u001a\u00020\u00002\b\b\u0003\u0010\u0002\u001a\u00020\u00032\b\b\u0003\u0010\u0004\u001a\u00020\u00032\b\b\u0003\u0010\u0005\u001a\u00020\u00062\n\b\u0003\u0010\u0007\u001a\u0004\u0018\u00010\b2\n\b\u0003\u0010\t\u001a\u0004\u0018\u00010\b2\n\b\u0003\u0010\n\u001a\u0004\u0018\u00010\b2\n\b\u0003\u0010\u000b\u001a\u0004\u0018\u00010\b2\b\b\u0003\u0010\f\u001a\u00020\r2\n\b\u0003\u0010\u000e\u001a\u0004\u0018\u00010\u00032\n\b\u0003\u0010\u000f\u001a\u0004\u0018\u00010\u00032\n\b\u0003\u0010\u0010\u001a\u0004\u0018\u00010\u0003H\u00c6\u0001J\u0013\u00101\u001a\u00020\r2\b\u00102\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u00103\u001a\u00020\u0006H\u00d6\u0001J\t\u00104\u001a\u00020\u0003H\u00d6\u0001R\u0013\u0010\n\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0013R\u0013\u0010\u000b\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0013R\u0013\u0010\u000e\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u0016R\u0013\u0010\u0017\u001a\u0004\u0018\u00010\b8F\u00a2\u0006\u0006\u001a\u0004\b\u0018\u0010\u0013R\u0013\u0010\u0019\u001a\u0004\u0018\u00010\b8F\u00a2\u0006\u0006\u001a\u0004\b\u001a\u0010\u0013R\u0011\u0010\f\u001a\u00020\r\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001b\u0010\u001cR\u0013\u0010\u0007\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001d\u0010\u0013R\u0013\u0010\t\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001e\u0010\u0013R\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u001f\u0010\u0016R\u0011\u0010\u0004\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b \u0010\u0016R\u0013\u0010\u0010\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b!\u0010\u0016R\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\"\u0010#R\u0013\u0010\u000f\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b$\u0010\u0016\u00a8\u00065"}, d2 = {"Lcom/trackrat/android/data/models/Stop;", "", "stationCode", "", "stationName", "stopSequence", "", "scheduledArrival", "Ljava/time/ZonedDateTime;", "scheduledDeparture", "actualArrival", "actualDeparture", "hasDepartedStation", "", "departureSource", "track", "status", "(Ljava/lang/String;Ljava/lang/String;ILjava/time/ZonedDateTime;Ljava/time/ZonedDateTime;Ljava/time/ZonedDateTime;Ljava/time/ZonedDateTime;ZLjava/lang/String;Ljava/lang/String;Ljava/lang/String;)V", "getActualArrival", "()Ljava/time/ZonedDateTime;", "getActualDeparture", "getDepartureSource", "()Ljava/lang/String;", "displayArrivalTime", "getDisplayArrivalTime", "displayDepartureTime", "getDisplayDepartureTime", "getHasDepartedStation", "()Z", "getScheduledArrival", "getScheduledDeparture", "getStationCode", "getStationName", "getStatus", "getStopSequence", "()I", "getTrack", "component1", "component10", "component11", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "component9", "copy", "equals", "other", "hashCode", "toString", "app_debug"})
public final class Stop {
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationCode = null;
    @org.jetbrains.annotations.NotNull()
    private final java.lang.String stationName = null;
    private final int stopSequence = 0;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime scheduledArrival = null;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime scheduledDeparture = null;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime actualArrival = null;
    @org.jetbrains.annotations.Nullable()
    private final java.time.ZonedDateTime actualDeparture = null;
    private final boolean hasDepartedStation = false;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String departureSource = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String track = null;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String status = null;
    
    public Stop(@com.squareup.moshi.Json(name = "station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationCode, @com.squareup.moshi.Json(name = "station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @com.squareup.moshi.Json(name = "stop_sequence")
    int stopSequence, @com.squareup.moshi.Json(name = "scheduled_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledArrival, @com.squareup.moshi.Json(name = "scheduled_departure")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledDeparture, @com.squareup.moshi.Json(name = "actual_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime actualArrival, @com.squareup.moshi.Json(name = "actual_departure")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime actualDeparture, @com.squareup.moshi.Json(name = "has_departed_station")
    boolean hasDepartedStation, @com.squareup.moshi.Json(name = "departure_source")
    @org.jetbrains.annotations.Nullable()
    java.lang.String departureSource, @com.squareup.moshi.Json(name = "track")
    @org.jetbrains.annotations.Nullable()
    java.lang.String track, @com.squareup.moshi.Json(name = "status")
    @org.jetbrains.annotations.Nullable()
    java.lang.String status) {
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
    
    public final int getStopSequence() {
        return 0;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getScheduledArrival() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getScheduledDeparture() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getActualArrival() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getActualDeparture() {
        return null;
    }
    
    public final boolean getHasDepartedStation() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getDepartureSource() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getTrack() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getStatus() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getDisplayDepartureTime() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime getDisplayArrivalTime() {
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
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component11() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String component2() {
        return null;
    }
    
    public final int component3() {
        return 0;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime component4() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime component5() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime component6() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.time.ZonedDateTime component7() {
        return null;
    }
    
    public final boolean component8() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component9() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.Stop copy(@com.squareup.moshi.Json(name = "station_code")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationCode, @com.squareup.moshi.Json(name = "station_name")
    @org.jetbrains.annotations.NotNull()
    java.lang.String stationName, @com.squareup.moshi.Json(name = "stop_sequence")
    int stopSequence, @com.squareup.moshi.Json(name = "scheduled_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledArrival, @com.squareup.moshi.Json(name = "scheduled_departure")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime scheduledDeparture, @com.squareup.moshi.Json(name = "actual_arrival")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime actualArrival, @com.squareup.moshi.Json(name = "actual_departure")
    @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime actualDeparture, @com.squareup.moshi.Json(name = "has_departed_station")
    boolean hasDepartedStation, @com.squareup.moshi.Json(name = "departure_source")
    @org.jetbrains.annotations.Nullable()
    java.lang.String departureSource, @com.squareup.moshi.Json(name = "track")
    @org.jetbrains.annotations.Nullable()
    java.lang.String track, @com.squareup.moshi.Json(name = "status")
    @org.jetbrains.annotations.Nullable()
    java.lang.String status) {
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