import SwiftUI

/// A row in the "Routes" list on `TrainSystemDetailView`. Shows a colored
/// swatch (system brand color), the route name, terminal subtitle, an optional
/// average-delay pill, and a chevron. Tapping is handled by the parent view.
struct SystemRouteListRow: View {
    let route: RouteLine
    let system: TrainSystem
    /// Average delay in minutes across this route's segments, or `nil` when
    /// no congestion data is available yet (e.g. still loading or no samples).
    let averageDelayMinutes: Double?

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 2)
                .fill(Color(hex: system.color))
                .frame(width: 4, height: 32)

            VStack(alignment: .leading, spacing: 2) {
                Text(route.name)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.primary)
                if let subtitle = route.terminalSubtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            if let delay = averageDelayMinutes {
                delayPill(delay)
            }

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 10)
        .padding(.horizontal)
        .contentShape(Rectangle())
    }

    @ViewBuilder
    private func delayPill(_ delay: Double) -> some View {
        let (label, color) = pillStyle(for: delay)
        Text(label)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Capsule().fill(color.opacity(0.2)))
            .foregroundColor(color)
    }

    private func pillStyle(for delay: Double) -> (String, Color) {
        if delay < 0.5 { return ("On time", .green) }
        let label = String(format: "+%.0f min", delay.rounded())
        if delay < 5 { return (label, .yellow) }
        return (label, .red)
    }
}
