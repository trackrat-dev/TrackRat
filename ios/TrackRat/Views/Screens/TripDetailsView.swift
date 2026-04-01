import SwiftUI

// MARK: - Trip Details View
/// Shows the full multi-leg journey with stops for each leg and transfer indicators between them.
/// Users can tap "Full train →" to navigate to the individual TrainDetailsView for any leg.
struct TripDetailsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel = TripDetailsViewModel()

    var body: some View {
        VStack(spacing: 0) {
            TrackRatNavigationHeader(
                title: viewModel.headerTitle,
                showBackButton: true,
                showCloseButton: false,
                trailingContent: {
                    Button("Close") {
                        appState.navigationPath = NavigationPath()
                    }
                    .font(.body)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                    .buttonStyle(.plain)
                }
            )

            ScrollView {
                if let trip = appState.selectedTrip {
                    VStack(spacing: 0) {
                        // Trip summary header
                        TripSummaryHeader(trip: trip)

                        if viewModel.hasError && !viewModel.isLoading {
                            ErrorView(message: "Failed to load trip details") {
                                Task { await viewModel.loadAllLegs(trip: trip) }
                            }
                            .padding(.top, 16)
                        }

                        // Legs with transfers
                        ForEach(Array(trip.legs.enumerated()), id: \.element.id) { index, leg in
                            LegDetailSection(
                                leg: leg,
                                train: viewModel.legTrains[leg.trainId],
                                isLoading: viewModel.isLoading,
                                onViewFullTrain: {
                                    appState.pendingNavigation = .trainDetailsFlexible(
                                        trainNumber: leg.trainId,
                                        fromStation: leg.boarding.code,
                                        journeyDate: leg.journeyDate,
                                        dataSource: leg.dataSource
                                    )
                                }
                            )

                            if index < trip.transfers.count {
                                TripTransferIndicator(transfer: trip.transfers[index])
                            }
                        }
                    }
                    .padding()
                } else {
                    Text("Trip details not available.")
                        .foregroundColor(.black.opacity(0.6))
                        .italic()
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                }
            }
        }
        .navigationBarHidden(true)
        .task {
            guard let trip = appState.selectedTrip else { return }
            await viewModel.loadAllLegs(trip: trip)
        }
        .task(id: viewModel.isViewVisible) {
            guard viewModel.isViewVisible, let trip = appState.selectedTrip else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                guard !Task.isCancelled, viewModel.isViewVisible else { break }
                await viewModel.refreshAllLegs(trip: trip)
            }
        }
        .onAppear { viewModel.isViewVisible = true }
        .onDisappear { viewModel.isViewVisible = false }
    }
}

// MARK: - View Model
@MainActor
class TripDetailsViewModel: ObservableObject {
    @Published var legTrains: [String: TrainV2] = [:]  // trainId -> TrainV2
    @Published var isLoading = true
    @Published var hasError = false
    @Published var isViewVisible = false

    private let apiService = APIService.shared

    var headerTitle: String {
        if legTrains.isEmpty && isLoading {
            return "Loading..."
        }
        return "Trip Details"
    }

    func loadAllLegs(trip: TripOption) async {
        isLoading = true
        hasError = false
        await fetchLegs(trip: trip)
        hasError = legTrains.isEmpty
        isLoading = false
    }

    func refreshAllLegs(trip: TripOption) async {
        await fetchLegs(trip: trip)
    }

    private func fetchLegs(trip: TripOption) async {
        await withTaskGroup(of: (String, TrainV2?).self) { group in
            for leg in trip.legs {
                group.addTask { [apiService] in
                    let train = try? await apiService.fetchTrainDetails(
                        id: leg.trainId,
                        fromStationCode: leg.boarding.code,
                        date: leg.journeyDate,
                        dataSource: leg.dataSource
                    )
                    return (leg.trainId, train)
                }
            }
            for await (trainId, train) in group {
                if let train = train {
                    legTrains[trainId] = train
                }
            }
        }
    }
}

// MARK: - Trip Summary Header
private struct TripSummaryHeader: View {
    let trip: TripOption

    private func timeString(_ date: Date) -> String {
        DateFormatter.easternTimeShort.string(from: date)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Origin → Destination
            Text("\(trip.legs.first?.boarding.name ?? "") → \(trip.legs.last?.alighting.name ?? "")")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(.black)

            HStack(spacing: 12) {
                Text(trip.durationDisplay)
                    .font(.subheadline)
                    .foregroundColor(.black.opacity(0.6))

                Text("\(timeString(trip.departureTime)) → \(timeString(trip.arrivalTime))")
                    .font(.subheadline)
                    .foregroundColor(.black.opacity(0.6))

                Text("\(trip.legs.count) trains • \(trip.transfers.count) transfer\(trip.transfers.count != 1 ? "s" : "")")
                    .font(.caption)
                    .foregroundColor(.black.opacity(0.5))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color.white.opacity(0.9))
        .cornerRadius(TrackRatTheme.CornerRadius.lg)
        .trackRatShadow()
        .padding(.bottom, 16)
    }
}

// MARK: - Leg Detail Section
private struct LegDetailSection: View {
    let leg: TripLeg
    let train: TrainV2?
    let isLoading: Bool
    let onViewFullTrain: () -> Void

    private var displayableStops: [StopV2] {
        guard let stops = train?.stops else { return [] }
        let fromCode = leg.boarding.code
        let toCode = leg.alighting.code
        let originIdx = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, fromCode) }
        let destIdx = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, toCode) }
        if let start = originIdx, let end = destIdx, start <= end {
            return Array(stops[start...end])
        }
        return stops
    }

    private var hasPreviousStops: Bool {
        guard let stops = train?.stops,
              let idx = stops.firstIndex(where: { Stations.areEquivalentStations($0.stationCode, leg.boarding.code) })
        else { return false }
        return idx > 0
    }

    private var hasLaterStops: Bool {
        guard let stops = train?.stops,
              let idx = stops.firstIndex(where: { Stations.areEquivalentStations($0.stationCode, leg.alighting.code) })
        else { return false }
        return idx < stops.count - 1
    }

    private var lineColor: Color {
        Color(hex: leg.line.color) ?? .gray
    }

    var body: some View {
        VStack(spacing: 0) {
            // Leg header
            HStack(spacing: 10) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(lineColor)
                    .frame(width: 4, height: 40)

                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text(leg.line.name)
                            .font(.headline)
                            .foregroundColor(.black)

                        if let train = train, train.observationType != "SCHEDULED" {
                            Text("Train \(train.trainId)")
                                .font(.subheadline)
                                .foregroundColor(.black.opacity(0.5))
                        }

                        if leg.isCancelled {
                            Text("Cancelled")
                                .font(.caption)
                                .foregroundColor(.red)
                                .fontWeight(.semibold)
                        }
                    }

                    Text("\(leg.boarding.name) → \(leg.alighting.name)")
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.5))
                }

                Spacer()

                Button(action: onViewFullTrain) {
                    Text("Full train →")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
                .buttonStyle(.plain)
            }
            .padding(16)

            // Data freshness
            if let train = train, let freshness = train.dataFreshness {
                HStack {
                    Text(train.dataSource)
                        .font(.caption2)
                        .foregroundColor(.black.opacity(0.4))
                    Text("•")
                        .font(.caption2)
                        .foregroundColor(.black.opacity(0.3))
                    Text("Updated \(freshness.ageSeconds)s ago")
                        .font(.caption2)
                        .foregroundColor(.black.opacity(0.4))
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 8)
            }

            // Stops
            if train == nil && isLoading {
                HStack(spacing: 8) {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text("Loading stops...")
                        .foregroundColor(.black.opacity(0.6))
                        .italic()
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
            } else if let train = train, !displayableStops.isEmpty {
                VStack(alignment: .leading, spacing: 0) {
                    if hasPreviousStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                            Text("Train has previous stops")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                                .italic()
                        }
                        .padding(.bottom, 4)
                        .padding(.horizontal, 20)
                    }

                    ForEach(displayableStops) { stop in
                        StopRowV2(
                            stop: stop,
                            isDestination: Stations.areEquivalentStations(stop.stationCode, leg.alighting.code),
                            isDeparture: Stations.areEquivalentStations(stop.stationCode, leg.boarding.code),
                            isBoarding: false,
                            boardingTrack: nil,
                            train: train,
                            departureStationCode: leg.boarding.code,
                            shouldShowJourneyPredictions: false
                        )
                    }

                    if hasLaterStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                            Text("Train has later stops")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                                .italic()
                        }
                        .padding(.top, 4)
                        .padding(.horizontal, 20)
                    }
                }
                .padding(.bottom, 12)
            } else if train == nil && !isLoading {
                Text("Could not load stops for this leg.")
                    .foregroundColor(.black.opacity(0.5))
                    .italic()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            }
        }
        .background(Color.white.opacity(0.9))
        .cornerRadius(TrackRatTheme.CornerRadius.lg)
        .trackRatShadow()
    }
}

// MARK: - Transfer Indicator
private struct TripTransferIndicator: View {
    let transfer: TransferInfo

    var body: some View {
        HStack(spacing: 10) {
            VStack(spacing: 0) {
                Rectangle()
                    .fill(Color.black.opacity(0.15))
                    .frame(width: 2, height: 12)
                Image(systemName: transfer.sameStation ? "arrow.down" : "figure.walk")
                    .font(.caption)
                    .foregroundColor(.black.opacity(0.4))
                Rectangle()
                    .fill(Color.black.opacity(0.15))
                    .frame(width: 2, height: 12)
            }
            .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text("Transfer")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.black.opacity(0.6))
                HStack(spacing: 4) {
                    Text(transfer.walkDescription)
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.45))
                    if !transfer.sameStation {
                        Text("to \(transfer.toStation.name)")
                            .font(.caption)
                            .foregroundColor(.black.opacity(0.35))
                    }
                }
            }

            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }
}
