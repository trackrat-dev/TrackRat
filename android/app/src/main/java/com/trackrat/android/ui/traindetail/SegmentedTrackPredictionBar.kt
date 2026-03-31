package com.trackrat.android.ui.traindetail

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

/**
 * Segmented bar view showing track prediction probabilities
 * Matches iOS SegmentedTrackPredictionView visual design
 */
@Composable
fun SegmentedTrackPredictionBar(
    platformPredictions: Map<String, Double>,
    isLoading: Boolean,
    modifier: Modifier = Modifier
) {
    // Sort platforms by number (extract first number from platform name)
    val sortedPlatforms = platformPredictions.entries.sortedBy { entry ->
        entry.key.split("&").first().trim().toIntOrNull() ?: 999
    }

    // Check if all predictions are low confidence (< 17%)
    val hasOnlyLowConfidence = sortedPlatforms.all { it.value < 0.17 }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Color(0xFFFFB84D).copy(alpha = 0.05f))
            .border(1.dp, Color(0xFFFFB84D).copy(alpha = 0.5f), RoundedCornerShape(12.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Header
        Text(
            text = "Track Predictions",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = Color(0xFFFFB84D)
        )

        when {
            isLoading -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(32.dp),
                        color = Color(0xFFFFB84D)
                    )
                }
            }

            hasOnlyLowConfidence && sortedPlatforms.isNotEmpty() -> {
                // Show "No clear favorite" but ONLY if we have predictions
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No clear favorite",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            sortedPlatforms.isNotEmpty() -> {
                // Show segmented bar for ANY predictions (even low confidence ones)
                Column(
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Main segmented bar
                    SegmentedBar(
                        platforms = sortedPlatforms,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(64.dp)
                    )

                    // Percentages below
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        sortedPlatforms.forEach { (platform, probability) ->
                            // Only show percentages for segments >= 15%
                            if (probability >= 0.15) {
                                Text(
                                    text = "${(probability * 100).toInt()}%",
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.Medium,
                                    color = Color.Black,
                                    modifier = Modifier.weight(probability.toFloat())
                                )
                            } else {
                                // Empty spacer for small segments
                                Spacer(modifier = Modifier.weight(probability.toFloat()))
                            }
                        }
                    }
                }
            }

            else -> {
                Text(
                    text = "No prediction data available",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray.copy(alpha = 0.7f),
                    fontStyle = androidx.compose.ui.text.font.FontStyle.Italic,
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

/**
 * Individual segment in the prediction bar
 */
@Composable
private fun SegmentedBar(
    platforms: List<Map.Entry<String, Double>>,
    modifier: Modifier = Modifier
) {
    var selectedPlatform by remember { mutableStateOf<String?>(null) }
    val haptic = LocalHapticFeedback.current

    // Auto-deselect after a delay
    LaunchedEffect(selectedPlatform) {
        if (selectedPlatform != null) {
            delay(300)
            selectedPlatform = null
        }
    }

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .border(1.dp, Color.Black, RoundedCornerShape(8.dp)),
        horizontalArrangement = Arrangement.Start
    ) {
        platforms.forEach { (platform, probability) ->
            PlatformSegment(
                platformName = platform,
                probability = probability,
                isSelected = platform == selectedPlatform,
                onSelect = {
                    haptic.performHapticFeedback(androidx.compose.ui.hapticfeedback.HapticFeedbackType.LongPress)
                    selectedPlatform = platform
                },
                modifier = Modifier.weight(probability.toFloat())
            )
        }
    }
}

/**
 * Individual platform segment
 */
@Composable
private fun PlatformSegment(
    platformName: String,
    probability: Double,
    isSelected: Boolean,
    onSelect: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scale by animateFloatAsState(
        targetValue = if (isSelected) 1.05f else 1f,
        animationSpec = tween(durationMillis = 200),
        label = "segment_scale"
    )

    Box(
        modifier = modifier
            .fillMaxHeight()
            .scale(scale)
            .background(Color(0xFFFFB84D).copy(alpha = 0.5f))
            .border(1.dp, Color.Black)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = onSelect
            ),
        contentAlignment = Alignment.Center
    ) {
        // Show label for segments >= 15%
        if (probability >= 0.15) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
                modifier = Modifier.padding(vertical = 8.dp)
            ) {
                Text(
                    text = "Tracks",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                    color = Color.Black,
                    textAlign = TextAlign.Center,
                    lineHeight = 12.sp
                )
                Text(
                    text = platformName,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                    color = Color.Black,
                    textAlign = TextAlign.Center,
                    lineHeight = 12.sp
                )
            }
        }

        // Show selection indicator
        if (isSelected) {
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .border(2.dp, Color.White, RoundedCornerShape(2.dp))
            )
        }
    }
}
