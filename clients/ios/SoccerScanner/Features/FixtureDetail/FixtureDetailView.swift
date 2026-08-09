import SwiftUI

public struct FixtureDetailView: View {
    let fixture: Fixture
    let timeZone: TimeZone
    @Binding private var scoresRevealed: Bool
    let providers: [ProviderReport]
    let freshness: Freshness?
    let client: FixtureFetching

    public init(
        fixture: Fixture,
        timeZone: TimeZone,
        scoresRevealed: Binding<Bool>,
        providers: [ProviderReport] = [],
        freshness: Freshness? = nil,
        client: FixtureFetching
    ) {
        self.fixture = fixture
        self.timeZone = timeZone
        self._scoresRevealed = scoresRevealed
        self.providers = providers
        self.freshness = freshness
        self.client = client
    }

    public var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    StatusBadge(status: fixture.status)
                    Text("\(fixture.homeTeam.name) v \(fixture.awayTeam.name)")
                        .font(.title3.weight(.semibold))
                    if let scoreText = revealedScoreText {
                        Text(scoreText)
                            .font(.largeTitle.monospacedDigit())
                            .accessibilityIdentifier("detail-score")
                    } else if fixture.status.scoreAvailable && fixture.hasFullTimeScore {
                        Label(String(localized: "Score hidden"), systemImage: "eye.slash")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .accessibilityIdentifier("detail-score-hidden")
                    } else if fixture.status.scoreAvailable {
                        Label(String(localized: "Score unavailable"), systemImage: "questionmark")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .accessibilityIdentifier("detail-score-unavailable")
                    }
                }
                .padding(.vertical, Theme.Spacing.xs)
            }

            if fixture.status.scoreAvailable {
                Section(String(localized: "Spoiler control")) {
                    Button {
                        scoresRevealed.toggle()
                    } label: {
                        Label(
                            scoresRevealed
                                ? String(localized: "Hide score")
                                : String(localized: "Reveal score"),
                            systemImage: scoresRevealed ? "eye.slash" : "eye"
                        )
                    }
                    .accessibilityIdentifier("detail-score-toggle")
                }
            }

            Section(String(localized: "Match")) {
                LabeledContent(String(localized: "Kick-off"),
                               value: FixtureTime.kickoff(fixture.utcDate, in: timeZone))
                LabeledContent(String(localized: "Timezone"), value: timeZone.identifier)
                LabeledContent(
                    String(localized: "Competition"),
                    value: fixture.competition?.displayName ?? String(localized: "Unavailable")
                )
                .accessibilityIdentifier("detail-competition")
                LabeledContent(
                    String(localized: "Country"),
                    value: fixture.competition?.countryName ?? String(localized: "Unavailable")
                )
                LabeledContent(
                    String(localized: "Venue"),
                    value: fixture.venue ?? String(localized: "Unavailable")
                )
            }

            Section(String(localized: "Where to watch")) {
                if fixture.broadcasts.isEmpty {
                    Text(String(localized: "No broadcast listing was provided."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(fixture.broadcasts.enumerated()), id: \.offset) { index, broadcast in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(broadcast.name ?? String(localized: "Unknown service"))
                            HStack {
                                Text(broadcast.categoryLabel)
                                Spacer()
                                // Region is always shown, and labelled honestly when
                                // the provider did not supply one.
                                Text(broadcast.regionLabel)
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("detail-broadcast-\(fixture.id)-\(index)")
                    }
                }
                Text(String(localized: "Availability varies by region and subscription. Listings may be incomplete or out of date."))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            if !providers.isEmpty || freshness != nil {
                Section(String(localized: "Data quality")) {
                    ForEach(providers, id: \.name) { provider in
                        LabeledContent(
                            provider.name ?? String(localized: "Provider unavailable"),
                            value: providerStatusLabel(provider.status)
                        )
                    }
                    if let ageSeconds = freshness?.ageSeconds, ageSeconds >= 0 {
                        LabeledContent(
                            String(localized: "Last updated"),
                            value: freshnessLabel(ageSeconds)
                        )
                    }
                    Text(String(localized: "Provider coverage and update age describe this response, not a guarantee that every fixture is complete."))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(String(localized: "Match details"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("fixture-detail")
    }

    private func providerStatusLabel(_ status: String?) -> String {
        switch status?.lowercased() {
        case "success": return String(localized: "Available")
        case "disabled": return String(localized: "Disabled")
        case "partial": return String(localized: "Partial")
        case "rate_limited": return String(localized: "Rate limited")
        case "unavailable": return String(localized: "Unavailable")
        default: return String(localized: "Status unavailable")
        }
    }

    private func freshnessLabel(_ ageSeconds: Double) -> String {
        let seconds = Int(ageSeconds.rounded())
        if seconds < 60 { return String(localized: "\(seconds) seconds ago") }
        let minutes = seconds / 60
        if minutes < 60 { return String(localized: "\(minutes) minutes ago") }
        return String(localized: "\(minutes / 60) hours ago")
    }

    private var revealedScoreText: String? {
        guard scoresRevealed, fixture.status.scoreAvailable,
              let home = fixture.score?.fullTime?.home,
              let away = fixture.score?.fullTime?.away else { return nil }
        return "\(home) – \(away)"
    }
}
