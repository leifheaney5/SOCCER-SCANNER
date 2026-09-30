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

    public var displayName: String? {
        guard let name, !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        return name
    }
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

    public var categoryLabel: String {
        isStreaming ? String(localized: "Streaming") : String(localized: "Broadcast")
    }

    /// Region is shown honestly: an absent region is labelled, never guessed.
    public var regionLabel: String {
        guard let region, !region.isEmpty else { return String(localized: "Region unknown") }
        return region
    }
}

public struct WatchOption: Decodable, Hashable, Sendable {
    public let id: String?
    public let displayName: String
    public let type: String?
    public let region: String?
    public let officialUrl: String?
    public let logoPath: String?

    public init(broadcast: Broadcast) {
        id = nil
        displayName = broadcast.name ?? String(localized: "Unknown service")
        type = broadcast.type
        region = broadcast.region
        officialUrl = nil
        logoPath = nil
    }

    public var categoryLabel: String {
        type?.uppercased() == "TV" ? String(localized: "TV") : String(localized: "Streaming")
    }

    public var regionLabel: String {
        guard let region, !region.isEmpty else { return String(localized: "Region unknown") }
        return region
    }

    public var officialLinkURL: URL? {
        let verifiedDomains: [String]
        switch id {
        case .some("espn"): verifiedDomains = ["espn.com"]
        case .some("usa-network"): verifiedDomains = ["usanetwork.com"]
        case .some("peacock"): verifiedDomains = ["peacocktv.com"]
        case .some("espn-plus"): verifiedDomains = ["plus.espn.com", "espn.com"]
        case .some("paramount-plus"): verifiedDomains = ["paramountplus.com"]
        case .some("apple-tv"): verifiedDomains = ["tv.apple.com"]
        case .some("amazon-prime-video"): verifiedDomains = ["primevideo.com", "amazon.com"]
        case .some("dazn"): verifiedDomains = ["dazn.com"]
        case .some("fubo"): verifiedDomains = ["fubo.tv"]
        case .some("max"): verifiedDomains = ["max.com"]
        default: return nil
        }
        guard let officialUrl, let url = URL(string: officialUrl),
              url.scheme?.lowercased() == "https", let host = url.host?.lowercased(),
              verifiedDomains.contains(where: { host == $0 || host.hasSuffix("." + $0) }),
              url.user == nil, url.password == nil else {
            return nil
        }
        return url
    }
}

public struct BroadcastRegionCoverage: Decodable, Hashable, Sendable {
    public let region: String
    public let status: String
}

public struct BroadcastCoverage: Decodable, Hashable, Sendable {
    public let status: String
    public let regions: [BroadcastRegionCoverage]
    public let sourceUpdatedAt: String?

    public func status(for region: String) -> String? {
        regions.first(where: { $0.region == region })?.status
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
    public let whereToWatch: [WatchOption]
    public let broadcastCoverage: BroadcastCoverage?
    public let venue: String?
    public let interestEstimate: Double?

    /// Stable identity, preferring the durable canonical ID over a provider ID.
    public var id: String { canonicalFixtureId ?? providerId ?? "\(homeTeam.name)-\(awayTeam.name)" }

    public var streamingServices: [Broadcast] { broadcasts.filter(\.isStreaming) }

    public var hasFullTimeScore: Bool {
        score?.fullTime?.home != nil && score?.fullTime?.away != nil
    }

    private enum CodingKeys: String, CodingKey {
        case canonicalFixtureId, id, utcDate, localDate, status
        case homeTeam, awayTeam, competition, score, broadcasts, whereToWatch, broadcastCoverage, venue, interestEstimate
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
        // `try?` flattens the optional from decodeIfPresent, so this binds a
        // non-optional StatusObject.
        if let object = try? container.decodeIfPresent(StatusObject.self, forKey: .status) {
            status = MatchStatus.fromProviderCode(object.code)
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
        let decodedWatchOptions = try container.decodeIfPresent(
            [WatchOption].self,
            forKey: .whereToWatch
        )
        if let decodedWatchOptions, !decodedWatchOptions.isEmpty {
            whereToWatch = decodedWatchOptions
        } else {
            whereToWatch = broadcasts.map { WatchOption(broadcast: $0) }
        }
        broadcastCoverage = try container.decodeIfPresent(BroadcastCoverage.self, forKey: .broadcastCoverage)
        venue = try container.decodeIfPresent(String.self, forKey: .venue)
        interestEstimate = try container.decodeIfPresent(Double.self, forKey: .interestEstimate)
    }
}

public struct ProviderReport: Decodable, Hashable, Sendable {
    public let name: String?
    public let status: String?

    public init(name: String?, status: String?) {
        self.name = name
        self.status = status
    }
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

    private struct ProviderOutcome: Decodable {
        let status: String?
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        date = try container.decodeIfPresent(String.self, forKey: .date) ?? ""
        timezone = try container.decodeIfPresent(String.self, forKey: .timezone) ?? "UTC"
        matches = try container.decodeIfPresent([Fixture].self, forKey: .matches) ?? []
        state = try container.decodeIfPresent(String.self, forKey: .state)
        let providerOutcomes = try container.decodeIfPresent(
            [String: ProviderOutcome].self,
            forKey: .providers
        ) ?? [:]
        providers = providerOutcomes
            .map { ProviderReport(name: $0.key, status: $0.value.status) }
            .sorted { ($0.name ?? "") < ($1.name ?? "") }
        freshness = try container.decodeIfPresent(Freshness.self, forKey: .freshness)
    }

    /// A day that loaded but is known to be incomplete must say so rather than
    /// presenting a short list as the full schedule.
    public var isPartial: Bool {
        state == "partial"
    }
    public var isStale: Bool { state == "stale" }
}

/// Kickoff instant parsing.
///
/// Fractional seconds are optional upstream, so both forms are attempted. This
/// is a distinct type rather than an `ISO8601DateFormatter` extension: adding a
/// `date(from:)` method there would shadow the built-in and recurse.
public enum FixtureDateParser {
    // ISO8601DateFormatter is documented as thread-safe for parsing, and these
    // are configured once and never mutated afterwards. `nonisolated(unsafe)`
    // states that explicitly rather than paying to rebuild a formatter per call.
    nonisolated(unsafe) private static let withFractionalSeconds: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    nonisolated(unsafe) private static let plain: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    public static func date(from string: String) -> Date? {
        withFractionalSeconds.date(from: string) ?? plain.date(from: string)
    }
}
