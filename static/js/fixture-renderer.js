const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [crestModule, fixtureStateModule, scorePreferenceModule, statusModule, timeZoneModule] = await Promise.all([
    import(versionedModule('./crest.js')),
    import(versionedModule('./fixture-state.js')),
    import(versionedModule('./score-preference.js')),
    import(versionedModule('./match-status.js')),
    import(versionedModule('./time-zone.js')),
]);
const {createCrest} = crestModule;
const {selectFeatured, statusKind, statusValue, summarizeMatches} = fixtureStateModule;
const {validScore} = scorePreferenceModule;
const {describeStatus, statusShortLabel, statusLabel: canonicalStatusLabel} = statusModule;
const {
    formatKickoff: formatKickoffInZone,
    formatFixtureDate,
    formatDateTime,
    resolveTimeZone,
} = timeZoneModule;

// The selected zone is page-level state; every renderer entry point reads it
// rather than each signature threading it through.
let activeTimeZone = 'UTC';

export function setRenderTimeZone(timeZone) {
    activeTimeZone = resolveTimeZone(timeZone, activeTimeZone);
    return activeTimeZone;
}

export function renderTimeZone() {
    return activeTimeZone;
}

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

export function formatKickoff(value, timeZone = activeTimeZone) {
    return formatKickoffInZone(value, timeZone);
}

function formatDate(value) {
    return formatFixtureDate(value, activeTimeZone);
}

// HT, ET, PEN, DELAYED, POSTPONED and ABANDONED all come from the canonical
// taxonomy instead of collapsing into a generic LIVE/UPCOMING badge.
function statusLabel(match) {
    return statusShortLabel(match);
}

function statusDescription(match) {
    return canonicalStatusLabel(match);
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
    home.append(createTeamIdentity(match?.homeTeam), createPinButton('team', match?.homeTeam?.canonicalId || match?.homeTeam?.name));
    away.append(createTeamIdentity(match?.awayTeam), createPinButton('team', match?.awayTeam?.canonicalId || match?.awayTeam?.name));
    teams.append(home, away);
    return teams;
}

function pinKey(kind, value) {
    return `${kind}:${String(value || '').trim().toLocaleLowerCase()}`;
}

function readPins() {
    try {
        return new Set(JSON.parse(sessionStorage.getItem('soccer-scanner:pins') || '[]'));
    } catch {
        return new Set();
    }
}

function createPinButton(kind, value) {
    const button = node('button', 'pin-button');
    const key = pinKey(kind, value);
    const pinned = Boolean(value) && readPins().has(key);
    button.type = 'button';
    button.dataset.action = 'toggle-pin';
    button.dataset.pinKind = kind;
    button.dataset.pinValue = String(value || '');
    button.dataset.pinned = String(pinned);
    button.setAttribute('aria-pressed', String(pinned));
    button.setAttribute('aria-label', `${pinned ? 'Unpin' : 'Pin'} ${kind}`);
    button.textContent = pinned ? 'Pinned' : 'Pin';
    button.disabled = !value;
    return button;
}

function fixtureId(match) {
    return String(match?.canonicalFixtureId || match?.id || `${match?.homeTeam?.name || 'home'}-${match?.awayTeam?.name || 'away'}-${match?.utcDate || ''}`);
}

export function formatFreshness(value, now = new Date()) {
    const updated = new Date(value);
    if (Number.isNaN(updated.getTime())) return '';
    const elapsedSeconds = Math.max(0, Math.floor((now.getTime() - updated.getTime()) / 1000));
    if (elapsedSeconds < 60) return 'Updated just now';
    const elapsedMinutes = Math.floor(elapsedSeconds / 60);
    if (elapsedMinutes < 60) return `Updated ${elapsedMinutes}m ago`;
    const elapsedHours = Math.floor(elapsedMinutes / 60);
    if (elapsedHours < 24) return `Updated ${elapsedHours}h ago`;
    const elapsedDays = Math.floor(elapsedHours / 24);
    return `Updated ${elapsedDays}d ago`;
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

// Older cached payloads (from before the streaming registry existed) carry
// only the raw provider-reported broadcast names, with no verified service
// or region attached. Those names are shown as plain, unlinked text so the
// section does not disappear for a visitor with a warm cache.
function legacyStreamingServiceNames(match) {
    const seen = new Set();
    const names = [];
    for (const item of (Array.isArray(match?.broadcasts) ? match.broadcasts : [])) {
        if (item?.type !== 'STREAMING' || typeof item?.name !== 'string') continue;
        const name = item.name.trim();
        const key = name.toLocaleLowerCase();
        if (!name || seen.has(key)) continue;
        seen.add(key);
        names.push(name);
    }
    return names;
}

// Reads the enriched `match.streaming` array produced by the streaming
// registry (id, displayName, region, regionKnown, officialUrl, source).
// Returns null when the payload predates enrichment, signalling the caller
// to fall back to the raw broadcast names instead.
function enrichedStreamingServices(match) {
    if (!Array.isArray(match?.streaming)) return null;
    return match.streaming.filter(
        item => item && typeof item.displayName === 'string' && item.displayName.trim(),
    );
}

function localLogoPath(value) {
    return typeof value === 'string' && value.startsWith('/static/') && !value.includes('://')
        ? value
        : null;
}

function createGenericStreamingIcon(size) {
    const icon = node('span', 'streaming-service-icon streaming-service-icon--generic');
    icon.style.setProperty('--streaming-icon-size', `${size}px`);
    icon.setAttribute('aria-hidden', 'true');
    return icon;
}

function createStreamingIcon(service, size = 18) {
    const logoPath = localLogoPath(service?.logoPath);
    if (!logoPath) return createGenericStreamingIcon(size);
    const image = node('img', 'streaming-service-icon streaming-service-icon--image');
    image.src = logoPath;
    image.alt = '';
    image.width = size;
    image.height = size;
    image.loading = 'lazy';
    image.decoding = 'async';
    image.setAttribute('aria-hidden', 'true');
    image.addEventListener('error', () => image.replaceWith(createGenericStreamingIcon(size)));
    return image;
}

// Normalizes both payload shapes into one array so callers (the card and the
// detail panel) never need to know which shape they received. Legacy
// entries carry no verified region or link — `region`/`officialUrl` stay
// null rather than guessing either.
export function resolveStreamingServices(match) {
    const enriched = enrichedStreamingServices(match);
    if (enriched !== null) return enriched;
    return legacyStreamingServiceNames(match).map(name => ({
        id: null,
        displayName: name,
        region: null,
        regionKnown: false,
        officialUrl: null,
        source: null,
    }));
}

function createStreamingNode(match) {
    const services = resolveStreamingServices(match);
    if (!services.length) return null;
    if (Array.isArray(match?.streaming)) {
        const [first, ...rest] = services;
        const label = `${first.displayName} · ${first.region}`;
        const summary = node('span', 'fixture-broadcast');
        summary.append(
            createStreamingIcon(first),
            node('span', '', rest.length ? `${label} +${rest.length}` : label),
        );
        const watchWhere = services.map(service => `${service.displayName} (${service.region})`).join(', ');
        summary.setAttribute('aria-label', `Watch on ${watchWhere}`);
        return summary;
    }
    const text = `Streaming: ${services.map(service => service.displayName).join(', ')}`;
    const summary = node('span', 'fixture-broadcast');
    summary.append(createStreamingIcon(services[0]), node('span', '', text));
    summary.setAttribute('aria-label', text);
    return summary;
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
    // The short badge is an abbreviation, so expose the full meaning to
    // assistive technology and on hover.
    label.title = describeStatus(match);
    label.setAttribute('aria-label', canonicalStatusLabel(match));
    if (kind === 'live') label.prepend(node('span', 'live-dot'));
    status.append(label);
    if (kind !== 'upcoming') status.append(node('span', 'fixture-kickoff', formatKickoff(match?.utcDate)));
    const freshness = formatFreshness(match?.sourceUpdatedAt || match?.lastUpdated);
    if (freshness) status.append(node('span', 'fixture-freshness', freshness));
    const streamingNode = createStreamingNode(match);

    const metadata = node('div', 'fixture-meta');
    const venue = match?.venue?.name || match?.venue;
    if (venue) metadata.append(node('span', 'fixture-venue', venue));
    const leg = match?.stage || match?.round || match?.aggregate;
    if (leg && !['REGULAR_SEASON', 'REGULAR'].includes(String(leg).toUpperCase())) {
        metadata.append(node('span', 'fixture-stage', leg));
    }

    const result = node('div', 'fixture-result');
    result.append(createScoreNode(match, revealed));
    if (streamingNode) result.append(streamingNode);

    const action = node('div', 'fixture-action');
    action.append(createDetailsButton(match));
    const mobileMeta = node('span', 'fixture-mobile-meta', match?.competition?.name || 'Competition');
    card.append(status, createTeamRows(match), result, metadata, mobileMeta, action);
    return card;
}

function competitionEmblem(competition) {
    if (competition?.emblem) return competition.emblem;
    if (/\bfriendly\b/i.test(competition?.name || '')) {
        return '/static/icons/competition-friendly.png';
    }
    return null;
}

function createCompetitionIdentity(competition) {
    const identity = node('div', 'competition-identity');
    const emblemTeam = {
        name: competition?.name || 'Competition',
        crest: competitionEmblem(competition),
    };
    identity.append(createCrest(emblemTeam, {
        size: 28,
        lazy: true,
        className: 'competition-emblem',
        allowLocal: true,
    }));
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
    meta.append(createPinButton('competition', group.competition?.canonicalId || group.competition?.name));
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
    const streamingCount = (Array.isArray(matches) ? matches : [])
        .filter(match => Array.isArray(match?.streaming) && match.streaming.length > 0).length;
    const sourcedCount = (Array.isArray(matches) ? matches : [])
        .filter(match => Array.isArray(match?.sources) && match.sources.length > 0).length;
    const items = [
        ['summary-primary', `${summary.total} ${summary.total === 1 ? 'match' : 'matches'}`],
        ['summary-live', `${summary.live} live`],
        ['summary-upcoming', `${summary.upcoming} upcoming`],
        ['summary-finished', `${summary.finished} finished`],
        ['summary-streaming', `${streamingCount} with streaming`],
        ['summary-sourced', `${sourcedCount} sourced`],
    ].map(([className, text]) => node('span', className, text));
    const lastUpdated = payload?.lastUpdated || payload?.last_updated;
    if (lastUpdated) {
        const updated = new Date(lastUpdated);
        if (!Number.isNaN(updated.getTime())) {
            items.push(node(
                'span',
                'summary-updated',
                `Updated ${formatDateTime(lastUpdated, activeTimeZone)} · ${activeTimeZone}`,
            ));
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
