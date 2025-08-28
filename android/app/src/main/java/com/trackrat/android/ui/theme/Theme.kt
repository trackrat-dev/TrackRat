package com.trackrat.android.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// TrackRat Dark Theme - Matching iOS App
private val TrackRatColorScheme = darkColorScheme(
    // Primary colors
    primary = TrackRatOrange,
    onPrimary = TrackRatBlack,
    
    // Container colors
    primaryContainer = TrackRatOrange,
    onPrimaryContainer = TrackRatBlack,
    
    // Secondary colors  
    secondary = TrackRatOrange,
    onSecondary = TrackRatBlack,
    
    // Background colors - Pure black like iOS
    background = TrackRatBlack,
    onBackground = TrackRatTextPrimary,
    
    // Surface colors - Using glassmorphic surfaces
    surface = TrackRatBlack,
    onSurface = TrackRatTextPrimary,
    surfaceVariant = TrackRatSurfaceCard,
    onSurfaceVariant = TrackRatTextSecondary,
    
    // Other surface variants
    surfaceContainer = TrackRatSurfaceElevated,
    surfaceContainerHigh = TrackRatSurfaceCard,
    
    // Outline colors for borders
    outline = TrackRatBorder,
    outlineVariant = TrackRatBorder.copy(alpha = 0.5f)
)

// Legacy color schemes for fallback
private val DarkColorScheme = darkColorScheme(
    primary = Purple80,
    secondary = PurpleGrey80,
    tertiary = Pink80
)

private val LightColorScheme = lightColorScheme(
    primary = Purple40,
    secondary = PurpleGrey40,
    tertiary = Pink40
)

@Composable
fun TrackRatTheme(
    darkTheme: Boolean = true, // Always use dark theme to match iOS
    // Dynamic color disabled to use our custom TrackRat colors
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    // Always use our custom TrackRat color scheme
    val colorScheme = TrackRatColorScheme
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            // Set status bar to black to match theme
            window.statusBarColor = TrackRatBlack.toArgb()
            // Use light status bar content (white text) on black background
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
