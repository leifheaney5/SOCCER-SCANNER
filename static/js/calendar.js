const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path;
const [stateModule, scoreModule, rendererModule, timeZoneModule] = await Promise.all([
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
    import(versionedModule('./fixture-renderer.js')),
    import(versionedModule('./time-zone.js')),
]);
const {isValidDate, isValidTimezone, shiftDate, todayLocal} = stateModule;
const {readScorePreference, syncScoreToggle, writeScorePreference} = scoreModule;
const {createScoreNode, setRenderTimeZone} = rendererModule;
const {formatFixtureDate} = timeZoneModule;

const byId = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
let timezone = isValidTimezone(params.get('timezone')) ? params.get('timezone') : detectedTimezone;
let start = isValidDate(params.get('start')) ? params.get('start') : todayLocal(new Date(), timezone);
let view = params.get('view') === 'grid' ? 'grid' : 'agenda';
let revealed = readScorePreference();
let controller = null;
let sequence = 0;
let activeDates = [];
const dayStates = new Map();
const dayGenerations = new Map();

function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== '') element.textContent = text;
    return element;
}

function dates() {
    return Array.from({length: 7}, (_, index) => shiftDate(start, index));
}

function syncUrl() {
    const query = new URLSearchParams({start, timezone});
    if (view === 'grid') query.set('view', 'grid');
    history.replaceState({calendar: true}, '', `/calendar?${query}`);
}

function syncControls() {
    byId('calendar-start').value = start;
    const select = byId('calendar-timezone');
    if (![...select.options].some(option => option.value === timezone)) {
        select.add(new Option(timezone.replaceAll('_', ' '), timezone));
    }
    select.value = timezone;
    byId('calendar-view-agenda').setAttribute('aria-pressed', String(view === 'agenda'));
    byId('calendar-view-grid').setAttribute('aria-pressed', String(view === 'grid'));
    byId('calendar-results').dataset.view = view;
    syncScoreToggle(byId('score-toggle'), revealed);
    setRenderTimeZone(timezone);
}

function dayLabel(date) {
    return formatFixtureDate(date, timezone, {month: 'short'});
}

function retryButton(date, label) {
    const button = node('button', 'calendar-retry', 'Retry');
    button.type = 'button';
    button.setAttribute('aria-label', `Retry fixtures for ${label}`);
    button.addEventListener('click', () => retryDay(date));
    return button;
}

function renderDay(date) {
    const result = dayStates.get(date) || {state: 'loading', date, matches: []};
    const section = node('section', 'calendar-day');
    section.dataset.date = date;
    section.dataset.state = result.state;
    const label = dayLabel(date);
    const heading = node('header');
    const headingTitle = node('h2', '', label);
    headingTitle.id = `calendar-day-${date}`;
    heading.append(headingTitle);
    if (result.state === 'success' || result.state === 'partial' || result.state === 'stale') {
        heading.append(node('span', 'calendar-day-count', `${result.matches.length} matches`));
    }
    const list = node('div', 'calendar-fixtures');
    list.setAttribute('aria-labelledby', headingTitle.id);
    if (result.state === 'loading') {
        list.append(node('p', 'calendar-day-message', 'Loading fixtures…'));
    } else if (result.state === 'empty') {
        list.append(node('p', 'calendar-empty', 'No matches scheduled'));
    } else if (result.state === 'error' || result.state === 'rate_limited' || result.state === 'network') {
        const message = result.state === 'rate_limited'
            ? 'Fixtures are rate limited for this day.'
            : result.state === 'network'
                ? 'Network unavailable for this day.'
                : 'Fixtures temporarily unavailable for this day.';
        const error = node('div', 'calendar-day-message', message);
        error.append(retryButton(date, label));
        list.append(error);
    } else {
        if (result.state === 'partial' || result.state === 'stale') {
            list.append(node(
                'p',
                'calendar-day-notice',
                result.state === 'stale' ? 'Showing saved fixture data.' : 'Some fixture sources are delayed.',
            ));
        }
        for (const match of result.matches) {
            const card = node('article', 'calendar-fixture');
            const teams = node('div', 'calendar-teams');
            teams.append(node('span', '', match?.homeTeam?.name || 'Home team'), node('span', '', match?.awayTeam?.name || 'Away team'));
            const score = createScoreNode(match, revealed);
            score.classList.add('calendar-score');
            card.append(teams, score);
            list.append(card);
        }
        if (!result.matches.length) list.append(node('p', 'calendar-empty', 'No matches scheduled'));
    }
    section.append(heading, list);
    return section;
}

function renderResults() {
    setRenderTimeZone(timezone);
    byId('calendar-results').replaceChildren(...activeDates.map(renderDay));
}

function updateStatus() {
    const states = activeDates.map(date => dayStates.get(date)?.state);
    const loading = states.filter(state => state === 'loading').length;
    const failed = states.filter(state => ['error', 'rate_limited', 'network'].includes(state)).length;
    const successful = states.filter(state => ['success', 'empty', 'partial', 'stale'].includes(state)).length;
    byId('calendar-status').textContent = loading
        ? `Loading ${loading} day${loading === 1 ? '' : 's'}`
        : failed === activeDates.length
            ? 'Calendar unavailable'
            : failed
                ? `${successful} days loaded; ${failed} need attention`
                : '7 days loaded';
}

async function mapLimit(items, limit, operation) {
    const results = new Array(items.length);
    let next = 0;
    async function worker() {
        while (next < items.length) {
            const index = next++;
            results[index] = await operation(items[index]);
        }
    }
    await Promise.all(Array.from({length: Math.min(limit, items.length)}, worker));
    return results;
}

async function loadDay(date, requestId, signal) {
    const generation = (dayGenerations.get(date) || 0) + 1;
    dayGenerations.set(date, generation);
    try {
        const response = await fetch(`/api/v2/fixtures?date=${encodeURIComponent(date)}&timezone=${encodeURIComponent(timezone)}`, {signal});
        let payload = null;
        try {
            payload = await response.json();
        } catch {
            payload = null;
        }
        if (!response.ok) {
            const state = response.status === 429 ? 'rate_limited' : 'error';
            throw Object.assign(new Error('Calendar fixture request failed'), {state});
        }
        if (requestId !== sequence || dayGenerations.get(date) !== generation) return;
        const matches = Array.isArray(payload?.matches) ? payload.matches : [];
        const state = payload?.stale ? 'stale' : payload?.partial ? 'partial' : matches.length ? 'success' : 'empty';
        dayStates.set(date, {state, date, matches, payload});
    } catch (error) {
        if (error?.name === 'AbortError' || requestId !== sequence || dayGenerations.get(date) !== generation) return;
        dayStates.set(date, {
            state: error.state || (navigator.onLine ? 'error' : 'network'),
            date,
            matches: [],
            error,
        });
    }
    renderResults();
    updateStatus();
}

async function loadWindow() {
    controller?.abort();
    controller = new AbortController();
    const requestId = ++sequence;
    activeDates = dates();
    dayStates.clear();
    for (const date of activeDates) {
        dayGenerations.set(date, 0);
        dayStates.set(date, {state: 'loading', date, matches: []});
    }
    byId('calendar-results').setAttribute('aria-busy', 'true');
    renderResults();
    updateStatus();
    await mapLimit(activeDates, 3, date => loadDay(date, requestId, controller.signal));
    if (requestId !== sequence) return;
    byId('calendar-results').setAttribute('aria-busy', 'false');
    renderResults();
    updateStatus();
}

function retryDay(date) {
    if (!activeDates.includes(date)) return;
    dayStates.set(date, {state: 'loading', date, matches: []});
    renderResults();
    updateStatus();
    loadDay(date, sequence, controller?.signal || new AbortController().signal);
}

function chooseStart(value) {
    if (!isValidDate(value)) return;
    start = value;
    syncControls();
    syncUrl();
    loadWindow();
}

byId('calendar-previous').addEventListener('click', () => chooseStart(shiftDate(start, -7)));
byId('calendar-today').addEventListener('click', () => chooseStart(todayLocal(new Date(), timezone)));
byId('calendar-next').addEventListener('click', () => chooseStart(shiftDate(start, 7)));
byId('calendar-start').addEventListener('change', event => chooseStart(event.target.value));
byId('calendar-timezone').addEventListener('change', event => {
    timezone = event.target.value;
    syncControls();
    syncUrl();
    loadWindow();
});
for (const mode of ['agenda', 'grid']) {
    byId(`calendar-view-${mode}`).addEventListener('click', () => {
        view = mode;
        syncControls();
        syncUrl();
    });
}
byId('score-toggle').addEventListener('click', () => {
    revealed = !revealed;
    writeScorePreference(sessionStorage, revealed);
    syncControls();
    renderResults();
});

syncControls();
syncUrl();
loadWindow();
