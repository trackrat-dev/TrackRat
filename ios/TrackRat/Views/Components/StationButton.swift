import SwiftUI

struct StationButton: View {
    let name: String
    let code: String
    let onTap: () -> Void
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                Text(Stations.displayName(for: name))
                    .font(.headline)
                    .foregroundColor(.white)
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.white.opacity(0.7))
                    .font(.caption)
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(.white.opacity(0.2))
            .cornerRadius(12)
        }
    }
}

#Preview {
    StationButton(
        name: "New York Penn Station",
        code: "NY"
    ) {
        print("Station selected")
    }
    .padding()
    .background(TrackRatTheme.Colors.surface)
}