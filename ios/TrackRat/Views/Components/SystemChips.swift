import SwiftUI

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
                    chip(for: system)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("systems: \(systems.map(\.displayName).joined(separator: ", "))")
        }
    }

    @ViewBuilder
    private func chip(for system: TrainSystem) -> some View {
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
            SystemChips(stationCode: "TSQ")
        }
    }
    .padding()
    .background(Color.black)
    .foregroundColor(.white)
}
