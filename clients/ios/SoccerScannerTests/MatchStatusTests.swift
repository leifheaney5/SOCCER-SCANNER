import XCTest
@testable import SoccerScanner

final class MatchStatusTests: XCTestCase {
    func testProviderCodesNormaliseOntoTheCanonicalTaxonomy() {
        XCTAssertEqual(MatchStatus.fromProviderCode("IN_PLAY"), .inProgress)
        XCTAssertEqual(MatchStatus.fromProviderCode("LIVE"), .inProgress)
        XCTAssertEqual(MatchStatus.fromProviderCode("PAUSED"), .halfTime)
        XCTAssertEqual(MatchStatus.fromProviderCode("HALF_TIME"), .halfTime)
        XCTAssertEqual(MatchStatus.fromProviderCode("EXTRA_TIME"), .extraTime)
        XCTAssertEqual(MatchStatus.fromProviderCode("PENALTIES"), .penalties)
        XCTAssertEqual(MatchStatus.fromProviderCode("AWARDED"), .finished)
        XCTAssertEqual(MatchStatus.fromProviderCode("CANCELED"), .cancelled)
        XCTAssertEqual(MatchStatus.fromProviderCode("ABANDONED"), .abandoned)
        XCTAssertEqual(MatchStatus.fromProviderCode("DELAYED"), .delayed)
    }

    func testUnknownAndMissingCodesDegradeSafely() {
        XCTAssertEqual(MatchStatus.fromProviderCode("SOMETHING_NEW"), .unknown)
        XCTAssertEqual(MatchStatus.fromProviderCode(nil), .scheduled)
        XCTAssertEqual(MatchStatus.fromProviderCode(""), .scheduled)
        // Casing and separators vary between providers.
        XCTAssertEqual(MatchStatus.fromProviderCode("half time"), .halfTime)
        XCTAssertEqual(MatchStatus.fromProviderCode("extra-time"), .extraTime)
    }

    func testHalfTimeExtraTimeAndPenaltiesAreDistinctFromGenericLive() {
        XCTAssertEqual(MatchStatus.halfTime.shortLabel, "HT")
        XCTAssertEqual(MatchStatus.extraTime.shortLabel, "ET")
        XCTAssertEqual(MatchStatus.penalties.shortLabel, "PEN")
        XCTAssertEqual(MatchStatus.inProgress.shortLabel, "LIVE")
        XCTAssertEqual(MatchStatus.abandoned.shortLabel, "ABANDONED")
    }

    func testAbandonedIsTerminalAndStopsRefreshing() {
        XCTAssertTrue(MatchStatus.abandoned.isTerminal)
        XCTAssertFalse(MatchStatus.abandoned.isActive)
        XCTAssertFalse(MatchStatus.abandoned.shouldRefresh)
    }

    func testSuspendedStaysActiveBecausePlayCanResume() {
        XCTAssertTrue(MatchStatus.suspended.isActive)
        XCTAssertFalse(MatchStatus.suspended.isTerminal)
        XCTAssertTrue(MatchStatus.suspended.shouldRefresh)
    }

    func testEveryActiveStatusRefreshes() {
        for status in MatchStatus.allCases where status.isActive {
            XCTAssertTrue(status.shouldRefresh, "\(status) should refresh")
            XCTAssertFalse(status.isTerminal, "\(status) must not be terminal")
        }
    }

    func testScoreAvailabilityMatchesTheWebContract() {
        XCTAssertFalse(MatchStatus.scheduled.scoreAvailable)
        XCTAssertFalse(MatchStatus.postponed.scoreAvailable)
        XCTAssertFalse(MatchStatus.cancelled.scoreAvailable)
        XCTAssertTrue(MatchStatus.inProgress.scoreAvailable)
        XCTAssertTrue(MatchStatus.penalties.scoreAvailable)
        XCTAssertTrue(MatchStatus.abandoned.scoreAvailable)
    }

    func testEveryStatusHasAnAccessibilityDescription() {
        for status in MatchStatus.allCases {
            XCTAssertFalse(status.label.isEmpty, "\(status) label")
            XCTAssertFalse(status.accessibilityDescription.isEmpty, "\(status) description")
        }
    }
}
