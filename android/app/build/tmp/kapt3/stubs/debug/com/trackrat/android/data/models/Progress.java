package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

/**
 * Real-time journey progress information
 */
@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00004\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0011\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0000\b\u0087\b\u0018\u00002\u00020\u0001B;\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0005\u001a\u00020\u0006\u0012\n\b\u0001\u0010\u0007\u001a\u0004\u0018\u00010\b\u0012\n\b\u0001\u0010\t\u001a\u0004\u0018\u00010\n\u00a2\u0006\u0002\u0010\u000bJ\t\u0010\u0015\u001a\u00020\u0003H\u00c6\u0003J\t\u0010\u0016\u001a\u00020\u0003H\u00c6\u0003J\t\u0010\u0017\u001a\u00020\u0006H\u00c6\u0003J\u000b\u0010\u0018\u001a\u0004\u0018\u00010\bH\u00c6\u0003J\u000b\u0010\u0019\u001a\u0004\u0018\u00010\nH\u00c6\u0003J?\u0010\u001a\u001a\u00020\u00002\b\b\u0003\u0010\u0002\u001a\u00020\u00032\b\b\u0003\u0010\u0004\u001a\u00020\u00032\b\b\u0003\u0010\u0005\u001a\u00020\u00062\n\b\u0003\u0010\u0007\u001a\u0004\u0018\u00010\b2\n\b\u0003\u0010\t\u001a\u0004\u0018\u00010\nH\u00c6\u0001J\u0013\u0010\u001b\u001a\u00020\u001c2\b\u0010\u001d\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010\u001e\u001a\u00020\u0003H\u00d6\u0001J\t\u0010\u001f\u001a\u00020 H\u00d6\u0001R\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\f\u0010\rR\u0013\u0010\u0007\u001a\u0004\u0018\u00010\b\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000fR\u0013\u0010\t\u001a\u0004\u0018\u00010\n\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\u0011R\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0013R\u0011\u0010\u0004\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0013\u00a8\u0006!"}, d2 = {"Lcom/trackrat/android/data/models/Progress;", "", "stopsCompleted", "", "stopsTotal", "journeyPercent", "", "lastDeparted", "Lcom/trackrat/android/data/models/DepartedStation;", "nextArrival", "Lcom/trackrat/android/data/models/NextArrival;", "(IIFLcom/trackrat/android/data/models/DepartedStation;Lcom/trackrat/android/data/models/NextArrival;)V", "getJourneyPercent", "()F", "getLastDeparted", "()Lcom/trackrat/android/data/models/DepartedStation;", "getNextArrival", "()Lcom/trackrat/android/data/models/NextArrival;", "getStopsCompleted", "()I", "getStopsTotal", "component1", "component2", "component3", "component4", "component5", "copy", "equals", "", "other", "hashCode", "toString", "", "app_debug"})
public final class Progress {
    private final int stopsCompleted = 0;
    private final int stopsTotal = 0;
    private final float journeyPercent = 0.0F;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.DepartedStation lastDeparted = null;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.NextArrival nextArrival = null;
    
    public Progress(@com.squareup.moshi.Json(name = "stops_completed")
    int stopsCompleted, @com.squareup.moshi.Json(name = "stops_total")
    int stopsTotal, @com.squareup.moshi.Json(name = "journey_percent")
    float journeyPercent, @com.squareup.moshi.Json(name = "last_departed")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.DepartedStation lastDeparted, @com.squareup.moshi.Json(name = "next_arrival")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.NextArrival nextArrival) {
        super();
    }
    
    public final int getStopsCompleted() {
        return 0;
    }
    
    public final int getStopsTotal() {
        return 0;
    }
    
    public final float getJourneyPercent() {
        return 0.0F;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.DepartedStation getLastDeparted() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.NextArrival getNextArrival() {
        return null;
    }
    
    public final int component1() {
        return 0;
    }
    
    public final int component2() {
        return 0;
    }
    
    public final float component3() {
        return 0.0F;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.DepartedStation component4() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.NextArrival component5() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.Progress copy(@com.squareup.moshi.Json(name = "stops_completed")
    int stopsCompleted, @com.squareup.moshi.Json(name = "stops_total")
    int stopsTotal, @com.squareup.moshi.Json(name = "journey_percent")
    float journeyPercent, @com.squareup.moshi.Json(name = "last_departed")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.DepartedStation lastDeparted, @com.squareup.moshi.Json(name = "next_arrival")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.NextArrival nextArrival) {
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