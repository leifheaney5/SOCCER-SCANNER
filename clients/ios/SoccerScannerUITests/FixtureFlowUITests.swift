import XCTest

/// UI coverage for the vertical slice.
///
/// The app is launched with a stub-data flag so these never depend on the
/// network or on which fixtures happen to be scheduled today.
final class FixtureFlowUITests: XCTestCase {
    private func launchApp(arguments: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-UITestStubData", "YES"] + arguments
        app.launchEnvironment["SOCCER_SCANNER_ENVIRONMENT"] = "development"
        app.launch()
        return app
    }

    func testFixtureListLoadsAndShowsTheSelectedTimezone() {
        let app = launchApp()

        XCTAssertTrue(app.otherElements["fixtures-list"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["timezone-label"].exists)
    }

    func testScoresStartHiddenAndToggleOn() {
        let app = launchApp()
        XCTAssertTrue(app.otherElements["fixtures-list"].waitForExistence(timeout: 10))

        // Spoiler-safe by default.
        XCTAssertTrue(app.images["fixture-score-hidden"].firstMatch.exists)
        XCTAssertFalse(app.staticTexts["fixture-score"].firstMatch.exists)

        app.buttons["score-toggle"].tap()
        XCTAssertTrue(app.staticTexts["fixture-score"].firstMatch.waitForExistence(timeout: 5))
    }

    func testOpeningAFixtureShowsDetail() {
        let app = launchApp()
        XCTAssertTrue(app.otherElements["fixtures-list"].waitForExistence(timeout: 10))

        app.otherElements["fixture-row"].firstMatch.tap()

        XCTAssertTrue(app.collectionViews["fixture-detail"].waitForExistence(timeout: 5))
    }

    func testAFailedLoadOffersRetry() {
        let app = launchApp(arguments: ["-UITestFailure", "YES"])

        XCTAssertTrue(app.otherElements["fixtures-error"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["fixtures-retry"].exists)
    }

    func testLayoutSurvivesLargestDynamicTypeSize() {
        let app = launchApp(arguments: ["-UIPreferredContentSizeCategoryName",
                                        "UICTContentSizeCategoryAccessibilityXXXL"])

        XCTAssertTrue(app.otherElements["fixtures-list"].waitForExistence(timeout: 10))
        // The score control must stay reachable at accessibility text sizes.
        XCTAssertTrue(app.buttons["score-toggle"].isHittable)
    }
}
