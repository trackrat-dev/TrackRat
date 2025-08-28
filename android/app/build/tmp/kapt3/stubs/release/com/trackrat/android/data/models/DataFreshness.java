package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;
import java.time.ZonedDateTime;

@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000$\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\b\n\u0002\b\u0010\n\u0002\u0010\u000e\n\u0000\b\u0087\b\u0018\u00002\u00020\u0001B%\u0012\b\b\u0001\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0005\u0012\n\b\u0001\u0010\u0006\u001a\u0004\u0018\u00010\u0007\u00a2\u0006\u0002\u0010\bJ\t\u0010\u000f\u001a\u00020\u0003H\u00c6\u0003J\t\u0010\u0010\u001a\u00020\u0005H\u00c6\u0003J\u0010\u0010\u0011\u001a\u0004\u0018\u00010\u0007H\u00c6\u0003\u00a2\u0006\u0002\u0010\rJ.\u0010\u0012\u001a\u00020\u00002\b\b\u0003\u0010\u0002\u001a\u00020\u00032\b\b\u0003\u0010\u0004\u001a\u00020\u00052\n\b\u0003\u0010\u0006\u001a\u0004\u0018\u00010\u0007H\u00c6\u0001\u00a2\u0006\u0002\u0010\u0013J\u0013\u0010\u0014\u001a\u00020\u00052\b\u0010\u0015\u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010\u0016\u001a\u00020\u0007H\u00d6\u0001J\t\u0010\u0017\u001a\u00020\u0018H\u00d6\u0001R\u0011\u0010\u0004\u001a\u00020\u0005\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0004\u0010\tR\u0011\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0015\u0010\u0006\u001a\u0004\u0018\u00010\u0007\u00a2\u0006\n\n\u0002\u0010\u000e\u001a\u0004\b\f\u0010\r\u00a8\u0006\u0019"}, d2 = {"Lcom/trackrat/android/data/models/DataFreshness;", "", "lastUpdated", "Ljava/time/ZonedDateTime;", "isStale", "", "stalenessSeconds", "", "(Ljava/time/ZonedDateTime;ZLjava/lang/Integer;)V", "()Z", "getLastUpdated", "()Ljava/time/ZonedDateTime;", "getStalenessSeconds", "()Ljava/lang/Integer;", "Ljava/lang/Integer;", "component1", "component2", "component3", "copy", "(Ljava/time/ZonedDateTime;ZLjava/lang/Integer;)Lcom/trackrat/android/data/models/DataFreshness;", "equals", "other", "hashCode", "toString", "", "app_release"})
public final class DataFreshness {
    @org.jetbrains.annotations.NotNull()
    private final java.time.ZonedDateTime lastUpdated = null;
    private final boolean isStale = false;
    @org.jetbrains.annotations.Nullable()
    private final java.lang.Integer stalenessSeconds = null;
    
    public DataFreshness(@com.squareup.moshi.Json(name = "last_updated")
    @org.jetbrains.annotations.NotNull()
    java.time.ZonedDateTime lastUpdated, @com.squareup.moshi.Json(name = "is_stale")
    boolean isStale, @com.squareup.moshi.Json(name = "staleness_seconds")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer stalenessSeconds) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.time.ZonedDateTime getLastUpdated() {
        return null;
    }
    
    public final boolean isStale() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Integer getStalenessSeconds() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.time.ZonedDateTime component1() {
        return null;
    }
    
    public final boolean component2() {
        return false;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Integer component3() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.DataFreshness copy(@com.squareup.moshi.Json(name = "last_updated")
    @org.jetbrains.annotations.NotNull()
    java.time.ZonedDateTime lastUpdated, @com.squareup.moshi.Json(name = "is_stale")
    boolean isStale, @com.squareup.moshi.Json(name = "staleness_seconds")
    @org.jetbrains.annotations.Nullable()
    java.lang.Integer stalenessSeconds) {
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