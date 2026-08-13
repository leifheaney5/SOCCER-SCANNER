const trigger = document.getElementById('global-search-trigger');
const dialog = document.getElementById('global-search-dialog');
const closeButton = document.getElementById('global-search-close');
const input = document.getElementById('global-search-input');
const status = document.getElementById('global-search-status');
const results = document.getElementById('global-search-results');
const selectedDate = document.getElementById('dashboard-date');
const assetVersion = new URL(import.meta.url).searchParams.get('v');

let timer = null;
let controller = null;
let resultIndex = -1;

function escapeHtml(value) {
    return String(value || '').replace(/[&<>'"]/g, character => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
}

function resultHref(result) {
    const params = new URLSearchParams();
    if (result.type === 'fixture') {
        params.set('date', result.date);
        params.set('fixture', result.id);
    } else {
        params.set('date', selectedDate?.value || '');
        params.set('q', result.name);
    }
    return `/?${params.toString()}`;
}

function render(items) {
    results.replaceChildren(...items.map((item, index) => {
        const option = document.createElement('a');
        option.className = 'global-search-result';
        option.href = resultHref(item);
        option.setAttribute('role', 'option');
        option.dataset.index = String(index);
        option.setAttribute('aria-selected', String(index === resultIndex));
        const label = item.type === 'fixture'
            ? `${item.homeTeam?.name || 'Home'} — ${item.awayTeam?.name || 'Away'}`
            : item.name;
        const detail = item.type === 'fixture'
            ? `${item.competition?.name || 'Competition'} · ${item.date || ''}`
            : item.type;
        option.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span>`;
        option.addEventListener('mouseenter', () => {
            resultIndex = index;
            render(items);
        });
        return option;
    }));
}

function showResults(payload) {
    const items = Array.isArray(payload?.results) ? payload.results : [];
    resultIndex = -1;
    render(items);
    if (payload?.state === 'partial') {
        status.textContent = `${items.length} results; some days need attention.`;
    } else {
        status.textContent = items.length ? `${items.length} results` : 'No results found.';
    }
}

async function search() {
    const query = input.value.trim();
    controller?.abort();
    if (query.length < 2) {
        results.replaceChildren();
        status.textContent = query ? 'Keep typing to search.' : 'Search teams, competitions, or fixtures.';
        return;
    }
    controller = new AbortController();
    status.textContent = 'Searching…';
    try {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        const response = await fetch(`/api/v2/search?q=${encodeURIComponent(query)}&timezone=${encodeURIComponent(timezone)}`, {
            signal: controller.signal,
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || 'Search unavailable');
        showResults(payload);
    } catch (error) {
        if (error.name === 'AbortError') return;
        results.replaceChildren();
        status.textContent = 'Search is temporarily unavailable.';
    }
}

function scheduleSearch() {
    clearTimeout(timer);
    timer = setTimeout(search, 250);
}

function close() {
    if (dialog.open) dialog.close();
    controller?.abort();
    resultIndex = -1;
    trigger.focus();
}

trigger.addEventListener('click', () => {
    dialog.showModal();
    input.focus();
    input.select();
});
closeButton.addEventListener('click', close);
dialog.addEventListener('cancel', event => {
    event.preventDefault();
    close();
});
input.addEventListener('input', scheduleSearch);
input.addEventListener('keydown', event => {
    const options = [...results.querySelectorAll('[role="option"]')];
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!options.length) return;
        resultIndex = event.key === 'ArrowDown'
            ? (resultIndex + 1) % options.length
            : (resultIndex - 1 + options.length) % options.length;
        options.forEach((option, index) => option.setAttribute('aria-selected', String(index === resultIndex)));
        options[resultIndex].scrollIntoView({block: 'nearest'});
    } else if (event.key === 'Enter' && resultIndex >= 0 && options[resultIndex]) {
        options[resultIndex].click();
    } else if (event.key === 'Escape') {
        event.preventDefault();
        close();
    }
});
document.addEventListener('keydown', event => {
    if (event.key === '/' && !dialog.open && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        event.preventDefault();
        dialog.showModal();
        input.focus();
    }
});
