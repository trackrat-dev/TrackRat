import SwiftUI
import MapKit

struct RouteStatusView: View {
    let context: RouteStatusContext
    @StateObject private var viewModel: RouteStatusViewModel
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared

    /// Locally-edited copies of matching subscriptions, keyed by ID.
    @State private var editedSubscriptions: [UUID: RouteAlertSubscription] = [:]

    /// Draft subscription used when no matching subscription exists yet.
    @State private var draftSubscription: RouteAlertSubscription?

    /// Selected history time period for the segmented picker.
    @State private var selectedHistoryPeriod: HistoryPeriod = .hour

    /// Preferred highlight mode derived from this route's data source
    private var preferredMode: SegmentHighlightMode {
        TrainSystem(rawValue: context.dataSource)?.preferredHighlightMode ?? .delays
    }

    /// Matching subscriptions from the service.
    private var matchingSubscriptions: [RouteAlertSubscription] {
        alertService.subscriptions(for: context)
    }

    /// Whether the user is currently subscribed to alerts for this route.
    private var isSubscribed: Bool {
        !matchingSubscriptions.isEmpty
    }

    init(context: RouteStatusContext) {
        self.context = context
        self._viewModel = StateObject(wrappedValue: RouteStatusViewModel(context: context))
    }

    /// Train selected for detail sheet
    @State private var selectedTrain: TrainV2?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    mapSection
                    operationsSummarySection
                    historySections
                    alertSubscriptionSection
                    upcomingTrainsSection
                    serviceAlertsSection
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
                // Initialize draft subscription for alert config if not yet subscribed
                if matchingSubscriptions.isEmpty && draftSubscription == nil,
                   let from = context.fromStationCode, let to = context.toStationCode {
                    draftSubscription = RouteAlertSubscription(
                        dataSource: context.dataSource,
                        fromStationCode: from,
                        toStationCode: to,
                        activeDays: 0
                    )
                }
                await viewModel.loadData()
            }
            .onDisappear {
                // Persist any edited subscriptions back to the service
                guard !editedSubscriptions.isEmpty else { return }
                for (_, edited) in editedSubscriptions {
                    alertService.updateSubscription(edited)
                }
                syncIfPossible()
            }
            .sheet(item: $selectedTrain) { train in
                NavigationStack {
                    TrainDetailsView(
                        trainNumber: train.trainId,
                        fromStation: context.effectiveFromStation,
                        journeyDate: train.journeyDate,
                        dataSource: train.dataSource,
                        isSheet: true
                    )
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            }
        }
    }

    // MARK: - Alert Subscription Section

    @ViewBuilder
    private var alertSubscriptionSection: some View {
        if context.fromStationCode != nil && context.toStationCode != nil {
            AlertConfigurationSection(subscription: alertConfigBinding)
                .onChange(of: alertConfigBinding.wrappedValue.activeDays) { _, newDays in
                    handleActiveDaysChange(newDays)
                }
            DigestConfigurationSection(subscription: alertConfigBinding)
        }
    }

    /// Single binding for alert configuration.
    /// Uses the first matching subscription (syncing edits to all), or the draft if none exist.
    private var alertConfigBinding: Binding<RouteAlertSubscription> {
        if let first = matchingSubscriptions.first {
            return Binding(
                get: { editedSubscriptions[first.id] ?? first },
                set: { newValue in
                    // Apply edits to all matching subscriptions
                    for sub in matchingSubscriptions {
                        let edited = RouteAlertSubscription.copySettings(from: newValue, to: editedSubscriptions[sub.id] ?? sub)
                        editedSubscriptions[sub.id] = edited
                    }
                }
            )
        } else {
            return Binding(
                get: {
                    // Draft is initialized in .task; fallback should never be needed
                    draftSubscription ?? RouteAlertSubscription(
                        dataSource: context.dataSource,
                        fromStationCode: context.fromStationCode ?? "",
                        toStationCode: context.toStationCode ?? "",
                        activeDays: 0
                    )
                },
                set: { draftSubscription = $0 }
            )
        }
    }

    /// Handle active days changes: auto-subscribe when going non-zero, auto-unsubscribe when zero.
    private func handleActiveDaysChange(_ newDays: Int) {
        guard let from = context.fromStationCode, let to = context.toStationCode else { return }

        if newDays > 0 && !isSubscribed {
            // Auto-subscribe — use draft or create a fresh template
            let template = draftSubscription ?? RouteAlertSubscription(
                dataSource: context.dataSource,
                fromStationCode: from,
                toStationCode: to,
                activeDays: newDays
            )
            alertService.addStationPairSubscriptions(template: template)
            // Move settings into edited subscriptions for the newly-created subs
            for sub in alertService.subscriptions(for: context) {
                var edited = RouteAlertSubscription.copySettings(from: template, to: sub)
                edited.activeDays = newDays
                editedSubscriptions[sub.id] = edited
                alertService.updateSubscription(edited)
            }
            draftSubscription = nil
            syncIfPossible()
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } else if newDays == 0 && isSubscribed {
            // Auto-unsubscribe — reset draft for potential re-subscribe
            for sub in matchingSubscriptions {
                alertService.removeSubscription(sub)
            }
            editedSubscriptions.removeAll()
            draftSubscription = RouteAlertSubscription(
                dataSource: context.dataSource,
                fromStationCode: from,
                toStationCode: to,
                activeDays: 0
            )
            syncIfPossible()
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
    }


    private func syncIfPossible() {
        Task { @MainActor in
            guard let token = AppDelegate.deviceToken else { return }
            await alertService.syncWithBackend(apnsToken: token)
        }
    }

    /// Dismiss this sheet and navigate to the full departures list in the main app.
    private func navigateToAllDepartures() {
        guard let to = context.effectiveToStation,
              let from = context.effectiveFromStation else { return }
        let destination = Stations.displayName(for: to)
        // Use pendingNavigation so the main NavigationStack handles it after sheet dismisses
        dismiss()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            appState.pendingNavigation = .trainList(
                destination: destination,
                departureStationCode: from
            )
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

    // MARK: - Service Alerts Section

    @ViewBuilder
    private var serviceAlertsSection: some View {
        if !viewModel.serviceAlerts.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label("Service Alerts (\(viewModel.serviceAlerts.count))", systemImage: "exclamationmark.triangle.fill")
                    .font(.headline)
                    .foregroundColor(.orange)

                ForEach(viewModel.serviceAlerts) { alert in
                    ServiceAlertCard(alert: alert)
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Upcoming Trains Section

    @ViewBuilder
    private var upcomingTrainsSection: some View {
        if !viewModel.upcomingTrains.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Upcoming Trains")
                    .font(.headline)

                ForEach(viewModel.upcomingTrains.prefix(3)) { train in
                    Button {
                        selectedTrain = train
                    } label: {
                        UpcomingTrainRow(train: train, dataSource: context.dataSource)
                    }
                    .buttonStyle(.plain)
                }

                if context.effectiveFromStation != nil && context.effectiveToStation != nil {
                    Button {
                        navigateToAllDepartures()
                    } label: {
                        HStack {
                            Text("View All Departures")
                                .font(.subheadline.bold())
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                        }
                        .foregroundColor(.orange)
                        .padding(.top, 4)
                    }
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - History Sections (Unified with Segmented Picker)

    @ViewBuilder
    private var historySections: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Route Performance")
                    .font(.headline)
                Spacer()
                Picker("", selection: $selectedHistoryPeriod) {
                    ForEach(HistoryPeriod.allCases, id: \.self) { period in
                        Text(period.label).tag(period)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 200)
            }

            switch selectedHistoryPeriod {
            case .hour:
                historyPeriodContent(
                    data: viewModel.pastHourData,
                    isLoading: viewModel.isLoadingPastHour,
                    error: viewModel.pastHourError,
                    hours: 1
                )
            case .day:
                historyPeriodContent(
                    data: viewModel.past24HoursData,
                    isLoading: viewModel.isLoadingPast24Hours,
                    error: viewModel.past24HoursError,
                    hours: 24
                )
            case .week:
                historyPeriodContent(
                    data: viewModel.past7DaysData,
                    isLoading: viewModel.isLoadingPast7Days,
                    error: viewModel.past7DaysError,
                    hours: 168
                )
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }

    @ViewBuilder
    private func historyPeriodContent(
        data: RouteHistoricalData?,
        isLoading: Bool,
        error: String?,
        hours: Double
    ) -> some View {
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

    @ViewBuilder
    private func historyContent(_ history: RouteHistoricalData, hours: Double) -> some View {
        let total = history.route.totalTrains
        let freqColor = frequencyColor(totalTrains: total, baseline: history.route.baselineTrainCount)

        let stats = history.aggregateStats
        let onTimeValue = stats.onTimePercentage.map { "\(Int($0))%" } ?? "N/A"
        let onTimeColor = onTimePercentageColor(stats.onTimePercentage)

        if preferredMode == .health {
            // Frequency-focused stats for rapid transit (PATH, Subway, PATCO)
            HStack(spacing: 12) {
                statCard(
                    title: "Frequency",
                    value: formatFrequency(totalTrains: total, hours: hours),
                    color: freqColor
                )
                statCard(title: "On Time", value: onTimeValue, color: onTimeColor)
            }

            if stats.cancellationRate > 0 {
                HStack(spacing: 12) {
                    statCard(
                        title: "Cancelled",
                        value: "\(Int(stats.cancellationRate))%",
                        color: stats.cancellationRate <= 5 ? .green : .red
                    )
                }
            }
        } else {
            // Delay-focused stats for commuter/intercity rail
            HStack(spacing: 12) {
                statCard(title: "On Time", value: onTimeValue, color: onTimeColor)
                statCard(
                    title: "Cancelled",
                    value: "\(Int(stats.cancellationRate))%",
                    color: stats.cancellationRate <= 5 ? .green : .red
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
                        value: formatDelay(stats.averageDepartureDelayMinutes),
                        color: delayColor(stats.averageDepartureDelayMinutes)
                    )
                    delayStatCard(
                        title: "Avg Arrival Delay",
                        value: stats.averageDelayMinutes.map { formatDelay($0) } ?? "N/A",
                        color: delayColor(stats.averageDelayMinutes)
                    )
                }
            }

        }
    }

    /// Color for on-time percentage: green >= 80%, orange >= 50%, red < 50%, gray if no data.
    private func onTimePercentageColor(_ percentage: Double?) -> Color {
        guard let pct = percentage else { return .secondary }
        if pct >= 80 { return .green }
        if pct >= 50 { return .orange }
        return .red
    }

    /// Color for delay minutes: green <= 5m, orange <= 15m, red > 15m, gray if no data.
    private func delayColor(_ minutes: Double?) -> Color {
        guard let m = minutes else { return .secondary }
        if m <= 5 { return .green }
        if m <= 15 { return .orange }
        return .red
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

// MARK: - History Period

enum HistoryPeriod: CaseIterable {
    case hour, day, week

    var label: String {
        switch self {
        case .hour: return "Hour"
        case .day: return "Day"
        case .week: return "Week"
        }
    }
}

// MARK: - Service Alert Card

private struct ServiceAlertCard: View {
    let alert: V2ServiceAlert
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(alert.alertTypeLabel.uppercased())
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(alertTypeColor.opacity(0.2)))
                    .foregroundColor(alertTypeColor)

                if alert.isActiveNow && !alert.activePeriods.isEmpty {
                    Text("ACTIVE NOW")
                        .font(.caption2.bold())
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.green.opacity(0.2)))
                        .foregroundColor(.green)
                }

                Spacer()
            }

            if let periodText = alert.activePeriodText {
                HStack(spacing: 4) {
                    Image(systemName: "calendar")
                        .font(.caption2)
                    Text(periodText)
                        .font(.caption)
                    if alert.additionalPeriodCount > 0 {
                        Text("(+\(alert.additionalPeriodCount) more)")
                            .font(.caption)
                    }
                }
                .foregroundColor(.secondary)
            }

            Text(alert.headerText)
                .font(.subheadline)
                .foregroundColor(.primary)

            if let description = alert.descriptionText, !description.isEmpty {
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(isExpanded ? nil : 3)

                if description.count > 120 {
                    Button(isExpanded ? "Show Less" : "Show More") {
                        withAnimation { isExpanded.toggle() }
                    }
                    .font(.caption.bold())
                    .foregroundColor(.orange)
                }
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }

    private var alertTypeColor: Color {
        switch alert.alertType {
        case "planned_work": return .yellow
        case "alert": return .red
        case "elevator": return .blue
        default: return .orange
        }
    }
}

// MARK: - Upcoming Train Row

private struct UpcomingTrainRow: View {
    let train: TrainV2
    let dataSource: String

    /// Whether this transit system uses synthetic train IDs (e.g., subway, PATCO)
    private var useSyntheticId: Bool {
        TrainSystem.syntheticTrainIdSources.contains(dataSource)
    }

    var body: some View {
        HStack(spacing: 12) {
            // Line color indicator
            RoundedRectangle(cornerRadius: 2)
                .fill(Color(hex: train.line.color))
                .frame(width: 4, height: 40)

            VStack(alignment: .leading, spacing: 2) {
                if useSyntheticId {
                    Text(train.line.name)
                        .font(.subheadline.bold())
                } else {
                    Text("Train \(train.trainId)")
                        .font(.subheadline.bold())
                }
                HStack(spacing: 8) {
                    if let track = train.departure.track, !track.isEmpty {
                        Text("Track \(track)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    if train.isCancelled {
                        Text("Cancelled")
                            .font(.caption.bold())
                            .foregroundColor(.red)
                    }
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(departureTimeString)
                    .font(.subheadline.bold())
                delayBadge
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }

    private var departureTimeString: String {
        let time = train.departure.updatedTime ?? train.departure.scheduledTime
        guard let time = time else { return "--" }
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: time)
    }

    @ViewBuilder
    private var delayBadge: some View {
        if train.isCancelled {
            EmptyView()
        } else if train.departure.delayMinutes > 0 {
            Text("+\(train.departure.delayMinutes)m")
                .font(.caption.bold())
                .foregroundColor(.red)
        } else {
            Text("On Time")
                .font(.caption)
                .foregroundColor(.green)
        }
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

    // Service alerts (MTA systems only)
    @Published var serviceAlerts: [V2ServiceAlert] = []

    // Upcoming trains
    @Published var upcomingTrains: [TrainV2] = []

    /// Data sources that have service alert data
    private static let serviceAlertSystems: Set<String> = ["SUBWAY", "LIRR", "MNR"]

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
            group.addTask { await self.loadServiceAlerts() }
            group.addTask { await self.loadUpcomingTrains() }
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
                    routeStationCodes.contains(segment.fromStation.uppercased()) &&
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

    // MARK: - Service Alerts

    private func loadServiceAlerts() async {
        guard Self.serviceAlertSystems.contains(context.dataSource) else { return }
        do {
            let alerts = try await APIService.shared.fetchServiceAlerts(dataSource: context.dataSource)
            let relevantRouteIds = context.gtfsRouteIds
            if relevantRouteIds.isEmpty {
                // No line context — show all alerts for this data source
                serviceAlerts = alerts
            } else {
                // Filter to alerts affecting this route's line(s)
                serviceAlerts = alerts.filter { alert in
                    !Set(alert.affectedRouteIds).isDisjoint(with: relevantRouteIds)
                }
            }
        } catch {
            // Silent failure — section just won't appear
            print("⚠️ Failed to load service alerts: \(error.localizedDescription)")
        }
    }

    // MARK: - Upcoming Trains

    private func loadUpcomingTrains() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else { return }
        do {
            let dataSource = TrainSystem(rawValue: context.dataSource)
            let trains = try await APIService.shared.searchTrains(
                fromStationCode: from,
                toStationCode: to,
                dataSources: dataSource.map { Set([$0]) }
            )
            upcomingTrains = Array(trains.prefix(5))
        } catch {
            print("⚠️ Failed to load upcoming trains: \(error.localizedDescription)")
        }
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
    .environmentObject(AppState())
}
