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
    let isScrollable: Bool
    
    // Drag gesture state
    @GestureState private var translation: CGFloat = 0
    @State private var isDragging = false
    @State private var scrollOffset: CGFloat = 0
    
    init(position: Binding<BottomSheetPosition>, isScrollable: Bool = false, @ViewBuilder content: () -> Content) {
        self._position = position
        self.isScrollable = isScrollable
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
                ZStack {
                    content
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                        .clipped()
                    
                    // Gradient overlay to indicate hidden content (only when not fully expanded)
                    if position != .expanded {
                        VStack {
                            Spacer()
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    Color.clear,
                                    TrackRatTheme.Colors.surface.opacity(0.6),
                                    TrackRatTheme.Colors.surface
                                ]),
                                startPoint: .top,
                                endPoint: .bottom
                            )
                            .frame(height: position == .compact ? 20 : 30)
                            .allowsHitTesting(false) // Allow gestures to pass through
                        }
                    }
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(TrackRatTheme.Colors.surface)
                    .ignoresSafeArea()
            )
            .offset(y: safeOffset(for: geometry.size.height))
            .animation(.interactiveSpring(response: 0.3, dampingFraction: 0.8, blendDuration: 0.25), value: position)
            .gesture(
                // Only apply drag gesture to entire sheet if content is not scrollable
                isScrollable ? nil : DragGesture()
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
    
    // Helper function to safely combine position offset and drag translation
    private func safeOffset(for screenHeight: CGFloat) -> CGFloat {
        let baseOffset = position.offsetFor(screenHeight: screenHeight)
        
        // Limit translation to only allow movement to adjacent positions
        var limitedTranslation = translation
        
        // Calculate the offsets for adjacent positions
        let compactOffset = BottomSheetPosition.compact.offsetFor(screenHeight: screenHeight)
        let mediumOffset = BottomSheetPosition.medium.offsetFor(screenHeight: screenHeight)
        let expandedOffset = BottomSheetPosition.expanded.offsetFor(screenHeight: screenHeight)
        
        // Limit based on current position
        switch position {
        case .compact:
            // Can only go up to medium
            let maxUpwardOffset = mediumOffset - baseOffset
            limitedTranslation = max(maxUpwardOffset, min(0, limitedTranslation))
        case .medium:
            // Can go to compact or expanded
            let maxDownwardOffset = compactOffset - baseOffset
            let maxUpwardOffset = expandedOffset - baseOffset
            limitedTranslation = max(maxUpwardOffset, min(maxDownwardOffset, limitedTranslation))
        case .expanded:
            // Can only go down to medium
            let maxDownwardOffset = mediumOffset - baseOffset
            limitedTranslation = min(maxDownwardOffset, max(0, limitedTranslation))
        }
        
        let combinedOffset = baseOffset + limitedTranslation
        
        // Additional safety: prevent sheet from going above screen or too far below
        let minOffset: CGFloat = 0
        let maxOffset = screenHeight * 0.95
        
        return max(minOffset, min(maxOffset, combinedOffset))
    }
    
    private var dragIndicator: some View {
        Capsule()
            .fill(Color.white.opacity(0.3))
            .frame(width: 40, height: 5)
            .contentShape(Rectangle().size(width: 100, height: 44)) // Larger hit area
            .onTapGesture {
                // Cycle through positions on tap
                cyclePosition()
            }
            .gesture(
                // Drag indicator is always draggable for sheet positioning
                DragGesture()
                    .updating($translation) { value, state, _ in
                        state = value.translation.height
                    }
                    .onChanged { _ in
                        isDragging = true
                    }
                    .onEnded { value in
                        isDragging = false
                        // Get screen height from UIScreen since we don't have geometry here
                        let screenHeight = UIScreen.main.bounds.height
                        snapToNearestPosition(
                            dragOffset: value.translation.height,
                            velocity: value.predictedEndTranslation.height,
                            screenHeight: screenHeight
                        )
                    }
            )
    }
    
    private func snapToNearestPosition(dragOffset: CGFloat, velocity: CGFloat, screenHeight: CGFloat) {
        let currentOffset = position.offsetFor(screenHeight: screenHeight)
        let finalOffset = currentOffset + dragOffset
        
        // Determine direction and step through positions
        let isDraggingUp = dragOffset < -10
        let isDraggingDown = dragOffset > 10
        
        var nearestPosition = position
        
        // Step through positions based on drag direction
        if isDraggingUp {
            switch position {
            case .compact:
                nearestPosition = .medium
            case .medium:
                nearestPosition = .expanded
            case .expanded:
                nearestPosition = .expanded // Stay at expanded
            }
        } else if isDraggingDown {
            switch position {
            case .compact:
                nearestPosition = .compact // Stay at compact
            case .medium:
                nearestPosition = .compact
            case .expanded:
                nearestPosition = .medium
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
            position = .medium  // Go back to medium, not compact
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