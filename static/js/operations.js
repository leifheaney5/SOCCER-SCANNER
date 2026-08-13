const form = document.getElementById('operations-auth');
const token = document.getElementById('operations-token');
const status = document.getElementById('operations-status');
const values = document.getElementById('operations-values');

function addValue(label, value) {
    const item = document.createElement('article');
    item.className = 'operations-value';
    const heading = document.createElement('h2');
    heading.textContent = label;
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(value, null, 2);
    item.append(heading, pre);
    values.append(item);
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    status.textContent = 'Loading operational status…';
    values.replaceChildren();
    try {
        const response = await fetch('/api/v2/operations', {
            headers: {'X-Ops-Token': token.value},
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || 'Status unavailable');
        addValue('Build', payload.build);
        addValue('Readiness', payload.readiness);
        addValue('Providers', payload.providers);
        addValue('Rate limiting', payload.rateLimit);
        addValue('Metrics', payload.metrics);
        values.hidden = false;
        status.textContent = 'Operational status loaded.';
    } catch (error) {
        values.hidden = true;
        status.textContent = error.message || 'Operational status unavailable.';
    }
});
