import SwiftUI

// MARK: - Bottom Sheet Position
enum BottomSheetPosition: CaseIterable {
    case medium     // 50% of screen height
    case expanded   // 100% of screen height
    
    func offsetFor(screenHeight: CGFloat) -> CGFloat {
        switch self {
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
                    
                    // Gradient overlay to indicate hidden content (only when at medium)
                    if position == .medium {
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
                            .frame(height: 30)
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
        
        // Limit translation to only allow movement between medium and expanded
        var limitedTranslation = translation
        
        // Calculate the offsets for positions
        let mediumOffset = BottomSheetPosition.medium.offsetFor(screenHeight: screenHeight)
        let expandedOffset = BottomSheetPosition.expanded.offsetFor(screenHeight: screenHeight)
        
        // Limit based on current position
        switch position {
        case .medium:
            // Can only go up to expanded or stay at medium
            let maxUpwardOffset = expandedOffset - baseOffset
            let maxDownwardOffset: CGFloat = 0  // Don't allow going lower than medium
            limitedTranslation = max(maxUpwardOffset, min(maxDownwardOffset, limitedTranslation))
        case .expanded:
            // Can only go down to medium
            let maxDownwardOffset = mediumOffset - baseOffset
            limitedTranslation = min(maxDownwardOffset, max(0, limitedTranslation))
        }
        
        let combinedOffset = baseOffset + limitedTranslation
        
        // Additional safety: prevent sheet from going above screen or too far below
        let minOffset: CGFloat = 0
        let maxOffset = screenHeight * 0.5  // Medium is the lowest position now
        
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
                // Only allow drag on indicator when content is not scrollable
                // When scrollable, let SheetAwareScrollView handle everything
                isScrollable ? nil : DragGesture()
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
        // Determine direction
        let isDraggingUp = dragOffset < -10
        let isDraggingDown = dragOffset > 10
        
        var nearestPosition = position
        
        // Simple two-state logic
        if isDraggingUp && position == .medium {
            nearestPosition = .expanded
        } else if isDraggingDown && position == .expanded {
            nearestPosition = .medium
        }
        // Otherwise stay in current position
        
        // Apply haptic feedback
        if nearestPosition != position {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
        
        position = nearestPosition
    }
    
    private func cyclePosition() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        // Simple toggle between medium and expanded
        switch position {
        case .medium:
            position = .expanded
        case .expanded:
            position = .medium
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