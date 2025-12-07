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
                // Loading state
                loadingView
            } else if hasError {
                // Hide on error
                EmptyView()
            } else if let summary = summary {
                // Success state - collapsible view
                collapsibleView(summary: summary)
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

    private var loadingView: some View {
        HStack(spacing: 8) {
            Image(systemName: "chart.bar.fill")
                .foregroundColor(.orange.opacity(0.8))
                .font(.subheadline)
            ProgressView()
                .scaleEffect(0.7)
                .frame(height: 16)
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(.systemGray6).opacity(0.9))
        )
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
                    Image(systemName: "chart.bar.fill")
                        .foregroundColor(.orange.opacity(0.8))
                        .font(.subheadline)
                        .padding(.top, 2)

                    Text(summary.headline)
                        .font(.subheadline)
                        .foregroundColor(.primary)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.secondary)
                        .font(.caption)
                        .fontWeight(.medium)
                        .padding(.top, 2)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
            }
            .buttonStyle(.plain)

            // Expanded content
            if isExpanded {
                VStack(alignment: .leading, spacing: 8) {
                    Divider()
                        .padding(.horizontal, 14)

                    Text(summary.body)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
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
                .fill(Color(.systemGray6).opacity(0.9))
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
    .background(Color(.systemBackground))
}
