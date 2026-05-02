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
    var onInactiveStationSelected: ((Station) -> Void)? = nil
    let onStationSelected: (Station) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var searchText = ""
    @FocusState private var isSearchFocused: Bool

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

    /// Search results grouped by whether the station belongs to an active system.
    private var searchResults: (active: [Station], inactive: [Station]) {
        guard !searchText.isEmpty else { return ([], []) }

        guard let systems = selectedSystems, !systems.isEmpty else {
            // No system filter — show all matching stations as active
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
            return (Array((prefixMatches + substringMatches).prefix(20)), [])
        }

        let grouped = Stations.searchGrouped(searchText, selectedSystems: systems)
        return (
            grouped.primary.compactMap { station(named: $0) },
            grouped.other.compactMap { station(named: $0) }
        )
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
            ("BART", "BART"),
            ("MBTA", "MBTA"),
            ("METRA", "Metra"),
            ("WMATA", "DC Metro"),
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
        let displayName = Stations.displayName(for: station.code)
        let lines = SubwayLines.lines(forStationCode: station.code)

        Button {
            if !isDisabled {
                selectedStation = station
                onStationSelected(station)
            }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        StationNameWithBadges(
                            name: displayName,
                            stationCode: station.code,
                            subwayLines: lines,
                            font: .headline,
                            foregroundColor: isDisabled ? .white.opacity(0.4) : .white,
                            chipSize: 14,
                            badgeOpacity: isDisabled ? 0.4 : 1
                        )
                    }

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

    @ViewBuilder
    private func inactiveSystemStationRow(_ station: Station) -> some View {
        let displayName = Stations.displayName(for: station.code)
        let lines = SubwayLines.lines(forStationCode: station.code)

        Button {
            onInactiveStationSelected?(station)
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        StationNameWithBadges(
                            name: displayName,
                            stationCode: station.code,
                            subwayLines: lines,
                            font: .headline,
                            foregroundColor: .white.opacity(0.7),
                            chipSize: 14,
                            badgeOpacity: 0.7
                        )
                    }

                    Text("Edit your train systems to use this station")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }

                Spacer()

                if onInactiveStationSelected != nil {
                    Image(systemName: "chevron.right")
                        .foregroundColor(.white.opacity(0.35))
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PlainButtonStyle())
        .listRowBackground(Color.clear)
    }

    private func station(named name: String) -> Station? {
        guard let code = Stations.getStationCode(name) else { return nil }
        return Station(code: code, name: name)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search bar
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.white.opacity(0.5))
                    TextField("Search stations...", text: $searchText)
                        .focused($isSearchFocused)
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
                    List {
                        ForEach(searchResults.active) { station in
                            stationRow(station)
                        }

                        if !searchResults.inactive.isEmpty {
                            Section {
                                ForEach(searchResults.inactive) { station in
                                    inactiveSystemStationRow(station)
                                }
                            } header: {
                                Text("Other systems")
                                    .font(.caption.weight(.semibold))
                                    .foregroundColor(.white.opacity(0.6))
                                    .textCase(nil)
                            }
                        }
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
        .onAppear { isSearchFocused = true }
    }
}
