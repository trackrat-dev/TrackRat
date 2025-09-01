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
    let showsIndicators: Bool
    let content: Content
    
    @State private var isScrolledToTop: Bool = true  // Track if we're at scroll top
    @State private var gestureMode: GestureMode = .idle
    
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
                            .onChange(of: innerGeo.frame(in: .global).minY) { newValue in
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
                }
            }
            .onAppear {
                // Initialize scroll state on appear
                print("📜 ScrollView appeared, initializing isScrolledToTop = true")
                isScrolledToTop = true
                // Ensure gesture state is clean on appear
                gestureMode = .idle
                print("🔧 ScrollView onAppear: Reset gestureMode to .idle")
            }
            .onChange(of: scenePhase) { oldPhase, newPhase in
                // Reset gesture state when app becomes active to prevent stuck states
                print("🔄 Scene phase changed: \(oldPhase) → \(newPhase)")
                
                switch newPhase {
                case .active:
                    // App became active - reset any stuck gesture states
                    if gestureMode != .idle {
                        print("⚠️ App became active with non-idle gesture mode: \(gestureMode)")
                        print("🔧 Resetting gestureMode to .idle")
                        gestureMode = .idle
                    }
                    // Re-evaluate scroll position when app becomes active
                    print("🔧 App active: Re-evaluating scroll position")
                    // Note: isScrolledToTop will be updated by the GeometryReader onChange
                    
                case .inactive:
                    // App is transitioning (e.g., control center, app switcher)
                    print("📱 App inactive - gesture mode: \(gestureMode)")
                    if gestureMode != .idle {
                        print("🔧 App inactive: Resetting gestureMode to .idle")
                        gestureMode = .idle
                    }
                    
                case .background:
                    // App entered background
                    print("📱 App entered background - gesture mode: \(gestureMode)")
                    if gestureMode != .idle {
                        print("🔧 App backgrounded: Force resetting gestureMode to .idle")
                        gestureMode = .idle
                    }
                    
                @unknown default:
                    print("❓ Unknown scene phase: \(newPhase)")
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
        
        print("🎯 Determining gesture mode:")
        print("   - Sheet position: \(sheetPosition)")
        print("   - Translation: \(translation)")
        print("   - isScrolledToTop: \(isScrolledToTop)")
        
        switch sheetPosition {
        case .medium:
            // From medium: only upward swipes do anything (expand sheet)
            if isSwipingUp {
                print("   → Mode: sheetMoving (will expand)")
                return .sheetMoving  // Will expand the sheet
            } else {
                print("   → Mode: idle (can't go lower)")
                return .idle  // Can't go lower than medium
            }
            
        case .expanded:
            // From expanded: depends on scroll position and direction
            if isSwipingUp {
                // Swiping up when expanded: always scroll (if there's content to scroll)
                print("   → Mode: scrolling (swipe up from expanded)")
                return .scrolling
            } else if isSwipingDown {
                // Swiping down when expanded: use our reliable scroll position flag
                if isScrolledToTop {
                    // We're truly at the top: collapse sheet
                    print("   → Mode: sheetMoving (at top, will collapse)")
                    return .sheetMoving
                } else {
                    // Not at top: must scroll up first
                    print("   → Mode: scrolling (not at top, will scroll up)")
                    return .scrolling
                }
            }
            print("   → Mode: idle (no swipe detected)")
            return .idle
        }
    }
    
    private func handleDragGesture(value: DragGesture.Value) {
        let translation = value.translation.height
        
        // Determine mode once at the start of gesture
        if gestureMode == .idle {
            print("🔄 Gesture started, determining mode...")
            print("   Current state - Sheet: \(sheetPosition), ScrollTop: \(isScrolledToTop)")
            let previousMode = gestureMode
            gestureMode = determineGestureMode(translation: translation)
            print("🔄 Gesture mode transition: \(previousMode) → \(gestureMode)")
            print("   Translation: \(translation), Direction: \(translation < 0 ? "Up" : "Down")")
            
            // If we determined this should be scrolling, let ScrollView handle it
            if gestureMode == .scrolling {
                print("🔄 Letting ScrollView handle the gesture")
            } else if gestureMode == .sheetMoving {
                print("🔄 Sheet will handle the gesture (ScrollView disabled)")
            }
        } else {
            // Log if we're getting drag updates while not idle (shouldn't happen normally)
            print("⚠️ Drag update received while gestureMode = \(gestureMode)")
        }
        
        // No position changes during drag - wait for gesture end
    }
    
    private func handleDragEnd(value: DragGesture.Value) {
        print("🏁 Gesture ending - Current mode: \(gestureMode)")
        
        defer {
            // Always reset gesture mode at the end
            let previousMode = gestureMode
            gestureMode = .idle
            print("🔧 Gesture mode reset: \(previousMode) → .idle")
        }
        
        // Only make position changes if we're in sheetMoving mode
        guard gestureMode == .sheetMoving else {
            print("🔄 Gesture ended without sheet movement, mode was: \(gestureMode)")
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
        
        // Apply position change if determined
        if shouldChangePosition {
            print("✅ Changing position to: \(targetPosition)")
            withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
                sheetPosition = targetPosition
            }
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } else {
            print("❌ Not changing position - insufficient velocity/translation")
        }
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