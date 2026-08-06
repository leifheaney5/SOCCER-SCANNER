const assetVersion = new URL(import.meta.url).searchParams.get('v');
const versionedModule = path => (
    assetVersion ? `${path}?v=${encodeURIComponent(assetVersion)}` : path
);
const [timeZoneModule] = await Promise.all([
    import(versionedModule('./time-zone.js')),
]);
const {browserTimeZone, formatTimezoneLabel, resolveTimeZone, supportedTimeZones} = timeZoneModule;

// supportedTimeZones() returns several hundred IANA zones; building a DOM
// node per zone up front would be wasted work every time the search field
// changes, so only the zones actually visible get rendered.
const MAX_RENDERED_OPTIONS = 50;

function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== '') element.textContent = text;
    return element;
}

/**
 * A searchable, accessible listbox for choosing the fixture timezone.
 *
 * This control never owns the timezone: `getTimeZone` is read on every
 * render and `onChange` is the only way it asks for a different one. The
 * caller (fixtures.js) remains the single source of truth so this control
 * and the `#timezone-filter` select can never drift apart.
 */
export function createTimezoneControl({root, getTimeZone, onChange}) {
    const trigger = root.querySelector('.timezone-trigger');
    const triggerLabel = trigger.querySelector('[data-timezone-label]');
    const popover = root.querySelector('.timezone-popover');
    const search = root.querySelector('.timezone-search');
    const list = root.querySelector('.timezone-options');

    const allZones = supportedTimeZones();
    const suggestedZones = [...new Set([browserTimeZone(), 'UTC'])].sort((a, b) => (a === 'UTC' ? -1 : b === 'UTC' ? 1 : 0));
    const suggestedSet = new Set(suggestedZones);
    const otherZones = allZones.filter(zone => !suggestedSet.has(zone));

    let renderedZones = [];
    let activeIndex = -1;

    function currentZone() {
        return resolveTimeZone(getTimeZone());
    }

    function matchingZones(source, needle) {
        return needle ? source.filter(zone => zone.toLocaleLowerCase().includes(needle)) : source;
    }

    function filteredEntries(term) {
        const needle = term.trim().toLocaleLowerCase();
        const suggested = matchingZones(suggestedZones, needle).map(zone => ({zone, group: 'Suggested'}));
        const rest = matchingZones(otherZones, needle).map(zone => ({zone, group: 'All timezones'}));
        return [...suggested, ...rest].slice(0, MAX_RENDERED_OPTIONS);
    }

    function renderOptions(term) {
        const entries = filteredEntries(term);
        renderedZones = entries.map(entry => entry.zone);
        activeIndex = -1;
        search.removeAttribute('aria-activedescendant');
        const selected = currentZone();
        const fragment = document.createDocumentFragment();
        let lastGroup = null;
        entries.forEach((entry, index) => {
            if (entry.group !== lastGroup) {
                fragment.append(node('li', 'timezone-group-label', entry.group));
                lastGroup = entry.group;
            }
            const descriptor = formatTimezoneLabel(entry.zone);
            const option = node('li', 'timezone-option');
            option.id = `timezone-option-${index}`;
            option.setAttribute('role', 'option');
            option.dataset.zone = entry.zone;
            option.setAttribute('aria-selected', String(entry.zone === selected));
            option.append(
                node('span', 'timezone-option-zone', entry.zone.replaceAll('_', ' ')),
                node('span', 'timezone-option-meta', `${descriptor.abbreviation} · ${descriptor.offsetLabel}`),
            );
            fragment.append(option);
        });
        if (entries.length === 0) fragment.append(node('li', 'timezone-empty', 'No matching timezones'));
        list.replaceChildren(fragment);
    }

    function setActiveIndex(index) {
        const options = [...list.querySelectorAll('.timezone-option')];
        options.forEach(option => option.classList.remove('is-active'));
        if (index < 0 || index >= options.length) {
            activeIndex = -1;
            search.removeAttribute('aria-activedescendant');
            return;
        }
        activeIndex = index;
        const option = options[index];
        option.classList.add('is-active');
        search.setAttribute('aria-activedescendant', option.id);
        option.scrollIntoView({block: 'nearest'});
    }

    function moveActive(delta) {
        const count = list.querySelectorAll('.timezone-option').length;
        if (!count) return;
        const next = activeIndex < 0
            ? (delta > 0 ? 0 : count - 1)
            : Math.min(Math.max(activeIndex + delta, 0), count - 1);
        setActiveIndex(next);
    }

    function openPopover() {
        if (root.dataset.open === 'true') return;
        root.dataset.open = 'true';
        popover.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        search.value = '';
        renderOptions('');
        search.focus();
        document.addEventListener('pointerdown', handleOutsidePointer, true);
    }

    function closePopover({focusTrigger = false} = {}) {
        if (root.dataset.open !== 'true') return;
        root.dataset.open = 'false';
        popover.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        document.removeEventListener('pointerdown', handleOutsidePointer, true);
        if (focusTrigger) trigger.focus();
    }

    function handleOutsidePointer(event) {
        if (root.contains(event.target)) return;
        closePopover();
    }

    function chooseZone(zone) {
        if (!zone) return;
        const changed = zone !== currentZone();
        closePopover({focusTrigger: true});
        if (changed) onChange(zone);
    }

    function selectActive() {
        const zone = activeIndex >= 0 ? renderedZones[activeIndex] : renderedZones[0];
        chooseZone(zone);
    }

    trigger.addEventListener('click', () => {
        if (root.dataset.open === 'true') closePopover({focusTrigger: true});
        else openPopover();
    });

    search.addEventListener('input', () => renderOptions(search.value));

    search.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            moveActive(1);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            moveActive(-1);
        } else if (event.key === 'Enter') {
            event.preventDefault();
            selectActive();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            closePopover({focusTrigger: true});
        }
    });

    list.addEventListener('click', event => {
        const option = event.target.closest('.timezone-option');
        if (option) chooseZone(option.dataset.zone);
    });

    function sync() {
        const descriptor = formatTimezoneLabel(currentZone());
        triggerLabel.textContent = descriptor.shortLabel;
        trigger.setAttribute('aria-label', descriptor.accessibleName);
    }

    sync();

    return {sync};
}
