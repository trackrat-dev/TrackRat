package com.trackrat.android.ui.components

import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalView
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * Smart scrolling component that coordinates with bottom sheet position
 * Matching iOS SheetAwareScrollView.swift behavior
 *
 * Key features:
 * - Detects scroll position (at top vs. mid-scroll)
 * - Routes gestures appropriately: sheet drag when at top, scroll when mid-content
 * - Prevents simultaneous sheet movement and scrolling via GestureMode state machine
 * - "One swipe = one action" - determines intent at gesture start
 *
 * Gesture logic (matching iOS):
 * - From MEDIUM + swipe up → expand sheet (SHEET_MOVING)
 * - From EXPANDED + at top + swipe down → collapse sheet (SHEET_MOVING)
 * - From EXPANDED + mid-scroll + swipe down → scroll up (SCROLLING)
 * - From EXPANDED + swipe up → scroll down (SCROLLING)
 *
 * @param sheetPosition Current sheet position
 * @param onSheetPositionChange Callback to change sheet position
 * @param content Scrollable content
 */
@Composable
fun SheetAwareScrollView(
    sheetPosition: BottomSheetPosition,
    onSheetPositionChange: (BottomSheetPosition) -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    val view = LocalView.current
    val scrollState = rememberScrollState()
    val dragState = LocalBottomSheetDragState.current

    // Track if scroll is at top (2px tolerance matching iOS)
    val isAtTop by remember {
        derivedStateOf {
            scrollState.value <= 2
        }
    }

    // Velocity and translation thresholds (matching iOS)
    val velocityThreshold = 50f
    val translationThreshold = 50f

    // Track gesture velocity for threshold detection
    var gestureVelocity by remember { mutableStateOf(0f) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(sheetPosition, isAtTop) {
                detectDragGestures(
                    onDragStart = {
                        // Reset state on new gesture
                        gestureVelocity = 0f
                        dragState.isDragging = false
                        dragState.gestureMode = GestureMode.IDLE
                    },
                    onDrag = { change, dragAmount ->
                        // Update velocity tracking
                        gestureVelocity = dragAmount.y

                        // Determine gesture mode on first movement (if still IDLE)
                        if (dragState.gestureMode == GestureMode.IDLE) {
                            val mode = determineGestureMode(
                                sheetPosition = sheetPosition,
                                isAtTop = isAtTop,
                                dragDeltaY = dragAmount.y
                            )
                            dragState.gestureMode = mode

                            if (mode == GestureMode.SHEET_MOVING) {
                                dragState.isDragging = true
                            }
                        }

                        // Handle based on current mode
                        when (dragState.gestureMode) {
                            GestureMode.SHEET_MOVING -> {
                                // Consume gesture and update sheet translation
                                change.consume()
                                dragState.updateTranslation(dragAmount.y)
                            }
                            GestureMode.SCROLLING -> {
                                // Let scroll handle it - don't consume
                                // ScrollState will handle the gesture naturally
                            }
                            GestureMode.IDLE -> {
                                // No action
                            }
                        }
                    },
                    onDragEnd = {
                        // Only change sheet position if we were in SHEET_MOVING mode
                        if (dragState.gestureMode == GestureMode.SHEET_MOVING) {
                            val shouldChangePosition = when (sheetPosition) {
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
                                val newPosition = when (sheetPosition) {
                                    BottomSheetPosition.MEDIUM -> BottomSheetPosition.EXPANDED
                                    BottomSheetPosition.EXPANDED -> BottomSheetPosition.MEDIUM
                                }
                                onSheetPositionChange(newPosition)

                                // Haptic feedback
                                view.performHapticFeedback(
                                    android.view.HapticFeedbackConstants.CONTEXT_CLICK,
                                    android.view.HapticFeedbackConstants.FLAG_IGNORE_GLOBAL_SETTING
                                )
                            }
                        }

                        // Reset state
                        dragState.reset()
                        gestureVelocity = 0f
                    },
                    onDragCancel = {
                        // Reset state on cancel
                        dragState.reset()
                        gestureVelocity = 0f
                    }
                )
            }
            .verticalScroll(
                state = scrollState,
                enabled = dragState.gestureMode != GestureMode.SHEET_MOVING
            )
    ) {
        content()
    }
}

/**
 * Smart lazy list component that coordinates with bottom sheet position
 * Matching iOS SheetAwareScrollView.swift behavior for LazyColumn
 *
 * Same gesture coordination logic as SheetAwareScrollView but optimized for LazyColumn
 * Uses LazyListState.firstVisibleItemIndex and scrollOffset for "at top" detection
 *
 * @param sheetPosition Current sheet position
 * @param onSheetPositionChange Callback to change sheet position
 * @param state LazyListState for scroll tracking
 * @param content LazyColumn content
 */
@Composable
fun SheetAwareLazyColumn(
    sheetPosition: BottomSheetPosition,
    onSheetPositionChange: (BottomSheetPosition) -> Unit,
    modifier: Modifier = Modifier,
    state: LazyListState = rememberLazyListState(),
    contentPadding: PaddingValues = PaddingValues(),
    content: LazyListScope.() -> Unit
) {
    val view = LocalView.current
    val dragState = LocalBottomSheetDragState.current
    val coroutineScope = rememberCoroutineScope()

    // Track if scroll is at top (2px tolerance matching iOS)
    val isAtTop by remember {
        derivedStateOf {
            state.firstVisibleItemIndex == 0 && state.firstVisibleItemScrollOffset <= 2
        }
    }

    // Velocity and translation thresholds (matching iOS)
    val velocityThreshold = 50f
    val translationThreshold = 50f

    // Track gesture velocity and accumulated scroll for threshold detection
    var gestureVelocity by remember { mutableStateOf(0f) }
    var accumulatedScroll by remember { mutableStateOf(0f) }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(sheetPosition, isAtTop) {
                detectDragGestures(
                    onDragStart = {
                        // Reset state on new gesture
                        gestureVelocity = 0f
                        accumulatedScroll = 0f
                        dragState.isDragging = false
                        dragState.gestureMode = GestureMode.IDLE
                    },
                    onDrag = { change, dragAmount ->
                        // Update velocity tracking
                        gestureVelocity = dragAmount.y

                        // Determine gesture mode on first movement (if still IDLE)
                        if (dragState.gestureMode == GestureMode.IDLE) {
                            val mode = determineGestureMode(
                                sheetPosition = sheetPosition,
                                isAtTop = isAtTop,
                                dragDeltaY = dragAmount.y
                            )
                            dragState.gestureMode = mode

                            if (mode == GestureMode.SHEET_MOVING) {
                                dragState.isDragging = true
                            }
                        }

                        // Handle based on current mode
                        when (dragState.gestureMode) {
                            GestureMode.SHEET_MOVING -> {
                                // Consume gesture and update sheet translation
                                change.consume()
                                dragState.updateTranslation(dragAmount.y)
                            }
                            GestureMode.SCROLLING -> {
                                // Manually scroll the LazyColumn
                                // LazyColumn doesn't automatically handle consumed gestures
                                change.consume()
                                accumulatedScroll += dragAmount.y
                                coroutineScope.launch {
                                    // Negative because drag down = scroll up
                                    state.scrollBy(-dragAmount.y)
                                }
                            }
                            GestureMode.IDLE -> {
                                // No action
                            }
                        }
                    },
                    onDragEnd = {
                        // Only change sheet position if we were in SHEET_MOVING mode
                        if (dragState.gestureMode == GestureMode.SHEET_MOVING) {
                            val shouldChangePosition = when (sheetPosition) {
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
                                val newPosition = when (sheetPosition) {
                                    BottomSheetPosition.MEDIUM -> BottomSheetPosition.EXPANDED
                                    BottomSheetPosition.EXPANDED -> BottomSheetPosition.MEDIUM
                                }
                                onSheetPositionChange(newPosition)

                                // Haptic feedback
                                view.performHapticFeedback(
                                    android.view.HapticFeedbackConstants.CONTEXT_CLICK,
                                    android.view.HapticFeedbackConstants.FLAG_IGNORE_GLOBAL_SETTING
                                )
                            }
                        }

                        // Reset state
                        dragState.reset()
                        gestureVelocity = 0f
                        accumulatedScroll = 0f
                    },
                    onDragCancel = {
                        // Reset state on cancel
                        dragState.reset()
                        gestureVelocity = 0f
                        accumulatedScroll = 0f
                    }
                )
            },
        state = state,
        contentPadding = contentPadding,
        userScrollEnabled = dragState.gestureMode != GestureMode.SHEET_MOVING
    ) {
        content()
    }
}

