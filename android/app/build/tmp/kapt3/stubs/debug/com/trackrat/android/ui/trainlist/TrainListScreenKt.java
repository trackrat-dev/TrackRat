package com.trackrat.android.ui.trainlist;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.hapticfeedback.HapticFeedbackType;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextOverflow;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.utils.Constants;
import com.trackrat.android.utils.HapticFeedbackHelper;
import java.time.format.DateTimeFormatter;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000B\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\t\n\u0000\u001a\u0010\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\u0018\u0010\u0004\u001a\u00020\u00012\u0006\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\bH\u0007\u001a.\u0010\t\u001a\u00020\u00012\u0006\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\u00062\u0006\u0010\r\u001a\u00020\u000e2\f\u0010\u000f\u001a\b\u0012\u0004\u0012\u00020\u00010\u0010H\u0007\u001aF\u0010\u0011\u001a\u00020\u00012\u0006\u0010\f\u001a\u00020\u00062\b\u0010\u0012\u001a\u0004\u0018\u00010\u00062\b\b\u0002\u0010\r\u001a\u00020\u000e2\f\u0010\u0013\u001a\b\u0012\u0004\u0012\u00020\u00010\u00102\u0012\u0010\u0014\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00010\u0015H\u0007\u001a\b\u0010\u0016\u001a\u00020\u0001H\u0007\u001a\u0018\u0010\u0017\u001a\u00020\u00062\u0006\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\u0006H\u0002\u001a\u0010\u0010\u0018\u001a\u00020\u00062\u0006\u0010\u0019\u001a\u00020\u001aH\u0002\u00a8\u0006\u001b"}, d2 = {"PredictionChip", "", "prediction", "Lcom/trackrat/android/data/models/PredictionData;", "StatusChip", "status", "", "isBoarding", "", "TrainCard", "train", "Lcom/trackrat/android/data/models/TrainV2;", "fromStation", "viewModel", "Lcom/trackrat/android/ui/trainlist/TrainListViewModel;", "onClick", "Lkotlin/Function0;", "TrainListScreen", "toStation", "onNavigateBack", "onTrainClicked", "Lkotlin/Function1;", "TrainListScreenPreview", "formatDepartureTime", "formatLastUpdated", "timestamp", "", "app_debug"})
public final class TrainListScreenKt {
    
    @kotlin.OptIn(markerClass = {androidx.compose.material3.ExperimentalMaterial3Api.class})
    @androidx.compose.runtime.Composable()
    public static final void TrainListScreen(@org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.Nullable()
    java.lang.String toStation, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.trainlist.TrainListViewModel viewModel, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onNavigateBack, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> onTrainClicked) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void TrainCard(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.TrainV2 train, @org.jetbrains.annotations.NotNull()
    java.lang.String fromStation, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.trainlist.TrainListViewModel viewModel, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onClick) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void StatusChip(@org.jetbrains.annotations.NotNull()
    java.lang.String status, boolean isBoarding) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void PredictionChip(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.PredictionData prediction) {
    }
    
    private static final java.lang.String formatDepartureTime(com.trackrat.android.data.models.TrainV2 train, java.lang.String fromStation) {
        return null;
    }
    
    private static final java.lang.String formatLastUpdated(long timestamp) {
        return null;
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void TrainListScreenPreview() {
    }
}