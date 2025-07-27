import SwiftUI
import UIKit

/// App icon management
final class AppIconManager: ObservableObject {
    @Published var isChangingIcon = false
    
    @MainActor
    func updateAppIcon(for theme: AppTheme) async {
        // Compile-time check for app extensions
        #if EXTENSION
        print("ℹ️ App icon changes not available in extension")
        return
        #else
        // Check if we're running in an app extension at runtime
        if Bundle.main.executablePath?.contains(".appex/") == true {
            print("ℹ️ App icon changes not available in extension")
            return
        }
        
        // Check if the app supports alternate icons
        guard UIApplication.shared.supportsAlternateIcons else {
            print("⚠️ Device does not support alternate app icons")
            return
        }
        
        let targetIconName = theme.iconName
        let currentIconName = UIApplication.shared.alternateIconName
        
        // Don't change if already using the target icon
        if currentIconName == targetIconName {
            return
        }
        
        isChangingIcon = true
        
        do {
            try await UIApplication.shared.setAlternateIconName(targetIconName)
            print("✅ App icon changed to: \(targetIconName ?? "default")")
        } catch {
            print("❌ Failed to change app icon: \(error.localizedDescription)")
        }
        
        isChangingIcon = false
        #endif
    }
}

enum AppTheme: String, CaseIterable {
    case blue = "blue"
    case black = "black"
    
    var displayName: String {
        switch self {
        case .blue: return "Ocean Blue"
        case .black: return "Midnight Black"
        }
    }
    
    var iconName: String? {
        switch self {
        case .blue: return nil // Default icon (nil means primary icon)
        case .black: return "AppIcon-Black"
        }
    }
}

final class ThemeManager: ObservableObject {
    static let shared = ThemeManager()
    
    private let iconManager = AppIconManager()
    
    @AppStorage("selectedTheme") var selectedTheme: AppTheme = .blue {
        didSet {
            Task { @MainActor in
                objectWillChange.send()
                // Automatically update app icon when theme changes
                await iconManager.updateAppIcon(for: selectedTheme)
            }
        }
    }
    
    private init() {}
    
    var colorScheme: ColorScheme? {
        return .dark
    }
    
    var tintColor: Color {
        return .white
    }
    
    var isChangingIcon: Bool {
        return iconManager.isChangingIcon
    }
    
    // MARK: - App Icon Management
    
    /// Updates the app icon to match the selected theme
    func updateAppIcon() async {
        await iconManager.updateAppIcon(for: selectedTheme)
    }
    
    /// Manually update app icon (for testing or explicit user action)
    func changeAppIcon(to theme: AppTheme) async {
        await MainActor.run {
            selectedTheme = theme
        }
    }
}