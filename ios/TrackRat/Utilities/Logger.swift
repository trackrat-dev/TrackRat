import Foundation
import os.log

/// Lightweight logging framework that only outputs in DEBUG builds
/// Usage: Log.debug("message"), Log.info("message"), Log.warning("message"), Log.error("message")
enum Log {
    enum Level: String {
        case debug = "DEBUG"
        case info = "INFO"
        case warning = "WARN"
        case error = "ERROR"
    }

    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.trackrat"
    private static let logger = os.Logger(subsystem: subsystem, category: "TrackRat")

    /// Debug level logging - only outputs in DEBUG builds
    static func debug(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        #if DEBUG
        log(message, level: .debug, file: file, function: function, line: line)
        #endif
    }

    /// Info level logging - only outputs in DEBUG builds
    static func info(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        #if DEBUG
        log(message, level: .info, file: file, function: function, line: line)
        #endif
    }

    /// Warning level logging - outputs in DEBUG builds
    static func warning(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        #if DEBUG
        log(message, level: .warning, file: file, function: function, line: line)
        #endif
    }

    /// Error level logging - always outputs (important for crash diagnostics)
    static func error(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        log(message, level: .error, file: file, function: function, line: line)
    }

    private static func log(_ message: String, level: Level, file: String, function: String, line: Int) {
        let filename = (file as NSString).lastPathComponent
        let logMessage = "[\(level.rawValue)] \(filename):\(line) - \(message)"

        switch level {
        case .debug:
            logger.debug("\(logMessage)")
        case .info:
            logger.info("\(logMessage)")
        case .warning:
            logger.warning("\(logMessage)")
        case .error:
            logger.error("\(logMessage)")
        }

        // Also print to console for Xcode debugging
        #if DEBUG
        print(logMessage)
        #endif
    }
}
