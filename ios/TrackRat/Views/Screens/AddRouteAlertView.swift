import SwiftUI

struct AddRouteAlertView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared

    enum AlertMode: String, CaseIterable {
        case line = "Line"
        case stations = "Stations"
        case train = "Train"
    }

    /// Data sources with stable daily train IDs suitable for recurring alerts.
    static let stableTrainIdSystems: Set<TrainSystem> = [.njt, .amtrak, .lirr, .mnr]

    @State private var mode: AlertMode = .line

    // Station-pair state
    @State private var showFromPicker = false
    @State private var showToPicker = false
    @State private var fromStation: Station? = nil
    @State private var toStation: Station? = nil
    @State private var confirmationMessage: String? = nil

    // Line mode state
    @State private var lineSystem: TrainSystem? = nil

    // Train mode state
    @State private var trainSystem: TrainSystem? = nil
    @State private var trainStation: Station? = nil
    @State private var showTrainStationPicker = false
    @State private var departures: [TrainV2] = []
    @State private var isLoadingDepartures = false
    @State private var weekdaysOnly = true  // UI toggle: true = Mon-Fri (31), false = all days (127)
    @State private var includePlannedWork = false

    /// MTA systems that support planned work / service alert notifications.
    private static let plannedWorkSystems: Set<TrainSystem> = [.subway, .lirr, .mnr]

    /// Systems available for line mode: user's selected systems that have routes.
    private var availableLineSystems: [TrainSystem] {
        appState.selectedSystems
            .sorted { $0.displayName < $1.displayName }
    }

    /// Routes filtered to the selected line system, excluding fully-subscribed lines.
    /// A route is fully subscribed when both directions have subscriptions.
    private var filteredRoutes: [RouteLine] {
        guard let system = lineSystem else { return [] }
        let ds = system.rawValue
        return RouteTopology.allRoutes.filter { route in
            guard route.dataSource == ds else { return false }
            let lineSubs = alertService.subscriptions.filter { $0.lineId == route.id && $0.dataSource == route.dataSource }
            let subscribedDirections = Set(lineSubs.compactMap(\.direction))
            let bothTermini = Set([route.stationCodes.first, route.stationCodes.last].compactMap { $0 })
            return !bothTermini.isSubset(of: subscribedDirections)
        }
        .sorted { $0.name < $1.name }
    }

    /// Systems available for train mode: intersection of stable-ID systems and user's selection.
    private var availableTrainSystems: [TrainSystem] {
        Self.stableTrainIdSystems
            .intersection(appState.selectedSystems)
            .sorted { $0.displayName < $1.displayName }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Picker("Mode", selection: $mode) {
                    ForEach(AlertMode.allCases, id: \.self) { m in
                        Text(m.rawValue).tag(m)
                    }
                }
                .pickerStyle(.segmented)
                .padding()

                switch mode {
                case .line:
                    lineList
                case .stations:
                    stationPairPicker
                case .train:
                    trainPicker
                }
            }
            .navigationTitle("Add Route Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.orange)
                }
            }
        }
        .preferredColorScheme(.dark)
        .onAppear {
            if availableLineSystems.count == 1 {
                lineSystem = availableLineSystems.first
            }
        }
        .onChange(of: lineSystem) { _ in
            includePlannedWork = false
        }
    }

    // MARK: - Line Mode

    private var lineSystemPickerRow: some View {
        HStack {
            Text("System")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
            Spacer()
            Menu {
                ForEach(availableLineSystems) { system in
                    Button(system.displayName) {
                        if lineSystem != system {
                            lineSystem = system
                        }
                    }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(lineSystem?.displayName ?? "Select")
                        .foregroundColor(lineSystem != nil ? .white : .white.opacity(0.4))
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        .padding(.horizontal)
        .padding(.top, 4)
    }

    private var lineList: some View {
        VStack(spacing: 0) {
            lineSystemPickerRow

            if let system = lineSystem, Self.plannedWorkSystems.contains(system) {
                plannedWorkToggleRow
            }

            if lineSystem == nil {
                Spacer()
            } else if filteredRoutes.isEmpty {
                VStack(spacing: 12) {
                    Spacer()
                    Image(systemName: "checkmark.circle")
                        .font(.system(size: 40))
                        .foregroundColor(.orange)
                    Text("All available routes subscribed")
                        .font(.headline)
                        .foregroundColor(.white)
                    Spacer()
                }
            } else {
                List {
                    ForEach(filteredRoutes) { route in
                        Button {
                            withAnimation {
                                alertService.addLineSubscriptions(
                                    dataSource: route.dataSource,
                                    lineId: route.id,
                                    lineName: route.name,
                                    route: route,
                                    includePlannedWork: includePlannedWork
                                )
                            }
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(route.name)
                                        .font(.headline)
                                        .foregroundColor(.white)
                                    if let subtitle = route.terminalSubtitle {
                                        Text(subtitle)
                                            .font(.caption)
                                            .foregroundColor(.white.opacity(0.7))
                                    }
                                }
                                Spacer()
                                Image(systemName: "plus.circle")
                                    .foregroundColor(.orange)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
    }

    // MARK: - Station-Pair Mode

    private var stationPairPicker: some View {
        VStack(spacing: 16) {
            // First station
            Button {
                showFromPicker = true
            } label: {
                HStack {
                    Text(fromStation.map { $0.name } ?? "Select station")
                        .foregroundColor(fromStation != nil ? .white : .white.opacity(0.4))
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.3))
                }
                .padding()
                .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
            }
            .buttonStyle(.plain)

            // Second station
            Button {
                showToPicker = true
            } label: {
                HStack {
                    Text(toStation.map { $0.name } ?? "Select station")
                        .foregroundColor(toStation != nil ? .white : .white.opacity(0.4))
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.3))
                }
                .padding()
                .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
            }
            .buttonStyle(.plain)

            // Add button
            if let from = fromStation, let to = toStation {
                Button {
                    let fromCode = from.code
                    let toCode = to.code
                    let fromSystems = Stations.systemStringsForStation(fromCode)
                    let toSystems = Stations.systemStringsForStation(toCode)
                    let selectedStrings = appState.selectedSystems.asRawStrings
                    // Pick a system shared by both stations that the user has enabled
                    let common = fromSystems.intersection(toSystems).intersection(selectedStrings)
                    let dataSource = common.first ?? fromSystems.intersection(toSystems).first ?? "NJT"

                    let bothExist = alertService.subscriptions.contains(where: {
                        $0.fromStationCode == fromCode &&
                        $0.toStationCode == toCode &&
                        $0.dataSource == dataSource
                    }) && alertService.subscriptions.contains(where: {
                        $0.fromStationCode == toCode &&
                        $0.toStationCode == fromCode &&
                        $0.dataSource == dataSource
                    })

                    if bothExist {
                        UINotificationFeedbackGenerator().notificationOccurred(.warning)
                        showConfirmation("Already subscribed")
                    } else {
                        alertService.addStationPairSubscriptions(
                            dataSource: dataSource,
                            fromStationCode: fromCode,
                            toStationCode: toCode
                        )
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        showConfirmation("Alerts added for both directions")
                    }

                    withAnimation {
                        fromStation = nil
                        toStation = nil
                    }
                } label: {
                    Text("Add Alert")
                        .font(.headline)
                        .foregroundColor(.black)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Capsule().fill(.orange))
                }
                .padding(.top, 8)
            }

            if let message = confirmationMessage {
                HStack(spacing: 6) {
                    Image(systemName: message.hasPrefix("Alert") ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                        .foregroundColor(message.hasPrefix("Alert") ? .green : .yellow)
                    Text(message)
                        .foregroundColor(.white)
                }
                .font(.subheadline)
                .transition(.opacity.combined(with: .move(edge: .top)))
                .padding(.top, 8)
            }

            Spacer()
        }
        .padding()
        .sheet(isPresented: $showFromPicker) {
            StationPickerSheet(
                selectedStation: $fromStation,
                disabledStation: toStation,
                selectedSystems: appState.selectedSystems,
                onStationSelected: { station in
                    fromStation = station
                    showFromPicker = false
                }
            )
        }
        .sheet(isPresented: $showToPicker) {
            StationPickerSheet(
                selectedStation: $toStation,
                disabledStation: fromStation,
                selectedSystems: appState.selectedSystems,
                onStationSelected: { station in
                    toStation = station
                    showToPicker = false
                }
            )
        }
    }

    // MARK: - Train Mode

    private var trainPicker: some View {
        VStack(spacing: 16) {
            if availableTrainSystems.isEmpty {
                noEligibleSystemsView
            } else {
                // System picker
                systemPickerRow

                // Station picker (shown after system selected)
                if trainSystem != nil {
                    stationPickerRow
                }

                // Weekdays-only toggle
                if trainStation != nil {
                    weekdaysToggleRow
                }

                // Departures list or loading indicator
                if isLoadingDepartures {
                    Spacer()
                    ProgressView("Loading departures...")
                        .foregroundColor(.white)
                    Spacer()
                } else if trainStation != nil {
                    departuresList
                }
            }
        }
        .padding()
        .sheet(isPresented: $showTrainStationPicker) {
            if let system = trainSystem {
                StationPickerSheet(
                    selectedStation: $trainStation,
                    disabledStation: nil,
                    selectedSystems: [system],
                    onStationSelected: { station in
                        trainStation = station
                        showTrainStationPicker = false
                        loadDepartures()
                    }
                )
            }
        }
    }

    private var noEligibleSystemsView: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 36))
                .foregroundColor(.white.opacity(0.3))
            Text("Train alerts require NJ Transit, Amtrak, LIRR, or Metro-North.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Spacer()
        }
    }

    private var systemPickerRow: some View {
        HStack {
            Text("System")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
            Spacer()
            Menu {
                ForEach(availableTrainSystems) { system in
                    Button(system.displayName) {
                        if trainSystem != system {
                            trainSystem = system
                            trainStation = nil
                            departures = []
                        }
                    }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(trainSystem?.displayName ?? "Select")
                        .foregroundColor(trainSystem != nil ? .white : .white.opacity(0.4))
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }

    private var stationPickerRow: some View {
        Button {
            showTrainStationPicker = true
        } label: {
            HStack {
                Text("Station")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.6))
                Spacer()
                Text(trainStation.map { $0.name } ?? "Select station")
                    .foregroundColor(trainStation != nil ? .white : .white.opacity(0.4))
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.3))
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
        .buttonStyle(.plain)
    }

    private var weekdaysToggleRow: some View {
        Toggle(isOn: $weekdaysOnly) {
            Text("Weekdays only")
                .font(.subheadline)
                .foregroundColor(.white)
        }
        .tint(.orange)
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }

    private var plannedWorkToggleRow: some View {
        Toggle(isOn: $includePlannedWork) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Planned work alerts")
                    .font(.subheadline)
                    .foregroundColor(.white)
                Text("Get notified about upcoming service changes")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }
        }
        .tint(.orange)
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        .padding(.horizontal)
        .padding(.top, 4)
    }

    private var departuresList: some View {
        Group {
            if departures.isEmpty {
                VStack(spacing: 8) {
                    Spacer()
                    Text("No upcoming departures")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.5))
                    Spacer()
                }
            } else {
                List {
                    ForEach(departures) { train in
                        Button {
                            let trainName = formatTrainName(train)
                            alertService.addTrainSubscription(
                                dataSource: train.dataSource,
                                trainId: train.trainId,
                                trainName: trainName,
                                activeDays: weekdaysOnly ? 31 : 127
                            )
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            dismiss()
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Train \(train.trainId)")
                                        .font(.headline)
                                        .foregroundColor(.white)
                                    HStack(spacing: 4) {
                                        if let time = train.departure.scheduledTime {
                                            Text(time, style: .time)
                                                .font(.subheadline)
                                                .foregroundColor(.white.opacity(0.8))
                                        }
                                        Text("→ \(train.destination)")
                                            .font(.subheadline)
                                            .foregroundColor(.white.opacity(0.6))
                                    }
                                }
                                Spacer()
                                Image(systemName: "plus.circle")
                                    .foregroundColor(.orange)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
    }

    // MARK: - Helpers

    private func loadDepartures() {
        guard let system = trainSystem, let station = trainStation else { return }
        isLoadingDepartures = true
        departures = []

        Task {
            do {
                let results = try await APIService.shared.searchTrains(
                    fromStationCode: station.code,
                    dataSources: [system]
                )
                // Filter out trains whose terminal stop is the selected station
                let filtered = results.filter { train in
                    guard let destCode = Stations.getStationCode(train.destination) else { return true }
                    return !Stations.areEquivalentStations(destCode, station.code)
                }
                await MainActor.run {
                    departures = filtered
                    isLoadingDepartures = false
                }
            } catch {
                await MainActor.run {
                    departures = []
                    isLoadingDepartures = false
                }
            }
        }
    }

    private func formatTrainName(_ train: TrainV2) -> String {
        var parts = [train.dataSource, train.trainId]
        if let time = train.departure.scheduledTime {
            let formatter = DateFormatter()
            formatter.dateFormat = "h:mma"
            formatter.timeZone = TimeZone(identifier: "America/New_York")
            parts.append(formatter.string(from: time).lowercased())
        }
        parts.append("→ \(train.destination)")
        return parts.joined(separator: " ")
    }

    private func showConfirmation(_ message: String) {
        withAnimation { confirmationMessage = message }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation { confirmationMessage = nil }
        }
    }
}
