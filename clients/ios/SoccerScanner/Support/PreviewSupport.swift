import Foundation

/// Deterministic sample data for SwiftUI previews and UI tests.
///
/// Previews must never hit the network: a preview that depends on a live
/// service breaks in review, offline, and on CI.
public struct PreviewFixtureClient: FixtureFetching {
    public enum Behaviour: Sendable {
        case loaded
        case partial
        case empty
        case failure(APIError)
    }

    private let behaviour: Behaviour

    public init(behaviour: Behaviour = .loaded) {
        self.behaviour = behaviour
    }

    public func fixtures(date: String, timeZone: TimeZone) async throws -> FixtureDay {
        switch behaviour {
        case .failure(let error):
            throw error
        case .empty:
            return try Self.decode(Self.payload(date: date, timeZone: timeZone, matches: "[]"))
        case .partial:
            return try Self.decode(Self.payload(
                date: date,
                timeZone: timeZone,
                matches: Self.sampleMatches,
                state: "partial",
                providerStatus: "unavailable"
            ))
        case .loaded:
            return try Self.decode(Self.payload(
                date: date, timeZone: timeZone, matches: Self.sampleMatches
            ))
        }
    }

    public func appConfig() async throws -> AppConfig {
        let json = """
        {"apiVersion":"v2","environment":"preview","webVersion":"2.0.0",
         "features":{"accounts":false,"favorites":false,"streaming_links":true},
         "defaults":{"timezone":"UTC","scoresHiddenByDefault":true},
         "minimumSupportedClient":{"ios":"1.0.0","web":"2.0.0"}}
        """
        return try JSONDecoder().decode(AppConfig.self, from: Data(json.utf8))
    }

    private static func decode(_ json: String) throws -> FixtureDay {
        try JSONDecoder().decode(FixtureDay.self, from: Data(json.utf8))
    }

    private static func payload(
        date: String,
        timeZone: TimeZone,
        matches: String,
        state: String = "ok",
        providerStatus: String = "ok"
    ) -> String {
        """
        {"date":"\(date)","timezone":"\(timeZone.identifier)","state":"\(state)",
         "providers":[{"name":"espn","status":"\(providerStatus)"}],
         "freshness":{"ageSeconds":12},"matches":\(matches)}
        """
    }

    /// Covers a live state, a distinct half-time state, and a terminal state.
    static let sampleMatches = """
    [
      {"canonicalFixtureId":"fx_aaaaaaaaaaaaaaaaaaaaaaaa","utcDate":"2026-08-05T19:00:00Z",
       "status":{"code":"IN_PLAY"},"homeTeam":{"name":"Arsenal"},"awayTeam":{"name":"Chelsea"},
       "competition":{"name":"Premier League","area":{"name":"England"}},
       "score":{"fullTime":{"home":1,"away":0}},
       "broadcasts":[{"type":"STREAMING","name":"Peacock","region":"US"}],"venue":"Emirates"},
      {"canonicalFixtureId":"fx_bbbbbbbbbbbbbbbbbbbbbbbb","utcDate":"2026-08-05T20:00:00Z",
       "status":{"code":"HALF_TIME"},"homeTeam":{"name":"Real Madrid"},"awayTeam":{"name":"Barcelona"},
       "competition":{"name":"LaLiga","area":{"name":"Spain"}},
       "score":{"fullTime":{"home":2,"away":2}},
       "broadcasts":[{"type":"STREAMING","name":"ESPN+"}]},
      {"canonicalFixtureId":"fx_cccccccccccccccccccccccc","utcDate":"2026-08-05T14:00:00Z",
       "status":{"code":"ABANDONED"},"homeTeam":{"name":"Ajax"},"awayTeam":{"name":"PSV"},
       "competition":{"name":"Eredivisie","area":{"name":"Netherlands"}},
       "score":{"fullTime":{"home":0,"away":1}},"broadcasts":[]}
    ]
    """
}
