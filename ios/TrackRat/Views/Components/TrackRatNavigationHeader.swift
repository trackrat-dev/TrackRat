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
    var onBackAction: (() -> Void)? = nil
    var trailingContent: (() -> TrailingContent)?

    init(
        title: String,
        subtitle: String? = nil,
        showBackButton: Bool = true,
        showCloseButton: Bool = true,
        onBackAction: (() -> Void)? = nil,
        @ViewBuilder trailingContent: @escaping () -> TrailingContent
    ) {
        self.title = title
        self.subtitle = subtitle
        self.showBackButton = showBackButton
        self.showCloseButton = showCloseButton
        self.onBackAction = onBackAction
        self.trailingContent = trailingContent
    }

    var body: some View {
        ZStack {
            // Center title - truly centered regardless of leading/trailing content
            VStack(spacing: 0) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.8))
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                }
            }
            .padding(.horizontal, 60)

            // Leading and trailing content
            HStack {
                // Back button
                if showBackButton {
                    Button {
                        if let onBackAction = onBackAction {
                            onBackAction()
                        } else if !appState.navigationPath.isEmpty {
                            appState.navigationPath.removeLast()
                        }
                    } label: {
                        Image(systemName: "chevron.left")
                            .font(TrackRatTheme.IconSize.small)
                            .foregroundColor(.white)
                            .frame(minWidth: 44, minHeight: 44)
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
                            .font(TrackRatTheme.IconSize.small)
                            .foregroundColor(.white)
                            .frame(minWidth: 44, minHeight: 44)
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
        showCloseButton: Bool = true,
        onBackAction: (() -> Void)? = nil
    ) {
        self.title = title
        self.subtitle = subtitle
        self.showBackButton = showBackButton
        self.showCloseButton = showCloseButton
        self.onBackAction = onBackAction
        self.trailingContent = nil
    }
}
