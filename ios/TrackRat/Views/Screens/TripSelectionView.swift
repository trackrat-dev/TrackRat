import SwiftUI

struct TripSelectionView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.openURL) private var openURL
    
    // Get favorite trips
    private var favoriteTrips: [TripPair] {
        return appState.getFavoriteTrips()
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 20) {
                    // Title
                    VStack(spacing: TrackRatTheme.Spacing.sm) {
                        Text("Where would you")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                        
                        Text("like to go?")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                    }
                    .padding(.top, 60)
                        // Active trips (Live Activity)
                        if #available(iOS 16.1, *) {
                            ActiveTripsSection()
                        }
                        
                        // Favorite routes
                        if !favoriteTrips.isEmpty {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("FAVORITE ROUTES")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal)
                                
                                ForEach(favoriteTrips) { trip in
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
                                .font(TrackRatTheme.Typography.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
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
                                .foregroundColor(TrackRatTheme.Colors.onSurface)
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                        .fill(TrackRatTheme.Colors.surfaceCard)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                                .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
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
                                .foregroundColor(TrackRatTheme.Colors.onSurface)
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                        .fill(TrackRatTheme.Colors.surfaceCard)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                                .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                        }
                        .padding(.top, 20)
                        
                        // WhatsApp Community button
                        Button {
                            openWhatsAppCommunity()
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack {
                                Image(systemName: "message.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(.green)
                                
                                Text("Report bugs and missing stations")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.7))
                                
                                Spacer()
                                
                                Image(systemName: "arrow.up.right")
                                    .font(.system(size: 12))
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(.white.opacity(0.08))
                                    .background(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(.white.opacity(0.15), lineWidth: 1)
                                    )
                            )
                            .padding(.horizontal)
                        }
                        .padding(.top, 20)
                        
                        // Advanced Configuration button
                        Button {
                            appState.navigationPath.append(NavigationDestination.advancedConfiguration)
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack {
                                Image(systemName: "gearshape.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(.gray)
                                
                                Text("Advanced Configuration")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.7))
                                
                                Spacer()
                                
                                Image(systemName: "chevron.right")
                                    .font(.system(size: 12))
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(.white.opacity(0.08))
                                    .background(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(.white.opacity(0.15), lineWidth: 1)
                                    )
                            )
                            .padding(.horizontal)
                        }
                        
                }
                .padding(.bottom, 40)
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .onAppear {
            appState.loadRecentTrips()
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    private func openWhatsAppCommunity() {
        let whatsappURL = "https://chat.whatsapp.com/LhYRVFBoWOt0fR1kDnvJbo"
        if let url = URL(string: whatsappURL) {
            openURL(url)
        }
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
                    Text("\(Stations.displayName(for: trip.departureName)) to \(trip.destinationName)")
                        .font(.callout)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                
                Spacer()
                
                // Unfavorite button (heart icon)
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavorite(trip)
                    }
                } label: {
                    Image(systemName: "heart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavorite(trip)
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
    
}

#Preview {
    TripSelectionView()
        .environmentObject(AppState())
}
