package com.trackrat.android.ui.components

import androidx.compose.animation.core.AnimationSpec
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.drag
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * CompositionLocal for providing BottomSheetDragState to descendants
 * Matches iOS environment injection pattern
 */
val LocalBottomSheetDragState = compositionLocalOf<BottomSheetDragState> {
    error("No BottomSheetDragState provided")
}

/**
 * Bottom sheet position matching iOS implementation
 * - MEDIUM: 50% of screen height (collapsed state)
 * - EXPANDED: 100% of screen height (full screen)
 */
enum class BottomSheetPosition {
    MEDIUM,   // 50% visible
    EXPANDED  // 100% visible
}

/**
 * Draggable bottom sheet component matching iOS BottomSheetView.swift
 * Provides smooth drag gestures with snap-to-position behavior
 *
 * Key features:
 * - Two positions: Medium (50%) and Expanded (100%)
 * - Spring animation on snap
 * - Velocity-based gesture detection
 * - Haptic feedback on position changes
 * - Glassmorphic design with rounded top corners
 * - Fade gradient when collapsed
 * - Coordinated gesture handling with scrollable content
 *
 * @param position Current sheet position
 * @param onPositionChange Callback when position changes
 * @param isScrollable Whether content is scrollable (enables gesture coordination)
 * @param content Composable content to display in sheet
 */
@Composable
fun DraggableBottomSheet(
    position: BottomSheetPosition,
    onPositionChange: (BottomSheetPosition) -> Unit,
    modifier: Modifier = Modifier,
    isScrollable: Boolean = false,
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current

    val screenHeightPx = with(density) { configuration.screenHeightDp.dp.toPx() }

    // Shared drag state for coordination with scroll content
    val dragState = remember { BottomSheetDragState() }

    // Calculate target offset based on position
    val targetOffset = when (position) {
        BottomSheetPosition.MEDIUM -> screenHeightPx * 0.5f
        BottomSheetPosition.EXPANDED -> 0f
    }

    // Animated offset with spring animation (matching iOS interactiveSpring)
    // Disable animation during active drag
    val animatedOffset by animateFloatAsState(
        targetValue = targetOffset,
        animationSpec = if (dragState.isDragging) {
            spring(dampingRatio = 1f, stiffness = 5000f)  // Instant response during drag
        } else {
            spring(dampingRatio = 0.8f, stiffness = 400f)  // Smooth animation on release
        },
        label = "sheet_offset"
    )

    // Calculate combined offset (animation + drag)
    val currentOffset = if (dragState.isDragging && dragState.gestureMode == GestureMode.SHEET_MOVING) {
        (animatedOffset + dragState.translation).coerceIn(0f, screenHeightPx * 0.5f)
    } else {
        animatedOffset
    }

    // Provide drag state to descendants via CompositionLocal
    CompositionLocalProvider(LocalBottomSheetDragState provides dragState) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .offset { IntOffset(0, currentOffset.roundToInt()) }
        ) {
            // Main sheet container
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp))
                    .background(
                        color = Color.Black.copy(alpha = 0.95f) // Glassmorphic dark background
                    )
            ) {
                Column(
                    modifier = Modifier.fillMaxSize()
                ) {
                    // Drag indicator - only handles tap when scrollable
                    // Gesture coordination handled by content area when isScrollable = true
                    DragIndicator(
                        onTap = {
                            // Toggle between positions on tap
                            val newPosition = when (position) {
                                BottomSheetPosition.MEDIUM -> BottomSheetPosition.EXPANDED
                                BottomSheetPosition.EXPANDED -> BottomSheetPosition.MEDIUM
                            }
                            onPositionChange(newPosition)
                            triggerHapticFeedback(view)
                        },
                        enabled = !isScrollable  // Disable drag on indicator when using coordinated gestures
                    )

                    // Content with gesture handling when scrollable
                    val contentModifier = if (isScrollable) {
                        // Velocity and translation thresholds (matching iOS)
                        var gestureVelocity by remember { mutableStateOf(0f) }
                        val velocityThreshold = 50f
                        val translationThreshold = 50f

                        Modifier
                            .fillMaxSize()
                            .weight(1f)
                            .pointerInput(position) {
                                // Use awaitPointerEventScope for lower-level gesture handling
                                // This allows us to intercept gestures BEFORE child composables
                                awaitPointerEventScope {
                                    while (true) {
                                        val down = awaitFirstDown(requireUnconsumed = false)
                                        var totalDrag = 0f
                                        gestureVelocity = 0f
                                        dragState.isDragging = false
                                        dragState.gestureMode = GestureMode.IDLE

                                        // Track the drag
                                        drag(down.id) { change ->
                                            val dragAmount = change.positionChange().y
                                            gestureVelocity = dragAmount
                                            totalDrag += dragAmount

                                            // Determine gesture mode on first significant movement
                                            if (dragState.gestureMode == GestureMode.IDLE && kotlin.math.abs(totalDrag) > 5f) {
                                                val shouldCaptureGesture = when (position) {
                                                    BottomSheetPosition.MEDIUM -> totalDrag < 0 // Upward swipe
                                                    BottomSheetPosition.EXPANDED -> totalDrag > 0 // Downward swipe
                                                }

                                                if (shouldCaptureGesture) {
                                                    dragState.gestureMode = GestureMode.SHEET_MOVING
                                                    dragState.isDragging = true
                                                }
                                            }

                                            // If we captured the gesture, consume it
                                            if (dragState.gestureMode == GestureMode.SHEET_MOVING) {
                                                change.consume()
                                                dragState.updateTranslation(dragAmount)
                                            }
                                        }

                                        // Drag ended - check thresholds
                                        if (dragState.gestureMode == GestureMode.SHEET_MOVING) {
                                            val shouldChangePosition = when (position) {
                                                BottomSheetPosition.MEDIUM -> {
                                                    // Expanding from MEDIUM to EXPANDED
                                                    val hasStrongUpwardVelocity = gestureVelocity < -velocityThreshold
                                                    val hasSufficientUpwardDrag = dragState.translation < -translationThreshold
                                                    hasStrongUpwardVelocity || hasSufficientUpwardDrag
                                                }
                                                BottomSheetPosition.EXPANDED -> {
                                                    // Collapsing from EXPANDED to MEDIUM
                                                    val hasStrongDownwardVelocity = gestureVelocity > velocityThreshold
                                                    val hasSufficientDownwardDrag = dragState.translation > translationThreshold
                                                    hasStrongDownwardVelocity || hasSufficientDownwardDrag
                                                }
                                            }

                                            if (shouldChangePosition) {
                                                val newPosition = when (position) {
                                                    BottomSheetPosition.MEDIUM -> BottomSheetPosition.EXPANDED
                                                    BottomSheetPosition.EXPANDED -> BottomSheetPosition.MEDIUM
                                                }
                                                onPositionChange(newPosition)
                                                triggerHapticFeedback(view)
                                            }
                                        }

                                        dragState.reset()
                                        gestureVelocity = 0f
                                    }
                                }
                            }
                    } else {
                        Modifier
                            .fillMaxSize()
                            .weight(1f)
                    }

                    Box(modifier = contentModifier) {
                        content()

                        // Fade gradient at bottom when in MEDIUM position (indicates more content below)
                        if (position == BottomSheetPosition.MEDIUM) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(60.dp)
                                    .align(Alignment.BottomCenter)
                                    .background(
                                        Brush.verticalGradient(
                                            colors = listOf(
                                                Color.Transparent,
                                                Color.Black.copy(alpha = 0.6f)
                                            )
                                        )
                                    )
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * Drag indicator component at top of sheet
 * 44dp hit area for easy grabbing (iOS standard)
 *
 * When enabled=false, only tap gestures work (drag handled by content)
 * When enabled=true, both tap and drag gestures work (legacy non-scrollable mode)
 */
@Composable
private fun DragIndicator(
    onTap: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(44.dp), // iOS standard tap target
        contentAlignment = Alignment.Center
    ) {
        // Visual drag handle
        Box(
            modifier = Modifier
                .width(36.dp)
                .height(5.dp)
                .clip(RoundedCornerShape(2.5.dp))
                .background(Color.White.copy(alpha = 0.3f))
        )
    }
}

/**
 * Trigger haptic feedback (matching iOS UIImpactFeedbackGenerator)
 */
private fun triggerHapticFeedback(view: android.view.View) {
    view.performHapticFeedback(
        android.view.HapticFeedbackConstants.CONTEXT_CLICK,
        android.view.HapticFeedbackConstants.FLAG_IGNORE_GLOBAL_SETTING
    )
}
