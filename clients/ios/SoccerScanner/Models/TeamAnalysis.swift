import Foundation

/// Provider-verified team identity and aggregate season statistics.
///
/// This type intentionally does not model recent or upcoming matches because
/// those payloads can contain scores outside the fixture spoiler preference.
public struct TeamAnalysis: Decodable, Hashable, Sendable {
    public let teamInfo: TeamAnalysisTeamInfo?
    public let stats: TeamAnalysisStats?

    public init(teamInfo: TeamAnalysisTeamInfo?, stats: TeamAnalysisStats?) {
        self.teamInfo = teamInfo
        self.stats = stats
    }

    private enum CodingKeys: String, CodingKey {
        case teamInfo = "team_info"
        case stats
    }
}

public struct TeamAnalysisTeamInfo: Decodable, Hashable, Sendable {
    public let name: String?
    public let canonicalId: String?
    public let providerId: String?

    public init(name: String?, canonicalId: String?, providerId: String?) {
        self.name = name
        self.canonicalId = canonicalId
        self.providerId = providerId
    }

    private enum CodingKeys: String, CodingKey {
        case name
        case canonicalId = "canonicalId"
        case providerId = "providerId"
    }
}

public struct TeamAnalysisStats: Decodable, Hashable, Sendable {
    public let matchesPlayed: Int?
    public let wins: Int?
    public let draws: Int?
    public let losses: Int?
    public let goalsFor: Int?
    public let goalsAgainst: Int?
    public let goalDifference: Int?

    public init(
        matchesPlayed: Int?,
        wins: Int?,
        draws: Int?,
        losses: Int?,
        goalsFor: Int?,
        goalsAgainst: Int?,
        goalDifference: Int?
    ) {
        self.matchesPlayed = matchesPlayed
        self.wins = wins
        self.draws = draws
        self.losses = losses
        self.goalsFor = goalsFor
        self.goalsAgainst = goalsAgainst
        self.goalDifference = goalDifference
    }

    private enum CodingKeys: String, CodingKey {
        case matchesPlayed = "matches_played"
        case wins
        case draws
        case losses
        case goalsFor = "goals_for"
        case goalsAgainst = "goals_against"
        case goalDifference = "goal_difference"
    }
}
