import SwiftUI

public struct FixtureListView: View {
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var model: FixtureListViewModel
    @State private var selectedFixture: Fixture?
    @State private var unavailableDestination = false
    @State private var routeOperationalFailure = false
    @State private var initialLoadCompleted = false
    @State private var claimedRoute: AppRoute?
    @State private var advancedFilterPresented = false
    @State private var draftFilter = FixtureFilter()
    private let router: AppRouter
    private let environment: AppEnvironment
    private let client: FixtureFetching

    public init(
        model: FixtureListViewModel,
        router: AppRouter,
        client: FixtureFetching,
        environment: AppEnvironment = .production
    ) {
        _model = State(initialValue: model)
        self.router = router
        self.client = client
        self.environment = environment
    }

    public var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                fixtureControls
                if unavailableDestination {
                    unavailableDestinationNotice
                }
                if routeOperationalFailure {
                    routeOperationalFailureNotice
                }
                content
            }
                .navigationTitle(String(localized: "Fixtures"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { toolbarContent }
                .navigationDestination(item: $selectedFixture) { fixture in
                    FixtureDetailView(
                        fixture: fixture,
                        timeZone: model.selectedTimeZone,
                        scoresRevealed: Binding(
                            get: { model.scoresRevealed },
                            set: { revealed in
                                if model.scoresRevealed != revealed {
                                    model.toggleScores()
                                }
                            }
                        ),
                        providers: model.currentProviders,
                        freshness: model.currentFreshness,
                        client: client
                    )
                }
        }
        .task {
            await model.load()
            initialLoadCompleted = true
            await consumeRouteIfNeeded(router.route)
        }
        .onChange(of: router.route) { _, route in
            guard initialLoadCompleted else { return }
            Task { await consumeRouteIfNeeded(route) }
        }
        .onChange(of: scenePhase) { _, phase in
            guard initialLoadCompleted, phase == .active else { return }
            Task { await model.load() }
        }
        .sheet(isPresented: $advancedFilterPresented) {
            AdvancedFixtureFilterSheet(
                filter: $draftFilter,
                competitionOptions: model.availableCompetitionOptions,
                countryOptions: model.availableCountryOptions,
                onApply: {
                    model.applyFilter($0)
                }
            )
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
        .searchable(
            text: Binding(
                get: { model.filter.searchText },
                set: { model.setSearchText($0) }
            ),
            placement: .navigationBarDrawer(displayMode: .always),
            prompt: "Search fixtures"
        )
        .accessibilityIdentifier("fixture-search")
    }

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            HStack {
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

                NavigationLink {
                    SettingsView(
                        environment: environment,
                        timeZone: model.selectedTimeZone
                    )
                } label: {
                    Label(String(localized: "Settings"), systemImage: "gearshape")
                }
                .accessibilityIdentifier("settings-link")
            }
        }
    }

    private var fixtureControls: some View {
        VStack(spacing: Theme.Spacing.sm) {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: Theme.Spacing.sm) {
                    dayNavigationButtons
                    datePicker
                    Spacer(minLength: 0)
                    timeZoneMenu
                }
                VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
                    HStack(spacing: Theme.Spacing.sm) {
                        dayNavigationButtons
                        datePicker
                    }
                    timeZoneMenu
                }
            }
            Text(FixtureTime.dayHeading(for: model.day, in: model.selectedTimeZone))
                .font(.caption)
                .foregroundStyle(.secondary)
                .accessibilityLabel(String(localized: "Selected fixture day"))
                .accessibilityValue(model.day)
                .accessibilityIdentifier("selected-day")
            statusFilter
            advancedFilterButton
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.vertical, Theme.Spacing.sm)
    }

    @ViewBuilder
    private var statusFilter: some View {
        if dynamicTypeSize.isAccessibilitySize {
            statusPicker.pickerStyle(.menu)
        } else {
            statusPicker.pickerStyle(.segmented)
        }
    }

    private var statusPicker: some View {
        Picker(
            String(localized: "Status"),
            selection: Binding(
                get: { model.filter.status },
                set: { model.setStatusFilter($0) }
            )
        ) {
            ForEach(FixtureStatusFilter.allCases, id: \.self) { status in
                Text(statusLabel(status)).tag(status)
            }
        }
        .accessibilityIdentifier("status-filter")
    }

    private var advancedFilterButton: some View {
        Button {
            draftFilter = model.filter
            advancedFilterPresented = true
        } label: {
            HStack(spacing: Theme.Spacing.sm) {
                Label(String(localized: "Advanced filters"), systemImage: "slider.horizontal.3")
                Spacer(minLength: 0)
                Text(String(model.activeFilterCount))
                    .font(.caption.weight(.semibold).monospacedDigit())
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("advanced-filter-count")
            }
        }
        .buttonStyle(.bordered)
        .accessibilityLabel(String(localized: "Advanced filters"))
        .accessibilityValue(String(localized: "\(model.activeFilterCount) active filters"))
        .accessibilityIdentifier("advanced-filter-button")
    }

    private var unavailableDestinationNotice: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.sm) {
            Label(String(localized: "Fixture unavailable"), systemImage: "exclamationmark.triangle")
                .font(.footnote.weight(.semibold))
            Text(String(localized: "This match is no longer available. You can continue browsing fixtures."))
                .font(.footnote)
            Spacer(minLength: 0)
            Button(String(localized: "Dismiss")) {
                unavailableDestination = false
            }
            .font(.footnote)
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.bottom, Theme.Spacing.sm)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("fixture-unavailable")
    }

    private var routeOperationalFailureNotice: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.sm) {
            Label(String(localized: "Fixture couldn't be opened"), systemImage: "wifi.exclamationmark")
                .font(.footnote.weight(.semibold))
            Text(String(localized: "The fixture could not be opened. Try again later."))
                .font(.footnote)
            Spacer(minLength: 0)
            Button(String(localized: "Dismiss")) {
                routeOperationalFailure = false
            }
            .font(.footnote)
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.bottom, Theme.Spacing.sm)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("fixture-route-error")
    }

    private var dayNavigationButtons: some View {
        HStack(spacing: Theme.Spacing.xs) {
            Button {
                Task { await model.shiftDay(by: -1) }
            } label: {
                Image(systemName: "chevron.left")
            }
            .accessibilityLabel(String(localized: "Previous day"))
            .accessibilityIdentifier("previous-day")

            Button(String(localized: "Today")) {
                Task { await model.selectDay(FixtureTime.today(in: model.selectedTimeZone)) }
            }
            .accessibilityIdentifier("today-day")

            Button {
                Task { await model.shiftDay(by: 1) }
            } label: {
                Image(systemName: "chevron.right")
            }
            .accessibilityLabel(String(localized: "Next day"))
            .accessibilityIdentifier("next-day")
        }
        .buttonStyle(.bordered)
    }

    private var datePicker: some View {
        DatePicker(
            String(localized: "Fixture date"),
            selection: Binding(
                get: { FixtureTime.datePickerDate(for: model.day, in: model.selectedTimeZone) },
                set: { date in
                    Task {
                        await model.selectDay(
                            FixtureTime.calendarDate(for: date, in: model.selectedTimeZone)
                        )
                    }
                }
            ),
            displayedComponents: .date
        )
        .labelsHidden()
        .environment(\.timeZone, model.selectedTimeZone)
        .accessibilityLabel(String(localized: "Select fixture date"))
        .accessibilityValue(model.day)
        .accessibilityIdentifier("date-picker")
    }

    private var timeZoneMenu: some View {
        Menu {
            Button {
                model.selectedTimeZone = .current
            } label: {
                Text(String(localized: "Device local time"))
            }
            .accessibilityIdentifier("timezone-device")

            Divider()

            ForEach(commonTimeZoneIdentifiers, id: \.self) { identifier in
                if let timeZone = TimeZone(identifier: identifier) {
                    Button {
                        model.selectedTimeZone = timeZone
                    } label: {
                        Text(identifier)
                    }
                    .accessibilityIdentifier("timezone-\(identifier)")
                }
            }
        } label: {
            Label(FixtureTime.zoneLabel(model.selectedTimeZone), systemImage: "globe")
        }
        .accessibilityLabel(FixtureTime.accessibleZoneName(model.selectedTimeZone))
        .accessibilityValue(model.selectedTimeZone.identifier)
        .accessibilityIdentifier("timezone-menu")
    }

    private var commonTimeZoneIdentifiers: [String] {
        [
            "UTC",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Australia/Sydney",
        ]
    }

    private func statusLabel(_ status: FixtureStatusFilter) -> String {
        switch status {
        case .all: return String(localized: "All")
        case .live: return String(localized: "Live")
        case .upcoming: return String(localized: "Upcoming")
        case .finished: return String(localized: "Finished")
        }
    }

    private func consumeRouteIfNeeded(_ route: AppRoute?) async {
        guard let route else { return }
        guard claimedRoute != route else { return }
        claimedRoute = route
        defer {
            if claimedRoute == route {
                claimedRoute = nil
            }
        }

        switch route {
        case .fixture(let id, let timeZoneIdentifier, let calendarDay):
            unavailableDestination = false
            routeOperationalFailure = false
            let outcome = await model.openRouteFixture(
                id: id,
                timeZoneIdentifier: timeZoneIdentifier,
                calendarDay: calendarDay,
                isCurrentRoute: { router.route == route }
            )
            guard router.route == route else { return }
            switch outcome {
            case .found(let fixture):
                unavailableDestination = false
                routeOperationalFailure = false
                selectedFixture = fixture
            case .missing:
                unavailableDestination = true
            case .failed:
                routeOperationalFailure = true
            case .superseded:
                break
            }
        case .unsupported:
            unavailableDestination = false
            routeOperationalFailure = false
        }

        router.consume(route)
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .idle, .loading:
            ProgressView(String(localized: "Loading fixtures"))
                .accessibilityIdentifier("fixtures-loading")
        case .loaded(let data):
            fixtureList(data, notice: model.notice(model.loadErrorNotice))
        case .stale(let data):
            fixtureList(data, notice: model.notice(String(localized: "Showing recently cached fixtures.")))
        case .partial(let data, let reason):
            fixtureList(data, notice: model.notice(reason))
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
                if model.filteredFixtures.isEmpty {
                    ContentUnavailableView(
                        String(localized: "No matching fixtures"),
                        systemImage: "line.3.horizontal.decrease.circle",
                        description: Text(String(localized: "No matches match your filters."))
                    )
                    .accessibilityIdentifier("fixtures-filtered-empty")
                } else {
                    ForEach(model.filteredFixtures) { fixture in
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
            .accessibilityIdentifier("fixture-row-\(fixture.id)")
                    }
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

private struct AdvancedFixtureFilterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var filter: FixtureFilter
    let competitionOptions: [String]
    let countryOptions: [String]
    let onApply: (FixtureFilter) -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.lg) {
                    Picker(
                        String(localized: "Competition"),
                        selection: Binding(
                            get: { filter.competition ?? "" },
                            set: { filter.competition = $0.isEmpty ? nil : $0 }
                        )
                    ) {
                        Text(String(localized: "All competitions")).tag("")
                        ForEach(competitionOptions, id: \.self) { option in
                            Text(option).tag(option)
                        }
                    }
                    .pickerStyle(.menu)
                    .accessibilityIdentifier("advanced-competition")

                    Picker(
                        String(localized: "Country or area"),
                        selection: Binding(
                            get: { filter.country ?? "" },
                            set: { filter.country = $0.isEmpty ? nil : $0 }
                        )
                    ) {
                        Text(String(localized: "All countries or areas")).tag("")
                        ForEach(countryOptions, id: \.self) { option in
                            Text(option).tag(option)
                        }
                    }
                    .pickerStyle(.menu)
                    .accessibilityIdentifier("advanced-country")

                    Picker(String(localized: "Time window"), selection: $filter.timeWindow) {
                        ForEach(FixtureTimeWindow.allCases, id: \.self) { window in
                            Text(window.label).tag(window)
                        }
                    }
                    .pickerStyle(.menu)
                    .accessibilityIdentifier("advanced-time-window")

                    Picker(String(localized: "Sort fixtures"), selection: $filter.sort) {
                        ForEach(FixtureSort.allCases, id: \.self) { sort in
                            Text(sort.label).tag(sort)
                        }
                    }
                    .pickerStyle(.menu)
                    .accessibilityIdentifier("advanced-sort")

                    Toggle(String(localized: "Hide finished fixtures"), isOn: $filter.hideFinished)
                        .accessibilityIdentifier("advanced-hide-finished")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Theme.Spacing.lg)
                .padding(.top, Theme.Spacing.lg)
                .padding(.bottom, Theme.Spacing.xl)
            }
                .scrollDismissesKeyboard(.interactively)

                actionBar
            }
            .navigationTitle(String(localized: "Advanced filters"))
            .navigationBarTitleDisplayMode(.inline)
            .accessibilityIdentifier("advanced-filter-sheet")
        }
        .onChange(of: competitionOptions) { _, options in
            if let selected = filter.competition, !options.contains(selected) {
                filter.competition = nil
            }
        }
        .onChange(of: countryOptions) { _, options in
            if let selected = filter.country, !options.contains(selected) {
                filter.country = nil
            }
        }
    }

    private var actionBar: some View {
        HStack(spacing: Theme.Spacing.sm) {
            Button(String(localized: "Reset")) {
                filter.resetAdvanced()
            }
            .accessibilityIdentifier("advanced-filter-reset")

            Spacer(minLength: Theme.Spacing.sm)

            Button(String(localized: "Close")) {
                dismiss()
            }
            .accessibilityIdentifier("advanced-filter-close")

            Button(String(localized: "Apply")) {
                onApply(filter)
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .accessibilityIdentifier("advanced-filter-apply")
        }
        .padding(.horizontal, Theme.Spacing.lg)
        .padding(.vertical, Theme.Spacing.sm)
        .background(.bar)
        .accessibilityElement(children: .contain)
    }
}

struct FixtureRow: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    let fixture: Fixture
    let timeZone: TimeZone
    let scoreText: String?

    var body: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                accessibilityLayout
            } else {
                normalLayout
            }
        }
        .padding(.vertical, Theme.Spacing.xs)
        .frame(minHeight: Theme.minimumTapTarget)
        .contentShape(Rectangle())
    }

    private var normalLayout: some View {
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

            scoreIndicator
        }
    }

    private var accessibilityLayout: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.sm) {
            HStack(alignment: .top, spacing: Theme.Spacing.sm) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    StatusBadge(status: fixture.status)
                    Text(FixtureTime.kickoff(fixture.utcDate, in: timeZone))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
                Spacer(minLength: Theme.Spacing.sm)
                scoreIndicator
            }

            accessibilityTeamNames
            competitionName
        }
    }

    private var accessibilityTeamNames: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(fixture.homeTeam.name)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("fixture-home-team-\(fixture.id)")
            Text(fixture.awayTeam.name)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("fixture-away-team-\(fixture.id)")
        }
        .layoutPriority(2)
    }

    @ViewBuilder
    private var competitionName: some View {
        if let competition = fixture.competition?.displayName {
            Text(competition)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("fixture-competition-\(fixture.id)")
        }
    }

    @ViewBuilder
    private var scoreIndicator: some View {
        if let scoreText {
            Text(scoreText)
                .font(.headline.monospacedDigit())
                .fixedSize(horizontal: true, vertical: false)
                .accessibilityIdentifier("fixture-score")
        } else if fixture.status.scoreAvailable && fixture.hasFullTimeScore {
            // A score exists but is deliberately concealed.
            Image(systemName: "eye.slash")
                .foregroundStyle(.secondary)
                .accessibilityLabel(String(localized: "Score hidden"))
                .accessibilityIdentifier("fixture-score-hidden")
        } else if fixture.status.scoreAvailable {
            Image(systemName: "questionmark")
                .foregroundStyle(.secondary)
                .accessibilityLabel(String(localized: "Score unavailable"))
                .accessibilityIdentifier("fixture-score-unavailable")
        }
    }

    private var accessibilitySummary: String {
        var parts = [
            String(localized: "\(fixture.homeTeam.name) versus \(fixture.awayTeam.name)"),
            fixture.status.label,
            FixtureTime.kickoff(fixture.utcDate, in: timeZone),
        ]
        if let competition = fixture.competition?.displayName {
            parts.append(competition)
        }
        if let scoreText {
            parts.append(String(localized: "Score \(scoreText)"))
        } else if fixture.status.scoreAvailable && fixture.hasFullTimeScore {
            parts.append(String(localized: "Score hidden"))
        } else if fixture.status.scoreAvailable {
            parts.append(String(localized: "Score unavailable"))
        }
        return parts.joined(separator: ", ")
    }
}

#Preview("Loaded") {
    let client = PreviewFixtureClient()
    FixtureListView(
        model: FixtureListViewModel(client: client),
        router: AppRouter(),
        client: client,
        environment: .development
    )
}
