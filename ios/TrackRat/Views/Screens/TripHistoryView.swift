import SwiftUI

struct TripHistoryView: View {
    @EnvironmentObject private var appState: AppState
    @State private var trips: [CompletedTrip] = []
    @State private var stats: TripStats = .empty

    // Group trips by month
    private var groupedTrips: [(String, [CompletedTrip])] {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM yyyy"

        let grouped = Dictionary(grouping: trips) { trip in
            formatter.string(from: trip.tripDate)
        }

        // Sort by date (most recent first)
        return grouped.sorted { first, second in
            guard let firstTrip = first.value.first,
                  let secondTrip = second.value.first else { return false }
            return firstTrip.tripDate > secondTrip.tripDate
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header
            HStack {
                Button {
                    if !appState.navigationPath.isEmpty {
                        appState.navigationPath.removeLast()
                    }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(width: 44, height: 44)
                }

                Spacer()

                Text("Trip History")
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Color.clear
                    .frame(width: 44, height: 44)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 8)

            if trips.isEmpty {
                // Empty state
                VStack(spacing: 16) {
                    Spacer()

                    Image(systemName: "tram.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.white.opacity(0.3))

                    Text("No Trips Yet")
                        .font(.title2.weight(.semibold))
                        .foregroundColor(.white)

                    Text("Start tracking trains with Live Activity\nto see your trip history here.")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)

                    Spacer()
                }
                .padding()
            } else {
                ScrollView {
                    VStack(spacing: 20) {
                        // Summary stats card
                        SummaryStatsCard(stats: stats)
                            .padding(.horizontal)

                        // Grouped trips by month
                        ForEach(groupedTrips, id: \.0) { monthYear, monthTrips in
                            VStack(spacing: 12) {
                                // Month header
                                HStack {
                                    Text(monthYear)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundColor(.white.opacity(0.8))
                                    Spacer()
                                    Text("\(monthTrips.count) trips")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.5))
                                }
                                .padding(.horizontal, 4)

                                // Trips list
                                VStack(spacing: 0) {
                                    ForEach(Array(monthTrips.enumerated()), id: \.element.id) { index, trip in
                                        TripHistoryRowView(trip: trip)

                                        if index < monthTrips.count - 1 {
                                            Divider()
                                                .background(Color.white.opacity(0.1))
                                        }
                                    }
                                }
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(.ultraThinMaterial)
                                )
                            }
                            .padding(.horizontal)
                        }
                    }
                    .padding(.vertical)
                    .padding(.bottom, 40)
                }
            }
        }
        .navigationBarHidden(true)
        .onAppear {
            trips = StorageService.shared.loadCompletedTrips()
            stats = StorageService.shared.computeTripStats()
        }
    }
}

// MARK: - Summary Stats Card

struct SummaryStatsCard: View {
    let stats: TripStats

    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Text("All-Time Stats")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.white.opacity(0.8))
                Spacer()
            }

            HStack(spacing: 0) {
                VStack(spacing: 4) {
                    Text("\(stats.totalTrips)")
                        .font(.title.bold())
                        .foregroundColor(.white)
                    Text("Trips")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }
                .frame(maxWidth: .infinity)

                Divider()
                    .frame(height: 40)
                    .background(Color.white.opacity(0.2))

                VStack(spacing: 4) {
                    Text(stats.formattedTotalDelay)
                        .font(.title.bold())
                        .foregroundColor(.red)
                    Text("Delays")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }
                .frame(maxWidth: .infinity)

                Divider()
                    .frame(height: 40)
                    .background(Color.white.opacity(0.2))

                VStack(spacing: 4) {
                    Text("\(stats.onTimePercentage)%")
                        .font(.title.bold())
                        .foregroundColor(stats.onTimePercentage >= 80 ? .green : (stats.onTimePercentage >= 50 ? .yellow : .red))
                    Text("On Time")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }
                .frame(maxWidth: .infinity)
            }

            if let route = stats.mostFrequentRoute {
                Divider()
                    .background(Color.white.opacity(0.2))

                HStack {
                    Image(systemName: "arrow.triangle.swap")
                        .foregroundColor(.orange)
                    Text("Most traveled: \(route.originName) ↔ \(route.destinationName)")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                    Text("\(route.count)×")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.orange)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
}

// MARK: - Trip History Row

struct TripHistoryRowView: View {
    let trip: CompletedTrip

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE, MMM d"
        return formatter.string(from: trip.tripDate)
    }

    private var formattedTime: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: trip.scheduledDeparture)
    }

    var body: some View {
        HStack(spacing: 12) {
            // Left: Date and time
            VStack(alignment: .leading, spacing: 2) {
                Text(formattedDate)
                    .font(.caption.weight(.medium))
                    .foregroundColor(.white.opacity(0.9))
                Text(formattedTime)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }
            .frame(width: 80, alignment: .leading)

            // Center: Route info
            VStack(alignment: .leading, spacing: 4) {
                Text(trip.routeDescription)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.white)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    Text(trip.lineName)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))

                    if let track = trip.track {
                        Text("Track \(track)")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
            }

            Spacer()

            // Right: Delay indicator
            VStack(alignment: .trailing, spacing: 2) {
                Text(trip.formattedDelay)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(trip.isOnTime ? .green : .red)

                if trip.arrivalDelayMinutes > 0 {
                    Text("late")
                        .font(.caption2)
                        .foregroundColor(.red.opacity(0.7))
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }
}

#Preview {
    NavigationStack {
        TripHistoryView()
            .environmentObject(AppState())
    }
}
