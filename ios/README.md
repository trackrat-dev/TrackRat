# TrackRat iOS App

A minimalistic iOS app for tracking train departures from New York Penn Station with real-time updates and intelligent track predictions.

## Features

- **Destination Search**: Quick access to recent destinations and autocomplete search
- **Real-time Updates**: 30-second refresh intervals with boarding status notifications
- **Track Predictions**: "Owl" system shows confidence-based track predictions
- **Journey Tracking**: Visual stop indicators with destination highlighting
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
- API server accessible at `https://prod.api.trackrat.net/api`

## Setup

1. Open `TrackRat.xcodeproj` in Xcode
2. Ensure the API server is accessible at `https://prod.api.trackrat.net/api`
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