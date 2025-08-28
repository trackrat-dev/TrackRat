package com.trackrat.android.ui.traindetail;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material3.*;
import androidx.compose.runtime.*;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextOverflow;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.data.models.Stop;
import com.trackrat.android.data.models.TrainV2;
import com.trackrat.android.ui.trainlist.Tuple4;
import java.time.format.DateTimeFormatter;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000J\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\t\n\u0000\u001a\u0010\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\u0010\u0010\u0004\u001a\u00020\u00012\u0006\u0010\u0005\u001a\u00020\u0006H\u0007\u001a\u0018\u0010\u0007\u001a\u00020\u00012\u0006\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u000bH\u0007\u001a$\u0010\f\u001a\u00020\u00012\u0006\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u000b2\b\b\u0002\u0010\u0010\u001a\u00020\u000bH\u0007\u001a4\u0010\u0011\u001a\u00020\u00012\u0006\u0010\u0012\u001a\u00020\t2\n\b\u0002\u0010\u0013\u001a\u0004\u0018\u00010\t2\b\b\u0002\u0010\u0014\u001a\u00020\u00152\f\u0010\u0016\u001a\b\u0012\u0004\u0012\u00020\u00010\u0017H\u0007\u001a\b\u0010\u0018\u001a\u00020\u0001H\u0007\u001a\u0018\u0010\u0019\u001a\u00020\u00012\u0006\u0010\u001a\u001a\u00020\u001b2\u0006\u0010\u0014\u001a\u00020\u0015H\u0007\u001a\u0010\u0010\u001c\u001a\u00020\t2\u0006\u0010\u001d\u001a\u00020\u001eH\u0002\u00a8\u0006\u001f"}, d2 = {"PredictionChipDetailed", "", "prediction", "Lcom/trackrat/android/data/models/PredictionData;", "ProgressCard", "progress", "Lcom/trackrat/android/data/models/Progress;", "StatusChip", "status", "", "isBoarding", "", "StopCard", "stop", "Lcom/trackrat/android/data/models/Stop;", "isOrigin", "isTerminal", "TrainDetailScreen", "trainId", "date", "viewModel", "Lcom/trackrat/android/ui/traindetail/TrainDetailViewModel;", "onNavigateBack", "Lkotlin/Function0;", "TrainDetailScreenPreview", "TrainHeaderCard", "train", "Lcom/trackrat/android/data/models/TrainV2;", "formatLastUpdated", "timestamp", "", "app_debug"})
public final class TrainDetailScreenKt {
    
    @kotlin.OptIn(markerClass = {androidx.compose.material3.ExperimentalMaterial3Api.class})
    @androidx.compose.runtime.Composable()
    public static final void TrainDetailScreen(@org.jetbrains.annotations.NotNull()
    java.lang.String trainId, @org.jetbrains.annotations.Nullable()
    java.lang.String date, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.traindetail.TrainDetailViewModel viewModel, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onNavigateBack) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void TrainHeaderCard(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.TrainV2 train, @org.jetbrains.annotations.NotNull()
    com.trackrat.android.ui.traindetail.TrainDetailViewModel viewModel) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void ProgressCard(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.Progress progress) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void StopCard(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.Stop stop, boolean isOrigin, boolean isTerminal) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void StatusChip(@org.jetbrains.annotations.NotNull()
    java.lang.String status, boolean isBoarding) {
    }
    
    @androidx.compose.runtime.Composable()
    public static final void PredictionChipDetailed(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.PredictionData prediction) {
    }
    
    private static final java.lang.String formatLastUpdated(long timestamp) {
        return null;
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void TrainDetailScreenPreview() {
    }
}