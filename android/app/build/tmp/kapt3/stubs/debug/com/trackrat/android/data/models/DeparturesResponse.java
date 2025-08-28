package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

/**
 * Response from /api/v2/trains/departures endpoint
 */
@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u00008\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u000e\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0087\b\u0018\u00002\u00020\u0001B5\u0012\u000e\b\u0001\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003\u0012\b\b\u0001\u0010\u0005\u001a\u00020\u0006\u0012\n\b\u0001\u0010\u0007\u001a\u0004\u0018\u00010\u0006\u0012\b\b\u0001\u0010\b\u001a\u00020\t\u00a2\u0006\u0002\u0010\nJ\u000f\u0010\u0012\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003H\u00c6\u0003J\t\u0010\u0013\u001a\u00020\u0006H\u00c6\u0003J\u000b\u0010\u0014\u001a\u0004\u0018\u00010\u0006H\u00c6\u0003J\t\u0010\u0015\u001a\u00020\tH\u00c6\u0003J9\u0010\u0016\u001a\u00020\u00002\u000e\b\u0003\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u00032\b\b\u0003\u0010\u0005\u001a\u00020\u00062\n\b\u0003\u0010\u0007\u001a\u0004\u0018\u00010\u00062\b\b\u0003\u0010\b\u001a\u00020\tH\u00c6\u0001J\u0013\u0010\u0017\u001a\u00020\u00182\b\u0010\u0019\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010\u001a\u001a\u00020\u001bH\u00d6\u0001J\t\u0010\u001c\u001a\u00020\u001dH\u00d6\u0001R\u0011\u0010\b\u001a\u00020\t\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\fR\u0011\u0010\u0005\u001a\u00020\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u0013\u0010\u0007\u001a\u0004\u0018\u00010\u0006\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u000eR\u0017\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\u0011\u00a8\u0006\u001e"}, d2 = {"Lcom/trackrat/android/data/models/DeparturesResponse;", "", "trains", "", "Lcom/trackrat/android/data/models/TrainV2;", "fromStation", "Lcom/trackrat/android/data/models/SimpleStation;", "toStation", "freshness", "Lcom/trackrat/android/data/models/DataFreshness;", "(Ljava/util/List;Lcom/trackrat/android/data/models/SimpleStation;Lcom/trackrat/android/data/models/SimpleStation;Lcom/trackrat/android/data/models/DataFreshness;)V", "getFreshness", "()Lcom/trackrat/android/data/models/DataFreshness;", "getFromStation", "()Lcom/trackrat/android/data/models/SimpleStation;", "getToStation", "getTrains", "()Ljava/util/List;", "component1", "component2", "component3", "component4", "copy", "equals", "", "other", "hashCode", "", "toString", "", "app_debug"})
public final class DeparturesResponse {
    @org.jetbrains.annotations.NotNull()
    private final java.util.List<com.trackrat.android.data.models.TrainV2> trains = null;
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.models.SimpleStation fromStation = null;
    @org.jetbrains.annotations.Nullable()
    private final com.trackrat.android.data.models.SimpleStation toStation = null;
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.models.DataFreshness freshness = null;
    
    public DeparturesResponse(@com.squareup.moshi.Json(name = "trains")
    @org.jetbrains.annotations.NotNull()
    java.util.List<com.trackrat.android.data.models.TrainV2> trains, @com.squareup.moshi.Json(name = "from_station")
    @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.SimpleStation fromStation, @com.squareup.moshi.Json(name = "to_station")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.SimpleStation toStation, @com.squareup.moshi.Json(name = "freshness")
    @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.DataFreshness freshness) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<com.trackrat.android.data.models.TrainV2> getTrains() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.SimpleStation getFromStation() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.SimpleStation getToStation() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.DataFreshness getFreshness() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<com.trackrat.android.data.models.TrainV2> component1() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.SimpleStation component2() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.SimpleStation component3() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.DataFreshness component4() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.DeparturesResponse copy(@com.squareup.moshi.Json(name = "trains")
    @org.jetbrains.annotations.NotNull()
    java.util.List<com.trackrat.android.data.models.TrainV2> trains, @com.squareup.moshi.Json(name = "from_station")
    @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.SimpleStation fromStation, @com.squareup.moshi.Json(name = "to_station")
    @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.SimpleStation toStation, @com.squareup.moshi.Json(name = "freshness")
    @org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.DataFreshness freshness) {
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