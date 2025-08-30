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
            // Amtrak-specific locations
            switch cardIndex {
            case 0:
                return (
                    title: "Amtrak Waiting Area",
                    icon: "building.2",
                    tracks: "Best for: Acela & Northeast Regional",
                    directions: "Enter through the Moynihan Train Hall on 33rd Street. Head to the upper level Amtrak waiting area with comfortable seating and departure boards.",
                    tip: "Pro tip: Amtrak passengers can use the Metropolitan Lounge if you have first class or business class tickets!"
                )
            case 1:
                return (
                    title: "West End Concourse",
                    icon: "arrow.left.square",
                    tracks: "Best for: Tracks 5-12",
                    directions: "Enter at 8th Avenue & 31st Street, go down one level. This entrance connects directly to Amtrak tracks and avoids the main hall crowds.",
                    tip: "Pro tip: There's a Starbucks here that's much less crowded than the one in the main hall."
                )
            case 2:
                return (
                    title: "Moynihan Food Hall",
                    icon: "fork.knife",
                    tracks: "Quick access to all Amtrak tracks",
                    directions: "Enter Moynihan Train Hall and head to the lower level food hall. Great spot to wait with food options, and you're directly above the tracks.",
                    tip: "Pro tip: The food hall has the best sight lines to departure boards and shortest walk to tracks."
                )
            default:
                return ("", "", "", "", "")
            }
        } else {
            // NJ Transit-specific locations
            switch cardIndex {
            case 0:
                return (
                    title: "Central Hall Side Corridors",
                    icon: "arrow.left.and.right",
                    tracks: "Best for: Tracks 1-12",
                    directions: "In the main NJ Transit area, avoid the center. Use the side corridors near the walls. Much faster when track is announced.",
                    tip: "Pro tip: Stand near the pillars by tracks 7-12 entrance for the quickest access when your track is called."
                )
            case 1:
                return (
                    title: "7th Avenue Entrance",
                    icon: "arrow.right.square",
                    tracks: "Best for: Tracks 13-21",
                    directions: "Enter from 7th Avenue side, near the LIRR area. This gives you backdoor access to higher-numbered NJ Transit tracks.",
                    tip: "Pro tip: The corridor connecting to LIRR has direct stairs to tracks 17-21, avoiding the main crush."
                )
            case 2:
                return (
                    title: "Exit Concourse Trick",
                    icon: "arrow.up.backward",
                    tracks: "Best for: Tracks 11-16",
                    directions: "Counter-intuitive but effective: wait near the taxi/exit signs on the north side. These exits become entrances when tracks are announced.",
                    tip: "Pro tip: Locals know this area clears out quickly after each train departure, giving you space to move fast."
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