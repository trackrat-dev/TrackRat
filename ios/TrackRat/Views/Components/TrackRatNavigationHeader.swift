import SwiftUI

/// Reusable navigation header that replaces the system navigation bar
/// to prevent layout shift issues on initial load.
struct TrackRatNavigationHeader<TrailingContent: View>: View {
    @EnvironmentObject private var appState: AppState

    let title: String
    var subtitle: String? = nil
    var showBackButton: Bool = true
    var showCloseButton: Bool = true
    var trailingContent: (() -> TrailingContent)?

    var body: some View {
        HStack {
            // Back button
            if showBackButton {
                Button {
                    if !appState.navigationPath.isEmpty {
                        appState.navigationPath.removeLast()
                    }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(width: 44, height: 44)
                }
            } else {
                Color.clear.frame(width: 44, height: 44)
            }

            Spacer()

            // Center title
            VStack(spacing: 0) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.8))
                }
            }

            Spacer()

            // Trailing content or close button
            if let trailingContent = trailingContent {
                trailingContent()
                    .frame(height: 44)
            } else if showCloseButton {
                Button("Close") {
                    appState.navigationPath = NavigationPath()
                }
                .foregroundColor(.white)
                .font(.body)
                .frame(width: 44, height: 44)
            } else {
                Color.clear.frame(width: 44, height: 44)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 8)
        .background(Color(UIColor.systemBackground))
    }
}

// Convenience initializer for headers without trailing content
extension TrackRatNavigationHeader where TrailingContent == EmptyView {
    init(
        title: String,
        subtitle: String? = nil,
        showBackButton: Bool = true,
        showCloseButton: Bool = true
    ) {
        self.title = title
        self.subtitle = subtitle
        self.showBackButton = showBackButton
        self.showCloseButton = showCloseButton
        self.trailingContent = nil
    }
}
