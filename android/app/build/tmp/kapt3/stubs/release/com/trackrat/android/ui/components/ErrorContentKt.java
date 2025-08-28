package com.trackrat.android.ui.components;

import androidx.compose.foundation.layout.*;
import androidx.compose.material.icons.Icons;
import androidx.compose.material3.*;
import androidx.compose.runtime.Composable;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.vector.ImageVector;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.data.models.ApiException;
import com.trackrat.android.utils.Constants;
import com.trackrat.android.utils.HapticFeedbackHelper;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000\"\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\u001a>\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\u000e\b\u0002\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u0005H\u0007\u001a\b\u0010\u000b\u001a\u00020\u0001H\u0007\u00a8\u0006\f"}, d2 = {"ErrorContent", "", "error", "Lcom/trackrat/android/data/models/ApiException;", "canRetry", "", "onRetryClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "hapticFeedbackEnabled", "ErrorContentPreview", "app_release"})
public final class ErrorContentKt {
    
    /**
     * Reusable error display component with retry functionality
     * Provides consistent error handling across all screens
     */
    @androidx.compose.runtime.Composable()
    public static final void ErrorContent(@org.jetbrains.annotations.NotNull()
    com.trackrat.android.data.models.ApiException error, boolean canRetry, @org.jetbrains.annotations.NotNull()
    kotlin.jvm.functions.Function0<kotlin.Unit> onRetryClick, @org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier, boolean hapticFeedbackEnabled) {
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void ErrorContentPreview() {
    }
}