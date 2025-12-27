import SwiftUI

// YouTube Link View Component
struct YouTubeLinkView: View {
    let thumbnailImageName: String
    let youtubeURL: String
    let maxHeight: CGFloat

    @Environment(\.openURL) private var openURL
    @State private var isPressed = false

    init(thumbnailImageName: String, youtubeURL: String, maxHeight: CGFloat = 200) {
        self.thumbnailImageName = thumbnailImageName
        self.youtubeURL = youtubeURL
        self.maxHeight = maxHeight
    }

    var body: some View {
        Button(action: {
            openYouTubeVideo()
        }) {
            ZStack {
                // Thumbnail image
                Image(thumbnailImageName)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxHeight: maxHeight)
                    .cornerRadius(TrackRatTheme.CornerRadius.md)
                    .clipped()
                    .frame(maxWidth: .infinity)

                // YouTube play button (no overlay)
                ZStack {
                    Circle()
                        .fill(Color.red)
                        .frame(width: 60, height: 60)

                    Image(systemName: "play.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.white)
                        .offset(x: 2) // Slight offset to center the play icon visually
                }
                .scaleEffect(isPressed ? 0.9 : 1.0)
                .animation(.easeInOut(duration: 0.1), value: isPressed)
            }
        }
        .buttonStyle(PlainButtonStyle())
        .onLongPressGesture(minimumDuration: 0, maximumDistance: .infinity, pressing: { pressing in
            isPressed = pressing
        }, perform: {})
    }

    private func openYouTubeVideo() {
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()

        // Try to open in YouTube app first, fallback to Safari
        if let youtubeAppURL = URL(string: youtubeURL.replacingOccurrences(of: "https://", with: "youtube://")) {
            openURL(youtubeAppURL) { success in
                if !success {
                    // Fallback to web URL if YouTube app is not installed
                    if let webURL = URL(string: youtubeURL) {
                        openURL(webURL)
                    }
                }
            }
        } else if let webURL = URL(string: youtubeURL) {
            openURL(webURL)
        }
    }
}

struct PennStationGuideView: View {
    let isAmtrak: Bool
    @State private var currentPage = 0

    var body: some View {
        NavigationStack {
            // Swipeable cards
            TabView(selection: $currentPage) {
                ForEach(0..<4) { index in
                    WaitingLocationCard(
                        isAmtrak: isAmtrak,
                        cardIndex: index
                    )
                    .tag(index)
                }
            }
            .tabViewStyle(PageTabViewStyle())
            .indexViewStyle(PageIndexViewStyle(backgroundDisplayMode: .always))
            .background(.ultraThinMaterial)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(.ultraThinMaterial)
        .preferredColorScheme(.dark)
    }
}

struct WaitingLocationCard: View {
    let isAmtrak: Bool
    let cardIndex: Int

    // Add YouTube URL for video cards
    var youtubeURL: String? {
        if isAmtrak && cardIndex == 0 {
            return "https://youtube.com/shorts/oEAzdvVJOcg"
        } else if !isAmtrak && cardIndex == 0 {
            return "https://youtube.com/shorts/H_WntclrDcI"
        }
        return nil
    }

    var locationInfo: (title: String, imageName: String, directions: String) {
        if isAmtrak {
            // Amtrak - West End Concourse strategy
            switch cardIndex {
            case 0:
                return (
                    title: "For Amtrak, use the West End Concourse!",
                    imageName: "amtrak_video",
                    directions: "\nSkip the crowded main areas of Penn Station & Moynihan Hall.\n\nClick to watch the video above or swipe for more info on how to get there."
                )
            case 1:
                return (
                    title: "Enter at 8th Ave & 33rd St",
                    imageName: "amtrak_1",
                    directions: "\nUse the entrance for Moynihan Hall at the corner of 8th Ave and 33rd Street."
                )
            case 2:
                return (
                    title: "Immediately take escalator on right",
                    imageName: "amtrak_2",
                    directions: "\nInstead of continuing into the main Moynihan Train Hall, take the escalator on your right down to the lower level.\n\nThis concourse is primarily used for LIRR (and making TikTok videos), but it serves all of the platforms used by Amtrak too."
                )
            case 3:
                return (
                    title: "Find your platform!",
                    imageName: "amtrak_3",
                    directions: "\nOnce in the West End Concourse, follow signs to your track number.\n\nEach platform can be accessed with the stairs on the left or elevators on the right."
                )
            default:
                return ("", "", "")
            }
        } else {
            // NJ Transit - 7th Avenue Concourse strategy
            switch cardIndex {
            case 0:
                return (
                    title: "For NJ Transit, use the sub-level Exit Concourse!",
                    imageName: "nj_transit_video",
                    directions: "\nSkip the crowded main NJ Transit waiting areas.\n\nClick to watch the video above or swipe for more info on how to get there."
                )
            case 1:
                return (
                    title: "Enter at 7th Ave & 33rd St",
                    imageName: "nj_transit_1",
                    directions: "\nStart at 7th Ave and 33rd Street and go down the escalator at the entrance with the large triangle."
                )
            case 2:
                return (
                    title: "Go straight until you find the Exit Concourse",
                    imageName: "nj_transit_2",
                    directions: "\nContinue straight down the long hallway until you see signs for the Exit Concourse on your left.\n\nIt's a long walk and you'll need to pass many restaurants and other concourses."
                )
            case 3:
                return (
                    title: "Navigate to Your Track",
                    imageName: "nj_transit_3",
                    directions: "\nOnce in the Exit Concourse, follow signs to your track number.\n\nThis area serves the platforms used by all NJ Transit trains."
                )
            default:
                return ("", "", "")
            }
        }
    }
    
    var body: some View {
        // Video cards (cardIndex == 0) get full-area treatment
        if let youtubeURL = youtubeURL {
            VStack(spacing: 0) {
                Text(locationInfo.title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)

                Spacer()

                YouTubeLinkView(
                    thumbnailImageName: locationInfo.imageName,
                    youtubeURL: youtubeURL,
                    maxHeight: .infinity
                )
                .frame(maxHeight: 350)

                Spacer()
            }
            .padding()
        } else {
            // Regular instruction cards with title, image, and directions
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 12) {
                    VStack(spacing: 12) {
                        Text(locationInfo.title)
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)

                        Image(locationInfo.imageName)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(maxHeight: 200)
                            .cornerRadius(TrackRatTheme.CornerRadius.md)
                            .clipped()
                            .frame(maxWidth: .infinity)
                    }

                    if !locationInfo.directions.isEmpty {
                        Text(locationInfo.directions)
                            .font(.body)
                            .foregroundColor(.white.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )

                Spacer()
            }
            .padding()
        }
    }
}

#Preview {
    PennStationGuideView(isAmtrak: false)
}

#Preview("Amtrak") {
    PennStationGuideView(isAmtrak: true)
}
