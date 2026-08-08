import Foundation
import XCTest

/// UI coverage for the vertical slice.
///
/// The app is launched with a stub-data flag so these never depend on the
/// network or on which fixtures happen to be scheduled today.
@MainActor
final class FixtureFlowUITests: XCTestCase {
    private func launchApp(
        arguments: [String] = [],
        environment: String = "development"
    ) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = [
            "-UITestStubData", "YES",
            "-AppleLanguages", "(en)",
            "-AppleLocale", "en_US",
        ] + arguments
        let mode: String
        if arguments.contains("-UITestFailure") {
            mode = "ui-test-failure"
        } else if arguments.contains("-UITestTeamFailure") {
            mode = "ui-test-team-failure"
        } else if arguments.contains("-UITestPartial") {
            mode = "ui-test-partial"
        } else if arguments.contains("-UITestStale") {
            mode = "ui-test-stale"
        } else if arguments.contains("-UITestEmpty") {
            mode = "ui-test-empty"
        } else if arguments.contains("-UITestAccessibilityFixtures") {
            mode = "ui-test-accessibility"
        } else if environment == "production" {
            mode = "ui-test-production"
        } else {
            mode = "ui-test"
        }
        app.launchEnvironment = ["SOCCER_SCANNER_UI_TEST_MODE": mode]
        app.terminate()
        app.launch()
        return app
    }

    /// Query by identifier without asserting an element type.
    ///
    /// SwiftUI does not guarantee which UIKit element a `List`, row or
    /// `ContentUnavailableView` becomes, and it changes between releases.
    /// Matching on identifier alone keeps these tests about behaviour.
    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        let identified = app.descendants(matching: .any).matching(identifier: identifier).firstMatch
        guard !identified.exists else { return identified }

        if identifier.hasPrefix("fixture-row-") {
            let fixtureLabels: [String: String] = [
                "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa": "Arsenal",
                "fixture-row-fx_bbbbbbbbbbbbbbbbbbbbbbbb": "Real Madrid",
                "fixture-row-fx_cccccccccccccccccccccccc": "Ajax",
                "fixture-row-fx_0123456789abcdef01234567": "Association Sportive",
            ]
            if let label = fixtureLabels[identifier] {
                return app.buttons.matching(
                    NSPredicate(format: "label CONTAINS %@", label)
                ).firstMatch
            }
        }

        switch identifier {
        case "advanced-filter-reset": return app.buttons["Reset"]
        case "advanced-filter-close": return app.buttons["Close"]
        case "advanced-filter-apply": return app.buttons["Apply"]
        case "advanced-competition": return app.buttons["Competition"]
        case "settings-privacy-link": return app.links["Privacy"]
        case "settings-terms-link": return app.links["Terms of Service"]
        case "settings-support-unavailable":
            return app.staticTexts["Support contact is not configured for this build."]
        default:
            if identifier.hasPrefix("timezone-") {
                return app.buttons[String(identifier.dropFirst("timezone-".count))]
            }
            return identified
        }
    }

    private func waitForList(_ app: XCUIApplication) {
        XCTAssertTrue(
            element(app, "fixtures-list").waitForExistence(timeout: 30),
            "fixture list never appeared"
        )
    }

    private func waitForElement(
        _ app: XCUIApplication,
        _ identifier: String,
        timeout: TimeInterval = 10
    ) -> XCUIElement {
        let target = element(app, identifier)
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if target.exists { return target }
            app.swipeUp()
        }
        return target
    }

    private func waitForHittable(
        _ app: XCUIApplication,
        _ identifier: String,
        timeout: TimeInterval = 10
    ) -> XCUIElement {
        let target = element(app, identifier)
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if target.isHittable { return target }
            let list = app.tables.firstMatch
            let scrollView = app.scrollViews.firstMatch
            if list.exists {
                list.swipeUp()
            } else if scrollView.exists {
                scrollView.swipeUp()
            } else {
                app.swipeUp()
            }
        }
        return target
    }

    private func tapFixture(_ app: XCUIApplication, id: String) {
        let target = waitForHittable(app, id)
        XCTAssertTrue(target.isHittable, "fixture row did not become tappable")
        target.tap()
    }

    private func selectedDay(_ app: XCUIApplication) -> String {
        let day = element(app, "selected-day")
        XCTAssertTrue(day.waitForExistence(timeout: 10), "selected day did not appear")
        return day.value as? String ?? ""
    }

    private func waitForValue(_ element: XCUIElement, toEqual expected: String) {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "value == %@", expected),
            object: element
        )
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: 10), .completed)
    }

    private func nextDay(after isoDay: String) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "yyyy-MM-dd"
        let date = try! XCTUnwrap(formatter.date(from: isoDay))
        let next = Calendar(identifier: .gregorian).date(byAdding: .day, value: 1, to: date)!
        return formatter.string(from: next)
    }

    private func calendarButtonLabel(for isoDay: String) -> String {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        parser.dateFormat = "yyyy-MM-dd"
        let date = try! XCTUnwrap(parser.date(from: isoDay))

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: date)
    }

    private func scrollToElement(_ target: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<8 {
            if target.isHittable {
                return
            }
            app.swipeUp()
        }
        XCTAssertTrue(target.isHittable, "target did not become visible after scrolling")
    }

    func testFixtureListLoadsAndExposesNativeDayAndTimezoneControls() {
        let app = launchApp()
        waitForList(app)

        XCTAssertTrue(element(app, "previous-day").isHittable)
        XCTAssertTrue(element(app, "today-day").isHittable)
        XCTAssertTrue(element(app, "next-day").isHittable)
        XCTAssertTrue(element(app, "date-picker").exists)
        XCTAssertTrue(element(app, "timezone-menu").isHittable)

        let initialDay = selectedDay(app)
        XCTAssertEqual(element(app, "date-picker").value as? String, initialDay)

        let datePicker = app.datePickers["date-picker"]
        let pickerTargetDay = nextDay(after: initialDay)
        datePicker.tap()
        let targetDay = app.buttons[calendarButtonLabel(for: pickerTargetDay)]
        XCTAssertTrue(targetDay.waitForExistence(timeout: 10))
        targetDay.tap()
        datePicker.tap()
        waitForValue(element(app, "selected-day"), toEqual: pickerTargetDay)
        XCTAssertEqual(datePicker.value as? String, pickerTargetDay)

        element(app, "previous-day").tap()
        let previousDay = selectedDay(app)
        XCTAssertNotEqual(previousDay, pickerTargetDay)
        XCTAssertEqual(element(app, "date-picker").value as? String, previousDay)

        element(app, "today-day").tap()
        waitForValue(element(app, "selected-day"), toEqual: initialDay)

        element(app, "next-day").tap()
        let nextDay = selectedDay(app)
        XCTAssertNotEqual(nextDay, initialDay)
        XCTAssertEqual(element(app, "date-picker").value as? String, nextDay)
    }

    func testTimezoneMenuOffersCommonZones() {
        let app = launchApp()
        waitForList(app)

        let timeZoneMenu = element(app, "timezone-menu")
        timeZoneMenu.tap()
        let deviceTimeZone = element(app, "timezone-device")
        XCTAssertTrue(deviceTimeZone.waitForExistence(timeout: 10))
        deviceTimeZone.tap()

        for identifier in [
            "UTC",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Australia/Sydney",
        ] {
            timeZoneMenu.tap()
            let option = element(app, "timezone-\(identifier)")
            XCTAssertTrue(option.waitForExistence(timeout: 10))
            option.tap()
            waitForValue(timeZoneMenu, toEqual: identifier)
        }
    }

    func testStatusFiltersProjectDeterministicFixtureRowsAndSearchShowsFilteredEmptyState() {
        let app = launchApp()
        waitForList(app)

        XCTAssertTrue(element(app, "status-filter").exists)
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa").exists)
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_bbbbbbbbbbbbbbbbbbbbbbbb").exists)
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)
        app.swipeDown()

        app.buttons["Live"].tap()
        XCTAssertTrue(element(app, "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "fixture-row-fx_bbbbbbbbbbbbbbbbbbbbbbbb").exists)
        XCTAssertFalse(element(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)

        app.buttons["Upcoming"].tap()
        XCTAssertTrue(element(app, "fixtures-filtered-empty").waitForExistence(timeout: 10))

        app.buttons["Finished"].tap()
        XCTAssertTrue(element(app, "fixtures-filtered-empty").waitForExistence(timeout: 10))

        app.buttons["All"].tap()
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)

        XCTAssertTrue(element(app, "fixture-search").waitForExistence(timeout: 10))
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("No matching club")

        XCTAssertTrue(element(app, "fixtures-filtered-empty").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "fixtures-empty").exists)
    }

    func testAdvancedFilterSheetKeepsDraftChangesUntilApplyAndSupportsReset() {
        let app = launchApp()
        waitForList(app)

        XCTAssertEqual(element(app, "advanced-filter-count").label, "0")
        waitForHittable(app, "advanced-filter-button").tap()

        XCTAssertTrue(element(app, "advanced-filter-sheet").waitForExistence(timeout: 10))
        XCTAssertTrue(waitForHittable(app, "advanced-filter-reset").isHittable)
        XCTAssertTrue(waitForHittable(app, "advanced-filter-close").isHittable)
        XCTAssertTrue(waitForHittable(app, "advanced-filter-apply").isHittable)

        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons["Premier League"].waitForExistence(timeout: 10))
        app.buttons["Premier League"].tap()
        waitForHittable(app, "advanced-filter-close").tap()

        // Close is cancel: the applied badge and rows remain unchanged.
        XCTAssertEqual(element(app, "advanced-filter-count").label, "0")
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)

        waitForHittable(app, "advanced-filter-button").tap()
        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons["Premier League"].waitForExistence(timeout: 10))
        app.buttons["Premier League"].tap()
        waitForHittable(app, "advanced-filter-reset").tap()
        waitForHittable(app, "advanced-filter-apply").tap()

        XCTAssertEqual(element(app, "advanced-filter-count").label, "0")
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)

        waitForHittable(app, "advanced-filter-button").tap()
        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons["Premier League"].waitForExistence(timeout: 10))
        app.buttons["Premier League"].tap()
        waitForHittable(app, "advanced-filter-apply").tap()

        XCTAssertEqual(element(app, "advanced-filter-count").label, "1")
        XCTAssertTrue(element(app, "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa").exists)
        XCTAssertFalse(element(app, "fixture-row-fx_cccccccccccccccccccccccc").exists)
    }

    func testScoresStartHiddenAndToggleOn() {
        let app = launchApp()
        waitForList(app)

        // Spoiler-safe by default.
        XCTAssertTrue(element(app, "fixture-score-hidden").exists)
        XCTAssertFalse(element(app, "fixture-score").exists)

        element(app, "score-toggle").tap()

        XCTAssertTrue(element(app, "fixture-score").waitForExistence(timeout: 10))

        element(app, "score-toggle").tap()

        XCTAssertTrue(element(app, "fixture-score-hidden").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "fixture-score").exists)
    }

    func testOpeningAFixtureShowsDetail() {
        let app = launchApp()
        waitForList(app)

        tapFixture(app, id: "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa")

        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
    }

    func testFixtureDetailShowsAllProviderBroadcastEntriesAndRegions() {
        let app = launchApp()
        waitForList(app)

        tapFixture(app, id: "fixture-row-fx_bbbbbbbbbbbbbbbbbbbbbbbb")
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["National Sports"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["GB"].exists)
        XCTAssertTrue(app.staticTexts["Broadcast"].exists)
        XCTAssertTrue(app.staticTexts["Availability varies by region and subscription. Listings may be incomplete or out of date."].exists)
    }

    func testFixtureDetailCanRevealAndHideItsScore() {
        let app = launchApp()
        waitForList(app)

        tapFixture(app, id: "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "detail-score-hidden").exists)
        XCTAssertFalse(element(app, "detail-score").exists)

        let scoreToggle = element(app, "detail-score-toggle")
        XCTAssertTrue(scoreToggle.waitForExistence(timeout: 10))
        scoreToggle.tap()
        XCTAssertTrue(element(app, "detail-score").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "detail-score-hidden").exists)

        scoreToggle.tap()
        XCTAssertTrue(element(app, "detail-score-hidden").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "detail-score").exists)
    }

    func testFixtureDetailOpensTeamIntelligenceWithoutRevealingScore() {
        let app = launchApp()
        waitForList(app)

        tapFixture(app, id: "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "detail-score-hidden").exists)
        XCTAssertFalse(element(app, "detail-score").exists)

        let teamButton = element(app, "team-intelligence-home-arsenal")
        XCTAssertTrue(teamButton.waitForExistence(timeout: 10))
        teamButton.tap()

        XCTAssertTrue(element(app, "team-intelligence-view").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "team-intelligence-identity").exists)
        XCTAssertTrue(element(app, "team-intelligence-stats").exists)
        XCTAssertTrue(app.staticTexts["Arsenal"].exists)
        XCTAssertTrue(app.staticTexts["Wins"].exists)
        XCTAssertFalse(element(app, "detail-score").exists)
    }

    func testTeamIntelligenceShowsGenericRetryableFailure() {
        let app = launchApp(arguments: ["-UITestTeamFailure", "YES"])
        waitForList(app)

        tapFixture(app, id: "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa")
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
        element(app, "team-intelligence-home-arsenal").tap()

        XCTAssertTrue(element(app, "team-intelligence-unavailable").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "team-intelligence-retry").exists)
        XCTAssertTrue(app.staticTexts["Verified team data is temporarily unavailable."].exists)
        XCTAssertFalse(app.staticTexts["Fixture provider request failed"].exists)

        element(app, "team-intelligence-retry").tap()
        XCTAssertTrue(element(app, "team-intelligence-unavailable").waitForExistence(timeout: 10))
    }

    func testSettingsExposeLegalLinksAndSpoilerExplanationWithoutScores() {
        let app = launchApp()
        waitForList(app)

        waitForHittable(app, "settings-link").tap()

        XCTAssertTrue(element(app, "settings-view").waitForExistence(timeout: 10))
        XCTAssertTrue(waitForElement(app, "settings-privacy-link").exists)
        XCTAssertTrue(waitForElement(app, "settings-terms-link").exists)
        let scoreExplanation = waitForElement(app, "settings-score-explanation")
        XCTAssertTrue(scoreExplanation.exists)
        XCTAssertEqual(
            scoreExplanation.label,
            "Scores stay hidden until you choose Reveal scores on the fixture list."
        )
        XCTAssertFalse(element(app, "fixture-score").exists)
        XCTAssertFalse(element(app, "detail-score").exists)
        XCTAssertTrue(waitForElement(app, "settings-support-unavailable").exists)
        XCTAssertTrue(app.staticTexts["Support contact is not configured for this build."].exists)
    }

    func testSettingsHideEnvironmentLabelInProduction() {
        let app = launchApp(environment: "production")
        waitForList(app)

        waitForHittable(app, "settings-link").tap()

        XCTAssertTrue(element(app, "settings-view").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "settings-environment").exists)
    }

    func testFixtureLinkAtLaunchOpensTheFixtureWithoutRevealingItsScore() {
        let app = launchApp(arguments: [
            "-UITestDeepLink", "https://soccerscanner.pro/fixtures/fx_aaaaaaaaaaaaaaaaaaaaaaaa?timezone=Asia/Tokyo&date=2026-08-05",
        ])

        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 30))
        XCTAssertTrue(element(app, "detail-score-hidden").exists)
        XCTAssertFalse(element(app, "detail-score").exists)
        XCTAssertTrue(app.staticTexts["Asia/Tokyo"].exists)

        app.navigationBars.buttons.firstMatch.tap()
        waitForValue(element(app, "selected-day"), toEqual: "2026-08-05")
    }

    func testWarmFixtureLinkNavigatesWithoutRevealingItsScore() {
        let app = launchApp()
        waitForList(app)

        app.open(URL(string: "https://soccerscanner.pro/fixtures/fx_bbbbbbbbbbbbbbbbbbbbbbbb?timezone=Europe/London&date=2026-08-05")!)

        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 30))
        XCTAssertTrue(element(app, "detail-score-hidden").exists)
        XCTAssertFalse(element(app, "detail-score").exists)
        XCTAssertTrue(app.staticTexts["Europe/London"].exists)
    }

    func testMissingFixtureLinkAtLaunchShowsAnUnavailableDestination() {
        let app = launchApp(arguments: [
            "-UITestDeepLink", "https://soccerscanner.pro/fixtures/fx_dddddddddddddddddddddddd",
        ])

        waitForList(app)
        XCTAssertTrue(element(app, "fixture-unavailable").waitForExistence(timeout: 30))
        XCTAssertTrue(element(app, "fixtures-list").exists)
    }

    func testAFailedLoadOffersRetry() {
        let app = launchApp(arguments: ["-UITestFailure", "YES"])

        // Assert on the control rather than its container: the retry button is
        // the affordance under test, and buttons expose identifiers reliably.
        XCTAssertTrue(
            app.buttons["fixtures-retry"].waitForExistence(timeout: 30),
            "a retryable failure must offer a retry action"
        )
        XCTAssertFalse(element(app, "fixtures-list").exists)
    }

    func testPartialStateRetainsRowsAndShowsAnIncompleteNotice() {
        let app = launchApp(arguments: ["-UITestPartial", "YES"])
        waitForList(app)
        XCTAssertTrue(waitForElement(app, "fixtures-notice").exists)
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa").exists)
    }

    func testStaleStateRetainsRowsAndShowsAStaleNotice() {
        let app = launchApp(arguments: ["-UITestStale", "YES"])
        waitForList(app)
        XCTAssertTrue(waitForElement(app, "fixtures-notice").exists)
        XCTAssertTrue(waitForElement(app, "fixture-row-fx_aaaaaaaaaaaaaaaaaaaaaaaa").exists)
    }

    func testEmptyDayIsDistinctFromFilteredEmptyState() {
        let app = launchApp(arguments: ["-UITestEmpty", "YES"])

        XCTAssertTrue(element(app, "fixtures-empty").waitForExistence(timeout: 30))
        XCTAssertFalse(element(app, "fixtures-filtered-empty").exists)
        XCTAssertFalse(element(app, "fixtures-list").exists)
    }

    func testLayoutSurvivesLargestDynamicTypeSize() {
        let app = launchApp(arguments: ["-UIPreferredContentSizeCategoryName",
                                        "UICTContentSizeCategoryAccessibilityXXXL"])
        waitForList(app)

        // The score control must stay reachable at accessibility text sizes.
        XCTAssertTrue(element(app, "score-toggle").isHittable)

        waitForHittable(app, "advanced-filter-button").tap()
        XCTAssertTrue(element(app, "advanced-filter-sheet").waitForExistence(timeout: 10))
        XCTAssertTrue(waitForHittable(app, "advanced-filter-close").isHittable)
        XCTAssertTrue(waitForHittable(app, "advanced-filter-apply").isHittable)
    }

    func testAccessibilityPreferencesKeepPrimaryControlsOperable() {
        let app = launchApp(arguments: [
            "-UIAccessibilityBoldTextEnabled", "YES",
            "-UIAccessibilityDarkerSystemColorsEnabled", "YES",
            "-UIAccessibilityDifferentiateWithoutColorEnabled", "YES",
            "-UIAccessibilityButtonShapesEnabled", "YES",
            "-UIAccessibilityReduceMotionEnabled", "YES",
            "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL",
        ])
        waitForList(app)

        XCTAssertTrue(element(app, "previous-day").isHittable)
        XCTAssertTrue(element(app, "today-day").isHittable)
        XCTAssertTrue(element(app, "next-day").isHittable)
        XCTAssertTrue(element(app, "status-filter").isHittable)
        XCTAssertTrue(element(app, "score-toggle").isHittable)
        XCTAssertFalse(element(app, "fixture-score").exists)
    }

    func testAccessibilityFixtureRowsKeepLongContentAndFiltersOperable() {
        let accessibilityFixtureID = "fx_0123456789abcdef01234567"
        let homeTeam = "Association Sportive de Saint-Étienne Métropole"
        let awayTeam = "Club Deportivo Universidad Nacional de la Patagonia"
        let competition = "International Championship for Regional Football Associations"
        let app = launchApp(arguments: [
            "-UITestAccessibilityFixtures", "YES",
            "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL",
        ])
        waitForList(app)

        XCTAssertTrue(element(app, "previous-day").isHittable)
        XCTAssertTrue(element(app, "next-day").isHittable)
        XCTAssertTrue(element(app, "date-picker").isHittable)
        XCTAssertTrue(element(app, "status-filter").isHittable)

        let initialDay = selectedDay(app)
        element(app, "next-day").tap()
        let shiftedDay = nextDay(after: initialDay)
        waitForValue(element(app, "selected-day"), toEqual: shiftedDay)

        let datePicker = app.datePickers["date-picker"]
        let datePickerTargetDay = nextDay(after: shiftedDay)
        XCTAssertNotEqual(datePickerTargetDay, shiftedDay)
        datePicker.tap()
        let targetDate = app.buttons[calendarButtonLabel(for: datePickerTargetDay)]
        XCTAssertTrue(targetDate.waitForExistence(timeout: 10))
        targetDate.tap()
        waitForValue(element(app, "selected-day"), toEqual: datePickerTargetDay)
        XCTAssertEqual(datePicker.value as? String, datePickerTargetDay)

        element(app, "status-filter").tap()
        XCTAssertTrue(app.buttons["Upcoming"].waitForExistence(timeout: 10))
        app.buttons["Upcoming"].tap()

        let longFixture = waitForHittable(app, "fixture-row-\(accessibilityFixtureID)")
        XCTAssertTrue(longFixture.exists)
        XCTAssertTrue(longFixture.isHittable)
        let rowHomeTeam = element(app, "fixture-home-team-\(accessibilityFixtureID)")
        let rowAwayTeam = element(app, "fixture-away-team-\(accessibilityFixtureID)")
        let rowCompetition = element(app, "fixture-competition-\(accessibilityFixtureID)")
        XCTAssertTrue(rowHomeTeam.waitForExistence(timeout: 10))
        XCTAssertTrue(rowAwayTeam.waitForExistence(timeout: 10))
        XCTAssertTrue(rowCompetition.waitForExistence(timeout: 10))
        XCTAssertEqual(rowHomeTeam.label, homeTeam)
        XCTAssertEqual(rowAwayTeam.label, awayTeam)
        XCTAssertEqual(rowCompetition.label, competition)
        XCTAssertFalse(element(app, "fixture-score").exists)

        longFixture.tap()
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
        let detailTitle = app.staticTexts["\(homeTeam) v \(awayTeam)"]
        XCTAssertTrue(detailTitle.waitForExistence(timeout: 10))
        XCTAssertTrue(detailTitle.isHittable)

        let detailCompetition = element(app, "detail-competition")
        scrollToElement(detailCompetition, in: app)

        let backButton = app.navigationBars.buttons["Fixtures"]
        XCTAssertTrue(backButton.waitForExistence(timeout: 10))
        backButton.tap()
        waitForList(app)

        waitForHittable(app, "advanced-filter-button").tap()
        XCTAssertTrue(element(app, "advanced-filter-sheet").waitForExistence(timeout: 10))
        XCTAssertTrue(waitForHittable(app, "advanced-filter-reset").isHittable)
        XCTAssertTrue(waitForHittable(app, "advanced-filter-close").isHittable)
        XCTAssertTrue(waitForHittable(app, "advanced-filter-apply").isHittable)

        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons[competition].waitForExistence(timeout: 10))
        app.buttons[competition].tap()
        waitForHittable(app, "advanced-filter-reset").tap()
        waitForHittable(app, "advanced-filter-apply").tap()
        XCTAssertEqual(element(app, "advanced-filter-count").label, "0")

        waitForHittable(app, "advanced-filter-button").tap()
        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons[competition].waitForExistence(timeout: 10))
        app.buttons[competition].tap()
        waitForHittable(app, "advanced-filter-close").tap()
        XCTAssertEqual(element(app, "advanced-filter-count").label, "0")

        waitForHittable(app, "advanced-filter-button").tap()
        waitForHittable(app, "advanced-competition").tap()
        XCTAssertTrue(app.buttons[competition].waitForExistence(timeout: 10))
        app.buttons[competition].tap()
        waitForHittable(app, "advanced-filter-apply").tap()
        XCTAssertEqual(element(app, "advanced-filter-count").label, "1")
        XCTAssertTrue(element(app, "fixture-row-\(accessibilityFixtureID)").exists)
    }

    func testAccessibilityFixtureRowsRemainOperableInLandscape() {
        XCUIDevice.shared.orientation = .landscapeLeft
        defer { XCUIDevice.shared.orientation = .portrait }

        let app = launchApp(arguments: [
            "-UITestAccessibilityFixtures", "YES",
            "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL",
        ])
        waitForList(app)

        XCTAssertTrue(element(app, "status-filter").isHittable)
        element(app, "status-filter").tap()
        XCTAssertTrue(app.buttons["Upcoming"].waitForExistence(timeout: 10))
        app.buttons["Upcoming"].tap()

        let longFixture = waitForHittable(app, "fixture-row-fx_0123456789abcdef01234567")
        XCTAssertTrue(longFixture.exists)
        XCTAssertTrue(longFixture.isHittable)
        longFixture.tap()
        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
    }
}
