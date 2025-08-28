package com.trackrat.android.utils;

import android.content.Context;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import androidx.compose.ui.hapticfeedback.HapticFeedback;
import androidx.compose.ui.hapticfeedback.HapticFeedbackType;
import kotlinx.coroutines.Dispatchers;

/**
 * Helper class for providing consistent haptic feedback throughout the app
 * All methods respect user preferences for haptic feedback
 */
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0004\b\u00c6\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002\u00a2\u0006\u0002\u0010\u0002J \u0010\u0003\u001a\u00020\u00042\u0006\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\bH\u0086@\u00a2\u0006\u0002\u0010\tJ\u0018\u0010\n\u001a\u00020\u00042\u0006\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\u0007\u001a\u00020\bJ\u0018\u0010\r\u001a\u00020\u00042\u0006\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\u0007\u001a\u00020\bJ \u0010\u000e\u001a\u00020\u00042\u0006\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\bH\u0086@\u00a2\u0006\u0002\u0010\tJ \u0010\u000f\u001a\u00020\u00042\u0006\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\bH\u0086@\u00a2\u0006\u0002\u0010\t\u00a8\u0006\u0010"}, d2 = {"Lcom/trackrat/android/utils/HapticFeedbackHelper;", "", "()V", "performErrorHaptic", "", "context", "Landroid/content/Context;", "enabled", "", "(Landroid/content/Context;ZLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "performLightHaptic", "hapticFeedback", "Landroidx/compose/ui/hapticfeedback/HapticFeedback;", "performMediumHaptic", "performRefreshHaptic", "performSuccessHaptic", "app_release"})
public final class HapticFeedbackHelper {
    @org.jetbrains.annotations.NotNull()
    public static final com.trackrat.android.utils.HapticFeedbackHelper INSTANCE = null;
    
    private HapticFeedbackHelper() {
        super();
    }
    
    /**
     * Provide light haptic feedback for UI interactions
     * @param hapticFeedback The compose haptic feedback instance
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    public final void performLightHaptic(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.hapticfeedback.HapticFeedback hapticFeedback, boolean enabled) {
    }
    
    /**
     * Provide medium haptic feedback for button presses and selections
     * @param hapticFeedback The compose haptic feedback instance
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    public final void performMediumHaptic(@org.jetbrains.annotations.NotNull()
    androidx.compose.ui.hapticfeedback.HapticFeedback hapticFeedback, boolean enabled) {
    }
    
    /**
     * Provide strong haptic feedback for error states or important actions
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object performErrorHaptic(@org.jetbrains.annotations.NotNull()
    android.content.Context context, boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Provide success haptic feedback for positive actions
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object performSuccessHaptic(@org.jetbrains.annotations.NotNull()
    android.content.Context context, boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
    
    /**
     * Provide haptic feedback for pull-to-refresh completion
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    @org.jetbrains.annotations.Nullable()
    public final java.lang.Object performRefreshHaptic(@org.jetbrains.annotations.NotNull()
    android.content.Context context, boolean enabled, @org.jetbrains.annotations.NotNull()
    kotlin.coroutines.Continuation<? super kotlin.Unit> $completion) {
        return null;
    }
}