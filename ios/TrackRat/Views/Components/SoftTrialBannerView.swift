import SwiftUI
import Combine

struct SoftTrialBannerView: View {
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @State private var currentTime = Date()
    let onTap: () -> Void

    private let timer = Timer.publish(every: 60, on: .main, in: .common).autoconnect()

    private var hoursRemaining: Int {
        subscriptionService.softTrialHoursRemaining ?? 0
    }

    var body: some View {
        Button {
            onTap()
        } label: {
            HStack(spacing: 12) {
                Image(systemName: "clock.fill")
                    .font(TrackRatTheme.IconSize.small)
                    .foregroundColor(.orange)

                VStack(alignment: .leading, spacing: 2) {
                    Text("You have \(hoursRemaining) \(hoursRemaining == 1 ? "hour" : "hours") remaining")
                        .font(TrackRatTheme.Typography.bodySecondary)
                        .foregroundColor(.white)
                        .textProtected()

                    Text("Subscribe to keep Pro features and support development")
                        .font(TrackRatTheme.Typography.caption)
                        .foregroundColor(.white.opacity(0.7))
                        .textProtected(lines: 2)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(TrackRatTheme.IconSize.xsmall)
                    .foregroundColor(.orange)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color.orange.opacity(0.15))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color.orange.opacity(0.5), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
        .onReceive(timer) { time in
            currentTime = time
        }
    }
}

#Preview {
    VStack {
        SoftTrialBannerView {
            print("Banner tapped")
        }
        .padding()
    }
    .background(Color.black)
    .preferredColorScheme(.dark)
}
