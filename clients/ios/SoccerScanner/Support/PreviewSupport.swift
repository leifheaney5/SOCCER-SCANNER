import Foundation

/// Deterministic sample data for SwiftUI previews and UI tests.
///
/// Previews must never hit the network: a preview that depends on a live
/// service breaks in review, offline, and on CI.
public struct PreviewFixtureClient: FixtureFetching {
    public enum Behaviour: Sendable {
        case loaded
        case accessibility
        case partial
        case stale
        case empty
        case teamFailure
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
        case .stale:
            return try Self.decode(Self.payload(
                date: date,
                timeZone: timeZone,
                matches: Self.sampleMatches,
                state: "stale"
            ))
        case .teamFailure:
            return try Self.decode(Self.payload(
                date: date, timeZone: timeZone, matches: Self.sampleMatches
            ))
        case .accessibility:
            return try Self.decode(Self.payload(
                date: date, timeZone: timeZone, matches: Self.accessibilityMatches
            ))
        case .loaded:
            return try Self.decode(Self.payload(
                date: date, timeZone: timeZone, matches: Self.sampleMatches
            ))
        }
    }

    public func fixture(id: String) async throws -> Fixture {
        let day = try await fixtures(date: "2026-08-05", timeZone: .gmt)
        guard let fixture = day.matches.first(where: { $0.id == id }) else {
            throw APIError.server(status: 404)
        }
        return fixture
    }

    public func teamAnalysis(canonicalId: String) async throws -> TeamAnalysis {
        if case .teamFailure = behaviour {
            throw APIError.providerUnavailable(message: "stub")
        }
        if case .failure(let error) = behaviour {
            throw error
        }
        guard let name = Self.teamNames[canonicalId] else {
            throw APIError.server(status: 404)
        }
        return TeamAnalysis(
            teamInfo: TeamAnalysisTeamInfo(
                name: name,
                canonicalId: canonicalId,
                providerId: "preview-\(canonicalId)"
            ),
            stats: TeamAnalysisStats(
                matchesPlayed: 12,
                wins: 8,
                draws: 2,
                losses: 2,
                goalsFor: 24,
                goalsAgainst: 11,
                goalDifference: 13
            )
        )
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
        state: String = "success",
        providerStatus: String = "success"
    ) -> String {
        """
        {"date":"\(date)","timezone":"\(timeZone.identifier)","state":"\(state)",
         "providers":{"espn":{"status":"\(providerStatus)"}},
         "freshness":{"ageSeconds":12},"matches":\(matches)}
        """
    }

    /// Covers a live state, a distinct half-time state, and a terminal state.
    private static let teamNames = [
        "arsenal": "Arsenal",
        "chelsea": "Chelsea",
        "real-madrid": "Real Madrid",
        "barcelona": "Barcelona",
        "ajax": "Ajax",
        "psv": "PSV",
        "saint-etienne": "Association Sportive de Saint-Étienne Métropole",
        "universidad-nacional": "Club Deportivo Universidad Nacional de la Patagonia",
    ]

    static let sampleMatches = """
    [
      {"canonicalFixtureId":"fx_aaaaaaaaaaaaaaaaaaaaaaaa","utcDate":"2026-08-05T19:00:00Z",
       "status":{"code":"IN_PLAY"},"homeTeam":{"canonicalId":"arsenal","name":"Arsenal"},"awayTeam":{"canonicalId":"chelsea","name":"Chelsea"},
       "competition":{"name":"Premier League","area":{"name":"England"}},
       "score":{"fullTime":{"home":1,"away":0}},
       "broadcasts":[{"type":"STREAMING","name":"Peacock","region":"US"}],"venue":"Emirates"},
      {"canonicalFixtureId":"fx_bbbbbbbbbbbbbbbbbbbbbbbb","utcDate":"2026-08-05T20:00:00Z",
       "status":{"code":"HALF_TIME"},"homeTeam":{"canonicalId":"real-madrid","name":"Real Madrid"},"awayTeam":{"canonicalId":"barcelona","name":"Barcelona"},
       "competition":{"name":"LaLiga","area":{"name":"Spain"}},
       "score":{"fullTime":{"home":2,"away":2}},
       "broadcasts":[{"type":"TV","name":"National Sports","region":"GB"}]},
      {"canonicalFixtureId":"fx_cccccccccccccccccccccccc","utcDate":"2026-08-05T14:00:00Z",
       "status":{"code":"ABANDONED"},"homeTeam":{"canonicalId":"ajax","name":"Ajax"},"awayTeam":{"canonicalId":"psv","name":"PSV"},
       "competition":{"name":"Eredivisie","area":{"name":"Netherlands"}},
       "score":{"fullTime":{"home":0,"away":1}},"broadcasts":[]}
    ]
    """

    /// Adds long, provider-shaped names only when UI tests explicitly request
    /// accessibility fixtures; the standard UI-test data remains compact.
    static let accessibilityMatches = """
    [
      {"canonicalFixtureId":"fx_0123456789abcdef01234567","utcDate":"2026-08-05T21:30:00Z",
       "status":{"code":"TIMED"},
       "homeTeam":{"canonicalId":"saint-etienne","name":"Association Sportive de Saint-Étienne Métropole"},
       "awayTeam":{"canonicalId":"universidad-nacional","name":"Club Deportivo Universidad Nacional de la Patagonia"},
       "competition":{"name":"International Championship for Regional Football Associations","area":{"name":"United Kingdom of Great Britain and Northern Ireland"}},
       "broadcasts":[],"venue":"Metropolitan Community Football Stadium"}
    ]
    """
}
