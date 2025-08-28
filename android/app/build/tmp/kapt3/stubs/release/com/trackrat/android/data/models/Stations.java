package com.trackrat.android.data.models;

/**
 * Static station data for TrackRat
 * Matches the iOS app's supported stations
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000 \n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0010\u000e\n\u0002\b\u0004\b\u00c6\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002J\u0010\u0010\n\u001a\u0004\u0018\u00010\u00052\u0006\u0010\u000b\u001a\u00020\fJ\u000e\u0010\r\u001a\u00020\f2\u0006\u0010\u000b\u001a\u00020\fJ\u0014\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\u00050\u00042\u0006\u0010\u000f\u001a\u00020\fR\u0017\u0010\u0003\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0006\u0010\u0007R\u0017\u0010\b\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004\u00a2\u0006\b\n\u0000\u001a\u0004\b\t\u0010\u0007\u00a8\u0006\u0010"}, d2 = {"Lcom/trackrat/android/data/models/Stations;", "", "()V", "ALL_STATIONS", "", "Lcom/trackrat/android/data/models/Station;", "getALL_STATIONS", "()Ljava/util/List;", "DEPARTURE_STATIONS", "getDEPARTURE_STATIONS", "getStation", "code", "", "getStationName", "search", "query", "app_release"})
public final class Stations {
    
    /**
     * Main departure stations supported by the app
     */
    @org.jetbrains.annotations.NotNull()
    private static final java.util.List<com.trackrat.android.data.models.Station> DEPARTURE_STATIONS = null;
    
    /**
     * All stations (for destination selection)
     * This is a subset - the full list can be expanded as needed
     */
    @org.jetbrains.annotations.NotNull()
    private static final java.util.List<com.trackrat.android.data.models.Station> ALL_STATIONS = null;
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.data.models.Stations INSTANCE = null;
    
    private Stations() {
        super();
    }
    
    /**
     * Main departure stations supported by the app
     */
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<com.trackrat.android.data.models.Station> getDEPARTURE_STATIONS() {
        return null;
    }
    
    /**
     * All stations (for destination selection)
     * This is a subset - the full list can be expanded as needed
     */
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<com.trackrat.android.data.models.Station> getALL_STATIONS() {
        return null;
    }
    
    /**
     * Get a station by code
     */
    @org.jetbrains.annotations.Nullable()
    public final com.trackrat.android.data.models.Station getStation(@org.jetbrains.annotations.NotNull()
    java.lang.String code) {
        return null;
    }
    
    /**
     * Get station name by code
     */
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getStationName(@org.jetbrains.annotations.NotNull()
    java.lang.String code) {
        return null;
    }
    
    /**
     * Search stations by name or code
     */
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<com.trackrat.android.data.models.Station> search(@org.jetbrains.annotations.NotNull()
    java.lang.String query) {
        return null;
    }
}