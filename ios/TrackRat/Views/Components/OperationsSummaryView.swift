import SwiftUI

/// A simple info box that displays a brief summary of recent train operations.
/// Supports three scopes: network (overall), route (origin to destination), and train (specific train).
/// Hides automatically on loading errors.
struct OperationsSummaryView: View {
    let scope: SummaryScope
    let fromStation: String?
    let toStation: String?
    let trainId: String?
    let isExpandable: Bool
    let onTrainTap: ((String) -> Void)?

    @State private var summary: OperationsSummaryResponse?
    @State private var isLoading = true
    @State private var hasError = false
    @State private var isExpanded = false
    @Environment(\.scenePhase) private var scenePhase

    init(
        scope: SummaryScope,
        fromStation: String? = nil,
        toStation: String? = nil,
        trainId: String? = nil,
        isExpandable: Bool = false,
        onTrainTap: ((String) -> Void)? = nil
    ) {
        self.scope = scope
        self.fromStation = fromStation
        self.toStation = toStation
        self.trainId = trainId
        self.isExpandable = isExpandable
        self.onTrainTap = onTrainTap
    }

    var body: some View {
        Group {
            if isLoading {
                // Use Color.clear instead of EmptyView to ensure .task fires
                Color.clear.frame(height: 0)
            } else if hasError {
                // Hide on error - show nothing
                Color.clear.frame(height: 0)
            } else if let summary = summary, !summary.body.isEmpty {
                // Only show if we have content (empty body means no data)
                if isExpandable && !summary.headline.isEmpty {
                    // Collapsible view - headline collapsed, body expanded
                    collapsibleView(summary: summary)
                } else {
                    // Simple view - show the summary body only
                    Text(summary.body)
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 10)
                                .fill(.ultraThinMaterial)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color.white.opacity(0.15), lineWidth: 1)
                        )
                }
            } else {
                // No data available - hide the section
                EmptyView()
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

        print("📊 OperationsSummary: Fetching scope=\(scope), from=\(fromStation ?? "nil"), to=\(toStation ?? "nil"), train=\(trainId ?? "nil")")

        do {
            let result = try await APIService.shared.fetchOperationsSummary(
                scope: scope,
                fromStation: fromStation,
                toStation: toStation,
                trainId: trainId
            )
            summary = result
            isLoading = false

            // Log what we received
            if result.body.isEmpty {
                print("📊 OperationsSummary: Received EMPTY body - view will be hidden (headline='\(result.headline)')")
            } else {
                print("📊 OperationsSummary: Received body='\(result.body.prefix(80))...' headline='\(result.headline)'")
            }
        } catch {
            print("❌ OperationsSummary: Failed to fetch - \(error) - view will be hidden")
            hasError = true
            isLoading = false
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

                    // Train distribution chart
                    if let trainsByCategory = summary.metrics?.trainsByCategory,
                       !trainsByCategory.values.allSatisfy({ $0.isEmpty }) {
                        Divider()
                            .background(Color.white.opacity(0.2))
                            .padding(.horizontal, 14)

                        TrainDistributionChart(trainsByCategory: trainsByCategory) { trainId in
                            onTrainTap?(trainId)
                        }
                        .padding(.horizontal, 10)
                    }
                }
                .padding(.bottom, 12)
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
    .background(Color.black)
}
