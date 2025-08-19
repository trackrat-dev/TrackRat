import SwiftUI
import AVKit
import AVFoundation

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    
    @State private var showVideo = true
    @State private var currentPage = 0
    @State private var homeStation: Station? = nil
    @State private var workStation: Station? = nil
    @State private var otherFavorites: [Station] = []
    @State private var searchText = ""
    @State private var showStationPicker = false
    @State private var isPickingOtherStation = false
    
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    
    let isRepeating: Bool
    
    private let totalPages = 3
    
    init(isRepeating: Bool = false) {
        self.isRepeating = isRepeating
        // Show video for both first-time and repeat onboarding
        self._showVideo = State(initialValue: true)
    }
    
    var body: some View {
        ZStack {
            // Background
            Color.black
                .ignoresSafeArea()
            
            if showVideo {
                // Show intro video first
                OnboardingVideoView {
                    withAnimation(.easeInOut(duration: 0.5)) {
                        showVideo = false
                    }
                }
            } else {
                // Show onboarding screens after video
                VStack(spacing: 0) {
                    // Content area
                    TabView(selection: $currentPage) {
                        // Screen 1: Welcome + Station Setup
                        welcomeAndSetupView()
                            .tag(0)
                        
                        // Screen 2: Your Favorite Stations
                        favoriteStationsView()
                            .tag(1)
                        
                        // Screen 3: Key Features
                        keyFeaturesView()
                            .tag(2)
                    }
                    .tabViewStyle(PageTabViewStyle(indexDisplayMode: .never))
                    .animation(.easeInOut, value: currentPage)
                
                // Page indicator and navigation
                VStack(spacing: 20) {
                    // Page indicators
                    HStack(spacing: 8) {
                        ForEach(0..<totalPages, id: \.self) { index in
                            Circle()
                                .fill(index == currentPage ? Color.orange : Color.gray.opacity(0.3))
                                .frame(width: 8, height: 8)
                                .animation(.easeInOut, value: currentPage)
                        }
                    }
                    
                    // Navigation buttons
                    HStack {
                        if currentPage > 0 {
                            Button("Back") {
                                withAnimation {
                                    currentPage -= 1
                                }
                            }
                            .foregroundColor(.white.opacity(0.7))
                        }
                        
                        Spacer()
                        
                        Button(currentPage == totalPages - 1 ? "Let's go!" : "Continue") {
                            if currentPage == totalPages - 1 {
                                completeOnboarding()
                            } else {
                                withAnimation {
                                    currentPage += 1
                                }
                            }
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(height: 50)
                        .frame(minWidth: 160)
                        .background(Color.orange)
                        .cornerRadius(12)
                        
                        if currentPage == 0 {
                            Button("Skip Setup") {
                                skipToFeatures()
                            }
                            .foregroundColor(.white.opacity(0.7))
                            .padding(.leading, 16)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 40)
                }
            }
        }
        .sheet(isPresented: $showStationPicker) {
            StationPickerSheet(
                selectedStation: isPickingOtherStation ? .constant(nil) : (homeStation == nil ? $homeStation : $workStation),
                onStationSelected: { station in
                    if isPickingOtherStation {
                        if !otherFavorites.contains(where: { $0.code == station.code }) {
                            otherFavorites.append(station)
                        }
                    }
                    showStationPicker = false
                }
            )
        }
    }
    
    // MARK: - Screen 1: Welcome + Station Setup
    private func welcomeAndSetupView() -> some View {
        VStack(spacing: 32) {
            Spacer()
            
            // Logo and title
            VStack(spacing: 16) {
                Text("Welcome!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                
                Text("Let's personalize your experience by\nselecting your frequently used stations")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
            }
            
            // Station selection cards
            VStack(spacing: 16) {
                // Home Station
                StationSelectionCard(
                    icon: "house.fill",
                    title: "Home Station",
                    selectedStation: homeStation,
                    onTap: {
                        isPickingOtherStation = false
                        showStationPicker = true
                    }
                )
                
                // Work Station
                StationSelectionCard(
                    icon: "building.2.fill",
                    title: "Work Station",
                    selectedStation: workStation,
                    onTap: {
                        isPickingOtherStation = false
                        showStationPicker = true
                    }
                )
                
                // Other Favorites
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(.orange)
                        Text("Other Favorites (Optional)")
                            .font(.headline)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    
                    if otherFavorites.isEmpty {
                        Button {
                            isPickingOtherStation = true
                            showStationPicker = true
                        } label: {
                            HStack {
                                Image(systemName: "plus")
                                Text("Add Station")
                            }
                            .foregroundColor(.orange)
                            .frame(height: 44)
                            .frame(maxWidth: .infinity)
                            .background(Color.white.opacity(0.1))
                            .cornerRadius(8)
                        }
                    } else {
                        ForEach(otherFavorites, id: \.code) { station in
                            HStack {
                                Text(station.name)
                                    .foregroundColor(.white)
                                Spacer()
                                Button {
                                    otherFavorites.removeAll { $0.code == station.code }
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(.gray)
                                }
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(Color.white.opacity(0.1))
                            .cornerRadius(8)
                        }
                        
                        if otherFavorites.count < 3 {
                            Button {
                                isPickingOtherStation = true
                                showStationPicker = true
                            } label: {
                                HStack {
                                    Image(systemName: "plus")
                                    Text("Add Another")
                                }
                                .foregroundColor(.orange)
                                .frame(height: 44)
                                .frame(maxWidth: .infinity)
                                .background(Color.white.opacity(0.1))
                                .cornerRadius(8)
                            }
                        }
                    }
                }
                .padding()
                .background(Material.ultraThin)
                .cornerRadius(12)
            }
            
            Spacer()
        }
        .padding(.horizontal, 20)
    }
    
    // MARK: - Screen 2: Your Favorite Stations
    private func favoriteStationsView() -> some View {
        VStack(spacing: 32) {
            Spacer()
            
            VStack(spacing: 16) {
                Text("Your Favorite Stations")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                
                Text("In the future, if you'd ever like to update these, just click the heart icon while browsing stations!")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
            }
            
            VStack(spacing: 12) {
                // Add selected stations
                if let home = homeStation {
                    FavoriteStationRow(
                        stationCode: home.code,
                        stationName: home.name,
                        isFavorite: true
                    )
                }
                
                if let work = workStation, work.code != homeStation?.code {
                    FavoriteStationRow(
                        stationCode: work.code,
                        stationName: work.name,
                        isFavorite: true
                    )
                }
                
                ForEach(otherFavorites.filter { station in
                    station.code != homeStation?.code && station.code != workStation?.code
                }, id: \.code) { station in
                    FavoriteStationRow(
                        stationCode: station.code,
                        stationName: station.name,
                        isFavorite: true
                    )
                }
            }
            
            Spacer()
        }
        .padding(.horizontal, 20)
    }
    
    // MARK: - Screen 3: Key Features
    private func keyFeaturesView() -> some View {
        VStack(spacing: 32) {
            Spacer()
            
            VStack(spacing: 16) {
                Text("What Makes TrackRat Special")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            
            VStack(spacing: 16) {
                FeatureCard(
                    icon: "bolt.fill",
                    title: "Super Fast",
                    description: "Real-time updates every 30 seconds\nwith intelligent caching"
                )
                
                FeatureCard(
                    icon: "tram.fill",
                    title: "Live Progress Updates",
                    description: "Track trains on your Lock Screen\nwith real-time updates"
                )
                
                FeatureCard(
                    icon: "map.fill",
                    title: "Visualize Delays and Congestion",
                    description: "System-wide delay visualization\n🟢 On time  🟡 5-15m  🟠 15-30m  🔴 30m+"
                )
                
                FeatureCard(
                    icon: "brain.head.profile",
                    title: "Track Predictions",
                    description: "AI-powered track assignments\nbefore official announcements"
                )
                
                FeatureCard(
                    icon: "lock.fill",
                    title: "Privacy First",
                    description: "No accounts, no tracking\nYour data stays on your device"
                )
            }
            
            Spacer()
        }
        .padding(.horizontal, 20)
    }
    
    // MARK: - Helper Functions
    private func skipToFeatures() {
        // Just add NY Penn as favorite and skip to features
        withAnimation {
            currentPage = 2
        }
    }
    
    private func completeOnboarding() {
        // Save selected stations as favorites
        var favoriteStations: Set<String> = []
        
        if let home = homeStation {
            favoriteStations.insert(home.code)
        }
        if let work = workStation {
            favoriteStations.insert(work.code)
        }
        for other in otherFavorites {
            favoriteStations.insert(other.code)
        }
        
        // Save to app state and storage
        for stationCode in favoriteStations {
            if let stationName = Stations.displayName(for: stationCode) {
                appState.toggleFavoriteStation(code: stationCode, name: stationName)
            }
        }
        
        // Mark onboarding as complete
        hasCompletedOnboarding = true
        
        // Provide haptic feedback
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        
        // Dismiss
        dismiss()
    }
}

// MARK: - Supporting Views
struct StationSelectionCard: View {
    let icon: String
    let title: String
    let selectedStation: Station?
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.orange)
                    .frame(width: 24)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Text(selectedStation?.name ?? "Select Station...")
                        .font(.subheadline)
                        .foregroundColor(selectedStation == nil ? .white.opacity(0.6) : .orange)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.white.opacity(0.5))
                    .font(.caption)
            }
            .padding()
            .background(Material.ultraThin)
            .cornerRadius(12)
        }
    }
}

struct FavoriteStationRow: View {
    let stationCode: String
    let stationName: String
    let isFavorite: Bool
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(stationName)
                    .font(.headline)
                    .foregroundColor(.white)
                Text(stationCode)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
            Spacer()
            Image(systemName: isFavorite ? "heart.fill" : "heart")
                .foregroundColor(.orange)
                .font(.system(size: 20))
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(12)
    }
}

struct FeatureCard: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.orange)
                .frame(width: 24, height: 24)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
            }
            
            Spacer()
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(12)
    }
}

// MARK: - Station Model
struct Station: Identifiable, Equatable {
    let id = UUID()
    let code: String
    let name: String
}

// MARK: - Station Picker Sheet
struct StationPickerSheet: View {
    @Binding var selectedStation: Station?
    let onStationSelected: (Station) -> Void
    @Environment(\.dismiss) private var dismiss
    
    @State private var searchText = ""
    
    private var filteredStations: [Station] {
        let allStations = Stations.all.compactMap { name -> Station? in
            guard let code = Stations.getStationCode(name) else { return nil }
            return Station(code: code, name: name)
        }
        
        if searchText.isEmpty {
            // Show popular stations when not searching
            let popularCodes = ["NY", "NP", "TR", "PJ", "MP"]
            let popularStations = popularCodes.compactMap { code -> Station? in
                guard let name = Stations.displayName(for: code) else { return nil }
                return Station(code: code, name: name)
            }
            return popularStations + allStations.filter { station in
                !popularCodes.contains(station.code)
            }
        } else {
            return allStations.filter { station in
                station.name.localizedCaseInsensitiveContains(searchText) ||
                station.code.localizedCaseInsensitiveContains(searchText)
            }
        }
    }
    
    var body: some View {
        NavigationView {
            VStack {
                // Search bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.gray)
                    TextField("Search stations...", text: $searchText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                .padding()
                
                List(filteredStations) { station in
                    Button {
                        selectedStation = station
                        onStationSelected(station)
                        dismiss()
                    } label: {
                        HStack {
                            Text(station.name)
                                .font(.headline)
                                .foregroundColor(.primary)
                            Spacer()
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            .navigationTitle("Select Station")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden()
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
}


// MARK: - Video Components

struct OnboardingVideoView: View {
    @State private var videoEnded = false
    @State private var videoFailed = false
    @State private var fadeToBlackOpacity: Double = 0
    @State private var videoViewOpacity: Double = 0
    @State private var isReadyToPlay = false
    @State private var hasStartedPlaying = false
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            if !videoFailed {
                if let videoURL = Bundle.main.url(forResource: "intro_animation", withExtension: "mp4") {
                    VideoPlayerView(
                        url: videoURL,
                        shouldPlay: isReadyToPlay
                    ) {
                        // Video ended successfully
                        videoEnded = true
                        
                        // Success haptic feedback
                        let notification = UINotificationFeedbackGenerator()
                        notification.notificationOccurred(.success)
                        
                        // Auto-advance to onboarding after brief pause
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            onComplete()
                        }
                    } onError: { error in
                        print("Video playback error: \(error)")
                        videoFailed = true
                    } onStart: {
                        // Only trigger once when actually playing
                        if !hasStartedPlaying {
                            hasStartedPlaying = true
                            
                            // Video started playing - light haptic feedback
                            let impactFeedback = UIImpactFeedbackGenerator(style: .light)
                            impactFeedback.impactOccurred()
                            
                            // Start fade to black delayed by 0.5s more (at 4.2 seconds into 4.2 second video)
                            DispatchQueue.main.asyncAfter(deadline: .now() + 4.2) {
                                withAnimation(.easeInOut(duration: 0.5)) {
                                    fadeToBlackOpacity = 1.0
                                }
                            }
                        }
                    }
                    .ignoresSafeArea()
                    .opacity(videoViewOpacity)
                    
                    // Fade to black overlay
                    Color.black
                        .opacity(fadeToBlackOpacity)
                        .ignoresSafeArea()
                        .allowsHitTesting(false)
                } else {
                    // Video file not found - skip directly to onboarding
                    Color.black
                        .ignoresSafeArea()
                        .onAppear {
                            print("Video file not found, skipping to onboarding")
                            onComplete()
                        }
                }
            } else {
                // Video failed - skip directly to onboarding
                Color.black
                    .ignoresSafeArea()
                    .onAppear {
                        onComplete()
                    }
            }
        }
        .onAppear {
            // Phase 1: Let the modal settle (0.3s)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                // Phase 2: Fade in the video view (0.3s animation)
                withAnimation(.easeIn(duration: 0.3)) {
                    videoViewOpacity = 1.0
                }
                
                // Phase 3: Start playing after fade begins (0.1s into fade)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    isReadyToPlay = true
                }
            }
        }
    }
}

struct VideoPlayerView: UIViewRepresentable {
    let url: URL
    var shouldPlay: Bool = true
    var onEnd: (() -> Void)?
    var onError: ((Error) -> Void)?
    var onStart: (() -> Void)?
    
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        
        // Create player item first to ensure we start from beginning
        let playerItem = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: playerItem)
        
        // Ensure we start from the beginning
        player.seek(to: .zero)
        
        let playerLayer = AVPlayerLayer(player: player)
        playerLayer.videoGravity = .resizeAspectFill
        playerLayer.frame = view.bounds
        view.layer.addSublayer(playerLayer)
        
        context.coordinator.player = player
        context.coordinator.playerLayer = playerLayer
        context.coordinator.shouldPlay = shouldPlay
        
        // Set up end notification
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(Coordinator.playerDidFinishPlaying),
            name: .AVPlayerItemDidPlayToEndTime,
            object: playerItem
        )
        
        // Set up error observation
        playerItem.addObserver(
            context.coordinator,
            forKeyPath: "status",
            options: [.new, .initial],
            context: nil
        )
        
        return view
    }
    
    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.playerLayer?.frame = uiView.bounds
        
        // Update shouldPlay state and trigger playback if needed
        if shouldPlay != context.coordinator.shouldPlay {
            context.coordinator.shouldPlay = shouldPlay
            if shouldPlay && context.coordinator.isReadyToPlay && !context.coordinator.hasStartedPlaying {
                context.coordinator.startPlayback()
            }
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject {
        let parent: VideoPlayerView
        var player: AVPlayer?
        var playerLayer: AVPlayerLayer?
        var shouldPlay: Bool = false
        var isReadyToPlay: Bool = false
        var hasStartedPlaying: Bool = false
        
        init(_ parent: VideoPlayerView) {
            self.parent = parent
            self.shouldPlay = parent.shouldPlay
        }
        
        @objc func playerDidFinishPlaying() {
            parent.onEnd?()
        }
        
        func startPlayback() {
            guard !hasStartedPlaying else { return }
            hasStartedPlaying = true
            
            player?.seek(to: .zero) { _ in
                self.player?.play()
                // Notify that playback has started
                self.parent.onStart?()
            }
        }
        
        override func observeValue(forKeyPath keyPath: String?, of object: Any?, change: [NSKeyValueChangeKey : Any]?, context: UnsafeMutableRawPointer?) {
            if keyPath == "status",
               let item = object as? AVPlayerItem {
                switch item.status {
                case .failed:
                    if let error = item.error {
                        parent.onError?(error)
                    }
                case .readyToPlay:
                    isReadyToPlay = true
                    // Preroll the video for smoother start
                    player?.preroll(atRate: 1.0) { finished in
                        if finished {
                            // Only start playing when both ready and should play
                            if self.shouldPlay && !self.hasStartedPlaying {
                                self.startPlayback()
                            }
                        }
                    }
                case .unknown:
                    break
                @unknown default:
                    break
                }
            }
        }
        
        deinit {
            NotificationCenter.default.removeObserver(self)
            player?.currentItem?.removeObserver(self, forKeyPath: "status")
        }
    }
}

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
