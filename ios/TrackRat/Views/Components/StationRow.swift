import SwiftUI

struct StationRow: View {
    let station: FavoriteStation
    @Binding var isFavorite: Bool
    let onToggleFavorite: () -> Void
    
    @State private var isAnimating = false
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(station.name)
                    .font(.headline)
                    .foregroundColor(.white)
            }

            Spacer()

            Button(action: {
                // Animate the heart
                withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                    isAnimating = true
                }

                // Haptic feedback
                UIImpactFeedbackGenerator(style: .light).impactOccurred()

                // Toggle favorite state
                onToggleFavorite()

                // Reset animation
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                        isAnimating = false
                    }
                }
            }) {
                Image(systemName: isFavorite ? "heart.fill" : "heart")
                    .foregroundColor(isFavorite ? .orange : .white.opacity(0.5))
                    .font(.system(size: 20))
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                .stroke(TrackRatTheme.Colors.surfaceCard, lineWidth: 0.5)
        )
    }
}

// MARK: - Search Station Row
struct SearchStationRow: View {
    let stationName: String
    let stationCode: String
    @Binding var isFavorite: Bool
    let onToggleFavorite: () -> Void
    
    @State private var isAnimating = false
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(stationName)
                    .font(.headline)
                    .foregroundColor(.white)
            }

            Spacer()

            Button(action: {
                // Animate the heart
                withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                    isAnimating = true
                }

                // Haptic feedback
                UIImpactFeedbackGenerator(style: .light).impactOccurred()

                // Toggle favorite state
                onToggleFavorite()

                // Reset animation
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                        isAnimating = false
                    }
                }
            }) {
                Image(systemName: isFavorite ? "heart.fill" : "heart")
                    .foregroundColor(isFavorite ? .orange : .white.opacity(0.5))
                    .font(.system(size: 20))
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                .stroke(TrackRatTheme.Colors.surfaceCard, lineWidth: 0.5)
        )
    }
}

// MARK: - Home/Work Station Row (Non-editable)
struct HomeWorkStationRow: View {
    let stationName: String
    let stationCode: String
    let isHome: Bool  // true for home, false for work

    var body: some View {
        HStack {
            // Icon
            Image(systemName: isHome ? "house.fill" : "briefcase.fill")
                .foregroundColor(.orange)
                .font(.system(size: 16))

            // Station name
            VStack(alignment: .leading, spacing: 4) {
                Text(stationName)
                    .font(.headline)
                    .foregroundColor(.white)

                Text(isHome ? "Home Station" : "Work Station")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                .stroke(TrackRatTheme.Colors.surfaceCard, lineWidth: 0.5)
        )
    }
}

#Preview {
    VStack(spacing: 16) {
        // Home & Work stations (non-editable)
        HomeWorkStationRow(
            stationName: "Orange",
            stationCode: "OG",
            isHome: true
        )
        
        HomeWorkStationRow(
            stationName: "New York Penn Station",
            stationCode: "NY",
            isHome: false
        )
        
        Divider()
        
        // Regular favorite stations
        StationRow(
            station: FavoriteStation(code: "NY", name: "New York Penn Station"),
            isFavorite: .constant(true),
            onToggleFavorite: {}
        )
        
        StationRow(
            station: FavoriteStation(code: "NP", name: "Newark Penn Station"),
            isFavorite: .constant(false),
            onToggleFavorite: {}
        )
        
        SearchStationRow(
            stationName: "Orange",
            stationCode: "OG",
            isFavorite: .constant(false),
            onToggleFavorite: {}
        )
    }
    .padding()
    .background(.ultraThinMaterial)
}