import SwiftUI

// MARK: - Bottom Sheet Position
enum BottomSheetPosition: CaseIterable {
    case compact    // 25% of screen height
    case medium     // 50% of screen height
    case expanded   // 100% of screen height
    
    func offsetFor(screenHeight: CGFloat) -> CGFloat {
        switch self {
        case .compact:
            return screenHeight * 0.75  // Show 25%
        case .medium:
            return screenHeight * 0.5   // Show 50%
        case .expanded:
            return 0                    // Show 100%
        }
    }
}

// MARK: - Bottom Sheet View
struct BottomSheetView<Content: View>: View {
    @Binding var position: BottomSheetPosition
    let content: Content
    
    // Drag gesture state
    @GestureState private var translation: CGFloat = 0
    @State private var isDragging = false
    
    init(position: Binding<BottomSheetPosition>, @ViewBuilder content: () -> Content) {
        self._position = position
        self.content = content()
    }
    
    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                // Drag indicator
                dragIndicator
                    .padding(.top, 12)
                    .padding(.bottom, 8)
                
                // Content with clipping and gradient overlay
                ZStack(alignment: .bottom) {
                    content
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .clipped()
                    
                    // Gradient overlay to indicate hidden content (only when not fully expanded)
                    if position != .expanded {
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color.clear,
                                TrackRatTheme.Colors.surface.opacity(0.8),
                                TrackRatTheme.Colors.surface
                            ]),
                            startPoint: .top,
                            endPoint: .bottom
                        )
                        .frame(height: 40)
                        .allowsHitTesting(false) // Allow gestures to pass through
                    }
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(TrackRatTheme.Colors.surface)
                    .ignoresSafeArea()
            )
            .offset(y: position.offsetFor(screenHeight: geometry.size.height))
            .offset(y: translation)
            .animation(.interactiveSpring(response: 0.3, dampingFraction: 0.8, blendDuration: 0.25), value: translation)
            .animation(.interactiveSpring(response: 0.3, dampingFraction: 0.8, blendDuration: 0.25), value: position)
            .gesture(
                DragGesture()
                    .updating($translation) { value, state, _ in
                        state = value.translation.height
                    }
                    .onChanged { _ in
                        isDragging = true
                    }
                    .onEnded { value in
                        isDragging = false
                        snapToNearestPosition(
                            dragOffset: value.translation.height,
                            velocity: value.predictedEndTranslation.height,
                            screenHeight: geometry.size.height
                        )
                    }
            )
        }
    }
    
    private var dragIndicator: some View {
        Capsule()
            .fill(Color.white.opacity(0.3))
            .frame(width: 40, height: 5)
            .onTapGesture {
                // Cycle through positions on tap
                cyclePosition()
            }
    }
    
    private func snapToNearestPosition(dragOffset: CGFloat, velocity: CGFloat, screenHeight: CGFloat) {
        let currentOffset = position.offsetFor(screenHeight: screenHeight)
        let finalOffset = currentOffset + dragOffset
        
        // Add velocity influence for more natural feeling
        let velocityInfluence = velocity * 0.2
        let targetOffset = finalOffset + velocityInfluence
        
        // Find nearest position
        var nearestPosition = position
        var minDistance = CGFloat.infinity
        
        for pos in BottomSheetPosition.allCases {
            let distance = abs(targetOffset - pos.offsetFor(screenHeight: screenHeight))
            if distance < minDistance {
                minDistance = distance
                nearestPosition = pos
            }
        }
        
        // Apply haptic feedback
        if nearestPosition != position {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
        
        position = nearestPosition
    }
    
    private func cyclePosition() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        switch position {
        case .compact:
            position = .medium
        case .medium:
            position = .expanded
        case .expanded:
            position = .compact
        }
    }
}

// MARK: - Preview
#Preview {
    ZStack {
        // Background content (simulating map)
        Color.blue.opacity(0.3)
            .ignoresSafeArea()
        
        // Bottom sheet
        BottomSheetView(position: .constant(.medium)) {
            VStack {
                Text("Bottom Sheet Content")
                    .font(.title)
                    .padding()
                
                Spacer()
            }
        }
    }
}