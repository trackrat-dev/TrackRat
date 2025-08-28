package com.trackrat.android.data.api;

import com.squareup.moshi.*;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/**
 * Moshi adapter for ZonedDateTime that handles Eastern Time zone
 * and multiple ISO8601 formats with fractional seconds
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000,\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\u0018\u0000 \u000f2\b\u0012\u0004\u0012\u00020\u00020\u0001:\u0001\u000fB\u0005\u00a2\u0006\u0002\u0010\u0003J\u0012\u0010\u0004\u001a\u0004\u0018\u00010\u00022\u0006\u0010\u0005\u001a\u00020\u0006H\u0017J\u0010\u0010\u0007\u001a\u00020\u00022\u0006\u0010\b\u001a\u00020\tH\u0002J\u001a\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\r2\b\u0010\u000e\u001a\u0004\u0018\u00010\u0002H\u0017\u00a8\u0006\u0010"}, d2 = {"Lcom/trackrat/android/data/api/ZonedDateTimeAdapter;", "Lcom/squareup/moshi/JsonAdapter;", "Ljava/time/ZonedDateTime;", "()V", "fromJson", "reader", "Lcom/squareup/moshi/JsonReader;", "parseDateTime", "dateString", "", "toJson", "", "writer", "Lcom/squareup/moshi/JsonWriter;", "value", "Companion", "app_release"})
public final class ZonedDateTimeAdapter extends com.squareup.moshi.JsonAdapter<java.time.ZonedDateTime> {
    private static final java.time.ZoneId ET_ZONE = null;
    @org.jetbrains.annotations.NotNull()
    private static final java.util.List<java.time.format.DateTimeFormatter> FORMATTERS = null;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.data.api.ZonedDateTimeAdapter.Companion Companion = null;
    
    public ZonedDateTimeAdapter() {
        super();
    }
    
    @com.squareup.moshi.FromJson()
    @java.lang.Override()
    @org.jetbrains.annotations.Nullable()
    public java.time.ZonedDateTime fromJson(@org.jetbrains.annotations.NotNull()
    com.squareup.moshi.JsonReader reader) {
        return null;
    }
    
    @com.squareup.moshi.ToJson()
    @java.lang.Override()
    public void toJson(@org.jetbrains.annotations.NotNull()
    com.squareup.moshi.JsonWriter writer, @org.jetbrains.annotations.Nullable()
    java.time.ZonedDateTime value) {
    }
    
    private final java.time.ZonedDateTime parseDateTime(java.lang.String dateString) {
        return null;
    }
    
    @kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000\u001e\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002R\u0016\u0010\u0003\u001a\n \u0005*\u0004\u0018\u00010\u00040\u0004X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001c\u0010\u0006\u001a\u0010\u0012\f\u0012\n \u0005*\u0004\u0018\u00010\b0\b0\u0007X\u0082\u0004\u00a2\u0006\u0002\n\u0000\u00a8\u0006\t"}, d2 = {"Lcom/trackrat/android/data/api/ZonedDateTimeAdapter$Companion;", "", "()V", "ET_ZONE", "Ljava/time/ZoneId;", "kotlin.jvm.PlatformType", "FORMATTERS", "", "Ljava/time/format/DateTimeFormatter;", "app_release"})
    public static final class Companion {
        
        private Companion() {
            super();
        }
    }
}