import SwiftUI

/// Stylized "beta" badge shown next to systems still in development.
struct BetaPill: View {
    var body: some View {
        Text("beta")
            .font(.caption2)
            .fontWeight(.semibold)
            .foregroundColor(.orange)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Capsule().fill(.orange.opacity(0.2)))
    }
}

/// A single compact colored pill identifying one transit system.
/// Currently renders the short `chipLabel` over the system's brand color;
/// designed so a future logo asset can replace the text without touching
/// callers.
struct SystemPill: View {
    let system: TrainSystem
    var size: CGFloat = 14

    var body: some View {
        let bg = Color(hex: system.color) ?? .gray
        Text(system.chipLabel)
            .font(.system(size: size * 0.55, weight: .heavy, design: .rounded))
            .foregroundColor(.white)
            .padding(.horizontal, size * 0.28)
            .frame(height: size)
            .background(
                RoundedRectangle(cornerRadius: size * 0.25)
                    .fill(bg)
            )
    }
}

/// Renders compact colored pills showing which non-subway transit systems
/// serve a station (e.g., "NJT", "AMK", "PATH"). Analogous to
/// `SubwayLineChips` but for commuter/intercity rail systems.
///
/// Empty when the station has no non-subway systems, so callers can use
/// this unconditionally alongside `SubwayLineChips`.
struct SystemChips: View {
    let stationCode: String
    var size: CGFloat = 14

    private var systems: [TrainSystem] {
        Stations.systemsForStation(stationCode)
            .filter { $0 != .subway }
            .sorted { $0.chipLabel < $1.chipLabel }
    }

    var body: some View {
        if !systems.isEmpty {
            HStack(spacing: 3) {
                ForEach(systems) { system in
                    SystemPill(system: system, size: size)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("systems: \(systems.map(\.displayName).joined(separator: ", "))")
        }
    }
}

#Preview {
    VStack(alignment: .leading, spacing: 12) {
        HStack(spacing: 6) {
            Text("Penn Station")
            SystemChips(stationCode: "NY")
        }
        HStack(spacing: 6) {
            Text("Newark Penn")
            SystemChips(stationCode: "NP")
        }
        HStack(spacing: 6) {
            Text("Jamaica")
            SystemChips(stationCode: "JAM")
        }
        HStack(spacing: 6) {
            Text("Times Sq-42 St")
            SubwayLineChips(lines: ["1", "2", "3", "7", "N", "Q", "R", "W", "S"])
            SystemChips(stationCode: "S127")
        }
        HStack(spacing: 6) {
            Text("NJ Transit")
            SystemPill(system: .njt, size: 22)
        }
    }
    .padding()
    .background(Color.black)
    .foregroundColor(.white)
}
