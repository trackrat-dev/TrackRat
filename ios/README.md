# TrackRat iOS App

A comprehensive iOS app for tracking NJ Transit and Amtrak trains with Live Activities, real-time updates, and intelligent track predictions.

## Features

- **Live Activities**: Real-time train tracking on Lock Screen and Dynamic Island
- **Multi-Station Support**: Departures from NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- **Real-time Updates**: 30-second refresh intervals with push notifications
- **Track Predictions**: "Owl" system shows confidence-based track predictions
- **Journey Tracking**: Visual progress indicators with stop-by-stop updates
- **Historical Analytics**: Performance data and track usage statistics
- **Native iOS Experience**: Haptic feedback, pull-to-refresh, and smooth animations

## Architecture

- **SwiftUI**: Modern declarative UI framework
- **Combine**: Reactive data flow and automatic UI updates
- **Async/Await**: Clean asynchronous API calls
- **MVVM Pattern**: Clear separation of concerns with ViewModels

## Requirements

- iOS 17.0+
- Xcode 15.0+
- Backend V2 API running (local or deployed)

## Setup

1. Open `TrackRat.xcodeproj` in Xcode
2. Configure API endpoint in the app (defaults to local development)
3. Build and run on simulator or device

## Project Structure

```
TrackRat/
├── App/
│   ├── TrackRatApp.swift      # Main app entry point
│   └── ContentView.swift       # Navigation root
├── Models/
│   ├── Train.swift            # Core data models
│   └── Stations.swift         # Station list and search
├── Services/
│   ├── APIService.swift       # API client
│   └── StorageService.swift   # Local persistence
├── Views/
│   └── Screens/
│       ├── TripSelectionView.swift
│       ├── AdvancedConfigurationView.swift
│       ├── DeparturePickerView.swift
│       ├── DestinationPickerView.swift
│       ├── TrainListView.swift
│       ├── TrainDetailsView.swift
│       ├── TrainNumberSearchView.swift
│       └── HistoricalDataView.swift
└── Resources/
    └── Info.plist             # App configuration
```

## Key Design Decisions

- **No External Dependencies**: Uses only native iOS frameworks
- **Single Navigation Stack**: Simple, predictable navigation flow
- **Optimistic UI**: Immediate feedback with background updates
- **Error Recovery**: Graceful handling with retry options
- **Accessibility**: Dynamic Type and VoiceOver support

## Future Enhancements

- Widget for Today View
- Push notifications for boarding status
- Siri Shortcuts integration
- Apple Watch companion app
- Offline mode with caching