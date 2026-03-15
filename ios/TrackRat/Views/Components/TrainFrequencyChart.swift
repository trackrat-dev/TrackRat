import SwiftUI

/// A row-based chart showing trains bucketed by headway (gap since prior departure).
/// Used for frequency-first systems (PATH, Subway, PATCO) where service frequency
/// matters more than schedule adherence.
struct TrainFrequencyChart: View {
    let trainsByHeadway: [String: [TrainDelaySummary]]
    let onTrainTap: (String) -> Void

    private let bins: [(key: String, label: String, color: Color)] = [
        ("0_5_min", "0–5 min", .green),
        ("5_10_min", "5–10 min", .yellow),
        ("10_20_min", "10–20 min", .orange),
        ("20_plus_min", "20+ min", .red),
    ]

    /// Maximum trains to show per row before showing "+N more"
    private let maxVisibleTrains = 6

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(bins, id: \.key) { bin in
                let trains = trainsByHeadway[bin.key] ?? []
                headwayRow(label: bin.label, color: bin.color, trains: trains)
            }
        }
        .padding(.vertical, 8)
    }

    private func headwayRow(label: String, color: Color, trains: [TrainDelaySummary]) -> some View {
        HStack(spacing: 6) {
            // Bin label
            Text(label)
                .font(.caption2)
                .foregroundColor(.white.opacity(0.6))
                .textProtected()
                .frame(width: 56, alignment: .leading)

            if trains.isEmpty {
                Text("—")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.3))
            } else {
                let visible = Array(trains.prefix(maxVisibleTrains))
                let remaining = trains.count - visible.count

                ForEach(visible) { train in
                    trainPill(train: train, color: color)
                }

                if remaining > 0 {
                    Text("+\(remaining)")
                        .font(.caption2)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(0.5))
                        .frame(minWidth: 28, minHeight: 22)
                        .background(
                            RoundedRectangle(cornerRadius: 4)
                                .fill(color.opacity(0.3))
                        )
                }
            }

            Spacer(minLength: 0)
        }
    }

    private func trainPill(train: TrainDelaySummary, color: Color) -> some View {
        Button {
            onTrainTap(train.trainId)
        } label: {
            Text(displayLabel(for: train.trainId))
                .font(.caption2)
                .fontWeight(.semibold)
                .foregroundColor(.white)
                .textProtected()
                .frame(minWidth: 40, minHeight: 22)
                .padding(.horizontal, 4)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(color.opacity(0.8))
                )
        }
        .buttonStyle(.plain)
    }

    /// Returns a short display label for a train ID.
    private func displayLabel(for trainId: String) -> String {
        if trainId.hasPrefix("PATH_") { return "PATH" }
        if trainId.hasPrefix("PATCO_") { return "PATCO" }
        if trainId.hasPrefix("LIRR_") { return "LIRR" }
        if trainId.hasPrefix("MNR_") { return "MNR" }
        if trainId.hasPrefix("S"), let dashIdx = trainId.firstIndex(of: "-"), dashIdx > trainId.startIndex {
            let route = trainId[trainId.index(after: trainId.startIndex)..<dashIdx]
            return "\(route) train"
        }
        return trainId
    }
}

// MARK: - Preview

#Preview("Train Frequency Chart") {
    let now = Date()
    let mockHeadway: [String: [TrainDelaySummary]] = [
        "0_5_min": [
            TrainDelaySummary(trainId: "PATH_WTC_33rd_001", delayMinutes: 0, category: .onTime, scheduledDeparture: now.addingTimeInterval(-600)),
            TrainDelaySummary(trainId: "PATH_WTC_33rd_002", delayMinutes: 1, category: .onTime, scheduledDeparture: now.addingTimeInterval(-300)),
            TrainDelaySummary(trainId: "PATH_WTC_33rd_003", delayMinutes: 0, category: .onTime, scheduledDeparture: now.addingTimeInterval(-60)),
        ],
        "5_10_min": [
            TrainDelaySummary(trainId: "PATH_WTC_33rd_004", delayMinutes: 2, category: .onTime, scheduledDeparture: now.addingTimeInterval(-1200)),
        ],
        "10_20_min": [
            TrainDelaySummary(trainId: "PATH_WTC_33rd_005", delayMinutes: 3, category: .onTime, scheduledDeparture: now.addingTimeInterval(-2400)),
        ],
        "20_plus_min": [],
    ]

    VStack {
        TrainFrequencyChart(trainsByHeadway: mockHeadway) { trainId in
            print("Tapped train: \(trainId)")
        }
    }
    .padding()
    .background(.ultraThinMaterial)
}

#Preview("Empty Frequency Chart") {
    let mockHeadway: [String: [TrainDelaySummary]] = [
        "0_5_min": [],
        "5_10_min": [],
        "10_20_min": [],
        "20_plus_min": [],
    ]

    VStack {
        TrainFrequencyChart(trainsByHeadway: mockHeadway) { _ in }
    }
    .padding()
    .background(.ultraThinMaterial)
}

#Preview("Many Trains Overflow") {
    let now = Date()
    let mockHeadway: [String: [TrainDelaySummary]] = [
        "0_5_min": (1...10).map { i in
            TrainDelaySummary(trainId: "PATH_WTC_33rd_\(i)", delayMinutes: 0, category: .onTime, scheduledDeparture: now.addingTimeInterval(Double(-i * 60)))
        },
        "5_10_min": [],
        "10_20_min": [],
        "20_plus_min": [],
    ]

    VStack {
        TrainFrequencyChart(trainsByHeadway: mockHeadway) { _ in }
    }
    .padding()
    .background(.ultraThinMaterial)
}
