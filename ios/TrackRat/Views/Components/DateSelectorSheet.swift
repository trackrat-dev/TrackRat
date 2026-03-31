import SwiftUI

/// Sheet for selecting a date from the next 7 days.
/// Used in TrainListView to view schedules for future days.
struct DateSelectorSheet: View {
    @Binding var selectedDate: Date
    @Environment(\.dismiss) private var dismiss

    /// Eastern timezone calendar for consistent date handling with train schedules
    private static let easternCalendar: Calendar = {
        var calendar = Calendar.current
        calendar.timeZone = TimeZone(identifier: "America/New_York") ?? TimeZone.current
        return calendar
    }()

    /// Available dates (today + next 6 days) in Eastern time
    private var availableDates: [Date] {
        let today = Self.easternCalendar.startOfDay(for: Date())
        return (0..<7).compactMap { offset in
            Self.easternCalendar.date(byAdding: .day, value: offset, to: today)
        }
    }

    var body: some View {
        NavigationStack {
            List(availableDates, id: \.self) { date in
                DateRow(
                    date: date,
                    isSelected: Self.easternCalendar.isDate(date, inSameDayAs: selectedDate),
                    onSelect: {
                        selectedDate = date
                        dismiss()
                    },
                    easternCalendar: Self.easternCalendar
                )
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(Color.black)
            .navigationTitle("Select Day")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white.opacity(0.7))
                }
            }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
        .presentationBackground(.black)
        .preferredColorScheme(.dark)
    }
}

/// Individual date row in the selector
private struct DateRow: View {
    let date: Date
    let isSelected: Bool
    let onSelect: () -> Void
    let easternCalendar: Calendar

    private var isToday: Bool {
        easternCalendar.isDateInToday(date)
    }

    var body: some View {
        Button(action: onSelect) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(isToday ? "Today" : date.formatted(.dateTime.weekday(.wide)))
                            .font(.headline)
                            .foregroundColor(.white)

                        if isToday {
                            Text("Live")
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.green)
                                .cornerRadius(4)
                        }
                    }

                    Text(date.formatted(.dateTime.month(.abbreviated).day()))
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                }

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark")
                        .foregroundColor(.orange)
                        .fontWeight(.semibold)
                }
            }
            .padding(.vertical, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .listRowBackground(
            isSelected
                ? Color.white.opacity(0.1)
                : Color.clear
        )
        .listRowSeparatorTint(.white.opacity(0.1))
    }
}

#Preview {
    Color.black
        .ignoresSafeArea()
        .sheet(isPresented: .constant(true)) {
            DateSelectorSheet(selectedDate: .constant(Date()))
        }
}
