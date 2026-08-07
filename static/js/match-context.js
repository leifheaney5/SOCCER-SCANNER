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
const {createScoreNode, formatFreshness, resolveStreamingServices} = fixtureRendererModule;
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

function sourceLabel(value) {
    const labels = {
        espn: 'ESPN',
        'football-data': 'Football-Data.org',
        football_data: 'Football-Data.org',
    };
    return labels[String(value || '').toLocaleLowerCase()] || sentenceCase(value);
}

// Every service is listed here (unlike the card, which shows only the
// first plus a `+N` count). An anchor is only ever created when
// `officialUrl` is present — an unverified name is never given a link, and
// `region` is rendered exactly as supplied (including "Region unknown")
// rather than guessed.
function createStreamingSection(match) {
    const services = resolveStreamingServices(match);
    if (!services.length) return null;
    const section = node('div', 'context-streaming');
    section.setAttribute('aria-label', 'Where to watch');
    section.append(node('h3', 'context-streaming-heading', 'Where to watch'));
    const list = node('ul', 'context-streaming-list');
    for (const service of services) {
        const item = node('li', 'context-streaming-item');
        if (service.officialUrl) {
            const link = node('a', 'context-streaming-link', service.displayName);
            link.href = service.officialUrl;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            item.append(link);
        } else {
            item.append(node('span', 'context-streaming-name', service.displayName));
        }
        if (service.region) {
            item.append(node('span', 'context-streaming-region', service.region));
        }
        list.append(item);
    }
    section.append(list);
    section.append(node(
        'p',
        'context-streaming-disclaimer',
        'Availability varies by region and subscription. Listings may be incomplete or out of date.',
    ));
    return section;
}

function createSourceInspector(match) {
    const inspector = node('details', 'source-inspector');
    inspector.append(node('summary', '', 'Source and freshness'));
    const evidence = node('dl', 'source-inspector-list');
    const sources = Array.isArray(match?.sources) ? match.sources.map(sourceLabel).filter(Boolean) : [];
    const updatedAt = match?.sourceUpdatedAt || match?.lastUpdated;
    const freshness = formatFreshness(updatedAt);
    addMeta(evidence, 'Source', sources.join(', ') || 'Source unavailable');
    if (updatedAt) {
        const updated = new Date(updatedAt);
        addMeta(evidence, 'Freshness', Number.isNaN(updated.getTime())
            ? freshness
            : `${freshness} · ${updated.toLocaleString()}`);
    }
    const missingFields = match?.dataQuality?.missingFields;
    if (Array.isArray(missingFields) && missingFields.length) {
        addMeta(evidence, 'Missing verified fields', missingFields.map(sentenceCase).join(', '));
    } else {
        addMeta(evidence, 'Verification', 'No known gaps');
    }
    inspector.append(evidence);
    return inspector;
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
    const fixtureId = String(match?.canonicalFixtureId || match?.id || '');
    const actions = node('div', 'context-actions');
    if (fixtureId) {
        const copy = node('button', 'control-button', 'Copy fixture link');
        copy.type = 'button';
        copy.addEventListener('click', async () => {
            const link = `${location.origin}/fixtures/${encodeURIComponent(fixtureId)}`;
            try {
                await navigator.clipboard.writeText(link);
                copy.textContent = 'Link copied';
            } catch {
                copy.textContent = link;
            }
        });
        const calendar = node('a', 'control-button', 'Add to calendar');
        calendar.href = `/fixtures/${encodeURIComponent(fixtureId)}.ics`;
        calendar.setAttribute('download', '');
        actions.append(copy, calendar);
    }
    const streamingSection = createStreamingSection(match);
    fragment.append(competition, heading, status, matchup, details);
    if (streamingSection) fragment.append(streamingSection);
    fragment.append(actions, createSourceInspector(match));
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
    onClose,
    dialogManager,
}) {
    let currentMatch = null;
    let activeTrigger = null;
    let preserveSelectionOnClose = false;

    const mediaQuery = window.matchMedia('(min-width: 1100px)');
    const desktop = () => mediaQuery.matches;

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

    function close(options) {
        preserveSelectionOnClose = Boolean(options?.preserveSelection);
        dialogManager.close(dialog, options);
    }

    function open(match, trigger) {
        currentMatch = match;
        activeTrigger = trigger;
        render();
        if (!desktop()) {
            dialogManager.open(dialog, activeTrigger);
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
        close({restoreFocus: false});
    }

    function onViewportChange() {
        if (!currentMatch) return;
        render();
        if (desktop()) {
            close({restoreFocus: false, preserveSelection: true});
        } else {
            dialogManager.open(dialog, activeTrigger);
            closeButton.focus();
        }
    }

    closeButton.addEventListener('click', close);
    dialog.addEventListener('click', event => {
        // The fixture stream is rebuilt by onClose before focus is restored.
        // Let that callback focus the fresh trigger instead of asking the
        // generic manager to focus the detached pre-render button first.
        if (event.target === dialog) close({restoreFocus: false});
    });
    dialog.addEventListener('close', () => {
        if (preserveSelectionOnClose) {
            preserveSelectionOnClose = false;
            return;
        }
        if (currentMatch) onClose?.(currentMatch);
    });
    mediaQuery.addEventListener('change', onViewportChange);
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
