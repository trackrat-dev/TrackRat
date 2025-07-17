import SwiftUI

struct TrackRatTheme {
    // MARK: - Colors
    struct Colors {
        // Brand Colors - Blue-based theme
        static let surface = Color(hex: "#0e5c8d")
        static let surfaceSecondary = Color(hex: "#0e5c8d").opacity(0.8)
        static let surfaceCard = Color.white.opacity(0.1)
        static let surfaceElevated = Color.white.opacity(0.05)
        
        // Keep orange accent for consistency
        static let accent = Color.orange
        static let accentSecondary = Color.orange.opacity(0.8)
        
        // Background Gradients - Blue-based
        static let primaryGradient = LinearGradient(
            colors: [Color(hex: "#0e5c8d"), Color.gray.opacity(0.2)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        
        static let cardGradient = LinearGradient(
            colors: [Color.white.opacity(0.1), Color.white.opacity(0.05)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        
        // Text Colors
        static let onSurface = Color.white
        static let onSurfaceSecondary = Color.white.opacity(0.7)
        static let onSurfaceTertiary = Color.white.opacity(0.5)
        
        // Status Colors
        static let success = Color(hex: "#0e5c8d")
        static let warning = Color.yellow
        static let error = Color.red
        static let info = Color.blue
        
        // Train Status Colors
        static let onTime = Color(hex: "#0e5c8d")
        static let delayed = Color.red
        static let boarding = accent
        static let departed = Color.blue
        static let cancelled = Color.gray
        
        // Border Colors
        static let border = Color.white.opacity(0.2)
        static let borderSecondary = Color.white.opacity(0.1)
    }
    
    // MARK: - Typography
    struct Typography {
        static let title1 = Font.largeTitle.weight(.bold)
        static let title2 = Font.title.weight(.semibold)
        static let title3 = Font.title2.weight(.medium)
        static let headline = Font.headline.weight(.semibold)
        static let body = Font.body
        static let bodySecondary = Font.body.weight(.medium)
        static let caption = Font.caption
        static let caption2 = Font.caption2
    }
    
    // MARK: - Spacing
    struct Spacing {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 16
        static let lg: CGFloat = 24
        static let xl: CGFloat = 32
        static let xxl: CGFloat = 48
    }
    
    // MARK: - Corner Radius
    struct CornerRadius {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 24
    }
    
    // MARK: - Shadows
    struct Shadows {
        static let light = Shadow(
            color: Color(hex: "#0e5c8d").opacity(0.4),
            radius: 4,
            x: 0,
            y: 2
        )
        
        static let medium = Shadow(
            color: Color(hex: "#0e5c8d").opacity(0.5),
            radius: 8,
            x: 0,
            y: 4
        )
        
        static let heavy = Shadow(
            color: Color(hex: "#0e5c8d").opacity(0.7),
            radius: 16,
            x: 0,
            y: 8
        )
    }
}

// MARK: - Shadow Helper
struct Shadow {
    let color: Color
    let radius: CGFloat
    let x: CGFloat
    let y: CGFloat
}

// MARK: - View Extensions for Theme
extension View {
    func trackRatCardStyle() -> some View {
        self
            .background(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .fill(.ultraThinMaterial)
                    .overlay(
                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                            .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                    )
            )
    }
    
    func trackRatPrimaryButtonStyle() -> some View {
        self
            .padding(.horizontal, TrackRatTheme.Spacing.lg)
            .padding(.vertical, TrackRatTheme.Spacing.md)
            .background(TrackRatTheme.Colors.accent)
            .foregroundColor(.white)
            .cornerRadius(TrackRatTheme.CornerRadius.md)
            .font(TrackRatTheme.Typography.headline)
    }
    
    func trackRatSecondaryButtonStyle() -> some View {
        self
            .padding(.horizontal, TrackRatTheme.Spacing.lg)
            .padding(.vertical, TrackRatTheme.Spacing.md)
            .background(.ultraThinMaterial)
            .foregroundColor(TrackRatTheme.Colors.onSurface)
            .cornerRadius(TrackRatTheme.CornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
            )
    }
    
    func trackRatGlassmorphicBackground() -> some View {
        self
            .background(TrackRatTheme.Colors.primaryGradient)
            .ignoresSafeArea()
    }
    
    func trackRatNavigationBarStyle() -> some View {
        self
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

