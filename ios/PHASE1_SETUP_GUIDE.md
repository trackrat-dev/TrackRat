# Phase 1: Foundation & Build Validation - Setup Guide

## ✅ Completed Tasks

All Phase 1 foundation work has been completed programmatically:

### 📁 Directory Structure Created
```
TrackRatTests/
├── BuildTests.swift                    # Basic compilation smoke tests
├── Info.plist                         # Test bundle configuration
├── Models/
│   ├── TrainTests.swift               # Train model unit tests
│   └── StationsTests.swift            # Stations data unit tests
├── Services/
│   ├── APIServiceTests.swift          # API service unit tests
│   └── StorageServiceTests.swift      # Storage service unit tests
├── TestFixtures/
│   └── TrainTestData.swift           # Sample data for testing
├── TestUtilities/
│   ├── TestHelpers.swift             # Helper functions and utilities
│   └── XCTestCase+Extensions.swift   # Test case extensions
└── Views/                             # (Empty, ready for future UI tests)
```

### 🧪 Test Files Created
- **BuildTests.swift**: Smoke tests that verify project compiles and core services instantiate
- **TrainTests.swift**: Unit tests for Train model initialization and properties
- **StationsTests.swift**: Tests for station data availability and search functionality
- **APIServiceTests.swift**: Tests for API service singleton and date decoding
- **StorageServiceTests.swift**: Tests for UserDefaults storage functionality
- **TrainTestData.swift**: Sample data fixtures for testing
- **TestHelpers.swift**: Utility functions for JSON decoding, date creation, and test assertions
- **XCTestCase+Extensions.swift**: Convenience methods for creating test objects

### ✅ Validation Complete
- ✅ Main project builds successfully
- ✅ All Swift test files have valid syntax
- ✅ Test infrastructure is ready
- ✅ Sample data and utilities available

## 🔧 Manual Xcode Setup Required

**Important**: The test target needs to be added manually in Xcode. Follow these steps:

### Step 1: Add Test Target to Xcode Project

1. **Open TrackRat.xcodeproj in Xcode**

2. **Add Test Target**:
   - Select the project in Navigator
   - Click the "+" button at the bottom of the targets list
   - Choose "iOS" → "Unit Testing Bundle" 
   - Name: `TrackRatTests`
   - Bundle Identifier: `net.trackrat.TrackRatTests`
   - Click "Finish"

3. **Configure Test Target**:
   - Delete the default `TrackRatTests.swift` file that Xcode creates
   - In Build Settings, set:
     - iOS Deployment Target: `17.0` (match main app)
     - Swift Language Version: `Swift 5`

### Step 2: Add Test Files to Target

1. **Add Test Directory**:
   - Right-click in Navigator
   - "Add Files to TrackRat"
   - Select the entire `TrackRatTests` folder
   - **Important**: Check "Add to target: TrackRatTests" (NOT TrackRat)
   - Click "Add"

2. **Verify File Targeting**:
   - Select any test file in Navigator
   - In File Inspector, ensure only "TrackRatTests" target is checked

### Step 3: Configure Test Scheme

1. **Edit Scheme**:
   - Product → Scheme → Edit Scheme
   - Select "Test" action
   - Click "+" to add test target
   - Add "TrackRatTests"
   - Ensure it's set to run on same device as main app

### Step 4: Test the Setup

Run these commands to verify everything works:

```bash
# Run tests via command line
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'

# Or in Xcode: Product → Test (⌘U)
```

## 📋 Success Criteria Verification

After manual setup, verify these work:

- [ ] `xcodebuild test` runs without errors
- [ ] All smoke tests in BuildTests.swift pass
- [ ] Model tests pass (Train, Stations)
- [ ] Service tests pass (APIService, StorageService)
- [ ] Test infrastructure works (fixtures, helpers)

## 🚀 Next Steps

Once manual setup is complete, Phase 1 is done! Ready for:

- **Phase 2**: Service Layer Testing (API mocking, network tests)
- **Phase 3**: ViewModel Testing (business logic, state management)
- **Phase 4**: UI Testing (SwiftUI view tests)

## 🛠 Troubleshooting

### Common Issues

1. **"Cannot find 'TrackRat' in scope"**
   - Ensure `@testable import TrackRat` is working
   - Check that test target has proper dependency on main target

2. **"Use of unresolved identifier"**
   - Verify all test files are added to TrackRatTests target
   - Check that main app models are public/internal (not private)

3. **Build errors in tests**
   - Ensure iOS deployment target matches between app and tests
   - Verify Swift version is consistent

### Manual Verification Script

Run this after Xcode setup:

```bash
./test_validation.sh
```

This validates all files exist and syntax is correct.

## 📝 Implementation Notes

The test infrastructure includes:

- **Singleton Testing**: Verifies APIService, StorageService, LiveActivityService
- **Model Testing**: Basic Train model initialization and properties
- **Date Handling**: Tests for ISO8601 date parsing with multiple formats
- **Storage Testing**: UserDefaults operations with cleanup
- **JSON Decoding**: Test infrastructure for API response parsing
- **Test Utilities**: Helper functions and extensions for clean test code

All tests follow iOS testing best practices with proper setup/teardown and isolated test data.