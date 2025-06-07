import SwiftUI

struct ExperimentalFeaturesView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var viewModel: TrainDetailsViewModel // Assuming viewModel is passed from TrainDetailsView
    @State private var isExpanded = false
    @State private var showingHistory = false // To control the presentation of HistoricalDataView

    // Add a train property that can be passed from the parent view
    let train: Train

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Image(systemName: "flask.fill")
                    .foregroundColor(.orange)
                Text("Experimental Features")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Button(action: { isExpanded.toggle() }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.white)
                }
            }
            .padding()
            .background(Color.black)
            .cornerRadius(12, corners: isExpanded ? [.topLeft, .topRight] : [.allCorners])
            .onTapGesture {
                isExpanded.toggle()
            }

            // Expanded details
            if isExpanded {
                VStack(spacing: 8) {
                    // Live Activity controls
                    if #available(iOS 16.1, *) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Live Activity")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(.white)
                            
                            LiveActivityControls(
                                train: train,
                                origin: appState.selectedDeparture ?? "",
                                destination: appState.selectedDestination ?? "",
                                originCode: appState.departureStationCode ?? "",
                                destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                            )
                        }
                        .padding()
                        .background(Color.black)
                    }

                    // Consolidated data section
                    if train.isConsolidated {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Multi-Source Data")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(.white)
                            
                            ConsolidatedDataCard(train: train)
                        }
                        .padding()
                        .background(Color.black)
                    }

                    // Show history section
                    Button {
                        showingHistory = true
                    } label: {
                        HStack {
                            Image(systemName: "clock.arrow.circlepath")
                            Text("View Historical Data")
                                .font(.subheadline)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                        }
                        .foregroundColor(.orange)
                        .padding()
                    }
                    .background(Color.black)
                }
                .background(Color.black)
                .cornerRadius(12, corners: [.bottomLeft, .bottomRight])
                .sheet(isPresented: $showingHistory) {
                    HistoricalDataView(train: train)
                }
            }
        }
        .animation(.easeInOut(duration: 0.3), value: isExpanded)
    }
}
