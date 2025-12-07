import SwiftUI

/// A simple info box that displays a brief summary of recent train operations.
/// Supports three scopes: network (overall), route (origin to destination), and train (specific train).
/// Hides automatically on loading errors.
struct OperationsSummaryView: View {
    let scope: SummaryScope
    let fromStation: String?
    let toStation: String?
    let trainId: String?

    @State private var summary: OperationsSummaryResponse?
    @State private var isLoading = true
    @State private var hasError = false
    @Environment(\.scenePhase) private var scenePhase

    init(scope: SummaryScope, fromStation: String? = nil, toStation: String? = nil, trainId: String? = nil) {
        self.scope = scope
        self.fromStation = fromStation
        self.toStation = toStation
        self.trainId = trainId
    }

    var body: some View {
        Group {
            if isLoading {
                // Loading state - show minimal placeholder
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
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
            } else if hasError {
                // Hide on error - show nothing
                EmptyView()
            } else if let summary = summary {
                // Success state - show the summary body
                Text(summary.body)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineSpacing(2)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 12)
                    .background(
                        RoundedRectangle(cornerRadius: 10)
                            .fill(Color(.systemGray6).opacity(0.9))
                    )
            }
        }
        .task {
            await fetchSummary()
        }
        .onChange(of: scenePhase) { _, newPhase in
            // Auto-refresh when returning to foreground
            if newPhase == .active {
                Task {
                    await fetchSummary()
                }
            }
        }
    }

    private func fetchSummary() async {
        isLoading = true
        hasError = false

        do {
            summary = try await APIService.shared.fetchOperationsSummary(
                scope: scope,
                fromStation: fromStation,
                toStation: toStation,
                trainId: trainId
            )
            isLoading = false
        } catch {
            print("❌ Failed to fetch operations summary: \(error)")
            hasError = true
            isLoading = false
        }
    }
}

// MARK: - Preview

#Preview("Network Summary") {
    VStack(spacing: 20) {
        OperationsSummaryView(scope: .network)

        OperationsSummaryView(
            scope: .route,
            fromStation: "NY",
            toStation: "NP"
        )

        OperationsSummaryView(
            scope: .train,
            trainId: "3847"
        )
    }
    .padding()
    .background(Color(.systemBackground))
}
