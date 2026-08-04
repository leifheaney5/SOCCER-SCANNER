const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [appStoreModule, fixtureStateModule, scorePreferenceModule, fixtureRendererModule, matchContextModule, teamDrawerModule] = await Promise.all([
    import(versionedModule('./app-store.js')),
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
    import(versionedModule('./fixture-renderer.js')),
    import(versionedModule('./match-context.js')),
    import(versionedModule('./team-drawer.js')),
]);
const {createStore} = appStoreModule;
const {
    createState,
    filterMatches,
    groupMatches,
    isValidDate,
    shiftDate,
    sortMatches,
    summarizeMatches,
    todayLocal,
} = fixtureStateModule;
const {
    readScorePreference,
    syncScoreToggle,
    writeScorePreference,
} = scorePreferenceModule;
const {
    renderFeatured,
    renderEmptyState,
    renderFixtureStream,
    renderLoading,
    renderNotice,
    renderRequestError,
    renderSummary,
} = fixtureRendererModule;
const {createMatchContext} = matchContextModule;
const {createTeamDrawer} = teamDrawerModule;

const byId = id => document.getElementById(id);
const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
const store = createStore(createState(window.location.search, detectedTimezone));
let state = store.getState();
store.subscribe(next => {
    state = next;
});
let payload = null;
let scoresRevealed = readScorePreference();
let searchTimer = null;
const expandedGroups = new Set();
let selectedFixtureId = null;
let activeRequestController = null;
let requestSequence = 0;
let matchContext = null;
let teamDrawer = null;

function setState(patch, metadata = {}) {
    return store.dispatch(patch, metadata);
}

function syncUrl(mode = 'replace') {
    const query = state.toSearchParams().toString();
    const method = mode === 'push' ? 'pushState' : 'replaceState';
    history[method]({dashboard: true}, '', `${location.pathname}?${query}`);
}

function syncControls() {
    byId('dashboard-date').value = state.date;
    const dateError = byId('date-error');
    dateError.hidden = !state.dateError;
    byId('dashboard-date').setAttribute('aria-invalid', String(Boolean(state.dateError)));
    const timezone = byId('timezone-filter');
    if (![...timezone.options].some(option => option.value === state.timezone)) {
        timezone.add(new Option(state.timezone.replaceAll('_', ' '), state.timezone));
    }
    timezone.value = state.timezone;
    byId('country-filter').value = state.country;
    byId('time-filter').value = state.timeWindow;
    byId('sort-filter').value = state.sort;
    byId('hide-finished').checked = state.hideFinished;
    byId('fixture-search').value = state.query;
    byId('clear-search').hidden = !state.query;
    const competition = byId('competition-filter');
    if ([...competition.options].some(option => option.value === state.competition)) {
        competition.value = state.competition;
    }
    document.querySelectorAll('[data-status]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.status === state.status));
    });
    const activeFilters = Number(Boolean(state.competition))
        + Number(Boolean(state.country))
        + Number(state.status !== 'all')
        + Number(Boolean(state.query))
        + Number(state.timeWindow !== 'all')
        + Number(state.hideFinished);
    byId('active-filter-count').textContent = String(activeFilters);
    byId('active-filter-count').hidden = activeFilters === 0;
    byId('clear-filters').hidden = activeFilters === 0;
    syncScoreToggle(byId('score-toggle'), scoresRevealed);
}

function populateCompetitions(matches) {
    const select = byId('competition-filter');
    const names = [...new Set(matches.map(match => match?.competition?.name).filter(Boolean))].sort();
    const options = [new Option('All competitions', ''), ...names.map(name => new Option(name, name))];
    select.replaceChildren(...options);
    if (state.competition && names.includes(state.competition)) {
        select.value = state.competition;
    } else if (state.competition) {
        setState({competition: ''}, {reason: 'reconcile'});
        syncUrl('replace');
    }
    const countrySelect = byId('country-filter');
    const countries = [...new Set(matches.map(match => match?.competition?.area?.name).filter(Boolean))].sort();
    countrySelect.replaceChildren(
        new Option('All countries', ''),
        ...countries.map(country => new Option(country, country)),
    );
    if (state.country && countries.includes(state.country)) {
        countrySelect.value = state.country;
    } else if (state.country) {
        setState({country: ''}, {reason: 'reconcile'});
        syncUrl('replace');
    }
}

function reflectCurrentResults() {
    if (!payload) return;
    const filteredMatches = filterMatches(payload.matches, state);
    const matches = sortMatches(filteredMatches, state.sort);
    if (selectedFixtureId && !matches.some(match => (
        String(match.canonicalFixtureId || match.id) === selectedFixtureId
    ))) {
        selectedFixtureId = null;
        matchContext?.reset();
    }
    const summary = summarizeMatches(matches);
    renderSummary(byId('daily-summary'), payload.matches, payload);
    renderNotice(byId('data-notice'), payload);
    renderFeatured(byId('featured-match'), filteredMatches, scoresRevealed);
    if (matches.length === 0) {
        renderEmptyState(byId('fixture-stream'), {filtered: payload.matches.length > 0});
    } else {
        renderFixtureStream(byId('fixture-stream'), groupMatches(matches), {
            revealed: scoresRevealed,
            expandedGroups,
            selectedId: selectedFixtureId,
        });
    }
    byId('fixture-result-count').textContent = `${summary.total} ${summary.total === 1 ? 'match' : 'matches'}`;
    byId('dashboard-status').textContent = `${summary.total} fixtures shown`;
    matchContext?.rerender();
    teamDrawer?.rerender();
}

async function loadFixtures() {
    activeRequestController?.abort();
    activeRequestController = new AbortController();
    const requestId = ++requestSequence;
    byId('dashboard-status').textContent = 'Loading fixtures';
    renderLoading(byId('fixture-stream'));
    byId('fixture-result-count').textContent = 'Loading';
    byId('featured-match').hidden = true;
    byId('featured-match').replaceChildren();
    byId('data-notice').hidden = true;
    try {
        const requestedDate = state.date;
        const response = await fetch(`/api/v2/fixtures?date=${encodeURIComponent(requestedDate)}&timezone=${encodeURIComponent(state.timezone)}`, {
            signal: activeRequestController.signal,
        });
        if (!response.ok) throw new Error('Fixture request failed');
        const nextPayload = await response.json();
        if (requestId !== requestSequence) return;
        payload = {...nextPayload, date: requestedDate};
        if (!Array.isArray(payload.matches)) payload.matches = [];
        populateCompetitions(payload.matches);
        syncControls();
        reflectCurrentResults();
    } catch (error) {
        if (error?.name === 'AbortError' || requestId !== requestSequence) return;
        byId('dashboard-status').textContent = 'Football data is temporarily unavailable';
        renderRequestError(byId('fixture-stream'), loadFixtures);
    }
}

function cancelPendingSearch() {
    clearTimeout(searchTimer);
    searchTimer = null;
}

function applyFilter(patch, {historyMode = 'push'} = {}) {
    if (!Object.hasOwn(patch, 'query')) cancelPendingSearch();
    setState(patch, {reason: 'filter'});
    syncControls();
    syncUrl(historyMode);
    reflectCurrentResults();
}

function chooseDate(date) {
    cancelPendingSearch();
    if (!isValidDate(date)) {
        setState({dateError: true}, {reason: 'invalid-date'});
        syncControls();
        return;
    }
    setState({date, dateError: false}, {reason: 'date'});
    selectedFixtureId = null;
    matchContext?.reset();
    syncControls();
    syncUrl('push');
    loadFixtures();
}

function bindEvents() {
    byId('previous-date').addEventListener('click', () => chooseDate(shiftDate(state.date, -1)));
    byId('today-date').addEventListener('click', () => chooseDate(todayLocal()));
    byId('next-date').addEventListener('click', () => chooseDate(shiftDate(state.date, 1)));
    byId('dashboard-date').addEventListener('change', event => chooseDate(event.target.value));
    byId('timezone-filter').addEventListener('change', event => {
        cancelPendingSearch();
        setState({timezone: event.target.value}, {reason: 'timezone'});
        selectedFixtureId = null;
        matchContext?.reset();
        syncControls();
        syncUrl('push');
        loadFixtures();
    });
    byId('competition-filter').addEventListener('change', event => applyFilter({competition: event.target.value}));
    byId('country-filter').addEventListener('change', event => applyFilter({country: event.target.value}));
    byId('time-filter').addEventListener('change', event => applyFilter({timeWindow: event.target.value}));
    byId('sort-filter').addEventListener('change', event => applyFilter({sort: event.target.value}));
    byId('hide-finished').addEventListener('change', event => applyFilter({hideFinished: event.target.checked}));
    document.querySelector('.status-filters').addEventListener('click', event => {
        const button = event.target.closest('[data-status]');
        if (button) applyFilter({status: button.dataset.status});
    });
    byId('fixture-search').addEventListener('input', event => {
        clearTimeout(searchTimer);
        const query = event.target.value;
        byId('clear-search').hidden = !query;
        searchTimer = setTimeout(() => applyFilter({query}, {historyMode: 'replace'}), 150);
    });
    byId('clear-search').addEventListener('click', () => {
        cancelPendingSearch();
        applyFilter({query: ''}, {historyMode: 'replace'});
    });
    byId('clear-filters').addEventListener('click', () => applyFilter({
        competition: '',
        country: '',
        status: 'all',
        query: '',
        timeWindow: 'all',
        hideFinished: false,
    }));
    byId('filter-toggle').addEventListener('click', event => {
        const expanded = event.currentTarget.getAttribute('aria-expanded') === 'true';
        event.currentTarget.setAttribute('aria-expanded', String(!expanded));
        byId('secondary-filters').classList.toggle('is-open', !expanded);
    });
    byId('score-toggle').addEventListener('click', () => {
        scoresRevealed = !scoresRevealed;
        writeScorePreference(window.localStorage, scoresRevealed);
        syncScoreToggle(byId('score-toggle'), scoresRevealed);
        reflectCurrentResults();
    });
    const fixtureAction = event => {
        const action = event.target.closest('[data-action]');
        if (!action) return;
        if (action.dataset.action === 'toggle-group') {
            const key = action.dataset.group;
            expandedGroups.has(key) ? expandedGroups.delete(key) : expandedGroups.add(key);
            reflectCurrentResults();
        } else if (action.dataset.action === 'select-fixture') {
            selectedFixtureId = action.dataset.fixtureId;
            reflectCurrentResults();
            const match = payload?.matches?.find(item => (
                String(item.canonicalFixtureId || item.id) === selectedFixtureId
            ));
            const replacement = byId('fixture-stream').querySelector(
                `.details-button[data-fixture-id="${CSS.escape(selectedFixtureId)}"]`,
            );
            if (match && replacement) matchContext.open(match, replacement);
        } else if (action.dataset.action === 'clear-filters') {
            applyFilter({competition: '', country: '', status: 'all', query: '', timeWindow: 'all', hideFinished: false});
        } else if (action.dataset.action === 'shift-date') {
            chooseDate(shiftDate(state.date, Number(action.dataset.days)));
        }
    };
    byId('fixture-stream').addEventListener('click', fixtureAction);
    byId('featured-match').addEventListener('click', fixtureAction);
    window.addEventListener('popstate', () => {
        cancelPendingSearch();
        const previous = state;
        const restored = createState(window.location.search, detectedTimezone);
        setState(restored, {reason: 'popstate'});
        selectedFixtureId = null;
        matchContext?.reset();
        syncControls();
        if (previous.date !== state.date || previous.timezone !== state.timezone) {
            loadFixtures();
        } else {
            reflectCurrentResults();
        }
    });
}

function init() {
    teamDrawer = createTeamDrawer({
        dialog: byId('team-drawer'),
        content: byId('team-drawer-content'),
        closeButton: byId('close-team-drawer'),
        getRevealed: () => scoresRevealed,
    });
    matchContext = createMatchContext({
        panel: byId('match-context'),
        panelContent: byId('match-context-content'),
        dialog: byId('match-context-dialog'),
        dialogContent: byId('match-context-dialog-content'),
        closeButton: byId('close-match-context'),
        getRevealed: () => scoresRevealed,
        onTeam: (team, trigger) => teamDrawer.open(team, trigger),
    });
    syncControls();
    bindEvents();
    loadFixtures();
}

init();
