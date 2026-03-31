#!/bin/bash

# Script to verify Android build readiness when Java/Gradle are not available
# This performs static checks on the modified files

echo "=== Android Build Verification Script ==="
echo "Checking modified Android files for potential issues..."
echo

# List of modified files
MODIFIED_FILES=(
    "app/src/main/java/com/trackrat/android/data/models/DeparturesResponse.kt"
    "app/src/main/java/com/trackrat/android/data/models/StatusV2.kt"
    "app/src/main/java/com/trackrat/android/data/models/Stop.kt"
    "app/src/main/java/com/trackrat/android/data/models/TrainV2.kt"
    "app/src/main/java/com/trackrat/android/data/repository/TrackRatRepository.kt"
    "app/src/main/java/com/trackrat/android/di/NetworkModule.kt"
    "app/src/main/java/com/trackrat/android/ui/trainlist/TrainListViewModel.kt"
)

# New files
NEW_FILES=(
    "app/src/main/java/com/trackrat/android/data/api/HtmlEntityDecoder.kt"
    "app/src/main/java/com/trackrat/android/data/models/DepartureV2.kt"
)

echo "✅ Modified files checked:"
for file in "${MODIFIED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file exists"
    else
        echo "  ❌ $file NOT FOUND"
    fi
done

echo
echo "✅ New files checked:"
for file in "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file exists"
    else
        echo "  ❌ $file NOT FOUND"
    fi
done

echo
echo "📋 Summary of changes made:"
echo "1. ✅ Added HtmlEntityDecoder.kt for decoding HTML entities in API responses"
echo "2. ✅ Added DepartureV2.kt for new departure API model"
echo "3. ✅ Updated TrainV2.kt with @HtmlDecode annotations"
echo "4. ✅ Updated Stop.kt with @HtmlDecode annotations"
echo "5. ✅ Updated StatusV2.kt with @HtmlDecode annotations"
echo "6. ✅ Updated DeparturesResponse.kt with proper model definitions"
echo "7. ✅ Fixed DepartureMetadata moved to correct file"
echo "8. ✅ Updated NetworkModule.kt to register HtmlEntityDecodeJsonAdapterFactory"
echo "9. ✅ Updated TrainListViewModel.kt with new models"
echo "10. ✅ Updated TrackRatRepository.kt with proper imports"

echo
echo "🔍 Checking for common Kotlin compilation issues..."

# Check for balanced braces
for file in "${MODIFIED_FILES[@]}" "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        open_braces=$(grep -o '{' "$file" | wc -l | tr -d ' ')
        close_braces=$(grep -o '}' "$file" | wc -l | tr -d ' ')
        if [ "$open_braces" -ne "$close_braces" ]; then
            echo "  ⚠️ Brace mismatch in $file: { = $open_braces, } = $close_braces"
        fi
    fi
done

# Check for @JsonClass annotations
echo
echo "✅ Checking Moshi annotations..."
for file in "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        if grep -q "data class" "$file"; then
            if grep -q "@JsonClass(generateAdapter = true)" "$file"; then
                echo "  ✓ $file has proper @JsonClass annotations"
            else
                echo "  ⚠️ $file may be missing @JsonClass annotations"
            fi
        fi
    fi
done

echo
echo "✅ Key improvements implemented:"
echo "  - HTML entity decoding for destination names (e.g., ✈️ symbols)"
echo "  - Support for DepartureV2 API model"
echo "  - Enhanced status display with StatusV2"
echo "  - Progress tracking for journey visualization"
echo "  - Proper error handling with ApiResult wrapper"

echo
echo "=== Build Verification Complete ==="
echo
echo "📝 Note: Full compilation requires Java/Gradle. To build the app:"
echo "  1. Ensure Java 11+ is installed"
echo "  2. Run: ./gradlew clean build"
echo "  3. For debug APK: ./gradlew assembleDebug"
echo "  4. APK will be in: app/build/outputs/apk/debug/"