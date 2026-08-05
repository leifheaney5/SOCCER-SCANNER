import XCTest
@testable import SoccerScanner

final class TimeZoneFormattingTests: XCTestCase {
    /// 00:30Z is still the 4th in the Americas and already the 5th in Asia.
    private let crossover = FixtureDateParser.date(from: "2026-08-05T00:30:00Z")!

    func testCalendarDayResolvesPerZoneAcrossUtcMidnight() {
        let expectations: [(String, String)] = [
            ("America/New_York", "2026-08-04"),
            ("America/Los_Angeles", "2026-08-04"),
            ("Europe/London", "2026-08-05"),
            ("Asia/Tokyo", "2026-08-05"),
            ("Australia/Sydney", "2026-08-05"),
            ("UTC", "2026-08-05"),
        ]
        for (identifier, expected) in expectations {
            let zone = TimeZone(identifier: identifier)!
            XCTAssertEqual(FixtureTime.calendarDate(for: crossover, in: zone), expected, identifier)
        }
    }

    func testZoneLabelReflectsDaylightSaving() {
        let newYork = TimeZone(identifier: "America/New_York")!
        let summer = FixtureDateParser.date(from: "2026-08-04T12:00:00Z")!
        let winter = FixtureDateParser.date(from: "2026-01-15T12:00:00Z")!

        XCTAssertEqual(FixtureTime.zoneLabel(newYork, at: summer), "EDT · UTC-04:00")
        XCTAssertEqual(FixtureTime.zoneLabel(newYork, at: winter), "EST · UTC-05:00")
    }

    func testShiftingDaysIsStableAcrossADstTransition() {
        // 8 March 2026 is the US spring-forward date; stepping days must not
        // skip or repeat one.
        XCTAssertEqual(FixtureTime.shiftDay("2026-03-07", by: 1), "2026-03-08")
        XCTAssertEqual(FixtureTime.shiftDay("2026-03-08", by: 1), "2026-03-09")
        XCTAssertEqual(FixtureTime.shiftDay("2026-03-08", by: -1), "2026-03-07")
    }

    func testDayHeadingDoesNotDriftBetweenZones() {
        let sydney = TimeZone(identifier: "Australia/Sydney")!
        let losAngeles = TimeZone(identifier: "America/Los_Angeles")!

        XCTAssertEqual(
            FixtureTime.dayHeading(for: "2026-08-04", in: sydney),
            FixtureTime.dayHeading(for: "2026-08-04", in: losAngeles)
        )
    }

    func testMissingKickoffRendersAPlaceholder() {
        XCTAssertEqual(FixtureTime.kickoff(nil, in: .init(identifier: "UTC")!), "Time TBC")
    }

    func testResolveFallsBackWhenTheIdentifierIsUnusable() {
        let fallback = TimeZone(identifier: "Europe/London")!
        XCTAssertEqual(FixtureTime.resolve("Asia/Tokyo", fallback: fallback).identifier, "Asia/Tokyo")
        XCTAssertEqual(FixtureTime.resolve("Mars/Olympus", fallback: fallback).identifier, "Europe/London")
        XCTAssertEqual(FixtureTime.resolve(nil, fallback: fallback).identifier, "Europe/London")
    }
}

final class DeepLinkTests: XCTestCase {
    func testParsesEveryRoutedUniversalLink() {
        let fixtureId = "fx_" + String(repeating: "a", count: 24)
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/fixtures/\(fixtureId)")!),
            .fixture(id: fixtureId, timeZoneIdentifier: nil)
        )
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/teams/arsenal")!),
            .team(canonicalId: "arsenal")
        )
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/competitions/premier-league")!),
            .competition(canonicalId: "premier-league")
        )
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/calendar")!),
            .calendar
        )
    }

    func testPreservesAValidTimezoneAndDropsAnInvalidOne() {
        let fixtureId = "fx_" + String(repeating: "b", count: 24)
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/fixtures/\(fixtureId)?timezone=Asia/Tokyo")!),
            .fixture(id: fixtureId, timeZoneIdentifier: "Asia/Tokyo")
        )
        XCTAssertEqual(
            DeepLink.parse(URL(string: "https://soccerscanner.pro/fixtures/\(fixtureId)?timezone=Mars/Olympus")!),
            .fixture(id: fixtureId, timeZoneIdentifier: nil)
        )
    }

    func testRejectsForeignHostsInsecureSchemesAndMalformedIdentifiers() {
        XCTAssertNil(DeepLink.parse(URL(string: "https://evil.example.com/fixtures/fx_" + String(repeating: "a", count: 24))!))
        XCTAssertNil(DeepLink.parse(URL(string: "http://soccerscanner.pro/calendar")!))
        XCTAssertNil(DeepLink.parse(URL(string: "https://soccerscanner.pro/fixtures/not-a-fixture")!))
        XCTAssertNil(DeepLink.parse(URL(string: "https://soccerscanner.pro/fixtures/fx_TOOSHORT")!))
        XCTAssertNil(DeepLink.parse(URL(string: "https://soccerscanner.pro/teams/../../etc/passwd")!))
        XCTAssertNil(DeepLink.parse(URL(string: "https://soccerscanner.pro/unknown/route")!))
    }
}

final class KeychainAbstractionTests: XCTestCase {
    func testSecureStoreRoundTripsAndRemoves() throws {
        let store = InMemorySecureStore()
        let secret = Data("refresh-token".utf8)

        try store.set(secret, for: "refresh")
        XCTAssertEqual(try store.data(for: "refresh"), secret)

        try store.remove("refresh")
        XCTAssertNil(try store.data(for: "refresh"))
    }

    func testReadingAnAbsentKeyIsNotAnError() throws {
        XCTAssertNil(try InMemorySecureStore().data(for: "missing"))
    }
}
