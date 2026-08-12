const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [appStoreModule, fixtureStateModule, scorePreferenceModule, fixtureRendererModule, matchContextModule, refreshModule, dialogModule, timezoneControlModule, timeZoneModule] = await Promise.all([
    import(versionedModule('./app-store.js')),
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
    import(versionedModule('./fixture-renderer.js')),
    import(versionedModule('./match-context.js')),
    import(versionedModule('./refresh-controller.js')),
    import(versionedModule('./dialog-manager.js')),
    import(versionedModule('./timezone-control.js')),
    import(versionedModule('./time-zone.js')),
]);
const {createStore} = appStoreModule;
const {
    buildDateTabs,
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
    renderUpdateFailure,
    setRenderTimeZone,
} = fixtureRendererModule;
const {createMatchContext} = matchContextModule;
const {createRefreshController} = refreshModule;
const {createDialogManager} = dialogModule;
const {createTimezoneControl} = timezoneControlModule;
const {calendarDateInZone} = timeZoneModule;

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
let selectedFixtureId = state.fixture || null;
let activeRequestController = null;
let requestSequence = 0;
let matchContext = null;
let refreshController = null;
let timezoneControl = null;
let filterDialog = null;
let filterDialogManager = null;
let filterDraft = null;
let filterMediaQuery = null;

const advancedFilterFields = ['competition', 'country', 'timeWindow', 'sort', 'hideFinished', 'timezone'];

function setState(patch, metadata = {}) {
    return store.dispatch(patch, metadata);
}

function syncUrl(mode = 'replace') {
    const query = state.toSearchParams().toString();
    const method = mode === 'push' ? 'pushState' : 'replaceState';
    history[method]({dashboard: true}, '', `${location.pathname}?${query}`);
}

function filterValues(source = state) {
    return Object.fromEntries(advancedFilterFields.map(field => [field, source[field]]));
}

function activeFilterCount(source = state) {
    return Number(Boolean(source.competition))
        + Number(Boolean(source.country))
        + Number(source.status !== 'all')
        + Number(Boolean(source.query))
        + Number(source.timeWindow !== 'all')
        + Number(source.sort !== 'kickoff')
        + Number(source.hideFinished);
}

function advancedFilterHasValues(source = state, baseline = state) {
    return Boolean(source.competition)
        || Boolean(source.country)
        || source.timeWindow !== 'all'
        || source.sort !== 'kickoff'
        || Boolean(source.hideFinished)
        || source.timezone !== baseline.timezone;
}

function syncControls({filterState = filterDraft || state} = {}) {
    byId('dashboard-date').value = state.date;
    const dateError = byId('date-error');
    dateError.hidden = !state.dateError;
    byId('dashboard-date').setAttribute('aria-invalid', String(Boolean(state.dateError)));
    const timezone = byId('timezone-filter');
    if (![...timezone.options].some(option => option.value === state.timezone)) {
        timezone.add(new Option(state.timezone.replaceAll('_', ' '), state.timezone));
    }
    timezone.value = filterState.timezone;
    byId('country-filter').value = filterState.country;
    byId('time-filter').value = filterState.timeWindow;
    byId('sort-filter').value = filterState.sort;
    byId('hide-finished').checked = filterState.hideFinished;
    byId('fixture-search').value = state.query;
    byId('clear-search').hidden = !state.query;
    const competition = byId('competition-filter');
    if ([...competition.options].some(option => option.value === filterState.competition)) {
        competition.value = filterState.competition;
    }
    document.querySelectorAll('[data-status]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.status === state.status));
    });
    const activeFilters = activeFilterCount(state);
    byId('active-filter-count').textContent = String(activeFilters);
    byId('active-filter-count').hidden = activeFilters === 0;
    byId('clear-filters').hidden = filterDialog?.open
        ? !advancedFilterHasValues(filterState, state)
        : !(activeFilters || advancedFilterHasValues(state));
    syncScoreToggle(byId('score-toggle'), scoresRevealed);
    timezoneControl?.sync();
}

function renderDateStrip() {
    const strip = byId('date-strip');
    if (!strip) return;
    strip.replaceChildren(...buildDateTabs(state.date).map(tab => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'date-strip-item';
        button.dataset.date = tab.date;
        button.setAttribute('aria-current', tab.date === state.date ? 'date' : 'false');
        const label = document.createElement('span');
        label.className = 'date-strip-label';
        label.textContent = tab.label;
        const date = document.createElement('span');
        date.className = 'date-strip-date';
        date.textContent = tab.shortLabel;
        button.append(label, date);
        button.addEventListener('click', () => chooseDate(tab.date));
        return button;
    }));
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
    const countryControl = countrySelect.closest('.select-control');
    const countries = [...new Set(matches.map(match => match?.competition?.area?.name).filter(Boolean))].sort();
    countrySelect.replaceChildren(
        new Option('All countries', ''),
        ...countries.map(country => new Option(country, country)),
    );
    // Fewer than two countries means the control cannot actually filter
    // anything — offering only "All countries" is a non-functional control,
    // so hide the wrapping label rather than leave it visibly empty.
    const countryFilterUsable = countries.length >= 2;
    if (countryControl) countryControl.hidden = !countryFilterUsable;
    if (!countryFilterUsable) {
        if (state.country) {
            setState({country: ''}, {reason: 'reconcile'});
            syncUrl('replace');
        }
    } else if (state.country && countries.includes(state.country)) {
        countrySelect.value = state.country;
    } else if (state.country) {
        setState({country: ''}, {reason: 'reconcile'});
        syncUrl('replace');
    }
    if (filterDraft) {
        if (filterDraft.competition && !names.includes(filterDraft.competition)) {
            filterDraft.competition = '';
        }
        if (filterDraft.country && !countries.includes(filterDraft.country)) {
            filterDraft.country = '';
        }
    }
}

function reflectCurrentResults() {
    if (!payload) return;
    // Every date and time rendered below must use the selected zone.
    setRenderTimeZone(state.timezone);
    const filteredMatches = filterMatches(payload.matches, state);
    const matches = sortMatches(filteredMatches, state.sort);
    if (selectedFixtureId && !matches.some(match => (
        String(match.canonicalFixtureId || match.id) === selectedFixtureId
    ))) {
        selectedFixtureId = null;
        if (state.fixture) {
            setState({fixture: ''}, {reason: 'reconcile-fixture'});
            syncUrl('replace');
        }
        matchContext?.reset();
    }
    const summary = summarizeMatches(matches);
    renderSummary(byId('daily-summary'), payload.matches, payload);
    renderNotice(byId('data-notice'), payload);
    renderFeatured(byId('featured-match'), filteredMatches, scoresRevealed);
    if (matches.length === 0) {
        renderEmptyState(byId('fixture-stream'), {filtered: payload.matches.length > 0});
    } else {
        renderFixtureStream(byId('fixture-stream'), groupMatches(matches, state.sort), {
            revealed: scoresRevealed,
            expandedGroups,
            selectedId: selectedFixtureId,
        });
    }
    byId('fixture-result-count').textContent = `${summary.total} ${summary.total === 1 ? 'match' : 'matches'}`;
    byId('dashboard-status').textContent = `${summary.total} fixtures shown`;
    byId('fixture-stream-title').textContent = 'Match schedule';
    const selectedMatch = selectedFixtureId
        ? payload.matches.find(item => String(item.canonicalFixtureId || item.id) === selectedFixtureId)
        : null;
    if (selectedMatch && matchContext?.selected()) {
        matchContext.update(selectedMatch);
    } else {
        matchContext?.rerender();
    }
    if (selectedMatch && !matchContext?.selected()) {
        const match = selectedMatch;
        const trigger = byId('fixture-stream').querySelector(
            `.details-button[data-fixture-id="${CSS.escape(selectedFixtureId)}"]`,
        );
        if (match && trigger) matchContext.open(match, trigger);
    }
}

function classifyRequestFailure(response, body, error = null) {
    const providerCode = body?.error?.code;
    let kind = providerCode || 'unavailable';
    if (!navigator.onLine) kind = 'offline';
    else if (response?.status === 429) kind = 'rate_limited';
    else if (response?.status === 400) kind = 'invalid_request';
    else if (error instanceof SyntaxError) kind = 'format';
    else if (error?.name === 'TimeoutError') kind = 'timeout';
    const headerDelay = Number(response?.headers?.get('Retry-After'));
    const retryAfterSeconds = Number(body?.error?.retryAfterSeconds) || (Number.isFinite(headerDelay) ? headerDelay : null);
    return {kind, retryAfterSeconds, retryAfterMs: retryAfterSeconds ? retryAfterSeconds * 1_000 : null};
}

async function loadFixtures({preserve = false} = {}) {
    activeRequestController?.abort();
    activeRequestController = new AbortController();
    const requestId = ++requestSequence;
    byId('dashboard-status').textContent = preserve ? 'Updating fixtures' : 'Loading fixtures';
    byId('refresh-fixtures').classList.toggle('is-updating', preserve);
    byId('refresh-fixtures').setAttribute('aria-busy', String(preserve));
    if (!preserve) {
        renderLoading(byId('fixture-stream'));
        byId('fixture-result-count').textContent = 'Loading';
        byId('featured-match').hidden = true;
        byId('featured-match').replaceChildren();
        byId('data-notice').hidden = true;
    }
    try {
        const requestedDate = state.date;
        const response = await fetch(`/api/v2/fixtures?date=${encodeURIComponent(requestedDate)}&timezone=${encodeURIComponent(state.timezone)}`, {
            signal: activeRequestController.signal,
        });
        let nextPayload = null;
        try {
            nextPayload = await response.json();
        } catch (error) {
            error.response = response;
            throw error;
        }
        if (!response.ok) {
            const failure = classifyRequestFailure(response, nextPayload);
            const error = new Error('Fixture request failed');
            Object.assign(error, {response, body: nextPayload, failure});
            throw error;
        }
        if (requestId !== requestSequence) return;
        payload = {...nextPayload, date: requestedDate};
        if (!Array.isArray(payload.matches)) payload.matches = [];
        populateCompetitions(payload.matches);
        syncControls();
        reflectCurrentResults();
        return {ok: true};
    } catch (error) {
        if (error?.name === 'AbortError' || requestId !== requestSequence) return {ok: false, aborted: true};
        const failure = error.failure || classifyRequestFailure(error.response, error.body, error);
        byId('dashboard-status').textContent = preserve ? 'Live update delayed; showing previous fixtures' : 'Football data is temporarily unavailable';
        if (preserve && payload) renderUpdateFailure(byId('data-notice'), failure);
        else renderRequestError(byId('fixture-stream'), () => loadFixtures(), failure);
        return {ok: false, ...failure};
    } finally {
        if (requestId === requestSequence) {
            byId('refresh-fixtures').classList.remove('is-updating');
            byId('refresh-fixtures').setAttribute('aria-busy', 'false');
        }
    }
}

function cancelPendingSearch() {
    clearTimeout(searchTimer);
    searchTimer = null;
}

function flushPendingSearch() {
    const hasPendingSearch = Boolean(searchTimer);
    const query = byId('fixture-search').value;
    cancelPendingSearch();
    if (hasPendingSearch && query !== state.query) {
        setState({query}, {reason: 'filter-input'});
    }
}

function applyFilter(patch, {historyMode = 'push'} = {}) {
    if (!Object.hasOwn(patch, 'query')) flushPendingSearch();
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
    setState({date, dateError: false, fixture: '', query: ''}, {reason: 'date'});
    selectedFixtureId = null;
    matchContext?.reset();
    syncControls();
    renderDateStrip();
    syncUrl('push');
    loadFixtures();
}

// Shared by the `#timezone-filter` select and the header timezone control so
// the two views of `state.timezone` cannot drift: whichever one changes the
// zone, this is the only place that applies it.
function applyTimezone(timezone, {extraPatch = {}, reason = 'timezone'} = {}) {
    cancelPendingSearch();
    const fixtureId = selectedFixtureId || state.fixture || '';
    const selectedMatch = fixtureId
        ? payload?.matches?.find(item => String(item.canonicalFixtureId || item.id) === fixtureId)
        : null;
    const date = selectedMatch?.utcDate
        ? calendarDateInZone(selectedMatch.utcDate, timezone)
        : state.date;
    setState({...extraPatch, timezone, date, fixture: fixtureId}, {reason});
    selectedFixtureId = fixtureId || null;
    syncControls();
    syncUrl('push');
    loadFixtures();
}

function isMobileFilterLayout() {
    return Boolean(filterMediaQuery?.matches);
}

function moveSecondaryFiltersForViewport() {
    const secondaryFilters = byId('secondary-filters');
    const dialogContent = byId('filter-dialog-content');
    const toolbar = document.querySelector('.filter-toolbar');
    if (!secondaryFilters || !dialogContent || !toolbar) return;
    if (isMobileFilterLayout()) {
        dialogContent.append(secondaryFilters);
    } else {
        if (filterDialog?.open) filterDialogManager?.close(filterDialog, {restoreFocus: false});
        toolbar.append(secondaryFilters);
    }
}

function updateFilterDraft(patch) {
    filterDraft = {...(filterDraft || filterValues()), ...patch};
    syncControls({filterState: filterDraft});
}

function closeFilterDialog() {
    filterDraft = null;
    filterDialogManager?.close(filterDialog);
}

function commitFilterDraft() {
    if (!filterDraft) return closeFilterDialog();
    const patch = {};
    advancedFilterFields.forEach(field => {
        if (filterDraft[field] !== state[field]) patch[field] = filterDraft[field];
    });
    const timezoneChanged = Object.hasOwn(patch, 'timezone');
    delete patch.timezone;
    if (timezoneChanged) {
        applyTimezone(filterDraft.timezone, {
            extraPatch: patch,
            reason: 'filter-dialog',
        });
    } else if (Object.keys(patch).length > 0) {
        applyFilter(patch);
    }
    closeFilterDialog();
}

function bindFilterDialog(dialogManager) {
    filterDialogManager = dialogManager;
    filterDialog = byId('filter-dialog');
    filterMediaQuery = window.matchMedia('(max-width: 767px)');
    moveSecondaryFiltersForViewport();
    filterMediaQuery.addEventListener?.('change', moveSecondaryFiltersForViewport);
    byId('filter-toggle').addEventListener('click', () => {
        if (!isMobileFilterLayout()) return;
        filterDraft = filterValues();
        syncControls({filterState: filterDraft});
        byId('filter-toggle').setAttribute('aria-expanded', 'true');
        filterDialogManager.open(filterDialog, byId('filter-toggle'));
    });
    byId('close-filter-dialog').addEventListener('click', closeFilterDialog);
    byId('cancel-filter-dialog').addEventListener('click', closeFilterDialog);
    byId('apply-filter-dialog').addEventListener('click', commitFilterDraft);
    filterDialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const focusable = [...filterDialog.querySelectorAll(
            'button:not([disabled]), select:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        )].filter(element => element.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
    filterDialog.addEventListener('click', event => {
        if (event.target === filterDialog) closeFilterDialog();
    });
    filterDialog.addEventListener('close', () => {
        filterDraft = null;
        byId('filter-toggle').setAttribute('aria-expanded', 'false');
        syncControls();
    });
}

function bindEvents() {
    byId('previous-date').addEventListener('click', () => chooseDate(shiftDate(state.date, -1)));
    byId('today-date').addEventListener('click', () => chooseDate(todayLocal(new Date(), state.timezone)));
    byId('next-date').addEventListener('click', () => chooseDate(shiftDate(state.date, 1)));
    byId('dashboard-date').addEventListener('change', event => chooseDate(event.target.value));
    byId('timezone-filter').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({timezone: event.target.value});
        else applyTimezone(event.target.value);
    });
    byId('competition-filter').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({competition: event.target.value});
        else applyFilter({competition: event.target.value});
    });
    byId('country-filter').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({country: event.target.value});
        else applyFilter({country: event.target.value});
    });
    byId('time-filter').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({timeWindow: event.target.value});
        else applyFilter({timeWindow: event.target.value});
    });
    byId('sort-filter').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({sort: event.target.value});
        else applyFilter({sort: event.target.value});
    });
    byId('hide-finished').addEventListener('change', event => {
        if (filterDialog?.open) updateFilterDraft({hideFinished: event.target.checked});
        else applyFilter({hideFinished: event.target.checked});
    });
    document.querySelector('.status-filters').addEventListener('click', event => {
        const button = event.target.closest('[data-status]');
        if (!button) return;
        applyFilter({status: button.dataset.status});
    });
    byId('fixture-search').addEventListener('input', event => {
        clearTimeout(searchTimer);
        const query = event.target.value;
        byId('clear-search').hidden = !query;
        searchTimer = setTimeout(() => {
            searchTimer = null;
            applyFilter({query}, {historyMode: 'replace'});
        }, 150);
    });
    byId('clear-search').addEventListener('click', () => {
        cancelPendingSearch();
        applyFilter({query: ''}, {historyMode: 'replace'});
    });
    byId('clear-filters').addEventListener('click', () => {
        const patch = {
            competition: '',
            country: '',
            timeWindow: 'all',
            hideFinished: false,
            sort: 'kickoff',
            timezone: state.timezone,
        };
        if (filterDialog?.open) updateFilterDraft(patch);
        else applyFilter({...patch, status: 'all', query: ''});
    });
    byId('score-toggle').addEventListener('click', () => {
        scoresRevealed = !scoresRevealed;
        writeScorePreference(window.sessionStorage, scoresRevealed);
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
            setState({fixture: selectedFixtureId}, {reason: 'fixture'});
            syncUrl('push');
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
        // The panel may currently be showing a different fixture than the
        // one this URL names (or none at all), so it is reconciled here —
        // but only when the restored selection actually differs from what's
        // displayed. `select-fixture` (below) already follows this pattern:
        // it switches panels with open() alone, no reset() first. Resetting
        // unconditionally would tear the panel down to its placeholder and
        // rebuild it even when nothing changed (e.g. Back after an
        // unrelated filter/sort change that left the same fixture
        // selected), which is pure churn and drops any focus placed inside
        // the panel with nothing to restore it.
        const previousFixtureId = selectedFixtureId;
        selectedFixtureId = state.fixture || null;
        if (selectedFixtureId !== previousFixtureId) matchContext?.reset();
        syncControls();
        if (previous.date !== state.date || previous.timezone !== state.timezone) {
            loadFixtures();
        } else {
            reflectCurrentResults();
        }
    });
    byId('refresh-fixtures').addEventListener('click', () => refreshController?.refresh('manual'));
}

renderDateStrip();

function init() {
    const dialogManager = createDialogManager();
    matchContext = createMatchContext({
        panel: byId('match-context'),
        panelContent: byId('match-context-content'),
        dialog: byId('match-context-dialog'),
        dialogContent: byId('match-context-dialog-content'),
        closeButton: byId('close-match-context'),
        getRevealed: () => scoresRevealed,
        getTimezone: () => state.timezone,
        onClose: () => {
            const closedFixtureId = selectedFixtureId;
            selectedFixtureId = null;
            matchContext?.reset();
            if (state.fixture) {
                setState({fixture: ''}, {reason: 'close-fixture'});
                syncUrl('replace');
            }
            reflectCurrentResults();
            if (closedFixtureId) {
                byId('fixture-stream').querySelector(
                    `.details-button[data-fixture-id="${CSS.escape(closedFixtureId)}"]`,
                )?.focus();
            }
        },
        dialogManager,
    });
    timezoneControl = createTimezoneControl({
        root: byId('timezone-control'),
        getTimeZone: () => state.timezone,
        onChange: applyTimezone,
    });
    bindFilterDialog(dialogManager);
    syncUrl('replace');
    syncControls();
    bindEvents();
    refreshController = createRefreshController({
        load: loadFixtures,
        getContext: () => ({
            date: state.date,
            matches: payload?.matches || [],
            timezone: state.timezone,
        }),
    });
    loadFixtures().finally(() => refreshController.start());
}

init();
