import SwiftUI

/// Compact, line-color-bar departure row used by overview screens
/// (route status, station details). For interactive trip-planning cards
/// see `TrainCard` in `TrainListView.swift`.
struct TrainRow: View {
    let train: TrainV2
    let dataSource: String

    /// Minimum destination-arrival delay before the badge flags an en-route
    /// slip; matches TrainCard.DELAY_THRESHOLD_MINUTES so the overview row
    /// and the trip list flag the same trains.
    private static let ARRIVAL_DELAY_THRESHOLD_MINUTES = 3

    /// Whether this transit system uses synthetic train IDs (e.g., subway, PATCO)
    private var useSyntheticId: Bool {
        TrainSystem.syntheticTrainIdSources.contains(dataSource)
    }

    /// Delay at the rider's destination; 0 on station boards, where the row
    /// has no destination context (`train.arrival` is nil).
    private var arrivalDelayMinutes: Int {
        train.arrival?.delayMinutes ?? 0
    }

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 2)
                .fill(Color(hex: train.line.color))
                .frame(width: 4, height: 40)

            VStack(alignment: .leading, spacing: 2) {
                if useSyntheticId {
                    Text(train.line.name)
                        .font(.subheadline.bold())
                } else {
                    Text("Train \(train.trainId)")
                        .font(.subheadline.bold())
                }
                HStack(spacing: 8) {
                    if let track = train.track, !track.isEmpty {
                        Text("Track \(track)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    if train.isCancelled {
                        Text("Cancelled")
                            .font(.caption.bold())
                            .foregroundColor(.red)
                    }
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(departureTimeString)
                    .font(.subheadline.bold())
                delayBadge
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }

    private var departureTimeString: String {
        guard let time = train.departure.updatedTime ?? train.departure.scheduledTime else {
            return "--"
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: time)
    }

    // A train can leave its origin on time and still slip en route
    // (issue #1527): with only the origin-departure delta this row claimed
    // "On Time" while the detail screen showed the destination running late.
    // Departure delay stays dominant (it decides whether the rider catches
    // the train); otherwise the destination-arrival slip is surfaced in
    // orange, mirroring TrainCard's arrival-delay color.
    @ViewBuilder
    private var delayBadge: some View {
        if train.isCancelled {
            EmptyView()
        } else if train.departure.delayMinutes > 0 {
            Text("+\(train.departure.delayMinutes)m")
                .font(.caption.bold())
                .foregroundColor(.red)
        } else if arrivalDelayMinutes >= TrainRow.ARRIVAL_DELAY_THRESHOLD_MINUTES {
            Text("Arr +\(arrivalDelayMinutes)m")
                .font(.caption.bold())
                .foregroundColor(.orange)
        } else {
            Text("On Time")
                .font(.caption)
                .foregroundColor(.green)
        }
    }
}
