import SwiftUI

/// Tracks the wider of the leading/trailing content widths so the centered
/// title can pad symmetrically and never overlap either side.
private struct NavSideWidthKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

/// Reusable navigation header that replaces the system navigation bar
/// to prevent layout shift issues on initial load.
///
/// `titleAccessory` renders inline before the title (e.g., a `SubwayLineChips`
/// bullet). It defaults to `EmptyView` so callers that don't need it can omit it.
struct TrackRatNavigationHeader<TitleAccessory: View, TrailingContent: View>: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let title: String
    var subtitle: String? = nil
    var showBackButton: Bool = true
    var showCloseButton: Bool = true
    var onBackAction: (() -> Void)? = nil
    var titleAccessory: () -> TitleAccessory
    var trailingContent: (() -> TrailingContent)?

    @State private var sideWidth: CGFloat = 0

    init(
        title: String,
        subtitle: String? = nil,
        showBackButton: Bool = true,
        showCloseButton: Bool = true,
        onBackAction: (() -> Void)? = nil,
        @ViewBuilder titleAccessory: @escaping () -> TitleAccessory,
        @ViewBuilder trailingContent: @escaping () -> TrailingContent
    ) {
        self.title = title
        self.subtitle = subtitle
        self.showBackButton = showBackButton
        self.showCloseButton = showCloseButton
        self.onBackAction = onBackAction
        self.titleAccessory = titleAccessory
        self.trailingContent = trailingContent
    }

    var body: some View {
        ZStack {
            // Center title - truly centered regardless of leading/trailing content
            VStack(spacing: 0) {
                HStack(spacing: 6) {
                    titleAccessory()
                    Text(title)
                        .font(TrackRatTheme.Typography.title3)
                        .foregroundColor(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                }
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.8))
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                }
            }
            .padding(.horizontal, sideWidth + 8)

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
                    .background(sideWidthReader)
                }

                Spacer()

                // Trailing content or close button
                if let trailingContent = trailingContent {
                    trailingContent()
                        .frame(height: 44)
                        .background(sideWidthReader)
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
                    .background(sideWidthReader)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .onPreferenceChange(NavSideWidthKey.self) { sideWidth = $0 }
    }

    private var sideWidthReader: some View {
        GeometryReader { geo in
            Color.clear.preference(key: NavSideWidthKey.self, value: geo.size.width)
        }
    }
}

// Convenience: trailing content only (no title accessory)
extension TrackRatNavigationHeader where TitleAccessory == EmptyView {
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
        self.titleAccessory = { EmptyView() }
        self.trailingContent = trailingContent
    }
}

// Convenience: title accessory only (no trailing content)
extension TrackRatNavigationHeader where TrailingContent == EmptyView {
    init(
        title: String,
        subtitle: String? = nil,
        showBackButton: Bool = true,
        showCloseButton: Bool = true,
        onBackAction: (() -> Void)? = nil,
        @ViewBuilder titleAccessory: @escaping () -> TitleAccessory
    ) {
        self.title = title
        self.subtitle = subtitle
        self.showBackButton = showBackButton
        self.showCloseButton = showCloseButton
        self.onBackAction = onBackAction
        self.titleAccessory = titleAccessory
        self.trailingContent = nil
    }
}

// Convenience: neither title accessory nor trailing content
extension TrackRatNavigationHeader where TitleAccessory == EmptyView, TrailingContent == EmptyView {
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
        self.titleAccessory = { EmptyView() }
        self.trailingContent = nil
    }
}
