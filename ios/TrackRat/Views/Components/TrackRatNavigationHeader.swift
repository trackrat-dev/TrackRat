import SwiftUI

/// Reusable navigation header that replaces the system navigation bar
/// to prevent layout shift issues on initial load.
struct TrackRatNavigationHeader<TrailingContent: View>: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let title: String
    var subtitle: String? = nil
    var showBackButton: Bool = true
    var showCloseButton: Bool = true
    var trailingContent: (() -> TrailingContent)?

    var body: some View {
        ZStack {
            // Center title - truly centered regardless of leading/trailing content
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

            // Leading and trailing content
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
                    .buttonStyle(.plain)
                }

                Spacer()

                // Trailing content or close button
                if let trailingContent = trailingContent {
                    trailingContent()
                        .frame(height: 44)
                } else if showCloseButton {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
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
