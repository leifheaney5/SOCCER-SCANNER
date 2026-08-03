const selector = document.getElementById('league-selector');
const frame = document.getElementById('standings-frame');
const status = document.getElementById('standings-status');
const fallback = document.getElementById('standings-fallback');

function loadSelectedStandings() {
    const option = selector.options[selector.selectedIndex];
    const leagueName = option.textContent;
    status.textContent = `Loading ${leagueName} standings…`;
    status.hidden = false;
    frame.title = `${leagueName} standings`;
    frame.src = option.value;
    fallback.href = option.value;
}

frame.addEventListener('load', () => {
    status.textContent = `${selector.options[selector.selectedIndex].textContent} loaded.`;
    window.setTimeout(() => { status.hidden = true; }, 1500);
});
selector.addEventListener('change', loadSelectedStandings);
loadSelectedStandings();
