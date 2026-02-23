import SwiftUI
import MapKit

struct RouteStatusView: View {
    let context: RouteStatusContext
    @StateObject private var viewModel: RouteStatusViewModel
    @Environment(\.dismiss) private var dismiss

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
                    historySection
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
                    stations: viewModel.journeyStations,
                    trainPositions: [],
                    onSegmentTap: { _ in }
                )
                .frame(height: 200)
                .cornerRadius(12)

                CompactCongestionLegend()
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

    // MARK: - History Section

    @ViewBuilder
    private var historySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("7-Day Performance")
                .font(.headline)

            if viewModel.isLoadingHistory {
                ProgressView()
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else if let history = viewModel.historicalData {
                historyContent(history)
            } else if let error = viewModel.historyError {
                Text("Could not load history: \(error)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }

    @ViewBuilder
    private func historyContent(_ history: RouteHistoricalData) -> some View {
        // Stat cards
        HStack(spacing: 12) {
            statCard(
                title: "On Time",
                value: "\(Int(history.aggregateStats.onTimePercentage))%",
                color: history.aggregateStats.onTimePercentage >= 80 ? .green : .orange
            )
            statCard(
                title: "Avg Delay",
                value: "\(Int(history.aggregateStats.averageDelayMinutes))m",
                color: history.aggregateStats.averageDelayMinutes <= 5 ? .green : .orange
            )
            statCard(
                title: "Cancelled",
                value: "\(Int(history.aggregateStats.cancellationRate * 100))%",
                color: history.aggregateStats.cancellationRate <= 0.05 ? .green : .red
            )
        }

        // Delay breakdown bar
        let breakdown = history.aggregateStats.delayBreakdown
        let total = history.route.totalTrains
        DelayPerformanceBar(
            label: "Delay Breakdown",
            stats: DelayStats(
                onTime: breakdown.onTime,
                slight: breakdown.slight,
                significant: breakdown.significant,
                major: breakdown.major,
                total: total,
                avgDelay: Int(history.aggregateStats.averageDelayMinutes)
            )
        )
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

    // History state
    @Published var historicalData: RouteHistoricalData?
    @Published var isLoadingHistory = false
    @Published var historyError: String?

    init(context: RouteStatusContext) {
        self.context = context
    }

    func loadData() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.loadCongestionMap() }
            group.addTask { await self.loadHistory() }
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

    private func loadHistory() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else {
            historyError = "No station pair available"
            return
        }

        isLoadingHistory = true
        defer { isLoadingHistory = false }

        do {
            historicalData = try await APIService.shared.fetchRouteHistoricalData(
                from: from,
                to: to,
                dataSource: context.dataSource,
                days: 7
            )
        } catch {
            historyError = error.localizedDescription
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
