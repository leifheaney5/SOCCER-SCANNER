import SwiftUI

public struct FixtureDetailView: View {
    let fixture: Fixture
    let timeZone: TimeZone
    let scoreText: String?

    public init(fixture: Fixture, timeZone: TimeZone, scoreText: String?) {
        self.fixture = fixture
        self.timeZone = timeZone
        self.scoreText = scoreText
    }

    public var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    StatusBadge(status: fixture.status)
                    Text("\(fixture.homeTeam.name) v \(fixture.awayTeam.name)")
                        .font(.title3.weight(.semibold))
                    if let scoreText {
                        Text(scoreText)
                            .font(.largeTitle.monospacedDigit())
                            .accessibilityIdentifier("detail-score")
                    } else if fixture.status.scoreAvailable {
                        Label(String(localized: "Score hidden"), systemImage: "eye.slash")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .accessibilityIdentifier("detail-score-hidden")
                    }
                }
                .padding(.vertical, Theme.Spacing.xs)
            }

            Section(String(localized: "Match")) {
                LabeledContent(String(localized: "Kick-off"),
                               value: FixtureTime.kickoff(fixture.utcDate, in: timeZone))
                LabeledContent(String(localized: "Timezone"), value: timeZone.identifier)
                if let competition = fixture.competition?.displayName {
                    LabeledContent(String(localized: "Competition"), value: competition)
                }
                if let country = fixture.competition?.countryName {
                    LabeledContent(String(localized: "Country"), value: country)
                }
                if let venue = fixture.venue {
                    LabeledContent(String(localized: "Venue"), value: venue)
                }
            }

            if !fixture.streamingServices.isEmpty {
                Section(String(localized: "Where to watch")) {
                    ForEach(Array(fixture.streamingServices.enumerated()), id: \.offset) { _, broadcast in
                        HStack {
                            Text(broadcast.name ?? String(localized: "Unknown service"))
                            Spacer()
                            // Region is always shown, and labelled honestly when
                            // the provider did not supply one.
                            Text(broadcast.regionLabel)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                    Text(String(localized: "Availability varies by region and subscription. Listings may be incomplete or out of date."))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(String(localized: "Match details"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("fixture-detail")
    }
}
