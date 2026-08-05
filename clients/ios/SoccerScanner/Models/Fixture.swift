import Foundation

public struct Team: Decodable, Hashable, Sendable {
    public let name: String
    public let canonicalId: String?
    public let crest: URL?

    public init(name: String, canonicalId: String? = nil, crest: URL? = nil) {
        self.name = name
        self.canonicalId = canonicalId
        self.crest = crest
    }

    private enum CodingKeys: String, CodingKey { case name, canonicalId, crest }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        name = try container.decodeIfPresent(String.self, forKey: .name) ?? "Unknown team"
        canonicalId = try container.decodeIfPresent(String.self, forKey: .canonicalId)
        // A malformed or absent crest URL must not fail the whole fixture.
        let rawCrest = try? container.decodeIfPresent(String.self, forKey: .crest)
        crest = (rawCrest ?? nil).flatMap(URL.init(string:))
    }
}

public struct Area: Decodable, Hashable, Sendable {
    public let name: String?
}

public struct Competition: Decodable, Hashable, Sendable {
    public let name: String?
    public let canonicalId: String?
    public let area: Area?

    public var displayName: String { name ?? "Competition" }
    public var countryName: String? { area?.name }
}

public struct ScoreLine: Decodable, Hashable, Sendable {
    public let home: Int?
    public let away: Int?
}

public struct Score: Decodable, Hashable, Sendable {
    public let fullTime: ScoreLine?
}

public struct Broadcast: Decodable, Hashable, Sendable {
    public let type: String?
    public let name: String?
    public let region: String?

    public var isStreaming: Bool { type?.uppercased() == "STREAMING" }

    /// Region is shown honestly: an absent region is labelled, never guessed.
    public var regionLabel: String {
        guard let region, !region.isEmpty else { return String(localized: "Region unknown") }
        return region
    }
}

public struct Fixture: Decodable, Identifiable, Hashable, Sendable {
    public let canonicalFixtureId: String?
    public let providerId: String?
    public let utcDate: Date?
    public let localDate: String?
    public let status: MatchStatus
    public let homeTeam: Team
    public let awayTeam: Team
    public let competition: Competition?
    public let score: Score?
    public let broadcasts: [Broadcast]
    public let venue: String?
    public let interestEstimate: Double?

    /// Stable identity, preferring the durable canonical ID over a provider ID.
    public var id: String { canonicalFixtureId ?? providerId ?? "\(homeTeam.name)-\(awayTeam.name)" }

    public var streamingServices: [Broadcast] { broadcasts.filter(\.isStreaming) }

    private enum CodingKeys: String, CodingKey {
        case canonicalFixtureId, id, utcDate, localDate, status
        case homeTeam, awayTeam, competition, score, broadcasts, venue, interestEstimate
    }

    private struct StatusObject: Decodable { let code: String? }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        canonicalFixtureId = try container.decodeIfPresent(String.self, forKey: .canonicalFixtureId)
        providerId = try container.decodeIfPresent(String.self, forKey: .id)

        // Kickoff instants are always UTC ISO-8601; the display zone is applied
        // at render time, never baked into the model.
        if let raw = try container.decodeIfPresent(String.self, forKey: .utcDate) {
            utcDate = FixtureDateParser.date(from: raw)
        } else {
            utcDate = nil
        }
        localDate = try container.decodeIfPresent(String.self, forKey: .localDate)

        // The API sends either {"code": "..."} or a bare string.
        if let object = try? container.decodeIfPresent(StatusObject.self, forKey: .status) {
            status = MatchStatus.fromProviderCode(object?.code)
        } else if let raw = try? container.decodeIfPresent(String.self, forKey: .status) {
            status = MatchStatus.fromProviderCode(raw)
        } else {
            status = .scheduled
        }

        homeTeam = try container.decodeIfPresent(Team.self, forKey: .homeTeam) ?? Team(name: "Home team")
        awayTeam = try container.decodeIfPresent(Team.self, forKey: .awayTeam) ?? Team(name: "Away team")
        competition = try container.decodeIfPresent(Competition.self, forKey: .competition)
        score = try container.decodeIfPresent(Score.self, forKey: .score)
        broadcasts = try container.decodeIfPresent([Broadcast].self, forKey: .broadcasts) ?? []
        venue = try container.decodeIfPresent(String.self, forKey: .venue)
        interestEstimate = try container.decodeIfPresent(Double.self, forKey: .interestEstimate)
    }
}

public struct ProviderReport: Decodable, Hashable, Sendable {
    public let name: String?
    public let status: String?
}

public struct Freshness: Decodable, Hashable, Sendable {
    public let ageSeconds: Double?
}

public struct FixtureDay: Decodable, Sendable {
    public let date: String
    public let timezone: String
    public let matches: [Fixture]
    public let state: String?
    public let providers: [ProviderReport]
    public let freshness: Freshness?

    private enum CodingKeys: String, CodingKey {
        case date, timezone, matches, state, providers, freshness
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        date = try container.decodeIfPresent(String.self, forKey: .date) ?? ""
        timezone = try container.decodeIfPresent(String.self, forKey: .timezone) ?? "UTC"
        matches = try container.decodeIfPresent([Fixture].self, forKey: .matches) ?? []
        state = try container.decodeIfPresent(String.self, forKey: .state)
        providers = try container.decodeIfPresent([ProviderReport].self, forKey: .providers) ?? []
        freshness = try container.decodeIfPresent(Freshness.self, forKey: .freshness)
    }

    /// A day that loaded but is known to be incomplete must say so rather than
    /// presenting a short list as the full schedule.
    public var isPartial: Bool { state == "partial" || providers.contains { $0.status != "ok" } }
    public var isStale: Bool { state == "stale" }
}

/// Kickoff instant parsing.
///
/// Fractional seconds are optional upstream, so both forms are attempted. This
/// is a distinct type rather than an `ISO8601DateFormatter` extension: adding a
/// `date(from:)` method there would shadow the built-in and recurse.
public enum FixtureDateParser {
    private static let withFractionalSeconds: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let plain: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    public static func date(from string: String) -> Date? {
        withFractionalSeconds.date(from: string) ?? plain.date(from: string)
    }
}
