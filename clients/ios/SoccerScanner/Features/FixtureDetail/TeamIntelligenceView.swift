import SwiftUI

/// On-demand, spoiler-safe team data for a fixture participant.
///
/// Match arrays are deliberately absent from `TeamAnalysis`, so this sheet can
/// never display a score outside the fixture score-preference boundary.
public struct TeamIntelligenceView: View {
    private enum LoadState {
        case loading
        case loaded(TeamAnalysis)
        case unavailable(retryable: Bool)
    }

    private struct RequestKey: Hashable {
        let canonicalId: String
        let generation: Int
    }

    let team: Team
    let client: FixtureFetching
    @State private var state: LoadState = .loading
    @State private var requestGeneration = 0

    public init(team: Team, client: FixtureFetching) {
        self.team = team
        self.client = client
    }

    public var body: some View {
        NavigationStack {
            content
                .navigationTitle(String(localized: "Team intelligence"))
                .navigationBarTitleDisplayMode(.inline)
        }
        .task(id: RequestKey(canonicalId: canonicalId, generation: requestGeneration)) {
            await load()
        }
        .accessibilityIdentifier("team-intelligence-view")
    }

    @ViewBuilder
    private var content: some View {
        switch state {
        case .loading:
            ProgressView(String(localized: "Loading team intelligence"))
                .accessibilityIdentifier("team-intelligence-loading")
        case .loaded(let analysis):
            List {
                Section {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(analysis.teamInfo?.name ?? team.name)
                            .font(.title3.weight(.semibold))
                        Label(
                            String(localized: "Provider-verified team identity"),
                            systemImage: "checkmark.seal"
                        )
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, Theme.Spacing.xs)
                    .accessibilityIdentifier("team-intelligence-identity")
                }

                Section(String(localized: "Season record")) {
                    if let stats = analysis.stats {
                        statRow(String(localized: "Played"), value: stats.matchesPlayed)
                        statRow(String(localized: "Wins"), value: stats.wins)
                        statRow(String(localized: "Draws"), value: stats.draws)
                        statRow(String(localized: "Losses"), value: stats.losses)
                        statRow(String(localized: "Goals for"), value: stats.goalsFor)
                        statRow(String(localized: "Goals against"), value: stats.goalsAgainst)
                        statRow(
                            String(localized: "Goal difference"),
                            value: stats.goalDifference,
                            signed: true
                        )
                    } else {
                        Text(String(localized: "No aggregate season statistics were provided."))
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .accessibilityIdentifier("team-intelligence-stats")
            }
        case .unavailable(let retryable):
            ContentUnavailableView {
                Label(
                    String(localized: "Team intelligence unavailable"),
                    systemImage: "chart.bar.xaxis"
                )
            } description: {
                Text(String(localized: "Verified team data is temporarily unavailable."))
            } actions: {
                if retryable {
                    Button(String(localized: "Try again")) {
                        requestGeneration += 1
                    }
                    .accessibilityIdentifier("team-intelligence-retry")
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("team-intelligence-unavailable")
        }
    }

    private var canonicalId: String {
        team.canonicalId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    private func statRow(_ label: String, value: Int?, signed: Bool = false) -> some View {
        LabeledContent(
            label,
            value: statValue(value, signed: signed)
        )
    }

    private func statValue(_ value: Int?, signed: Bool) -> String {
        guard let value else { return String(localized: "Unavailable") }
        if signed, value > 0 { return "+\(value)" }
        return String(value)
    }

    private func load() async {
        state = .loading
        do {
            let analysis = try await client.teamAnalysis(canonicalId: canonicalId)
            guard !Task.isCancelled else { return }
            state = .loaded(analysis)
        } catch is CancellationError {
            return
        } catch let error as APIError where error == .cancelled {
            return
        } catch let error as APIError {
            state = .unavailable(retryable: error.isRetryable)
        } catch {
            state = .unavailable(retryable: true)
        }
    }
}
