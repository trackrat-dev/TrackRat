package com.trackrat.android.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.utils.Constants
import com.trackrat.android.utils.HapticFeedbackHelper
import kotlinx.coroutines.launch

/**
 * Reusable error display component with retry functionality
 * Provides consistent error handling across all screens
 */
@Composable
fun ErrorContent(
    error: ApiException,
    canRetry: Boolean = true,
    onRetryClick: () -> Unit = {},
    modifier: Modifier = Modifier,
    hapticFeedbackEnabled: Boolean = true
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    
    // Provide error haptic feedback when error is displayed
    LaunchedEffect(error) {
        HapticFeedbackHelper.performErrorHaptic(context, hapticFeedbackEnabled)
    }
    
    val (icon, iconTint, title, subtitle) = when (error) {
        is ApiException.NetworkError -> {
            ErrorInfo(
                icon = Icons.Default.CloudOff,
                iconTint = MaterialTheme.colorScheme.error,
                title = "No Connection",
                subtitle = error.message
            )
        }
        is ApiException.ServerError -> {
            ErrorInfo(
                icon = Icons.Default.Error,
                iconTint = MaterialTheme.colorScheme.error,
                title = "Server Error",
                subtitle = error.message
            )
        }
        is ApiException.TimeoutError -> {
            ErrorInfo(
                icon = Icons.Default.Warning,
                iconTint = MaterialTheme.colorScheme.error,
                title = "Request Timed Out",
                subtitle = error.message
            )
        }
        is ApiException.ClientError -> {
            ErrorInfo(
                icon = Icons.Default.Warning,
                iconTint = MaterialTheme.colorScheme.error,
                title = "Request Failed",
                subtitle = error.message
            )
        }
        is ApiException.ParseError -> {
            ErrorInfo(
                icon = Icons.Default.Error,
                iconTint = MaterialTheme.colorScheme.error,
                title = "Data Error",
                subtitle = error.message
            )
        }
        is ApiException.UnknownError -> {
            ErrorInfo(
                icon = Icons.Default.Error,
                iconTint = MaterialTheme.colorScheme.error,
                title = "Something Went Wrong",
                subtitle = error.message
            )
        }
    }
    
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(Constants.PADDING_MEDIUM_DP.dp),
            modifier = Modifier.padding(Constants.PADDING_LARGE_DP.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = iconTint
            )
            
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            
            if (canRetry) {
                Button(
                    onClick = {
                        coroutineScope.launch {
                            HapticFeedbackHelper.performSuccessHaptic(context, hapticFeedbackEnabled)
                        }
                        onRetryClick()
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(Constants.BRAND_ORANGE)
                    ),
                    modifier = Modifier.padding(top = Constants.PADDING_SMALL_DP.dp)
                ) {
                    Text("Try Again")
                }
            }
        }
    }
}

/**
 * Data class to hold error display information
 */
private data class ErrorInfo(
    val icon: ImageVector,
    val iconTint: Color,
    val title: String,
    val subtitle: String
)

@Preview(showBackground = true)
@Composable
fun ErrorContentPreview() {
    ErrorContent(
        error = ApiException.NetworkError(),
        canRetry = true,
        onRetryClick = {}
    )
}