package com.trackrat.android.ui.theme

import androidx.compose.ui.graphics.Color

// TrackRat Brand Colors - Matching iOS App
val TrackRatOrange = Color(0xFFFF9500)  // iOS Orange accent
val TrackRatBlack = Color(0xFF000000)   // Pure black background
val TrackRatWhite = Color(0xFFFFFFFF)   // Pure white

// Surface Colors (Glassmorphic effects)
val TrackRatSurfaceCard = Color(0x1AFFFFFF)      // White 10% opacity
val TrackRatSurfaceElevated = Color(0x0DFFFFFF)  // White 5% opacity 
val TrackRatBorder = Color(0x4DFFFFFF)           // White 30% opacity

// Text Colors
val TrackRatTextPrimary = Color(0xFFFFFFFF)      // Pure white
val TrackRatTextSecondary = Color(0xB3FFFFFF)    // White 70% opacity
val TrackRatTextTertiary = Color(0x80FFFFFF)     // White 50% opacity

// Status Colors
val StatusOnTime = Color(0xFF0E5C8D)      // Blue from iOS
val StatusDelayed = Color(0xFFFF3B30)     // Red
val StatusBoarding = TrackRatOrange       // Orange
val StatusDeparted = Color(0xFF007AFF)    // Blue
val StatusCancelled = Color(0xFF8E8E93)   // Gray

// Legacy colors (keeping for now to avoid breaking changes)
val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)

val Purple40 = Color(0xFF6650a4)
val PurpleGrey40 = Color(0xFF625b71)
val Pink40 = Color(0xFF7D5260)