import Foundation

/// Typed failure modes. The UI branches on these rather than on raw status
/// codes, so every error path has a designed presentation.
public enum APIError: Error, Equatable, Sendable {
    case offline
    case rateLimited(retryAfterSeconds: Int?)
    case invalidRequest(message: String)
    case providerUnavailable(message: String)
    case decoding(message: String)
    case server(status: Int)
    case cancelled

    public var isRetryable: Bool {
        switch self {
        case .offline, .rateLimited, .providerUnavailable, .server: return true
        case .invalidRequest, .decoding, .cancelled: return false
        }
    }

    public var userMessage: String {
        switch self {
        case .offline:
            return String(localized: "You appear to be offline.")
        case .rateLimited:
            return String(localized: "Too many requests. Please retry shortly.")
        case .invalidRequest(let message):
            return message
        case .providerUnavailable:
            return String(localized: "Fixture data is temporarily unavailable.")
        case .decoding:
            return String(localized: "The response could not be read.")
        case .server:
            return String(localized: "Something went wrong. Please try again.")
        case .cancelled:
            return String(localized: "Request cancelled.")
        }
    }
}

/// Server error envelope: `{"error": {"code", "message", "retryAfterSeconds"}}`.
private struct ErrorEnvelope: Decodable {
    struct Body: Decodable {
        let code: String?
        let message: String?
        let retryAfterSeconds: Int?
    }
    let error: Body
}

private struct FixtureEnvelope: Decodable {
    let fixture: Fixture
}

public protocol FixtureFetching: Sendable {
    func fixtures(date: String, timeZone: TimeZone) async throws -> FixtureDay
    func fixture(id: String) async throws -> Fixture
    func teamAnalysis(canonicalId: String) async throws -> TeamAnalysis
    func appConfig() async throws -> AppConfig
}

public actor APIClient: FixtureFetching {
    private let environment: AppEnvironment
    private let session: URLSession

    public init(environment: AppEnvironment, session: URLSession = .shared) {
        self.environment = environment
        self.session = session
    }

    public func fixtures(date: String, timeZone: TimeZone) async throws -> FixtureDay {
        // The timezone is always explicit. Relying on the server's default
        // would silently reintroduce the wrong-calendar-day class of bug.
        var components = URLComponents(
            url: environment.baseURL.appendingPathComponent("api/v2/fixtures"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [
            URLQueryItem(name: "date", value: date),
            URLQueryItem(name: "timezone", value: timeZone.identifier),
        ]
        guard let url = components?.url else {
            throw APIError.invalidRequest(message: "Could not build the fixtures URL.")
        }
        return try await get(url, as: FixtureDay.self)
    }

    public func fixture(id: String) async throws -> Fixture {
        let envelope = try await get(
            environment.baseURL
                .appendingPathComponent("api/v2/fixtures")
                .appendingPathComponent(id),
            as: FixtureEnvelope.self
        )
        return envelope.fixture
    }

    public func teamAnalysis(canonicalId: String) async throws -> TeamAnalysis {
        try await get(
            environment.baseURL
                .appendingPathComponent("api/v2/teams")
                .appendingPathComponent(canonicalId)
                .appendingPathComponent("analysis"),
            as: TeamAnalysis.self
        )
    }

    public func appConfig() async throws -> AppConfig {
        try await get(
            environment.baseURL.appendingPathComponent("api/v2/app-config"),
            as: AppConfig.self
        )
    }

    private func get<T: Decodable>(_ url: URL, as type: T.Type) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(environment.userAgent, forHTTPHeaderField: "User-Agent")
        // A per-request ID makes a native failure traceable in server logs.
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")
        request.timeoutInterval = 20

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let error as URLError {
            switch error.code {
            case .notConnectedToInternet, .networkConnectionLost, .dataNotAllowed:
                throw APIError.offline
            case .cancelled:
                throw APIError.cancelled
            default:
                throw APIError.server(status: error.errorCode)
            }
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError.server(status: -1)
        }

        guard (200..<300).contains(http.statusCode) else {
            throw Self.mapFailure(status: http.statusCode, data: data, response: http)
        }

        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decoding(message: String(describing: error))
        }
    }

    private static func mapFailure(status: Int, data: Data, response: HTTPURLResponse) -> APIError {
        let envelope = try? JSONDecoder().decode(ErrorEnvelope.self, from: data)
        let message = envelope?.error.message ?? ""

        switch status {
        case 429:
            // Prefer the structured value, then the standard header.
            let retryAfter = envelope?.error.retryAfterSeconds
                ?? response.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init)
            return .rateLimited(retryAfterSeconds: retryAfter)
        case 400:
            return .invalidRequest(message: message.isEmpty
                ? String(localized: "That request was not valid.") : message)
        case 503:
            return .providerUnavailable(message: message)
        default:
            return .server(status: status)
        }
    }
}
