package com.trackrat.android.ui.components

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Gesture mode state machine matching iOS implementation
 * Ensures "one swipe = one action" by determining intent at gesture start
 *
 * - IDLE: No gesture active
 * - SHEET_MOVING: Sheet expanding/collapsing, block scrolling
 * - SCROLLING: Content scrolling, block sheet movement
 */
enum class GestureMode {
    IDLE,
    SHEET_MOVING,
    SCROLLING
}

/**
 * Shared state coordination between DraggableBottomSheet and scroll content
 * Matches iOS BottomSheetDragState class behavior
 *
 * This class acts as a communication channel between the sheet container
 * and scrollable content, ensuring coordinated gesture handling.
 *
 * @property translation Current drag offset in pixels (real-time during gesture)
 * @property isDragging Whether a drag gesture is currently active
 * @property gestureMode Current gesture mode determining which component handles input
 */
@Stable
class BottomSheetDragState {
    /**
     * Current drag translation in pixels
     * Updated in real-time during drag gestures
     */
    var translation by mutableFloatStateOf(0f)

    /**
     * Whether a drag gesture is currently active
     * Used to disable animations during interaction
     */
    var isDragging by mutableStateOf(false)

    /**
     * Current gesture mode determining input routing
     * Set at gesture start based on context (position, scroll state, direction)
     */
    var gestureMode by mutableStateOf(GestureMode.IDLE)

    /**
     * Update drag translation during gesture
     * Called by the active gesture handler
     */
    fun updateTranslation(delta: Float) {
        translation += delta
    }

    /**
     * Reset all state to initial values
     * Called on gesture end or cancellation
     */
    fun reset() {
        translation = 0f
        isDragging = false
        gestureMode = GestureMode.IDLE
    }
}

/**
 * Determine which gesture mode to use based on current context
 * Matches iOS determineGestureMode logic
 *
 * Decision logic:
 * - From MEDIUM + swipe up → expand sheet (SHEET_MOVING)
 * - From EXPANDED + at top + swipe down → collapse sheet (SHEET_MOVING)
 * - From EXPANDED + mid-scroll + swipe down → scroll content (SCROLLING)
 * - From EXPANDED + swipe up → scroll content (SCROLLING)
 *
 * @param sheetPosition Current sheet position
 * @param isAtTop Whether scrollable content is at top
 * @param dragDeltaY Vertical drag delta (negative = up, positive = down)
 * @return The appropriate gesture mode for this context
 */
fun determineGestureMode(
    sheetPosition: BottomSheetPosition,
    isAtTop: Boolean,
    dragDeltaY: Float
): GestureMode {
    return when {
        // Swipe up from medium → expand sheet
        sheetPosition == BottomSheetPosition.MEDIUM && dragDeltaY < 0 -> {
            GestureMode.SHEET_MOVING
        }

        // Swipe down from expanded at top → collapse sheet
        sheetPosition == BottomSheetPosition.EXPANDED && dragDeltaY > 0 && isAtTop -> {
            GestureMode.SHEET_MOVING
        }

        // Swipe down from expanded mid-scroll → scroll content up
        sheetPosition == BottomSheetPosition.EXPANDED && dragDeltaY > 0 && !isAtTop -> {
            GestureMode.SCROLLING
        }

        // Swipe up from expanded → scroll content down
        sheetPosition == BottomSheetPosition.EXPANDED && dragDeltaY < 0 -> {
            GestureMode.SCROLLING
        }

        // No action
        else -> GestureMode.IDLE
    }
}
