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

    /// Query by identifier without asserting an element type.
    ///
    /// SwiftUI does not guarantee which UIKit element a `List`, row or
    /// `ContentUnavailableView` becomes, and it changes between releases.
    /// Matching on identifier alone keeps these tests about behaviour.
    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    private func waitForList(_ app: XCUIApplication) {
        XCTAssertTrue(
            element(app, "fixtures-list").waitForExistence(timeout: 30),
            "fixture list never appeared"
        )
    }

    func testFixtureListLoadsAndShowsTheSelectedTimezone() {
        let app = launchApp()
        waitForList(app)

        XCTAssertTrue(element(app, "timezone-label").exists)
    }

    func testScoresStartHiddenAndToggleOn() {
        let app = launchApp()
        waitForList(app)

        // Spoiler-safe by default.
        XCTAssertTrue(element(app, "fixture-score-hidden").exists)
        XCTAssertFalse(element(app, "fixture-score").exists)

        element(app, "score-toggle").tap()

        XCTAssertTrue(element(app, "fixture-score").waitForExistence(timeout: 10))
    }

    func testOpeningAFixtureShowsDetail() {
        let app = launchApp()
        waitForList(app)

        element(app, "fixture-row").tap()

        XCTAssertTrue(element(app, "fixture-detail").waitForExistence(timeout: 10))
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

    func testLayoutSurvivesLargestDynamicTypeSize() {
        let app = launchApp(arguments: ["-UIPreferredContentSizeCategoryName",
                                        "UICTContentSizeCategoryAccessibilityXXXL"])
        waitForList(app)

        // The score control must stay reachable at accessibility text sizes.
        XCTAssertTrue(element(app, "score-toggle").isHittable)
    }
}
