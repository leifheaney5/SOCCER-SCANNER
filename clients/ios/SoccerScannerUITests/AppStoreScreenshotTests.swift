import Foundation
import XCTest

/// Captures App Store screenshots of the real app against live production data.
///
/// Skipped unless `CAPTURE_APP_STORE_SCREENSHOTS=1` reaches the test runner
/// (xcodebuild forwards `TEST_RUNNER_CAPTURE_APP_STORE_SCREENSHOTS=1`), so the
/// regular simulator suite never depends on the network. Each screenshot is a
/// kept XCTAttachment that `.github/workflows/ios-screenshots.yml` exports.
/// Scores stay hidden: the app starts every launch with scores hidden and this
/// test never reveals them.
@MainActor
final class AppStoreScreenshotTests: XCTestCase {
    func testCaptureAppStoreScreenshots() throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["CAPTURE_APP_STORE_SCREENSHOTS"] == "1",
            "App Store screenshot capture runs only from the screenshot workflow."
        )
        continueAfterFailure = true
        XCUIDevice.shared.orientation = .portrait
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        // US Eastern kickoff times for the US storefront; CI runners default to UTC.
        app.launchEnvironment = ["SOCCER_SCANNER_ENVIRONMENT": "production", "TZ": "America/New_York"]
        app.launch()

        let list = identified(app, "fixtures-list")
        XCTAssertTrue(list.waitForExistence(timeout: 90), "fixture list never loaded from production")
        settle(4)
        snap("01-fixtures")

        let firstRow = app.descendants(matching: .any)
            .matching(NSPredicate(format: "identifier BEGINSWITH 'fixture-row-'"))
            .firstMatch
        if firstRow.waitForExistence(timeout: 20) {
            firstRow.tap()
            if identified(app, "fixture-detail").waitForExistence(timeout: 20) {
                settle(2)
                snap("02-match-details")
            }
            goBack(app)
        }

        if selectStatus(app, "Upcoming") {
            settle(3)
            snap("03-upcoming")
            _ = selectStatus(app, "All")
        }

        let filterButton = identified(app, "advanced-filter-button")
        if filterButton.waitForExistence(timeout: 10) {
            filterButton.tap()
            if identified(app, "advanced-filter-sheet").waitForExistence(timeout: 10) {
                settle(1)
                snap("04-filters")
                let close = identified(app, "advanced-filter-close")
                if close.exists { close.tap() } else { app.swipeDown() }
            }
        }

        let settingsLink = identified(app, "settings-link")
        if settingsLink.waitForExistence(timeout: 10) {
            settingsLink.tap()
            if identified(app, "settings-view").waitForExistence(timeout: 10) {
                settle(1)
                snap("05-settings")
            }
        }
    }

    private func identified(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    /// Picks a status segment; returns false when the control is unavailable.
    private func selectStatus(_ app: XCUIApplication, _ label: String) -> Bool {
        let picker = identified(app, "status-filter")
        guard picker.waitForExistence(timeout: 10) else { return false }
        let segment = picker.buttons[label].exists ? picker.buttons[label] : app.buttons[label]
        guard segment.exists else { return false }
        segment.tap()
        return true
    }

    private func goBack(_ app: XCUIApplication) {
        let back = app.navigationBars.buttons.element(boundBy: 0)
        if back.exists { back.tap() }
        _ = identified(app, "fixtures-list").waitForExistence(timeout: 10)
    }

    /// Lets crests and live data finish loading before a capture.
    private func settle(_ seconds: TimeInterval) {
        RunLoop.current.run(until: Date().addingTimeInterval(seconds))
    }

    private func snap(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
