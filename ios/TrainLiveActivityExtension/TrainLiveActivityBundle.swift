import SwiftUI
import ActivityKit
import WidgetKit

@available(iOS 16.1, *)
@main
struct TrainLiveActivityBundle: WidgetBundle {
    var body: some Widget {
        TrainLiveActivity()
    }
}

// This file ensures the Live Activity widget is properly registered with the system