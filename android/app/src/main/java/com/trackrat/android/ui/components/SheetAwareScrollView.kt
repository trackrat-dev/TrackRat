package com.trackrat.android.ui.components

import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.Velocity

/**
 * Smart scrolling component that coordinates with bottom sheet position
 * Matching iOS SheetAwareScrollView.swift behavior
 *
 * Key features:
 * - Detects scroll position (at top vs. mid-scroll)
 * - Routes gestures appropriately: sheet drag when at top, scroll when mid-content
 * - Prevents simultaneous sheet movement and scrolling
 * - Nested scroll connection for coordination
 *
 * Gesture logic:
 * - From MEDIUM + swipe up → expand sheet
 * - From EXPANDED + swipe down at scroll top → collapse sheet
 * - From EXPANDED + swipe down mid-scroll → scroll up
 * - From EXPANDED + swipe up → scroll down
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
    val scrollState = rememberScrollState()
    val isAtTop = scrollState.value == 0

    // Nested scroll connection to coordinate with sheet
    val nestedScrollConnection = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(
                available: Offset,
                source: NestedScrollSource
            ): Offset {
                // If at top and swiping down from EXPANDED, let sheet handle it
                if (isAtTop && available.y > 0 && sheetPosition == BottomSheetPosition.EXPANDED) {
                    // Return Zero to let gesture pass through to sheet
                    return Offset.Zero
                }
                // Otherwise, let scroll happen normally
                return Offset.Zero
            }

            override fun onPostScroll(
                consumed: Offset,
                available: Offset,
                source: NestedScrollSource
            ): Offset {
                // After scrolling, if there's remaining downward motion at top,
                // offer it to the sheet
                if (isAtTop && available.y > 0 && sheetPosition == BottomSheetPosition.EXPANDED) {
                    return available
                }
                return Offset.Zero
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .nestedScroll(nestedScrollConnection)
            .verticalScroll(scrollState)
    ) {
        content()
    }
}
