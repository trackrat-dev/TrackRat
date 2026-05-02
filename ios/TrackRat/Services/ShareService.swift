import Foundation
import SwiftUI

/// Service for generating shareable URLs and handling share functionality
class ShareService {
    static let shared = ShareService()
    
    private init() {}
    
    /// Generate a shareable URL for a train
    func createShareURL(
        for train: TrainV2,
        fromStationCode: String?,
        destinationName: String?
    ) -> URL? {
        let toStationCode: String? = destinationName.flatMap { Stations.getStationCode($0) }
        let deepLink = DeepLink(
            trainId: train.trainId,
            date: Date(), // Current date for context
            fromStationCode: fromStationCode,
            toStationCode: toStationCode
        )

        return deepLink.generateURL()
    }

    /// Generate share text for a train (e.g. ``"View NJT 7801 to Trenton"``).
    func createShareText(
        for train: TrainV2,
        fromStationCode: String?,
        destinationName: String?
    ) -> String {
        let toStationCode: String? = destinationName.flatMap { Stations.getStationCode($0) }
        let deepLink = DeepLink(
            trainId: train.trainId,
            date: Date(),
            fromStationCode: fromStationCode,
            toStationCode: toStationCode
        )

        return deepLink.generateShareText(
            dataSource: train.dataSource,
            destinationName: destinationName
        )
    }
    
    /// Present the native iOS share sheet
    func presentShareSheet(
        url: URL,
        from view: UIView? = nil
    ) {
        let items: [Any] = [url]
        let activityViewController = UIActivityViewController(
            activityItems: items,
            applicationActivities: nil
        )
        
        // For iPad support
        if let popover = activityViewController.popoverPresentationController {
            if let sourceView = view {
                popover.sourceView = sourceView
                popover.sourceRect = sourceView.bounds
            } else {
                // Fallback to center of screen
                if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                   let window = windowScene.windows.first {
                    popover.sourceView = window.rootViewController?.view
                    popover.sourceRect = CGRect(
                        x: window.frame.midX,
                        y: window.frame.midY,
                        width: 0,
                        height: 0
                    )
                }
            }
        }
        
        // Present the share sheet
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let window = windowScene.windows.first,
           let rootViewController = window.rootViewController {
            rootViewController.present(activityViewController, animated: true)
        }
    }
}

/// SwiftUI wrapper for share functionality
struct ShareButton: View {
    let train: TrainV2
    let fromStationCode: String?
    let destinationName: String?
    
    @State private var showingShareSheet = false
    
    var body: some View {
        Button(action: shareAction) {
            Image(systemName: "square.and.arrow.up")
                .font(.system(size: 14))
                .fontWeight(.medium)
                .foregroundColor(.white)
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showingShareSheet) {
            if let url = ShareService.shared.createShareURL(
                for: train,
                fromStationCode: fromStationCode,
                destinationName: destinationName
            ) {
                // Pass both the descriptive text and the URL as activity
                // items. iMessage typically still renders the rich preview
                // for the URL, but the text gives recipients a readable
                // message even if the preview is gated behind "tap to load".
                let text = ShareService.shared.createShareText(
                    for: train,
                    fromStationCode: fromStationCode,
                    destinationName: destinationName
                )
                ShareSheetView(items: [text, url])
            }
        }
    }
    
    private func shareAction() {
        showingShareSheet = true
    }
}

/// UIViewControllerRepresentable for UIActivityViewController
struct ShareSheetView: UIViewControllerRepresentable {
    let items: [Any]
    
    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(
            activityItems: items,
            applicationActivities: nil
        )
        return controller
    }
    
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {
        // No updates needed
    }
}