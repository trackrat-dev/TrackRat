import SwiftUI

struct ExperimentalFeaturesView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var viewModel: TrainDetailsViewModel // Assuming viewModel is passed from TrainDetailsView
    @State private var isExpanded = false
    @State private var showingHistory = false // To control the presentation of HistoricalDataView

    // Add a train property that can be passed from the parent view
    let train: Train

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "beaker.fill") // Using a science-related icon for experimental features
                    .foregroundColor(Color(hex: "667eea")) // Consistent with app's purple theme
                Text("Experimental Features")
                    .font(.headline)
                    .foregroundColor(Color.primary) // Adapts to light/dark mode
                Spacer()
                Button(action: { isExpanded.toggle() }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(Color.secondary) // Standard secondary color
                }
            }
            .padding()
            .background(Color(UIColor.systemGray6)) // A light gray background, common in iOS settings
            .cornerRadius(12)
            .onTapGesture {
                isExpanded.toggle()
            }

            // Expanded details
            if isExpanded {
                VStack(spacing: 20) {
                    // Live Activity controls
                    if #available(iOS 16.1, *) {
                        LiveActivityControls(
                            train: train,
                            origin: appState.selectedDeparture ?? "",
                            destination: appState.selectedDestination ?? "",
                            originCode: appState.departureStationCode ?? "",
                            destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                        )
                        .padding(.horizontal)
                    }

                    // Consolidated data section
                    if train.isConsolidated {
                        ConsolidatedDataCard(train: train) // Assuming this card is already styled appropriately or will be
                            .padding(.horizontal)
                    }

                    // Show history button
                    Button {
                        showingHistory = true
                    } label: {
                        HStack {
                            Image(systemName: "clock.arrow.circlepath")
                            Text("Details from past trains")
                                .font(.subheadline)
                        }
                        .foregroundColor(Color(hex: "667eea")) // Use accent color
                    }
                    .padding(.horizontal)
                    .padding(.bottom) // Add some padding at the bottom of the expanded section
                }
                .sheet(isPresented: $showingHistory) {
                    HistoricalDataView(train: train) // Present HistoricalDataView as a sheet
                }
            }
        }
        .animation(.easeInOut(duration: 0.3), value: isExpanded)
    }
}
