const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [crestModule, fixtureRendererModule, fixtureStateModule] = await Promise.all([
    import(versionedModule('./crest.js')),
    import(versionedModule('./fixture-renderer.js')),
    import(versionedModule('./fixture-state.js')),
]);
const {createCrest} = crestModule;
const {createScoreNode} = fixtureRendererModule;
const {statusKind} = fixtureStateModule;

function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== '') element.textContent = text;
    return element;
}

function sentenceCase(value) {
    const words = String(value || '').replaceAll('_', ' ').toLocaleLowerCase();
    return words ? words.charAt(0).toLocaleUpperCase() + words.slice(1) : '';
}

function statusText(match) {
    const raw = String(match?.status || '').toUpperCase();
    if (raw === 'PAUSED' || raw === 'HALFTIME') return 'Half-time';
    const kind = statusKind(match);
    if (kind === 'live') return 'Live now';
    if (kind === 'finished') return 'Full-time';
    if (kind === 'upcoming') return 'Upcoming';
    return sentenceCase(kind);
}

function localKickoff(match) {
    const date = new Date(match?.utcDate);
    if (Number.isNaN(date.getTime())) return 'Kickoff time unavailable';
    return date.toLocaleString([], {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function focusableElements(dialog) {
    return [...dialog.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter(element => !element.hidden);
}

function createTeam(team, onTeam) {
    const card = node('div', 'context-team');
    card.append(
        createCrest(team, {size: 52, lazy: false, className: 'team-crest--context'}),
        node('strong', 'context-team-name', team?.name || 'Team unavailable'),
    );
    const button = node('button', 'context-team-button', 'Team intelligence');
    button.type = 'button';
    button.setAttribute('aria-label', `Open ${team?.name || 'team'} intelligence`);
    button.addEventListener('click', event => onTeam?.(team, event.currentTarget));
    card.append(button);
    return card;
}

function addMeta(list, label, value) {
    if (value === null || value === undefined || value === '') return;
    const item = node('div', 'context-meta-item');
    item.append(node('dt', '', label), node('dd', '', String(value)));
    list.append(item);
}

function createContextContent(match, revealed, onTeam, headingId) {
    const fragment = document.createDocumentFragment();
    const competition = node('p', 'context-competition', match?.competition?.name || 'Competition unavailable');
    const heading = node('h2', 'context-heading', `${match?.homeTeam?.name || 'Home team'} — ${match?.awayTeam?.name || 'Away team'}`);
    if (headingId) heading.id = headingId;
    const status = node('p', `context-status context-status--${statusKind(match)}`, statusText(match));
    const matchup = node('div', 'context-matchup');
    matchup.append(
        createTeam(match?.homeTeam, onTeam),
        createScoreNode(match, revealed, {featured: true}),
        createTeam(match?.awayTeam, onTeam),
    );

    const details = node('dl', 'context-meta');
    addMeta(details, 'Local kickoff', localKickoff(match));
    addMeta(details, 'Venue', match?.venue);
    addMeta(details, 'Matchday', match?.matchday ?? match?.season?.currentMatchday ? `Matchday ${match?.matchday ?? match?.season?.currentMatchday}` : null);
    addMeta(details, 'Stage', sentenceCase(match?.stage));
    addMeta(details, 'Source', match?.enhanced_info?.source);
    fragment.append(competition, heading, status, matchup, details);
    return fragment;
}

export function createMatchContext({
    panel,
    panelContent,
    dialog,
    dialogContent,
    closeButton,
    getRevealed,
    onTeam,
}) {
    let currentMatch = null;
    let activeTrigger = null;

    const desktop = () => window.matchMedia('(min-width: 1100px)').matches;

    function render() {
        if (!currentMatch) return;
        const target = desktop() ? panelContent : dialogContent;
        target.replaceChildren(createContextContent(
            currentMatch,
            getRevealed(),
            onTeam,
            desktop() ? 'match-context-title' : null,
        ));
        panel.classList.toggle('has-selection', desktop());
    }

    function restoreFocus() {
        document.body.classList.remove('dialog-open');
        if (activeTrigger?.isConnected) activeTrigger.focus();
    }

    function close() {
        if (dialog.open) dialog.close();
    }

    function open(match, trigger) {
        currentMatch = match;
        activeTrigger = trigger;
        render();
        if (!desktop()) {
            if (!dialog.open) dialog.showModal();
            document.body.classList.add('dialog-open');
            closeButton.focus();
        }
    }

    function reset() {
        currentMatch = null;
        panel.classList.remove('has-selection');
        const heading = node('h2', '', 'Select a fixture');
        heading.id = 'match-context-title';
        panelContent.replaceChildren(
            heading,
            node('p', '', 'Choose a match to inspect the kickoff, venue, competition, and both teams.'),
        );
        close();
    }

    closeButton.addEventListener('click', close);
    dialog.addEventListener('close', restoreFocus);
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

    return {
        open,
        close,
        reset,
        rerender: render,
        selected: () => currentMatch,
    };
}
