# Plan to Fix Live Activities (V2)

## 1. Problem Summary

The Live Activity feature is not working because the UI components are in the main app target (`TrackRat`) instead of a dedicated Widget Extension target (`TrainLiveActivityExtension`). This prevents iOS from discovering and displaying the Live Activities.

This plan outlines the steps to move the necessary files, configure the targets correctly, and ensure the Live Activity feature works as intended.

## 2. Code and File Changes

### Step 2.1: Create a Shared Directory

To avoid code duplication, we will create a shared directory for files that need to be accessed by both the main app and the widget extension.

1.  Create a new directory at `ios/TrackRat/Shared`.
2.  Move the following files into this new directory:
    *   `ios/TrackRat/Models/LiveActivityModels.swift` -> `ios/TrackRat/Shared/LiveActivityModels.swift`
    *   `ios/TrackRat/Models/Stations.swift` -> `ios/TrackRat/Shared/Stations.swift` (Assuming this is where the `Stations` helper is located, will verify)

### Step 2.2: Move Live Activity Source Files

The core Live Activity source files must be moved to the extension's directory.

1.  Move `ios/TrackRat/LiveActivity/TrainLiveActivityBundle.swift` to `ios/TrainLiveActivityExtension/TrainLiveActivityBundle.swift`.
2.  Move `ios/TrackRat/Views/LiveActivityWidget.swift` to `ios/TrainLiveActivityExtension/LiveActivityWidget.swift`.

### Step 2.3: Correct the Extension's `Info.plist`

The `Info.plist` for the extension is missing a critical key.

1.  Open `ios/TrainLiveActivityExtension/Info.plist`.
2.  Add the `NSExtensionPrincipalClass` key to the `NSExtension` dictionary:
    ```xml
    <key>NSExtension</key>
    <dict>
        <key>NSExtensionPointIdentifier</key>
        <string>com.apple.widgetkit-extension</string>
        <key>NSExtensionPrincipalClass</key>
        <string>$(PRODUCT_MODULE_NAME).TrainLiveActivityBundle</string>
    </dict>
    ```

## 3. Xcode Project Configuration (Manual Steps)

These changes must be made within the Xcode IDE, as they involve modifying the project's build settings and target memberships.

### Step 3.1: Update Target Membership for Moved Files

1.  Open `TrackRat.xcodeproj` in Xcode.
2.  In the Project Navigator, locate the files that were moved in **Step 2.2**:
    *   `TrainLiveActivityBundle.swift`
    *   `LiveActivityWidget.swift`
3.  For each file, open the "Target Membership" inspector on the right-hand side.
4.  Ensure that each file is a member of the `TrainLiveActivityExtension` target **only**. Uncheck the `TrackRat` target if it is selected.

### Step 3.2: Update Target Membership for Shared Files

1.  In the Project Navigator, locate the files that were moved in **Step 2.1**:
    *   `LiveActivityModels.swift`
    *   `Stations.swift`
2.  For each file, open the "Target Membership" inspector.
3.  Ensure that each file is a member of **both** the `TrackRat` and `TrainLiveActivityExtension` targets.

### Step 3.3: Verify Embedded Content

1.  Go to the `TrackRat` target's "General" settings.
2.  Under "Frameworks, Libraries, and Embedded Content", ensure that `TrainLiveActivityExtension.appex` is listed and set to "Embed & Sign".

## 4. Operational Steps (Post-Implementation)

After the code and project changes are complete, follow these steps to validate the fix:

### Step 4.1: Clean and Build

1.  In Xcode, perform a clean build by pressing **Cmd+Shift+K**.
2.  Build the project for a **physical iOS device** (Live Activities do not work reliably on the simulator).

### Step 4.2: Run and Test

1.  Run the app on the physical device.
2.  Start tracking a train to initiate a Live Activity.
3.  **Verification:**
    *   Confirm that the Live Activity appears on the Lock Screen.
    *   Confirm that the Dynamic Island shows the compact Live Activity view.
    *   Tap the Dynamic Island to see the expanded view.
    *   Verify that the Live Activity updates in real-time as the train's status changes.

### Step 4.3: Troubleshooting

If the Live Activity still does not appear:

1.  **Check Device Console:** Connect the device to a Mac and open the "Console" app. Filter for messages from `TrackRat` and `TrainLiveActivityExtension` to look for errors.
2.  **Verify Entitlements:** Double-check that both the `TrackRat.entitlements` and `TrainLiveActivityExtension.entitlements` files contain the necessary keys for Live Activities and push notifications.
3.  **Check Bundle Identifiers:** Ensure the bundle identifiers for the main app and the extension are correct and follow the `net.trackrat.TrackRat` and `net.trackrat.TrackRat.TrainLiveActivityExtension` pattern.