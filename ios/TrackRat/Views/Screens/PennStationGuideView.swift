import SwiftUI

struct PennStationGuideView: View {
    let isAmtrak: Bool
    @State private var currentPage = 0
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Swipeable cards
                TabView(selection: $currentPage) {
                    ForEach(0..<3) { index in
                        WaitingLocationCard(
                            isAmtrak: isAmtrak,
                            cardIndex: index
                        )
                        .tag(index)
                    }
                }
                .tabViewStyle(PageTabViewStyle())
                .indexViewStyle(PageIndexViewStyle(backgroundDisplayMode: .always))
                
            }
            .background(Color(UIColor.systemGroupedBackground))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }
}

struct WaitingLocationCard: View {
    let isAmtrak: Bool
    let cardIndex: Int
    
    var locationInfo: (title: String, icon: String, tracks: String, directions: String, tip: String) {
        if isAmtrak {
            // Amtrak - West End Concourse strategy
            switch cardIndex {
            case 0:
                return (
                    title: "Skip the Crowds",
                    icon: "figure.walk",
                    tracks: "West End Concourse • Tracks 5-17",
                    directions: "There's a hidden entrance that 90% of travelers don't know about. The West End Concourse gives you direct access to Amtrak tracks without fighting through the main station crowds.",
                    tip: "This is Penn Station's best-kept secret for Amtrak passengers. Quieter, faster, with charging stations."
                )
            case 1:
                return (
                    title: "Find the Entrance",
                    icon: "location.circle",
                    tracks: "31st Street & 8th Avenue",
                    directions: "Exit at the southwest corner of 31st & 8th Ave. Look for \"To Trains\" signs. Take the elevator or walk down the ramps with white walls. You'll see NYC imagery on the walls—that's how you know you're in the right place.",
                    tip: "Alternative: From Moynihan Train Hall, use the elevators on the eastern end—they stop at West End Concourse level."
                )
            case 2:
                return (
                    title: "Navigate to Your Track",
                    icon: "arrow.down.circle",
                    tracks: "Best for tracks 7-16",
                    directions: "Once in the West End Concourse, follow signs to your track number. Each platform has elevators and stairs. Check the Amtrak app for your track—there aren't many monitors down here.",
                    tip: "Tracks 5-6 require longer walks. For tracks 17+, use the main Moynihan entrance instead."
                )
            default:
                return ("", "", "", "", "")
            }
        } else {
            // NJ Transit - 7th Avenue Concourse strategy
            switch cardIndex {
            case 0:
                return (
                    title: "Avoid \"The Pit\"",
                    icon: "figure.walk",
                    tracks: "7th Avenue Concourse • All NJ Transit",
                    directions: "Skip the notorious main waiting area (\"the pit\") entirely. There's a dedicated NJ Transit entrance that 81,000+ daily commuters use—it completely bypasses the chaos above.",
                    tip: "This entrance opened in 2009 and remains one of the most efficient ways to board NJ Transit."
                )
            case 1:
                return (
                    title: "Find the Entrance",
                    icon: "location.circle",
                    tracks: "31st Street & 7th Avenue",
                    directions: "Look for the NJ Transit entrance at 31st & 7th Ave. You'll see a distinctive barrel-vaulted ceiling that looks like the original Penn Station. Take the escalators or elevators straight down.",
                    tip: "This entrance never touches LIRR or Amtrak areas—it's 100% dedicated to NJ Transit."
                )
            case 2:
                return (
                    title: "Navigate to Your Track",
                    icon: "arrow.down.circle",
                    tracks: "Direct access to tracks 1-12",
                    directions: "The concourse has Italian marble walls and granite floors. Check the departure boards, then head directly to your track. For tracks 1-4, you're golden. For tracks 5-12, follow the Exit Concourse signs for the fastest route.",
                    tip: "Check NJ Transit's Departure Vision website on station WiFi for real-time track updates."
                )
            default:
                return ("", "", "", "", "")
            }
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Location card
            VStack(alignment: .leading, spacing: 12) {
                // Icon and title
                HStack {
                    Image(systemName: locationInfo.icon)
                        .font(.title2)
                        .foregroundColor(.orange)
                    
                    Text(locationInfo.title)
                        .font(.headline)
                    
                    Spacer()
                }
                
                // Track coverage
                Text(locationInfo.tracks)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
                
                Divider()
                
                // Directions
                Text(locationInfo.directions)
                    .font(.body)
                    .foregroundColor(.primary)
                    .fixedSize(horizontal: false, vertical: true)
                
                // Pro tip
                HStack {
                    Image(systemName: "lightbulb.fill")
                        .font(.caption)
                        .foregroundColor(.orange)
                    
                    Text(locationInfo.tip)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding()
                .background(Color(UIColor.secondarySystemGroupedBackground))
                .cornerRadius(10)
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 10, x: 0, y: 4)
            
            Spacer()
        }
        .padding()
    }
}

#Preview {
    PennStationGuideView(isAmtrak: false)
}

#Preview("Amtrak") {
    PennStationGuideView(isAmtrak: true)
}