import XCTest
@testable import SoccerScanner

@MainActor
final class FixtureListViewModelTests: XCTestCase {
    private func model(_ behaviour: PreviewFixtureClient.Behaviour = .loaded) -> FixtureListViewModel {
        FixtureListViewModel(
            client: PreviewFixtureClient(behaviour: behaviour),
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
    }

    func testLoadedDayExposesFixtures() async {
        let viewModel = model()
        await viewModel.load()

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("expected loaded, got \(viewModel.state)")
        }
        XCTAssertEqual(data.fixtures.count, 3)
        // Apple normalises the "UTC" alias to the "GMT" identifier, so compare
        // against the resolved zone rather than the string that was requested.
        XCTAssertEqual(data.timeZoneIdentifier, TimeZone(identifier: "UTC")!.identifier)
    }

    func testAPartialDayIsNotPresentedAsComplete() async {
        let viewModel = model(.partial)
        await viewModel.load()

        guard case .partial(_, let reason) = viewModel.state else {
            return XCTFail("expected partial, got \(viewModel.state)")
        }
        XCTAssertFalse(reason.isEmpty)
    }

    func testAnEmptyPartialResponseRemainsPartialInsteadOfEmpty() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            state: "partial",
            providers: "{\"espn\":{\"status\":\"unavailable\"}}",
            matches: "[]"
        )))
        await load.value

        guard case .partial(let data, let reason) = viewModel.state else {
            return XCTFail("an empty partial response must not become empty")
        }
        XCTAssertTrue(data.fixtures.isEmpty)
        XCTAssertFalse(reason.isEmpty)
    }

    func testPartialExplanationNamesFailingProvidersButNotDisabledOptionalProviders() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            state: "partial",
            providers: "{\"espn\":{\"status\":\"partial\"},\"football-data\":{\"status\":\"disabled\"}}",
            matches: #"[{"canonicalFixtureId":"fx_partial","homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]"#
        )))
        await load.value

        guard case .partial(_, let reason) = viewModel.state else {
            return XCTFail("authoritative partial response must remain partial")
        }
        XCTAssertTrue(reason.contains("espn"))
        XCTAssertFalse(reason.contains("football-data"))
    }

    func testSuccessWithADisabledOptionalProviderIsPresentedAsLoaded() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            providers: "{\"espn\":{\"status\":\"success\"},\"football-data\":{\"status\":\"disabled\"}}",
            matches: #"[{"canonicalFixtureId":"fx_loaded","homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]"#
        )))
        await load.value

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("success with a disabled optional provider must remain loaded")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_loaded"])
    }

    func testStaleWithADisabledOptionalProviderIsPresentedAsStale() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            state: "stale",
            providers: "{\"espn\":{\"status\":\"success\"},\"football-data\":{\"status\":\"disabled\"}}",
            matches: #"[{"canonicalFixtureId":"fx_stale","homeTeam":{"name":"A"},"awayTeam":{"name":"B"}}]"#
        )))
        await load.value

        guard case .stale(let data) = viewModel.state else {
            return XCTFail("stale with a disabled optional provider must remain stale")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_stale"])
    }

    func testAnEmptyDayIsDistinctFromAFailure() async {
        let viewModel = model(.empty)
        await viewModel.load()

        XCTAssertEqual(viewModel.state, .empty)
    }

    func testTypedFailuresSurfaceRetryability() async {
        let viewModel = model(.failure(.rateLimited(retryAfterSeconds: 30)))
        await viewModel.load()

        guard case .failed(let error) = viewModel.state else {
            return XCTFail("expected failure, got \(viewModel.state)")
        }
        XCTAssertEqual(error, .rateLimited(retryAfterSeconds: 30))
        XCTAssertTrue(error.isRetryable)
    }

    func testRefreshFailureRetainsUsableFixturesAndExposesTheError() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        XCTAssertTrue(viewModel.isRefreshing)
        await client.releaseNext(.success(try fixtureDay(
            matches: #"[{"canonicalFixtureId":"fx_retained","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Retained"},"awayTeam":{"name":"Fixture"}}]"#
        )))
        await initialLoad.value

        let refresh = Task { await viewModel.load() }
        await client.waitForRequestCount(2)
        XCTAssertEqual(viewModel.refreshNotice, "Refreshing fixtures for 2026-08-05.")
        await client.releaseNext(.failure(.providerUnavailable(message: "unavailable")))
        await refresh.value

        XCTAssertFalse(viewModel.isRefreshing)
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("a refresh failure must retain the usable fixture state")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_retained"])
        XCTAssertEqual(viewModel.lastLoadError, .providerUnavailable(message: "unavailable"))
    }

    func testAnInvalidRequestIsNotOfferedForRetry() async {
        let viewModel = model(.failure(.invalidRequest(message: "bad date")))
        await viewModel.load()

        guard case .failed(let error) = viewModel.state else {
            return XCTFail("expected failure")
        }
        XCTAssertFalse(error.isRetryable)
    }

    func testPreviewFixtureLookupReturnsTheMatchingFixtureAndMissingIDIs404() async throws {
        let client = PreviewFixtureClient()

        let fixture = try await client.fixture(id: "fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertEqual(fixture.id, "fx_aaaaaaaaaaaaaaaaaaaaaaaa")

        do {
            _ = try await client.fixture(id: "fx_unknown")
            XCTFail("expected a not-found error")
        } catch let error as APIError {
            XCTAssertEqual(error, .server(status: 404))
        }
    }

    // MARK: - Score privacy

    func testScoresStartHiddenAndAreNeverPersisted() async {
        let viewModel = model()
        await viewModel.load()

        XCTAssertFalse(viewModel.scoresRevealed)
        guard case .loaded(let data) = viewModel.state else { return XCTFail("expected loaded") }
        for fixture in data.fixtures {
            XCTAssertNil(viewModel.scoreText(for: fixture), "score leaked for \(fixture.id)")
        }

        // A fresh instance must start hidden again — no stored preference.
        let relaunched = model()
        await relaunched.load()
        XCTAssertFalse(relaunched.scoresRevealed)
    }

    func testRevealingScoresShowsOnlyStatusesThatHaveOne() async {
        let viewModel = model()
        await viewModel.load()
        viewModel.toggleScores()

        guard case .loaded(let data) = viewModel.state else { return XCTFail("expected loaded") }
        let live = try? XCTUnwrap(data.fixtures.first { $0.status == .inProgress })
        let halfTime = data.fixtures.first { $0.status == .halfTime }

        XCTAssertEqual(viewModel.scoreText(for: live!), "1 – 0")
        XCTAssertEqual(viewModel.scoreText(for: halfTime!), "2 – 2")
    }

    func testAScheduledFixtureNeverShowsAScoreEvenWhenRevealed() async {
        let json = """
        {"date":"2026-08-05","timezone":"UTC","matches":[
          {"canonicalFixtureId":"fx_dddddddddddddddddddddddd","status":{"code":"SCHEDULED"},
           "homeTeam":{"name":"A"},"awayTeam":{"name":"B"},
           "score":{"fullTime":{"home":9,"away":9}}}]}
        """
        let day = try! JSONDecoder().decode(FixtureDay.self, from: Data(json.utf8))
        let fixture = day.matches[0]
        let viewModel = model()
        viewModel.toggleScores()

        XCTAssertFalse(viewModel.canShowScore(for: fixture))
        XCTAssertNil(viewModel.scoreText(for: fixture))
    }

    // MARK: - Timezone

    func testTheSelectedTimezoneDrivesTheRequestedDay() async {
        let viewModel = FixtureListViewModel(
            client: PreviewFixtureClient(),
            timeZone: TimeZone(identifier: "Asia/Tokyo")!,
            day: nil,
            now: FixtureDateParser.date(from: "2026-08-05T00:30:00Z")!
        )
        // 00:30Z is already the 5th in Tokyo.
        XCTAssertEqual(viewModel.day, "2026-08-05")

        let newYork = FixtureListViewModel(
            client: PreviewFixtureClient(),
            timeZone: TimeZone(identifier: "America/New_York")!,
            day: nil,
            now: FixtureDateParser.date(from: "2026-08-05T00:30:00Z")!
        )
        // ...but still the 4th in New York.
        XCTAssertEqual(newYork.day, "2026-08-04")
    }

    func testShiftingDaysMovesTheRequestedDay() async {
        let viewModel = model()
        await viewModel.shiftDay(by: 1)
        XCTAssertEqual(viewModel.day, "2026-08-06")
        await viewModel.shiftDay(by: -2)
        XCTAssertEqual(viewModel.day, "2026-08-04")
    }

    // MARK: - Local query state

    func testAllFilterUsesDeterministicDefaultKickoffOrdering() async {
        let viewModel = model()
        await viewModel.load()

        XCTAssertEqual(viewModel.filter, FixtureFilter(status: .all, searchText: ""))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_cccccccccccccccccccccccc",
            "fx_aaaaaaaaaaaaaaaaaaaaaaaa",
            "fx_bbbbbbbbbbbbbbbbbbbbbbbb",
        ])
    }

    func testLiveFilterIncludesInProgressAndHalfTimeFixtures() async {
        let viewModel = model()
        await viewModel.load()
        viewModel.setStatusFilter(.live)

        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_aaaaaaaaaaaaaaaaaaaaaaaa",
            "fx_bbbbbbbbbbbbbbbbbbbbbbbb",
        ])
    }

    func testUpcomingFilterIncludesScheduledDelayedAndUnknownButExcludesActiveAndTerminalFixtures() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(matches: """
        [
          {"canonicalFixtureId":"fx_scheduled","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Scheduled"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_delayed","status":{"code":"DELAYED"},"homeTeam":{"name":"Delayed"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_unknown","status":{"code":"NEW_STATUS"},"homeTeam":{"name":"Unknown"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_live","status":{"code":"IN_PLAY"},"homeTeam":{"name":"Live"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_finished","status":{"code":"FINISHED"},"homeTeam":{"name":"Finished"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_postponed","status":{"code":"POSTPONED"},"homeTeam":{"name":"Postponed"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_cancelled","status":{"code":"CANCELLED"},"homeTeam":{"name":"Cancelled"},"awayTeam":{"name":"Team"}},
          {"canonicalFixtureId":"fx_abandoned","status":{"code":"ABANDONED"},"homeTeam":{"name":"Abandoned"},"awayTeam":{"name":"Team"}}
        ]
        """)))
        await load.value
        viewModel.setStatusFilter(.upcoming)

        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_delayed",
            "fx_scheduled",
            "fx_unknown",
        ])
    }

    func testFinishedFilterIncludesOnlyFinishedFixtures() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let load = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(matches: """
        [
          {"canonicalFixtureId":"fx_finished","status":{"code":"FINISHED"},
           "homeTeam":{"name":"Finished Home"},"awayTeam":{"name":"Finished Away"}}
        ]
        """)))
        await load.value

        viewModel.setStatusFilter(.finished)

        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_finished"])
    }

    func testSearchMatchesTeamCompetitionAndAreaCaseInsensitively() async {
        let viewModel = model()
        await viewModel.load()

        viewModel.setSearchText("cHeLsEa")
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_aaaaaaaaaaaaaaaaaaaaaaaa"])

        viewModel.setSearchText("laliga")
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_bbbbbbbbbbbbbbbbbbbbbbbb"])

        viewModel.setSearchText("NETHERLANDS")
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_cccccccccccccccccccccccc"])
    }

    // MARK: - Advanced local filters

    func testCompetitionAndCountryFiltersExposeOnlyKnownMetadataOptions() async throws {
        let (viewModel, _) = try await advancedModel()

        XCTAssertEqual(viewModel.availableCompetitionOptions, ["Alpha", "Beta"])
        XCTAssertEqual(viewModel.availableCountryOptions, ["England", "Spain"])

        viewModel.applyFilter(FixtureFilter(competition: "Alpha"))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_morning", "fx_evening"])

        viewModel.applyFilter(FixtureFilter(country: "Spain"))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_late", "fx_finished", "fx_afternoon"])
    }

    func testTimeWindowUsesTheSelectedTimezoneAndExcludesUnknownKickoff() async throws {
        let (viewModel, _) = try await advancedModel(
            timeZone: TimeZone(identifier: "America/New_York")!
        )

        viewModel.applyFilter(FixtureFilter(timeWindow: .morning, hideFinished: true))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_morning"])

        viewModel.applyFilter(FixtureFilter(timeWindow: .afternoon, hideFinished: true))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_afternoon"])

        viewModel.applyFilter(FixtureFilter(timeWindow: .evening, hideFinished: true))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_evening"])

        viewModel.applyFilter(FixtureFilter(timeWindow: .lateNight, hideFinished: true))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_late"])

        viewModel.applyFilter(FixtureFilter(timeWindow: .all))
        XCTAssertTrue(viewModel.filteredFixtures.contains { $0.id == "fx_no_kickoff" })
    }

    func testSortModesAreDeterministicAndRecommendedUsesInterestOnly() async throws {
        let (viewModel, _) = try await advancedModel()

        viewModel.applyFilter(FixtureFilter(sort: .kickoff))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_late", "fx_morning", "fx_finished", "fx_afternoon", "fx_evening", "fx_no_kickoff",
        ])

        viewModel.applyFilter(FixtureFilter(sort: .competition))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_morning", "fx_evening", "fx_late", "fx_finished", "fx_afternoon", "fx_no_kickoff",
        ])

        viewModel.applyFilter(FixtureFilter(sort: .liveFirst))
        XCTAssertEqual(Array(viewModel.filteredFixtures.map(\.id).prefix(1)), ["fx_evening"])

        viewModel.applyFilter(FixtureFilter(sort: .recommended))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), [
            "fx_afternoon", "fx_evening", "fx_late", "fx_morning", "fx_finished", "fx_no_kickoff",
        ])
    }

    func testHideFinishedIsLocalAndDoesNotInspectOrRevealScores() async throws {
        let (viewModel, client) = try await advancedModel()
        let requestCountBeforeApply = await client.requestCount()

        viewModel.applyFilter(FixtureFilter(hideFinished: true))

        let requestCountAfterApply = await client.requestCount()
        XCTAssertEqual(requestCountAfterApply, requestCountBeforeApply)
        XCTAssertFalse(viewModel.filteredFixtures.contains { $0.id == "fx_finished" })
        XCTAssertTrue(viewModel.filteredFixtures.contains { $0.id == "fx_evening" })
        XCTAssertNil(viewModel.scoreText(for: viewModel.filteredFixtures[0]))
    }

    func testActiveFilterCountAndDraftResetPreserveVisibleStatusAndSearch() async throws {
        let (viewModel, client) = try await advancedModel()
        viewModel.setStatusFilter(.live)
        viewModel.setSearchText("Alpha")
        viewModel.applyFilter(FixtureFilter(
            status: .live,
            searchText: "Alpha",
            competition: "Alpha",
            country: "England",
            timeWindow: .evening,
            sort: .recommended,
            hideFinished: true
        ))

        XCTAssertEqual(viewModel.activeFilterCount, 7)
        let requestCount = await client.requestCount()
        XCTAssertEqual(requestCount, 1)

        viewModel.resetAdvancedFilter()

        XCTAssertEqual(viewModel.filter.status, .live)
        XCTAssertEqual(viewModel.filter.searchText, "Alpha")
        XCTAssertNil(viewModel.filter.competition)
        XCTAssertNil(viewModel.filter.country)
        XCTAssertEqual(viewModel.filter.timeWindow, .all)
        XCTAssertEqual(viewModel.filter.sort, .kickoff)
        XCTAssertFalse(viewModel.filter.hideFinished)
        XCTAssertEqual(viewModel.activeFilterCount, 2)
    }

    func testFilteredEmptyDoesNotReplaceANonemptySourceDay() async {
        let viewModel = model()
        await viewModel.load()
        viewModel.setSearchText("no matching club")

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("expected source day to remain loaded")
        }
        XCTAssertEqual(data.fixtures.count, 3)
        XCTAssertTrue(viewModel.filteredFixtures.isEmpty)
    }

    func testAdvancedFilteredEmptyRemainsDistinctFromEmptySourceDay() async throws {
        let (viewModel, _) = try await advancedModel()
        viewModel.applyFilter(FixtureFilter(competition: "Not a real competition"))

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("expected source day to remain loaded")
        }
        XCTAssertFalse(data.fixtures.isEmpty)
        XCTAssertTrue(viewModel.filteredFixtures.isEmpty)
    }

    func testLoadedDayClearsCompetitionAndCountrySelectionsAbsentFromNewMetadata() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(matches: """
        [{"canonicalFixtureId":"fx_alpha","utcDate":"2026-08-05T12:00:00Z",
          "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Alpha"},"awayTeam":{"name":"Fixture"},
          "competition":{"name":"Alpha League","area":{"name":"England"}}}]
        """)))
        await initialLoad.value

        viewModel.applyFilter(FixtureFilter(competition: "Alpha League", country: "England"))
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_alpha"])

        let nextDayLoad = Task { await viewModel.selectDay("2026-08-06") }
        await client.waitForRequestCount(2)
        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-06",
            matches: """
            [{"canonicalFixtureId":"fx_gamma","utcDate":"2026-08-06T12:00:00Z",
              "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Gamma"},"awayTeam":{"name":"Fixture"},
              "competition":{"name":"Gamma League","area":{"name":"France"}}}]
            """
        )))
        await nextDayLoad.value

        XCTAssertNil(viewModel.filter.competition)
        XCTAssertNil(viewModel.filter.country)
        XCTAssertEqual(viewModel.availableCompetitionOptions, ["Gamma League"])
        XCTAssertEqual(viewModel.availableCountryOptions, ["France"])
        XCTAssertEqual(viewModel.filteredFixtures.map(\.id), ["fx_gamma"])
    }

    func testDelayedOlderResponseCannotReplaceNewerDay() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-04"
        )
        let oldLoad = Task { await viewModel.selectDay("2026-08-04") }
        await client.waitForRequestCount(1)

        let newLoad = Task { await viewModel.selectDay("2026-08-05") }
        await client.waitForRequestCount(2)

        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-04",
            matches: #"[{"canonicalFixtureId":"fx_old","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Old"},"awayTeam":{"name":"Day"}}]"#
        )))
        await Task.yield()
        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-05",
            matches: #"[{"canonicalFixtureId":"fx_new","status":{"code":"SCHEDULED"},"homeTeam":{"name":"New"},"awayTeam":{"name":"Day"}}]"#
        )))
        await oldLoad.value
        await newLoad.value

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("expected newest loaded state, got \(viewModel.state)")
        }
        XCTAssertEqual(data.day, "2026-08-05")
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_new"])
    }

    func testChangingTimezoneKeepsTheSelectedDayAndRequestsTheNewZone() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )

        viewModel.applyFilter(FixtureFilter(competition: "Old League", country: "England"))
        viewModel.selectedTimeZone = try XCTUnwrap(TimeZone(identifier: "America/New_York"))
        await client.waitForRequestCount(1)

        XCTAssertEqual(viewModel.day, "2026-08-05")
        let request = await client.lastRequest()
        XCTAssertEqual(request?.date, "2026-08-05")
        XCTAssertEqual(request?.timeZoneIdentifier, "America/New_York")

        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-05",
            matches: """
            [{"canonicalFixtureId":"fx_new_zone","utcDate":"2026-08-05T12:00:00Z",
              "status":{"code":"SCHEDULED"},"homeTeam":{"name":"New"},"awayTeam":{"name":"Zone"},
              "competition":{"name":"New League","area":{"name":"France"}}}]
            """
        )))
        for _ in 0..<5 { await Task.yield() }

        XCTAssertNil(viewModel.filter.competition)
        XCTAssertNil(viewModel.filter.country)
        XCTAssertEqual(viewModel.availableCompetitionOptions, ["New League"])
        XCTAssertEqual(viewModel.availableCountryOptions, ["France"])
    }

    func testOpenFixtureLoadsItsCalendarDayAndReturnsTheLookup() async {
        let viewModel = FixtureListViewModel(
            client: PreviewFixtureClient(),
            timeZone: TimeZone(identifier: "America/New_York")!,
            day: "2026-08-01"
        )

        let fixture = await viewModel.openFixture(id: "fx_aaaaaaaaaaaaaaaaaaaaaaaa")

        XCTAssertEqual(fixture?.id, "fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertEqual(viewModel.day, "2026-08-05")
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("expected route fixture day to load")
        }
        XCTAssertEqual(data.day, "2026-08-05")
    }

    func testOpenFixtureNotFoundDoesNotReplaceLoadedDataWithAnError() async {
        let viewModel = model()
        await viewModel.load()

        let fixture = await viewModel.openFixture(id: "fx_missing")

        XCTAssertNil(fixture)
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("not found should retain the current loaded state")
        }
        XCTAssertEqual(data.fixtures.count, 3)
    }

    func testWarmRouteAppliesItsTimezoneAndFixtureDayAfterTheListIsLoaded() async {
        let viewModel = model()
        await viewModel.load()

        let outcome = await viewModel.openRouteFixture(
            id: "fx_aaaaaaaaaaaaaaaaaaaaaaaa",
            timeZoneIdentifier: "Asia/Tokyo",
            calendarDay: "2026-08-03",
            isCurrentRoute: { true }
        )

        guard case .found(let fixture) = outcome else {
            return XCTFail("expected a route fixture, got \(outcome)")
        }
        XCTAssertEqual(fixture.id, "fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertEqual(viewModel.selectedTimeZone.identifier, "Asia/Tokyo")
        XCTAssertEqual(viewModel.day, "2026-08-03")
    }

    func testSupersededRouteCannotMutateTheActiveListDayOrTimezone() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            matches: #"[{"canonicalFixtureId":"fx_initial","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Initial"},"awayTeam":{"name":"Day"}}]"#
        )))
        await initialLoad.value

        let router = AppRouter()
        let firstID = "fx_" + String(repeating: "a", count: 24)
        let secondID = "fx_" + String(repeating: "b", count: 24)
        let firstRoute = AppRoute.fixture(
            id: firstID,
            timeZoneIdentifier: "Asia/Tokyo",
            calendarDay: nil
        )
        router.handle(URL(string: "https://soccerscanner.pro/fixtures/\(firstID)?timezone=Asia/Tokyo")!)

        let firstLookup = Task {
            await viewModel.openRouteFixture(
                id: firstID,
                timeZoneIdentifier: "Asia/Tokyo",
                calendarDay: nil,
                isCurrentRoute: { router.route == firstRoute }
            )
        }
        await client.waitForLookupCount(1)
        await client.releaseLookupNext(.success(try routeFixture()))
        await client.waitForRequestCount(2)
        router.handle(URL(string: "https://soccerscanner.pro/fixtures/\(secondID)")!)
        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-06",
            matches: #"[{"canonicalFixtureId":"fx_route_day","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Route"},"awayTeam":{"name":"Day"}}]"#
        )))

        let outcome = await firstLookup.value
        guard case .superseded = outcome else {
            return XCTFail("expected superseded route, got \(outcome)")
        }
        XCTAssertFalse(viewModel.isRefreshing)
        XCTAssertEqual(
            router.route,
            .fixture(id: secondID, timeZoneIdentifier: nil, calendarDay: nil)
        )
        XCTAssertEqual(viewModel.selectedTimeZone.identifier, TimeZone(identifier: "UTC")!.identifier)
        XCTAssertEqual(viewModel.day, "2026-08-05")
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("stale route changed the active list state")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_initial"])
    }

    func testRouteLookupFailureRemainsTypedInsteadOfMissing() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            matches: #"[{"canonicalFixtureId":"fx_loaded","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Loaded"},"awayTeam":{"name":"Fixture"}}]"#
        )))
        await initialLoad.value
        let lookup = Task {
            await viewModel.openRouteFixture(
                id: "fx_failure",
                timeZoneIdentifier: nil,
                calendarDay: nil,
                isCurrentRoute: { true }
            )
        }
        await client.waitForLookupCount(1)
        await client.releaseLookupNext(.failure(.providerUnavailable(message: "unavailable")))

        let outcome = await lookup.value
        guard case .failed(let error) = outcome else {
            return XCTFail("expected typed route failure, got \(outcome)")
        }
        XCTAssertEqual(error, .providerUnavailable(message: "unavailable"))
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("route failure should retain usable fixtures")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_loaded"])
    }

    func testCancelledRouteLookupIsSupersededAndRetainsLoadedData() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            matches: #"[{"canonicalFixtureId":"fx_loaded","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Loaded"},"awayTeam":{"name":"Fixture"}}]"#
        )))
        await initialLoad.value

        let lookup = Task {
            await viewModel.openRouteFixture(
                id: "fx_cancelled",
                timeZoneIdentifier: nil,
                calendarDay: nil,
                isCurrentRoute: { true }
            )
        }
        await client.waitForLookupCount(1)
        await client.releaseLookupNext(.failure(.cancelled))

        let outcome = await lookup.value
        guard case .superseded = outcome else {
            return XCTFail("cancelled route lookup must be non-presenting, got \(outcome)")
        }
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("cancelled route lookup should retain usable fixtures")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_loaded"])
    }

    func testCancelledRouteDayLoadIsSupersededAndRetainsLoadedData() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-05"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            matches: #"[{"canonicalFixtureId":"fx_loaded","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Loaded"},"awayTeam":{"name":"Fixture"}}]"#
        )))
        await initialLoad.value

        let routeResolution = Task {
            await viewModel.openRouteFixture(
                id: "fx_route",
                timeZoneIdentifier: nil,
                calendarDay: nil,
                isCurrentRoute: { true }
            )
        }
        await client.waitForLookupCount(1)
        await client.releaseLookupNext(.success(try routeFixture()))
        await client.waitForRequestCount(2)
        await client.releaseNext(.failure(.cancelled))

        let outcome = await routeResolution.value
        guard case .superseded = outcome else {
            return XCTFail("cancelled route-day load must be superseded, got \(outcome)")
        }
        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("cancelled route-day load should retain usable fixtures")
        }
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_loaded"])
    }

    func testOlderRouteLookupFailureCannotReplaceNewerLoadedDay() async throws {
        let client = DelayedFixtureClient()
        let viewModel = FixtureListViewModel(
            client: client,
            timeZone: TimeZone(identifier: "UTC")!,
            day: "2026-08-04"
        )
        let initialLoad = Task { await viewModel.load() }
        await client.waitForRequestCount(1)
        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-04",
            matches: #"[{"canonicalFixtureId":"fx_initial","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Initial"},"awayTeam":{"name":"Day"}}]"#
        )))
        await initialLoad.value

        let routeLookup = Task { await viewModel.openFixture(id: "fx_route") }
        await client.waitForLookupCount(1)

        let newerLoad = Task { await viewModel.selectDay("2026-08-05") }
        await client.waitForRequestCount(2)
        await client.releaseNext(.success(try fixtureDay(
            date: "2026-08-05",
            matches: #"[{"canonicalFixtureId":"fx_newer","status":{"code":"SCHEDULED"},"homeTeam":{"name":"Newer"},"awayTeam":{"name":"Day"}}]"#
        )))
        await newerLoad.value
        await client.releaseLookupNext(.failure(.providerUnavailable(message: "unavailable")))
        _ = await routeLookup.value

        guard case .loaded(let data) = viewModel.state else {
            return XCTFail("an old route lookup failure replaced the newer state")
        }
        XCTAssertEqual(data.day, "2026-08-05")
        XCTAssertEqual(data.fixtures.map(\.id), ["fx_newer"])
    }
}

private actor DelayedFixtureClient: FixtureFetching {
    struct Request: Equatable, Sendable {
        let date: String
        let timeZoneIdentifier: String
    }

    private var pendingResponses: [CheckedContinuation<FixtureDay, Error>] = []
    private var requestWaiters: [(Int, CheckedContinuation<Void, Never>)] = []
    private(set) var requests: [Request] = []
    private var pendingLookups: [CheckedContinuation<Fixture, Error>] = []
    private var lookupWaiters: [(Int, CheckedContinuation<Void, Never>)] = []
    private var lookupIDs: [String] = []

    func fixtures(date: String, timeZone: TimeZone) async throws -> FixtureDay {
        requests.append(Request(date: date, timeZoneIdentifier: timeZone.identifier))
        releaseRequestWaiters()
        return try await withCheckedThrowingContinuation { continuation in
            pendingResponses.append(continuation)
        }
    }

    func fixture(id: String) async throws -> Fixture {
        lookupIDs.append(id)
        releaseLookupWaiters()
        return try await withCheckedThrowingContinuation { continuation in
            pendingLookups.append(continuation)
        }
    }

    func teamAnalysis(canonicalId: String) async throws -> TeamAnalysis {
        throw APIError.server(status: 500)
    }

    func appConfig() async throws -> AppConfig {
        fatalError("not used by fixture list tests")
    }

    func waitForRequestCount(_ count: Int) async {
        guard requests.count < count else { return }
        await withCheckedContinuation { continuation in
            requestWaiters.append((count, continuation))
        }
    }

    func releaseNext(_ result: Result<FixtureDay, APIError>) {
        guard !pendingResponses.isEmpty else {
            fatalError("test attempted to release a response before the request was pending")
        }
        let continuation = pendingResponses.removeFirst()
        switch result {
        case .success(let day):
            continuation.resume(returning: day)
        case .failure(let error):
            continuation.resume(throwing: error)
        }
    }

    func lastRequest() -> Request? { requests.last }

    func requestCount() -> Int { requests.count }

    func waitForLookupCount(_ count: Int) async {
        guard lookupIDs.count < count else { return }
        await withCheckedContinuation { continuation in
            lookupWaiters.append((count, continuation))
        }
    }

    func releaseLookupNext(_ result: Result<Fixture, APIError>) {
        guard !pendingLookups.isEmpty else {
            fatalError("test attempted to release a lookup before it was pending")
        }
        let continuation = pendingLookups.removeFirst()
        switch result {
        case .success(let fixture):
            continuation.resume(returning: fixture)
        case .failure(let error):
            continuation.resume(throwing: error)
        }
    }

    private func releaseRequestWaiters() {
        let ready = requestWaiters.filter { $0.0 <= requests.count }
        requestWaiters.removeAll { $0.0 <= requests.count }
        ready.forEach { $0.1.resume() }
    }

    private func releaseLookupWaiters() {
        let ready = lookupWaiters.filter { $0.0 <= lookupIDs.count }
        lookupWaiters.removeAll { $0.0 <= lookupIDs.count }
        ready.forEach { $0.1.resume() }
    }
}

@MainActor
private func advancedModel(
    timeZone: TimeZone = TimeZone(identifier: "UTC")!
) async throws -> (viewModel: FixtureListViewModel, client: DelayedFixtureClient) {
    let client = DelayedFixtureClient()
    let viewModel = FixtureListViewModel(
        client: client,
        timeZone: timeZone,
        day: "2026-08-05"
    )
    let load = Task { await viewModel.load() }
    await client.waitForRequestCount(1)
    await client.releaseNext(.success(try fixtureDay(matches: """
    [
      {"canonicalFixtureId":"fx_morning","utcDate":"2026-08-05T10:00:00Z",
       "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Morning"},"awayTeam":{"name":"Fixture"},
       "competition":{"name":"Alpha","area":{"name":"England"}},"interestEstimate":0.1},
      {"canonicalFixtureId":"fx_afternoon","utcDate":"2026-08-05T16:00:00Z",
       "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Afternoon"},"awayTeam":{"name":"Fixture"},
       "competition":{"name":"Beta","area":{"name":"Spain"}},
       "score":{"fullTime":{"home":99,"away":0}},"interestEstimate":0.9},
      {"canonicalFixtureId":"fx_evening","utcDate":"2026-08-05T22:00:00Z",
       "status":{"code":"IN_PLAY"},"homeTeam":{"name":"Evening"},"awayTeam":{"name":"Fixture"},
       "competition":{"name":"Alpha","area":{"name":"England"}},
       "score":{"fullTime":{"home":0,"away":99}},"interestEstimate":0.5},
      {"canonicalFixtureId":"fx_late","utcDate":"2026-08-05T08:00:00Z",
       "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Late"},"awayTeam":{"name":"Fixture"},
       "competition":{"name":"Beta","area":{"name":"Spain"}},"interestEstimate":0.2},
      {"canonicalFixtureId":"fx_finished","utcDate":"2026-08-05T12:00:00Z",
       "status":{"code":"FINISHED"},"homeTeam":{"name":"Finished"},"awayTeam":{"name":"Fixture"},
       "competition":{"name":"Beta","area":{"name":"Spain"}},"interestEstimate":0.05},
      {"canonicalFixtureId":"fx_no_kickoff","status":{"code":"SCHEDULED"},
       "homeTeam":{"name":"Unknown"},"awayTeam":{"name":"Fixture"}}
    ]
    """)))
    await load.value
    return (viewModel, client)
}

private func fixtureDay(
    date: String = "2026-08-05",
    state: String = "success",
    providers: String = "{\"espn\":{\"status\":\"success\"}}",
    matches: String = "[]"
) throws -> FixtureDay {
    try JSONDecoder().decode(FixtureDay.self, from: Data("""
    {"date":"\(date)","timezone":"UTC","state":"\(state)",
     "providers":\(providers),"matches":\(matches)}
    """.utf8))
}

private func routeFixture() throws -> Fixture {
    try JSONDecoder().decode(Fixture.self, from: Data("""
    {"canonicalFixtureId":"fx_route","utcDate":"2026-08-05T19:00:00Z",
     "status":{"code":"SCHEDULED"},"homeTeam":{"name":"Route"},"awayTeam":{"name":"Fixture"}}
    """.utf8))
}
