import XCTest
@testable import TrackRat

class DeepLinkTests: XCTestCase {

    // MARK: - Legacy Universal Link (trackrat.net/train/{id})

    func testLegacyUniversalLink_parsesTrainId() {
        let link = DeepLink(url: URL(string: "https://trackrat.net/train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
        XCTAssertNil(link?.fromStationCode)
        XCTAssertNil(link?.toStationCode)
    }

    func testLegacyUniversalLink_wwwHostAlsoParses() {
        let link = DeepLink(url: URL(string: "https://www.trackrat.net/train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
    }

    func testLegacyUniversalLink_parsesQueryParameters() {
        let link = DeepLink(url: URL(string: "https://trackrat.net/train/A174?date=2026-03-15&from=NY&to=PH")!)
        XCTAssertEqual(link?.trainId, "A174")
        XCTAssertEqual(link?.fromStationCode, "NY")
        XCTAssertEqual(link?.toStationCode, "PH")
        XCTAssertEqual(link?.date, easternDate(year: 2026, month: 3, day: 15))
    }

    func testLegacyUniversalLink_missingTrainIdReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "https://trackrat.net/train/")!))
    }

    func testLegacyUniversalLink_missingPathSegmentReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "https://trackrat.net/train")!))
    }

    func testUnrecognizedHostReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "https://evil.com/train/A174")!))
    }

    // MARK: - Share Universal Link (apiv2.trackrat.net/share/train/{id})

    func testShareUniversalLink_parsesTrainId() {
        let link = DeepLink(url: URL(string: "https://apiv2.trackrat.net/share/train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
    }

    func testShareUniversalLink_parsesQueryParameters() {
        let link = DeepLink(url: URL(string: "https://apiv2.trackrat.net/share/train/A174?date=2026-03-15&from=NY&to=PH")!)
        XCTAssertEqual(link?.trainId, "A174")
        XCTAssertEqual(link?.fromStationCode, "NY")
        XCTAssertEqual(link?.toStationCode, "PH")
    }

    func testShareUniversalLink_missingShareSegmentReturnsNil() {
        // Legacy-shaped path on the share host must not silently match.
        XCTAssertNil(DeepLink(url: URL(string: "https://apiv2.trackrat.net/train/A174")!))
    }

    func testShareUniversalLink_wrongMiddleSegmentReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "https://apiv2.trackrat.net/share/journey/A174")!))
    }

    func testShareUniversalLink_missingTrainIdReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "https://apiv2.trackrat.net/share/train/")!))
    }

    // MARK: - Custom URL Scheme (trackrat://...)

    func testCustomScheme_trainAsHost() {
        // trackrat://train/A174 - "train" is parsed as the URL host, id is the path.
        let link = DeepLink(url: URL(string: "trackrat://train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
    }

    func testCustomScheme_trainAsHost_parsesQueryParameters() {
        let link = DeepLink(url: URL(string: "trackrat://train/A174?from=NY&to=PH")!)
        XCTAssertEqual(link?.trainId, "A174")
        XCTAssertEqual(link?.fromStationCode, "NY")
        XCTAssertEqual(link?.toStationCode, "PH")
    }

    func testCustomScheme_trainInPathAfterHost() {
        // trackrat://someHost/train/A174 - "train" is a path segment, not the host.
        let link = DeepLink(url: URL(string: "trackrat://someHost/train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
    }

    func testCustomScheme_trainNestedDeeperInPath() {
        // trackrat://someHost/extra/train/A174 - "train" two segments into the path.
        let link = DeepLink(url: URL(string: "trackrat://someHost/extra/train/A174")!)
        XCTAssertEqual(link?.trainId, "A174")
    }

    func testCustomScheme_missingTrainIdReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "trackrat://train/")!))
    }

    func testCustomScheme_noTrainSegmentReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "trackrat://someHost/journey")!))
    }

    func testUnsupportedSchemeReturnsNil() {
        XCTAssertNil(DeepLink(url: URL(string: "tel://train/A174")!))
    }

    // MARK: - generateURL()

    func testGenerateURL_emitsShareUniversalLinkFormat() {
        let link = DeepLink(trainId: "A174")
        XCTAssertEqual(link.generateURL()?.absoluteString, "https://apiv2.trackrat.net/share/train/A174")
    }

    func testGenerateURL_roundTripsThroughParsing() throws {
        let date = easternDate(year: 2026, month: 3, day: 15)
        let original = DeepLink(trainId: "A174", date: date, fromStationCode: "NY", toStationCode: "PH")

        let url = try XCTUnwrap(original.generateURL())
        let reparsed = try XCTUnwrap(DeepLink(url: url))

        XCTAssertEqual(reparsed.trainId, "A174")
        XCTAssertEqual(reparsed.fromStationCode, "NY")
        XCTAssertEqual(reparsed.toStationCode, "PH")
        XCTAssertEqual(reparsed.date, date)
    }

    // MARK: - generateShareText()

    func testGenerateShareText_trainIdOnly() {
        let link = DeepLink(trainId: "7801")
        XCTAssertEqual(link.generateShareText(), "View 7801")
    }

    func testGenerateShareText_includesDataSourcePrefix() {
        let link = DeepLink(trainId: "7801")
        XCTAssertEqual(link.generateShareText(dataSource: "NJT"), "View NJT 7801")
    }

    func testGenerateShareText_explicitDestinationNameWinsOverStationCode() {
        let link = DeepLink(trainId: "7801", toStationCode: "NY")
        XCTAssertEqual(link.generateShareText(destinationName: "Somewhere Else"), "View 7801 to Somewhere Else")
    }

    func testGenerateShareText_fallsBackToStationCodeLookup() {
        let link = DeepLink(trainId: "7801", toStationCode: "NY")
        XCTAssertEqual(link.generateShareText(), "View 7801 to New York Penn")
    }

    func testGenerateShareText_unknownStationCodeOmitsDestination() {
        let link = DeepLink(trainId: "7801", toStationCode: "NOPE")
        XCTAssertEqual(link.generateShareText(), "View 7801")
    }

    // MARK: - ShareService (thin wrapper over DeepLink — same fixtures, no separate logic)

    func testShareServiceCreateShareURL_delegatesToDeepLink() throws {
        let train = MockDataFactory.createMockTrainV2(trainId: "7801")
        let url = try XCTUnwrap(ShareService.shared.createShareURL(
            for: train,
            fromStationCode: "NY",
            destinationName: nil
        ))

        let parsed = try XCTUnwrap(DeepLink(url: url))
        XCTAssertEqual(parsed.trainId, "7801")
        XCTAssertEqual(parsed.fromStationCode, "NY")
    }

    func testShareServiceCreateShareText_includesDataSourceAndDestination() {
        let train = MockDataFactory.createMockTrainV2(trainId: "7801") // dataSource fixed to "NJT"
        let text = ShareService.shared.createShareText(
            for: train,
            fromStationCode: "NY",
            destinationName: "Trenton"
        )
        XCTAssertEqual(text, "View NJT 7801 to Trenton")
    }

    // MARK: - Helpers

    private func easternDate(year: Int, month: Int, day: Int) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.date(from: String(format: "%04d-%02d-%02d", year, month, day))!
    }
}
