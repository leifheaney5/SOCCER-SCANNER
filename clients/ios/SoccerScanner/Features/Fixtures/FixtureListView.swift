import SwiftUI

public struct FixtureListView: View {
    @State private var model: FixtureListViewModel
    @State private var selectedFixture: Fixture?

    public init(model: FixtureListViewModel) {
        _model = State(initialValue: model)
    }

    public var body: some View {
        NavigationStack {
            content
                .navigationTitle(String(localized: "Fixtures"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { toolbarContent }
                .navigationDestination(item: $selectedFixture) { fixture in
                    FixtureDetailView(
                        fixture: fixture,
                        timeZone: model.selectedTimeZone,
                        scoreText: model.scoreText(for: fixture)
                    )
                }
        }
        .task { await model.load() }
    }

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            // Timezone sits beside the score control, mirroring the web header.
            Text(FixtureTime.zoneLabel(model.selectedTimeZone))
                .font(.caption)
                .foregroundStyle(.secondary)
                .accessibilityLabel(FixtureTime.accessibleZoneName(model.selectedTimeZone))
                .accessibilityIdentifier("timezone-label")
        }
        ToolbarItem(placement: .topBarTrailing) {
            Button {
                model.toggleScores()
            } label: {
                Label(
                    model.scoresRevealed
                        ? String(localized: "Hide scores")
                        : String(localized: "Reveal scores"),
                    systemImage: model.scoresRevealed ? "eye.slash" : "eye"
                )
            }
            .accessibilityIdentifier("score-toggle")
        }
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .idle, .loading:
            ProgressView(String(localized: "Loading fixtures"))
                .accessibilityIdentifier("fixtures-loading")
        case .loaded(let data):
            fixtureList(data, notice: nil)
        case .stale(let data):
            fixtureList(data, notice: String(localized: "Showing recently cached fixtures."))
        case .partial(let data, let reason):
            fixtureList(data, notice: reason)
        case .empty:
            ContentUnavailableView(
                String(localized: "No fixtures"),
                systemImage: "calendar",
                description: Text(String(localized: "No matches are scheduled for this day."))
            )
            .accessibilityIdentifier("fixtures-empty")
        case .failed(let error):
            errorView(error)
        }
    }

    private func fixtureList(_ data: FixtureDayViewData, notice: String?) -> some View {
        List {
            if let notice {
                Section {
                    Label(notice, systemImage: "exclamationmark.triangle")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .accessibilityIdentifier("fixtures-notice")
                }
            }
            Section(FixtureTime.dayHeading(for: data.day, in: model.selectedTimeZone)) {
                ForEach(data.fixtures) { fixture in
                    Button {
                        selectedFixture = fixture
                    } label: {
                        FixtureRow(
                            fixture: fixture,
                            timeZone: model.selectedTimeZone,
                            scoreText: model.scoreText(for: fixture)
                        )
                    }
                    .buttonStyle(.plain)
                    // The identifier belongs on the control, not its label:
                    // the Button is the element that is queried and tapped.
                    .accessibilityIdentifier("fixture-row")
                }
            }
        }
        .listStyle(.insetGrouped)
        .refreshable { await model.load() }
        .accessibilityIdentifier("fixtures-list")
    }

    private func errorView(_ error: APIError) -> some View {
        ContentUnavailableView {
            Label(String(localized: "Fixtures unavailable"), systemImage: "wifi.exclamationmark")
        } description: {
            Text(error.userMessage)
        } actions: {
            if error.isRetryable {
                Button(String(localized: "Try again")) {
                    Task { await model.load() }
                }
                .accessibilityIdentifier("fixtures-retry")
            }
        }
        // Without `.contain` the view is not an accessibility container, so the
        // identifier is not queryable by assistive technology or UI tests.
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("fixtures-error")
    }
}

struct FixtureRow: View {
    let fixture: Fixture
    let timeZone: TimeZone
    let scoreText: String?

    var body: some View {
        HStack(alignment: .center, spacing: Theme.Spacing.md) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                StatusBadge(status: fixture.status)
                Text(FixtureTime.kickoff(fixture.utcDate, in: timeZone))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            .frame(width: 92, alignment: .leading)

            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(fixture.homeTeam.name).font(.body)
                Text(fixture.awayTeam.name).font(.body)
                if let competition = fixture.competition?.displayName {
                    Text(competition)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer(minLength: Theme.Spacing.sm)

            if let scoreText {
                Text(scoreText)
                    .font(.headline.monospacedDigit())
                    .accessibilityIdentifier("fixture-score")
            } else if fixture.status.scoreAvailable {
                // A score exists but is deliberately concealed.
                Image(systemName: "eye.slash")
                    .foregroundStyle(.secondary)
                    .accessibilityLabel(String(localized: "Score hidden"))
                    .accessibilityIdentifier("fixture-score-hidden")
            }
        }
        .padding(.vertical, Theme.Spacing.xs)
        .frame(minHeight: Theme.minimumTapTarget)
        .contentShape(Rectangle())
        // Children are deliberately left addressable rather than combined:
        // `.combine` would flatten the row and hide the score elements from
        // both assistive technology queries and UI tests.
        .accessibilityElement(children: .contain)
    }
}

#Preview("Loaded") {
    FixtureListView(model: FixtureListViewModel(client: PreviewFixtureClient()))
}
