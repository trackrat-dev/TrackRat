package com.trackrat.android.ui.components;

import androidx.compose.animation.core.*;
import androidx.compose.foundation.layout.*;
import androidx.compose.material3.CardDefaults;
import androidx.compose.runtime.Composable;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Brush;
import androidx.compose.ui.tooling.preview.Preview;
import com.trackrat.android.utils.Constants;

@kotlin.Metadata(mv = {1, 9, 0}, k = 2, xi = 48, d1 = {"\u0000\u001c\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0007\n\u0002\u0018\u0002\n\u0000\u001a\u001c\u0010\u0000\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u0005H\u0003\u001a\u0012\u0010\u0006\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\b\u0010\u0007\u001a\u00020\u0001H\u0007\u001a\u0012\u0010\b\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\b\u0010\t\u001a\u00020\u0001H\u0007\u001a\u0012\u0010\n\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\u0012\u0010\u000b\u001a\u00020\u00012\b\b\u0002\u0010\u0002\u001a\u00020\u0003H\u0007\u001a\b\u0010\f\u001a\u00020\rH\u0003\u00a8\u0006\u000e"}, d2 = {"ShimmerBox", "", "modifier", "Landroidx/compose/ui/Modifier;", "cornerRadius", "", "TrainCardSkeleton", "TrainCardSkeletonPreview", "TrainDetailSkeleton", "TrainDetailSkeletonPreview", "TrainListSkeleton", "TrainStopSkeleton", "shimmerBrush", "Landroidx/compose/ui/graphics/Brush;", "app_release"})
public final class LoadingSkeletonsKt {
    
    /**
     * Shimmer animation effect for loading states
     */
    @androidx.compose.runtime.Composable()
    private static final androidx.compose.ui.graphics.Brush shimmerBrush() {
        return null;
    }
    
    /**
     * Generic shimmer box component
     */
    @androidx.compose.runtime.Composable()
    private static final void ShimmerBox(androidx.compose.ui.Modifier modifier, int cornerRadius) {
    }
    
    /**
     * Train card loading skeleton
     */
    @androidx.compose.runtime.Composable()
    public static final void TrainCardSkeleton(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier) {
    }
    
    /**
     * Train list loading skeleton
     */
    @androidx.compose.runtime.Composable()
    public static final void TrainListSkeleton(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier) {
    }
    
    /**
     * Train detail stop skeleton
     */
    @androidx.compose.runtime.Composable()
    public static final void TrainStopSkeleton(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier) {
    }
    
    /**
     * Train detail loading skeleton
     */
    @androidx.compose.runtime.Composable()
    public static final void TrainDetailSkeleton(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.Modifier modifier) {
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void TrainCardSkeletonPreview() {
    }
    
    @androidx.compose.ui.tooling.preview.Preview(showBackground = true)
    @androidx.compose.runtime.Composable()
    public static final void TrainDetailSkeletonPreview() {
    }
}