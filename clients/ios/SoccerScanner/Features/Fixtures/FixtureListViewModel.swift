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

/// The route resolver preserves not-found separately from typed transport or
/// decoding failures, so navigation never turns an operational error into a
/// false missing-fixture claim.
public enum RouteFixtureOutcome {
    case found(Fixture)
    case missing
    case failed(APIError)
    case superseded
}

private enum FixtureLoadOutcome {
    case applied
    case discarded
    case failed
}

public enum FixtureStatusFilter: String, CaseIterable, Equatable, Hashable, Sendable {
    case all
    case live
    case upcoming
    case finished
}

public enum FixtureTimeWindow: String, CaseIterable, Equatable, Hashable, Sendable {
    case all
    case morning
    case afternoon
    case evening
    case lateNight

    public var label: String {
        switch self {
        case .all: return String(localized: "Any time")
        case .morning: return String(localized: "Morning")
        case .afternoon: return String(localized: "Afternoon")
        case .evening: return String(localized: "Evening")
        case .lateNight: return String(localized: "Late night")
        }
    }
}

public enum FixtureSort: String, CaseIterable, Equatable, Hashable, Sendable {
    case kickoff
    case competition
    case liveFirst
    case recommended

    public var label: String {
        switch self {
        case .kickoff: return String(localized: "Kickoff time")
        case .competition: return String(localized: "Competition")
        case .liveFirst: return String(localized: "Live first")
        case .recommended: return String(localized: "Recommended")
        }
    }
}

public struct FixtureFilter: Equatable, Sendable {
    public var status: FixtureStatusFilter
    public var searchText: String
    public var competition: String?
    public var country: String?
    public var timeWindow: FixtureTimeWindow
    public var sort: FixtureSort
    public var hideFinished: Bool

    public init(
        status: FixtureStatusFilter = .all,
        searchText: String = "",
        competition: String? = nil,
        country: String? = nil,
        timeWindow: FixtureTimeWindow = .all,
        sort: FixtureSort = .kickoff,
        hideFinished: Bool = false
    ) {
        self.status = status
        self.searchText = searchText
        self.competition = competition
        self.country = country
        self.timeWindow = timeWindow
        self.sort = sort
        self.hideFinished = hideFinished
    }

    /// Reset only controls owned by the advanced-filter sheet. Search and
    /// status stay visible on the main screen and therefore remain intact.
    public mutating func resetAdvanced() {
        competition = nil
        country = nil
        timeWindow = .all
        sort = .kickoff
        hideFinished = false
    }

    public var activeFilterCount: Int {
        let hasCompetition = !(competition?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
        let hasCountry = !(country?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
        return (hasCompetition ? 1 : 0)
            + (hasCountry ? 1 : 0)
            + (status == .all ? 0 : 1)
            + (searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0 : 1)
            + (timeWindow == .all ? 0 : 1)
            + (sort == .kickoff ? 0 : 1)
            + (hideFinished ? 1 : 0)
    }
}

public struct FixtureDayViewData: Equatable {
    public let day: String
    public let fixtures: [Fixture]
    public let timeZoneIdentifier: String
    public let providers: [ProviderReport]
    public let freshness: Freshness?

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
    public private(set) var lastLoadError: APIError?
    public private(set) var isRefreshing = false
    public private(set) var filter = FixtureFilter()

    /// Counts every non-default visible filtering or ordering control.
    public var activeFilterCount: Int {
        filter.activeFilterCount
    }

    /// Options are derived from the currently loaded metadata only. Missing
    /// names are omitted rather than relabelled as a guessed competition or
    /// country.
    public var availableCompetitionOptions: [String] {
        Self.availableOptions(sourceFixtures.compactMap { $0.competition?.name })
    }

    public var availableCountryOptions: [String] {
        Self.availableOptions(sourceFixtures.compactMap { $0.competition?.countryName })
    }

    public var currentProviders: [ProviderReport] {
        switch state {
        case .loaded(let data), .partial(let data, _), .stale(let data): return data.providers
        case .idle, .loading, .empty, .failed: return []
        }
    }

    public var currentFreshness: Freshness? {
        switch state {
        case .loaded(let data), .partial(let data, _), .stale(let data): return data.freshness
        case .idle, .loading, .empty, .failed: return nil
        }
    }

    public var loadErrorNotice: String? {
        lastLoadError?.userMessage
    }

    public var refreshNotice: String? {
        guard isRefreshing else { return nil }
        return String(localized: "Refreshing fixtures for \(day).")
    }

    public func notice(_ notice: String?) -> String? {
        let messages = [notice, refreshNotice].compactMap { $0 }
        return messages.isEmpty ? nil : messages.joined(separator: " ")
    }

    public func combinedNotice(_ notice: String) -> String {
        self.notice(notice) ?? notice
    }

    public var selectedTimeZone: TimeZone {
        didSet {
            guard selectedTimeZone != oldValue else { return }
            guard !suppressTimeZoneLoad else { return }
            // A selected calendar day remains a calendar day when its display
            // zone changes; only the query zone changes.
            Task { await load() }
        }
    }

    public private(set) var day: String

    private let client: FixtureFetching
    private var loadGeneration = 0
    private var activeLoad: Task<FixtureLoadOutcome, Never>?
    private var suppressTimeZoneLoad = false

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

    public func setStatusFilter(_ status: FixtureStatusFilter) {
        filter.status = status
    }

    public func setSearchText(_ searchText: String) {
        filter.searchText = searchText
    }

    /// Applies a local projection only. This method never starts a network
    /// request; the loaded source day remains the sole filtering input.
    public func applyFilter(_ nextFilter: FixtureFilter) {
        filter = nextFilter
    }

    public func resetAdvancedFilter() {
        var nextFilter = filter
        nextFilter.resetAdvanced()
        filter = nextFilter
    }

    /// The local projection intentionally uses only non-score fixture fields.
    /// Provider data remains unmodified in `FixtureDayViewData` for the list
    /// state and source-data truthfulness boundaries.
    public var filteredFixtures: [Fixture] {
        let normalizedSearch = Self.normalizedSearch(filter.searchText)
        let filtered = sourceFixtures.filter { fixture in
            guard Self.matches(status: fixture.status, filter: filter.status) else { return false }
            guard !filter.hideFinished || fixture.status != .finished else { return false }
            guard Self.matches(
                fixture.competition?.name,
                selected: filter.competition
            ) else { return false }
            guard Self.matches(
                fixture.competition?.countryName,
                selected: filter.country
            ) else { return false }
            guard Self.matches(
                fixture.utcDate,
                window: filter.timeWindow,
                timeZone: selectedTimeZone
            ) else { return false }
            guard !normalizedSearch.isEmpty else { return true }
            return Self.normalizedSearch(Self.searchHaystack(for: fixture))
                .contains(normalizedSearch)
        }
        return filtered.sorted { Self.isOrdered($0, before: $1, by: filter.sort) }
    }

    /// Spoiler control. Scores start hidden every launch — never persisted,
    /// matching the web client's session-scoped behaviour.
    public func toggleScores() {
        scoresRevealed.toggle()
    }

    public func load() async {
        let task = beginLoad()
        _ = await task.value
    }

    /// Looks up a route fixture, then makes its timezone-local day the active
    /// list query before returning the lookup result for navigation.
    public func openFixture(id: String) async -> Fixture? {
        let generation = loadGeneration
        let requestedDay = day
        let requestedTimeZoneIdentifier = selectedTimeZone.identifier
        do {
            let fixture = try await client.fixture(id: id)
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ) else { return nil }
            let resolvedTimeZone = FixtureTime.resolve(
                selectedTimeZone.identifier,
                fallback: selectedTimeZone
            )
            selectedTimeZone = resolvedTimeZone
            if let kickoff = fixture.utcDate {
                day = FixtureTime.calendarDate(for: kickoff, in: resolvedTimeZone)
                await load()
            }
            return fixture
        } catch let error as APIError {
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ) else { return nil }
            if error == .server(status: 404) || error == .cancelled { return nil }
            state = .failed(error)
            return nil
        } catch {
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ) else { return nil }
            state = .failed(.server(status: -1))
            return nil
        }
    }

    /// Resolves a fixture route and applies its selected day only after the
    /// route-owned day load returns while the same route still owns the model.
    public func openRouteFixture(
        id: String,
        timeZoneIdentifier: String?,
        calendarDay: String?,
        isCurrentRoute: @escaping @MainActor () -> Bool
    ) async -> RouteFixtureOutcome {
        let generation = loadGeneration
        let requestedDay = day
        let requestedTimeZoneIdentifier = selectedTimeZone.identifier

        do {
            let fixture = try await client.fixture(id: id)
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ), isCurrentRoute() else {
                return .superseded
            }

            let resolvedTimeZone = FixtureTime.resolve(
                timeZoneIdentifier,
                fallback: selectedTimeZone
            )
            let resolvedDay = calendarDay
                ?? fixture.utcDate.map { FixtureTime.calendarDate(for: $0, in: resolvedTimeZone) }
            if let resolvedDay {
                let routeLoad = beginRouteDayLoad(
                    day: resolvedDay,
                    timeZone: resolvedTimeZone,
                    isCurrentRoute: isCurrentRoute
                )
                switch await routeLoad.value {
                case .applied:
                    guard isCurrentRoute() else { return .superseded }
                case .discarded:
                    return .superseded
                case .failed:
                    return isCurrentRoute() ? .failed(.server(status: -1)) : .superseded
                }
            } else if timeZoneIdentifier != nil {
                guard isCurrentRoute() else { return .superseded }
                suppressTimeZoneLoad = true
                selectedTimeZone = FixtureTime.resolve(
                    timeZoneIdentifier,
                    fallback: selectedTimeZone
                )
                suppressTimeZoneLoad = false
            }
            return .found(fixture)
        } catch let error as APIError {
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ), isCurrentRoute() else {
                return .superseded
            }
            if error == .cancelled { return .superseded }
            if error == .server(status: 404) { return .missing }
            return .failed(error)
        } catch {
            guard isCurrentRequest(
                generation: generation,
                day: requestedDay,
                timeZoneIdentifier: requestedTimeZoneIdentifier
            ), isCurrentRoute() else {
                return .superseded
            }
            return .failed(.server(status: -1))
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

    private var sourceFixtures: [Fixture] {
        switch state {
        case .loaded(let data), .stale(let data), .partial(let data, _):
            return data.fixtures
        case .idle, .loading, .empty, .failed:
            return []
        }
    }

    private func beginLoad() -> Task<FixtureLoadOutcome, Never> {
        activeLoad?.cancel()
        loadGeneration += 1

        let generation = loadGeneration
        let requestedDay = day
        let requestedTimeZone = selectedTimeZone
        let requestedTimeZoneIdentifier = requestedTimeZone.identifier
        let client = client

        if !hasUsableData {
            state = .loading
        }
        isRefreshing = true

        let task: Task<FixtureLoadOutcome, Never> = Task { [weak self] in
            defer {
                if let self, self.loadGeneration == generation {
                    self.isRefreshing = false
                }
            }
            do {
                let response = try await client.fixtures(
                    date: requestedDay,
                    timeZone: requestedTimeZone
                )
                guard let self,
                      !Task.isCancelled,
                      self.isCurrentRequest(
                          generation: generation,
                          day: requestedDay,
                          timeZoneIdentifier: requestedTimeZoneIdentifier
                      ) else { return .discarded }
                self.isRefreshing = false
                self.apply(response, requestedDay: requestedDay, timeZoneIdentifier: requestedTimeZoneIdentifier)
                self.lastLoadError = nil
                return .applied
            } catch let error as APIError {
                guard let self,
                      !Task.isCancelled,
                      self.isCurrentRequest(
                          generation: generation,
                          day: requestedDay,
                          timeZoneIdentifier: requestedTimeZoneIdentifier
                      ),
                      error != .cancelled else { return .discarded }
                self.isRefreshing = false
                if self.hasUsableData {
                    self.lastLoadError = error
                } else {
                    self.state = .failed(error)
                }
                return .applied
            } catch {
                guard let self,
                      !Task.isCancelled,
                      self.isCurrentRequest(
                          generation: generation,
                          day: requestedDay,
                          timeZoneIdentifier: requestedTimeZoneIdentifier
                      ) else { return .discarded }
                self.isRefreshing = false
                let error = APIError.server(status: -1)
                if self.hasUsableData {
                    self.lastLoadError = error
                } else {
                    self.state = .failed(error)
                }
                return .applied
            }
        }
        activeLoad = task
        return task
    }

    /// Fetches a route's target day without exposing it as the selected day
    /// until both the generation and route owner still match after the await.
    private func beginRouteDayLoad(
        day requestedDay: String,
        timeZone requestedTimeZone: TimeZone,
        isCurrentRoute: @escaping @MainActor () -> Bool
    ) -> Task<FixtureLoadOutcome, Never> {
        activeLoad?.cancel()
        loadGeneration += 1

        let generation = loadGeneration
        let requestedTimeZoneIdentifier = requestedTimeZone.identifier
        let client = client
        isRefreshing = true
        let task: Task<FixtureLoadOutcome, Never> = Task { [weak self] in
            defer {
                if let self, self.loadGeneration == generation {
                    self.isRefreshing = false
                }
            }
            do {
                let response = try await client.fixtures(
                    date: requestedDay,
                    timeZone: requestedTimeZone
                )
                guard let self,
                      !Task.isCancelled,
                      self.loadGeneration == generation,
                      isCurrentRoute() else { return .discarded }
                self.isRefreshing = false
                self.suppressTimeZoneLoad = true
                self.selectedTimeZone = requestedTimeZone
                self.suppressTimeZoneLoad = false
                self.day = requestedDay
                self.apply(
                    response,
                    requestedDay: requestedDay,
                    timeZoneIdentifier: requestedTimeZoneIdentifier
                )
                return .applied
            } catch let error as APIError {
                // Route failures return through RouteFixtureOutcome and must
                // not replace usable rows with a full-screen list failure.
                guard let self,
                      !Task.isCancelled,
                      self.loadGeneration == generation,
                      isCurrentRoute() else { return .discarded }
                self.isRefreshing = false
                return error == .cancelled ? .discarded : .failed
            } catch {
                // Route failures return through RouteFixtureOutcome and must
                // not replace usable rows with a full-screen list failure.
                guard let self,
                      !Task.isCancelled,
                      self.loadGeneration == generation,
                      isCurrentRoute() else { return .discarded }
                self.isRefreshing = false
                return .failed
            }
        }
        activeLoad = task
        return task
    }

    private var hasUsableData: Bool {
        switch state {
        case .loaded, .partial, .stale: return true
        case .idle, .loading, .empty, .failed: return false
        }
    }

    private func isCurrentRequest(generation: Int, day: String, timeZoneIdentifier: String) -> Bool {
        loadGeneration == generation
            && self.day == day
            && selectedTimeZone.identifier == timeZoneIdentifier
    }

    private func apply(_ response: FixtureDay, requestedDay: String, timeZoneIdentifier: String) {
        reconcileMetadataSelections(with: response.matches)
        let data = FixtureDayViewData(
            day: response.date.isEmpty ? requestedDay : response.date,
            fixtures: response.matches,
            timeZoneIdentifier: timeZoneIdentifier,
            providers: response.providers,
            freshness: response.freshness
        )
        if response.isPartial {
            let failing = response.providers
                .filter { $0.status != "success" && $0.status != "disabled" }
                .compactMap(\.name)
                .joined(separator: ", ")
            state = .partial(data, reason: failing.isEmpty
                ? String(localized: "Some fixtures may be missing.")
                : String(localized: "Incomplete data from \(failing)."))
        } else if response.matches.isEmpty {
            state = .empty
        } else if response.isStale {
            state = .stale(data)
        } else {
            state = .loaded(data)
        }
    }

    /// A competition or area selection is meaningful only for the currently
    /// loaded metadata. Clear selections that disappear on a new day or zone
    /// response so the picker and result state never claim a stale option.
    private func reconcileMetadataSelections(with fixtures: [Fixture]) {
        let competitions = Set(Self.availableOptions(
            fixtures.compactMap { $0.competition?.name }
        ).map { Self.normalizedSearch($0) })
        let countries = Set(Self.availableOptions(
            fixtures.compactMap { $0.competition?.countryName }
        ).map { Self.normalizedSearch($0) })

        if let competition = filter.competition,
           !competitions.contains(Self.normalizedSearch(competition)) {
            filter.competition = nil
        }
        if let country = filter.country,
           !countries.contains(Self.normalizedSearch(country)) {
            filter.country = nil
        }
    }

    private static func matches(status: MatchStatus, filter: FixtureStatusFilter) -> Bool {
        switch filter {
        case .all: return true
        case .live: return status.isActive
        case .upcoming:
            return !status.isActive && !status.isTerminal
                && [.scheduled, .delayed, .unknown].contains(status)
        case .finished: return status == .finished
        }
    }

    private static func matches(_ value: String?, selected: String?) -> Bool {
        guard let selected, !selected.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return true
        }
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return false
        }
        return normalizedSearch(value) == normalizedSearch(selected)
    }

    private static func matches(
        _ instant: Date?,
        window: FixtureTimeWindow,
        timeZone: TimeZone
    ) -> Bool {
        guard window != .all else { return true }
        guard let instant else { return false }

        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let hour = calendar.component(.hour, from: instant)
        switch window {
        case .all: return true
        case .morning: return hour >= 6 && hour < 12
        case .afternoon: return hour >= 12 && hour < 18
        case .evening: return hour >= 18 && hour < 24
        case .lateNight: return hour >= 0 && hour < 6
        }
    }

    private static func availableOptions(_ values: [String]) -> [String] {
        var unique = Set<String>()
        return values
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty && unique.insert($0).inserted }
            .sorted { left, right in
                let leftKey = normalizedSortKey(left)
                let rightKey = normalizedSortKey(right)
                return leftKey == rightKey ? left < right : leftKey < rightKey
            }
    }

    private static func isOrdered(
        _ left: Fixture,
        before right: Fixture,
        by sort: FixtureSort
    ) -> Bool {
        switch sort {
        case .kickoff:
            return kickoffThenStable(left, right)
        case .competition:
            let leftCompetition = left.competition?.name
                .map { normalizedSortKey($0) }
            let rightCompetition = right.competition?.name
                .map { normalizedSortKey($0) }
            if leftCompetition != rightCompetition {
                switch (leftCompetition, rightCompetition) {
                case (nil, _): return false
                case (_, nil): return true
                case let (left?, right?): return left < right
                }
            }
            return kickoffThenStable(left, right)
        case .liveFirst:
            let leftRank = liveFirstRank(for: left.status)
            let rightRank = liveFirstRank(for: right.status)
            if leftRank != rightRank { return leftRank < rightRank }
            return kickoffThenStable(left, right)
        case .recommended:
            let leftInterest = finiteInterest(for: left)
            let rightInterest = finiteInterest(for: right)
            if leftInterest != rightInterest {
                switch (leftInterest, rightInterest) {
                case (nil, _): return false
                case (_, nil): return true
                case let (left?, right?): return left > right
                }
            }
            return kickoffThenStable(left, right)
        }
    }

    private static func kickoffThenStable(_ left: Fixture, _ right: Fixture) -> Bool {
        if left.utcDate != right.utcDate {
            switch (left.utcDate, right.utcDate) {
            case (nil, _): return false
            case (_, nil): return true
            case let (left?, right?): return left < right
            }
        }
        return stableKey(for: left) < stableKey(for: right)
    }

    private static func liveFirstRank(for status: MatchStatus) -> Int {
        if status.isActive { return 0 }
        if status.isTerminal { return 2 }
        return 1
    }

    private static func finiteInterest(for fixture: Fixture) -> Double? {
        guard let interest = fixture.interestEstimate, interest.isFinite else { return nil }
        return interest
    }

    private static func stableKey(for fixture: Fixture) -> String {
        [
            fixture.competition?.name ?? "",
            fixture.competition?.countryName ?? "",
            fixture.homeTeam.name,
            fixture.awayTeam.name,
            fixture.id,
        ]
        .map(normalizedSortKey)
        .joined(separator: "\u{001F}")
    }

    private static func normalizedSortKey(_ value: String) -> String {
        value
            .folding(
                options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive],
                locale: Locale(identifier: "en_US_POSIX")
            )
            .lowercased()
    }

    private static func searchHaystack(for fixture: Fixture) -> String {
        [
            fixture.homeTeam.name,
            fixture.awayTeam.name,
            fixture.competition?.name ?? "",
            fixture.competition?.area?.name ?? "",
        ].joined(separator: " ")
    }

    private static func normalizedSearch(_ value: String) -> String {
        value
            .folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: .current)
            .lowercased()
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
