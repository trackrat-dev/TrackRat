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
            WrappingHStackLayout(spacing: 3, rowSpacing: 3) {
                ForEach(lines, id: \.self) { line in
                    SubwayLineChip(line: line, size: size)
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(accessibilityLabel)
        }
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

/// Station labels with their transit badges. The badge area is constrained to
/// half of the available width and wraps, so the station name keeps priority.
struct StationNameWithBadges: View {
    let name: String
    var stationCode: String? = nil
    var subwayLines: [String] = []
    var font: Font = .body
    var foregroundColor: Color = .white
    var chipSize: CGFloat = 14
    var badgeOpacity: Double = 1
    var includeSystemChips: Bool = true
    /// When true, the name uses `textProtected()` (one line, scales to 75%).
    /// Set false to render at the full font size with no line limit, matching
    /// callers whose original plain `Text` had neither modifier.
    var protectText: Bool = true

    var body: some View {
        // Don't wrap the Text in `.frame(maxWidth: .infinity)`: that makes its
        // ideal-width report `.infinity`, which collapses the layout's resolved
        // nameWidth to 0 and erases the station name whenever there are no
        // badges (e.g. non-subway stops in TrainDetailsView).
        StationNameBadgesLayout(spacing: 6) {
            Text(name)
                .font(font)
                .foregroundColor(foregroundColor)
                .lineLimit(protectText ? 1 : nil)
                .minimumScaleFactor(protectText ? 0.75 : 1.0)

            StationBadges(
                stationCode: stationCode,
                subwayLines: subwayLines,
                size: chipSize,
                includeSystemChips: includeSystemChips
            )
            .opacity(badgeOpacity)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct StationBadges: View {
    let stationCode: String?
    let subwayLines: [String]
    var size: CGFloat
    var includeSystemChips: Bool

    private var systems: [TrainSystem] {
        guard includeSystemChips, let stationCode else { return [] }
        return Stations.systemsForStation(stationCode)
            .filter { $0 != .subway }
            .sorted { $0.chipLabel < $1.chipLabel }
    }

    var body: some View {
        if !subwayLines.isEmpty || !systems.isEmpty {
            WrappingHStackLayout(spacing: 3, rowSpacing: 3) {
                ForEach(subwayLines, id: \.self) { line in
                    SubwayLineChip(line: line, size: size)
                }

                ForEach(systems) { system in
                    SystemPill(system: system, size: size)
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(accessibilityLabel)
        }
    }

    private var accessibilityLabel: String {
        let lineLabel = subwayLines.isEmpty ? nil : "lines: \(subwayLines.joined(separator: ", "))"
        let systemLabel = systems.isEmpty ? nil : "systems: \(systems.map(\.displayName).joined(separator: ", "))"
        return [lineLabel, systemLabel].compactMap { $0 }.joined(separator: "; ")
    }
}

private struct SubwayLineChip: View {
    let line: String
    var size: CGFloat

    var body: some View {
        let hex = SubwayLines.lineColor[line] ?? "#666666"
        let bg = Color(hex: hex)
        let fg = SubwayLineChips.contrastingTextColor(forHex: hex)
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
}

private struct StationNameBadgesLayout: Layout {
    var spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard subviews.count == 2 else { return .zero }

        let proposedWidth = resolvedWidth(proposal.width, fallback: idealWidth(for: subviews))
        let sizes = measuredSizes(for: subviews, width: proposedWidth)

        return CGSize(
            width: proposedWidth,
            height: max(sizes.name.height, sizes.badges.height)
        )
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard subviews.count == 2 else { return }

        let width = resolvedWidth(bounds.width, fallback: idealWidth(for: subviews))
        let sizes = measuredSizes(for: subviews, width: width)
        let nameY = bounds.minY + (bounds.height - sizes.name.height) / 2
        let badgesY = bounds.minY + (bounds.height - sizes.badges.height) / 2

        subviews[0].place(
            at: CGPoint(x: bounds.minX, y: nameY),
            proposal: ProposedViewSize(width: sizes.name.width, height: sizes.name.height)
        )

        subviews[1].place(
            at: CGPoint(x: bounds.minX + sizes.name.width + sizes.spacing, y: badgesY),
            proposal: ProposedViewSize(width: sizes.badges.width, height: sizes.badges.height)
        )
    }

    private func resolvedWidth(_ width: CGFloat?, fallback: CGFloat) -> CGFloat {
        guard let width, width.isFinite else {
            return fallback.isFinite ? max(0, fallback) : 0
        }
        return max(0, width)
    }

    private func measuredSizes(for subviews: Subviews, width: CGFloat) -> (name: CGSize, badges: CGSize, spacing: CGFloat) {
        let unconstrainedBadges = subviews[1].sizeThatFits(.unspecified)
        let hasBadges = unconstrainedBadges.width > 0 && unconstrainedBadges.height > 0
        let activeSpacing = hasBadges ? spacing : 0
        let contentWidth = max(0, width - activeSpacing)
        let badgeMaxWidth = hasBadges ? contentWidth * 0.5 : 0
        let badges = hasBadges
            ? subviews[1].sizeThatFits(ProposedViewSize(width: badgeMaxWidth, height: nil))
            : .zero
        let badgeWidth = min(badges.width, badgeMaxWidth)
        let nameWidth = hasBadges ? max(contentWidth - badgeWidth, contentWidth * 0.5) : width
        let name = subviews[0].sizeThatFits(ProposedViewSize(width: nameWidth, height: nil))

        return (
            CGSize(width: nameWidth, height: name.height),
            CGSize(width: badgeWidth, height: badges.height),
            activeSpacing
        )
    }

    private func idealWidth(for subviews: Subviews) -> CGFloat {
        let name = subviews[0].sizeThatFits(.unspecified)
        let badges = subviews[1].sizeThatFits(.unspecified)
        let activeSpacing = badges.width > 0 && badges.height > 0 ? spacing : 0
        return name.width + activeSpacing + badges.width
    }
}

private struct WrappingHStackLayout: Layout {
    var spacing: CGFloat
    var rowSpacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = rows(for: subviews, maxWidth: proposal.width)
        return CGSize(width: rows.width, height: rows.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = rows(for: subviews, maxWidth: bounds.width)
        var y = bounds.minY

        for row in rows.items {
            var x = bounds.minX
            for item in row.items {
                subviews[item.index].place(
                    at: CGPoint(x: x, y: y),
                    proposal: ProposedViewSize(width: item.size.width, height: item.size.height)
                )
                x += item.size.width + spacing
            }
            y += row.height + rowSpacing
        }
    }

    private func rows(for subviews: Subviews, maxWidth: CGFloat?) -> (items: [Row], width: CGFloat, height: CGFloat) {
        let availableWidth = maxWidth ?? .greatestFiniteMagnitude
        var rows: [Row] = []
        var current = Row()

        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            let nextWidth = current.items.isEmpty ? size.width : current.width + spacing + size.width

            if !current.items.isEmpty && nextWidth > availableWidth {
                rows.append(current)
                current = Row()
            }

            current.append(Item(index: index, size: size), spacing: spacing)
        }

        if !current.items.isEmpty {
            rows.append(current)
        }

        let width = min(rows.map(\.width).max() ?? 0, availableWidth)
        let height = rows.reduce(0) { total, row in
            total + row.height
        } + CGFloat(max(0, rows.count - 1)) * rowSpacing

        return (rows, width, height)
    }

    private struct Item {
        let index: Int
        let size: CGSize
    }

    private struct Row {
        var items: [Item] = []
        var width: CGFloat = 0
        var height: CGFloat = 0

        mutating func append(_ item: Item, spacing: CGFloat) {
            width += items.isEmpty ? item.size.width : spacing + item.size.width
            height = max(height, item.size.height)
            items.append(item)
        }
    }
}

#Preview {
    VStack(alignment: .leading, spacing: 12) {
        SubwayLineChips(lines: ["N", "W"])
        SubwayLineChips(lines: ["1", "2", "3"])
        SubwayLineChips(lines: ["A", "C", "E"])
        SubwayLineChips(lines: ["B", "D", "F", "M"])
        SubwayLineChips(lines: ["1", "2", "3", "4", "5", "6", "A", "B", "C", "D"])
        StationNameWithBadges(
            name: "Times Sq-42 St",
            stationCode: "S127",
            subwayLines: ["1", "2", "3", "7", "N", "Q", "R", "W", "S"]
        )
        SubwayLineChips(lines: [])
    }
    .padding()
    .background(Color.black)
}
