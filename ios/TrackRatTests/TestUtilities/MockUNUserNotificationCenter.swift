import UserNotifications
import XCTest // Import XCTest for XCTFail

// Availability check for the entire class
@available(iOS 10.0, *) // UNUserNotificationCenter is available from iOS 10
class MockUNUserNotificationCenter: UNUserNotificationCenter {

    // Properties to store captured data and control behavior
    private(set) var requestedAuthorizationOptions: UNAuthorizationOptions?
    var shouldGrantAuthorization: Bool = true // Default to granted
    var authorizationError: Error? = nil

    private(set) var addedNotificationRequests: [UNNotificationRequest] = []
    var addNotificationRequestError: Error? = nil

    var mockNotificationSettings: UNNotificationSettings?
    var getNotificationSettingsError: Error? = nil

    // Override requestAuthorization
    override func requestAuthorization(options: UNAuthorizationOptions, completionHandler: @escaping (Bool, Error?) -> Void) {
        requestedAuthorizationOptions = options
        // Simulate async behavior
        DispatchQueue.main.async {
            completionHandler(self.shouldGrantAuthorization, self.authorizationError)
        }
    }

    // Override add UNNotificationRequest
    override func add(_ request: UNNotificationRequest, withCompletionHandler completionHandler: ((Error?) -> Void)? = nil) {
        addedNotificationRequests.append(request)
        // Simulate async behavior
        DispatchQueue.main.async {
            completionHandler?(self.addNotificationRequestError)
        }
    }

    // Override getNotificationSettings
    override func getNotificationSettings(completionHandler: @escaping (UNNotificationSettings) -> Void) {
        // Simulate async behavior
        DispatchQueue.main.async {
            if let settings = self.mockNotificationSettings {
                completionHandler(settings)
            } else if self.getNotificationSettingsError != nil {
                // This scenario is tricky, as the original method doesn't throw or pass an error.
                // For testing, we might just return some default 'denied' settings or log.
                // Or, the test could check if an error was *set* on the mock if it expected one.
                // For now, let's create some default settings if an error is set but no mockSettings.
                 XCTFail("getNotificationSettingsError was set on MockUNUserNotificationCenter, but this method does not propagate errors. Provide mockNotificationSettings.")
                // Fallback to a 'denied' like setting if not configured
                let deniedSettings = UNNotificationSettings(coder: MockNSCoder())! // A way to get a default instance
                completionHandler(deniedSettings)

            } else {
                 XCTFail("mockNotificationSettings not set for getNotificationSettings on MockUNUserNotificationCenter")
                // Fallback to a 'denied' like setting
                let deniedSettings = UNNotificationSettings(coder: MockNSCoder())!
                completionHandler(deniedSettings)
            }
        }
    }

    // Helper to reset state for tests
    func reset() {
        requestedAuthorizationOptions = nil
        shouldGrantAuthorization = true
        authorizationError = nil
        addedNotificationRequests = []
        addNotificationRequestError = nil
        mockNotificationSettings = nil
        getNotificationSettingsError = nil
    }
}

// Helper MockNSCoder to initialize UNNotificationSettings if needed for default/error cases.
// UNNotificationSettings's init?(coder:) is required but not meant for direct use to create fully custom settings.
// This is a bit of a hack to get a non-nil UNNotificationSettings object.
// In a real test, you'd typically provide a fully configured mockNotificationSettings.
private class MockNSCoder: NSCoder {
    override var allowsKeyedCoding: Bool { true }
    override func decodeObject(forKey key: String) -> Any? { nil }
    override func decodeInteger(forKey key: String) -> Int { 0 }
    override func decodeBool(forKey key: String) -> Bool { false }
    // Implement other decode methods as needed if UNNotificationSettings constructor uses them.
    // For basic settings, these might be enough to avoid a crash.
}
