import CoreLocation
import Foundation

/// A coordinate snapshot. A value type so SwiftUI can observe it with `onChange`,
/// which `CLLocationCoordinate2D` can't support (it isn't `Equatable`).
struct LocationFix: Equatable {
    let latitude: CLLocationDegrees
    let longitude: CLLocationDegrees

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
}

/// One-shot location lookup used to bootstrap setup: pick the rider's transit
/// system and surface nearby stations instead of making them search thousands.
///
/// The fix never leaves the device — it is only used locally to rank stations,
/// and only for the lifetime of the app run. Permission is requested when the
/// user explicitly asks for it, never on launch.
@MainActor
final class LocationService: NSObject, ObservableObject {
    static let shared = LocationService()

    @Published private(set) var fix: LocationFix?
    @Published private(set) var isLocating = false
    @Published private(set) var authorizationStatus: CLAuthorizationStatus = .notDetermined

    private let manager = CLLocationManager()

    private override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
        authorizationStatus = manager.authorizationStatus
    }

    /// Whether asking for a fix can still produce one (the user hasn't refused).
    var canRequestFix: Bool {
        switch authorizationStatus {
        case .notDetermined, .authorizedWhenInUse, .authorizedAlways:
            return true
        case .denied, .restricted:
            return false
        @unknown default:
            return false
        }
    }

    /// Request a single location fix, prompting for permission the first time.
    func requestFix() {
        guard canRequestFix, !isLocating else { return }
        isLocating = true

        if authorizationStatus == .notDetermined {
            // The fix is requested once the authorization callback lands.
            manager.requestWhenInUseAuthorization()
        } else {
            manager.requestLocation()
        }
    }

    private func handle(status: CLAuthorizationStatus) {
        authorizationStatus = status
        guard isLocating else { return }

        switch status {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.requestLocation()
        case .denied, .restricted:
            isLocating = false
        case .notDetermined:
            break  // Prompt is still on screen.
        @unknown default:
            isLocating = false
        }
    }

    private func handle(fix newFix: LocationFix?) {
        isLocating = false
        if let newFix {
            fix = newFix
        }
    }
}

// MARK: - CLLocationManagerDelegate

// Callbacks are delivered outside the main actor, so each one extracts the
// values it needs and hops back before touching published state.
extension LocationService: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in self.handle(status: status) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let newFix = locations.last.map {
            LocationFix(latitude: $0.coordinate.latitude, longitude: $0.coordinate.longitude)
        }
        Task { @MainActor in self.handle(fix: newFix) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Log.warning("Location request failed: \(error.localizedDescription)")
        Task { @MainActor in self.handle(fix: nil) }
    }
}

// MARK: - Nearby Stations

extension Stations {
    /// Codes of the stations closest to `coordinate`, nearest first.
    ///
    /// Equivalent stations (one complex under several codes) are collapsed so a
    /// list of five isn't five entrances to the same station. Pass `systems` to
    /// restrict the result to the systems the user has selected.
    static func nearestCodes(
        to coordinate: CLLocationCoordinate2D,
        systems: Set<TrainSystem>? = nil,
        limit: Int = 5,
        within maxDistance: CLLocationDistance = 40_000
    ) -> [String] {
        let candidates = sortedByDistance(to: coordinate, within: maxDistance) { code in
            guard isStationAvailable(code) else { return false }
            guard let systems, !systems.isEmpty else { return true }
            return isStationVisible(code, withSystems: systems)
        }

        var nearest: [String] = []
        for candidate in candidates {
            guard nearest.count < limit else { break }
            guard !nearest.contains(where: { areEquivalentStations($0, candidate.code) }) else { continue }
            nearest.append(candidate.code)
        }
        return nearest
    }

    /// The user-facing system whose closest station is nearest to `coordinate`,
    /// or nil when the rider isn't inside a metro area TrackRat covers.
    static func nearestSystem(
        to coordinate: CLLocationCoordinate2D,
        within maxDistance: CLLocationDistance = 80_000
    ) -> TrainSystem? {
        // Candidates are already sorted, so the first distance seen for a system
        // is that system's closest station.
        var closestBySystem: [TrainSystem: CLLocationDistance] = [:]
        for candidate in sortedByDistance(to: coordinate, within: maxDistance, where: isStationAvailable) {
            for system in systemsForStation(candidate.code) where !system.isDisabled {
                if closestBySystem[system] == nil {
                    closestBySystem[system] = candidate.distance
                }
            }
        }

        return closestBySystem.min {
            $0.value == $1.value ? $0.key.rawValue < $1.key.rawValue : $0.value < $1.value
        }?.key
    }

    private static func sortedByDistance(
        to coordinate: CLLocationCoordinate2D,
        within maxDistance: CLLocationDistance,
        where isEligible: (String) -> Bool
    ) -> [(code: String, distance: CLLocationDistance)] {
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)

        var scored: [(code: String, distance: CLLocationDistance)] = []
        for (code, stationCoordinate) in stationCoordinates where isEligible(code) {
            let distance = origin.distance(
                from: CLLocation(
                    latitude: stationCoordinate.latitude,
                    longitude: stationCoordinate.longitude
                )
            )
            if distance <= maxDistance {
                scored.append((code: code, distance: distance))
            }
        }
        return scored.sorted { $0.distance < $1.distance }
    }
}
