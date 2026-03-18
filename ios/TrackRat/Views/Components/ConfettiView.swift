import SwiftUI

/// A confetti celebration effect that sprinkles colorful particles down the screen.
/// Fires once when `isActive` becomes true, then fades out after the animation completes.
struct ConfettiView: View {
    let isActive: Bool

    private let particleCount = 30
    private let colors: [Color] = [
        .orange,
        .orange.opacity(0.8),
        .yellow,
        .white,
        .white.opacity(0.7),
        Color(red: 0.4, green: 0.5, blue: 0.9), // Soft blue
        Color(red: 0.6, green: 0.3, blue: 0.7), // Soft purple
    ]

    var body: some View {
        ZStack {
            if isActive {
                ForEach(0..<particleCount, id: \.self) { index in
                    ConfettiParticle(
                        color: colors[index % colors.count],
                        index: index,
                        totalCount: particleCount
                    )
                }
            }
        }
        .allowsHitTesting(false)
    }
}

// MARK: - Single Confetti Particle

private struct ConfettiParticle: View {
    let color: Color
    let index: Int
    let totalCount: Int

    @State private var isAnimating = false

    // Deterministic randomness from index
    private var xStart: CGFloat {
        // Spread particles across full width
        let fraction = CGFloat(index) / CGFloat(totalCount)
        // Add offset variety based on index
        let jitter = CGFloat((index * 7 + 3) % 11) / 11.0 * 0.08 - 0.04
        return fraction + jitter
    }

    private var xDrift: CGFloat {
        // Horizontal drift during fall
        let seed = (index * 13 + 5) % 20
        return CGFloat(seed - 10) * 3
    }

    private var delay: Double {
        // Stagger start times over 0.6 seconds
        let seed = (index * 11 + 7) % 15
        return Double(seed) / 15.0 * 0.6
    }

    private var duration: Double {
        // Vary fall duration between 2.0 and 3.0 seconds
        let seed = (index * 17 + 3) % 10
        return 2.0 + Double(seed) / 10.0
    }

    private var rotationAmount: Double {
        let seed = (index * 19 + 2) % 8
        return Double(seed - 4) * 90
    }

    private var shapeType: Int {
        index % 3 // 0 = circle, 1 = rounded rect, 2 = capsule
    }

    private var particleSize: CGFloat {
        let seed = (index * 23 + 1) % 5
        return CGFloat(seed) + 4 // 4-8 points
    }

    var body: some View {
        GeometryReader { geo in
            confettiShape
                .frame(width: particleSize, height: shapeType == 1 ? particleSize * 1.5 : particleSize)
                .foregroundColor(color)
                .position(
                    x: geo.size.width * xStart + (isAnimating ? xDrift : 0),
                    y: isAnimating ? geo.size.height + 20 : -20
                )
                .rotationEffect(.degrees(isAnimating ? rotationAmount : 0))
                .opacity(isAnimating ? 0 : 1)
                .onAppear {
                    withAnimation(
                        .easeIn(duration: duration)
                        .delay(delay)
                    ) {
                        isAnimating = true
                    }
                }
        }
    }

    @ViewBuilder
    private var confettiShape: some View {
        switch shapeType {
        case 0:
            Circle()
        case 1:
            RoundedRectangle(cornerRadius: 2)
        default:
            Capsule()
        }
    }
}
