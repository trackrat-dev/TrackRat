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
                    .foregroundColor(.primary)
                Text(station.id)
                    .font(.caption)
                    .foregroundColor(.secondary)
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
                    .foregroundColor(isFavorite ? .orange : .secondary)
                    .font(.system(size: 20))
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.white.opacity(0.1), lineWidth: 0.5)
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
                    .foregroundColor(.primary)
                Text(stationCode)
                    .font(.caption)
                    .foregroundColor(.secondary)
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
                    .foregroundColor(isFavorite ? .orange : .secondary)
                    .font(.system(size: 20))
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.white.opacity(0.1), lineWidth: 0.5)
        )
    }
}

#Preview {
    VStack(spacing: 16) {
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
    .background(Color.black)
}