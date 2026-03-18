import SwiftUI
import MapKit

struct RouteStatusView: View {
    let context: RouteStatusContext
    @StateObject private var viewModel: RouteStatusViewModel
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    /// Locally-edited copies of matching subscriptions, keyed by ID.
    @State private var editedSubscriptions: [UUID: RouteAlertSubscription] = [:]

    /// Draft subscription used when no matching subscription exists yet.
    @State private var draftSubscription: RouteAlertSubscription?

    @State private var showingPaywall = false

    /// Selected history time period for the segmented picker.
    @State private var selectedHistoryPeriod: HistoryPeriod = .hour

    /// Selected service alert filter (active vs upcoming).
    @State private var selectedAlertFilter: ServiceAlertFilter = .active

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
                    routeSettingsSection
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
            .sheet(isPresented: $showingPaywall) {
                PaywallView(context: .routeAlerts)
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
            // Check freemium limit before auto-subscribing
            if !subscriptionService.isPro
                && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit {
                // Reset activeDays so the UI reverts to "None" when paywall is dismissed
                draftSubscription?.activeDays = 0
                showingPaywall = true
                return
            }
            // Auto-subscribe — create both directions from draft or fresh template
            let template = draftSubscription ?? RouteAlertSubscription(
                dataSource: context.dataSource,
                fromStationCode: from,
                toStationCode: to,
                activeDays: newDays
            )
            let subAB = RouteAlertSubscription(
                dataSource: template.dataSource,
                fromStationCode: from,
                toStationCode: to,
                activeDays: template.activeDays,
                activeStartMinutes: template.activeStartMinutes,
                activeEndMinutes: template.activeEndMinutes,
                timezone: template.timezone,
                delayThresholdMinutes: template.delayThresholdMinutes,
                serviceThresholdPct: template.serviceThresholdPct,
                cancellationThresholdPct: template.cancellationThresholdPct,
                notifyCancellation: template.notifyCancellation,
                notifyDelay: template.notifyDelay,
                notifyRecovery: template.notifyRecovery,
                digestTimeMinutes: template.digestTimeMinutes
            )
            let subBA = RouteAlertSubscription(
                dataSource: template.dataSource,
                fromStationCode: to,
                toStationCode: from,
                activeDays: template.activeDays,
                activeStartMinutes: template.activeStartMinutes,
                activeEndMinutes: template.activeEndMinutes,
                timezone: template.timezone,
                delayThresholdMinutes: template.delayThresholdMinutes,
                serviceThresholdPct: template.serviceThresholdPct,
                cancellationThresholdPct: template.cancellationThresholdPct,
                notifyCancellation: template.notifyCancellation,
                notifyDelay: template.notifyDelay,
                notifyRecovery: template.notifyRecovery,
                digestTimeMinutes: template.digestTimeMinutes
            )
            alertService.addSubscriptions(subscriptionService.isPro ? [subAB, subBA] : [subAB])
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
        // Use pendingNavigation so the main NavigationStack handles it after sheets dismiss.
        // Setting pendingNavigation triggers TripSelectionView to dismiss its settings sheet,
        // while dismiss() closes this RouteStatusView sheet. The delay allows both to animate out.
        dismiss()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            appState.pendingNavigation = .trainList(
                destination: destination,
                departureStationCode: from
            )
        }
    }

    // MARK: - Route Settings Section

    @ViewBuilder
    private var routeSettingsSection: some View {
        if viewModel.showRouteSettings {
            VStack(alignment: .leading, spacing: 12) {
                Text("Route Settings")
                    .font(.headline)

                ForEach(viewModel.discoveredSystems) { systemInfo in
                    VStack(alignment: .leading, spacing: 8) {
                        // System header — tappable to toggle all lines
                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                viewModel.toggleSystem(systemInfo.system)
                            }
                        } label: {
                            HStack {
                                Image(systemName: systemInfo.system.icon)
                                    .font(.caption)
                                Text(systemInfo.system.displayName)
                                    .font(.subheadline.bold())
                                Spacer()
                            }
                            .foregroundColor(viewModel.isSystemEnabled(systemInfo.system) ? .white : .white.opacity(0.4))
                        }
                        .buttonStyle(.plain)

                        // Line bubbles
                        if !systemInfo.lines.isEmpty {
                            lineFilterGrid(lines: systemInfo.lines)
                        }
                    }
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    private func lineFilterGrid(lines: [RouteLineInfo]) -> some View {
        let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: min(lines.count, 7))
        return LazyVGrid(columns: columns, spacing: 6) {
            ForEach(lines) { line in
                let isOn = viewModel.isLineEnabled(line.id)
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        viewModel.toggleLine(line.id)
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
                        .foregroundColor(isOn ? lineTextColor(for: line.lineColor) : .white.opacity(0.6))
                }
                .buttonStyle(.plain)
            }
        }
    }

    /// Determine text color for a line bubble based on background color brightness
    private func lineTextColor(for hexColor: String) -> Color {
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
            let activeAlerts = viewModel.serviceAlerts
                .filter { $0.isActiveNow }
                .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
            let upcomingAlerts = viewModel.serviceAlerts
                .filter { !$0.isActiveNow }
                .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
            let filteredAlerts = selectedAlertFilter == .active ? activeAlerts : upcomingAlerts

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Service Alerts")
                        .font(.headline)
                    Spacer()
                    Picker("", selection: $selectedAlertFilter) {
                        ForEach(ServiceAlertFilter.allCases, id: \.self) { filter in
                            Text(filter.label(activeCount: activeAlerts.count, upcomingCount: upcomingAlerts.count)).tag(filter)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 220)
                }

                if filteredAlerts.isEmpty {
                    Text(selectedAlertFilter == .active ? "No active alerts" : "No upcoming alerts")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.vertical, 8)
                } else {
                    ForEach(filteredAlerts) { alert in
                        ServiceAlertCard(alert: alert)
                    }
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
                        UpcomingTrainRow(train: train, dataSource: train.dataSource)
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

    // MARK: - History Sections (Stacked Per-System with Segmented Picker)

    @ViewBuilder
    private var historySections: some View {
        if !viewModel.historyBySystem.isEmpty {
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

            // Stacked display: one block per enabled system
            let systems = viewModel.historyBySystem.keys.sorted()
            ForEach(systems, id: \.self) { system in
                if let state = viewModel.historyBySystem[system] {
                    VStack(alignment: .leading, spacing: 8) {
                        // Show system label only when multiple systems present
                        if systems.count > 1, let trainSystem = TrainSystem(rawValue: system) {
                            HStack(spacing: 4) {
                                Image(systemName: trainSystem.icon)
                                    .font(.caption2)
                                Text(trainSystem.displayName)
                                    .font(.caption)
                                    .fontWeight(.semibold)
                            }
                            .foregroundColor(.secondary)
                        }

                        switch selectedHistoryPeriod {
                        case .hour:
                            historyPeriodContent(
                                data: state.pastHour,
                                isLoading: state.isLoadingPastHour,
                                error: state.pastHourError,
                                hours: 1,
                                dataSource: system
                            )
                        case .day:
                            historyPeriodContent(
                                data: state.past24Hours,
                                isLoading: state.isLoadingPast24Hours,
                                error: state.past24HoursError,
                                hours: 24,
                                dataSource: system
                            )
                        case .week:
                            historyPeriodContent(
                                data: state.past7Days,
                                isLoading: state.isLoadingPast7Days,
                                error: state.past7DaysError,
                                hours: 168,
                                dataSource: system
                            )
                        }
                    }

                    if system != systems.last {
                        Divider()
                    }
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    @ViewBuilder
    private func historyPeriodContent(
        data: RouteHistoricalData?,
        isLoading: Bool,
        error: String?,
        hours: Double,
        dataSource: String? = nil
    ) -> some View {
        if isLoading {
            ProgressView()
                .frame(maxWidth: .infinity, alignment: .center)
                .padding()
        } else if let history = data, history.route.totalTrains > 0 {
            historyContent(history, hours: hours, dataSource: dataSource)
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
    private func historyContent(_ history: RouteHistoricalData, hours: Double, dataSource: String? = nil) -> some View {
        let total = history.route.totalTrains
        let freqColor = frequencyColor(totalTrains: total, baseline: history.route.baselineTrainCount)

        let stats = history.aggregateStats
        let onTimeValue = stats.onTimePercentage.map { "\(Int($0))%" } ?? "N/A"
        let onTimeColor = onTimePercentageColor(stats.onTimePercentage)

        let mode = dataSource.flatMap { TrainSystem(rawValue: $0)?.preferredHighlightMode } ?? preferredMode

        if mode == .health {
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

// MARK: - Service Alert Filter

enum ServiceAlertFilter: CaseIterable {
    case active, upcoming

    func label(activeCount: Int, upcomingCount: Int) -> String {
        switch self {
        case .active: return "Active (\(activeCount))"
        case .upcoming: return "Upcoming (\(upcomingCount))"
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
                    if let track = train.track, !track.isEmpty {
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

    // History state — keyed by system for stacked display
    @Published var historyBySystem: [String: HistoryState] = [:]

    /// Per-system history loading/data/error state
    struct HistoryState {
        var pastHour: RouteHistoricalData?
        var past24Hours: RouteHistoricalData?
        var past7Days: RouteHistoricalData?
        var isLoadingPastHour = false
        var isLoadingPast24Hours = false
        var isLoadingPast7Days = false
        var pastHourError: String?
        var past24HoursError: String?
        var past7DaysError: String?
    }

    // MARK: - Route Filter State

    /// Discovered systems and their lines for this station pair
    @Published var discoveredSystems: [RouteSystemInfo] = []

    /// Currently enabled line IDs (format: "SYSTEM:LINE_CODE"). Empty = all enabled (default).
    @Published var enabledLineIds: Set<String> = []

    /// Whether filter discovery is complete
    @Published var filterLoaded = false

    /// Debounced save task — cancelled and re-scheduled on each toggle
    private var saveTask: Task<Void, Never>?

    /// Whether there's anything to filter (multiple systems or multiple lines)
    var showRouteSettings: Bool {
        guard filterLoaded else { return false }
        if discoveredSystems.count > 1 { return true }
        if discoveredSystems.count == 1, discoveredSystems[0].lines.count > 1 { return true }
        return false
    }

    /// Systems that are currently enabled (have at least one line enabled)
    var enabledSystems: Set<String> {
        if enabledLineIds.isEmpty { return Set(discoveredSystems.map(\.system.rawValue)) }
        var systems = Set<String>()
        for id in enabledLineIds {
            if let system = id.split(separator: ":").first {
                systems.insert(String(system))
            }
        }
        return systems
    }

    /// Check if a specific line is enabled
    func isLineEnabled(_ lineId: String) -> Bool {
        enabledLineIds.isEmpty || enabledLineIds.contains(lineId)
    }

    /// Check if a system has any line enabled
    func isSystemEnabled(_ system: TrainSystem) -> Bool {
        enabledSystems.contains(system.rawValue)
    }

    init(context: RouteStatusContext) {
        self.context = context
    }

    func loadData() async {
        // Discover available systems first, then load data in parallel
        await discoverSystems()
        await reloadFilteredData()
    }

    /// Reload all data sections using current filter state.
    /// Called on initial load and after filter changes.
    private func reloadFilteredData() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.loadCongestionMap() }
            group.addTask { await self.loadAllHistory() }
            group.addTask { await self.loadServiceAlerts() }
            group.addTask { await self.loadUpcomingTrains() }
        }
    }

    // MARK: - System Discovery

    private func discoverSystems() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else {
            filterLoaded = true
            return
        }

        // Find systems that serve both stations
        let fromSystems = Stations.systemsForStation(from)
        let toSystems = Stations.systemsForStation(to)
        let commonSystems = fromSystems.intersection(toSystems).sorted { $0.displayName < $1.displayName }

        guard !commonSystems.isEmpty else {
            filterLoaded = true
            return
        }

        // Discover available lines by fetching departures across all systems
        do {
            let trains = try await APIService.shared.searchTrains(
                fromStationCode: from,
                toStationCode: to,
                dataSources: Set(commonSystems)
            )

            // Group lines by system
            var linesBySystem: [String: [RouteLineInfo]] = [:]
            var seenLines = Set<String>()

            for train in trains {
                let lineId = "\(train.dataSource):\(train.line.code)"
                guard !seenLines.contains(lineId) else { continue }
                seenLines.insert(lineId)

                let info = RouteLineInfo(
                    dataSource: train.dataSource,
                    lineCode: train.line.code,
                    lineName: train.line.name,
                    lineColor: train.line.color
                )
                linesBySystem[train.dataSource, default: []].append(info)
            }

            // Build system info, including systems with no trains found (they exist in topology)
            var systems: [RouteSystemInfo] = []
            for system in commonSystems {
                let lines = linesBySystem[system.rawValue] ?? []
                if !lines.isEmpty {
                    systems.append(RouteSystemInfo(system: system, lines: lines.sorted { $0.lineCode < $1.lineCode }))
                }
            }

            discoveredSystems = systems
        } catch {
            // Fall back to just using the context's data source
            if let system = TrainSystem(rawValue: context.dataSource) {
                discoveredSystems = [RouteSystemInfo(system: system, lines: [])]
            }
        }

        // Load saved preference from backend
        await loadSavedPreference(from: from, to: to)

        filterLoaded = true
    }

    private func loadSavedPreference(from: String, to: String) async {
        let deviceId = AlertSubscriptionService.shared.deviceId
        do {
            let pref = try await APIService.shared.fetchRoutePreference(
                deviceId: deviceId, from: from, to: to
            )
            // Convert saved preference to enabledLineIds
            var lineIds = Set<String>()
            for (system, lines) in pref.enabledSystems {
                if lines.isEmpty {
                    // Empty array means all lines for this system
                    for discoveredSystem in discoveredSystems where discoveredSystem.system.rawValue == system {
                        for line in discoveredSystem.lines {
                            lineIds.insert(line.id)
                        }
                    }
                } else {
                    for lineCode in lines {
                        lineIds.insert("\(system):\(lineCode)")
                    }
                }
            }
            enabledLineIds = lineIds
        } catch {
            // No saved preference — default to all enabled (empty set)
            enabledLineIds = []
        }
    }

    /// Toggle a line on/off, debounce save, and reload data
    func toggleLine(_ lineId: String) {
        // If currently "all enabled" (empty set), populate with all discovered lines first
        if enabledLineIds.isEmpty {
            enabledLineIds = Set(discoveredSystems.flatMap { $0.lines.map(\.id) })
        }

        if enabledLineIds.contains(lineId) {
            // Don't allow deselecting the last line
            if enabledLineIds.count > 1 {
                enabledLineIds.remove(lineId)
            }
        } else {
            enabledLineIds.insert(lineId)
        }

        // Check if all lines are now enabled — collapse back to empty set
        let allLineIds = Set(discoveredSystems.flatMap { $0.lines.map(\.id) })
        if enabledLineIds == allLineIds {
            enabledLineIds = []
        }

        debounceSaveAndReload()
    }

    /// Toggle all lines for a system on/off, debounce save, and reload data
    func toggleSystem(_ system: TrainSystem) {
        guard let systemInfo = discoveredSystems.first(where: { $0.system == system }) else { return }
        let systemLineIds = Set(systemInfo.lines.map(\.id))

        // If currently "all enabled" (empty set), populate with all discovered lines first
        if enabledLineIds.isEmpty {
            enabledLineIds = Set(discoveredSystems.flatMap { $0.lines.map(\.id) })
        }

        let allSystemLinesEnabled = systemLineIds.isSubset(of: enabledLineIds)
        if allSystemLinesEnabled {
            // Don't allow deselecting if it would leave nothing
            let remaining = enabledLineIds.subtracting(systemLineIds)
            if !remaining.isEmpty {
                enabledLineIds = remaining
            }
        } else {
            enabledLineIds.formUnion(systemLineIds)
        }

        // Check if all lines are now enabled — collapse back to empty set
        let allLineIds = Set(discoveredSystems.flatMap { $0.lines.map(\.id) })
        if enabledLineIds == allLineIds {
            enabledLineIds = []
        }

        debounceSaveAndReload()
    }

    /// Debounce: cancel any pending save, wait 500ms, then save + reload data
    private func debounceSaveAndReload() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(nanoseconds: 500_000_000) // 500ms
            guard !Task.isCancelled else { return }
            await savePreference()
            await reloadFilteredData()
        }
    }

    private func savePreference() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else { return }

        let deviceId = AlertSubscriptionService.shared.deviceId

        // Convert enabledLineIds to the API format: {system: [lineCodes]}
        var systems: [String: [String]] = [:]
        if enabledLineIds.isEmpty {
            // All enabled — save all discovered systems with empty arrays (= all lines)
            for system in discoveredSystems {
                systems[system.system.rawValue] = []
            }
        } else {
            for lineId in enabledLineIds {
                let parts = lineId.split(separator: ":")
                guard parts.count == 2 else { continue }
                let system = String(parts[0])
                let lineCode = String(parts[1])
                systems[system, default: []].append(lineCode)
            }
        }

        do {
            try await APIService.shared.saveRoutePreference(
                deviceId: deviceId, from: from, to: to, enabledSystems: systems
            )
        } catch {
            print("⚠️ Failed to save route preference: \(error.localizedDescription)")
        }
    }

    // MARK: - Congestion Map

    private func loadCongestionMap() async {
        isLoadingMap = true
        defer { isLoadingMap = false }

        let routeStationCodes = Set(context.stationCodes.map { $0.uppercased() })

        // Fetch congestion data for each enabled system
        var allSegments: [CongestionSegment] = []

        let systemsToFetch = enabledSystems.isEmpty
            ? Set([context.dataSource])
            : enabledSystems

        await withTaskGroup(of: [CongestionSegment].self) { group in
            for system in systemsToFetch {
                group.addTask {
                    do {
                        let response = try await APIService.shared.fetchCongestionData(
                            timeWindowHours: 1,
                            maxPerSegment: 100,
                            dataSource: system
                        )
                        if routeStationCodes.isEmpty {
                            return response.aggregatedSegments
                        } else {
                            return response.aggregatedSegments.filter { segment in
                                routeStationCodes.contains(segment.fromStation.uppercased()) &&
                                routeStationCodes.contains(segment.toStation.uppercased())
                            }
                        }
                    } catch {
                        return []
                    }
                }
            }
            for await segments in group {
                allSegments.append(contentsOf: segments)
            }
        }

        filteredSegments = allSegments
        buildStationsFromSegments()
        setMapRegion()
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
        // Fetch service alerts for all enabled systems that support them
        let systemsToFetch = enabledSystems.isEmpty
            ? Set([context.dataSource])
            : enabledSystems

        let relevantRouteIds = context.gtfsRouteIds
        var allAlerts: [V2ServiceAlert] = []

        await withTaskGroup(of: [V2ServiceAlert].self) { group in
            for system in systemsToFetch {
                guard Self.serviceAlertSystems.contains(system) else { continue }
                group.addTask {
                    do {
                        let alerts = try await APIService.shared.fetchServiceAlerts(dataSource: system)
                        if relevantRouteIds.isEmpty {
                            return alerts
                        } else {
                            return alerts.filter { alert in
                                !Set(alert.affectedRouteIds).isDisjoint(with: relevantRouteIds)
                            }
                        }
                    } catch {
                        return []
                    }
                }
            }
            for await alerts in group {
                allAlerts.append(contentsOf: alerts)
            }
        }

        serviceAlerts = allAlerts
    }

    // MARK: - Upcoming Trains

    private func loadUpcomingTrains() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else { return }
        do {
            // Fetch from all enabled systems
            let systemsToFetch: Set<TrainSystem>
            if enabledSystems.isEmpty {
                systemsToFetch = TrainSystem(rawValue: context.dataSource).map { Set([$0]) } ?? []
            } else {
                systemsToFetch = Set(enabledSystems.compactMap { TrainSystem(rawValue: $0) })
            }

            let trains = try await APIService.shared.searchTrains(
                fromStationCode: from,
                toStationCode: to,
                dataSources: systemsToFetch
            )

            // Filter by enabled lines
            let filtered: [TrainV2]
            if enabledLineIds.isEmpty {
                filtered = trains
            } else {
                filtered = trains.filter { train in
                    enabledLineIds.contains("\(train.dataSource):\(train.line.code)")
                }
            }

            upcomingTrains = Array(filtered.prefix(5))
        } catch {
            print("⚠️ Failed to load upcoming trains: \(error.localizedDescription)")
        }
    }

    // MARK: - History (Per-System for Stacked Display)

    private func loadAllHistory() async {
        guard let from = context.effectiveFromStation,
              let to = context.effectiveToStation else { return }

        let systemsToFetch = enabledSystems.isEmpty
            ? [context.dataSource]
            : Array(enabledSystems).sorted()

        // Initialize history state for each system
        for system in systemsToFetch {
            historyBySystem[system] = HistoryState(
                isLoadingPastHour: true,
                isLoadingPast24Hours: true,
                isLoadingPast7Days: true
            )
        }

        // Extract per-system line codes from enabledLineIds for filtering
        // When enabledLineIds is empty (all enabled), pass nil to skip filtering
        let linesBySystem: [String: [String]?] = {
            if enabledLineIds.isEmpty { return [:] }
            var result: [String: [String]] = [:]
            for id in enabledLineIds {
                let parts = id.split(separator: ":")
                guard parts.count == 2 else { continue }
                let system = String(parts[0])
                let lineCode = String(parts[1])
                result[system, default: []].append(lineCode)
            }
            return result
        }()

        // Fetch all periods for all systems in parallel
        await withTaskGroup(of: Void.self) { group in
            for system in systemsToFetch {
                let systemLines = linesBySystem[system] ?? nil
                // Past hour
                group.addTask {
                    do {
                        let data = try await APIService.shared.fetchRouteHistoricalData(
                            from: from, to: to, dataSource: system, hours: 1, lines: systemLines
                        )
                        await MainActor.run {
                            self.historyBySystem[system]?.pastHour = data
                            self.historyBySystem[system]?.isLoadingPastHour = false
                        }
                    } catch {
                        await MainActor.run {
                            self.historyBySystem[system]?.pastHourError = error.localizedDescription
                            self.historyBySystem[system]?.isLoadingPastHour = false
                        }
                    }
                }
                // Past 24 hours
                group.addTask {
                    do {
                        let data = try await APIService.shared.fetchRouteHistoricalData(
                            from: from, to: to, dataSource: system, hours: 24, lines: systemLines
                        )
                        await MainActor.run {
                            self.historyBySystem[system]?.past24Hours = data
                            self.historyBySystem[system]?.isLoadingPast24Hours = false
                        }
                    } catch {
                        await MainActor.run {
                            self.historyBySystem[system]?.past24HoursError = error.localizedDescription
                            self.historyBySystem[system]?.isLoadingPast24Hours = false
                        }
                    }
                }
                // Past 7 days
                group.addTask {
                    do {
                        let data = try await APIService.shared.fetchRouteHistoricalData(
                            from: from, to: to, dataSource: system, days: 7, lines: systemLines
                        )
                        await MainActor.run {
                            self.historyBySystem[system]?.past7Days = data
                            self.historyBySystem[system]?.isLoadingPast7Days = false
                        }
                    } catch {
                        await MainActor.run {
                            self.historyBySystem[system]?.past7DaysError = error.localizedDescription
                            self.historyBySystem[system]?.isLoadingPast7Days = false
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Route Filter Models

struct RouteLineInfo: Hashable, Identifiable {
    let dataSource: String
    let lineCode: String
    let lineName: String
    let lineColor: String
    var id: String { "\(dataSource):\(lineCode)" }
}

struct RouteSystemInfo: Identifiable {
    let system: TrainSystem
    let lines: [RouteLineInfo]
    var id: String { system.rawValue }
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
