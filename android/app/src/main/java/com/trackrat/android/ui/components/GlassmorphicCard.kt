package com.trackrat.android.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.trackrat.android.ui.theme.TrackRatBorder
import com.trackrat.android.ui.theme.TrackRatSurfaceCard

/**
 * A glassmorphic card component matching iOS design aesthetic.
 * Provides semi-transparent white background with subtle border.
 */
@Composable
fun GlassmorphicCard(
    modifier: Modifier = Modifier,
    backgroundColor: Color = TrackRatSurfaceCard, // Default: white 10% opacity
    borderColor: Color = TrackRatBorder, // Default: white 30% opacity
    cornerRadius: Dp = 12.dp,
    padding: Dp = 16.dp,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(cornerRadius))
            .background(backgroundColor)
            .border(
                width = 1.dp,
                color = borderColor,
                shape = RoundedCornerShape(cornerRadius)
            )
            .padding(padding)
    ) {
        content()
    }
}

/**
 * Variant for elevated cards with slightly more opacity
 */
@Composable
fun GlassmorphicCardElevated(
    modifier: Modifier = Modifier,
    cornerRadius: Dp = 12.dp,
    padding: Dp = 16.dp,
    content: @Composable () -> Unit
) {
    GlassmorphicCard(
        modifier = modifier,
        backgroundColor = Color.White.copy(alpha = 0.15f), // Slightly more opaque
        borderColor = TrackRatBorder.copy(alpha = 0.6f), // Slightly more visible border
        cornerRadius = cornerRadius,
        padding = padding,
        content = content
    )
}

/**
 * Variant for search bars and input fields
 */
@Composable
fun GlassmorphicSearchCard(
    modifier: Modifier = Modifier,
    cornerRadius: Dp = 16.dp,
    padding: Dp = 12.dp,
    content: @Composable () -> Unit
) {
    GlassmorphicCard(
        modifier = modifier,
        backgroundColor = TrackRatSurfaceCard,
        borderColor = TrackRatBorder.copy(alpha = 0.3f),
        cornerRadius = cornerRadius,
        padding = padding,
        content = content
    )
}