import SwiftUI

/// A collapsible info box for train details that shows:
/// - Similar trains' on-time performance (past 90 minutes, same route + carrier)
/// - This specific train's historical on-time performance
///
/// The headline shows a brief summary, expandable to show full details.
/// Hides automatically on loading errors.
struct TrainStatsSummaryView: View {
    let trainId: String
    let fromStation: String?
    let toStation: String?

    @State private var summary: OperationsSummaryResponse?
    @State private var isExpanded = false
    @State private var isLoading = true
    @State private var hasError = false
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if isLoading {
                // Use Color.clear instead of EmptyView to ensure .task fires
                Color.clear.frame(height: 0)
            } else if hasError {
                // Hide on error
                Color.clear.frame(height: 0)
            } else if let summary = summary, !summary.headline.isEmpty {
                // Success state - collapsible view (only show if headline has content)
                collapsibleView(summary: summary)
            } else {
                // No data available - hide the section
                EmptyView()
            }
        }
        .task {
            await fetchSummary()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                Task {
                    await fetchSummary()
                }
            }
        }
    }

    private func collapsibleView(summary: OperationsSummaryResponse) -> some View {
        VStack(spacing: 0) {
            // Collapsed header (always visible, tappable)
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    isExpanded.toggle()
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                HStack(alignment: .top, spacing: 8) {
                    Text(summary.headline)
                        .font(.subheadline)
                        .foregroundColor(.white)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.white.opacity(0.5))
                        .font(.caption)
                        .fontWeight(.medium)
                        .padding(.top, 2)
                }
                .contentShape(Rectangle())
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
            }
            .buttonStyle(.plain)

            // Expanded content
            if isExpanded {
                VStack(alignment: .leading, spacing: 8) {
                    Divider()
                        .background(Color.white.opacity(0.2))
                        .padding(.horizontal, 14)

                    Text(summary.body)
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)
                        .padding(.horizontal, 14)
                        .padding(.bottom, 12)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.white.opacity(0.15), lineWidth: 1)
        )
    }

    private func fetchSummary() async {
        isLoading = true
        hasError = false

        do {
            summary = try await APIService.shared.fetchOperationsSummary(
                scope: .train,
                fromStation: fromStation,
                toStation: toStation,
                trainId: trainId
            )
            isLoading = false
        } catch {
            print("❌ Failed to fetch train stats summary: \(error)")
            hasError = true
            isLoading = false
        }
    }
}

// MARK: - Preview

#Preview("Train Stats Summary") {
    VStack(spacing: 20) {
        TrainStatsSummaryView(
            trainId: "3847",
            fromStation: "MP",
            toStation: "NY"
        )
    }
    .padding()
    .background(Color.black)
}
