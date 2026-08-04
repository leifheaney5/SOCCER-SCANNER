const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [crestModule, fixtureRendererModule] = await Promise.all([
    import(versionedModule('./crest.js')),
    import(versionedModule('./fixture-renderer.js')),
]);
const {createCrest} = crestModule;
const {createScoreNode, formatKickoff} = fixtureRendererModule;

function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== '') element.textContent = text;
    return element;
}

function focusableElements(dialog) {
    return [...dialog.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter(element => !element.hidden);
}

function renderSkeleton(content) {
    const skeleton = node('div', 'team-drawer-loading');
    skeleton.setAttribute('aria-label', 'Loading team intelligence');
    skeleton.append(...Array.from({length: 4}, () => {
        const row = node('div', 'team-drawer-skeleton');
        row.dataset.skeleton = 'team';
        row.setAttribute('aria-hidden', 'true');
        return row;
    }));
    content.replaceChildren(skeleton);
}

function statValue(stats, key, fallback = 0) {
    const value = stats?.[key];
    return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function createIdentity(data) {
    const team = data?.team_info || {};
    const identity = node('section', 'team-intelligence-identity');
    const copy = node('div', 'team-intelligence-copy');
    copy.append(node('h3', 'team-intelligence-name', team.name || 'Team intelligence'));
    const facts = node('div', 'team-facts');
    if (team.founded) facts.append(node('span', '', `Founded ${team.founded}`));
    if (team.venue) facts.append(node('span', '', team.venue));
    if (team.clubColors) facts.append(node('span', '', team.clubColors));
    if (!facts.children.length) facts.append(node('span', '', 'Club details unavailable'));
    copy.append(facts);
    identity.append(createCrest(team, {size: 56, lazy: false, className: 'team-crest--drawer'}), copy);
    return identity;
}

function createRecord(stats) {
    const section = node('section', 'team-section');
    section.append(node('h3', 'team-section-title', 'Season record'));
    const wins = statValue(stats, 'wins');
    const draws = statValue(stats, 'draws');
    const losses = statValue(stats, 'losses');
    const played = wins + draws + losses;
    const difference = statValue(stats, 'goal_difference', statValue(stats, 'goals_for') - statValue(stats, 'goals_against'));
    const values = [
        ['Played', `${played} played`],
        ['Wins', `${wins} wins`],
        ['Draws', `${draws} draws`],
        ['Losses', `${losses} losses`],
        ['Goals for', `${statValue(stats, 'goals_for')} goals for`],
        ['Goals against', `${statValue(stats, 'goals_against')} goals against`],
        ['Goal difference', `${difference > 0 ? '+' : ''}${difference} goal difference`],
    ];
    const grid = node('dl', 'record-grid');
    for (const [label, value] of values) {
        const item = node('div', 'record-stat');
        item.append(node('dt', '', label), node('dd', '', value));
        grid.append(item);
    }
    section.append(grid);

    const form = Array.isArray(stats?.form) ? stats.form.slice(0, 5) : [];
    if (form.length) {
        const formBlock = node('div', 'form-block');
        formBlock.append(node('h4', '', 'Recent form'));
        const sequence = node('div', 'form-sequence');
        const names = {W: 'Win', D: 'Draw', L: 'Loss'};
        for (const result of form) {
            const value = names[result] ? result : '?';
            const indicator = node('span', `form-result form-result--${value.toLocaleLowerCase()}`, value);
            indicator.setAttribute('aria-label', names[value] || 'Result unavailable');
            sequence.append(indicator);
        }
        formBlock.append(sequence);
        section.append(formBlock);
    }
    return section;
}

function createMatchList(title, matches, revealed, upcoming = false) {
    const section = node('section', 'team-section team-match-section');
    section.append(node('h3', 'team-section-title', title));
    const list = node('div', 'team-match-list');
    if (!matches.length) {
        list.append(node('p', 'section-empty', upcoming ? 'No upcoming matches available.' : 'No recent results available.'));
    } else {
        for (const match of matches.slice(0, 5)) {
            const item = node('article', 'team-match-row');
            const teams = node('div', 'team-match-teams');
            teams.append(
                node('span', '', match?.homeTeam?.name || 'Home team'),
                node('span', '', match?.awayTeam?.name || 'Away team'),
            );
            const meta = node('div', 'team-match-meta');
            meta.append(
                createScoreNode(match, revealed),
                node('span', 'team-match-kickoff', upcoming ? formatKickoff(match?.utcDate) : (match?.competition?.name || 'Competition')),
            );
            item.append(teams, meta);
            list.append(item);
        }
    }
    section.append(list);
    return section;
}

function createSquad(data) {
    const section = node('section', 'team-section');
    section.append(node('h3', 'team-section-title', 'Squad summary'));
    const squad = Array.isArray(data?.squad) ? data.squad : [];
    const summary = data?.top_performers?.squad_summary || {};
    const values = node('div', 'squad-summary');
    values.append(node('span', '', `${squad.length} ${squad.length === 1 ? 'player' : 'players'}`));
    if (data?.formation_data?.formation) values.append(node('span', '', data.formation_data.formation));
    if (summary.average_age) values.append(node('span', '', `${summary.average_age} average age`));
    section.append(values);
    return section;
}

function isLimited(data) {
    const team = data?.team_info || {};
    const stats = data?.stats || {};
    return !team.founded
        && !team.venue
        && !team.clubColors
        && Object.keys(stats).length === 0
        && !(data?.squad || []).length
        && !(data?.recent_matches || []).length
        && !(data?.upcoming_matches || []).length;
}

function renderTeam(content, data, revealed) {
    const sections = [createIdentity(data)];
    if (isLimited(data)) {
        const notice = node('div', 'team-data-notice');
        notice.append(node('strong', '', 'Limited team data'), node('span', '', 'The provider returned club identity only.'));
        sections.push(notice);
    }
    sections.push(
        createRecord(data?.stats || {}),
        createMatchList('Recent results', Array.isArray(data?.recent_matches) ? data.recent_matches : [], revealed),
        createMatchList('Upcoming matches', Array.isArray(data?.upcoming_matches) ? data.upcoming_matches : [], revealed, true),
        createSquad(data),
    );
    content.replaceChildren(...sections);
}

function renderError(content, retry) {
    const state = node('div', 'team-drawer-state team-drawer-state--error');
    state.append(
        node('h3', '', 'Team intelligence unavailable'),
        node('p', '', 'The team provider did not respond. Try the request again.'),
    );
    const button = node('button', 'control-button', 'Retry');
    button.type = 'button';
    button.addEventListener('click', retry, {once: true});
    state.append(button);
    content.replaceChildren(state);
}

function renderIdentityUnavailable(content, team) {
    const state = node('div', 'team-drawer-state team-drawer-state--unavailable');
    state.append(
        node('h3', '', 'Team intelligence unavailable'),
        node('p', '', `Verified provider mapping is not available for ${team?.name || 'this team'}.`),
    );
    content.replaceChildren(state);
}

export function createTeamDrawer({dialog, content, closeButton, getRevealed}) {
    const cache = new Map();
    const inFlight = new Map();
    let currentTeam = null;
    let currentData = null;
    let activeTrigger = null;

    function syncBodyLock() {
        document.body.classList.toggle('dialog-open', Boolean(document.querySelector('dialog[open]')));
    }

    function close() {
        if (dialog.open) dialog.close();
    }

    async function request(canonicalId, force = false) {
        if (!force && cache.has(canonicalId)) return cache.get(canonicalId);
        if (!force && inFlight.has(canonicalId)) return inFlight.get(canonicalId);
        const operation = fetch(`/api/v2/teams/${encodeURIComponent(canonicalId)}/analysis`)
            .then(response => {
                if (!response.ok) throw new Error('Team provider request failed');
                return response.json();
            })
            .then(data => {
                cache.set(canonicalId, data);
                return data;
            })
            .finally(() => inFlight.delete(canonicalId));
        inFlight.set(canonicalId, operation);
        return operation;
    }

    async function load(force = false) {
        const canonicalId = String(currentTeam?.canonicalId || '');
        if (!canonicalId) {
            renderIdentityUnavailable(content, currentTeam);
            return;
        }
        renderSkeleton(content);
        try {
            const data = await request(canonicalId, force);
            if (String(currentTeam?.canonicalId || '') !== canonicalId) return;
            currentData = data;
            renderTeam(content, data, getRevealed());
        } catch {
            if (String(currentTeam?.canonicalId || '') !== canonicalId) return;
            currentData = null;
            renderError(content, () => load(true));
        }
    }

    function open(team, trigger) {
        currentTeam = team;
        activeTrigger = trigger;
        currentData = cache.get(String(team?.canonicalId || '')) || null;
        if (!dialog.open) dialog.showModal();
        document.body.classList.add('dialog-open');
        closeButton.focus();
        if (currentData) renderTeam(content, currentData, getRevealed());
        else load();
    }

    function rerender() {
        if (currentData) renderTeam(content, currentData, getRevealed());
    }

    closeButton.addEventListener('click', close);
    dialog.addEventListener('close', () => {
        syncBodyLock();
        if (activeTrigger?.isConnected) activeTrigger.focus();
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) close();
    });
    dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const focusable = focusableElements(dialog);
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

    return {open, close, rerender};
}
