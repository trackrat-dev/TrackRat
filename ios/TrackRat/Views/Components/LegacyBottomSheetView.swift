import SwiftUI
import Combine

// MARK: - Shared drag state for coordinating between BottomSheetView and SheetAwareScrollView
class BottomSheetDragState: ObservableObject {
    @Published var translation: CGFloat = 0
    @Published var isDragging: Bool = false

    func reset() {
        translation = 0
        isDragging = false
    }
}

// MARK: - Preference Keys for Bottom Sheet communication
struct DragTranslationPreferenceKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

struct IsDraggingPreferenceKey: PreferenceKey {
    static var defaultValue: Bool = false
    static func reduce(value: inout Bool, nextValue: () -> Bool) {
        value = nextValue()
    }
}

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

    // Shared drag state for scrollable content
    @StateObject private var dragState = BottomSheetDragState()

    // Scene phase monitoring for safety
    @Environment(\.scenePhase) private var scenePhase
    
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
                    // For scrollable content, we pass the drag state through environment
                    if isScrollable {
                        content
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                            .environmentObject(dragState)
                    } else {
                        content
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                            .clipped()
                    }
                    
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
                    .fill(.ultraThinMaterial)
                    .ignoresSafeArea()
            )
            .offset(y: safeOffset(for: geometry.size.height))
            // Animate position changes smoothly, but not during active dragging
            .animation(
                (isDragging || dragState.isDragging) ? nil : .interactiveSpring(response: 0.3, dampingFraction: 0.95),
                value: position
            )
            .animation(
                (isDragging || dragState.isDragging) ? nil : .interactiveSpring(response: 0.3, dampingFraction: 0.95),
                value: dragState.translation
            )
            .onChange(of: scenePhase) { oldPhase, newPhase in
                print("🎛️ BottomSheet: Scene phase changed: \(oldPhase) → \(newPhase)")
                
                // Always reset dragging state on any phase change for safety
                if isDragging {
                    isDragging = false
                    print("🔧 BottomSheet: Reset isDragging to false")
                }
                // Note: @GestureState translation auto-resets
            }
            .gesture(
                // Only apply drag gesture to entire sheet if content is not scrollable
                isScrollable ? nil : DragGesture()
                    .updating($translation) { value, state, _ in
                        state = value.translation.height
                    }
                    .onChanged { _ in
                        if !isDragging {
                            print("🎛️ BottomSheet: Drag started (isDragging → true)")
                        }
                        isDragging = true
                    }
                    .onEnded { value in
                        print("🎛️ BottomSheet: Drag ended (isDragging → false)")
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

        // Use shared drag state for scrollable content, internal for non-scrollable
        let activeTranslation = isScrollable ? dragState.translation : translation

        // Apply translation limits
        var limitedTranslation = activeTranslation

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
                // Allow tap to cycle position
                cyclePosition()
            }
            .gesture(
                // Add drag gesture for smooth dragging
                DragGesture()
                    .onEnded { value in
                        let translation = value.translation.height
                        let velocity = value.predictedEndTranslation.height - translation
                        
                        // Use same thresholds as SheetAwareScrollView
                        let velocityThreshold: CGFloat = 50
                        let translationThreshold: CGFloat = 50
                        
                        if position == .medium {
                            // Swipe up to expand
                            if velocity < -velocityThreshold || translation < -translationThreshold {
                                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
                                    position = .expanded
                                }
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } else if position == .expanded {
                            // Swipe down to collapse
                            if velocity > velocityThreshold || translation > translationThreshold {
                                withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
                                    position = .medium
                                }
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        }
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
        
        // Direct position update - animation handled by SheetAwareScrollView
        position = nearestPosition
    }
    
    private func cyclePosition() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        // Simple toggle between medium and expanded
        // Animation only for tap gesture (SheetAwareScrollView doesn't handle taps)
        withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.95)) {
            switch position {
            case .medium:
                position = .expanded
            case .expanded:
                position = .medium
            }
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