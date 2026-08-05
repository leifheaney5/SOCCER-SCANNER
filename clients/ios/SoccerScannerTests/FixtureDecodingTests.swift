import XCTest
@testable import SoccerScanner

final class FixtureDecodingTests: XCTestCase {
    private func decodeDay(_ json: String) throws -> FixtureDay {
        try JSONDecoder().decode(FixtureDay.self, from: Data(json.utf8))
    }

    func testDecodesTheProductionFixturePayload() throws {
        // Captured verbatim from GET /api/v2/fixtures.
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"ok",
         "providers":[{"name":"espn","status":"ok"}],"freshness":{"ageSeconds":12},
         "matches":[{"canonicalFixtureId":"fx_aaaaaaaaaaaaaaaaaaaaaaaa","id":"espn-1",
          "utcDate":"2026-08-05T19:00:00Z","localDate":"2026-08-05","status":{"code":"IN_PLAY"},
          "homeTeam":{"canonicalId":"arsenal","crest":null,"name":"Arsenal"},
          "awayTeam":{"canonicalId":"chelsea","crest":null,"name":"Chelsea"},
          "competition":{"area":{"name":"England"},"canonicalId":"premier-league","name":"Premier League"},
          "score":{"fullTime":{"away":0,"home":1}},
          "broadcasts":[{"name":"Peacock","region":"US","type":"STREAMING"}],
          "interestEstimate":0.8,"sourceUpdatedAt":"2026-08-05T19:30:00Z","venue":"Emirates"}]}
        """
        let day = try decodeDay(json)
        let fixture = try XCTUnwrap(day.matches.first)

        XCTAssertEqual(day.date, "2026-08-05")
        XCTAssertEqual(day.timezone, "UTC")
        XCTAssertEqual(fixture.id, "fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertEqual(fixture.status, .inProgress)
        XCTAssertEqual(fixture.homeTeam.name, "Arsenal")
        XCTAssertEqual(fixture.competition?.countryName, "England")
        XCTAssertEqual(fixture.score?.fullTime?.home, 1)
        XCTAssertEqual(fixture.streamingServices.first?.regionLabel, "US")
        XCTAssertFalse(day.isPartial)
    }

    func testPrefersTheDurableCanonicalIdentifier() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","matches":[
          {"canonicalFixtureId":"fx_bbbbbbbbbbbbbbbbbbbbbbbb","id":"espn-9",
           "homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """
        XCTAssertEqual(try decodeDay(json).matches.first?.id, "fx_bbbbbbbbbbbbbbbbbbbbbbbb")
    }

    func testMissingOptionalFieldsDoNotFailTheWholeResponse() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","matches":[
          {"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """
        let fixture = try XCTUnwrap(try decodeDay(json).matches.first)

        XCTAssertEqual(fixture.status, .scheduled)
        XCTAssertNil(fixture.utcDate)
        XCTAssertTrue(fixture.broadcasts.isEmpty)
    }

    func testAMalformedCrestUrlDoesNotFailTheFixture() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","matches":[
          {"homeTeam":{"name":"A","crest":""},"awayTeam":{"name":"B"}}]}
        """
        let fixture = try XCTUnwrap(try decodeDay(json).matches.first)
        XCTAssertEqual(fixture.homeTeam.name, "A")
    }

    func testKickoffInstantsParseWithAndWithoutFractionalSeconds() {
        XCTAssertNotNil(FixtureDateParser.date(from: "2026-08-05T19:00:00Z"))
        XCTAssertNotNil(FixtureDateParser.date(from: "2026-08-05T19:00:00.250Z"))
        XCTAssertNil(FixtureDateParser.date(from: "not-a-date"))
    }

    func testAFailingProviderMarksTheDayPartial() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"ok",
         "providers":[{"name":"espn","status":"unavailable"}],
         "matches":[{"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """
        XCTAssertTrue(try decodeDay(json).isPartial)
    }

    func testAppConfigReportsGuestModeAndUpgradeFloor() throws {
        let json = """
        {"apiVersion":"v2","environment":"production","webVersion":"2.0.0",
         "features":{"accounts":false,"favorites":false,"streaming_links":true},
         "defaults":{"timezone":"UTC","scoresHiddenByDefault":true},
         "minimumSupportedClient":{"ios":"1.2.0","web":"2.0.0"}}
        """
        let config = try JSONDecoder().decode(AppConfig.self, from: Data(json.utf8))

        XCTAssertFalse(config.accountsAvailable)
        XCTAssertFalse(config.favoritesAvailable)
        XCTAssertTrue(config.isEnabled("streaming_links"))
        XCTAssertTrue(config.scoresHiddenByDefault)
        XCTAssertTrue(config.requiresUpgrade(currentVersion: "1.0.0"))
        XCTAssertFalse(config.requiresUpgrade(currentVersion: "1.2.0"))
        // An unknown flag must fail closed.
        XCTAssertFalse(config.isEnabled("notifications"))
    }
}
