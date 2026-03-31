import SwiftUI

/// A collapsible info box for train details that shows:
/// - Similar trains' on-time performance (past 90 minutes, same route + carrier)
/// - This specific train's historical on-time performance
///
/// The headline shows a brief summary, expandable to show full details.
/// Includes a visual distribution chart showing trains by delay category.
/// Hides automatically on loading errors.
struct TrainStatsSummaryView: View {
    let trainId: String
    let fromStation: String?
    let toStation: String?
    let journeyDate: Date?
    let showDepartureOdds: Bool
    let onTrainTap: ((String) -> Void)?
    let prefetchedSummary: OperationsSummaryResponse?
    let prefetchedForecast: DelayForecastResponse?

    @State private var summary: OperationsSummaryResponse?
    @State private var delayForecast: DelayForecastResponse?
    @State private var isExpanded = false
    @State private var isLoading = true
    @State private var hasError = false
    @Environment(\.scenePhase) private var scenePhase

    init(trainId: String, fromStation: String?, toStation: String?, journeyDate: Date? = nil, showDepartureOdds: Bool = true, onTrainTap: ((String) -> Void)? = nil, prefetchedSummary: OperationsSummaryResponse? = nil, prefetchedForecast: DelayForecastResponse? = nil) {
        self.trainId = trainId
        self.fromStation = fromStation
        self.toStation = toStation
        self.journeyDate = journeyDate
        self.showDepartureOdds = showDepartureOdds
        self.onTrainTap = onTrainTap
        self.prefetchedSummary = prefetchedSummary
        self.prefetchedForecast = prefetchedForecast
    }

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
            if let prefetched = prefetchedSummary {
                summary = prefetched
                delayForecast = prefetchedForecast
                isLoading = false
            } else {
                await fetchSummary()
            }
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

                    // Delay forecast section (controlled by showDepartureOdds toggle)
                    if showDepartureOdds, let text = forecastText {
                        Divider()
                            .background(Color.white.opacity(0.2))
                            .padding(.horizontal, 14)

                        Text(text)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(2)
                            .padding(.horizontal, 14)
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

    private func fetchSummary() async {
        isLoading = true
        hasError = false

        do {
            // Load operations summary and delay forecast in parallel
            async let summaryTask = APIService.shared.fetchOperationsSummary(
                scope: .train,
                fromStation: fromStation,
                toStation: toStation,
                trainId: trainId
            )

            // Only fetch forecast if we have the required parameters
            async let forecastTask: DelayForecastResponse? = {
                guard let stationCode = fromStation,
                      let date = journeyDate else {
                    return nil
                }
                return try? await APIService.shared.getDelayForecast(
                    trainId: trainId,
                    stationCode: stationCode,
                    journeyDate: date
                )
            }()

            summary = try await summaryTask
            delayForecast = await forecastTask
            isLoading = false
        } catch {
            print("❌ Failed to fetch train stats summary: \(error)")
            hasError = true
            isLoading = false
        }
    }

    // MARK: - Forecast Display Text

    /// Generates the forecast text based on sample count and probabilities
    private var forecastText: String? {
        guard let forecast = delayForecast else { return nil }

        let sampleWord = forecast.sampleCount == 1 ? "journey" : "journeys"
        let onTimePercent = forecast.onTimePercentage

        // Calculate 15+ minute delay probability (significant + major)
        let significantDelayPercent = Int((forecast.delayProbabilities.significant + forecast.delayProbabilities.major) * 100)
        let showDelayWarning = significantDelayPercent >= 10
        let showCancellationWarning = forecast.cancellationPercentage >= 10

        var text = "Based on \(forecast.sampleCount) similar \(sampleWord), our guess is it's \(onTimePercent)% likely you'll depart on time"

        // Add warnings if applicable
        if showDelayWarning && showCancellationWarning {
            text += ", with a \(significantDelayPercent)% chance of a 15+ minute delay and a \(forecast.cancellationPercentage)% chance of cancellation"
        } else if showDelayWarning {
            text += ", with a \(significantDelayPercent)% chance of a 15+ minute delay"
        } else if showCancellationWarning {
            text += ", with a \(forecast.cancellationPercentage)% chance of cancellation"
        }

        text += "."
        return text
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
    .background(.ultraThinMaterial)
}
