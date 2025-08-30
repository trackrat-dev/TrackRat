import SwiftUI

// MARK: - Sheet-Aware ScrollView
/// A custom ScrollView that coordinates with BottomSheetView position
/// to provide intuitive gesture handling:
/// - When sheet is not expanded: swipe up expands sheet first
/// - When sheet is expanded & content at top: swipe down collapses sheet
/// - Otherwise: normal scrolling behavior
struct SheetAwareScrollView<Content: View>: View {
    @Binding var sheetPosition: BottomSheetPosition
    let showsIndicators: Bool
    let content: Content
    
    @State private var scrollOffset: CGFloat = 0
    @State private var isDragging = false
    @State private var gestureStartPosition: CGFloat = 0
    @State private var hasTriggeredPositionChange = false
    @State private var isScrollingEnabled = true
    
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
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: showsIndicators) {
                VStack(spacing: 0) {
                    // Hidden anchor for scroll position tracking
                    Color.clear
                        .frame(height: 1)
                        .id("top")
                    
                    // Actual content
                    content
                        .allowsHitTesting(isScrollingEnabled) // Prevent interaction when disabled
                    
                    // Track scroll position
                    GeometryReader { geometry in
                        Color.clear
                            .preference(key: ScrollOffsetPreferenceKey.self,
                                      value: geometry.frame(in: .named("scroll")).minY)
                    }
                    .frame(height: 0)
                }
            }
            .coordinateSpace(name: "scroll")
            .onPreferenceChange(ScrollOffsetPreferenceKey.self) { value in
                scrollOffset = value
            }
            .disabled(!isScrollingEnabled) // Disable scrolling when needed
            .simultaneousGesture(
                DragGesture(minimumDistance: 10)
                    .onChanged { value in
                        handleDragChanged(value: value, proxy: proxy)
                    }
                    .onEnded { value in
                        handleDragEnded(value: value)
                    }
            )
        }
    }
    
    private func handleDragChanged(value: DragGesture.Value, proxy: ScrollViewProxy) {
        if !isDragging {
            isDragging = true
            gestureStartPosition = value.location.y
            hasTriggeredPositionChange = false
        }
        
        // Only trigger position change once per gesture
        if hasTriggeredPositionChange {
            return
        }
        
        let translation = value.translation.height
        var shouldMoveSheet = false
        
        // Determine if sheet should move instead of scrolling
        if sheetPosition == .compact && translation < -20 {
            // Sheet is compact and swiping up -> expand to medium
            shouldMoveSheet = true
        } else if sheetPosition == .medium && translation < -20 {
            // Sheet is medium and swiping up -> expand fully
            shouldMoveSheet = true
        } else if sheetPosition == .expanded && scrollOffset >= -10 && translation > 50 {
            // Sheet is expanded, at top of scroll, swiping down -> collapse to medium
            shouldMoveSheet = true
        } else if sheetPosition == .medium && translation > 50 {
            // Sheet is at medium and swiping down -> collapse to compact
            shouldMoveSheet = true
        }
        
        // If sheet should move, disable scrolling first
        if shouldMoveSheet {
            hasTriggeredPositionChange = true
            isScrollingEnabled = false // Disable scrolling immediately
            
            // Perform the sheet movement
            if sheetPosition == .compact && translation < -20 {
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .medium
                }
            } else if sheetPosition == .medium && translation < -20 {
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .expanded
                }
            } else if sheetPosition == .expanded && scrollOffset >= -10 && translation > 50 {
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .medium
                }
            } else if sheetPosition == .medium && translation > 50 {
                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                    sheetPosition = .compact
                }
            }
            
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            
            // Re-enable scrolling after animation completes
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                isScrollingEnabled = true
            }
        }
    }
    
    private func handleDragEnded(value: DragGesture.Value) {
        isDragging = false
        gestureStartPosition = 0
        hasTriggeredPositionChange = false
        
        // Ensure scrolling is re-enabled after gesture ends
        if !isScrollingEnabled {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                isScrollingEnabled = true
            }
        }
    }
}

// MARK: - Preference Key for Scroll Offset
struct ScrollOffsetPreferenceKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
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