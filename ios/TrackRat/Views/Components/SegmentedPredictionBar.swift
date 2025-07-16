import SwiftUI

// MARK: - Segmented Prediction Bar
struct SegmentedPredictionBar: View {
    let train: TrainV2
    @State private var selectedSegment: PredictionSegment?
    @State private var showingOthersPopup = false
    @State private var animateAppearance = false
    
    private var predictionSegments: [PredictionSegment] {
        guard let predictionData = train.predictionData,
              let trackProbabilities = predictionData.trackProbabilities else {
            return []
        }
        
        // Group tracks by platform and create segments
        let platformProbabilities = PredictionData.groupTracksByPlatform(trackProbabilities)
        let filteredPlatforms = platformProbabilities.filter { $0.value >= 0.04 }
        let sortedPlatforms = filteredPlatforms.sorted { $0.value > $1.value }
        
        return createSegments(from: sortedPlatforms)
    }
    
    private var owlMessage: String {
        guard !predictionSegments.isEmpty else {
            return "🤷 TrackRat is thinking..."
        }
        
        let topSegment = predictionSegments.first!
        let confidence = topSegment.probability
        
        if confidence >= 0.8 {
            return "🐀 TrackRat predicts tracks \(topSegment.platformName)"
        } else if confidence >= 0.5 {
            return "🤔 TrackRat thinks it may be tracks \(topSegment.platformName)"
        } else {
            let topTracks = predictionSegments.prefix(2).map { $0.platformName }
            return "🤷 TrackRat sees several possibilities"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with owl messaging
            HStack {
                Image(systemName: "tram.circle.fill")
                    .foregroundColor(.black)
                    .font(.title2)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Track Predictions")
                        .font(.headline)
                        .foregroundColor(.black)
                    
                    Text(owlMessage)
                        .font(.subheadline)
                        .foregroundColor(.black.opacity(0.8))
                        .fontWeight(.medium)
                }
                
                Spacer()
            }
            
            if !predictionSegments.isEmpty {
                VStack(spacing: 8) {
                    // Labels for segments that need them above the bar
                    if hasSegmentsWithTopLabels {
                        topLabelsView
                    }
                    
                    // Main segmented bar
                    segmentedBarView
                        .frame(height: 32)
                }
                .padding(.top, 4)
            } else {
                Text("No prediction data available")
                    .font(.caption)
                    .foregroundColor(.gray)
                    .italic()
            }
        }
        .padding()
        .background(Color.orange.opacity(0.05))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.orange.opacity(0.3), lineWidth: 1)
        )
        .onAppear {
            // Animate segments in from left to right with slight delay
            withAnimation(.easeOut(duration: 0.8)) {
                animateAppearance = true
            }
        }
        .alert("Other Predictions", isPresented: $showingOthersPopup) {
            Button("OK") { }
        } message: {
            if let othersSegment = predictionSegments.first(where: { $0.isOthersGroup }) {
                Text(othersSegment.detailText)
            }
        }
    }
    
    // MARK: - Segmented Bar View
    private var segmentedBarView: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                ForEach(predictionSegments) { segment in
                    segmentView(segment: segment, totalWidth: geometry.size.width)
                }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    
    private func segmentView(segment: PredictionSegment, totalWidth: CGFloat) -> some View {
        let segmentWidth = totalWidth * segment.probability
        let isSelected = selectedSegment?.id == segment.id
        
        return Rectangle()
            .fill(segment.color)
            .frame(width: animateAppearance ? segmentWidth : 0)
            .overlay(
                // Label inside segment if wide enough
                segment.labelPosition == .inside ? 
                Text(segment.displayText)
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .opacity(animateAppearance ? 1 : 0)
                : nil
            )
            .scaleEffect(isSelected ? 1.05 : 1.0)
            .overlay(
                // Subtle border for selected segment
                isSelected ? 
                RoundedRectangle(cornerRadius: 2)
                    .stroke(Color.white, lineWidth: 2)
                : nil
            )
            .onTapGesture {
                handleSegmentTap(segment)
            }
            .animation(.easeInOut(duration: 0.2), value: isSelected)
    }
    
    // MARK: - Top Labels View
    private var hasSegmentsWithTopLabels: Bool {
        predictionSegments.contains { $0.labelPosition == .above }
    }
    
    private var topLabelsView: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                ForEach(predictionSegments) { segment in
                    let segmentWidth = geometry.size.width * segment.probability
                    
                    VStack(spacing: 2) {
                        if segment.labelPosition == .above {
                            VStack(spacing: 1) {
                                Text(segment.platformName)
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundColor(.black)
                                
                                // Small connector line
                                Rectangle()
                                    .fill(Color.black.opacity(0.3))
                                    .frame(width: min(segmentWidth * 0.8, 20), height: 1)
                            }
                            .opacity(animateAppearance ? 1 : 0)
                            .animation(.easeOut(duration: 0.8).delay(0.2), value: animateAppearance)
                        } else {
                            Text("")
                                .font(.caption2)
                        }
                    }
                    .frame(width: segmentWidth)
                }
            }
        }
        .frame(height: 18)
    }
    
    // MARK: - Helper Methods
    private func createSegments(from platformProbabilities: [(key: String, value: Double)]) -> [PredictionSegment] {
        var segments: [PredictionSegment] = []
        var othersSegments: [PredictionSegment] = []
        let maxMainSegments = 4 // Show up to 4 main segments
        
        for (index, platform) in platformProbabilities.enumerated() {
            let segment = PredictionSegment(
                id: platform.key,
                platformName: platform.key,
                probability: platform.value,
                rank: index + 1
            )
            
            // Group segments as "Others" if:
            // 1. Probability is less than 8% AND we already have 3+ segments, OR
            // 2. We've reached the maximum number of main segments
            if (platform.value < 0.08 && segments.count >= 3) || segments.count >= maxMainSegments {
                othersSegments.append(segment)
            } else {
                segments.append(segment)
            }
        }
        
        // Create "Others" segment if we have grouped segments
        if !othersSegments.isEmpty {
            let totalOthersProbability = othersSegments.reduce(0) { $0 + $1.probability }
            
            // Ensure Others segment is wide enough to be tappable (minimum 24px at typical screen width)
            let minOthersWidth = 0.06 // ~6% minimum width
            let adjustedProbability = max(totalOthersProbability, minOthersWidth)
            
            let othersSegment = PredictionSegment(
                id: "others",
                platformName: "Others",
                probability: adjustedProbability,
                rank: segments.count + 1,
                isOthersGroup: true,
                detailText: createOthersDetailText(from: othersSegments)
            )
            segments.append(othersSegment)
        }
        
        return segments
    }
    
    private func createOthersDetailText(from segments: [PredictionSegment]) -> String {
        let sortedSegments = segments.sorted { $0.probability > $1.probability }
        return sortedSegments.map { 
            "Tracks \($0.platformName): \(Int($0.probability * 100))%" 
        }.joined(separator: "\n")
    }
    
    private func handleSegmentTap(_ segment: PredictionSegment) {
        // Haptic feedback
        let impactFeedback = UIImpactFeedbackGenerator(style: .light)
        impactFeedback.impactOccurred()
        
        if segment.isOthersGroup {
            showingOthersPopup = true
        } else {
            // Brief highlight animation
            withAnimation(.easeInOut(duration: 0.2)) {
                selectedSegment = segment
            }
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                selectedSegment = nil
            }
        }
    }
}

// MARK: - Prediction Segment Model
struct PredictionSegment: Identifiable, Equatable {
    let id: String
    let platformName: String
    let probability: Double
    let rank: Int
    let isOthersGroup: Bool
    let detailText: String
    
    init(id: String, platformName: String, probability: Double, rank: Int, isOthersGroup: Bool = false, detailText: String = "") {
        self.id = id
        self.platformName = platformName
        self.probability = probability
        self.rank = rank
        self.isOthersGroup = isOthersGroup
        self.detailText = detailText
    }
    
    var displayText: String {
        if isOthersGroup {
            return "Others"
        }
        return "\(platformName)\n\(Int(probability * 100))%"
    }
    
    var color: Color {
        if isOthersGroup {
            return .gray.opacity(0.6)
        }
        
        switch rank {
        case 1:
            return .orange // Primary prediction
        case 2:
            return .orange.opacity(0.7) // Secondary
        case 3:
            return .orange.opacity(0.5) // Tertiary
        default:
            return .orange.opacity(0.3) // Lower probability
        }
    }
    
    var labelPosition: LabelPosition {
        if isOthersGroup {
            return .inside
        }
        
        // Determine label position based on segment width
        // We need to estimate the width based on probability
        if probability >= 0.15 {
            return .inside // Wide enough for label inside
        } else if probability >= 0.08 {
            return .above // Medium size, label above
        } else {
            return .inside // Small segments are grouped as "Others"
        }
    }
}

// MARK: - Label Position Enum
enum LabelPosition {
    case inside
    case above
}

// MARK: - Preview
#Preview {
    let mockTrain = TrainV2(
        id: 1,
        trainId: "1234",
        line: "Northeast Corridor",
        destination: "Trenton",
        departureTime: Date(),
        track: nil,
        status: .scheduled,
        delayMinutes: 0,
        stops: [],
        predictionData: PredictionData(trackProbabilities: [
            "1": 0.35,
            "2": 0.20,
            "3": 0.15,
            "4": 0.12,
            "7": 0.08,
            "8": 0.05,
            "9": 0.03,
            "10": 0.02
        ]),
        originStationCode: "NY"
    )
    
    return SegmentedPredictionBar(train: mockTrain)
        .padding()
        .background(Color.gray.opacity(0.1))
}