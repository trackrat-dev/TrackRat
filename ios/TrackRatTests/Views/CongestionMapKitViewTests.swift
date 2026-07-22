import XCTest
import CoreLocation
import MapKit
import SwiftUI
import UIKit
@testable import TrackRat

/// Tests for `CongestionMapKitView` base routes and live-overlay reconciliation.
///
/// The route-status map only receives live congestion segments, so a
/// low-frequency route like the Amtrak Keystone showed gaps (e.g. Paoli→
/// Philadelphia 30th St) whenever no train completed a segment inside the
/// congestion window. `baseRoutePolylineCoordinates` builds the static
/// topology path that is drawn beneath the live segments to close those gaps.
@MainActor
final class CongestionMapKitViewTests: XCTestCase {

    // MARK: - Reported gap: Keystone Paoli → Philadelphia 30th St

    func testKeystonePaoliToPhiladelphiaUsesShapeData() {
        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH", "PAO"])

        XCTAssertEqual(runs.count, 1, "PH→PAO is one adjacent pair and must produce exactly one polyline, got \(runs.count)")
        guard let run = runs.first else { return }
        XCTAssertGreaterThan(
            run.count, 2,
            "PAO-PH has GTFS shape data in RouteShapes, so the polyline should follow the track (\(run.count) points), not a 2-point straight line"
        )
    }

    // MARK: - Full Keystone line has no gaps

    func testFullKeystoneRouteDrawsEveryAdjacentPair() {
        guard let keystone = RouteTopology.allRoutes.first(where: { $0.id == "amtrak-keystone" }) else {
            XCTFail("amtrak-keystone route missing from RouteTopology")
            return
        }

        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: keystone.stationCodes)

        XCTAssertEqual(
            runs.count, keystone.stationCodes.count - 1,
            "Every adjacent Keystone pair must produce a polyline (stations: \(keystone.stationCodes)), otherwise the base layer has gaps like the reported PAO→PH one"
        )
        for (index, run) in runs.enumerated() {
            XCTAssertGreaterThanOrEqual(
                run.count, 2,
                "Polyline \(index) (\(keystone.stationCodes[index])→\(keystone.stationCodes[index + 1])) needs at least 2 coordinates to draw, got \(run.count)"
            )
        }
    }

    // MARK: - Straight-line fallback

    func testStraightLineFallbackForPairWithoutShapeData() {
        // NY→HAR are not topology-adjacent, so no GTFS shape exists for the pair.
        // If this precondition ever breaks, RouteShapes gained a NY-HAR entry and
        // the pair below needs replacing with another shapeless one.
        XCTAssertNil(
            RouteShapes.coordinates(from: "NY", to: "HAR"),
            "Test precondition: NY-HAR must have no shape data so the fallback path is exercised"
        )

        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["NY", "HAR"])

        XCTAssertEqual(runs.count, 1, "A pair of known stations must still produce a polyline without shape data")
        guard let run = runs.first,
              let nyCoords = Stations.getCoordinates(for: "NY"),
              let harCoords = Stations.getCoordinates(for: "HAR") else {
            XCTFail("NY and HAR must both have station coordinates")
            return
        }
        XCTAssertEqual(run.count, 2, "Without shape data the fallback is a straight from→to line, got \(run.count) points")
        XCTAssertEqual(run[0].latitude, nyCoords.latitude, accuracy: 0.0001, "Straight line must start at the from-station")
        XCTAssertEqual(run[0].longitude, nyCoords.longitude, accuracy: 0.0001, "Straight line must start at the from-station")
        XCTAssertEqual(run[1].latitude, harCoords.latitude, accuracy: 0.0001, "Straight line must end at the to-station")
        XCTAssertEqual(run[1].longitude, harCoords.longitude, accuracy: 0.0001, "Straight line must end at the to-station")
    }

    // MARK: - Unknown codes and degenerate input

    func testUnknownStationCodesAreSkipped() {
        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH", "NOT_A_STATION", "PAO"])
        XCTAssertTrue(
            runs.isEmpty,
            "Both pairs touch an unknown station code, so no polylines should be produced, got \(runs.count)"
        )
    }

    func testEmptyAndSingleStationPathsProduceNoPolylines() {
        XCTAssertTrue(
            CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: []).isEmpty,
            "An empty path has no pairs to draw"
        )
        XCTAssertTrue(
            CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH"]).isEmpty,
            "A single station has no pairs to draw"
        )
    }

    // MARK: - Segment merge key (adjacent same-color coalescing)

    /// Build a `CongestionSegment` by decoding the API JSON shape (its only
    /// initializer), so tests exercise the same decode path the app uses.
    private func makeSegment(
        dataSource: String,
        fromStation: String = "A",
        toStation: String = "B",
        congestionFactor: Double,
        frequencyFactor: Double?,
        cancellationRate: Double = 0,
        sampleCount: Int = 5,
        averageDelayMinutes: Double = 0,
        realFromStation: String? = nil,
        realToStation: String? = nil
    ) throws -> CongestionSegment {
        var dict: [String: Any] = [
            "from_station": fromStation, "to_station": toStation,
            "from_station_name": fromStation, "to_station_name": toStation,
            "data_source": dataSource,
            "congestion_factor": congestionFactor,
            "congestion_level": "normal",
            "average_delay_minutes": averageDelayMinutes,
            "baseline_minutes": 1,
            "current_average_minutes": 1,
            "sample_count": sampleCount,
            "cancellation_count": 0,
            "cancellation_rate": cancellationRate,
        ]
        if let frequencyFactor { dict["frequency_factor"] = frequencyFactor }
        if let realFromStation { dict["real_from_station"] = realFromStation }
        if let realToStation { dict["real_to_station"] = realToStation }
        let data = try JSONSerialization.data(withJSONObject: dict)
        return try JSONDecoder().decode(CongestionSegment.self, from: data)
    }

    /// Decode the production API shape because `IndividualJourneySegment` intentionally
    /// has no test-only initializer.
    private func makeIndividualSegment(
        actualDeparture: Date,
        journeyID: String = "journey-1",
        fromStation: String = "NY",
        toStation: String = "SE",
        congestionFactor: Double = 1,
        isCancelled: Bool = false,
        delayMinutes: Double = 0
    ) throws -> IndividualJourneySegment {
        let dateFormatter = ISO8601DateFormatter()
        let scheduledDeparture = actualDeparture.addingTimeInterval(-60)
        let scheduledArrival = actualDeparture.addingTimeInterval(540)
        let actualArrival = actualDeparture.addingTimeInterval(600)
        let dict: [String: Any] = [
            "journey_id": journeyID,
            "train_id": "train-1",
            "from_station": fromStation,
            "to_station": toStation,
            "from_station_name": fromStation,
            "to_station_name": toStation,
            "data_source": "NJT",
            "scheduled_departure": dateFormatter.string(from: scheduledDeparture),
            "actual_departure": dateFormatter.string(from: actualDeparture),
            "scheduled_arrival": dateFormatter.string(from: scheduledArrival),
            "actual_arrival": dateFormatter.string(from: actualArrival),
            "scheduled_minutes": 10,
            "actual_minutes": 10 + delayMinutes,
            "delay_minutes": delayMinutes,
            "congestion_factor": congestionFactor,
            "congestion_level": "normal",
            "is_cancelled": isCancelled,
            "journey_date": "2026-07-22",
        ]
        let data = try JSONSerialization.data(withJSONObject: dict)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(IndividualJourneySegment.self, from: data)
    }

    private func makeSystemView(
        segments: [CongestionSegment],
        individualSegments: [IndividualJourneySegment] = [],
        highlightMode: SegmentHighlightMode = .delays,
        onSegmentTap: @escaping (CongestionSegment) -> Void = { _ in }
    ) -> SystemCongestionMapView {
        SystemCongestionMapView(
            region: .constant(MKCoordinateRegion()),
            segments: segments,
            individualSegments: individualSegments,
            stations: [],
            selectedSystems: [],
            highlightMode: highlightMode,
            onSegmentTap: onSegmentTap
        )
    }

    private func makeJourneyView(
        segments: [CongestionSegment],
        highlightMode: SegmentHighlightMode = .delays,
        baseRouteStationCodes: [String] = []
    ) -> CongestionMapKitView {
        CongestionMapKitView(
            region: .constant(MKCoordinateRegion()),
            segments: segments,
            stations: [],
            highlightMode: highlightMode,
            baseRouteStationCodes: baseRouteStationCodes,
            onSegmentTap: { _ in }
        )
    }

    func testMergeKeyUsesFrequencyTierInHealthMode() throws {
        // SUBWAY is a Health-mode (frequency-colored) source. Two segments with
        // the SAME frequency color but DIFFERENT delay tiers must share a key so
        // they coalesce; the old delay-based key left them as separate stubs.
        let a = try makeSegment(dataSource: "SUBWAY", congestionFactor: 1.0, frequencyFactor: 0.95)
        let b = try makeSegment(dataSource: "SUBWAY", congestionFactor: 2.0, frequencyFactor: 0.92)
        XCTAssertEqual(visualMergeKey(for: a), visualMergeKey(for: b))

        // DIFFERENT frequency colors must NOT merge even with identical delay
        // tiers; the old key merged them into one wrongly-colored run.
        let c = try makeSegment(dataSource: "SUBWAY", congestionFactor: 1.0, frequencyFactor: 0.55)
        XCTAssertNotEqual(visualMergeKey(for: a), visualMergeKey(for: c))
    }

    func testMergeKeyFallsBackToDelayWhenNoFrequency() throws {
        // A Health-mode segment lacking a frequency factor is colored by the
        // delay fallback, so its key must be the delay tier — different delay
        // colors must stay separate, not collapse into one "no-frequency" bucket.
        let normal = try makeSegment(dataSource: "SUBWAY", congestionFactor: 1.0, frequencyFactor: nil)
        let severe = try makeSegment(dataSource: "SUBWAY", congestionFactor: 2.0, frequencyFactor: nil)
        XCTAssertNotEqual(visualMergeKey(for: normal), visualMergeKey(for: severe))
    }

    func testMergeKeyUsesDelayTierInDelayMode() throws {
        // NJT is a delay-mode source: the frequency factor is ignored and the
        // delay tier drives merging.
        let a = try makeSegment(dataSource: "NJT", congestionFactor: 1.0, frequencyFactor: 0.5)
        let b = try makeSegment(dataSource: "NJT", congestionFactor: 1.05, frequencyFactor: 0.9)
        XCTAssertEqual(visualMergeKey(for: a), visualMergeKey(for: b), "both are normal delay")

        let c = try makeSegment(dataSource: "NJT", congestionFactor: 2.0, frequencyFactor: 0.5)
        XCTAssertNotEqual(visualMergeKey(for: a), visualMergeKey(for: c))
    }

    // MARK: - Production MapKit reconciliation

    func testSystemReconciliationRebuildsForFrequencyTierAndCancellationTierChanges() throws {
        let healthy = try makeSegment(
            dataSource: "SUBWAY", fromStation: "S142", toStation: "S139",
            congestionFactor: 1, frequencyFactor: 0.95)
        let reduced = try makeSegment(
            dataSource: "SUBWAY", fromStation: "S142", toStation: "S139",
            congestionFactor: 1, frequencyFactor: 0.55)
        let reducedWithCancellations = try makeSegment(
            dataSource: "SUBWAY", fromStation: "S142", toStation: "S139",
            congestionFactor: 1, frequencyFactor: 0.55, cancellationRate: 20)
        let mapView = MKMapView()
        let initialView = makeSystemView(segments: [healthy])
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator

        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        XCTAssertEqual(
            mapView.overlays.compactMap { $0 as? SystemCongestionPolyline }.count,
            1,
            "Initial System reconciliation must install exactly one live aggregate overlay"
        )
        guard let healthyOverlay = coordinator.aggregatedOverlays.first else {
            XCTFail("Initial healthy segment must install one live aggregate overlay")
            return
        }

        makeSystemView(segments: [reduced]).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        guard let reducedOverlay = coordinator.aggregatedOverlays.first else {
            XCTFail("Frequency-tier update must leave one replacement aggregate overlay installed")
            return
        }
        XCTAssertEqual(
            mapView.overlays.compactMap { $0 as? SystemCongestionPolyline }.count,
            1,
            "Tier replacement must remove the stale aggregate overlay from MKMapView"
        )
        XCTAssertFalse(healthyOverlay === reducedOverlay, "Crossing a frequency tier must replace the live overlay")
        let frequencyRenderer = coordinator.mapView(mapView, rendererFor: reducedOverlay) as? MKPolylineRenderer
        XCTAssertTrue(
            frequencyRenderer?.strokeColor?.isEqual(UIColor.systemOrange) == true,
            "A 0.55 Health-mode frequency factor must render in the reduced-service orange tier"
        )

        makeSystemView(segments: [reducedWithCancellations]).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        let cancellationOverlay = try XCTUnwrap(coordinator.aggregatedOverlays.first)
        XCTAssertFalse(
            reducedOverlay === cancellationOverlay,
            "A cancellation-only health change must replace the stale overlay"
        )
        let cancellationRenderer = coordinator.mapView(
            mapView,
            rendererFor: cancellationOverlay
        ) as? MKPolylineRenderer
        XCTAssertTrue(
            cancellationRenderer?.strokeColor?.isEqual(UIColor.systemRed) == true,
            "A 20% cancellation rate must shift 0.55 service health from orange to severe red"
        )
    }

    func testSystemReconciliationRetainsOverlayAndRefreshesPayloadAndCallback() throws {
        let represented = try makeSegment(
            dataSource: "SUBWAY", fromStation: "S142", toStation: "S139",
            congestionFactor: 1, frequencyFactor: 0.95,
            averageDelayMinutes: 1, realFromStation: "OLD", realToStation: "OLD_TO")
        let latest = try makeSegment(
            dataSource: "SUBWAY", fromStation: "S142", toStation: "S139",
            congestionFactor: 1.02, frequencyFactor: 0.92,
            sampleCount: 6, averageDelayMinutes: 8,
            realFromStation: "NEW", realToStation: "NEW_TO")
        let mapView = MKMapView()
        let initialView = makeSystemView(segments: [represented])
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let retainedOverlay = try XCTUnwrap(coordinator.aggregatedOverlays.first)

        var tappedNavigation = ""
        let updatedView = makeSystemView(segments: [latest]) {
            tappedNavigation = "\($0.navFromStation)-\($0.navToStation)"
        }
        updatedView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)

        XCTAssertTrue(coordinator.aggregatedOverlays.first === retainedOverlay, "Same tier and unchanged draw position must retain the installed MapKit overlay")
        XCTAssertEqual(mapView.overlays.compactMap { $0 as? SystemCongestionPolyline }.count, 1, "Payload refresh must not duplicate installed live overlays")
        XCTAssertEqual(retainedOverlay.segment?.averageDelayMinutes, 8, "Retained overlay tap payload must refresh to the latest metrics")
        XCTAssertEqual(retainedOverlay.segment?.navFromStation, "NEW", "Retained overlay must carry the latest navigation origin")
        if let tappedSegment = retainedOverlay.segment {
            coordinator.onSegmentTap(tappedSegment)
        }
        XCTAssertEqual(tappedNavigation, "NEW-NEW_TO", "The callback closure must refresh even when no overlay rebuild occurs")
    }

    func testAggregateOnlyRebuildPreservesBaseAggregateIndividualOrderAndIndividualObject() throws {
        let normal = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1, frequencyFactor: nil)
        let cancellationTier = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1, frequencyFactor: nil, cancellationRate: 20)
        let departure = Date().addingTimeInterval(-600)
        let individual = try makeIndividualSegment(
            actualDeparture: departure, delayMinutes: 1)
        let updatedIndividual = try makeIndividualSegment(
            actualDeparture: departure.addingTimeInterval(60),
            congestionFactor: 1.01,
            delayMinutes: 8
        )

        let mapView = MKMapView()
        let initialView = makeSystemView(
            segments: [normal],
            individualSegments: [individual]
        )
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        let baseCoordinates = [
            try XCTUnwrap(Stations.getCoordinates(for: "NY")),
            try XCTUnwrap(Stations.getCoordinates(for: "SE")),
        ]
        let baseOverlay = RouteTopologyPolyline(
            coordinates: baseCoordinates,
            count: baseCoordinates.count
        )
        mapView.insertOverlay(baseOverlay, at: 0)
        coordinator.routeTopologyOverlays = [baseOverlay]

        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let retainedIndividual = try XCTUnwrap(
            coordinator.individualOverlayMap[individual.id]
        )

        makeSystemView(
            segments: [cancellationTier],
            individualSegments: [updatedIndividual]
        ).reconcileLiveOverlays(on: mapView, coordinator: coordinator)

        XCTAssertTrue(
            coordinator.individualOverlayMap[individual.id] === retainedIndividual,
            "A one-train same-tier payload update must not rebuild the individual overlay"
        )
        XCTAssertEqual(
            retainedIndividual.individualSegment?.delayMinutes,
            8,
            "The retained individual overlay must carry the latest tap payload"
        )
        XCTAssertEqual(mapView.overlays.count, 3, "Reconciliation must leave one base, aggregate, and individual overlay")
        XCTAssertTrue(
            (mapView.overlays[0] as? RouteTopologyPolyline) === baseOverlay,
            "The static base route must remain the bottom overlay"
        )
        XCTAssertTrue(
            mapView.overlays[1] is SystemCongestionPolyline,
            "A rebuilt aggregate overlay must remain above the base and below individuals"
        )
        XCTAssertTrue(
            (mapView.overlays[2] as? IndividualJourneyPolyline) === retainedIndividual,
            "The retained individual train overlay must remain visually on top"
        )
    }

    func testEqualSampleBidirectionalResponseReorderKeepsStableWinnerAndOverlay() throws {
        let forward = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1, frequencyFactor: nil, sampleCount: 5)
        let reverse = try makeSegment(
            dataSource: "NJT", fromStation: "SE", toStation: "NY",
            congestionFactor: 1, frequencyFactor: nil, sampleCount: 5)
        XCTAssertEqual(
            selectedBidirectionalCongestionSegments(from: [reverse, forward]).first?.id,
            forward.id,
            "Equal-sample bidirectional winner must use the stable lexicographically smaller id"
        )

        let mapView = MKMapView()
        let initialView = makeSystemView(segments: [reverse, forward])
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let retainedOverlay = try XCTUnwrap(coordinator.aggregatedOverlays.first)

        makeSystemView(segments: [forward, reverse]).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        XCTAssertTrue(coordinator.aggregatedOverlays.first === retainedOverlay, "Response reordering must not replace the live overlay")
        XCTAssertEqual(retainedOverlay.segment?.id, forward.id, "Rendering must use the same stable winner as reconciliation state")

        let reverseWinner = try makeSegment(
            dataSource: "NJT", fromStation: "SE", toStation: "NY",
            congestionFactor: 1, frequencyFactor: nil, sampleCount: 6)
        makeSystemView(segments: [forward, reverseWinner]).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        XCTAssertFalse(coordinator.aggregatedOverlays.first === retainedOverlay, "Changing the selected bidirectional winner must rebuild the live collection")
        XCTAssertEqual(coordinator.aggregatedOverlays.first?.segment?.id, reverseWinner.id, "Rendered overlay and state fingerprint must select the same higher-sample winner")
    }

    func testSystemIndividualReconciliationRebuildsCancellationAndUsesCancelledStyling() throws {
        let departure = Date().addingTimeInterval(-600)
        let active = try makeIndividualSegment(actualDeparture: departure)
        let cancelled = try makeIndividualSegment(actualDeparture: departure, isCancelled: true)
        let mapView = MKMapView()
        let initialView = makeSystemView(segments: [], individualSegments: [active])
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let activeOverlay = try XCTUnwrap(coordinator.individualOverlayMap[active.id])

        makeSystemView(segments: [], individualSegments: [cancelled]).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        let cancelledOverlay = try XCTUnwrap(coordinator.individualOverlayMap[cancelled.id])
        XCTAssertFalse(activeOverlay === cancelledOverlay, "Cancellation behavior change must rebuild the entire individual collection")
        XCTAssertEqual(mapView.overlays.compactMap { $0 as? IndividualJourneyPolyline }.count, 1, "Cancellation rebuild must replace rather than duplicate the installed individual overlay")
        let renderer = coordinator.mapView(mapView, rendererFor: cancelledOverlay) as? MKPolylineRenderer
        XCTAssertTrue(renderer?.strokeColor?.isEqual(UIColor.systemRed) == true, "Cancelled trains must render red")
        XCTAssertEqual(renderer?.alpha ?? 0, 0.9, accuracy: 0.001, "Cancelled trains must preserve the fixed 0.9 alpha instead of recency fading")
    }

    func testJourneyReconciliationUsesSemanticOrderAndKeepsStaticBaseBelowLive() throws {
        let first = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1, frequencyFactor: nil, averageDelayMinutes: 1)
        let second = try makeSegment(
            dataSource: "NJT", fromStation: "SE", toStation: "NP",
            congestionFactor: 1.05, frequencyFactor: nil)
        let payloadUpdate = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1.02, frequencyFactor: nil, averageDelayMinutes: 9)
        let mapView = MKMapView()
        let initialView = makeJourneyView(
            segments: [first, second],
            baseRouteStationCodes: ["NY", "SE", "NP"]
        )
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        initialView.reconcileBaseRouteOverlays(on: mapView, coordinator: coordinator)
        let retainedLive = coordinator.polylines
        let retainedBase = coordinator.baseRoutePolylines

        let updatedView = makeJourneyView(
            segments: [payloadUpdate, second],
            baseRouteStationCodes: ["NY", "SE", "NP"]
        )
        updatedView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        updatedView.reconcileBaseRouteOverlays(on: mapView, coordinator: coordinator)

        XCTAssertTrue(zip(coordinator.polylines, retainedLive).allSatisfy { $0.0 === $0.1 }, "Same tiers and relative order must retain every Journey live overlay")
        XCTAssertTrue(zip(coordinator.baseRoutePolylines, retainedBase).allSatisfy { $0.0 === $0.1 }, "Unchanged static topology must retain its overlay objects")
        XCTAssertEqual(coordinator.polylines.first?.segment?.averageDelayMinutes, 9, "Retained Journey overlay must carry the latest payload")
        XCTAssertTrue(
            mapView.overlays.prefix(retainedBase.count).allSatisfy { $0 is RouteTopologyPolyline },
            "Every static base polyline must remain ordered below all live congestion overlays"
        )

        let severeFirst = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 2, frequencyFactor: nil)
        makeJourneyView(
            segments: [severeFirst, second],
            baseRouteStationCodes: ["NY", "SE", "NP"]
        ).reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let severeOverlay = try XCTUnwrap(
            coordinator.polylines.first { $0.segment?.id == severeFirst.id }
        )
        XCTAssertFalse(
            severeOverlay === retainedLive.first,
            "A visual-tier change with the same id and raw congestion level must rebuild Journey overlays"
        )
        let severeRenderer = coordinator.mapView(
            mapView,
            rendererFor: severeOverlay
        ) as? MKPolylineRenderer
        XCTAssertTrue(
            severeRenderer?.strokeColor?.isEqual(UIColor.systemRed) == true,
            "The rebuilt Journey overlay must use the latest severe color tier"
        )
        XCTAssertTrue(zip(coordinator.baseRoutePolylines, retainedBase).allSatisfy { $0.0 === $0.1 }, "Live rebuilds must not replace the independent static base layer")
    }

    func testJourneyHighlightChangeRepaintsWithoutReplacingOverlay() throws {
        let segment = try makeSegment(
            dataSource: "NJT", fromStation: "NY", toStation: "SE",
            congestionFactor: 1, frequencyFactor: nil)
        let mapView = MKMapView()
        let initialView = makeJourneyView(segments: [segment], highlightMode: .delays)
        let coordinator = initialView.makeCoordinator()
        mapView.delegate = coordinator
        initialView.reconcileLiveOverlays(on: mapView, coordinator: coordinator)
        let retainedOverlay = try XCTUnwrap(coordinator.polylines.first)

        makeJourneyView(segments: [segment], highlightMode: .off).reconcileLiveOverlays(
            on: mapView,
            coordinator: coordinator
        )
        XCTAssertTrue(coordinator.polylines.first === retainedOverlay, "Highlight switching must repaint rather than rebuild semantic overlays")
        let renderer = coordinator.mapView(mapView, rendererFor: retainedOverlay) as? MKPolylineRenderer
        XCTAssertTrue(renderer?.strokeColor?.isEqual(UIColor.clear) == true, "Off highlight mode must repaint the retained overlay clear")
    }

    // MARK: - Merged overlay grouping

    func testMergedOverlayGroupingFollowsFrequencyVisualTier() throws {
        guard let route = RouteTopology.allRoutes.first(where: { route in
            route.dataSource == "SUBWAY" && route.stationCodes.count >= 3 &&
            route.stationCodes.prefix(3).allSatisfy { Stations.getCoordinates(for: $0) != nil }
        }) else {
            XCTFail("A three-station SUBWAY route with coordinates is required to exercise production merge grouping")
            return
        }
        let codes = Array(route.stationCodes.prefix(3))
        let first = try makeSegment(
            dataSource: route.dataSource, fromStation: codes[0], toStation: codes[1],
            congestionFactor: 1, frequencyFactor: 0.95)
        let sameTier = try makeSegment(
            dataSource: route.dataSource, fromStation: codes[1], toStation: codes[2],
            congestionFactor: 2, frequencyFactor: 0.92)
        let differentTier = try makeSegment(
            dataSource: route.dataSource, fromStation: codes[1], toStation: codes[2],
            congestionFactor: 2, frequencyFactor: 0.55)

        let merged = buildMergedAggregatedOverlays(from: [first, sameTier], isDimmed: false)
        XCTAssertEqual(merged.count, 1, "Adjacent segments with the same rendered frequency tier should form one overlay")
        XCTAssertEqual(merged.first?.segments.map(\.id), [first.id, sameTier.id], "The merged overlay must retain both tap payloads in route order")

        let firstWithHigherDelay = try makeSegment(
            dataSource: route.dataSource, fromStation: codes[0], toStation: codes[1],
            congestionFactor: 2, frequencyFactor: 0.95)
        let secondWithLowerDelay = try makeSegment(
            dataSource: route.dataSource, fromStation: codes[1], toStation: codes[2],
            congestionFactor: 1, frequencyFactor: 0.92)
        XCTAssertEqual(
            systemCongestionOverlayState(for: [first, sameTier]),
            systemCongestionOverlayState(for: [firstWithHigherDelay, secondWithLowerDelay]),
            "Raw delay-factor reordering inside one merged health run must not rebuild an unchanged overlay"
        )

        let split = buildMergedAggregatedOverlays(from: [first, differentTier], isDimmed: false)
        XCTAssertEqual(split.count, 2, "Adjacent segments with different frequency colors must remain separate overlays")
        XCTAssertEqual(split.flatMap(\.segments).count, 2, "Splitting by visual tier must not lose either segment")
    }
}
