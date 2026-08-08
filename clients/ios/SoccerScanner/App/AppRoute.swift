import Foundation
import Observation

/// A validated in-app destination. Only fixture routes have a native screen;
/// other parsed web routes are intentionally retained as non-navigating values.
public enum AppRoute: Hashable, Sendable {
    case fixture(id: String, timeZoneIdentifier: String?, calendarDay: String?)
    case unsupported(DeepLink)

    public init(_ deepLink: DeepLink) {
        switch deepLink {
        case .fixture(let id, let timeZoneIdentifier, let calendarDay):
            self = .fixture(
                id: id,
                timeZoneIdentifier: timeZoneIdentifier,
                calendarDay: calendarDay
            )
        case .team, .competition, .calendar:
            self = .unsupported(deepLink)
        }
    }
}

/// Holds one validated route until the active screen has handled it.
@MainActor
@Observable
public final class AppRouter {
    public private(set) var route: AppRoute?

    public init() {}

    /// Invalid URLs leave an already-pending valid route intact.
    public func handle(_ url: URL) {
        guard let deepLink = DeepLink.parse(url) else { return }
        route = AppRoute(deepLink)
    }

    /// Only the route currently pending may clear itself, avoiding an older
    /// async resolution consuming a newer warm link.
    public func consume(_ route: AppRoute) {
        guard self.route == route else { return }
        self.route = nil
    }
}
