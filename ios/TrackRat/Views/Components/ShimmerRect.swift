import SwiftUI

/// A rectangle with an animated shimmer/shine effect for skeleton loading states.
struct ShimmerRect: View {
    var width: CGFloat? = nil
    var height: CGFloat
    var cornerRadius: CGFloat = 6

    @State private var phase: CGFloat = -1

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius)
            .fill(Color(.secondarySystemGroupedBackground))
            .frame(width: width, height: height)
            .overlay(
                GeometryReader { geometry in
                    let gradientWidth = geometry.size.width * 0.6
                    LinearGradient(
                        colors: [.clear, .white.opacity(0.12), .clear],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: gradientWidth)
                    .offset(x: phase * (geometry.size.width + gradientWidth) - gradientWidth)
                }
                .clipped()
            )
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .onAppear {
                withAnimation(.linear(duration: 1.2).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }
}

#Preview {
    VStack(spacing: 12) {
        ShimmerRect(height: 200, cornerRadius: 12)
        ShimmerRect(width: 140, height: 20)
        HStack(spacing: 12) {
            ShimmerRect(height: 70)
            ShimmerRect(height: 70)
            ShimmerRect(height: 70)
        }
    }
    .padding()
    .background(Color(.systemGroupedBackground))
    .preferredColorScheme(.dark)
}
