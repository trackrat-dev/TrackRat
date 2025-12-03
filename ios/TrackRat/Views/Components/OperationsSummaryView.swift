import SwiftUI

/// A collapsible info box that displays a brief summary of recent train operations.
/// Supports three scopes: network (overall), route (origin to destination), and train (specific train).
struct OperationsSummaryView: View {
    let scope: SummaryScope
    let fromStation: String?
    let toStation: String?
    let trainId: String?

    @State private var summary: OperationsSummaryResponse?
    @State private var isExpanded = false
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
        VStack(spacing: 0) {
            // Collapsed pill (always visible)
            Button(action: {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    isExpanded.toggle()
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }) {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(.orange.opacity(0.8))
                        .font(.subheadline)

                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.7)
                            .frame(height: 16)
                    } else if hasError {
                        Text("Unable to load summary")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    } else if let summary = summary {
                        Text(summary.headline)
                            .font(.subheadline)
                            .foregroundColor(.primary)
                            .lineLimit(1)
                    }

                    Spacer()

                    if !isLoading && !hasError && summary != nil {
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .foregroundColor(.secondary)
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(.systemGray6).opacity(0.9))
                )
            }
            .buttonStyle(.plain)

            // Expanded content
            if isExpanded, let summary = summary {
                VStack(alignment: .leading, spacing: 10) {
                    Text(summary.body)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)

                    // Metrics row (if available)
                    if let metrics = summary.metrics {
                        metricsRow(metrics)
                    }

                    HStack {
                        Spacer()
                        Text("Updated \(summary.dataFreshnessFormatted)")
                            .font(.caption2)
                            .foregroundColor(.tertiary)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(.systemGray6).opacity(0.9))
                )
                .transition(.opacity.combined(with: .move(edge: .top)))
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

    @ViewBuilder
    private func metricsRow(_ metrics: SummaryMetrics) -> some View {
        HStack(spacing: 16) {
            if let onTime = metrics.onTimePercentage {
                metricBadge(
                    value: "\(Int(onTime))%",
                    label: "On Time",
                    color: onTime >= 85 ? .green : (onTime >= 70 ? .yellow : .orange)
                )
            }

            if let trainCount = metrics.trainCount, trainCount > 0 {
                metricBadge(
                    value: "\(trainCount)",
                    label: trainCount == 1 ? "Train" : "Trains",
                    color: .blue
                )
            }

            if let cancellations = metrics.cancellationCount, cancellations > 0 {
                metricBadge(
                    value: "\(cancellations)",
                    label: "Cancelled",
                    color: .red
                )
            }

            if let track = metrics.mostCommonTrack {
                metricBadge(
                    value: track,
                    label: "Track",
                    color: .purple
                )
            }
        }
        .padding(.top, 4)
    }

    @ViewBuilder
    private func metricBadge(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(color)

            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
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
