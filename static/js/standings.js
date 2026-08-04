const selector = document.getElementById('league-selector');
const frame = document.getElementById('standings-frame');
const status = document.getElementById('standings-status');
const fallback = document.getElementById('standings-fallback');
const reveal = document.getElementById('reveal-standings');
let revealed = false;

function loadSelectedStandings() {
    const option = selector.options[selector.selectedIndex];
    const leagueName = option.textContent;
    status.textContent = `Loading ${leagueName} standings…`;
    status.hidden = false;
    frame.title = `${leagueName} standings`;
    frame.src = option.value;
    fallback.href = option.value;
    frame.hidden = false;
}

frame.addEventListener('load', () => {
    status.textContent = `${selector.options[selector.selectedIndex].textContent} loaded.`;
    window.setTimeout(() => { status.hidden = true; }, 1500);
});
selector.addEventListener('change', () => {
    const option = selector.options[selector.selectedIndex];
    fallback.href = option.value;
    if (revealed) loadSelectedStandings();
    else status.textContent = `${option.textContent} selected. Choose reveal to load standings.`;
});
reveal.addEventListener('click', () => {
    revealed = true;
    reveal.setAttribute('aria-pressed', 'true');
    reveal.textContent = 'Table revealed';
    loadSelectedStandings();
});
fallback.href = selector.options[selector.selectedIndex].value;
