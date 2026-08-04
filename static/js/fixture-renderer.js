const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [crestModule, fixtureStateModule, scorePreferenceModule] = await Promise.all([
    import(versionedModule('./crest.js')),
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
]);
const {createCrest} = crestModule;
const {selectFeatured, statusKind, statusValue, summarizeMatches} = fixtureStateModule;
const {validScore} = scorePreferenceModule;

const GROUP_PREVIEW_LIMIT = 6;
const SVG_NS = 'http://www.w3.org/2000/svg';

function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== '') element.textContent = text;
    return element;
}

function icon(paths, className = 'icon') {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', className);
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    for (const definition of paths) {
        const path = document.createElementNS(SVG_NS, 'path');
        path.setAttribute('d', definition);
        svg.append(path);
    }
    return svg;
}

function eyeOffIcon() {
    return icon([
        'M3 3l18 18',
        'M10.6 10.7a2 2 0 0 0 2.7 2.7',
        'M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9 5.2 9 5.2a15 15 0 0 1-2.1 2.6',
        'M6.6 6.6C4.4 8 3 10 3 10s3.5 5 9 5c1.2 0 2.3-.2 3.3-.6',
    ]);
}

function detailsIcon() {
    return icon(['M9 18l6-6-6-6']);
}

export function formatKickoff(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Time TBC';
    return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

function formatDate(value) {
    const date = new Date(`${value}T12:00:00`);
    if (Number.isNaN(date.getTime())) return 'Selected date';
    return date.toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'});
}

function statusLabel(match) {
    const status = statusValue(match);
    if (status === 'PAUSED' || status === 'HALFTIME') return 'HT';
    const kind = statusKind(match);
    if (kind === 'live') return 'LIVE';
    if (kind === 'finished') return 'FT';
    if (kind === 'postponed') return 'POSTPONED';
    if (kind === 'cancelled') return 'CANCELLED';
    if (kind === 'suspended') return 'SUSPENDED';
    return 'UPCOMING';
}

function statusDescription(match) {
    const label = statusLabel(match);
    if (label === 'LIVE') return 'Live now';
    if (label === 'HT') return 'Half-time';
    if (label === 'FT') return 'Full-time';
    return label.charAt(0) + label.slice(1).toLocaleLowerCase();
}

export function createScoreNode(match, revealed, {featured = false} = {}) {
    const score = node('div', featured ? 'score-display score-display--featured' : 'score-display');
    const kind = statusKind(match);
    if (kind === 'upcoming') {
        score.classList.add('score-display--kickoff');
        score.textContent = formatKickoff(match?.utcDate);
        return score;
    }
    if (!['live', 'finished'].includes(kind)) {
        score.classList.add('score-display--state');
        score.textContent = statusDescription(match);
        return score;
    }
    if (!revealed) {
        score.classList.add('score-display--hidden');
        score.append(eyeOffIcon(), node('span', '', 'Score hidden'));
        return score;
    }
    const values = validScore(match);
    if (!values) {
        score.classList.add('score-display--unavailable');
        score.textContent = 'Score unavailable';
        return score;
    }
    score.classList.add('score-display--revealed');
    score.textContent = `${values.home} – ${values.away}`;
    return score;
}

function createTeamIdentity(team, {featured = false} = {}) {
    const identity = node('div', featured ? 'team-identity team-identity--featured' : 'team-identity');
    identity.append(
        createCrest(team, {size: featured ? 52 : 32, lazy: !featured, className: featured ? 'team-crest--featured' : ''}),
        node('span', 'team-name', team?.name || 'Team unavailable'),
    );
    return identity;
}

function createTeamRows(match) {
    const teams = node('div', 'fixture-teams');
    const home = node('div', 'team-row team-row--home');
    const away = node('div', 'team-row team-row--away');
    home.append(createTeamIdentity(match?.homeTeam));
    away.append(createTeamIdentity(match?.awayTeam));
    teams.append(home, away);
    return teams;
}

function fixtureId(match) {
    return String(match?.canonicalFixtureId || match?.id || `${match?.homeTeam?.name || 'home'}-${match?.awayTeam?.name || 'away'}-${match?.utcDate || ''}`);
}

function createDetailsButton(match, featured = false) {
    const label = featured ? 'Open match details' : 'Details';
    const button = node('button', featured ? 'details-button details-button--featured' : 'details-button');
    button.type = 'button';
    button.dataset.action = 'select-fixture';
    button.dataset.fixtureId = fixtureId(match);
    button.setAttribute('aria-label', `Open match details for ${match?.homeTeam?.name || 'home team'} and ${match?.awayTeam?.name || 'away team'}`);
    button.append(node('span', '', label), detailsIcon());
    return button;
}

function createFixtureCard(match, revealed, selectedId = null) {
    const id = fixtureId(match);
    const kind = statusKind(match);
    const card = node('article', `fixture-card fixture-card--${kind}`);
    card.dataset.fixtureId = id;
    if (selectedId === id) {
        card.classList.add('is-selected');
        card.setAttribute('aria-current', 'true');
    }

    const status = node('div', 'fixture-status');
    const label = node('span', 'fixture-status-label', statusLabel(match));
    if (kind === 'live') label.prepend(node('span', 'live-dot'));
    status.append(label);
    if (kind !== 'upcoming') status.append(node('span', 'fixture-kickoff', formatKickoff(match?.utcDate)));

    const action = node('div', 'fixture-action');
    action.append(createDetailsButton(match));
    const mobileMeta = node('span', 'fixture-mobile-meta', match?.competition?.name || 'Competition');
    card.append(status, createTeamRows(match), createScoreNode(match, revealed), mobileMeta, action);
    return card;
}

function createCompetitionIdentity(competition) {
    const identity = node('div', 'competition-identity');
    const emblemTeam = {name: competition?.name || 'Competition', crest: competition?.emblem};
    identity.append(createCrest(emblemTeam, {size: 28, lazy: true, className: 'competition-emblem'}));
    const text = node('div', 'competition-copy');
    text.append(node('h3', 'competition-name', competition?.name || 'Other competition'));
    const area = competition?.area?.name;
    if (area) text.append(node('p', 'competition-area', area));
    identity.append(text);
    return identity;
}

function createCompetitionGroup(group, options) {
    const {revealed, expandedGroups, selectedId} = options;
    const section = node('section', 'competition-group');
    const contentId = `competition-${group.key.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
    section.dataset.competition = group.key;

    const header = node('div', 'competition-header');
    header.append(createCompetitionIdentity(group.competition));
    const meta = node('div', 'competition-meta');
    const count = group.matches.length;
    meta.append(node('span', 'competition-count', `${count} ${count === 1 ? 'match' : 'matches'}`));
    const expandable = count > GROUP_PREVIEW_LIMIT;
    const expanded = expandedGroups.has(group.key);
    if (expandable) {
        const toggle = node('button', 'competition-toggle', expanded ? 'Show fewer' : `Show all ${count} matches`);
        toggle.type = 'button';
        toggle.dataset.action = 'toggle-group';
        toggle.dataset.group = group.key;
        toggle.setAttribute('aria-expanded', String(expanded));
        toggle.setAttribute('aria-controls', contentId);
        meta.append(toggle);
    }
    header.append(meta);

    const fixtures = node('div', 'competition-fixtures');
    fixtures.id = contentId;
    const visible = expandable && !expanded ? group.matches.slice(0, GROUP_PREVIEW_LIMIT) : group.matches;
    fixtures.append(...visible.map(match => createFixtureCard(match, revealed, selectedId)));
    section.append(header, fixtures);
    return section;
}

export function renderLoading(container, count = 6) {
    container.setAttribute('aria-busy', 'true');
    const rows = Array.from({length: count}, () => {
        const row = node('article', 'fixture-skeleton');
        row.dataset.skeleton = 'fixture';
        row.setAttribute('aria-hidden', 'true');
        row.append(
            node('span', 'skeleton skeleton-time'),
            node('span', 'skeleton skeleton-teams'),
            node('span', 'skeleton skeleton-score'),
        );
        return row;
    });
    container.replaceChildren(...rows);
}

export function renderSummary(container, matches, payload) {
    const summary = summarizeMatches(matches);
    const items = [
        ['summary-primary', `${summary.total} ${summary.total === 1 ? 'match' : 'matches'}`],
        ['summary-live', `${summary.live} live`],
        ['summary-upcoming', `${summary.upcoming} upcoming`],
        ['summary-finished', `${summary.finished} finished`],
    ].map(([className, text]) => node('span', className, text));
    if (payload?.last_updated) {
        const updated = new Date(payload.last_updated);
        if (!Number.isNaN(updated.getTime())) {
            items.push(node('span', 'summary-updated', `Updated ${updated.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`));
        }
    }
    container.replaceChildren(...items);
    const dateLabel = document.getElementById('selected-date-label');
    if (dateLabel) dateLabel.textContent = formatDate(payload?.date);
}

export function renderNotice(container, payload) {
    container.hidden = true;
    container.replaceChildren();
    if (!payload?.partial && !payload?.stale) return;
    const title = payload.stale ? 'Showing saved fixture data' : 'Some fixture sources are delayed';
    const detail = payload.stale
        ? 'Live updates may be behind while providers recover.'
        : 'Available matches are shown while another provider reconnects.';
    container.append(node('strong', '', title), node('span', '', detail));
    container.dataset.state = payload.stale ? 'stale' : 'partial';
    container.hidden = false;
}

export function renderFeatured(container, matches, revealed) {
    const match = selectFeatured(matches);
    container.replaceChildren();
    if (!match) {
        container.hidden = true;
        return;
    }
    const kind = statusKind(match);
    const header = node('div', 'featured-header');
    const label = kind === 'live' ? 'Live now' : (kind === 'upcoming' ? 'Next up' : 'Latest result');
    header.append(
        node('span', 'featured-label', label),
        node('span', 'featured-competition', match?.competition?.name || 'Competition'),
    );
    const teams = node('div', 'featured-teams');
    teams.append(
        createTeamIdentity(match?.homeTeam, {featured: true}),
        createScoreNode(match, revealed, {featured: true}),
        createTeamIdentity(match?.awayTeam, {featured: true}),
    );
    const footer = node('div', 'featured-footer');
    footer.append(node('span', 'featured-status', `${statusDescription(match)} · ${formatKickoff(match?.utcDate)}`), createDetailsButton(match, true));
    container.append(header, teams, footer);
    container.hidden = false;
}

export function renderFixtureStream(container, groups, options) {
    container.setAttribute('aria-busy', 'false');
    container.replaceChildren(...groups.map(group => createCompetitionGroup(group, options)));
}

export function renderEmptyState(container, {filtered = false} = {}) {
    const state = node('div', 'dashboard-state dashboard-state--empty');
    if (filtered) {
        state.append(
            node('h3', '', 'No fixtures match these filters'),
            node('p', '', 'Try another team, competition, or match status.'),
        );
        const clear = node('button', 'control-button', 'Clear filters');
        clear.type = 'button';
        clear.dataset.action = 'clear-filters';
        state.append(clear);
    } else {
        state.append(
            node('h3', '', 'No matches scheduled'),
            node('p', '', 'There are no tracked fixtures on this date. Try an adjacent day.'),
        );
        const actions = node('div', 'empty-actions');
        const previous = node('button', 'control-button', 'Previous day');
        previous.type = 'button';
        previous.dataset.action = 'shift-date';
        previous.dataset.days = '-1';
        const next = node('button', 'control-button', 'Next day');
        next.type = 'button';
        next.dataset.action = 'shift-date';
        next.dataset.days = '1';
        actions.append(previous, next);
        state.append(actions);
    }
    container.replaceChildren(state);
    container.setAttribute('aria-busy', 'false');
}

export function renderRequestError(container, onRetry, {kind = 'unavailable', retryAfterSeconds = null} = {}) {
    const copy = {
        invalid_request: ['Check the fixture request', 'The selected date or timezone is not valid.'],
        rate_limited: ['Fixture updates are temporarily limited', retryAfterSeconds ? `Try again in about ${retryAfterSeconds} seconds.` : 'Please wait a moment before trying again.'],
        offline: ['You appear to be offline', 'Reconnect to refresh fixture data.'],
        timeout: ['Fixture providers are taking too long', 'The request timed out before providers completed.'],
        format: ['Fixture data could not be read', 'A provider returned an unexpected response.'],
        unavailable: ['Football data is temporarily unavailable', 'The fixture providers did not respond. Try the request again.'],
    }[kind] || ['Football data is temporarily unavailable', 'The fixture providers did not respond. Try the request again.'];
    const state = node('div', 'dashboard-state dashboard-state--error');
    state.append(
        node('h3', '', copy[0]),
        node('p', '', copy[1]),
    );
    const retry = node('button', 'control-button', 'Retry');
    retry.type = 'button';
    retry.addEventListener('click', onRetry, {once: true});
    state.append(retry);
    container.replaceChildren(state);
    container.setAttribute('aria-busy', 'false');
}

export function renderUpdateFailure(container, {kind = 'unavailable'} = {}) {
    const detail = kind === 'offline'
        ? 'Showing the last loaded fixtures while this device is offline.'
        : 'Showing the last loaded fixtures while the next update is retried.';
    container.replaceChildren(node('strong', '', 'Live update delayed'), node('span', '', detail));
    container.dataset.state = 'update-delayed';
    container.hidden = false;
}
