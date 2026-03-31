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
                // Translucent material background
                Color.clear
                    .background(.ultraThinMaterial)
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
                            .cornerRadius(TrackRatTheme.CornerRadius.sm)
                            .font(.body.bold())
                            .buttonStyle(.plain)
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

    private static func serviceDisplayName(for source: String) -> String {
        if let system = TrainSystem(rawValue: source) {
            return "All \(system.displayName) trains"
        }
        return "All NJ Transit trains"
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
                        let trainLabel = train.displayLabel
                        DelayPerformanceBar(
                            label: "\(trainLabel) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    // Route-wide statistics (same service only)
                    if let stats = routeStats, let source = dataSource {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        let serviceLabel = Self.serviceDisplayName(for: source)
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
                .cornerRadius(TrackRatTheme.CornerRadius.lg)
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

    private static func serviceDisplayName(for source: String) -> String {
        if let system = TrainSystem(rawValue: source) {
            return "All \(system.displayName) trains"
        }
        return "All NJ Transit trains"
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
                        let trainLabel = train.displayLabel
                        TrackUsageBar(
                            label: "\(trainLabel) (\(fromCode)→\(toCode))",
                            stats: stats
                        )
                    }
                    
                    // Route-wide track usage (same service only)
                    if let stats = routeStats, let source = dataSource {
                        let fromCode = fromStationCode ?? "?"
                        let toCode = toStationCode ?? "?"
                        let serviceLabel = Self.serviceDisplayName(for: source)
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
                .cornerRadius(TrackRatTheme.CornerRadius.lg)
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
                .cornerRadius(TrackRatTheme.CornerRadius.xs)
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
                .cornerRadius(TrackRatTheme.CornerRadius.xs)
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
            // Use train's data source directly (handles NJT, AMTRAK, PATH, PATCO)
            let dataSource = train.dataSource

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
        let breakdown = routeData.aggregateStats.delayBreakdown
        let routeStats = DelayStats(
            onTime: breakdown?.onTime ?? 0,
            slight: breakdown?.slight ?? 0,
            significant: breakdown?.significant ?? 0,
            major: breakdown?.major ?? 0,
            total: routeData.route.totalTrains,
            avgDelay: routeData.aggregateStats.averageDelayMinutes.map { Int($0.rounded()) } ?? 0
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
            let hlBreakdown = highlighted.delayBreakdown
            trainStats = DelayStats(
                onTime: hlBreakdown?.onTime ?? 0,
                slight: hlBreakdown?.slight ?? 0,
                significant: hlBreakdown?.significant ?? 0,
                major: hlBreakdown?.major ?? 0,
                total: 1, // Individual train has at most 1 journey in the time period
                avgDelay: highlighted.averageDelayMinutes.map { Int($0.rounded()) } ?? 0
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
        journeyDate: Date(),
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
        observationType: nil,
        isCancelled: false,
        cancellationReason: nil,
        isCompleted: false,
        dataSource: "NJT",
        stops: nil
    ))
}

// MARK: - Congestion Data View

struct CongestionDataView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: CongestionDataViewModel
    @Environment(\.dismiss) private var dismiss
    
    let train: TrainV2
    
    init(train: TrainV2, userOrigin: String? = nil, userDestination: String? = nil) {
        self.train = train
        self._viewModel = StateObject(wrappedValue: CongestionDataViewModel(
            train: train,
            userOrigin: userOrigin,
            userDestination: userDestination
        ))
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Translucent material background
                Color.clear
                    .background(.ultraThinMaterial)
                    .ignoresSafeArea()

                ScrollView {
                    if viewModel.isLoading {
                        TrackRatLoadingView(message: "Loading congestion data...")
                            .frame(maxWidth: .infinity, minHeight: 400)
                    } else if let segments = viewModel.relevantSegments, !segments.isEmpty {
                        VStack(spacing: 16) {
                            // Map view
                            JourneyCongestionMapView(
                                train: train,
                                userOrigin: viewModel.userOrigin,
                                userDestination: viewModel.userDestination,
                                onSegmentTap: { segment in
                                    guard appState.enableSegmentTap else { return }
                                    let route = RouteTopology.routeContaining(
                                        from: segment.fromStation,
                                        to: segment.toStation,
                                        dataSource: segment.dataSource
                                    )
                                    viewModel.routeStatusContext = RouteStatusContext(
                                        dataSource: segment.dataSource,
                                        lineId: route?.id,
                                        fromStationCode: segment.fromStation,
                                        toStationCode: segment.toStation
                                    )
                                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                }
                            )
                            .padding(.horizontal)
                            
                            // Header info

                            
                            // Route Cards Section
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("Route Segments")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(.white)
                                    Spacer()
                                }
                                .padding(.horizontal)
                                
                                ForEach(segments, id: \.id) { segment in
                                    Button {
                                        let route = RouteTopology.routeContaining(
                                            from: segment.fromStation,
                                            to: segment.toStation,
                                            dataSource: segment.dataSource
                                        )
                                        viewModel.routeStatusContext = RouteStatusContext(
                                            dataSource: segment.dataSource,
                                            lineId: route?.id,
                                            fromStationCode: segment.fromStation,
                                            toStationCode: segment.toStation
                                        )
                                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                    } label: {
                                        CongestionSegmentCard(segment: segment)
                                    }
                                    .buttonStyle(.plain)
                                    .padding(.horizontal)
                                }
                            }
                            
                            // Instructions
                            Text("Tap any route segment to see congestion details")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.6))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }
                        .padding(.top)
                    } else if viewModel.error != nil {
                        VStack(spacing: 16) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 60))
                                .foregroundColor(.orange)
                            
                            Text("Unable to load congestion data")
                                .font(.title2)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            
                            Text("Please try again later")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.8))
                            
                            Button("Try Again") {
                                Task {
                                    await viewModel.loadCongestionData()
                                }
                            }
                            .padding(.horizontal, 24)
                            .padding(.vertical, 12)
                            .background(Color.orange)
                            .foregroundColor(.white)
                            .cornerRadius(TrackRatTheme.CornerRadius.sm)
                            .font(.body.bold())
                            .buttonStyle(.plain)
                        }
                        .frame(maxWidth: .infinity, minHeight: 400)
                        .padding()
                    } else {
                        VStack(spacing: 16) {
                            Image(systemName: "arrow.triangle.branch")
                                .font(.system(size: 60))
                                .foregroundColor(.white.opacity(0.6))
                            
                            Text("No Route Data")
                                .font(.title2)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            
                            Text("Congestion data is not available for this route.")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.8))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }
                        .frame(maxWidth: .infinity, minHeight: 400)
                    }
                }
            }
            .navigationTitle("Route Congestion (beta)")
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
            .sheet(item: $viewModel.routeStatusContext) { context in
                RouteStatusView(context: context)
            }
        }
        .task {
            await viewModel.loadCongestionData()
        }
    }
}

// MARK: - Congestion Segment Card
struct CongestionSegmentCard: View {
    let segment: CongestionSegment
    
    var body: some View {
        HStack(spacing: 12) {
            Text("\(segment.fromStationDisplayName) → \(segment.toStationDisplayName)\(segment.averageTransitTimeText)\(segment.delayText)")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.white)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
            
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(segment.displayColor.opacity(0.2))
        .cornerRadius(TrackRatTheme.CornerRadius.sm)
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.sm)
                .stroke(segment.displayColor.opacity(0.4), lineWidth: 1)
        )
    }
}

// MARK: - Congestion Comparison Bar
struct CongestionComparisonBar: View {
    let segment: CongestionSegment
    
    private var delayMinutes: Int {
        Int(segment.averageDelayMinutes.rounded())
    }
    
    private var delayText: String {
        if delayMinutes > 0 {
            return "+\(delayMinutes) min delay"
        } else {
            return "On time"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Baseline: \(Int(segment.baselineMinutes.rounded())) min")
                    .font(.caption)
                    .foregroundColor(.black.opacity(0.6))
                
                Spacer()
                
                Text(delayText)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(segment.displayColor)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background bar
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 8)
                    
                    // Baseline indicator
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.gray.opacity(0.4))
                        .frame(width: geometry.size.width * (segment.baselineMinutes / segment.currentAverageMinutes), height: 8)
                    
                    // Current time bar
                    RoundedRectangle(cornerRadius: 4)
                        .fill(segment.displayColor.opacity(0.8))
                        .frame(width: geometry.size.width, height: 8)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: - Congestion Data View Model
@MainActor
class CongestionDataViewModel: ObservableObject {
    @Published var congestionData: CongestionMapResponse?
    @Published var relevantSegments: [CongestionSegment]?
    @Published var isLoading = false
    @Published var error: String?
    @Published var lastUpdated: Date?
    @Published var routeStatusContext: RouteStatusContext?
    
    private let train: TrainV2
    let userOrigin: String?
    let userDestination: String?
    private let apiService = APIService.shared
    
    init(train: TrainV2, userOrigin: String? = nil, userDestination: String? = nil) {
        self.train = train
        self.userOrigin = userOrigin
        self.userDestination = userDestination
    }
    
    func loadCongestionData() async {
        isLoading = true
        error = nil
        
        do {
            let trainSystem = TrainSystem(rawValue: train.dataSource)
            let systems: Set<TrainSystem>? = trainSystem.map { Set([$0]) }
            let response = try await apiService.fetchCongestionData(timeWindowHours: 2, systems: systems)
            congestionData = response
            lastUpdated = Date()
            
            // Filter segments relevant to the train's route
            filterRelevantSegments()
        } catch {
            print("❌ Error loading congestion data: \(error)")
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    private func filterRelevantSegments() {
        guard let congestionData = congestionData,
              let allStops = train.stops else {
            relevantSegments = nil
            return
        }
        
        let expectedDataSource = train.dataSource
        
        // Extract user's journey segment if available, otherwise use full route
        let journeyStops = extractUserJourneyStops(from: allStops) ?? allStops
        
        // Get station codes from the journey segment
        let stationCodes = journeyStops.map { $0.stationCode.uppercased() }
        
        // Filter segments that are valid forward paths in the journey AND match the train type
        let filtered = congestionData.aggregatedSegments.filter { segment in
            // First check if data source matches train type
            guard segment.dataSource.uppercased() == expectedDataSource else {
                return false
            }
            
            // Check if stations are in the journey with proper ordering
            let fromIndex = stationCodes.firstIndex(of: segment.fromStation.uppercased())
            let toIndex = stationCodes.firstIndex(of: segment.toStation.uppercased())
            
            // Include any segment where 'to' station comes after 'from' station
            if let fromIdx = fromIndex, let toIdx = toIndex, toIdx > fromIdx {
                return true
            }
            return false
        }
        
        // Sort segments by their appearance in the journey
        let sorted = filtered.sorted { seg1, seg2 in
            let idx1 = stationCodes.firstIndex(of: seg1.fromStation.uppercased()) ?? 0
            let idx2 = stationCodes.firstIndex(of: seg2.fromStation.uppercased()) ?? 0
            return idx1 < idx2
        }
        
        relevantSegments = sorted
    }
    
    private func extractUserJourneyStops(from allStops: [StopV2]) -> [StopV2]? {
        // If we don't have user journey info, return nil to use full route
        guard let userOrigin = userOrigin, let userDestination = userDestination else {
            return nil
        }

        // Find origin stop by station code
        guard let originIndex = allStops.firstIndex(where: { stop in
            Stations.areEquivalentStations(stop.stationCode, userOrigin)
        }) else {
            return nil
        }

        // Find destination stop by station code (reliable matching)
        guard let destinationIndex = allStops.firstIndex(where: { stop in
            Stations.areEquivalentStations(stop.stationCode, userDestination)
        }) else {
            return nil
        }

        // Ensure origin comes before destination
        guard originIndex <= destinationIndex else {
            return nil
        }

        // Return the journey segment (inclusive of both origin and destination)
        return Array(allStops[originIndex...destinationIndex])
    }
}
