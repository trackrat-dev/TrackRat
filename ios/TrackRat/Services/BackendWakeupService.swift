import Foundation

// MARK: - Health Check Result
struct HealthCheckResult: Equatable {
    let success: Bool
    let statusCode: Int?
    let responseTime: TimeInterval
    let errorMessage: String?
    let responseBody: String?
}

// MARK: - Wakeup Cache Entry
private struct WakeupCacheEntry {
    let timestamp: Date
    let success: Bool
}

@MainActor
final class BackendWakeupService {
    static let shared = BackendWakeupService()
    private let storageService = StorageService()
    private var wakeupTask: Task<Void, Never>?
    
    // Cache for wake-up requests, keyed by environment
    private var wakeupCache: [String: WakeupCacheEntry] = [:]
    private let cacheExpirationInterval: TimeInterval = 900 // 15 minutes
    
    private init() {}
    
    func wakeupBackend() {
        // Cancel any existing wake-up task
        wakeupTask?.cancel()
        
        // Start new wake-up task
        wakeupTask = Task {
            let startTime = Date()
            let environment = storageService.loadServerEnvironment()
            let environmentKey = environment.rawValue
            
            // Check cache first
            if let cacheEntry = wakeupCache[environmentKey] {
                let cacheAge = Date().timeIntervalSince(cacheEntry.timestamp)
                
                if cacheEntry.success && cacheAge < cacheExpirationInterval {
                    print("💾 Backend Wake-up: Cache hit for \(environment.displayName)")
                    print("   - Cache age: \(String(format: "%.1f", cacheAge / 60)) minutes")
                    print("   - Skipping request (backend should still be warm)")
                    return
                } else if cacheAge >= cacheExpirationInterval {
                    print("💾 Backend Wake-up: Cache expired for \(environment.displayName)")
                    print("   - Cache age: \(String(format: "%.1f", cacheAge / 60)) minutes")
                    wakeupCache.removeValue(forKey: environmentKey)
                } else {
                    print("💾 Backend Wake-up: Cache miss for \(environment.displayName) (previous request failed)")
                }
            } else {
                print("💾 Backend Wake-up: No cache entry for \(environment.displayName)")
            }
            
            let healthURL = environment.baseURL.replacingOccurrences(of: "/api", with: "/health")
            
            print("🔄 Backend Wake-up: Starting request to \(environment.displayName) environment")
            print("🔄 Backend Wake-up: Health URL: \(healthURL)")
            
            guard let url = URL(string: healthURL) else {
                print("❌ Backend Wake-up: Invalid health URL: \(healthURL)")
                // Clear cache for invalid URL
                wakeupCache.removeValue(forKey: environmentKey)
                print("💾 Backend Wake-up: Cleared cache for \(environment.displayName) due to invalid URL")
                return
            }
            
            do {
                // Use URLSession with short timeout for wake-up request
                var request = URLRequest(url: url)
                request.timeoutInterval = 60.0 // 60 second timeout
                request.httpMethod = "GET"
                
                print("🔄 Backend Wake-up: Sending GET request with 60s timeout...")
                
                let (data, response) = try await URLSession.shared.data(for: request)
                
                let elapsedTime = Date().timeIntervalSince(startTime)
                
                if let httpResponse = response as? HTTPURLResponse {
                    let isSuccess = httpResponse.statusCode == 200
                    
                    print("✅ Backend Wake-up: Success!")
                    print("   - Status Code: \(httpResponse.statusCode)")
                    print("   - Response Time: \(String(format: "%.2f", elapsedTime))s")
                    print("   - Environment: \(environment.displayName)")
                    print("   - URL: \(healthURL)")
                    
                    if let responseString = String(data: data, encoding: .utf8) {
                        print("   - Response Body: \(responseString)")
                    }
                    
                    if isSuccess {
                        // Cache successful result
                        wakeupCache[environmentKey] = WakeupCacheEntry(timestamp: Date(), success: true)
                        print("💾 Backend Wake-up: Cached successful result for \(environment.displayName)")
                    } else {
                        print("⚠️  Backend Wake-up: Non-200 status code received")
                        // Remove cache entry for non-200 responses
                        wakeupCache.removeValue(forKey: environmentKey)
                        print("💾 Backend Wake-up: Cleared cache for \(environment.displayName) due to non-200 status")
                    }
                } else {
                    print("⚠️  Backend Wake-up: Received non-HTTP response")
                    // Remove cache entry for invalid responses
                    wakeupCache.removeValue(forKey: environmentKey)
                    print("💾 Backend Wake-up: Cleared cache for \(environment.displayName) due to invalid response")
                }
                
            } catch let error as URLError {
                let elapsedTime = Date().timeIntervalSince(startTime)
                print("❌ Backend Wake-up: URLError after \(String(format: "%.2f", elapsedTime))s")
                print("   - Error Code: \(error.code.rawValue)")
                print("   - Description: \(error.localizedDescription)")
                print("   - URL: \(healthURL)")
                
                // Clear cache on network errors
                wakeupCache.removeValue(forKey: environmentKey)
                print("💾 Backend Wake-up: Cleared cache for \(environment.displayName) due to network error")
                
                switch error.code {
                case .timedOut:
                    print("   - Timeout: Request exceeded 60 second limit")
                case .cannotConnectToHost:
                    print("   - Connection Failed: Cannot reach backend")
                case .notConnectedToInternet:
                    print("   - No Internet: Device appears offline")
                default:
                    print("   - Other URLError: \(error.code)")
                }
            } catch {
                let elapsedTime = Date().timeIntervalSince(startTime)
                print("❌ Backend Wake-up: General error after \(String(format: "%.2f", elapsedTime))s")
                print("   - Error Type: \(type(of: error))")
                print("   - Description: \(error.localizedDescription)")
                print("   - URL: \(healthURL)")
                
                // Clear cache on general errors
                wakeupCache.removeValue(forKey: environmentKey)
                print("💾 Backend Wake-up: Cleared cache for \(environment.displayName) due to general error")
            }
        }
    }
    
    func cancelWakeup() {
        if let task = wakeupTask, !task.isCancelled {
            task.cancel()
            print("🔄 Backend Wake-up: Cancelled pending wake-up request")
        }
    }
    
    // MARK: - Health Check
    func performHealthCheck(environment: ServerEnvironment? = nil) async -> HealthCheckResult {
        let startTime = Date()
        let env = environment ?? storageService.loadServerEnvironment()
        let healthURL = env.baseURL.replacingOccurrences(of: "/api", with: "/health")
        
        print("🏥 Health Check: Starting for \(env.displayName) environment")
        print("🏥 Health Check: URL: \(healthURL)")
        
        guard let url = URL(string: healthURL) else {
            return HealthCheckResult(
                success: false,
                statusCode: nil,
                responseTime: Date().timeIntervalSince(startTime),
                errorMessage: "Invalid health URL",
                responseBody: nil
            )
        }
        
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 30.0 // 30 second timeout for health check
            request.httpMethod = "GET"
            
            let (data, response) = try await URLSession.shared.data(for: request)
            let elapsedTime = Date().timeIntervalSince(startTime)
            
            if let httpResponse = response as? HTTPURLResponse {
                let responseBody = String(data: data, encoding: .utf8)
                let success = httpResponse.statusCode == 200
                
                print("🏥 Health Check: \(success ? "✅ Success" : "❌ Failed")")
                print("   - Status Code: \(httpResponse.statusCode)")
                print("   - Response Time: \(String(format: "%.2f", elapsedTime))s")
                
                return HealthCheckResult(
                    success: success,
                    statusCode: httpResponse.statusCode,
                    responseTime: elapsedTime,
                    errorMessage: success ? nil : "HTTP \(httpResponse.statusCode)",
                    responseBody: responseBody
                )
            } else {
                return HealthCheckResult(
                    success: false,
                    statusCode: nil,
                    responseTime: elapsedTime,
                    errorMessage: "Invalid response type",
                    responseBody: nil
                )
            }
        } catch let error as URLError {
            let elapsedTime = Date().timeIntervalSince(startTime)
            var errorMessage = error.localizedDescription
            
            switch error.code {
            case .timedOut:
                errorMessage = "Request timed out"
            case .cannotConnectToHost:
                errorMessage = "Cannot connect to server"
            case .notConnectedToInternet:
                errorMessage = "No internet connection"
            default:
                break
            }
            
            print("🏥 Health Check: ❌ Failed")
            print("   - Error: \(errorMessage)")
            print("   - Response Time: \(String(format: "%.2f", elapsedTime))s")
            
            return HealthCheckResult(
                success: false,
                statusCode: nil,
                responseTime: elapsedTime,
                errorMessage: errorMessage,
                responseBody: nil
            )
        } catch {
            let elapsedTime = Date().timeIntervalSince(startTime)
            print("🏥 Health Check: ❌ Failed")
            print("   - Error: \(error.localizedDescription)")
            
            return HealthCheckResult(
                success: false,
                statusCode: nil,
                responseTime: elapsedTime,
                errorMessage: error.localizedDescription,
                responseBody: nil
            )
        }
    }
}