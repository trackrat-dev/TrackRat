import SwiftUI
import AVKit
import AVFoundation

struct VideoPlayerView: UIViewRepresentable {
    let url: URL
    var onEnd: (() -> Void)?
    var onError: ((Error) -> Void)?
    var onStart: (() -> Void)?
    
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        
        // Create player item first to ensure we start from beginning
        let playerItem = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: playerItem)
        
        // Ensure we start from the beginning
        player.seek(to: .zero)
        
        let playerLayer = AVPlayerLayer(player: player)
        playerLayer.videoGravity = .resizeAspectFill
        playerLayer.frame = view.bounds
        view.layer.addSublayer(playerLayer)
        
        context.coordinator.player = player
        context.coordinator.playerLayer = playerLayer
        
        // Set up end notification
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(Coordinator.playerDidFinishPlaying),
            name: .AVPlayerItemDidPlayToEndTime,
            object: playerItem
        )
        
        // Set up error observation
        playerItem.addObserver(
            context.coordinator,
            forKeyPath: "status",
            options: [.new, .initial],
            context: nil
        )
        
        // Don't start playing immediately - wait for ready state
        
        return view
    }
    
    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.playerLayer?.frame = uiView.bounds
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject {
        let parent: VideoPlayerView
        var player: AVPlayer?
        var playerLayer: AVPlayerLayer?
        
        init(_ parent: VideoPlayerView) {
            self.parent = parent
        }
        
        @objc func playerDidFinishPlaying() {
            parent.onEnd?()
        }
        
        override func observeValue(forKeyPath keyPath: String?, of object: Any?, change: [NSKeyValueChangeKey : Any]?, context: UnsafeMutableRawPointer?) {
            if keyPath == "status",
               let item = object as? AVPlayerItem {
                switch item.status {
                case .failed:
                    if let error = item.error {
                        parent.onError?(error)
                    }
                case .readyToPlay:
                    // Only start playing when the video is ready
                    if player?.timeControlStatus != .playing {
                        player?.seek(to: .zero) { _ in
                            self.player?.play()
                            // Notify that playback has started
                            self.parent.onStart?()
                        }
                    }
                case .unknown:
                    break
                @unknown default:
                    break
                }
            }
        }
        
        deinit {
            NotificationCenter.default.removeObserver(self)
            player?.currentItem?.removeObserver(self, forKeyPath: "status")
        }
    }
}