import SwiftUI

/// A horizontal bar chart showing train distribution by delay category.
/// Each category column contains stacked train pills with train numbers.
/// Tapping a pill navigates to the train detail view.
struct TrainDistributionChart: View {
    let trainsByCategory: [String: [TrainDelaySummary]]
    let onTrainTap: (String) -> Void

    private let categories: [(key: String, label: String, color: Color)] = [
        ("on_time", "On time", .green),
        ("slight_delay", "5-15m", .yellow),
        ("delayed", "15m+", .orange),
        ("cancelled", "Cancelled", .gray)
    ]

    /// Maximum trains to show per column before showing "+N more"
    private let maxVisibleTrains = 5

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            ForEach(categories, id: \.key) { category in
                categoryColumn(
                    key: category.key,
                    label: category.label,
                    color: category.color,
                    trains: trainsByCategory[category.key] ?? []
                )
            }
        }
        .padding(.vertical, 8)
    }

    private func categoryColumn(
        key: String,
        label: String,
        color: Color,
        trains: [TrainDelaySummary]
    ) -> some View {
        VStack(spacing: 4) {
            // Train pills stack
            if trains.isEmpty {
                // Empty placeholder
                Text("—")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.3))
                    .frame(width: 52, height: 24)
            } else {
                // Show trains (limited to maxVisibleTrains)
                let visibleTrains = Array(trains.prefix(maxVisibleTrains))
                let remainingCount = trains.count - visibleTrains.count

                VStack(spacing: 2) {
                    // Overflow indicator at top if needed
                    if remainingCount > 0 {
                        Text("+\(remainingCount)")
                            .font(.caption2)
                            .fontWeight(.medium)
                            .foregroundColor(.white.opacity(0.5))
                            .frame(width: 52, height: 18)
                            .background(
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(color.opacity(0.3))
                            )
                    }

                    // Train pills (reversed so newest at bottom)
                    ForEach(visibleTrains.reversed()) { train in
                        trainPill(train: train, color: color)
                    }
                }
            }

            // Category label
            Text(label)
                .font(.caption2)
                .foregroundColor(.white.opacity(0.6))
                .lineLimit(1)

            // Count
            Text("(\(trains.count))")
                .font(.caption2)
                .foregroundColor(.white.opacity(0.4))
        }
        .frame(maxWidth: .infinity)
    }

    private func trainPill(train: TrainDelaySummary, color: Color) -> some View {
        Button {
            onTrainTap(train.trainId)
        } label: {
            Text(displayLabel(for: train.trainId))
                .font(.caption2)
                .fontWeight(.semibold)
                .foregroundColor(.white)
                .frame(width: 52, height: 24)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(color.opacity(0.8))
                )
        }
        .buttonStyle(.plain)
    }

    /// Returns a short display label for a train ID.
    /// PATH/PATCO synthetic IDs (e.g., "PATH_PHO_33rd_1737900000") show just the prefix.
    private func displayLabel(for trainId: String) -> String {
        if trainId.hasPrefix("PATH_") { return "PATH" }
        if trainId.hasPrefix("PATCO_") { return "PATCO" }
        return trainId
    }
}

// MARK: - Preview

#Preview("Train Distribution Chart") {
    let mockTrains: [String: [TrainDelaySummary]] = [
        "on_time": [
            TrainDelaySummary(trainId: "3847", delayMinutes: 0, category: .onTime, scheduledDeparture: Date()),
            TrainDelaySummary(trainId: "3851", delayMinutes: 2, category: .onTime, scheduledDeparture: Date()),
            TrainDelaySummary(trainId: "3855", delayMinutes: 1, category: .onTime, scheduledDeparture: Date()),
            TrainDelaySummary(trainId: "3859", delayMinutes: 3, category: .onTime, scheduledDeparture: Date()),
        ],
        "slight_delay": [
            TrainDelaySummary(trainId: "3849", delayMinutes: 7, category: .slightDelay, scheduledDeparture: Date()),
            TrainDelaySummary(trainId: "3853", delayMinutes: 12, category: .slightDelay, scheduledDeparture: Date()),
        ],
        "delayed": [
            TrainDelaySummary(trainId: "3861", delayMinutes: 18, category: .delayed, scheduledDeparture: Date()),
        ],
        "cancelled": [
            TrainDelaySummary(trainId: "3863", delayMinutes: 0, category: .cancelled, scheduledDeparture: Date()),
        ]
    ]

    VStack {
        TrainDistributionChart(trainsByCategory: mockTrains) { trainId in
            print("Tapped train: \(trainId)")
        }
    }
    .padding()
    .background(.ultraThinMaterial)
}

#Preview("Empty Categories") {
    let mockTrains: [String: [TrainDelaySummary]] = [
        "on_time": [
            TrainDelaySummary(trainId: "3847", delayMinutes: 0, category: .onTime, scheduledDeparture: Date()),
        ],
        "slight_delay": [],
        "delayed": [],
        "cancelled": []
    ]

    VStack {
        TrainDistributionChart(trainsByCategory: mockTrains) { trainId in
            print("Tapped train: \(trainId)")
        }
    }
    .padding()
    .background(.ultraThinMaterial)
}

#Preview("Many Trains") {
    let mockTrains: [String: [TrainDelaySummary]] = [
        "on_time": (1...8).map { i in
            TrainDelaySummary(trainId: "\(3840 + i)", delayMinutes: 0, category: .onTime, scheduledDeparture: Date())
        },
        "slight_delay": [],
        "delayed": [],
        "cancelled": []
    ]

    VStack {
        TrainDistributionChart(trainsByCategory: mockTrains) { trainId in
            print("Tapped train: \(trainId)")
        }
    }
    .padding()
    .background(.ultraThinMaterial)
}
