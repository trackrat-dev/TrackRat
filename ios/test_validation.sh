#!/bin/bash

# Test validation script for Phase 1: Foundation & Build Validation

echo "🚀 TrackRat iOS - Phase 1 Test Validation"
echo "========================================="

# Check if main project builds
echo "📦 Building main project..."
if xcodebuild -project TrackRat.xcodeproj -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16' build -quiet; then
    echo "✅ Main project builds successfully"
else
    echo "❌ Main project build failed"
    exit 1
fi

# Check test directory structure
echo ""
echo "📁 Checking test directory structure..."

required_dirs=(
    "TrackRatTests"
    "TrackRatTests/Models"
    "TrackRatTests/Services"
    "TrackRatTests/Views"
    "TrackRatTests/TestFixtures"
    "TrackRatTests/TestUtilities"
)

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir exists"
    else
        echo "❌ $dir missing"
        exit 1
    fi
done

# Check test files exist
echo ""
echo "📋 Checking test files..."

required_files=(
    "TrackRatTests/BuildTests.swift"
    "TrackRatTests/Models/TrainTests.swift"
    "TrackRatTests/Models/StationsTests.swift"
    "TrackRatTests/Services/APIServiceTests.swift"
    "TrackRatTests/Services/StorageServiceTests.swift"
    "TrackRatTests/TestFixtures/TrainTestData.swift"
    "TrackRatTests/TestUtilities/TestHelpers.swift"
    "TrackRatTests/TestUtilities/XCTestCase+Extensions.swift"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
        exit 1
    fi
done

# Check Swift syntax in test files
echo ""
echo "🔍 Validating Swift syntax in test files..."

find TrackRatTests -name "*.swift" | while read -r file; do
    if xcrun swiftc -parse "$file" -import-objc-header /dev/null > /dev/null 2>&1; then
        echo "✅ $file: Valid Swift syntax"
    else
        echo "❌ $file: Syntax errors"
        exit 1
    fi
done

echo ""
echo "🎉 Phase 1 validation complete!"
# Run actual tests to verify everything works
echo ""
echo "🧪 Running actual tests..."
if xcodebuild test -project TrackRat.xcodeproj -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16' -quiet; then
    echo "✅ All tests passed successfully!"
else
    echo "❌ Some tests failed"
    exit 1
fi

echo ""
echo "🎉 Phase 1 Complete - All Success Criteria Met:"
echo "✅ Project builds successfully"
echo "✅ Test target added and configured"
echo "✅ Test directory structure created"
echo "✅ Core test files implemented"
echo "✅ Test fixtures and utilities ready"
echo "✅ All Swift files have valid syntax"
echo "✅ All tests pass"
echo ""
echo "🚀 Ready for Phase 2: Service Layer Testing"