const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path;
const [stateModule, scoreModule, rendererModule] = await Promise.all([
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
    import(versionedModule('./fixture-renderer.js')),
]);
const {isValidDate, isValidTimezone, shiftDate, todayLocal} = stateModule;
const {readScorePreference, syncScoreToggle, writeScorePreference} = scoreModule;
const {createScoreNode} = rendererModule;

const byId = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
let start = isValidDate(params.get('start')) ? params.get('start') : todayLocal();
let timezone = isValidTimezone(params.get('timezone')) ? params.get('timezone') : detectedTimezone;
let view = params.get('view') === 'grid' ? 'grid' : 'agenda';
let revealed = readScorePreference();
let controller = null;
let sequence = 0;

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

function renderDay(payload) {
    const section = node('section', 'calendar-day');
    const heading = node('header');
    const label = new Date(`${payload.date}T12:00:00`).toLocaleDateString([], {weekday: 'long', month: 'short', day: 'numeric'});
    heading.append(node('h2', '', label), node('span', 'calendar-day-count', `${payload.matches.length} matches`));
    const list = node('div', 'calendar-fixtures');
    if (!payload.matches.length) {
        list.append(node('p', 'calendar-empty', 'No matches scheduled'));
    } else {
        for (const match of payload.matches) {
            const card = node('article', 'calendar-fixture');
            const teams = node('div', 'calendar-teams');
            teams.append(node('span', '', match?.homeTeam?.name || 'Home team'), node('span', '', match?.awayTeam?.name || 'Away team'));
            const score = createScoreNode(match, revealed);
            score.classList.add('calendar-score');
            card.append(teams, score);
            list.append(card);
        }
    }
    section.append(heading, list);
    return section;
}

async function loadWindow() {
    controller?.abort();
    controller = new AbortController();
    const requestId = ++sequence;
    const windowDates = dates();
    byId('calendar-status').textContent = 'Loading 7 days';
    byId('calendar-results').setAttribute('aria-busy', 'true');
    try {
        const payloads = await mapLimit(windowDates, 3, async date => {
            const response = await fetch(`/api/v2/fixtures?date=${encodeURIComponent(date)}&timezone=${encodeURIComponent(timezone)}`, {signal: controller.signal});
            if (!response.ok) throw new Error('Calendar fixture request failed');
            const payload = await response.json();
            return {...payload, date, matches: Array.isArray(payload.matches) ? payload.matches : []};
        });
        if (requestId !== sequence) return;
        byId('calendar-results').replaceChildren(...payloads.map(renderDay));
        byId('calendar-results').setAttribute('aria-busy', 'false');
        byId('calendar-status').textContent = '7 days loaded';
    } catch (error) {
        if (error?.name === 'AbortError' || requestId !== sequence) return;
        byId('calendar-results').replaceChildren(node('div', 'calendar-error', 'Calendar fixtures are temporarily unavailable.'));
        byId('calendar-results').setAttribute('aria-busy', 'false');
        byId('calendar-status').textContent = 'Calendar unavailable';
    }
}

function chooseStart(value) {
    if (!isValidDate(value)) return;
    start = value;
    syncControls();
    syncUrl();
    loadWindow();
}

byId('calendar-previous').addEventListener('click', () => chooseStart(shiftDate(start, -7)));
byId('calendar-next').addEventListener('click', () => chooseStart(shiftDate(start, 7)));
byId('calendar-today').addEventListener('click', () => chooseStart(todayLocal()));
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
    loadWindow();
});

syncControls();
syncUrl();
loadWindow();
