import SwiftUI

final class ThemeManager: ObservableObject {
    static let shared = ThemeManager()
    
    private init() {}
    
    var colorScheme: ColorScheme? {
        return .dark
    }
    
    var tintColor: Color {
        return .white
    }
}