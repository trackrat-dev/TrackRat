import SwiftUI

/// Renders MTA's colored line bullets (e.g., the orange `B`, the yellow `N/Q/R/W`)
/// as a row of small circular chips. Used to disambiguate same-name subway
/// stations in search results and to highlight transfer lines on stop cells.
///
/// Empty `lines` collapses to nothing rendered, so callers can call this
/// unconditionally without guarding.
struct SubwayLineChips: View {
    /// MTA bullets in display order — typically from `SubwayLines.lines(forStationCode:)`.
    let lines: [String]

    /// Diameter of each chip. The default size (16pt) sits comfortably next to
    /// `.subheadline` text. Use a smaller value in tight contexts (e.g. compact
    /// list rows) or larger in headers.
    var size: CGFloat = 16

    var body: some View {
        if !lines.isEmpty {
            HStack(spacing: 3) {
                ForEach(lines, id: \.self) { line in
                    chip(for: line)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(accessibilityLabel)
        }
    }

    @ViewBuilder
    private func chip(for line: String) -> some View {
        let hex = SubwayLines.lineColor[line] ?? "#666666"
        let bg = Color(hex: hex)
        let fg = Self.contrastingTextColor(forHex: hex)
        ZStack {
            Circle().fill(bg)
            Text(line)
                .font(.system(size: size * 0.62, weight: .heavy, design: .rounded))
                .foregroundColor(fg)
                .minimumScaleFactor(0.7)
                .lineLimit(1)
        }
        .frame(width: size, height: size)
    }

    private var accessibilityLabel: String {
        // VoiceOver: "lines: 1, 2, 3"
        "lines: \(lines.joined(separator: ", "))"
    }

    /// Picks black or white based on perceived luminance of the background hex.
    /// Matches the rule used elsewhere in the app (`LineSelectionView`).
    static func contrastingTextColor(forHex hexColor: String) -> Color {
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

#Preview {
    VStack(alignment: .leading, spacing: 12) {
        SubwayLineChips(lines: ["N", "W"])
        SubwayLineChips(lines: ["1", "2", "3"])
        SubwayLineChips(lines: ["A", "C", "E"])
        SubwayLineChips(lines: ["B", "D", "F", "M"])
        SubwayLineChips(lines: ["1", "2", "3", "4", "5", "6", "A", "B", "C", "D"])
        SubwayLineChips(lines: [])
    }
    .padding()
    .background(Color.black)
}
