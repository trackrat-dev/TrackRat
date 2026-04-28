import SwiftUI

/// Alert mode: route-specific (station pair) or system-wide.
private enum AlertMode: String, CaseIterable {
    case route = "Route"
    case system = "System"
}

/// Single source of truth for which secondary sheet is currently presented.
/// Replaces three separate `.sheet` modifiers — stacked sheets on the same view are a known
/// SwiftUI footgun and were a likely contributor to mid-edit reset flakiness.
private enum ActiveAlertSheet: Identifiable {
    case directional(DirectionalSheetData)
    case system(DirectionalSheetData)
    case trainSystems

    var id: String {
        switch self {
        case .directional(let data): return "directional-\(data.id)"
        case .system(let data): return "system-\(data.id)"
        case .trainSystems: return "trainSystems"
        }
    }
}

struct AddRouteAlertView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    // Paywall
    @State private var showingPaywall = false

    // Mode selection
    @State private var alertMode: AlertMode = .route

    // Station-pair state
    @State private var showFromPicker = false
    @State private var showToPicker = false
    @State private var fromStation: Station? = nil
    @State private var toStation: Station? = nil
    @State private var confirmationMessage: String? = nil

    // Unified secondary-sheet state
    @State private var activeSheet: ActiveAlertSheet? = nil

    /// User's selected systems that support real-time alerts.
    private var alertCapableSystems: Set<TrainSystem> {
        appState.selectedSystems.filter { $0.supportsAlerts }
    }

    var body: some View {
        NavigationStack {
            alertContent
                .navigationTitle("Add Route Alert")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Done") { dismiss() }
                            .foregroundColor(.orange)
                    }
                }
        }
        .preferredColorScheme(.dark)
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .routeAlerts)
        }
        .sheet(item: $activeSheet) { sheet in
            switch sheet {
            case .directional(let data):
                DirectionalAlertConfigurationSheet(directions: data.directions) { subs in
                    saveDirectionalSubscriptions(subs)
                }
            case .system(let data):
                DirectionalAlertConfigurationSheet(directions: data.directions) { subs in
                    saveSystemSubscription(subs)
                }
            case .trainSystems:
                SettingsView(editTrainSystems: true)
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
        }
    }

    // MARK: - Save Subscriptions

    private var atAlertLimit: Bool {
        !subscriptionService.isPro
            && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit
    }

    private func saveDirectionalSubscriptions(_ subs: [RouteAlertSubscription]) {
        guard !atAlertLimit else {
            activeSheet = nil
            showingPaywall = true
            return
        }
        alertService.addSubscriptions(subs)
        alertService.syncIfPossible()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        activeSheet = nil
        withAnimation {
            fromStation = nil
            toStation = nil
        }
    }

    private func saveSystemSubscription(_ subs: [RouteAlertSubscription]) {
        guard !atAlertLimit else {
            activeSheet = nil
            showingPaywall = true
            return
        }
        alertService.addSubscriptions(subs)
        alertService.syncIfPossible()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        activeSheet = nil
    }

    // MARK: - Alert Content

    private var alertContent: some View {
        VStack(spacing: 16) {
            Picker("Alert Type", selection: $alertMode) {
                ForEach(AlertMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)

            switch alertMode {
            case .route:
                if alertCapableSystems.isEmpty {
                    noEligibleSystemsView(detail: "Your selected systems are schedule-only and cannot detect delays.")
                } else {
                    routeModePicker
                }
            case .system:
                systemModePicker
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
            }
        }
        .padding(.top)
    }

    // MARK: - System Mode

    private var systemModePicker: some View {
        VStack(spacing: 16) {
            Text("Get notified about service alerts, delays, and planned work across an entire transit system.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            systemGrid

            Spacer()
        }
    }

    private var systemGrid: some View {
        let systems = TrainSystem.allCases
            .filter { $0.supportsAlerts }
            .sorted { $0.displayName < $1.displayName }

        return LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 10)], spacing: 10) {
            ForEach(systems) { (system: TrainSystem) in
                let isActive = appState.selectedSystems.contains(system)
                Button {
                    if isActive {
                        openSystemAlertSheet(for: system)
                    } else {
                        activeSheet = .trainSystems
                    }
                } label: {
                    Text(system.displayName)
                        .font(.subheadline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
                        .foregroundColor(.white)
                        .opacity(isActive ? 1.0 : 0.4)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal)
    }

    private func openSystemAlertSheet(for system: TrainSystem) {
        let alreadyExists = alertService.subscriptions.contains {
            $0.isSystemWide && $0.dataSource == system.rawValue
        }

        if alreadyExists {
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
            showConfirmation("Already subscribed")
            return
        }

        if atAlertLimit {
            showingPaywall = true
            return
        }

        let sub = RouteAlertSubscription(dataSource: system.rawValue)
        activeSheet = .system(DirectionalSheetData(directions: [
            DirectionDraft(
                label: "\(system.displayName) System Alerts",
                subscription: sub,
                alreadySubscribed: false
            ),
        ]))
    }

    // MARK: - Route Mode (Station-Pair Picker)

    private var routeModePicker: some View {
        VStack(spacing: 16) {
            Text("Get notified about delays and cancellations between two stations.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
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
                    if atAlertLimit {
                        showingPaywall = true
                        return
                    }
                    let fromCode = from.code
                    let toCode = to.code
                    let fromSystems = Stations.systemStringsForStation(fromCode)
                    let toSystems = Stations.systemStringsForStation(toCode)
                    let alertCapableStrings = alertCapableSystems.asRawStrings
                    // Pick a system shared by both stations that supports alerts
                    let common = fromSystems.intersection(toSystems).intersection(alertCapableStrings)
                    let dataSource = common.first ?? fromSystems.intersection(toSystems).first ?? "NJT"

                    let existsAB = alertService.subscriptions.contains {
                        $0.fromStationCode == fromCode &&
                        $0.toStationCode == toCode &&
                        $0.dataSource == dataSource
                    }
                    let existsBA = alertService.subscriptions.contains {
                        $0.fromStationCode == toCode &&
                        $0.toStationCode == fromCode &&
                        $0.dataSource == dataSource
                    }

                    if existsAB && existsBA {
                        UINotificationFeedbackGenerator().notificationOccurred(.warning)
                        showConfirmation("Already subscribed")
                    } else {
                        let subAB = RouteAlertSubscription(
                            dataSource: dataSource, fromStationCode: fromCode, toStationCode: toCode
                        )
                        let subBA = RouteAlertSubscription(
                            dataSource: dataSource, fromStationCode: toCode, toStationCode: fromCode
                        )
                        activeSheet = .directional(DirectionalSheetData(directions: [
                            DirectionDraft(
                                label: "To \(Stations.displayName(for: toCode))",
                                subscription: subAB,
                                alreadySubscribed: existsAB
                            ),
                            DirectionDraft(
                                label: "To \(Stations.displayName(for: fromCode))",
                                subscription: subBA,
                                alreadySubscribed: existsBA
                            ),
                        ]))
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

            Spacer()
        }
        .padding(.horizontal)
        .sheet(isPresented: $showFromPicker) {
            StationPickerSheet(
                selectedStation: $fromStation,
                disabledStation: toStation,
                selectedSystems: alertCapableSystems,
                onInactiveStationSelected: { _ in
                    showFromPicker = false
                },
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
                selectedSystems: alertCapableSystems,
                onInactiveStationSelected: { _ in
                    showToPicker = false
                },
                onStationSelected: { station in
                    toStation = station
                    showToPicker = false
                }
            )
        }
    }

    private func noEligibleSystemsView(detail: String) -> some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 36))
                .foregroundColor(.white.opacity(0.3))
            Text("Route alerts require real-time data.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Text(detail)
                .font(.caption)
                .foregroundColor(.white.opacity(0.4))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Spacer()
        }
    }

    private func showConfirmation(_ message: String) {
        withAnimation { confirmationMessage = message }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation { confirmationMessage = nil }
        }
    }
}
