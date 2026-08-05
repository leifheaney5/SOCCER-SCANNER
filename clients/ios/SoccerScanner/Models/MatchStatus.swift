import Foundation

/// Canonical match-status taxonomy.
///
/// This mirrors `static/js/match-status.js` exactly. Status semantics are a
/// cross-platform contract: if the native client and the web client disagree
/// about whether a fixture is live, they disagree about the same match.
public enum MatchStatus: String, CaseIterable, Sendable {
    case scheduled
    case delayed
    case inProgress
    case halfTime
    case extraTime
    case penalties
    case finished
    case postponed
    case cancelled
    case suspended
    case abandoned
    case unknown

    /// Provider vocabulary. Unmapped codes resolve to `.unknown` rather than
    /// failing the decode, so a new upstream status never blanks the schedule.
    public static func fromProviderCode(_ raw: String?) -> MatchStatus {
        guard let raw, !raw.trimmingCharacters(in: .whitespaces).isEmpty else { return .scheduled }
        let normalized = raw
            .trimmingCharacters(in: .whitespaces)
            .uppercased()
            .replacingOccurrences(of: " ", with: "_")
            .replacingOccurrences(of: "-", with: "_")

        switch normalized {
        case "SCHEDULED", "TIMED", "NOT_STARTED", "PRE", "UPCOMING": return .scheduled
        case "DELAYED": return .delayed
        case "LIVE", "IN_PLAY", "IN_PROGRESS", "FIRST_HALF", "SECOND_HALF": return .inProgress
        case "PAUSED", "HALFTIME", "HALF_TIME", "HT": return .halfTime
        case "EXTRA_TIME", "EXTRATIME", "ET": return .extraTime
        case "PENALTIES", "PENALTY_SHOOTOUT", "PEN": return .penalties
        case "FINISHED", "FULL_TIME", "AWARDED", "POST": return .finished
        case "POSTPONED": return .postponed
        case "CANCELLED", "CANCELED": return .cancelled
        case "SUSPENDED": return .suspended
        case "ABANDONED": return .abandoned
        default: return .unknown
        }
    }

    public var shortLabel: String {
        switch self {
        case .scheduled: return "SCHEDULED"
        case .delayed: return "DELAYED"
        case .inProgress: return "LIVE"
        case .halfTime: return "HT"
        case .extraTime: return "ET"
        case .penalties: return "PEN"
        case .finished: return "FT"
        case .postponed: return "POSTPONED"
        case .cancelled: return "CANCELLED"
        case .suspended: return "SUSPENDED"
        case .abandoned: return "ABANDONED"
        case .unknown: return "UNKNOWN"
        }
    }

    public var label: String {
        switch self {
        case .scheduled: return String(localized: "Scheduled")
        case .delayed: return String(localized: "Delayed")
        case .inProgress: return String(localized: "Live")
        case .halfTime: return String(localized: "Half time")
        case .extraTime: return String(localized: "Extra time")
        case .penalties: return String(localized: "Penalty shootout")
        case .finished: return String(localized: "Full time")
        case .postponed: return String(localized: "Postponed")
        case .cancelled: return String(localized: "Cancelled")
        case .suspended: return String(localized: "Suspended")
        case .abandoned: return String(localized: "Abandoned")
        case .unknown: return String(localized: "Status unavailable")
        }
    }

    /// Spoken by VoiceOver in place of the abbreviated badge.
    public var accessibilityDescription: String {
        switch self {
        case .scheduled: return String(localized: "Kick-off has not started yet.")
        case .delayed: return String(localized: "Kick-off is delayed and the start time may change.")
        case .inProgress: return String(localized: "The match is being played right now.")
        case .halfTime: return String(localized: "The match is paused at half time.")
        case .extraTime: return String(localized: "The match is in extra time.")
        case .penalties: return String(localized: "The match is being decided by a penalty shootout.")
        case .finished: return String(localized: "The match has finished.")
        case .postponed: return String(localized: "The match was postponed and will be rescheduled.")
        case .cancelled: return String(localized: "The match was cancelled and will not be played.")
        case .suspended: return String(localized: "The match is suspended and may resume.")
        case .abandoned: return String(localized: "The match was abandoned before completion.")
        case .unknown: return String(localized: "The provider did not report a usable status.")
        }
    }

    /// Play can still change the scoreline.
    public var isActive: Bool {
        switch self {
        case .inProgress, .halfTime, .extraTime, .penalties, .suspended: return true
        default: return false
        }
    }

    /// No further change expected; stop polling.
    public var isTerminal: Bool {
        switch self {
        case .finished, .postponed, .cancelled, .abandoned: return true
        default: return false
        }
    }

    public var shouldRefresh: Bool {
        if isTerminal { return false }
        return isActive || self == .delayed || self == .unknown
    }

    /// Whether a scoreline is meaningful at all. Governs spoiler handling.
    public var scoreAvailable: Bool {
        switch self {
        case .scheduled, .delayed, .postponed, .cancelled, .unknown: return false
        default: return true
        }
    }
}
