const root = document.querySelector('[data-team-id]');
const teamId = root?.dataset.teamId;
const title = document.getElementById('team-page-title');
const status = document.getElementById('team-page-status');
const facts = document.getElementById('team-page-facts');

function addFact(label, value) {
    if (value === null || value === undefined || value === '') return;
    const wrapper = document.createElement('div');
    const term = document.createElement('dt');
    const detail = document.createElement('dd');
    term.textContent = label;
    detail.textContent = String(value);
    wrapper.append(term, detail);
    facts.append(wrapper);
}

async function load() {
    try {
        const response = await fetch(`/api/v2/teams/${encodeURIComponent(teamId)}/analysis`);
        if (!response.ok) throw new Error('Team unavailable');
        const data = await response.json();
        const team = data.team_info || {};
        title.textContent = team.name || teamId.replaceAll('-', ' ');
        facts.replaceChildren();
        addFact('Founded', team.founded);
        addFact('Venue', team.venue);
        addFact('Club colors', team.clubColors);
        addFact('Squad', Array.isArray(data.squad) ? `${data.squad.length} players` : null);
        status.textContent = facts.children.length ? 'Verified club details' : 'Limited verified club data';
    } catch {
        title.textContent = teamId.replaceAll('-', ' ');
        status.textContent = 'Verified team intelligence is temporarily unavailable.';
    }
}

if (teamId) load();
