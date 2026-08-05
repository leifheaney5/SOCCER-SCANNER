import Foundation

/// Build/runtime environment selection.
///
/// Chosen from the `SOCCER_SCANNER_ENVIRONMENT` variable so development,
/// staging and production are switchable without separate code paths.
public struct AppEnvironment: Sendable, Equatable {
    public let name: String
    public let baseURL: URL

    public var userAgent: String { "SoccerScanner-iOS/\(Bundle.appVersion) (\(name))" }

    public static let production = AppEnvironment(
        name: "production",
        baseURL: URL(string: "https://soccerscanner.pro")!
    )

    public static let staging = AppEnvironment(
        name: "staging",
        baseURL: URL(string: "https://web-staging-staging-eec1.up.railway.app")!
    )

    public static let development = AppEnvironment(
        name: "development",
        baseURL: URL(string: "http://localhost:5000")!
    )

    public static func current(
        processInfo: ProcessInfo = .processInfo
    ) -> AppEnvironment {
        switch processInfo.environment["SOCCER_SCANNER_ENVIRONMENT"]?.lowercased() {
        case "development": return .development
        case "staging": return .staging
        default: return .production
        }
    }
}

public extension Bundle {
    static var appVersion: String {
        main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0.0"
    }

    static var buildNumber: String {
        main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
    }
}
