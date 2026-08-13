const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [crestModule, fixtureRendererModule, fixtureStateModule] = await Promise.all([
    import(versionedModule('./crest.js')),
    import(versionedModule('./fixture-renderer.js')),
    import(versionedModule('./fixture-state.js')),
]);
const timeZoneModule = await import(versionedModule('./time-zone.js'));
const statusModule = await import(versionedModule('./match-status.js'));
const {createCrest} = crestModule;
const {createScoreNode, formatFreshness, resolveStreamingServices} = fixtureRendererModule;
const {statusKind} = fixtureStateModule;
const {formatDateTime, formatFixtureDate, formatKickoff} = timeZoneModule;
const {statusLabel: canonicalStatusLabel} = statusModule;

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

function localKickoff(match, timeZone) {
    if (!match?.utcDate) return 'Kickoff time unavailable';
    return `${formatFixtureDate(match.utcDate, timeZone)} at ${formatKickoff(match.utcDate, timeZone)}`;
}

function focusableElements(dialog) {
    return [...dialog.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter(element => !element.hidden);
}

function createTeam(team) {
    const card = node('div', 'context-team');
    card.append(
        createCrest(team, {size: 52, lazy: false, className: 'team-crest--context'}),
        node('strong', 'context-team-name', team?.name || 'Team unavailable'),
    );
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
        const icon = typeof service.logoPath === 'string'
            ? node('img', 'streaming-service-icon streaming-service-icon--image')
            : node('span', 'streaming-service-icon streaming-service-icon--generic');
        icon.setAttribute('aria-hidden', 'true');
        if (icon.tagName === 'IMG') {
            icon.src = service.logoPath.startsWith('/static/') && !service.logoPath.includes('://')
                ? service.logoPath
                : '';
            icon.alt = '';
            icon.width = 28;
            icon.height = 28;
            icon.addEventListener('error', () => {
                icon.replaceWith(node('span', 'streaming-service-icon streaming-service-icon--generic'));
            });
        }
        item.append(icon);
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
        if (service.observedAt) {
            const observed = new Date(service.observedAt);
            if (!Number.isNaN(observed.getTime())) {
                item.append(node(
                    'span',
                    'context-streaming-observed',
                    `Observed ${observed.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'})}`,
                ));
            }
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

function createSourceInspector(match, timeZone) {
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
            : `${freshness} · ${formatDateTime(updatedAt, timeZone, {year: 'numeric'})} · ${timeZone}`);
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

function createContextContent(match, revealed, headingId, timeZone) {
    const fragment = document.createDocumentFragment();
    const competition = node('p', 'context-competition', match?.competition?.name || 'Competition unavailable');
    const heading = node('h2', 'context-heading', `${match?.homeTeam?.name || 'Home team'} — ${match?.awayTeam?.name || 'Away team'}`);
    if (headingId) heading.id = headingId;
    const status = node('p', `context-status context-status--${statusKind(match)}`, canonicalStatusLabel(match));
    const matchup = node('div', 'context-matchup');
    matchup.append(
        createTeam(match?.homeTeam),
        createScoreNode(match, revealed, {featured: true}),
        createTeam(match?.awayTeam),
    );

    const details = node('dl', 'context-meta');
    addMeta(details, 'Local kickoff', localKickoff(match, timeZone));
    addMeta(details, 'Venue', match?.venue);
    addMeta(details, 'Matchday', match?.matchday ?? match?.season?.currentMatchday ? `Matchday ${match?.matchday ?? match?.season?.currentMatchday}` : null);
    addMeta(details, 'Stage', sentenceCase(match?.stage));
    addMeta(details, 'Source', match?.enhanced_info?.source);
    const fixtureId = String(match?.canonicalFixtureId || match?.id || '');
    const actions = node('div', 'context-actions');
    if (fixtureId) {
        const copy = node('button', 'control-button', 'Copy fixture link');
        copy.type = 'button';
        copy.dataset.focusKey = 'copy-fixture-link';
        copy.addEventListener('click', async () => {
            const link = `${location.origin}/fixtures/${encodeURIComponent(fixtureId)}?timezone=${encodeURIComponent(timeZone)}`;
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
    fragment.append(actions, createSourceInspector(match, timeZone));
    return fragment;
}

export function createMatchContext({
    panel,
    panelContent,
    dialog,
    dialogContent,
    closeButton,
    getRevealed,
    getTimezone,
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
            desktop() ? 'match-context-title' : null,
            getTimezone(),
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

    function update(match) {
        if (!match) return;
        currentMatch = match;
        render();
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
        update,
        rerender: render,
        selected: () => currentMatch,
    };
}
