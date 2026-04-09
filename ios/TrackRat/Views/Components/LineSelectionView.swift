import SwiftUI

/// Standalone Line Selection UI that discovers systems/lines for a station pair
/// and allows the user to toggle them on/off. Used in RouteStatusView and alert configuration.
struct LineSelectionView: View {
    let systems: [RouteSystemInfo]
    @Binding var enabledLineIds: Set<String>

    /// Whether there's anything to show (multiple systems or multiple lines)
    var hasContent: Bool {
        if systems.count > 1 { return true }
        if systems.count == 1, systems[0].lines.count > 1 { return true }
        return false
    }

    var body: some View {
        if hasContent {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Line Selection")
                        .font(.headline)
                    Spacer()
                    if !enabledLineIds.isEmpty {
                        Button("Select All") {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                enabledLineIds = []
                            }
                        }
                        .font(.subheadline)
                        .foregroundColor(.orange)
                    }
                }

                ForEach(systems) { systemInfo in
                    VStack(alignment: .leading, spacing: 8) {
                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                toggleSystem(systemInfo.system)
                            }
                        } label: {
                            HStack {
                                Image(systemName: systemInfo.system.icon)
                                    .font(.caption)
                                Text(systemInfo.system.displayName)
                                    .font(.subheadline.bold())
                                Spacer()
                            }
                            .foregroundColor(isSystemEnabled(systemInfo.system) ? .white : .white.opacity(0.4))
                        }
                        .buttonStyle(.plain)

                        if !systemInfo.lines.isEmpty {
                            lineGrid(lines: systemInfo.lines)
                        }
                    }
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Line Grid

    private func lineGrid(lines: [RouteLineInfo]) -> some View {
        let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: min(lines.count, 7))
        return LazyVGrid(columns: columns, spacing: 6) {
            ForEach(lines) { line in
                let isOn = isLineEnabled(line.id)
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        toggleLine(line.id)
                    }
                } label: {
                    Text(line.lineCode)
                        .font(.caption2)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .fill(isOn ? Color(hex: line.lineColor) : Color.white.opacity(0.08))
                        )
                        .foregroundColor(isOn ? textColor(for: line.lineColor) : .white.opacity(0.6))
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Toggle Logic

    private var allLineIds: Set<String> {
        Set(systems.flatMap { $0.lines.map(\.id) })
    }

    private func isLineEnabled(_ lineId: String) -> Bool {
        enabledLineIds.isEmpty || enabledLineIds.contains(lineId)
    }

    private func isSystemEnabled(_ system: TrainSystem) -> Bool {
        let enabledSystems: Set<String>
        if enabledLineIds.isEmpty {
            enabledSystems = Set(systems.map(\.system.rawValue))
        } else {
            enabledSystems = Set(enabledLineIds.compactMap { $0.split(separator: ":").first.map(String.init) })
        }
        return enabledSystems.contains(system.rawValue)
    }

    private func toggleLine(_ lineId: String) {
        if enabledLineIds.isEmpty {
            enabledLineIds = allLineIds
        }

        if enabledLineIds.contains(lineId) {
            if enabledLineIds.count > 1 {
                enabledLineIds.remove(lineId)
            }
        } else {
            enabledLineIds.insert(lineId)
        }

        if enabledLineIds == allLineIds {
            enabledLineIds = []
        }
    }

    private func toggleSystem(_ system: TrainSystem) {
        guard let systemInfo = systems.first(where: { $0.system == system }) else { return }
        let systemLineIds = Set(systemInfo.lines.map(\.id))

        if enabledLineIds.isEmpty {
            enabledLineIds = allLineIds
        }

        let allSystemLinesEnabled = systemLineIds.isSubset(of: enabledLineIds)
        if allSystemLinesEnabled {
            let remaining = enabledLineIds.subtracting(systemLineIds)
            if !remaining.isEmpty {
                enabledLineIds = remaining
            }
        } else {
            enabledLineIds.formUnion(systemLineIds)
        }

        if enabledLineIds == allLineIds {
            enabledLineIds = []
        }
    }

    // MARK: - Text Color

    private func textColor(for hexColor: String) -> Color {
        let hex = hexColor.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard hex.count >= 6,
              let r = UInt8(hex.prefix(2), radix: 16),
              let g = UInt8(hex.dropFirst(2).prefix(2), radix: 16),
              let b = UInt8(hex.dropFirst(4).prefix(2), radix: 16) else {
            return .white
        }
        let brightness = (Double(r) * 299 + Double(g) * 587 + Double(b) * 114) / 1000
        return brightness > 150 ? .black : .white
    }
}
