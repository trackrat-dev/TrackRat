import SwiftUI

struct AddRouteAlertView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    // Station-pair state
    @State private var showFromPicker = false
    @State private var showToPicker = false
    @State private var fromStation: Station? = nil
    @State private var toStation: Station? = nil
    @State private var confirmationMessage: String? = nil

    // Customization sheet state
    @State private var directionalSheetData: DirectionalSheetData? = nil

    /// User's selected systems that support real-time alerts.
    private var alertCapableSystems: Set<TrainSystem> {
        appState.selectedSystems.filter { $0.supportsAlerts }
    }

    var body: some View {
        NavigationStack {
            stationPairPicker
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
        .sheet(item: $directionalSheetData) { data in
            DirectionalAlertConfigurationSheet(directions: data.directions) { subs in
                saveDirectionalSubscriptions(subs)
            }
        }
    }

    // MARK: - Save Subscriptions

    private var atAlertLimit: Bool {
        !subscriptionService.isPro
            && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit
    }

    private func saveDirectionalSubscriptions(_ subs: [RouteAlertSubscription]) {
        guard !atAlertLimit else { return }
        alertService.addSubscriptions(subs)
        alertService.syncIfPossible()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        directionalSheetData = nil
        withAnimation {
            fromStation = nil
            toStation = nil
        }
    }

    // MARK: - Station-Pair Picker

    private var stationPairPicker: some View {
        VStack(spacing: 16) {
            if alertCapableSystems.isEmpty {
                noEligibleSystemsView(detail: "Your selected systems are schedule-only and cannot detect delays.")
            } else {
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
                        directionalSheetData = DirectionalSheetData(directions: [
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
                        ])
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
            } // else alertCapableSystems not empty
        }
        .padding()
        .sheet(isPresented: $showFromPicker) {
            StationPickerSheet(
                selectedStation: $fromStation,
                disabledStation: toStation,
                selectedSystems: alertCapableSystems,
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
