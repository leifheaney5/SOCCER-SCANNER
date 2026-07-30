const params = new URLSearchParams(window.location.search);
        let fixturePayload = null;
        let activeFixture = null;
        let refreshTimer = null;
        const favoriteFixtures = new Set(JSON.parse(localStorage.getItem('favoriteFixtures') || '[]'));

        function fixtureKey(match) {
            return String(match.id || `${match.homeTeam.name}-${match.awayTeam.name}-${match.utcDate}`);
        }

        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>'"]/g, character => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
            })[character]);
        }

        function fixtureStatus(match) {
            if (['LIVE', 'IN_PLAY', 'PAUSED'].includes(match.status)) return 'live';
            if (['FINISHED', 'AWARDED'].includes(match.status)) return 'finished';
            return 'upcoming';
        }

        function populateCompetitionFilter(matches) {
            const select = document.getElementById('competition-filter');
            const selected = select.value || new URLSearchParams(window.location.search).get('competition') || '';
            const competitions = [...new Set(matches.map(match => match.competition.name))].sort();
            select.replaceChildren(new Option('All competitions', ''));
            competitions.forEach(name => select.add(new Option(name, name)));
            select.value = competitions.includes(selected) ? selected : '';
        }

        function renderFilteredFixtures() {
            if (!fixturePayload) return;
            const query = document.getElementById('fixture-search').value.trim().toLowerCase();
            const competition = document.getElementById('competition-filter').value;
            const status = document.getElementById('status-filter').value;
            const favoritesOnly = document.getElementById('favorites-filter').value === 'favorites';
            const url = new URL(window.location);
            [['q', query], ['competition', competition], ['status', status],
             ['favorites', favoritesOnly ? '1' : '']].forEach(([key, value]) => {
                value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
            });
            window.history.replaceState({}, '', url);
            const matches = fixturePayload.matches.filter(match => {
                const searchable = `${match.homeTeam.name} ${match.awayTeam.name} ${match.competition.name}`.toLowerCase();
                return (!query || searchable.includes(query))
                    && (!competition || match.competition.name === competition)
                    && (!status || fixtureStatus(match) === status)
                    && (!favoritesOnly || favoriteFixtures.has(fixtureKey(match)));
            });
            displayMatches({
                ...fixturePayload,
                matches,
                featured_matches: matches.slice(0, 6),
                total_matches: matches.length,
            });
        }
        function formatLocalDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }

        let selectedDate = params.get('date') || formatLocalDate(new Date());

        function parseLocalDate(value) {
            return new Date(`${value}T12:00:00`);
        }

        function updateDateHeader() {
            document.getElementById('date-picker').value = selectedDate;
            document.getElementById('current-date').textContent =
                parseLocalDate(selectedDate).toLocaleDateString('en-US', {
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            });
        }

        function chooseDate(value) {
            selectedDate = value;
            const url = new URL(window.location);
            url.searchParams.set('date', selectedDate);
            window.history.replaceState({}, '', url);
            updateDateHeader();
            loadTodaysMatches();
        }

        function shiftDate(days) {
            const date = parseLocalDate(selectedDate);
            date.setDate(date.getDate() + days);
            chooseDate(formatLocalDate(date));
        }

        document.getElementById('fixture-search').value = params.get('q') || '';
        document.getElementById('status-filter').value = params.get('status') || '';
        document.getElementById('favorites-filter').value = params.get('favorites') === '1' ? 'favorites' : '';
        updateDateHeader();

        // Competition priority ranking (higher number = higher priority) - Top 20 Competitions
        const competitionPriorities = {
            // Tier 1: Elite Global Competitions (90-100)
            'Premier League': 100,
            'UEFA Champions League': 95,
            'La Liga': 90,
            
            // Tier 2: Major European Leagues (80-89)
            'Bundesliga': 85,
            'Serie A': 85,
            'Ligue 1': 80,
            
            // Tier 3: European Competitions (70-79)
            'UEFA Europa League': 75,
            'UEFA Conference League': 70,
            'Copa del Rey': 70,
            'FA Cup': 70,
            'DFB-Pokal': 65,
            'Coppa Italia': 65,
            
            // Tier 4: Secondary European Leagues (60-69)
            'Eredivisie': 68,
            'Primeira Liga': 65,
            'Pro League': 62,                    // Belgium
            'Süper Lig': 60,                    // Turkey
            'Austrian Bundesliga': 58,
            'Scottish Premiership': 55,
            
            // Tier 5: Second Divisions (50-59)
            'Championship': 58,                  // England Championship
            'Segunda División': 55,             // Spain Segunda
            '2. Bundesliga': 56,                // Germany 2. Bundesliga
            'Serie B': 54,                      // Italy Serie B
            
            // Tier 6: Americas & International (40-59)
            'Brasileirão': 65,                  // Brazil Serie A
            'Liga Profesional': 60,            // Argentina
            'FIFA World Cup': 100,
            'UEFA European Championship': 95,
            'Copa America': 85,
            'UEFA Nations League': 70,
            'Copa Libertadores': 75,
            'MLS': 50,
            'Liga MX': 52,
            'J1 League': 45,                    // Japan
            'K League 1': 40,                   // South Korea
        };

        function getPriority(competitionName) {
            return competitionPriorities[competitionName] || 30;
        }

        function getPriorityClass(priority) {
            if (priority >= 80) return 'priority-high';
            if (priority >= 60) return 'priority-medium';
            return 'priority-low';
        }

        function getPriorityLabel(priority) {
            if (priority >= 80) return 'High Priority';
            if (priority >= 60) return 'Medium Priority';
            return 'Lower Priority';
        }

        async function loadTodaysMatches() {
            try {
                const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
                const response = await fetch(`/api/matches-today?date=${encodeURIComponent(selectedDate)}&timezone=${encodeURIComponent(timezone)}`);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to load matches');
                }

                fixturePayload = data;
                populateCompetitionFilter(data.matches || []);
                const notice = document.getElementById('data-notice');
                if (data.stale || data.partial) {
                    notice.textContent = data.stale
                        ? 'Showing cached fixture data while live providers recover.'
                        : 'Some competitions may be missing because a data provider is degraded.';
                    notice.style.display = 'block';
                } else {
                    notice.style.display = 'none';
                }
                renderFilteredFixtures();
            } catch (error) {
                console.error('Error loading matches:', error);
                showError(error.message);
            } finally {
                scheduleRefresh();
            }
        }

        function scheduleRefresh() {
            window.clearTimeout(refreshTimer);
            const hasLiveMatches = fixturePayload?.matches?.some(match => fixtureStatus(match) === 'live');
            const delay = document.hidden ? 5 * 60 * 1000 : (hasLiveMatches ? 30 * 1000 : 2 * 60 * 1000);
            refreshTimer = window.setTimeout(loadTodaysMatches, delay);
        }

        function displayMatches(data) {
            const loadingDiv = document.getElementById('loading');
            const containerDiv = document.getElementById('matches-container');
            const contentDiv = document.getElementById('matches-content');
            const statsDiv = document.getElementById('daily-stats');

            loadingDiv.style.display = 'none';
            containerDiv.style.display = 'block';

            if (!data.matches || data.matches.length === 0) {
                const filteredEmpty = fixturePayload && fixturePayload.matches.length > 0;
                contentDiv.innerHTML = `
                    <div class="no-matches">
                        <div class="no-matches-icon"></div>
                        <h2>${filteredEmpty ? 'No fixtures match these filters' : 'No Fixtures Found'}</h2>
                        <p>${filteredEmpty ? 'Try a different team, competition, or status.' : `There are no tracked fixtures on ${parseLocalDate(selectedDate).toLocaleDateString('en-US', {
                            weekday: 'long', 
                            month: 'long', 
                            day: 'numeric' 
                        })}) in the tracked competitions.`}</p>
                        ${filteredEmpty ? '<button class="date-button" type="button" data-action="clear-filters">Clear filters</button>' : '<p>Try the previous or next day to keep browsing.</p>'}
                        <div class="tracked-competitions">
                            <small>Tracking: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, Europa League, Conference League, Eredivisie, Primeira Liga, Pro League, Austrian Bundesliga, Süper Lig, Scottish Premiership, Championship, Segunda División, 2. Bundesliga, Serie B, Brasileirão, Liga Profesional</small>
                        </div>
                    </div>
                `;
                statsDiv.innerHTML = `
                    <div class="stats-header">
                        <h3>Today's Overview</h3>
                    </div>
                    <div class="no-stats">
                        <p>No match statistics available for today</p>
                    </div>
                `;
                statsDiv.style.display = 'block';
                return;
            }

            // Since we're now only showing today's matches, update the date logic
            const today = new Date().toISOString().split('T')[0];
            const hasTodayMatches = data.matches.some(match => {
                const matchDate = new Date(match.utcDate || match.date).toISOString().split('T')[0];
                return matchDate === today;
            });

            // Display daily statistics if available
            if (data.match_statistics) {
                displayDailyStatistics(data.match_statistics, data.source_stats);
                statsDiv.style.display = 'block';
            }

            let html = '';

            // Add notice about showing only today's matches
            html += `
                <div class="date-notice today-only">
                    <div class="notice-content">
                        <i class="calendar-icon"></i>
                        <div class="notice-text">
                            <h4>Fixtures for this date</h4>
                            <p>Showing matches scheduled for ${parseLocalDate(selectedDate).toLocaleDateString('en-US', {
                                weekday: 'long', 
                                month: 'long', 
                                day: 'numeric', 
                                year: 'numeric' 
                            })}</p>
                        </div>
                    </div>
                </div>
            `;

            // Featured Matches Section (Top 6)
            if (data.featured_matches && data.featured_matches.length > 0) {
                let featuredTitle = 'Featured Matches';
                let featuredSubtitle = '';
                
                html += `
                    <div class="featured-section">
                        <h2>${featuredTitle}</h2>
                        ${featuredSubtitle}
                        <div class="featured-grid">
                            ${data.featured_matches.map((match, index) => createFeaturedMatchCard(match, index + 1)).join('')}
                        </div>
                    </div>
                `;
            }



            // All Matches Section
            html += `
                <div class="all-matches-section">
                    <div class="section-header all-matches-header">
                        <h2>All Fixtures</h2>
                        <p>${data.total_matches} matches on this date</p>
                        ${data.source_stats ? `
                        <div class="source-info">
                            <small>Sources: ESPN API primary, Football-data.org fallback</small>
                            ${data.last_updated ? `<div class="freshness">Updated ${new Date(data.last_updated).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}${data.cached ? ' • Cached' : ''}</div>` : ''}
                        </div>
                        ` : ''}
                    </div>
            `;

            // Group matches by competition and sort by priority
            const matchesByCompetition = {};
            
            data.matches.forEach(match => {
                const competition = match.competition.name;
                if (!matchesByCompetition[competition]) {
                    matchesByCompetition[competition] = {
                        matches: [],
                        priority: getEnhancedPriority(competition, match),
                        competition: match.competition
                    };
                }
                matchesByCompetition[competition].matches.push(match);
            });

            // Sort competitions by priority (highest first)
            const sortedCompetitions = Object.entries(matchesByCompetition)
                .sort(([,a], [,b]) => b.priority - a.priority);

            sortedCompetitions.forEach(([competitionName, competitionData]) => {
                const priorityClass = getPriorityClass(competitionData.priority);
                const priorityLabel = getPriorityLabel(competitionData.priority);

                html += `
                    <div class="competition-section">
                        <div class="competition-header">
                            <div class="competition-info">
                                <span class="competition-name">${escapeHtml(competitionName)}</span>
                                <span class="match-count">${competitionData.matches.length} matches</span>
                            </div>
                            <span class="competition-priority ${priorityClass}">${priorityLabel}</span>
                        </div>
                        <div class="matches-list">
                `;

                // Sort matches within competition by time
                competitionData.matches.sort((a, b) => new Date(a.utcDate) - new Date(b.utcDate));

                competitionData.matches.forEach(match => {
                    html += createEnhancedMatchListItem(match);
                });

                html += `
                        </div>
                    </div>
                `;
            });

            html += `</div>`;
            
            contentDiv.innerHTML = html;
        }

        function displayDailyStatistics(stats, sourceStats) {
            const statsDiv = document.getElementById('daily-stats');
            
            let html = `
                <div class="stats-header">
                    <h3>Today's Match Overview</h3>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-number">${stats.total_matches}</div>
                        <div class="stat-label">Total Matches</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.high_importance}</div>
                        <div class="stat-label">High Priority</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.live_matches}</div>
                        <div class="stat-label">Live Now</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.rivalries}</div>
                        <div class="stat-label">Rivalries</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.major_leagues}</div>
                        <div class="stat-label">Major Leagues</div>
                    </div>
                </div>
            `;
            
            statsDiv.innerHTML = html;
        }

        function getEnhancedPriority(competitionName, match) {
            const baseScore = getPriority(competitionName);
            const enhancedInfo = match.enhanced_info || {};
            const importanceScore = enhancedInfo.importance_score || 0;
            
            // Combine base competition priority with match-specific importance
            return baseScore + (importanceScore * 0.3);
        }

        function createFeaturedMatchCard(match, rank) {
            const matchTime = new Date(match.utcDate);
            const timeString = matchTime.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit',
                hour12: true 
            });

            let status = match.status;
            let statusClass = 'status-scheduled';
            let statusText = 'Scheduled';

            if (status === 'LIVE' || status === 'IN_PLAY') {
                statusClass = 'status-live';
                statusText = '🔴 LIVE';
            } else if (status === 'FINISHED') {
                statusClass = 'status-finished';
                statusText = 'Finished';
            } else if (matchTime < new Date()) {
                statusClass = 'status-finished';
                statusText = 'Finished';
            }

            const homeTeam = escapeHtml(match.homeTeam.name);
            const awayTeam = escapeHtml(match.awayTeam.name);
            const competition = escapeHtml(match.competition.name);
            const venue = escapeHtml(match.venue || 'Venue TBD');

            // Enhanced information
            const enhancedInfo = match.enhanced_info || {};
            const importanceScore = enhancedInfo.importance_score || 0;
            const tvCoverage = enhancedInfo.tv_coverage || 'TBD';
            const rivalryFactor = enhancedInfo.rivalry_factor;
            const attendance = enhancedInfo.attendance_estimate || 'TBD';

            // Check if score is available
            let scoreDisplay = '';
            if (match.score && match.score.fullTime && 
                (match.score.fullTime.home !== null || match.score.fullTime.away !== null)) {
                scoreDisplay = `
                    <div class="featured-score">
                        <span class="score-number">${match.score.fullTime.home}</span>
                        <span class="score-separator">-</span>
                        <span class="score-number">${match.score.fullTime.away}</span>
                    </div>
                `;
            }

            const priorityClass = getPriorityClass(importanceScore);
            
            // Check if match is not today
            const today = new Date().toISOString().split('T')[0];
            const matchDate = new Date(match.utcDate).toISOString().split('T')[0];
            const isToday = matchDate === today;
            
            let dateDisplay = '';
            if (!isToday) {
                const matchDateObj = new Date(match.utcDate);
                const dateString = matchDateObj.toLocaleDateString('en-US', { 
                    weekday: 'short', 
                    month: 'short', 
                    day: 'numeric' 
                });
                const daysFromToday = enhancedInfo.days_from_today || 0;
                let dayLabel = '';
                if (daysFromToday < 0) {
                    dayLabel = `${Math.abs(daysFromToday)} day${Math.abs(daysFromToday) !== 1 ? 's' : ''} ago`;
                } else if (daysFromToday > 0) {
                    dayLabel = `in ${daysFromToday} day${daysFromToday !== 1 ? 's' : ''}`;
                }
                
                dateDisplay = `<div class="match-date-info">📅 ${dateString} ${dayLabel ? `(${dayLabel})` : ''}</div>`;
            }

            return `
                <div class="featured-match-card ${priorityClass}">
                    <div class="featured-rank">#${rank}</div>
                    <div class="importance-score">★ ${importanceScore}</div>
                    <div class="featured-competition">${competition}</div>
                    ${dateDisplay}
                    ${rivalryFactor ? `<div class="rivalry-badge">⚔️ ${escapeHtml(rivalryFactor)}</div>` : ''}
                    <div class="featured-teams">
                        <div class="team-name home-team">${homeTeam}</div>
                        ${scoreDisplay}
                        <div class="vs-text">vs</div>
                        <div class="team-name away-team">${awayTeam}</div>
                    </div>
                    <div class="featured-details">
                        <div class="featured-time">${timeString}</div>
                        <div class="featured-status ${statusClass}">${statusText}</div>
                    </div>
                    <div class="featured-venue">${venue}</div>
                    <div class="featured-extras">
                        <div class="tv-info">Coverage estimate: ${escapeHtml(tvCoverage)}</div>
                        <div class="attendance-info">Attendance estimate: ${escapeHtml(attendance)}</div>
                    </div>
                </div>
            `;
        }

        function createEnhancedMatchListItem(match) {
            const matchTime = new Date(match.utcDate);
            const now = new Date();
            const timeString = matchTime.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit',
                hour12: true 
            });

            let status = match.status;
            let statusClass = 'status-scheduled';
            let statusText = 'Scheduled';

            if (status === 'LIVE' || status === 'IN_PLAY') {
                statusClass = 'status-live';
                statusText = '🔴 LIVE';
            } else if (status === 'FINISHED') {
                statusClass = 'status-finished';
                statusText = 'Finished';
            } else if (matchTime < now) {
                statusClass = 'status-finished';
                statusText = 'Finished';
            }

            const homeTeam = escapeHtml(match.homeTeam.name);
            const awayTeam = escapeHtml(match.awayTeam.name);
            const venue = escapeHtml(match.venue || 'Venue TBD');

            // Enhanced information
            const enhancedInfo = match.enhanced_info || {};
            const importanceScore = enhancedInfo.importance_score || 0;
            const rivalryFactor = enhancedInfo.rivalry_factor;
            const tvCoverage = enhancedInfo.tv_coverage || '';
            const key = fixtureKey(match);
            const isFavorite = favoriteFixtures.has(key);

            // Check if score is available
            let scoreDisplay = '';
            if (match.score && match.score.fullTime && 
                (match.score.fullTime.home !== null || match.score.fullTime.away !== null)) {
                scoreDisplay = ` (${match.score.fullTime.home} - ${match.score.fullTime.away})`;
            }

            let enhancedBadges = '';
            if (rivalryFactor) {
                enhancedBadges += `<span class="rivalry-mini">⚔️ ${escapeHtml(rivalryFactor)}</span>`;
            }
            if (importanceScore >= 70) {
                enhancedBadges += `<span class="high-importance">High Priority</span>`;
            }
            if (tvCoverage && tvCoverage !== 'TBD') {
                enhancedBadges += `<span class="tv-badge">Estimated: ${escapeHtml(tvCoverage)}</span>`;
            }

            return `
                <div class="match-item enhanced-match" data-fixture-id="${encodeURIComponent(key)}">
                    <div class="match-header">
                        <div class="match-teams">
                            ${homeTeam} vs ${awayTeam}${scoreDisplay}
                            ${enhancedBadges ? `<div class="match-badges">${enhancedBadges}</div>` : ''}
                        </div>
                        <div class="match-time-info">
                            <div class="match-time">${timeString}</div>
                            <div class="fixture-actions">
                                <button class="fixture-action ${isFavorite ? 'favorite' : ''}" type="button" data-action="favorite" aria-label="${isFavorite ? 'Remove fixture from favorites' : 'Add fixture to favorites'}">${isFavorite ? '★' : '☆'}</button>
                                <button class="fixture-action" type="button" data-action="details" aria-label="Open fixture details">Details</button>
                            </div>
                        </div>
                    </div>
                    <div class="match-details">
                        <div class="match-venue">${venue}</div>
                        <div class="match-status ${statusClass}">${statusText}</div>
                    </div>
                </div>
            `;
        }

        function showError(message) {
            const loadingDiv = document.getElementById('loading');
            const containerDiv = document.getElementById('matches-container');
            const notice = document.getElementById('data-notice');
            loadingDiv.style.display = 'none';
            containerDiv.style.display = 'block';
            notice.style.display = 'block';
            notice.textContent = `Unable to refresh fixtures: ${message}`;
        }

        function openFixtureDetails(match) {
            activeFixture = match;
            const kickoff = new Date(match.utcDate);
            const score = match.score?.fullTime;
            document.getElementById('dialog-teams').textContent = `${match.homeTeam.name} vs ${match.awayTeam.name}`;
            document.getElementById('dialog-score').textContent = score && score.home !== null
                ? `${score.home} – ${score.away}` : fixtureStatus(match).toUpperCase();
            document.getElementById('dialog-meta').textContent = [
                match.competition.name,
                kickoff.toLocaleString([], {dateStyle: 'full', timeStyle: 'short'}),
                match.venue || 'Venue to be confirmed',
                `Timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`,
            ].join(' • ');
            document.getElementById('fixture-dialog').showModal();
        }

        function downloadCalendarFixture(match) {
            const start = new Date(match.utcDate);
            const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
            const icsDate = value => value.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
            const summary = `${match.homeTeam.name} vs ${match.awayTeam.name}`.replace(/[;,]/g, '');
            const content = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VEVENT',
                `DTSTART:${icsDate(start)}`, `DTEND:${icsDate(end)}`,
                `SUMMARY:${summary}`, `LOCATION:${(match.venue || '').replace(/[;,]/g, '')}`,
                'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
            const link = document.createElement('a');
            link.href = URL.createObjectURL(new Blob([content], {type: 'text/calendar'}));
            link.download = `${summary.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.ics`;
            link.click();
            URL.revokeObjectURL(link.href);
        }

        // Load matches when page loads
        document.getElementById('previous-date').addEventListener('click', () => shiftDate(-1));
        document.getElementById('next-date').addEventListener('click', () => shiftDate(1));
        document.getElementById('today-date').addEventListener('click', () => chooseDate(formatLocalDate(new Date())));
        document.getElementById('date-picker').addEventListener('change', event => chooseDate(event.target.value));
        ['fixture-search', 'competition-filter', 'status-filter', 'favorites-filter'].forEach(id => {
            document.getElementById(id).addEventListener('input', renderFilteredFixtures);
        });
        document.getElementById('matches-content').addEventListener('click', event => {
            const action = event.target.closest('[data-action]');
            if (action?.dataset.action === 'clear-filters') {
                document.getElementById('fixture-search').value = '';
                document.getElementById('competition-filter').value = '';
                document.getElementById('status-filter').value = '';
                document.getElementById('favorites-filter').value = '';
                renderFilteredFixtures();
                return;
            }
            const row = event.target.closest('[data-fixture-id]');
            if (!action || !row || !fixturePayload) return;
            const match = fixturePayload.matches.find(item => fixtureKey(item) === decodeURIComponent(row.dataset.fixtureId));
            if (!match) return;
            if (action.dataset.action === 'favorite') {
                const key = fixtureKey(match);
                favoriteFixtures.has(key) ? favoriteFixtures.delete(key) : favoriteFixtures.add(key);
                localStorage.setItem('favoriteFixtures', JSON.stringify([...favoriteFixtures]));
                renderFilteredFixtures();
            } else {
                openFixtureDetails(match);
            }
        });
        document.getElementById('close-dialog').addEventListener('click', () => document.getElementById('fixture-dialog').close());
        document.getElementById('calendar-action').addEventListener('click', () => activeFixture && downloadCalendarFixture(activeFixture));
        document.getElementById('share-action').addEventListener('click', async () => {
            if (!activeFixture) return;
            const text = `${activeFixture.homeTeam.name} vs ${activeFixture.awayTeam.name}`;
            if (navigator.share) await navigator.share({title: text, text, url: window.location.href});
            else await navigator.clipboard.writeText(`${text} ${window.location.href}`);
        });
        document.addEventListener('DOMContentLoaded', loadTodaysMatches);
        document.addEventListener('visibilitychange', scheduleRefresh);
