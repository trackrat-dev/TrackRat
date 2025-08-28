package com.trackrat.android.ui.stationselection;

import androidx.lifecycle.ViewModel;
import com.trackrat.android.data.models.Station;
import com.trackrat.android.data.models.Stations;
import com.trackrat.android.data.repository.TrackRatRepository;
import dagger.hilt.android.lifecycle.HiltViewModel;
import kotlinx.coroutines.flow.StateFlow;
import javax.inject.Inject;

/**
 * ViewModel for station selection screens
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000:\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u000b\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0004\b\u0007\u0018\u00002\u00020\u0001B\u000f\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u00a2\u0006\u0002\u0010\u0004J\u0006\u0010\u0019\u001a\u00020\u001aJ\u000e\u0010\u001b\u001a\u00020\u001a2\u0006\u0010\u001c\u001a\u00020\u001dJ\u000e\u0010\u001e\u001a\u00020\u001a2\u0006\u0010\u001f\u001a\u00020\bJ\u000e\u0010 \u001a\u00020\u001a2\u0006\u0010\u001f\u001a\u00020\bR\u001a\u0010\u0005\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001a\u0010\t\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001a\u0010\n\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0016\u0010\u000b\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\b0\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u0016\u0010\f\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\b0\u0006X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001d\u0010\r\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u001d\u0010\u0011\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0010R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004\u00a2\u0006\u0002\n\u0000R\u001d\u0010\u0013\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\b0\u00070\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0010R\u0019\u0010\u0015\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\b0\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0010R\u0019\u0010\u0017\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\b0\u000e\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0018\u0010\u0010\u00a8\u0006!"}, d2 = {"Lcom/trackrat/android/ui/stationselection/StationSelectionViewModel;", "Landroidx/lifecycle/ViewModel;", "repository", "Lcom/trackrat/android/data/repository/TrackRatRepository;", "(Lcom/trackrat/android/data/repository/TrackRatRepository;)V", "_allStations", "Lkotlinx/coroutines/flow/MutableStateFlow;", "", "Lcom/trackrat/android/data/models/Station;", "_departureStations", "_searchResults", "_selectedDestination", "_selectedOrigin", "allStations", "Lkotlinx/coroutines/flow/StateFlow;", "getAllStations", "()Lkotlinx/coroutines/flow/StateFlow;", "departureStations", "getDepartureStations", "searchResults", "getSearchResults", "selectedDestination", "getSelectedDestination", "selectedOrigin", "getSelectedOrigin", "clearSelections", "", "searchStations", "query", "", "selectDestination", "station", "selectOrigin", "app_release"})
@dagger.hilt.android.lifecycle.HiltViewModel()
public final class StationSelectionViewModel extends androidx.lifecycle.ViewModel {
    @org.jetbrains.annotations.NotNull()
    private final com.trackrat.android.data.repository.TrackRatRepository repository = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<java.util.List<com.trackrat.android.data.models.Station>> _departureStations = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> departureStations = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<java.util.List<com.trackrat.android.data.models.Station>> _allStations = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> allStations = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<java.util.List<com.trackrat.android.data.models.Station>> _searchResults = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> searchResults = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.trackrat.android.data.models.Station> _selectedOrigin = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.data.models.Station> selectedOrigin = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.MutableStateFlow<com.trackrat.android.data.models.Station> _selectedDestination = null;
    @org.jetbrains.annotations.NotNull()
    private final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.data.models.Station> selectedDestination = null;
    
    @javax.inject.Inject()
    public StationSelectionViewModel(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.repository.TrackRatRepository repository) {
        super();
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> getDepartureStations() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> getAllStations() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<java.util.List<com.trackrat.android.data.models.Station>> getSearchResults() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.data.models.Station> getSelectedOrigin() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final kotlinx.coroutines.flow.StateFlow<com.trackrat.android.data.models.Station> getSelectedDestination() {
        return null;
    }
    
    /**
     * Select origin station
     */
    public final void selectOrigin(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.Station station) {
    }
    
    /**
     * Select destination station
     */
    public final void selectDestination(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.Station station) {
    }
    
    /**
     * Search stations by query
     */
    public final void searchStations(@org.jetbrains.annotations.NotNull()
    java.lang.String query) {
    }
    
    /**
     * Clear selections
     */
    public final void clearSelections() {
    }
}