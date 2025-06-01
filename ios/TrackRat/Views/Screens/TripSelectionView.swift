import SwiftUI

struct TripSelectionView: View {
    @EnvironmentObject private var appState: AppState
    
    // Get unique trips (no duplicates)
    private var uniqueTrips: [TripPair] {
        var seen = Set<String>()
        return appState.recentTrips.compactMap { trip in
            let key = "\(trip.departureCode)-\(trip.destinationCode)"
            if seen.contains(key) {
                return nil
            } else {
                seen.insert(key)
                return trip
            }
        }
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color(hex: "667eea"), Color(hex: "764ba2")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 24) {
                // Title
                VStack(spacing: 8) {
                    Text("Where would you")
                        .font(.largeTitle)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                    
                    Text("like to go?")
                        .font(.largeTitle)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                }
                .padding(.top, 60)
                
                ScrollView {
                    VStack(spacing: 20) {
                        // Active trips (Live Activity)
                        if #available(iOS 16.1, *) {
                            ActiveTripsSection()
                        }
                        
                        // Recent trips
                        if !uniqueTrips.isEmpty {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("RECENT TRIPS")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white.opacity(0.7))
                                    .padding(.horizontal)
                                
                                ForEach(uniqueTrips) { trip in
                                    TripButton(trip: trip) {
                                        selectTrip(trip)
                                    }
                                    .padding(.horizontal)
                                }
                            }
                            .padding(.top, 20)
                        }
                        
                        // Add a new trip section
                        VStack(alignment: .leading, spacing: 16) {
                            Text("ADD A NEW TRIP")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.7))
                                .padding(.horizontal)
                            
                            // New trip button
                            Button {
                                appState.navigationPath.append(NavigationDestination.departureSelector)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            } label: {
                                HStack {
                                    Image(systemName: "plus.circle.fill")
                                        .font(.system(size: 20))
                                    Text("Choose a new route")
                                        .font(.headline)
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 14, weight: .semibold))
                                }
                                .foregroundColor(.white)
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(.white.opacity(0.2))
                                        .background(
                                            RoundedRectangle(cornerRadius: 12)
                                                .stroke(.white.opacity(0.3), lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                            
                            // Train number search
                            Button {
                                appState.navigationPath.append(NavigationDestination.trainNumberSearch)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            } label: {
                                HStack {
                                    Image(systemName: "number.circle.fill")
                                        .font(.system(size: 20))
                                    Text("Search by train number")
                                        .font(.headline)
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 14, weight: .semibold))
                                }
                                .foregroundColor(.white)
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(.white.opacity(0.2))
                                        .background(
                                            RoundedRectangle(cornerRadius: 12)
                                                .stroke(.white.opacity(0.3), lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                        }
                        .padding(.top, 20)
                    }
                    .padding(.bottom, 40)
                }
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .onAppear {
            appState.loadRecentTrips()
            
            // If no trips, go directly to departure selection
            if uniqueTrips.isEmpty {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    appState.navigationPath.append(NavigationDestination.departureSelector)
                }
            }
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
        
        // Update last used time
        appState.saveCurrentTrip()
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
}

// MARK: - Trip Button
struct TripButton: View {
    let trip: TripPair
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(formatDepartureName(trip.departureName)) to \(trip.destinationName)")
                        .font(.callout)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                
                Spacer()
                
                // Remove button
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.removeTrip(trip)
                    }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.white.opacity(0.6))
                }
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.removeTrip(trip)
                    }
                }
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.15))
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.2), lineWidth: 1)
                    )
            )
        }
    }
    
    private func formatDepartureName(_ name: String) -> String {
        // Simplify display names for better UI
        switch name {
        case "New York Penn Station":
            return "New York Penn"
        case "Newark Penn Station":
            return "Newark Penn"
        default:
            return name
        }
    }
}

#Preview {
    TripSelectionView()
        .environmentObject(AppState())
}
