import Foundation
import Observation

/// Every state the fixture list can be in.
///
/// `partial` and `stale` are first-class rather than being flattened into
/// `loaded`: presenting an incomplete day as though it were the full schedule
/// is a correctness problem, not a cosmetic one.
public enum FixtureListState: Equatable {
    case idle
    case loading
    case loaded(FixtureDayViewData)
    case partial(FixtureDayViewData, reason: String)
    case stale(FixtureDayViewData)
    case empty
    case failed(APIError)
}

public struct FixtureDayViewData: Equatable {
    public let day: String
    public let fixtures: [Fixture]
    public let timeZoneIdentifier: String

    public static func == (lhs: FixtureDayViewData, rhs: FixtureDayViewData) -> Bool {
        lhs.day == rhs.day
            && lhs.timeZoneIdentifier == rhs.timeZoneIdentifier
            && lhs.fixtures.map(\.id) == rhs.fixtures.map(\.id)
    }
}

@MainActor
@Observable
public final class FixtureListViewModel {
    public private(set) var state: FixtureListState = .idle
    public private(set) var scoresRevealed = false

    public var selectedTimeZone: TimeZone {
        didSet {
            guard selectedTimeZone != oldValue else { return }
            // Changing zone can move the fixture day, so reload against the
            // day that is "today" in the newly selected zone.
            Task { await load() }
        }
    }

    public private(set) var day: String

    private let client: FixtureFetching

    public init(
        client: FixtureFetching,
        timeZone: TimeZone = .current,
        day: String? = nil,
        now: Date = Date()
    ) {
        self.client = client
        self.selectedTimeZone = timeZone
        self.day = day ?? FixtureTime.today(in: timeZone, now: now)
    }

    public func selectDay(_ newDay: String) async {
        day = newDay
        await load()
    }

    public func shiftDay(by days: Int) async {
        day = FixtureTime.shiftDay(day, by: days)
        await load()
    }

    /// Spoiler control. Scores start hidden every launch — never persisted,
    /// matching the web client's session-scoped behaviour.
    public func toggleScores() {
        scoresRevealed.toggle()
    }

    public func load() async {
        state = .loading
        do {
            let response = try await client.fixtures(date: day, timeZone: selectedTimeZone)
            let data = FixtureDayViewData(
                day: response.date.isEmpty ? day : response.date,
                fixtures: response.matches,
                timeZoneIdentifier: selectedTimeZone.identifier
            )
            if response.matches.isEmpty {
                state = .empty
            } else if response.isPartial {
                let failing = response.providers
                    .filter { $0.status != "ok" }
                    .compactMap(\.name)
                    .joined(separator: ", ")
                state = .partial(data, reason: failing.isEmpty
                    ? String(localized: "Some fixtures may be missing.")
                    : String(localized: "Incomplete data from \(failing)."))
            } else if response.isStale {
                state = .stale(data)
            } else {
                state = .loaded(data)
            }
        } catch let error as APIError {
            state = .failed(error)
        } catch {
            state = .failed(.server(status: -1))
        }
    }

    /// Whether a score may be shown at all, independent of the reveal toggle.
    public func canShowScore(for fixture: Fixture) -> Bool {
        fixture.status.scoreAvailable
    }

    public func scoreText(for fixture: Fixture) -> String? {
        guard scoresRevealed, canShowScore(for: fixture) else { return nil }
        guard let home = fixture.score?.fullTime?.home,
              let away = fixture.score?.fullTime?.away else { return nil }
        return "\(home) – \(away)"
    }
}
