import {
    createState,
    filterMatches,
    shiftDate,
    summarizeMatches,
    todayLocal,
} from './fixture-state.js';
import {
    readScorePreference,
    syncScoreToggle,
    writeScorePreference,
} from './score-preference.js';

const byId = id => document.getElementById(id);
const state = createState(window.location.search);
let payload = null;
let scoresRevealed = readScorePreference();
let searchTimer = null;

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
    byId('fixture-result-count').textContent = `${summary.total} ${summary.total === 1 ? 'match' : 'matches'}`;
    byId('dashboard-status').textContent = `${summary.total} fixtures shown`;
}

async function loadFixtures() {
    byId('dashboard-status').textContent = 'Loading fixtures';
    try {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        const response = await fetch(`/api/matches-today?date=${encodeURIComponent(state.date)}&timezone=${encodeURIComponent(timezone)}`);
        if (!response.ok) throw new Error('Fixture request failed');
        payload = await response.json();
        if (!Array.isArray(payload.matches)) payload.matches = [];
        populateCompetitions(payload.matches);
        syncControls();
        reflectCurrentResults();
    } catch {
        byId('dashboard-status').textContent = 'Football data is temporarily unavailable';
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
    });
}

function init() {
    syncControls();
    bindEvents();
    loadFixtures();
}

init();
