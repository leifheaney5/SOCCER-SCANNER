import SwiftUI
import Observation

@main
struct SoccerScannerApp: App {
    @State private var container = AppContainer()

    var body: some Scene {
        WindowGroup {
            FixtureListView(
                model: container.makeFixtureListModel(),
                router: container.router,
                client: container.client,
                environment: container.environment
            )
                .onOpenURL { url in
                    container.handle(url)
                }
                // Universal links arrive as a user activity, not onOpenURL.
                .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                    if let url = activity.webpageURL {
                        container.handle(url)
                    }
                }
        }
    }
}

/// Composition root. Dependencies are constructed here and injected, so tests
/// substitute a stub client without touching the network.
@MainActor
@Observable
final class AppContainer {
    let environment: AppEnvironment
    let client: FixtureFetching
    let router: AppRouter

    init(
        environment: AppEnvironment = .current(),
        client: FixtureFetching? = nil,
        defaults: UserDefaults = .standard
    ) {
        self.environment = environment
        self.client = client ?? Self.resolveClient(environment: environment, defaults: defaults)
        self.router = AppRouter()
        if let urlString = defaults.string(forKey: "UITestDeepLink")
            ?? Self.argumentValue("UITestDeepLink"),
           let url = URL(string: urlString) {
            router.handle(url)
        }
    }

    /// UI tests run against deterministic stub data so they never depend on the
    /// network or on which fixtures happen to be scheduled today.
    private static func resolveClient(
        environment: AppEnvironment,
        defaults: UserDefaults
    ) -> FixtureFetching {
        #if DEBUG
        let diagnosticMode = ProcessInfo.processInfo.environment["SOCCER_SCANNER_UI_TEST_MODE"] ?? "nil"
        let diagnosticArguments = ProcessInfo.processInfo.arguments
        let diagnosticDefaults = defaults.dictionaryRepresentation().keys.filter { $0.hasPrefix("UITest") }
        print(
            "SOCCER_SCANNER_DIAGNOSTIC env=\(diagnosticMode) args=\(diagnosticArguments) defaults=\(diagnosticDefaults)"
        )
        #endif
        switch (ProcessInfo.processInfo.environment["SOCCER_SCANNER_UI_TEST_MODE"]
            ?? ProcessInfo.processInfo.environment["SOCCER_SCANNER_ENVIRONMENT"]) {
        case "ui-test-failure":
            return PreviewFixtureClient(behaviour: .failure(.providerUnavailable(message: "stub")))
        case "ui-test-team-failure":
            return PreviewFixtureClient(behaviour: .teamFailure)
        case "ui-test-partial":
            return PreviewFixtureClient(behaviour: .partial)
        case "ui-test-stale":
            return PreviewFixtureClient(behaviour: .stale)
        case "ui-test-empty":
            return PreviewFixtureClient(behaviour: .empty)
        case "ui-test-accessibility":
            return PreviewFixtureClient(behaviour: .accessibility)
        case "ui-test", "ui-test-production":
            return PreviewFixtureClient(behaviour: .loaded)
        default:
            break
        }
        guard Self.flag("UITestStubData", defaults: defaults) else {
            return APIClient(environment: environment)
        }
        if Self.flag("UITestFailure", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .failure(.providerUnavailable(message: "stub")))
        }
        if Self.flag("UITestTeamFailure", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .teamFailure)
        }
        if Self.flag("UITestPartial", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .partial)
        }
        if Self.flag("UITestStale", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .stale)
        }
        if Self.flag("UITestEmpty", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .empty)
        }
        if Self.flag("UITestAccessibilityFixtures", defaults: defaults) {
            return PreviewFixtureClient(behaviour: .accessibility)
        }
        return PreviewFixtureClient(behaviour: .loaded)
    }

    private static func flag(_ name: String, defaults: UserDefaults) -> Bool {
        defaults.bool(forKey: name)
            || ProcessInfo.processInfo.environment["SOCCER_SCANNER_UI_TEST_\(name)"] == "1"
            || ProcessInfo.processInfo.arguments.contains("-\(name)")
    }

    private static func argumentValue(_ name: String) -> String? {
        if let environmentValue = ProcessInfo.processInfo.environment["SOCCER_SCANNER_UI_TEST_\(name)"] {
            return environmentValue
        }
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: "-\(name)"),
              arguments.index(after: index) < arguments.endIndex else {
            return nil
        }
        return arguments[arguments.index(after: index)]
    }

    func makeFixtureListModel() -> FixtureListViewModel {
        FixtureListViewModel(client: client, timeZone: .current)
    }

    /// Unparseable links are ignored so the system can fall back to the web.
    func handle(_ url: URL) {
        router.handle(url)
    }
}
