import SwiftUI

struct HistoricalDataView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: HistoricalDataViewModel
    @Environment(\.dismiss) private var dismiss
    
    let train: TrainV2
    
    init(train: TrainV2, toStationCode: String? = nil) {
        self.train = train
        self._viewModel = StateObject(wrappedValue: HistoricalDataViewModel(train: train, toStationCode: toStationCode))
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Black gradient background
                TrackRatTheme.Colors.primaryBackground
                    .ignoresSafeArea()
                
                ScrollView {
                    if viewModel.isLoading {
                        TrackRatLoadingView(message: "Loading historical data...")
                            .frame(maxWidth: .infinity, minHeight: 400)
                    } else if let data = viewModel.historicalData {
                        let hasPerformanceData = data.trainStats != nil || data.lineStats != nil || data.destinationStats != nil
                        let hasTrackData = data.trainTrackStats != nil || data.lineTrackStats != nil || data.destinationTrackStats != nil
                        
                        if hasPerformanceData || hasTrackData {
                            VStack(spacing: 24) {
                                // On-time Performance
                                PerformanceSection(
                                    trainStats: data.trainStats,
                                    lineStats: data.lineStats,
                                    destinationStats: data.destinationStats,
                                    routeStats: data.routeStats,
                                    train: train,
                                    fromStationCode: appState.departureStationCode,
                                    toStationCode: viewModel.destinationStationCode,
                                    dataSource: data.dataSource
                                )
                                
                                // Track Usage
                                TrackUsageSection(
                                    trainStats: data.trainTrackStats,
                                    lineStats: data.lineTrackStats,
                                    destinationStats: data.destinationTrackStats,
                                    routeStats: data.routeTrackStats,
                                    train: train,
                                    fromStationCode: appState.departureStationCode,
                                    toStationCode: viewModel.destinationStationCode,
                                    dataSource: data.dataSource
                                )
                            }
                            .padding()
                        } else {
                            VStack(spacing: 16) {
                                Image(systemName: "chart.bar.xaxis")
                                    .font(.system(size: 60))
                                    .foregroundColor(.white.opacity(0.6))
                                
                                Text("No Historical Data")
                                    .font(.title2)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)
                                
                                Text("Historical data will appear here once trains complete their journeys on this route.")
                                    .font(.body)
                                    .foregroundColor(.white.opacity(0.8))
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal)
                            }
                            .frame(maxWidth: .infinity, minHeight: 400)
                        }
                    } else if let error = viewModel.error {
                        VStack(spacing: 16) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 60))
                                .foregroundColor(.orange)
                            
                            Text("Something went wrong")
                                .font(.title2)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            
                            Text(error)
                                .font(.body)
                                .foregroundColor(.white.opacity(0.8))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                            
                            Button("Try Again") {
                                Task {
                                    await viewModel.loadHistoricalData(fromStationCode: appState.departureStationCode, toStationCode: nil, includeRouteTrains: true)
                                }
                            }
                            .padding(.horizontal, 24)
                            .padding(.vertical, 12)
                            .background(Color.orange)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                            .font(.body.bold())
                        }
                        .frame(maxWidth: .infinity, minHeight: 400)
                        .padding()
                    }
                }
            }
            .navigationTitle("Historical Data (beta)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
            }
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .task {
            await viewModel.loadHistoricalData(fromStationCode: appState.departureStationCode, toStationCode: nil, includeRouteTrains: true)
        }
    }
}

// MARK: - Performance Section
struct PerformanceSection: View {
    let trainStats: DelayStats?
    let lineStats: DelayStats?
    let destinationStats: DelayStats?
    let routeStats: DelayStats?
    let train: TrainV2
    let fromStationCode: String?
    let toStationCode: String?
    let dataSource: String?
    
    var hasData: Bool {
        trainStats != nil || lineStats != nil || destinationStats != nil || routeStats != nil
    }
    
    var body: some View {
        if hasData {
            VStack(alignment: .leading, spacing: 16) {
                Text("On-time Performance")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                
                VStack(spacing: 20) {
                    if let stats = trainStats {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        DelayPerformanceBar(
                            label: "Train \(train.trainId) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    // Route-wide statistics (same service only)
                    if let stats = routeStats, let source = dataSource {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        let serviceLabel = source == "AMTRAK" ? "All Amtrak trains" : "All NJ Transit trains"
                        DelayPerformanceBar(
                            label: "\(serviceLabel) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    if let stats = lineStats {
                        DelayPerformanceBar(
                            label: "\(train.line) Line",
                            stats: stats
                        )
                    }
                    
                    if let stats = destinationStats {
                        DelayPerformanceBar(
                            label: "Trains to \(train.destination)",
                            stats: stats
                        )
                    }
                }
                .padding()
                .background(Color.white.opacity(0.9))
                .cornerRadius(16)
            }
        }
    }
}

// MARK: - Track Usage Section
struct TrackUsageSection: View {
    let trainStats: TrackStats?
    let lineStats: TrackStats?
    let destinationStats: TrackStats?
    let routeStats: TrackStats?
    let train: TrainV2
    let fromStationCode: String?
    let toStationCode: String?
    let dataSource: String?
    
    var hasData: Bool {
        trainStats != nil || lineStats != nil || destinationStats != nil || routeStats != nil
    }
    
    var body: some View {
        if hasData {
            VStack(alignment: .leading, spacing: 16) {
                Text("Track Usage")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                
                VStack(spacing: 20) {
                    if let stats = trainStats {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        TrackUsageBar(
                            label: "Train \(train.trainId) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    // Route-wide track usage (same service only)
                    if let stats = routeStats, let source = dataSource {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        let serviceLabel = source == "AMTRAK" ? "All Amtrak trains" : "All NJ Transit trains"
                        TrackUsageBar(
                            label: "\(serviceLabel) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    if let stats = lineStats {
                        TrackUsageBar(
                            label: "\(train.line) Line",
                            stats: stats
                        )
                    }
                    
                    if let stats = destinationStats {
                        TrackUsageBar(
                            label: "Trains to \(train.destination)",
                            stats: stats
                        )
                    }
                }
                .padding()
                .background(Color.white.opacity(0.9))
                .cornerRadius(16)
            }
        }
    }
}

// MARK: - Delay Performance Bar
struct DelayPerformanceBar: View {
    let label: String
    let stats: DelayStats
    
    private let segments: [(name: String, value: Int, color: Color)] = [
        ("On Time", 0, .green),
        ("Slight", 0, .yellow),
        ("Significant", 0, .orange),
        ("Major", 0, .red)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.headline)
                .foregroundColor(.black)
            
            // Bar visualization
            GeometryReader { geometry in
                HStack(spacing: 1) {
                    if stats.onTime > 0 {
                        Rectangle()
                            .fill(Color.green)
                            .frame(width: geometry.size.width * CGFloat(stats.onTime) / 100)
                            .overlay(
                                Text("\(stats.onTime)%")
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .opacity(stats.onTime > 5 ? 1 : 0)
                            )
                    }
                    
                    if stats.slight > 0 {
                        Rectangle()
                            .fill(Color.yellow)
                            .frame(width: geometry.size.width * CGFloat(stats.slight) / 100)
                            .overlay(
                                Text("\(stats.slight)%")
                                    .font(.caption)
                                    .foregroundColor(.black)
                                    .opacity(stats.slight > 5 ? 1 : 0)
                            )
                    }
                    
                    if stats.significant > 0 {
                        Rectangle()
                            .fill(Color.orange)
                            .frame(width: geometry.size.width * CGFloat(stats.significant) / 100)
                            .overlay(
                                Text("\(stats.significant)%")
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .opacity(stats.significant > 5 ? 1 : 0)
                            )
                    }
                    
                    if stats.major > 0 {
                        Rectangle()
                            .fill(Color.red)
                            .frame(width: geometry.size.width * CGFloat(stats.major) / 100)
                            .overlay(
                                Text("\(stats.major)%")
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .opacity(stats.major > 5 ? 1 : 0)
                            )
                    }
                }
                .frame(height: 24)
                .cornerRadius(4)
            }
            .frame(height: 24)
            
            Text("\(stats.total) trips, avg \(stats.avgDelay)min delay")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Track Usage Bar
struct TrackUsageBar: View {
    let label: String
    let stats: TrackStats
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.headline)
                .foregroundColor(.black)
            
            // Bar visualization
            GeometryReader { geometry in
                HStack(spacing: 1) {
                    ForEach(stats.tracks, id: \.track) { trackData in
                        Rectangle()
                            .fill(trackColor(for: trackData.track))
                            .frame(width: geometry.size.width * CGFloat(trackData.percentage) / 100)
                            .overlay(
                                Text(trackData.track)
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .opacity(trackData.percentage > 5 ? 1 : 0)
                            )
                    }
                }
                .frame(height: 24)
                .cornerRadius(4)
            }
            .frame(height: 24)
            
            Text("\(stats.total) trips across \(stats.tracks.count) tracks")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
    
    private func trackColor(for track: String) -> Color {
        guard let trackNumber = Int(track), trackNumber >= 1, trackNumber <= 21 else {
            return .gray
        }
        
        let hue = Double((trackNumber - 1) * 360 / 21) / 360.0
        return Color(hue: hue, saturation: 0.75, brightness: 0.55)
    }
}

// MARK: - View Model
@MainActor
class HistoricalDataViewModel: ObservableObject {
    @Published var historicalData: HistoricalData?
    @Published var isLoading = false
    @Published var error: String?
    
    private let train: TrainV2
    private let toStationCode: String?
    private let apiService = APIService.shared
    
    init(train: TrainV2, toStationCode: String? = nil) {
        self.train = train
        // Only apply fallback when toStationCode is truly nil
        if let userDestination = toStationCode {
            self.toStationCode = userDestination
        } else {
            self.toStationCode = Stations.getStationCode(train.destination)
        }
    }
    
    var destinationStationCode: String? {
        return toStationCode
    }
    
    func loadHistoricalData(fromStationCode: String? = nil, toStationCode: String? = nil, includeRouteTrains: Bool = false) async {
        isLoading = true
        error = nil
        
        // Validate from station code
        guard let fromCode = fromStationCode else {
            print("❌ Error: Missing fromStationCode in loadHistoricalData")
            self.error = "Unable to load historical data: departure station not specified"
            isLoading = false
            return
        }
        
        // Use provided toStationCode or fall back to stored value
        guard let toCode = toStationCode ?? self.toStationCode else {
            print("❌ Error: Missing toStationCode in loadHistoricalData for train destination: \(train.destination)")
            self.error = "Cannot determine destination station code for '\(train.destination)'"
            isLoading = false
            return
        }
        
        // Ensure from and to stations are different
        guard fromCode != toCode else {
            print("❌ Error: fromStationCode and toStationCode are the same: \(fromCode)")
            self.error = "Historical data requires different departure and destination stations"
            isLoading = false
            return
        }
        
        do {
            // Determine data source from train
            let dataSource = train.trainClass == "Amtrak" ? "AMTRAK" : "NJT"
            
            // Use new route-based API
            let routeData = try await apiService.fetchRouteHistoricalData(
                from: fromCode,
                to: toCode,
                dataSource: dataSource,
                highlightTrain: train.trainId,
                days: 365
            )
            
            // Convert RouteHistoricalData to HistoricalData format
            historicalData = convertRouteDataToHistoricalData(routeData)
            
        } catch {
            print("❌ Error loading historical data: \(error)")
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    // MARK: - Data Conversion Helper
    
    private func convertRouteDataToHistoricalData(_ routeData: RouteHistoricalData) -> HistoricalData {
        // Convert route aggregate stats to route stats
        let routeStats = DelayStats(
            onTime: routeData.aggregateStats.delayBreakdown.onTime,
            slight: routeData.aggregateStats.delayBreakdown.slight,
            significant: routeData.aggregateStats.delayBreakdown.significant,
            major: routeData.aggregateStats.delayBreakdown.major,
            total: routeData.route.totalTrains,
            avgDelay: Int(routeData.aggregateStats.averageDelayMinutes.rounded())
        )
        
        // Convert route track usage to route track stats
        let routeTrackStats: TrackStats?
        if !routeData.aggregateStats.trackUsageAtOrigin.isEmpty {
            let tracks = routeData.aggregateStats.trackUsageAtOrigin
                .sorted { $0.value > $1.value }  // Sort by usage percentage descending
                .map { (track: $0.key, percentage: $0.value, count: Int(Double(routeData.route.totalTrains) * Double($0.value) / 100)) }
            
            routeTrackStats = TrackStats(
                tracks: tracks,
                total: routeData.route.totalTrains
            )
        } else {
            routeTrackStats = nil
        }
        
        // Convert highlighted train stats to train stats if available
        let trainStats: DelayStats?
        let trainTrackStats: TrackStats?
        
        if let highlighted = routeData.highlightedTrain {
            trainStats = DelayStats(
                onTime: highlighted.delayBreakdown.onTime,
                slight: highlighted.delayBreakdown.slight,
                significant: highlighted.delayBreakdown.significant,
                major: highlighted.delayBreakdown.major,
                total: 1, // Individual train has at most 1 journey in the time period
                avgDelay: Int(highlighted.averageDelayMinutes.rounded())
            )
            
            // Convert highlighted train track usage
            if !highlighted.trackUsageAtOrigin.isEmpty {
                let tracks = highlighted.trackUsageAtOrigin
                    .sorted { $0.value > $1.value }
                    .map { (track: $0.key, percentage: $0.value, count: Int(Double($0.value) / 100)) }
                
                trainTrackStats = TrackStats(
                    tracks: tracks,
                    total: 1
                )
            } else {
                trainTrackStats = nil
            }
        } else {
            trainStats = nil
            trainTrackStats = nil
        }
        
        return HistoricalData(
            trainStats: trainStats,
            lineStats: nil,  // Not provided by route API
            destinationStats: nil,  // Not provided by route API
            trainTrackStats: trainTrackStats,
            lineTrackStats: nil,  // Not provided by route API
            destinationTrackStats: nil,  // Not provided by route API
            routeStats: routeStats,
            routeTrackStats: routeTrackStats,
            dataSource: routeData.route.dataSource
        )
    }
}

#Preview {
    HistoricalDataView(train: TrainV2(
        trainId: "3923",
        line: LineInfo(code: "NEC", name: "Northeast Corridor", color: "#0066CC"),
        destination: "Trenton",
        departure: StationTiming(
            code: "NYP",
            name: "New York Penn Station",
            scheduledTime: Date(),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        ),
        arrival: nil,
        trainPosition: nil,
        dataFreshness: nil,
        isCancelled: false,
        isCompleted: false,
        dataSourceType: "realtime",
        stops: nil
    ))
}
