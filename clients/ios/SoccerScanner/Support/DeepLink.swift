import Foundation

/// Universal-link routing.
///
/// Incoming paths are validated against the same shapes the server accepts.
/// An unrecognised or hostile path resolves to `nil` so the system falls back
/// to the website instead of opening an arbitrary in-app screen.
public enum DeepLink: Hashable, Sendable {
    case fixture(id: String, timeZoneIdentifier: String?, calendarDay: String?)
    case team(canonicalId: String)
    case competition(canonicalId: String)
    case calendar

    /// Matches the server's `fx_` + 24 lowercase hex identifier format.
    private static let fixturePattern = try? NSRegularExpression(pattern: "^fx_[a-f0-9]{24}$")
    private static let slugPattern = try? NSRegularExpression(pattern: "^[a-z0-9][a-z0-9-]{0,79}$")

    private static func matches(_ regex: NSRegularExpression?, _ value: String) -> Bool {
        guard let regex else { return false }
        let range = NSRange(value.startIndex..<value.endIndex, in: value)
        return regex.firstMatch(in: value, range: range) != nil
    }

    public static func parse(_ url: URL, allowedHosts: Set<String> = ["soccerscanner.pro"]) -> DeepLink? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return nil
        }
        // Only https links from a host we own may open the app.
        guard components.scheme == "https",
              let host = components.host,
              allowedHosts.contains(host) else { return nil }

        let segments = components.path.split(separator: "/").map(String.init)
        let timeZone = components.queryItems?.first { $0.name == "timezone" }?.value
        let calendarDay = components.queryItems?.first { $0.name == "date" }?.value
        if let calendarDay, !FixtureTime.isValidCalendarDay(calendarDay) { return nil }

        switch segments.first {
        case "fixtures" where segments.count == 2:
            let identifier = segments[1]
            guard matches(fixturePattern, identifier) else { return nil }
            // Only propagate a zone the platform actually recognises.
            let validated = timeZone.flatMap { TimeZone(identifier: $0) }?.identifier
            return .fixture(
                id: identifier,
                timeZoneIdentifier: validated,
                calendarDay: calendarDay
            )
        case "teams" where segments.count == 2:
            guard matches(slugPattern, segments[1]) else { return nil }
            return .team(canonicalId: segments[1])
        case "competitions" where segments.count == 2:
            guard matches(slugPattern, segments[1]) else { return nil }
            return .competition(canonicalId: segments[1])
        case "calendar" where segments.count == 1:
            return .calendar
        default:
            return nil
        }
    }
}
