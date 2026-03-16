import SwiftUI

// MARK: - Station Model
struct Station: Identifiable, Equatable {
    let id = UUID()
    let code: String
    let name: String
}

// MARK: - Station Picker Sheet
struct StationPickerSheet: View {
    @Binding var selectedStation: Station?
    let disabledStation: Station?  // Station that should be shown as disabled
    var selectedSystems: Set<TrainSystem>? = nil  // Optional: filter stations by selected systems
    let onStationSelected: (Station) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var searchText = ""

    /// All visible stations filtered by selected systems.
    private var visibleStations: [Station] {
        var allStations = Stations.all.compactMap { name -> Station? in
            guard let code = Stations.getStationCode(name) else { return nil }
            return Station(code: code, name: name)
        }

        if let systems = selectedSystems, !systems.isEmpty {
            allStations = allStations.filter { station in
                Stations.isStationVisible(station.code, withSystems: systems)
            }
        }

        return allStations
    }

    /// Search results using ranked search (prefix > substring).
    private var searchResults: [Station] {
        guard !searchText.isEmpty else { return [] }
        let q = searchText.lowercased()
        let stations = visibleStations
        let prefixMatches = stations.filter { $0.name.lowercased().hasPrefix(q) }
            .sorted { $0.name < $1.name }
        let substringMatches = stations.filter {
            !$0.name.lowercased().hasPrefix(q) &&
            ($0.name.localizedCaseInsensitiveContains(searchText) ||
             $0.code.localizedCaseInsensitiveContains(searchText))
        }
            .sorted { $0.name < $1.name }
        return Array((prefixMatches + substringMatches).prefix(20))
    }

    /// Stations grouped by system for the browse view (when search is empty).
    private var groupedStations: [(system: String, stations: [Station])] {
        let systemOrder: [(raw: String, label: String)] = [
            ("NJT", "NJ Transit"),
            ("AMTRAK", "Amtrak"),
            ("PATH", "PATH"),
            ("PATCO", "PATCO"),
            ("LIRR", "LIRR"),
            ("MNR", "Metro-North"),
            ("SUBWAY", "NYC Subway"),
        ]

        let stations = visibleStations
        var groups: [(system: String, stations: [Station])] = []

        // Group by system
        for (raw, label) in systemOrder {
            let systemStations = stations
                .filter { Stations.systemStringsForStation($0.code).contains(raw) }
                .sorted { $0.name < $1.name }
            if !systemStations.isEmpty {
                groups.append((system: label, stations: systemStations))
            }
        }

        return groups
    }

    @ViewBuilder
    private func stationRow(_ station: Station) -> some View {
        let isDisabled = disabledStation?.code == station.code

        Button {
            if !isDisabled {
                selectedStation = station
                onStationSelected(station)
            }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(station.name)
                        .font(.headline)
                        .foregroundColor(isDisabled ? .white.opacity(0.4) : .white)

                    if isDisabled {
                        Text("Already selected")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
                Spacer()

                if station.code == selectedStation?.code {
                    Image(systemName: "checkmark")
                        .foregroundColor(.orange)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PlainButtonStyle())
        .disabled(isDisabled)
        .listRowBackground(Color.clear)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search bar
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.white.opacity(0.5))
                    TextField("Search stations...", text: $searchText)
                        .foregroundColor(.white)
                        .autocorrectionDisabled(true)
                        .textInputAutocapitalization(.never)
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )
                .padding()

                if searchText.isEmpty {
                    List {
                        ForEach(groupedStations, id: \.system) { group in
                            Section {
                                ForEach(group.stations) { station in
                                    stationRow(station)
                                }
                            } header: {
                                Text(group.system)
                                    .font(.caption.weight(.semibold))
                                    .foregroundColor(.white.opacity(0.6))
                                    .textCase(nil)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                } else {
                    List(searchResults) { station in
                        stationRow(station)
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .background(.ultraThinMaterial)
            .navigationTitle("Select Station")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden()
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
