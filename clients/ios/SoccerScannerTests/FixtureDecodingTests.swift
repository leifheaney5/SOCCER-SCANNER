import Foundation
import XCTest
@testable import SoccerScanner

private final class FixtureURLProtocol: URLProtocol {
    nonisolated(unsafe) static var capturedRequest: URLRequest?
    nonisolated(unsafe) static var response: (HTTPURLResponse, Data)?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.capturedRequest = request
        guard let (response, data) = Self.response else {
            fatalError("FixtureURLProtocol response was not configured")
        }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

final class FixtureDecodingTests: XCTestCase {
    private func decodeDay(_ json: String) throws -> FixtureDay {
        try JSONDecoder().decode(FixtureDay.self, from: Data(json.utf8))
    }

    func testDecodesTheProductionFixturePayload() throws {
        // Captured verbatim from GET /api/v2/fixtures.
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"success",
         "providers":{"espn":{"status":"success"}},"freshness":{"ageSeconds":12},
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

    func testBroadcastEntriesPreserveTypeAndHonestRegionLabels() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","matches":[
          {"homeTeam":{"name":"A"},"awayTeam":{"name":"B"},"broadcasts":[
            {"type":"TV","name":"National Sports","region":"GB"},
            {"type":"STREAMING","name":"Peacock"}
          ]}]}
        """
        let fixture = try XCTUnwrap(try decodeDay(json).matches.first)

        XCTAssertEqual(fixture.broadcasts.map(\.categoryLabel), ["Broadcast", "Streaming"])
        XCTAssertEqual(fixture.broadcasts.map(\.regionLabel), ["GB", "Region unknown"])
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

    func testAnActualPartialResponseMarksTheDayPartial() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"partial",
         "providers":{"espn":{"status":"unavailable"}},
         "matches":[{"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """
        XCTAssertTrue(try decodeDay(json).isPartial)
    }

    func testSuccessWithADisabledOptionalProviderIsNotPartial() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"success",
         "providers":{"espn":{"status":"success"},
                      "football-data":{"status":"disabled"}},
         "matches":[{"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """

        let day = try decodeDay(json)

        XCTAssertFalse(day.isPartial)
        XCTAssertFalse(day.isStale)
        XCTAssertEqual(day.providers.map(\.status), ["success", "disabled"])
    }

    func testStaleWithADisabledOptionalProviderRemainsStale() throws {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"stale",
         "providers":{"espn":{"status":"success"},
                      "football-data":{"status":"disabled"}},
         "matches":[{"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """

        let day = try decodeDay(json)

        XCTAssertFalse(day.isPartial)
        XCTAssertTrue(day.isStale)
        XCTAssertEqual(day.providers.map(\.status), ["success", "disabled"])
    }

    func testDecodesKeyedProviderOutcomesInNameOrder() throws {
        // Captured from the canonical API, which emits provider reports as an
        // object keyed by provider name rather than a UI-shaped array.
        let json = """
        {"date":"2026-08-05","timezone":"UTC","state":"partial",
         "providers":{"football-data":{"status":"rate_limited"},
                      "espn":{"status":"success"}},
         "matches":[{"homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]}
        """

        let day = try decodeDay(json)

        XCTAssertEqual(day.providers.map(\.name), ["espn", "football-data"])
        XCTAssertEqual(day.providers.map(\.status), ["success", "rate_limited"])
        XCTAssertTrue(day.isPartial)
    }

    func testFixtureLookupRequestsCanonicalPathAndDecodesEnvelope() async throws {
        let identifier = "fx_aaaaaaaaaaaaaaaaaaaaaaaa"
        let responseURL = URL(string: "https://fixtures.example/api/v2/fixtures/\(identifier)")!
        let json = """
        {"fixture":{"canonicalFixtureId":"\(identifier)","homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}}
        """
        FixtureURLProtocol.capturedRequest = nil
        FixtureURLProtocol.response = (
            HTTPURLResponse(
                url: responseURL,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!,
            Data(json.utf8)
        )
        defer { FixtureURLProtocol.response = nil }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [FixtureURLProtocol.self]
        let client = APIClient(
            environment: AppEnvironment(name: "test", baseURL: URL(string: "https://fixtures.example")!),
            session: URLSession(configuration: configuration)
        )

        let fixture = try await client.fixture(id: identifier)

        XCTAssertEqual(fixture.id, identifier)
        XCTAssertEqual(FixtureURLProtocol.capturedRequest?.url?.path, "/api/v2/fixtures/\(identifier)")
        XCTAssertEqual(FixtureURLProtocol.capturedRequest?.httpMethod, "GET")
    }

    func testTeamAnalysisDecodesOnlyVerifiedIdentityAndAggregateStatistics() throws {
        // A canonical team response can include score-bearing match arrays.
        // Native team intelligence must deliberately omit them from its model.
        let json = """
        {"team_info":{"name":"Arsenal","canonicalId":"arsenal","providerId":"57"},
         "stats":{"matches_played":12,"wins":8,"draws":2,"losses":2,
                  "goals_for":24,"goals_against":11,"goal_difference":13},
         "recent_matches":[{"homeTeam":{"name":"Arsenal"},"awayTeam":{"name":"Chelsea"},
                            "score":{"fullTime":{"home":3,"away":1}}}],
         "upcoming_matches":[{"homeTeam":{"name":"Arsenal"},"awayTeam":{"name":"Liverpool"}}]}
        """

        let analysis = try JSONDecoder().decode(TeamAnalysis.self, from: Data(json.utf8))

        XCTAssertEqual(analysis.teamInfo?.canonicalId, "arsenal")
        XCTAssertEqual(analysis.teamInfo?.providerId, "57")
        XCTAssertEqual(analysis.teamInfo?.name, "Arsenal")
        XCTAssertEqual(analysis.stats?.matchesPlayed, 12)
        XCTAssertEqual(analysis.stats?.wins, 8)
        XCTAssertEqual(analysis.stats?.draws, 2)
        XCTAssertEqual(analysis.stats?.losses, 2)
        XCTAssertEqual(analysis.stats?.goalsFor, 24)
        XCTAssertEqual(analysis.stats?.goalsAgainst, 11)
        XCTAssertEqual(analysis.stats?.goalDifference, 13)
        XCTAssertFalse(
            Mirror(reflecting: analysis).children.compactMap(\.label).contains("recentMatches"),
            "TeamAnalysis must not expose score-bearing match lists"
        )
    }

    func testTeamAnalysisRequestsCanonicalPath() async throws {
        let canonicalId = "arsenal"
        let responseURL = URL(string: "https://fixtures.example/api/v2/teams/\(canonicalId)/analysis")!
        let json = """
        {"team_info":{"name":"Arsenal","canonicalId":"arsenal","providerId":"57"},
         "stats":{"matches_played":12,"wins":8}}
        """
        FixtureURLProtocol.capturedRequest = nil
        FixtureURLProtocol.response = (
            HTTPURLResponse(
                url: responseURL,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!,
            Data(json.utf8)
        )
        defer { FixtureURLProtocol.response = nil }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [FixtureURLProtocol.self]
        let client = APIClient(
            environment: AppEnvironment(name: "test", baseURL: URL(string: "https://fixtures.example")!),
            session: URLSession(configuration: configuration)
        )

        let analysis = try await client.teamAnalysis(canonicalId: canonicalId)

        XCTAssertEqual(analysis.teamInfo?.name, "Arsenal")
        XCTAssertEqual(FixtureURLProtocol.capturedRequest?.url?.path, "/api/v2/teams/arsenal/analysis")
        XCTAssertEqual(FixtureURLProtocol.capturedRequest?.httpMethod, "GET")
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
