import SwiftUI

public struct SettingsView: View {
    private let environment: AppEnvironment
    private let timeZone: TimeZone
    private let publicBaseURL: URL

    public init(environment: AppEnvironment, timeZone: TimeZone) {
        self.environment = environment
        self.timeZone = timeZone
        self.publicBaseURL = AppEnvironment.production.baseURL
    }

    public var body: some View {
        Form {
            Section(String(localized: "About")) {
                LabeledContent(String(localized: "Version"), value: Bundle.appVersion)
                LabeledContent(String(localized: "Build"), value: Bundle.buildNumber)
                LabeledContent(
                    String(localized: "Timezone"),
                    value: FixtureTime.accessibleZoneName(timeZone)
                )
                if environment != .production {
                    LabeledContent(String(localized: "Environment"), value: environment.name)
                        .accessibilityIdentifier("settings-environment")
                }
            }

            Section(String(localized: "Scores")) {
                Text(String(localized: "Scores stay hidden until you choose Reveal scores on the fixture list."))
                    .accessibilityIdentifier("settings-score-explanation")
            }

            Section(String(localized: "Data sources")) {
                Text(String(localized: "Fixture sources and availability are documented on the website."))
                Link(String(localized: "Data sources"), destination: pageURL("data-sources"))
                    .accessibilityIdentifier("settings-data-sources-link")
            }

            Section(String(localized: "Support")) {
                Text(String(localized: "Support contact is not configured for this build."))
                    .accessibilityIdentifier("settings-support-unavailable")
            }

            Section(String(localized: "Website and legal")) {
                Link(String(localized: "Soccer Scanner website"), destination: publicBaseURL)
                    .accessibilityIdentifier("settings-website-link")
                Link(String(localized: "Privacy"), destination: pageURL("privacy"))
                    .accessibilityIdentifier("settings-privacy-link")
                Link(String(localized: "Terms of Service"), destination: pageURL("terms"))
                    .accessibilityIdentifier("settings-terms-link")
            }
        }
        .navigationTitle(String(localized: "Settings"))
        .accessibilityIdentifier("settings-view")
    }

    private func pageURL(_ path: String) -> URL {
        publicBaseURL.appendingPathComponent(path)
    }
}
