import {
    createState,
    filterMatches,
    groupMatches,
    shiftDate,
    summarizeMatches,
    todayLocal,
} from './fixture-state.js';
import {
    readScorePreference,
    syncScoreToggle,
    writeScorePreference,
} from './score-preference.js';
import {
    renderFeatured,
    renderEmptyState,
    renderFixtureStream,
    renderLoading,
    renderNotice,
    renderRequestError,
    renderSummary,
} from './fixture-renderer.js';
import {createMatchContext} from './match-context.js';

const byId = id => document.getElementById(id);
const state = createState(window.location.search);
let payload = null;
let scoresRevealed = readScorePreference();
let searchTimer = null;
const expandedGroups = new Set();
let selectedFixtureId = null;
let activeRequestController = null;
let requestSequence = 0;
let matchContext = null;

function syncUrl() {
    const query = state.toSearchParams().toString();
    history.replaceState(null, '', `${location.pathname}?${query}`);
}

function syncControls() {
    byId('dashboard-date').value = state.date;
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
        + Number(state.status !== 'all')
        + Number(Boolean(state.query));
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
    if (state.competition && names.includes(state.competition)) select.value = state.competition;
}

function reflectCurrentResults() {
    if (!payload) return;
    const matches = filterMatches(payload.matches, state);
    const summary = summarizeMatches(matches);
    renderSummary(byId('daily-summary'), payload.matches, payload);
    renderNotice(byId('data-notice'), payload);
    renderFeatured(byId('featured-match'), matches, scoresRevealed);
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
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        const requestedDate = state.date;
        const response = await fetch(`/api/matches-today?date=${encodeURIComponent(requestedDate)}&timezone=${encodeURIComponent(timezone)}`, {
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

function applyFilter(patch) {
    state.set(patch);
    syncControls();
    syncUrl();
    reflectCurrentResults();
}

function chooseDate(date) {
    state.set({date});
    selectedFixtureId = null;
    matchContext?.reset();
    syncControls();
    syncUrl();
    loadFixtures();
}

function bindEvents() {
    byId('previous-date').addEventListener('click', () => chooseDate(shiftDate(state.date, -1)));
    byId('today-date').addEventListener('click', () => chooseDate(todayLocal()));
    byId('next-date').addEventListener('click', () => chooseDate(shiftDate(state.date, 1)));
    byId('dashboard-date').addEventListener('change', event => chooseDate(event.target.value));
    byId('competition-filter').addEventListener('change', event => applyFilter({competition: event.target.value}));
    document.querySelector('.status-filters').addEventListener('click', event => {
        const button = event.target.closest('[data-status]');
        if (button) applyFilter({status: button.dataset.status});
    });
    byId('fixture-search').addEventListener('input', event => {
        clearTimeout(searchTimer);
        const query = event.target.value;
        byId('clear-search').hidden = !query;
        searchTimer = setTimeout(() => applyFilter({query}), 150);
    });
    byId('clear-search').addEventListener('click', () => applyFilter({query: ''}));
    byId('clear-filters').addEventListener('click', () => applyFilter({competition: '', status: 'all', query: ''}));
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
            const match = payload?.matches?.find(item => String(item.id) === selectedFixtureId);
            const replacement = byId('fixture-stream').querySelector(
                `.details-button[data-fixture-id="${CSS.escape(selectedFixtureId)}"]`,
            );
            if (match && replacement) matchContext.open(match, replacement);
        } else if (action.dataset.action === 'clear-filters') {
            applyFilter({competition: '', status: 'all', query: ''});
        } else if (action.dataset.action === 'shift-date') {
            chooseDate(shiftDate(state.date, Number(action.dataset.days)));
        }
    };
    byId('fixture-stream').addEventListener('click', fixtureAction);
    byId('featured-match').addEventListener('click', fixtureAction);
}

function init() {
    matchContext = createMatchContext({
        panel: byId('match-context'),
        panelContent: byId('match-context-content'),
        dialog: byId('match-context-dialog'),
        dialogContent: byId('match-context-dialog-content'),
        closeButton: byId('close-match-context'),
        getRevealed: () => scoresRevealed,
        onTeam: () => {},
    });
    syncControls();
    bindEvents();
    loadFixtures();
}

init();
