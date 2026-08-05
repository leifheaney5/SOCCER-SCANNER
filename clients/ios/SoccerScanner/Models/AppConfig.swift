import Foundation

/// Server-owned client configuration from `/api/v2/app-config`.
///
/// Feature availability is decided by the server. The client must not offer an
/// affordance the backend cannot honour — notably sign-in, which does not exist
/// under the current guest-mode decision.
public struct AppConfig: Decodable, Sendable, Equatable {
    public struct Defaults: Decodable, Sendable, Equatable {
        public let timezone: String?
        public let scoresHiddenByDefault: Bool?
    }

    public struct MinimumSupportedClient: Decodable, Sendable, Equatable {
        public let ios: String?
        public let web: String?
    }

    public let apiVersion: String?
    public let environment: String?
    public let webVersion: String?
    public let features: [String: Bool]
    public let defaults: Defaults?
    public let minimumSupportedClient: MinimumSupportedClient?

    public func isEnabled(_ feature: String) -> Bool { features[feature] ?? false }

    public var accountsAvailable: Bool { isEnabled("accounts") }
    public var favoritesAvailable: Bool { isEnabled("favorites") }

    /// Scores start hidden unless the server explicitly says otherwise.
    public var scoresHiddenByDefault: Bool { defaults?.scoresHiddenByDefault ?? true }

    /// True when this build is older than the server's supported floor.
    public func requiresUpgrade(currentVersion: String = Bundle.appVersion) -> Bool {
        guard let minimum = minimumSupportedClient?.ios else { return false }
        return currentVersion.compare(minimum, options: .numeric) == .orderedAscending
    }

    private enum CodingKeys: String, CodingKey {
        case apiVersion, environment, webVersion, features, defaults, minimumSupportedClient
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        apiVersion = try container.decodeIfPresent(String.self, forKey: .apiVersion)
        environment = try container.decodeIfPresent(String.self, forKey: .environment)
        webVersion = try container.decodeIfPresent(String.self, forKey: .webVersion)
        features = try container.decodeIfPresent([String: Bool].self, forKey: .features) ?? [:]
        defaults = try container.decodeIfPresent(Defaults.self, forKey: .defaults)
        minimumSupportedClient = try container.decodeIfPresent(
            MinimumSupportedClient.self, forKey: .minimumSupportedClient
        )
    }
}
