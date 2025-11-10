import SwiftUI

// MARK: - Gesture Mode
/// Tracks what action a gesture should perform
enum GestureMode {
    case idle           // No gesture active
    case sheetMoving    // Sheet is being moved, block scrolling
    case scrolling      // Content is scrolling, block sheet movement
}

// MARK: - Sheet-Aware ScrollView
/// A custom ScrollView that coordinates with BottomSheetView position
/// to provide intuitive gesture handling:
/// - One swipe = one action (either sheet movement OR scrolling, never both)
/// - When sheet is not expanded: swipe up expands sheet first
/// - When sheet is expanded & content at top: swipe down collapses sheet
/// - Otherwise: normal scrolling behavior
struct SheetAwareScrollView<Content: View>: View {
    @Binding var sheetPosition: BottomSheetPosition
    @EnvironmentObject var dragState: BottomSheetDragState  // Shared drag state
    let showsIndicators: Bool
    let content: Content

    @State private var isScrolledToTop: Bool = true  // Track if we're at scroll top
    @State private var gestureMode: GestureMode = .idle

    // ScrollView recreation ID - changing this forces SwiftUI to recreate the ScrollView
    @State private var scrollViewID = UUID()

    // Scene phase monitoring to detect app lifecycle changes
    @Environment(\.scenePhase) private var scenePhase
    
    init(
        sheetPosition: Binding<BottomSheetPosition>,
        showsIndicators: Bool = true,
        @ViewBuilder content: () -> Content
    ) {
        self._sheetPosition = sheetPosition
        self.showsIndicators = showsIndicators
        self.content = content()
    }
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView(.vertical, showsIndicators: showsIndicators) {
                VStack(spacing: 0) {
                    // Track position with a background GeometryReader
                    GeometryReader { innerGeo in
                        Color.clear
                            .onChange(of: innerGeo.frame(in: .global).minY) { _, newValue in
                                // Check if we're at the top
                                // The scroll view content starts at the same Y as the scroll view itself when at top
                                let scrollViewTop = geometry.frame(in: .global).minY
                                let contentTop = newValue
                                let wasScrolledToTop = isScrolledToTop

                                // We're at top if content hasn't moved up (within small tolerance)
                                isScrolledToTop = contentTop >= (scrollViewTop - 2)
                                
                                if wasScrolledToTop != isScrolledToTop {
                                    print("📜 Scroll state changed: isScrolledToTop = \(isScrolledToTop), contentTop = \(contentTop), scrollViewTop = \(scrollViewTop)")
                                }
                            }
                    }
                    .frame(height: 0)  // Invisible tracker
                    
                    // Actual content
                    content
                        .onAppear {
                            print("📜 SheetAwareScrollView: Content appeared")
                        }
                }
            }
            .id(scrollViewID)  // Forces ScrollView recreation when ID changes
            .onAppear {
                // Initialize state on appear
                isScrolledToTop = true
                gestureMode = .idle
            }
            .onChange(of: scenePhase) { newPhase in
                print("🔄 Scene phase changed to: \(newPhase)")

                switch newPhase {
                case .active:
                    // App became active - always recreate ScrollView when resuming
                    // Force ScrollView recreation to ensure clean state
                    print("🔧 App resumed: Forcing ScrollView recreation")
                    scrollViewID = UUID()

                    // Reset all gesture-related state to defaults
                    gestureMode = .idle
                    isScrolledToTop = true
                    dragState.reset()
                    print("✅ ScrollView recreated with fresh state")
                    
                case .inactive:
                    // App is transitioning - reset gesture state for safety
                    print("📱 App inactive")
                    gestureMode = .idle
                    
                case .background:
                    // App entered background - reset gesture state
                    print("📱 App backgrounded")
                    gestureMode = .idle
                    
                @unknown default:
                    break
                }
            }
            .disabled(gestureMode == .sheetMoving)  // Disable scroll when sheet is moving
            .simultaneousGesture(
                // Use simultaneous gesture to detect gesture start and determine mode
                DragGesture(minimumDistance: 5)
                    .onChanged { value in
                        handleDragGesture(value: value)
                    }
                    .onEnded { value in
                        handleDragEnd(value: value)
                    }
            )
        }
    }
    
    private func determineGestureMode(translation: CGFloat) -> GestureMode {
        // Determine what action should happen based on current state and swipe direction
        let isSwipingUp = translation < 0
        let isSwipingDown = translation > 0
        
        switch sheetPosition {
        case .medium:
            // From medium: only upward swipes do anything (expand sheet)
            if isSwipingUp {
                return .sheetMoving  // Will expand the sheet
            } else {
                return .idle  // Can't go lower than medium
            }
            
        case .expanded:
            // From expanded: depends on scroll position and direction
            if isSwipingUp {
                // Swiping up when expanded: always scroll (if there's content to scroll)
                return .scrolling
            } else if isSwipingDown {
                // Swiping down when expanded: check scroll position
                if isScrolledToTop {
                    // We're truly at the top: collapse sheet
                    return .sheetMoving
                } else {
                    // Not at top: must scroll up first
                    return .scrolling
                }
            }
            return .idle
        }
    }
    
    private func handleDragGesture(value: DragGesture.Value) {
        let translation = value.translation.height

        // Determine mode once at the start of gesture
        if gestureMode == .idle {
            gestureMode = determineGestureMode(translation: translation)
            print("🔄 Gesture: \(gestureMode) (Sheet: \(sheetPosition), Translation: \(String(format: "%.1f", translation)))")

            // Set dragging state when we start moving the sheet
            if gestureMode == .sheetMoving {
                dragState.isDragging = true
            }
        }

        // Update translation in real-time when moving the sheet
        if gestureMode == .sheetMoving {
            dragState.translation = translation
        }
    }
    
    private func handleDragEnd(value: DragGesture.Value) {
        defer {
            // Always reset gesture mode at the end
            gestureMode = .idle
        }

        // Only make position changes if we're in sheetMoving mode
        guard gestureMode == .sheetMoving else {
            return
        }

        let translation = value.translation.height
        let velocity = value.predictedEndTranslation.height - translation

        print("🎯 Gesture ended with translation: \(translation), velocity: \(velocity)")

        // Determine intent based on velocity and translation
        // Velocity threshold for "intentional" swipe
        let velocityThreshold: CGFloat = 50

        // Translation threshold for "sufficient" drag
        let translationThreshold: CGFloat = 50

        // Determine if user intended to change position
        let shouldChangePosition: Bool
        let targetPosition: BottomSheetPosition

        switch sheetPosition {
        case .medium:
            // From medium, can only go to expanded (swipe up)
            let hasStrongUpwardVelocity = velocity < -velocityThreshold
            let hasSufficientUpwardDrag = translation < -translationThreshold

            shouldChangePosition = hasStrongUpwardVelocity || hasSufficientUpwardDrag
            targetPosition = .expanded

            print("📊 From medium: velocity=\(velocity), translation=\(translation)")
            print("   Strong velocity: \(hasStrongUpwardVelocity), Sufficient drag: \(hasSufficientUpwardDrag)")

        case .expanded:
            // From expanded, can only go to medium (swipe down)
            // We already verified we're at scroll top in determineGestureMode
            let hasStrongDownwardVelocity = velocity > velocityThreshold
            let hasSufficientDownwardDrag = translation > translationThreshold

            shouldChangePosition = hasStrongDownwardVelocity || hasSufficientDownwardDrag
            targetPosition = .medium

            print("📊 From expanded: velocity=\(velocity), translation=\(translation)")
            print("   Strong velocity: \(hasStrongDownwardVelocity), Sufficient drag: \(hasSufficientDownwardDrag)")
        }

        // Apply position change and reset translation with animation
        if shouldChangePosition {
            print("✅ Changing position to: \(targetPosition)")
            withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
                sheetPosition = targetPosition
                dragState.translation = 0  // Reset translation to 0 with animation
            }
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } else {
            print("❌ Not changing position - insufficient velocity/translation")
            // Snap back to current position
            withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
                dragState.translation = 0  // Reset translation to 0 with animation
            }
        }

        // Reset dragging state
        dragState.isDragging = false
    }
    
}

// MARK: - Helper Extension
extension SheetAwareScrollView {
    /// Convenience initializer for simple content without explicit scroll control
    init(
        sheetPosition: Binding<BottomSheetPosition>,
        @ViewBuilder content: () -> Content
    ) {
        self.init(
            sheetPosition: sheetPosition,
            showsIndicators: true,
            content: content
        )
    }
}