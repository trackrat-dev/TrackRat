package com.trackrat.android.utils

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Helper class for providing consistent haptic feedback throughout the app
 * All methods respect user preferences for haptic feedback
 */
object HapticFeedbackHelper {
    
    /**
     * Provide light haptic feedback for UI interactions
     * @param hapticFeedback The compose haptic feedback instance
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    fun performLightHaptic(hapticFeedback: HapticFeedback, enabled: Boolean = true) {
        if (enabled) {
            hapticFeedback.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        }
    }
    
    /**
     * Provide medium haptic feedback for button presses and selections
     * @param hapticFeedback The compose haptic feedback instance
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    fun performMediumHaptic(hapticFeedback: HapticFeedback, enabled: Boolean = true) {
        if (enabled) {
            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
        }
    }
    
    /**
     * Provide strong haptic feedback for error states or important actions
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    suspend fun performErrorHaptic(context: Context, enabled: Boolean = true) {
        if (!enabled) return
        withContext(Dispatchers.Main) {
            val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            vibrator?.let {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    val effect = VibrationEffect.createOneShot(
                        Constants.HAPTIC_FEEDBACK_DURATION_MS, 
                        VibrationEffect.DEFAULT_AMPLITUDE
                    )
                    it.vibrate(effect)
                } else {
                    @Suppress("DEPRECATION")
                    it.vibrate(Constants.HAPTIC_FEEDBACK_DURATION_MS)
                }
            }
        }
    }
    
    /**
     * Provide success haptic feedback for positive actions
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    suspend fun performSuccessHaptic(context: Context, enabled: Boolean = true) {
        if (!enabled) return
        withContext(Dispatchers.Main) {
            val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            vibrator?.let {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    val effect = VibrationEffect.createOneShot(
                        25L, // Shorter duration for success
                        VibrationEffect.DEFAULT_AMPLITUDE
                    )
                    it.vibrate(effect)
                } else {
                    @Suppress("DEPRECATION")
                    it.vibrate(25L)
                }
            }
        }
    }
    
    /**
     * Provide haptic feedback for pull-to-refresh completion
     * @param context Android context
     * @param enabled Whether haptic feedback is enabled (from user preferences)
     */
    suspend fun performRefreshHaptic(context: Context, enabled: Boolean = true) {
        if (!enabled) return
        withContext(Dispatchers.Main) {
            val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            vibrator?.let {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    // Double pulse for refresh
                    val timings = longArrayOf(0, 30, 20, 30)
                    val amplitudes = intArrayOf(0, VibrationEffect.DEFAULT_AMPLITUDE, 0, VibrationEffect.DEFAULT_AMPLITUDE)
                    val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
                    it.vibrate(effect)
                } else {
                    @Suppress("DEPRECATION")
                    it.vibrate(longArrayOf(0, 30, 20, 30), -1)
                }
            }
        }
    }
}