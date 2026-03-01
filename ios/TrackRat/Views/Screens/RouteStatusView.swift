import SwiftUI
import MapKit

struct RouteStatusView: View {
    let context: RouteStatusContext
    @StateObject private var viewModel: RouteStatusViewModel
    @Environment(\.dismiss) private var dismiss

    /// Preferred highlight mode derived from this route's data source
    private var preferredMode: SegmentHighlightMode {
        TrainSystem(rawValue: context.dataSource)?.preferredHighlightMode ?? .delays
    }

    init(context: RouteStatusContext) {
        self.context = context
        self._viewModel = StateObject(wrappedValue: RouteStatusViewModel(context: context))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    mapSection
                    operationsSummarySection
                    historySections
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle(context.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .task {
                await viewModel.loadData()
            }
        }
    }

    // MARK: - Map Section

    @ViewBuilder
    private var mapSection: some View {
        VStack(spacing: 8) {
            if viewModel.isLoadingMap {
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
                    .frame(height: 200)
                    .overlay(ProgressView().progressViewStyle(CircularProgressViewStyle(tint: .orange)))
            } else if !viewModel.filteredSegments.isEmpty {
                CongestionMapKitView(
                    region: $viewModel.mapRegion,
                    segments: viewModel.filteredSegments,
                    stations: [],
                    trainPositions: [],
                    highlightMode: .delays,  // "on" — per-segment coloring is automatic
                    onSegmentTap: { _ in }
                )
                .frame(height: 200)
                .cornerRadius(12)

                // Legend intentionally omitted — map colors are self-explanatory
            } else if viewModel.mapError != nil {
                ContentUnavailableView("Map Unavailable", systemImage: "map", description: Text("Could not load congestion data"))
                    .frame(height: 200)
            }
        }
    }

    // MARK: - Operations Summary Section

    private var operationsSummarySection: some View {
        OperationsSummaryView(
            scope: .route,
            fromStation: context.effectiveFromStation,
            toStation: context.effectiveToStation
        )
    }

    // MARK: - History Sections (Past Hour, Past 24 Hours, Past 7 Days)

    @ViewBuilder
    private var historySections: some View {
        timePeriodSection(
            title: "Past Hour",
            data: viewModel.pastHourData,
            isLoading: viewModel.isLoadingPastHour,
            error: viewModel.pastHourError,
            hours: 1
        )
        timePeriodSection(
            title: "Past 24 Hours",
            data: viewModel.past24HoursData,
            isLoading: viewModel.isLoadingPast24Hours,
            error: viewModel.past24HoursError,
            hours: 24
        )
        timePeriodSection(
            title: "Past 7 Days",
            data: viewModel.past7DaysData,
            isLoading: viewModel.isLoadingPast7Days,
            error: viewModel.past7DaysError,
            hours: 168
        )
    }

    @ViewBuilder
    private func timePeriodSection(
        title: String,
        data: RouteHistoricalData?,
        isLoading: Bool,
        error: String?,
        hours: Double
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)

            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else if let history = data, history.route.totalTrains > 0 {
                historyContent(history, hours: hours)
            } else if let error = error {
                Text("Could not load history: \(error)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
            } else {
                Text("No trains in this time period")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }

    @ViewBuilder
    private func historyContent(_ history: RouteHistoricalData, hours: Double) -> some View {
        let total = history.route.totalTrains
        let freqColor = frequencyColor(totalTrains: total, baseline: history.route.baselineTrainCount)

        if preferredMode == .health {
            // Frequency-focused stats for rapid transit (PATH, Subway, PATCO)
            HStack(spacing: 12) {
                statCard(
                    title: "Frequency",
                    value: formatFrequency(totalTrains: total, hours: hours),
                    color: freqColor
                )
                statCard(
                    title: "On Time",
                    value: "\(Int(history.aggregateStats.onTimePercentage))%",
                    color: history.aggregateStats.onTimePercentage >= 80 ? .green : .orange
                )
            }

            if history.aggregateStats.cancellationRate > 0 {
                HStack(spacing: 12) {
                    statCard(
                        title: "Cancelled",
                        value: "\(Int(history.aggregateStats.cancellationRate))%",
                        color: history.aggregateStats.cancellationRate <= 5 ? .green : .red
                    )
                }
            }
        } else {
            // Delay-focused stats for commuter/intercity rail
            HStack(spacing: 12) {
                statCard(
                    title: "On Time",
                    value: "\(Int(history.aggregateStats.onTimePercentage))%",
                    color: history.aggregateStats.onTimePercentage >= 80 ? .green : .orange
                )
                statCard(
                    title: "Cancelled",
                    value: "\(Int(history.aggregateStats.cancellationRate))%",
                    color: history.aggregateStats.cancellationRate <= 5 ? .green : .red
                )
                statCard(
                    title: "Frequency",
                    value: formatFrequency(totalTrains: total, hours: hours),
                    color: freqColor
                )
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Delay Statistics")
                    .font(.subheadline.bold())

                HStack(spacing: 12) {
                    delayStatCard(
                        title: "Avg Departure Delay",
                        value: formatDelay(history.aggregateStats.averageDepartureDelayMinutes),
                        color: history.aggregateStats.averageDepartureDelayMinutes <= 5 ? .green : .orange
                    )
                    delayStatCard(
                        title: "Avg Arrival Delay",
                        value: formatDelay(history.aggregateStats.averageDelayMinutes),
                        color: history.aggregateStats.averageDelayMinutes <= 5 ? .green : .orange
                    )
                }
            }

        }
    }

    /// Color for frequency based on comparison to historical baseline.
    /// Uses the same thresholds as CongestionSegment.frequencyDisplayColor.
    private func frequencyColor(totalTrains: Int, baseline: Double?) -> Color {
        guard let baseline = baseline, baseline > 0 else { return .white }
        let factor = Double(totalTrains) / baseline
        if factor >= 0.9 { return .green }
        if factor >= 0.7 { return .yellow }
        if factor >= 0.5 { return .orange }
        return .red
    }

    private func formatDelay(_ minutes: Double) -> String {
        let rounded = Int(round(minutes))
        return "\(rounded)m"
    }

    private func formatFrequency(totalTrains: Int, hours: Double) -> String {
        let perHour = Double(totalTrains) / hours
        if perHour >= 1 {
            return perHour == perHour.rounded() ? "\(Int(perHour))/hr" : String(format: "%.1f/hr", perHour)
        } else {
            let perDay = perHour * 24
            return perDay == perDay.rounded() ? "\(Int(perDay))/day" : String(format: "%.1f/day", perDay)
        }
    }

    private func statCard(title: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2.bold())
                .foregroundColor(color)
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }

    private func delayStatCard(title: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.bold())
                .foregroundColor(color)
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }
}

// MARK: - View Model

@MainActor
final class RouteStatusViewModel: ObservableObject {
    let context: RouteStatusContext

    // Map state
    @Published var filteredSegments: [CongestionSegment] = []
    @Published var journeyStations: [JourneyStation] = []
    @Published var mapRegion = MKCoordinateRegion()
    @Published var isLoadingMap = false
    @Published var mapError: String?

    // History state - per-section loading and error
    @Published var pastHourData: RouteHistoricalData?
    @Published var past24HoursData: RouteHistoricalData?
    @Published var past7DaysData: RouteHistoricalData?
    @Published var isLoadingPastHour = false
    @Published var isLoadingPast24Hours = false
    @Published var isLoadingPast7Days = false
    @Published var pastHourError: String?
    @Published var past24HoursError: String?
    @Published var past7DaysError: String?

    init(context: RouteStatusContext) {
        self.context = context
    }

    func loadData() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.loadCongestionMap() }
            group.addTask { await self.loadAllHistory() }
        }
    }

    // MARK: - Congestion Map

    private func loadCongestionMap() async {
        isLoadingMap = true
        defer { isLoadingMap = false }

        do {
            let response = try await APIService.shared.fetchCongestionData(
                timeWindowHours: 1,
                maxPerSegment: 100,
                dataSource: context.dataSource
            )
            let routeStationCodes = Set(context.stationCodes.map { $0.uppercased() })

            if routeStationCodes.isEmpty {
                filteredSegments = response.aggregatedSegments
            } else {
                filteredSegments = response.aggregatedSegments.filter { segment in
                    routeStationCodes.contains(segment.fromStation.uppercased()) ||
                    routeStationCodes.contains(segment.toStation.uppercased())
                }
            }

            buildStationsFromSegments()
            setMapRegion()
        } catch {
            mapError = error.localizedDescription
        }
    }

    private func buildStationsFromSegments() {
        var seen = Set<String>()
        var stations: [JourneyStation] = []
        let routeCodes = context.stationCodes

        for segment in filteredSegments {
            for (code, name) in [(segment.fromStation, segment.fromStationName),
                                 (segment.toStation, segment.toStationName)] {
                guard !seen.contains(code),
                      let coordinate = Stations.getCoordinates(for: code) else { continue }
                seen.insert(code)
                stations.append(JourneyStation(
                    code: code,
                    name: name,
                    coordinate: coordinate,
                    isOrigin: code.uppercased() == routeCodes.first?.uppercased(),
                    isDestination: code.uppercased() == routeCodes.last?.uppercased()
                ))
            }
        }
        journeyStations = stations
    }

    private func setMapRegion() {
        guard !journeyStations.isEmpty else { return }
        let coordinates = journeyStations.map { $0.coordinate }
        let minLat = coordinates.map { $0.latitude }.min() ?? 0
        let maxLat = coordinates.map { $0.latitude }.max() ?? 0
        let minLon = coordinates.map { $0.longitude }.min() ?? 0
        let maxLon = coordinates.map { $0.longitude }.max() ?? 0

        let center = CLLocationCoordinate2D(
            latitude: (minLat + maxLat) / 2,
            longitude: (minLon + maxLon) / 2
        )
        let span = MKCoordinateSpan(
            latitudeDelta: (maxLat - minLat) * 1.4 + 0.01,
            longitudeDelta: (maxLon - minLon) * 1.4 + 0.01
        )
        mapRegion = MKCoordinateRegion(center: center, span: span)
    }

    // MARK: - History

    private func loadAllHistory() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else {
            pastHourError = "No station pair available"
            past24HoursError = "No station pair available"
            past7DaysError = "No station pair available"
            return
        }

        isLoadingPastHour = true
        isLoadingPast24Hours = true
        isLoadingPast7Days = true

        // Fetch all three time periods in parallel
        await withTaskGroup(of: Void.self) { group in
            group.addTask {
                do {
                    let data = try await APIService.shared.fetchRouteHistoricalData(
                        from: from, to: to,
                        dataSource: self.context.dataSource,
                        hours: 1
                    )
                    await MainActor.run {
                        self.pastHourData = data
                        self.isLoadingPastHour = false
                    }
                } catch {
                    await MainActor.run {
                        self.pastHourError = error.localizedDescription
                        self.isLoadingPastHour = false
                    }
                }
            }
            group.addTask {
                do {
                    let data = try await APIService.shared.fetchRouteHistoricalData(
                        from: from, to: to,
                        dataSource: self.context.dataSource,
                        hours: 24
                    )
                    await MainActor.run {
                        self.past24HoursData = data
                        self.isLoadingPast24Hours = false
                    }
                } catch {
                    await MainActor.run {
                        self.past24HoursError = error.localizedDescription
                        self.isLoadingPast24Hours = false
                    }
                }
            }
            group.addTask {
                do {
                    let data = try await APIService.shared.fetchRouteHistoricalData(
                        from: from, to: to,
                        dataSource: self.context.dataSource,
                        days: 7
                    )
                    await MainActor.run {
                        self.past7DaysData = data
                        self.isLoadingPast7Days = false
                    }
                } catch {
                    await MainActor.run {
                        self.past7DaysError = error.localizedDescription
                        self.isLoadingPast7Days = false
                    }
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    RouteStatusView(context: RouteStatusContext(
        dataSource: "NJT",
        lineId: nil,
        fromStationCode: "NY",
        toStationCode: "TR"
    ))
}
