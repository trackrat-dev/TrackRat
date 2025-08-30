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
            }
            .disabled(gestureMode == .sheetMoving)  // Disable scroll when sheet is moving
            .simultaneousGesture(
                // Use simultaneous gesture to detect gesture start and determine mode
                DragGesture(minimumDistance: 5)
                    .onChanged { value in
                        handleDragGesture(value: value)
                    }
                    .onEnded { _ in
                        gestureMode = .idle  // Reset for next gesture
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
            gestureMode = determineGestureMode(translation: translation)
            print("🔄 Gesture mode set to: \(gestureMode)")
            
            // If we determined this should be scrolling, do nothing else
            // The ScrollView will handle it naturally
            if gestureMode == .scrolling {
                print("🔄 Letting ScrollView handle the gesture")
                return
            }
        }
        
        // Only handle sheet movement if we're in sheetMoving mode
        if gestureMode == .sheetMoving {
            // Check if we should actually move the sheet based on drag distance
            if sheetPosition == .medium && translation < -20 {
                // Expand the sheet
                print("📍 Expanding sheet from medium to expanded")
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .expanded
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                
            } else if sheetPosition == .expanded && translation > 20 {
                // Collapse the sheet (we already verified we're at scroll top in determineGestureMode)
                print("📍 Collapsing sheet from expanded to medium")
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .medium
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
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