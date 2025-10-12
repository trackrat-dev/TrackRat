package com.trackrat.android.ui.components

import androidx.compose.animation.core.AnimationSpec
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlin.math.abs
import kotlin.math.roundToInt

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
 *
 * @param position Current sheet position
 * @param onPositionChange Callback when position changes
 * @param content Composable content to display in sheet
 */
@Composable
fun DraggableBottomSheet(
    position: BottomSheetPosition,
    onPositionChange: (BottomSheetPosition) -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current

    val screenHeightPx = with(density) { configuration.screenHeightDp.dp.toPx() }

    // Calculate target offset based on position
    val targetOffset = when (position) {
        BottomSheetPosition.MEDIUM -> screenHeightPx * 0.5f
        BottomSheetPosition.EXPANDED -> 0f
    }

    // Animated offset with spring animation (matching iOS interactiveSpring)
    val animatedOffset by animateFloatAsState(
        targetValue = targetOffset,
        animationSpec = spring(
            dampingRatio = 0.8f,  // iOS uses 0.95, Android needs slightly less for similar feel
            stiffness = 400f
        ),
        label = "sheet_offset"
    )

    // Track drag state
    var dragOffset by remember { mutableStateOf(0f) }
    var isDragging by remember { mutableStateOf(false) }

    // Calculate combined offset (animation + drag)
    val currentOffset = if (isDragging) {
        (animatedOffset + dragOffset).coerceIn(0f, screenHeightPx * 0.5f)
    } else {
        animatedOffset
    }

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
                // Drag indicator
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
                    onDrag = { delta ->
                        isDragging = true
                        dragOffset = (dragOffset + delta).coerceIn(-screenHeightPx * 0.5f, 0f)
                    },
                    onDragEnd = { velocity ->
                        isDragging = false

                        // Determine new position based on velocity and distance
                        // iOS thresholds: ±50 for velocity, ±50 for translation
                        val newPosition = when {
                            // Strong swipe up
                            velocity < -50 -> BottomSheetPosition.EXPANDED
                            // Strong swipe down
                            velocity > 50 -> BottomSheetPosition.MEDIUM
                            // Based on distance dragged
                            dragOffset < -screenHeightPx * 0.25f -> BottomSheetPosition.EXPANDED
                            dragOffset > 0 -> BottomSheetPosition.MEDIUM
                            // Default: stay at current position
                            else -> position
                        }

                        if (newPosition != position) {
                            onPositionChange(newPosition)
                            triggerHapticFeedback(view)
                        }

                        dragOffset = 0f
                    }
                )

                // Content
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .weight(1f)
                ) {
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

/**
 * Drag indicator component at top of sheet
 * 44dp hit area for easy grabbing (iOS standard)
 */
@Composable
private fun DragIndicator(
    onTap: () -> Unit,
    onDrag: (Float) -> Unit,
    onDragEnd: (Float) -> Unit,
    modifier: Modifier = Modifier
) {
    var dragVelocity by remember { mutableStateOf(0f) }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(44.dp) // iOS standard tap target
            .pointerInput(Unit) {
                detectDragGestures(
                    onDragStart = {
                        dragVelocity = 0f
                    },
                    onDrag = { change, dragAmount ->
                        change.consume()
                        onDrag(dragAmount.y)
                        dragVelocity = dragAmount.y
                    },
                    onDragEnd = {
                        onDragEnd(dragVelocity)
                    },
                    onDragCancel = {
                        onDragEnd(0f)
                    }
                )
            },
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
