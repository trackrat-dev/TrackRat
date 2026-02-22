import SwiftUI

struct AddRouteAlertView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared

    enum AlertMode: String, CaseIterable {
        case line = "Line"
        case stations = "Stations"
    }

    @State private var mode: AlertMode = .line
    @State private var showFromPicker = false
    @State private var showToPicker = false
    @State private var fromStation: Station? = nil
    @State private var toStation: Station? = nil

    /// Routes filtered to the user's selected train systems.
    private var filteredRoutes: [RouteLine] {
        let dataSources = appState.selectedSystems.asRawStrings
        return RouteTopology.allRoutes.filter { dataSources.contains($0.dataSource) }
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
                }
            }
            .navigationTitle("Add Route Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.orange)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: - Line Mode

    private var lineList: some View {
        List {
            ForEach(filteredRoutes) { route in
                Button {
                    alertService.addLineSubscription(
                        dataSource: route.dataSource,
                        lineId: route.id,
                        lineName: route.name
                    )
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    dismiss()
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(route.name)
                                .font(.headline)
                                .foregroundColor(.white)
                            Text(route.dataSource)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.6))
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

    // MARK: - Station-Pair Mode

    private var stationPairPicker: some View {
        VStack(spacing: 16) {
            // From station
            Button {
                showFromPicker = true
            } label: {
                HStack {
                    Text("From")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                    Text(fromStation.map { $0.name } ?? "Select station")
                        .foregroundColor(fromStation != nil ? .white : .white.opacity(0.4))
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.3))
                }
                .padding()
                .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
            }
            .buttonStyle(.plain)

            // To station
            Button {
                showToPicker = true
            } label: {
                HStack {
                    Text("To")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                    Text(toStation.map { $0.name } ?? "Select station")
                        .foregroundColor(toStation != nil ? .white : .white.opacity(0.4))
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

                    alertService.addStationPairSubscription(
                        dataSource: dataSource,
                        fromStationCode: fromCode,
                        toStationCode: toCode
                    )
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    dismiss()
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
}
