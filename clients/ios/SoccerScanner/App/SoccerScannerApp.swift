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
        if let urlString = defaults.string(forKey: "UITestDeepLink"),
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
        guard defaults.bool(forKey: "UITestStubData") else {
            return APIClient(environment: environment)
        }
        if defaults.bool(forKey: "UITestFailure") {
            return PreviewFixtureClient(behaviour: .failure(.providerUnavailable(message: "stub")))
        }
        if defaults.bool(forKey: "UITestTeamFailure") {
            return PreviewFixtureClient(behaviour: .teamFailure)
        }
        if defaults.bool(forKey: "UITestPartial") {
            return PreviewFixtureClient(behaviour: .partial)
        }
        if defaults.bool(forKey: "UITestStale") {
            return PreviewFixtureClient(behaviour: .stale)
        }
        if defaults.bool(forKey: "UITestEmpty") {
            return PreviewFixtureClient(behaviour: .empty)
        }
        if defaults.bool(forKey: "UITestAccessibilityFixtures") {
            return PreviewFixtureClient(behaviour: .accessibility)
        }
        return PreviewFixtureClient(behaviour: .loaded)
    }

    func makeFixtureListModel() -> FixtureListViewModel {
        FixtureListViewModel(client: client, timeZone: .current)
    }

    /// Unparseable links are ignored so the system can fall back to the web.
    func handle(_ url: URL) {
        router.handle(url)
    }
}
