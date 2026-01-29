import SwiftUI

struct TrackRatTheme {
    // MARK: - Colors
    struct Colors {
        // Brand Colors - Midnight Black theme
        static let surface: Color = Color.black
        
        static var surfaceSecondary: Color {
            surface.opacity(0.8)
        }
        
        static var surfaceCard: Color {
            return Color.white.opacity(0.1)
        }
        
        static var surfaceElevated: Color {
            return Color.white.opacity(0.05)
        }
        
        // Keep orange accent for consistency
        static let accent = Color.orange
        static let accentSecondary = Color.orange.opacity(0.8)
        
        // Background
        static let primaryBackground: Color = surface
        
        static var cardGradient: LinearGradient {
            return LinearGradient(
                colors: [Color.white.opacity(0.1), Color.white.opacity(0.05)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
        
        // Text Colors
        static let onSurface: Color = Color.white
        
        static var onSurfaceSecondary: Color {
            onSurface.opacity(0.7)
        }
        
        static var onSurfaceTertiary: Color {
            onSurface.opacity(0.5)
        }
        
        // Status Colors - Adjust for visibility
        static var success: Color {
            return Color(hex: "#0e5c8d")
        }
        
        static let warning = Color.yellow
        static let error = Color.red
        static let info = Color.blue
        
        // Train Status Colors
        static var onTime: Color {
            success
        }
        
        static let delayed = Color.red
        static let boarding = accent
        static let departed = Color.blue
        static let cancelled = Color.gray
        
        // Border Colors
        static let border: Color = Color.white.opacity(0.3)
        static let borderSecondary: Color = Color.white.opacity(0.2)

        // Shadow Colors
        static let shadow: Color = Color.black.opacity(0.1)
        static let shadowMedium: Color = Color.black.opacity(0.2)
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
    
    // MARK: - Spacing (fixed values for layout constraints)
    struct Spacing {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 16
        static let lg: CGFloat = 24
        static let xl: CGFloat = 32
        static let xxl: CGFloat = 48
    }

    // MARK: - Icon Sizes (semantic sizes that work with Dynamic Type)
    struct IconSize {
        /// Extra small icons for disclosure indicators (14pt base)
        static let xsmall: Font = .system(size: 14, weight: .semibold)
        /// Small icons in lists, labels (16pt base)
        static let small: Font = .system(size: 16, weight: .medium)
        /// Medium icons for buttons, navigation (20pt base)
        static let medium: Font = .system(size: 20, weight: .medium)
        /// Large icons for prominent UI elements (24pt base)
        static let large: Font = .system(size: 24, weight: .medium)
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
        static var shadowColor: Color {
            return Colors.surface.opacity(0.4)
        }
        
        static var light: Shadow {
            Shadow(
                color: shadowColor,
                radius: 4,
                x: 0,
                y: 2
            )
        }
        
        static var medium: Shadow {
            Shadow(
                color: shadowColor.opacity(1.25),
                radius: 8,
                x: 0,
                y: 4
            )
        }
        
        static var heavy: Shadow {
            Shadow(
                color: shadowColor.opacity(1.75),
                radius: 16,
                x: 0,
                y: 8
            )
        }
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
            .background(.ultraThinMaterial)
            .ignoresSafeArea()
    }
    
    func trackRatNavigationBarStyle() -> some View {
        self
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }

    /// Standard section header styling - uppercase caption with secondary color
    func trackRatSectionHeader() -> some View {
        self
            .font(TrackRatTheme.Typography.caption)
            .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
            .textCase(.uppercase)
            .tracking(0.5)
    }

    /// Standard card shadow
    func trackRatShadow() -> some View {
        self.shadow(color: TrackRatTheme.Colors.shadow, radius: 8, x: 0, y: 4)
    }

    /// Lighter card shadow for subtle elevation
    func trackRatShadowLight() -> some View {
        self.shadow(color: TrackRatTheme.Colors.shadow, radius: 4, x: 0, y: 2)
    }

    /// Protects text from overflow by limiting lines and allowing scaling
    /// Use on text in constrained spaces (pills, badges, navigation)
    func textProtected(lines: Int = 1, minScale: CGFloat = 0.75) -> some View {
        self
            .lineLimit(lines)
            .minimumScaleFactor(minScale)
    }

    /// Limits Dynamic Type scaling to prevent extreme sizes breaking layouts
    /// Use on screens or components that can't handle accessibility sizes
    func dynamicTypeBounded(_ range: ClosedRange<DynamicTypeSize> = .small ... .xxxLarge) -> some View {
        self.dynamicTypeSize(range)
    }

    /// Makes navigation destination backgrounds transparent to allow sheet's
    /// presentationBackground material to show through.
    /// On iOS 26+: Uses Liquid Glass compatible transparent backgrounds
    /// On iOS 18.x: Keeps default navigation backgrounds to prevent ghosting during transitions
    @ViewBuilder
    func transparentNavigationBackground() -> some View {
        if #available(iOS 26, *) {
            self
                .scrollContentBackground(.hidden)
                .containerBackground(.clear, for: .navigation)
        } else {
            // On iOS 18.x, don't clear the navigation container background
            // as it causes both old and new views to be visible during transitions
            self
                .scrollContentBackground(.hidden)
        }
    }

    /// Applies presentation background only on iOS 18 and earlier.
    /// On iOS 26+, Liquid Glass automatically provides the glassy sheet appearance,
    /// and manually specifying presentationBackground conflicts with it.
    @ViewBuilder
    func legacyPresentationBackground(_ material: Material) -> some View {
        if #available(iOS 26, *) {
            self
        } else {
            self.presentationBackground(material)
        }
    }
}

