import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    
    // Get favorite trips
    private var favoriteTrips: [TripPair] {
        return appState.getFavoriteTrips()
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient matching app design
                LinearGradient(
                    colors: [Color(hex: "667eea"), Color(hex: "764ba2")],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Favorite Routes Section
                        favoriteRoutesSection
                        
                        // Community Support Section
                        communitySupportSection
                        
                        Spacer(minLength: 40)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 20)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                    .fontWeight(.semibold)
                }
            }
            .preferredColorScheme(.dark)
        }
        .onAppear {
            appState.loadRecentTrips()
        }
    }
    
    // MARK: - Favorite Routes Section
    private var favoriteRoutesSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Favorite Routes")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                Spacer()
            }
            
            if favoriteTrips.isEmpty {
                // Empty state
                VStack(spacing: 12) {
                    Image(systemName: "heart")
                        .font(.system(size: 40))
                        .foregroundColor(.white.opacity(0.6))
                    
                    Text("No Favorite Routes")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Text("Add routes to your favorites from the train list by tapping the heart icon")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                }
                .padding(.vertical, 40)
                .frame(maxWidth: .infinity)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(.white.opacity(0.1))
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(.white.opacity(0.2), lineWidth: 1)
                        )
                )
            } else {
                // Favorite routes list
                ForEach(favoriteTrips) { trip in
                    FavoriteRouteCard(trip: trip) {
                        // Navigate to train list for this route
                        appState.selectedDeparture = trip.departureName
                        appState.departureStationCode = trip.departureCode
                        appState.selectedDestination = trip.destinationName
                        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
                        dismiss()
                    }
                }
            }
        }
    }
    
    // MARK: - Community Support Section
    private var communitySupportSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Support & Community")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                Spacer()
            }
            
            // WhatsApp Community Button
            Button {
                openWhatsAppCommunity()
            } label: {
                HStack(spacing: 16) {
                    Image(systemName: "message.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.green)
                        .frame(width: 32, height: 32)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Join WhatsApp Community")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                        
                        Text("Get support and report bugs")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                    }
                    
                    Spacer()
                    
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white.opacity(0.6))
                }
                .padding(20)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(.white.opacity(0.15))
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(.white.opacity(0.2), lineWidth: 1)
                        )
                )
            }
        }
    }
    
    // MARK: - Actions
    private func openWhatsAppCommunity() {
        let whatsappURL = "https://chat.whatsapp.com/LhYRVFBoWOt0fR1kDnvJbo"
        if let url = URL(string: whatsappURL) {
            openURL(url)
        }
    }
}

// MARK: - Favorite Route Card
struct FavoriteRouteCard: View {
    let trip: TripPair
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        Button {
            onTap()
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } label: {
            HStack(spacing: 16) {
                // Route info
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(Stations.displayName(for: trip.departureName))")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(0.8))
                    
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.down")
                            .font(.system(size: 12))
                            .foregroundColor(.orange)
                        
                        Text(trip.destinationName)
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                    }
                }
                
                Spacer()
                
                // Remove from favorites button
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavorite(trip)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Image(systemName: "heart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
            }
            .padding(20)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(.white.opacity(0.1))
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(.white.opacity(0.2), lineWidth: 1)
                    )
            )
        }
    }
}

#Preview {
    SettingsView()
        .environmentObject(AppState())
}