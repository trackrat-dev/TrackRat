package com.trackrat.android.ui.stationselection;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.data.models.Station;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000H\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u000b\u001a\u00a4\u0001\u0010\u0000\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u00032\f\u0010\u0004\u001a\b\u0012\u0004\u0012\u00020\u00060\u00052\f\u0010\u0007\u001a\b\u0012\u0004\u0012\u00020\u00060\u00052\b\u0010\b\u001a\u0004\u0018\u00010\u00062\b\u0010\t\u001a\u0004\u0018\u00010\u00062\u0006\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\r2\u0012\u0010\u000e\u001a\u000e\u0012\u0004\u0012\u00020\u000b\u0012\u0004\u0012\u00020\u00010\u000f2\u0012\u0010\u0010\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00010\u000f2\u0012\u0010\u0011\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00010\u000f2\f\u0010\u0012\u001a\b\u0012\u0004\u0012\u00020\u00010\u00132\u0006\u0010\u0014\u001a\u00020\u0015H\u0007\u001ao\u0010\u0016\u001a\u00020\u00012\b\b\u0002\u0010\u0014\u001a\u00020\u001528\u0010\u0017\u001a4\u0012\u0013\u0012\u00110\u000b\u00a2\u0006\f\b\u0019\u0012\b\b\u001a\u0012\u0004\b\b(\u001b\u0012\u0015\u0012\u0013\u0018\u00010\u000b\u00a2\u0006\f\b\u0019\u0012\b\b\u001a\u0012\u0004\b\b(\u001c\u0012\u0004\u0012\u00020\u00010\u00182!\u0010\u001d\u001a\u001d\u0012\u0013\u0012\u00110\u000b\u00a2\u0006\f\b\u0019\u0012\b\b\u001a\u0012\u0004\b\b(\u001e\u0012\u0004\u0012\u00020\u00010\u000fH\u0007\u001a\b\u0010\u001f\u001a\u00020\u0001H\u0007\u001a<\u0010 \u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u00032\u0006\u0010!\u001a\u00020\u000b2\u0012\u0010\"\u001a\u000e\u0012\u0004\u0012\u00020\u000b\u0012\u0004\u0012\u00020\u00010\u000f2\f\u0010#\u001a\b\u0012\u0004\u0012\u00020\u00010\u0013H\u0007\u00a8\u0006$"}, d2 = {"StationSelectionContent", "", "modifier", "Landroidx/compose/ui/Modifier;", "departureStations", "", "Lcom/trackrat/android/data/models/Station;", "searchResults", "selectedOrigin", "selectedDestination", "destinationSearchText", "", "showDestinationSearch", "", "onDestinationSearchTextChange", "Lkotlin/Function1;", "onOriginSelected", "onDestinationSelected", "onFindTrainsClicked", "Lkotlin/Function0;", "viewModel", "Lcom/trackrat/android/ui/stationselection/StationSelectionViewModel;", "StationSelectionScreen", "onNavigateToTrains", "Lkotlin/Function2;", "Lkotlin/ParameterName;", "name", "originCode", "destinationCode", "onNavigateToTrainDetail", "trainId", "StationSelectionScreenPreview", "TrainSearchContent", "trainSearchText", "onTrainSearchTextChange", "onSearchTrain", "app_release"})
public final class StationSelectionScreenKt {
    
    @kotlin.OptIn(markerClass = {androidx.compose.material3.ExperimentalMaterial3Api.class})
    @androidx.compose.runtime.Composable()
    public static final void StationSelectionScreen(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.stationselection.StationSelectionViewModel viewModel, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function2<? super java.lang.String, ? super java.lang.String, kotlin.Unit> onNavigateToTrains, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> onNavigateToTrainDetail) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void StationSelectionContent(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier, @org.jetbrains.annotations.NotNull()
    java.util.List<com.trackrat.android.data.models.Station> departureStations, @org.jetbrains.annotations.NotNull()
    java.util.List<com.trackrat.android.data.models.Station> searchResults, @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.Station selectedOrigin, @org.jetbrains.annotations.Nullable()
    com.trackrat.android.data.models.Station selectedDestination, @org.jetbrains.annotations.NotNull()
    java.lang.String destinationSearchText, boolean showDestinationSearch, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> onDestinationSearchTextChange, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super com.trackrat.android.data.models.Station, kotlin.Unit> onOriginSelected, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super com.trackrat.android.data.models.Station, kotlin.Unit> onDestinationSelected, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onFindTrainsClicked, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.stationselection.StationSelectionViewModel viewModel) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void TrainSearchContent(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier, @org.jetbrains.annotations.NotNull()
    java.lang.String trainSearchText, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> onTrainSearchTextChange, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onSearchTrain) {
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void StationSelectionScreenPreview() {
    }
}