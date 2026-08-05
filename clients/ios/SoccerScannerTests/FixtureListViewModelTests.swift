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
        XCTAssertEqual(data.timeZoneIdentifier, "UTC")
    }

    func testAPartialDayIsNotPresentedAsComplete() async {
        let viewModel = model(.partial)
        await viewModel.load()

        guard case .partial(_, let reason) = viewModel.state else {
            return XCTFail("expected partial, got \(viewModel.state)")
        }
        XCTAssertFalse(reason.isEmpty)
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

    func testAnInvalidRequestIsNotOfferedForRetry() async {
        let viewModel = model(.failure(.invalidRequest(message: "bad date")))
        await viewModel.load()

        guard case .failed(let error) = viewModel.state else {
            return XCTFail("expected failure")
        }
        XCTAssertFalse(error.isRetryable)
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
}
