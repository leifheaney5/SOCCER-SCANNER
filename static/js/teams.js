let competitions = [];
        let teams = [];

        // Load competitions on page load
        window.addEventListener('load', loadCompetitions);

        async function loadCompetitions() {
            try {
                const response = await fetch('/api/competitions');
                const data = await response.json();
                
                if (data.competitions) {
                    competitions = data.competitions;
                    populateCompetitions();
                } else {
                    showError('Failed to load competitions');
                }
            } catch (error) {
                showError('Error loading competitions: ' + error.message);
            }
        }

        function populateCompetitions() {
            const select = document.getElementById('competitionSelect');
            safeDOM.setHTML(select, '<option value="">Select a competition</option>');
            
            // Filter for major competitions
            const majorCompetitions = competitions.filter(comp => 
                comp.plan === 'TIER_ONE' || comp.plan === 'TIER_TWO'
            );
            
            majorCompetitions.forEach(competition => {
                const option = document.createElement('option');
                option.value = competition.id;
                option.textContent = competition.name;
                select.appendChild(option);
            });

            select.addEventListener('change', function() {
                if (this.value) {
                    loadTeams(this.value);
                } else {
                    document.getElementById('teamSelector').classList.add('is-hidden');
                    document.getElementById('analyzeBtn').disabled = true;
                }
            });
        }

        async function loadTeams(competitionId) {
            try {
                document.getElementById('teamSelector').classList.add('is-hidden');
                document.getElementById('analyzeBtn').disabled = true;
                
                const response = await fetch(`/api/teams/${competitionId}`);
                const data = await response.json();
                
                if (data.teams) {
                    teams = data.teams;
                    populateTeams();
                    document.getElementById('teamSelector').classList.remove('is-hidden');
                } else {
                    showError('Failed to load teams for this competition');
                }
            } catch (error) {
                showError('Error loading teams: ' + error.message);
            }
        }

        function populateTeams(query = '') {
            const teamSelect = document.getElementById('teamSelect');
            
            safeDOM.setHTML(teamSelect, '<option value="">Select a team</option>');
            
            teams.filter(team => team.name.toLowerCase().includes(query.toLowerCase())).forEach(team => {
                const option = document.createElement('option');
                option.value = team.id;
                option.textContent = team.name;
                teamSelect.appendChild(option);
            });

        }

        async function analyzeTeam() {
            const teamId = document.getElementById('teamSelect').value;
            const resultsDiv = document.getElementById('results');
            
            if (!teamId) {
                showError('Please select a team to analyze');
                return;
            }

            // Show loading
            resultsDiv.classList.add('is-visible');
            safeDOM.setHTML(resultsDiv, `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Analyzing team...</p>
                </div>
            `);

            try {
                const response = await fetch(`/api/team-analysis/${teamId}`);
                const data = await response.json();
                
                if (data.error) {
                    showError(data.error);
                    return;
                }

                displayTeamAnalysis(data);
                
            } catch (error) {
                showError('Error analyzing team: ' + error.message);
            }
        }

        function displayTeamAnalysis(data) {
            const resultsDiv = document.getElementById('results');
            const team = data.team_info;
            const stats = data.stats;
            const recentMatches = data.recent_matches || [];
            const upcomingMatches = data.upcoming_matches || [];
            const topPerformers = data.top_performers || {};
            const squad = data.squad || [];
            
            // Create form display
            let formHtml = '';
            if (stats.form && stats.form.length > 0) {
                formHtml = stats.form.map(result => {
                    const color = result === 'W' ? '#4CAF50' : result === 'L' ? '#f44336' : '#ff9800';
                    return `<span style="background: ${color}; color: white; padding: 5px 8px; border-radius: 3px; margin: 2px; font-weight: bold;">${result}</span>`;
                }).join('');
            }
            
            // Create timeline data for performance visualization
            const timelineData = createTimelineData(recentMatches, team.id);
            
            // Recent matches HTML
            let recentMatchesHtml = '';
            recentMatches.slice(0, 5).forEach(match => {
                const homeTeam = match.homeTeam.name;
                const awayTeam = match.awayTeam.name;
                const score = match.score.fullTime;
                const date = new Date(match.utcDate).toLocaleDateString();
                const competition = match.competition.name;
                
                // Determine result for the team
                const isHome = match.homeTeam.id === team.id;
                const teamScore = isHome ? score.home : score.away;
                const opponentScore = isHome ? score.away : score.home;
                let resultClass = '';
                if (teamScore > opponentScore) resultClass = 'win';
                else if (teamScore < opponentScore) resultClass = 'loss';
                else resultClass = 'draw';
                
                recentMatchesHtml += `
                    <div class="match-item ${resultClass}">
                        <div class="match-teams">${homeTeam} vs ${awayTeam}</div>
                        <div class="match-score">${score.home} - ${score.away}</div>
                        <div class="match-date">${date} • ${competition}</div>
                    </div>
                `;
            });
            
            // Upcoming matches HTML
            let upcomingMatchesHtml = '';
            upcomingMatches.slice(0, 3).forEach(match => {
                const homeTeam = match.homeTeam.name;
                const awayTeam = match.awayTeam.name;
                const date = new Date(match.utcDate).toLocaleDateString();
                const time = new Date(match.utcDate).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                const competition = match.competition.name;
                
                upcomingMatchesHtml += `
                    <div class="match-item upcoming">
                        <div class="match-teams">${homeTeam} vs ${awayTeam}</div>
                        <div class="match-date">${date} ${time} • ${competition}</div>
                    </div>
                `;
            });

            safeDOM.setHTML(resultsDiv, `
                <div class="team-analysis">
                    <!-- Season Context Banner -->
                    <div class="season-context">
                        <div class="season-info">
                            <h4>Current Season Analysis</h4>
                            <p>All statistics and match data reflect the current ${new Date().getFullYear()}-${new Date().getFullYear() + 1} season performance.</p>
                        </div>
                    </div>

                    <!-- Team Header -->
                    <div class="team-header">
                        <div class="team-crest">
                            ${team.crest ? `<img src="${team.crest}" alt="${team.name}" style="width: 80px; height: 80px; object-fit: contain;">` : '⚽'}
                        </div>
                        <div class="team-details">
                            <h1>${team.name}</h1>
                            <p><strong>Founded:</strong> ${team.founded || 'Unknown'}</p>
                            <p><strong>Venue:</strong> ${team.venue || 'Unknown'}</p>
                            <p><strong>Colors:</strong> ${team.clubColors || 'Unknown'}</p>
                            ${topPerformers && topPerformers.squad_summary ? `
                                <div class="squad-overview-compact">
                                    <p><strong>Squad:</strong> ${topPerformers.squad_summary.total_players} players • Avg age ${topPerformers.squad_summary.average_age} • Ages ${topPerformers.squad_summary.youngest_age}-${topPerformers.squad_summary.oldest_age} • ${topPerformers.squad_summary.total_nationalities} nationalities</p>
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <!-- Performance Timeline -->
                    <div class="timeline-section">
                        <h3 class="text-white">Performance Timeline (Last 10 Matches)</h3>
                        <div class="timeline-container">
                            ${timelineData.html}
                        </div>
                        <div class="timeline-legend">
                            <span class="legend-item"><span class="legend-color win"></span> Win</span>
                            <span class="legend-item"><span class="legend-color draw"></span> Draw</span>
                            <span class="legend-item"><span class="legend-color loss"></span> Loss</span>
                        </div>
                    </div>

                    <!-- Statistics Grid (Hidden - all stats showing 0) -->
                    <div class="stats-grid" style="display: none;">
                        <div class="stat-card">
                            <div class="stat-number">${stats.wins || 0}</div>
                            <div class="stat-label">Wins</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.draws || 0}</div>
                            <div class="stat-label">Draws</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.losses || 0}</div>
                            <div class="stat-label">Losses</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.win_percentage || 0}%</div>
                            <div class="stat-label">Win Rate</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.goals_for || 0}</div>
                            <div class="stat-label">Goals For</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.goals_against || 0}</div>
                            <div class="stat-label">Goals Against</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.goal_difference || 0}</div>
                            <div class="stat-label">Goal Difference</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.clean_sheets || 0}</div>
                            <div class="stat-label">Clean Sheets</div>
                        </div>
                    </div>

                    <!-- Current Form -->
                    ${formHtml ? `
                    <div class="form-section">
                        <h3>Recent Form (Last 5 matches)</h3>
                        <div class="form-display">${formHtml}</div>
                    </div>
                    ` : ''}

                    <!-- Home vs Away Record -->
                    <div class="record-comparison">
                        <div class="record-section">
                            <h4>Home Record</h4>
                            <div class="record-stats">
                                <span class="record-stat">W: ${stats.home_record?.wins || 0}</span>
                                <span class="record-stat">D: ${stats.home_record?.draws || 0}</span>
                                <span class="record-stat">L: ${stats.home_record?.losses || 0}</span>
                            </div>
                        </div>
                        <div class="record-section">
                            <h4>Away Record</h4>
                            <div class="record-stats">
                                <span class="record-stat">W: ${stats.away_record?.wins || 0}</span>
                                <span class="record-stat">D: ${stats.away_record?.draws || 0}</span>
                                <span class="record-stat">L: ${stats.away_record?.losses || 0}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Recent Matches -->
                    <div class="matches-section">
                        <h3>Recent Matches</h3>
                        <div class="matches-list">
                            ${recentMatchesHtml || '<p>No recent matches found</p>'}
                        </div>
                    </div>

                    <!-- Squad Highlights Section -->
                    <div class="performers-section">
                        <h3>Squad Highlights</h3>
                        <div class="performers-container">
                            ${createTopPerformersDisplay(topPerformers)}
                        </div>
                    </div>

                    <!-- Upcoming Matches -->
                    ${upcomingMatchesHtml ? `
                    <div class="matches-section">
                        <h3>Upcoming Matches</h3>
                        <div class="matches-list">
                            ${upcomingMatchesHtml}
                        </div>
                    </div>
                    ` : ''}

                    <!-- Competitions -->
                    ${data.competitions ? `
                    <div class="competitions-section">
                        <h3>Competition Analysis</h3>
                        
                        ${data.competitions.active && data.competitions.active.length > 0 ? `
                            <div class="competition-category">
                                <h4 class="competition-status-title active">Active Competitions</h4>
                                ${data.competitions.active.map(comp => `
                                    <div class="competition-item active-competition">
                                        <div class="competition-header">
                                            ${comp.emblem ? `<img src="${comp.emblem}" alt="${comp.name}" class="competition-emblem">` : '<i class="fas fa-trophy"></i>'}
                                            <div class="competition-info">
                                                <span class="competition-name">${comp.name}</span>
                                                <span class="competition-type">${comp.type}</span>
                                            </div>
                                            <div class="competition-status">
                                                <span class="status-badge active">Active</span>
                                            </div>
                                        </div>
                                        <div class="competition-details">
                                            <div class="match-stats">
                                                <span class="stat-item">
                                                    <i class="fas fa-check-circle"></i>
                                                    ${comp.matches_played || 0} played
                                                </span>
                                                <span class="stat-item">
                                                    <i class="fas fa-clock"></i>
                                                    ${comp.matches_remaining || 0} remaining
                                                </span>
                                            </div>
                                            ${comp.next_match ? `
                                                <div class="next-match">
                                                    <i class="fas fa-calendar-plus"></i>
                                                    Next: vs ${comp.next_match.opponent?.name || 'TBD'} 
                                                    (${new Date(comp.next_match.date).toLocaleDateString()})
                                                </div>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                        
                        ${data.competitions.upcoming && data.competitions.upcoming.length > 0 ? `
                            <div class="competition-category">
                                <h4 class="competition-status-title upcoming">🚀 Upcoming Competitions</h4>
                                ${data.competitions.upcoming.map(comp => `
                                    <div class="competition-item upcoming-competition">
                                        <div class="competition-header">
                                            ${comp.emblem ? `<img src="${comp.emblem}" alt="${comp.name}" class="competition-emblem">` : '<i class="fas fa-trophy"></i>'}
                                            <div class="competition-info">
                                                <span class="competition-name">${comp.name}</span>
                                                <span class="competition-type">${comp.type}</span>
                                            </div>
                                            <div class="competition-status">
                                                <span class="status-badge upcoming">Upcoming</span>
                                            </div>
                                        </div>
                                        <div class="competition-details">
                                            <div class="match-stats">
                                                <span class="stat-item">
                                                    <i class="fas fa-calendar-check"></i>
                                                    ${comp.matches_remaining || 0} matches scheduled
                                                </span>
                                            </div>
                                            ${comp.starts ? `
                                                <div class="starts-info">
                                                    <i class="fas fa-play-circle"></i>
                                                    Starts: ${new Date(comp.starts).toLocaleDateString()}
                                                </div>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                        
                        ${(!data.competitions.active || data.competitions.active.length === 0) && 
                          (!data.competitions.upcoming || data.competitions.upcoming.length === 0) ? `
                            <div class="no-competitions">
                                <i class="fas fa-info-circle"></i>
                                No competition data available for this team
                            </div>
                        ` : ''}
                    </div>
                    ` : stats.competitions && stats.competitions.length > 0 ? `
                    <div class="competitions-section">
                        <h3>Active Competitions</h3>
                        <div class="competitions-list">
                            ${stats.competitions.map(comp => `<span class="competition-badge">${comp}</span>`).join('')}
                        </div>
                    </div>
                    ` : ''}
                </div>
            `);
        }

        function createTimelineData(matches, teamId) {
            if (!matches || matches.length === 0) {
                return { html: '<p>No match data available for timeline</p>' };
            }

            // Sort matches by date (oldest first for timeline)
            const sortedMatches = matches.slice().reverse();
            
            let timelineHtml = '<div class="timeline">';
            
            sortedMatches.forEach((match, index) => {
                const homeTeam = match.homeTeam;
                const awayTeam = match.awayTeam;
                const score = match.score.fullTime;
                const formattedDate = new Date(match.utcDate).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                });
                
                // Determine result for the team
                const isHome = homeTeam.id === teamId;
                const teamScore = isHome ? score.home : score.away;
                const opponentScore = isHome ? score.away : score.home;
                const opponent = isHome ? awayTeam.name : homeTeam.name;
                const venue = isHome ? 'H' : 'A';
                
                let result = '';
                let resultClass = '';
                if (teamScore > opponentScore) {
                    result = 'W';
                    resultClass = 'win';
                } else if (teamScore < opponentScore) {
                    result = 'L';
                    resultClass = 'loss';
                } else {
                    result = 'D';
                    resultClass = 'draw';
                }
                
                timelineHtml += `
                    <div class="timeline-item ${resultClass}">
                        <div class="timeline-marker"></div>
                        <div class="timeline-content">
                            <div class="timeline-result">${result}</div>
                            <div class="timeline-score">${teamScore}-${opponentScore}</div>
                            <div class="timeline-opponent">${opponent}</div>
                            <div class="timeline-details">${formattedDate} (${venue})</div>
                        </div>
                    </div>
                `;
            });
            
            timelineHtml += '</div>';
            
            return { html: timelineHtml };
        }

        function displayMatchResults(data, team1Name, team2Name) {
            const resultsDiv = document.getElementById('results');
            const record = data.record;
            
            let matchesHtml = '';
            data.matches.slice(0, 10).forEach(match => {
                const homeTeam = match.homeTeam.name;
                const awayTeam = match.awayTeam.name;
                const score = match.score.fullTime;
                const date = new Date(match.utcDate).toLocaleDateString();
                
                matchesHtml += `
                    <div class="match-item">
                        <div class="match-teams">${homeTeam} vs ${awayTeam}</div>
                        <div class="match-score">${score.home} - ${score.away}</div>
                        <div class="match-date">${date}</div>
                    </div>
                `;
            });

            safeDOM.setHTML(resultsDiv, `
                <div class="matches-found">
                    <h2>📊 Head-to-Head Record</h2>
                    <p><strong>${team1Name}</strong> vs <strong>${team2Name}</strong></p>
                    
                    <div class="record-summary">
                        <div class="record-item">
                            <div class="number">${record.team1_wins}</div>
                            <div class="label">${team1Name} Wins</div>
                        </div>
                        <div class="record-item">
                            <div class="number">${record.draws}</div>
                            <div class="label">Draws</div>
                        </div>
                        <div class="record-item">
                            <div class="number">${record.team2_wins}</div>
                            <div class="label">${team2Name} Wins</div>
                        </div>
                        <div class="record-item">
                            <div class="number">${record.total_matches}</div>
                            <div class="label">Total Matches</div>
                        </div>
                    </div>
                    
                    <h3>Recent Matches</h3>
                    <div class="matches-list">
                        ${matchesHtml}
                    </div>
                    ${data.matches.length > 10 ? `<p style="text-align: center; margin-top: 15px; color: #666;">Showing 10 of ${data.matches.length} total matches</p>` : ''}
                    ${data.note ? `<p style="text-align: center; margin-top: 15px; color: #666; font-style: italic; background: #f8f9fa; padding: 10px; border-radius: 5px;">${data.note}</p>` : ''}
                </div>
            `);
        }

        function showError(message) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.classList.add('is-visible');
            safeDOM.setHTML(resultsDiv, `
                <div class="error">
                    <strong>Error:</strong> ${message}
                </div>
            `);
        }

        function createTopPerformersDisplay(topPerformers) {
            if (!topPerformers || Object.keys(topPerformers).length === 0) {
                return '<p>No squad data available</p>';
            }

            let html = '';

            // Squad Summary
            if (topPerformers.squad_summary) {
                const summary = topPerformers.squad_summary;
                html += `
                    <div class="roster-summary">
                        <div class="summary-item">
                            <span class="summary-number">${summary.total_players}</span>
                            <span class="summary-label">Total Players</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-number">${summary.average_age}</span>
                            <span class="summary-label">Avg Age</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-number">${summary.youngest_age}-${summary.oldest_age}</span>
                            <span class="summary-label">Age Range</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-number">${summary.total_nationalities}</span>
                            <span class="summary-label">Nationalities</span>
                        </div>
                    </div>
                `;
            }

            // Squad Analytics Section
            if (topPerformers.squad_analytics) {
                const analytics = topPerformers.squad_analytics;
                html += `
                    <div class="squad-analytics-section">
                        <div class="analytics-grid">
                            ${analytics.top_nationality ? `
                                <div class="analytics-card">
                                    <h4>${getFlagEmoji(analytics.top_nationality.country)} Top Nationality</h4>
                                    <div class="analytics-stat">
                                        <span class="stat-value">${analytics.top_nationality.country}</span>
                                        <span class="stat-detail">${analytics.top_nationality.count} players (${analytics.top_nationality.percentage}%)</span>
                                    </div>
                                </div>
                            ` : ''}
                            
                            <div class="analytics-card">
                                <h4>🏟️ Squad Depth</h4>
                                <div class="depth-breakdown">
                                    <div class="depth-item">
                                        <span>🥅 GK: ${analytics.squad_depth.goalkeepers}</span>
                                    </div>
                                    <div class="depth-item">
                                        <span>🛡️ DEF: ${analytics.squad_depth.defenders}</span>
                                    </div>
                                    <div class="depth-item">
                                        <span>⚽ MID: ${analytics.squad_depth.midfielders}</span>
                                    </div>
                                    <div class="depth-item">
                                        <span>🎯 ATT: ${analytics.squad_depth.attackers}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="analytics-card">
                                <h4>Age Distribution</h4>
                                <div class="age-breakdown">
                                    <div class="age-group">
                                        <span class="age-label">Under 20:</span>
                                        <span class="age-count">${analytics.age_distribution.under_20}</span>
                                    </div>
                                    <div class="age-group">
                                        <span class="age-label">20-24:</span>
                                        <span class="age-count">${analytics.age_distribution.age_20_24}</span>
                                    </div>
                                    <div class="age-group">
                                        <span class="age-label">25-29:</span>
                                        <span class="age-count">${analytics.age_distribution.age_25_29}</span>
                                    </div>
                                    <div class="age-group">
                                        <span class="age-label">30+:</span>
                                        <span class="age-count">${analytics.age_distribution.age_30_plus}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Nationality Breakdown
            if (topPerformers.nationality_breakdown) {
                const nationalities = Object.entries(topPerformers.nationality_breakdown).slice(0, 10);
                if (nationalities.length > 0) {
                    html += `
                        <div class="nationality-breakdown">
                            <h4>🌍 Nationality Breakdown</h4>
                            <div class="nationality-grid">
                                ${nationalities.map(([country, count]) => `
                                    <div class="nationality-item">
                                        <span class="flag">${getFlagEmoji(country)}</span>
                                        <span class="country">${country}</span>
                                        <span class="count">${count}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }
            }

            // Full Squad by Position using player cards
            if (topPerformers.full_squad_by_position) {
                const positions = topPerformers.full_squad_by_position;
                const positionOrder = ['Goalkeepers', 'Defenders', 'Midfielders', 'Attackers'];
                
                positionOrder.forEach(positionGroup => {
                    const players = positions[positionGroup];
                    if (players && players.length > 0) {
                        const positionIcons = {
                            'Goalkeepers': '🥅',
                            'Defenders': '🛡️',
                            'Midfielders': '⚽',
                            'Attackers': '🎯'
                        };
                        
                        html += `
                            <div class="position-group">
                                <div class="position-header">${positionIcons[positionGroup] || '👤'} ${positionGroup} (${players.length})</div>
                                <div class="players-grid">
                                    ${players.map(player => createPlayerCard(player)).join('')}
                                </div>
                            </div>
                        `;
                    }
                });
            }

            return html || '<p>No squad data available</p>';
        }

        function calculateAge(dateOfBirth) {
            if (!dateOfBirth) return 'Unknown';
            const today = new Date();
            const birthDate = new Date(dateOfBirth);
            let age = today.getFullYear() - birthDate.getFullYear();
            const monthDiff = today.getMonth() - birthDate.getMonth();
            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                age--;
            }
            return age;
        }

        // Function to get country flag emoji or image
        function getFlagEmoji(nationality) {
            const countryFlags = {
                // Europe
                'England':'GB', // Using Union Jack for England
                'Spain': '🇪🇸',
                'France': '🇫🇷',
                'Germany': '🇩🇪',
                'Italy': '🇮🇹',
                'Portugal': '🇵🇹',
                'Netherlands': '🇳🇱',
                'Belgium': '🇧🇪',
                'Croatia': '🇭🇷',
                'Poland': '🇵🇱',
                'Ukraine': '🇺🇦',
                'Serbia': '🇷🇸',
                'Denmark': '🇩🇰',
                'Austria': '🇦🇹',
                'Switzerland': '🇨🇭',
                'Czech Republic': '🇨🇿',
                'Slovakia': '🇸🇰',
                'Hungary': '🇭🇺',
                'Slovenia': '🇸🇮',
                'Romania': '🇷🇴',
                'Bulgaria': '🇧🇬',
                'Greece': '🇬🇷',
                'Turkey': '🇹🇷',
                'Norway': '🇳🇴',
                'Sweden': '🇸🇪',
                'Finland': '🇫🇮',
                'Ireland': '🇮🇪',
                'Scotland': '🇬🇧', // Using Union Jack for Scotland
                'Wales': '🇬🇧', // Using Union Jack for Wales
                'Northern Ireland': '🇬🇧',
                'Iceland': '🇮🇸',
                'Russia': '🇷🇺',
                'Belarus': '🇧🇾',
                'Lithuania': '🇱🇹',
                'Latvia': '🇱🇻',
                'Estonia': '🇪🇪',
                'Moldova': '🇲🇩',
                'Albania': '🇦🇱',
                'Montenegro': '🇲🇪',
                'Bosnia and Herzegovina': '🇧🇦',
                'North Macedonia': '🇲🇰',
                'Kosovo': '🇽🇰',
                
                // Americas
                'Brazil': '🇧🇷',
                'Argentina': '🇦🇷',
                'Canada': '🇨🇦',
                'United States': '🇺🇸',
                'USA': '🇺🇸',
                'Mexico': '🇲🇽',
                'Colombia': '🇨🇴',
                'Uruguay': '🇺🇾',
                'Chile': '🇨🇱',
                'Peru': '🇵🇪',
                'Ecuador': '🇪🇨',
                'Venezuela': '🇻🇪',
                'Paraguay': '🇵🇾',
                'Bolivia': '🇧🇴',
                'Jamaica': '🇯🇲',
                'Costa Rica': '🇨🇷',
                'Panama': '🇵🇦',
                'Honduras': '🇭🇳',
                'Guatemala': '🇬🇹',
                'El Salvador': '🇸🇻',
                'Nicaragua': '🇳🇮',
                'Cuba': '🇨🇺',
                'Dominican Republic': '🇩🇴',
                'Haiti': '🇭🇹',
                'Trinidad and Tobago': '🇹🇹',
                
                // Asia
                'Japan': '🇯🇵',
                'South Korea': '🇰🇷',
                'China': '🇨🇳',
                'India': '🇮🇳',
                'Iran': '🇮🇷',
                'Saudi Arabia': '🇸🇦',
                'Iraq': '🇮🇶',
                'Qatar': '🇶🇦',
                'UAE': '🇦🇪',
                'Israel': '🇮🇱',
                'Jordan': '🇯🇴',
                'Lebanon': '🇱🇧',
                'Syria': '🇸🇾',
                'Yemen': '🇾🇪',
                'Oman': '🇴🇲',
                'Kuwait': '🇰🇼',
                'Bahrain': '🇧🇭',
                'Afghanistan': '🇦🇫',
                'Pakistan': '🇵🇰',
                'Bangladesh': '🇧🇩',
                'Sri Lanka': '🇱🇰',
                'Thailand': '🇹🇭',
                'Vietnam': '🇻🇳',
                'Malaysia': '🇲🇾',
                'Singapore': '🇸🇬',
                'Indonesia': '🇮🇩',
                'Philippines': '🇵🇭',
                'Myanmar': '🇲🇲',
                'Cambodia': '🇰🇭',
                'Laos': '🇱🇦',
                'Mongolia': '🇲🇳',
                'North Korea': '🇰🇵',
                'Kazakhstan': '🇰🇿',
                'Uzbekistan': '🇺🇿',
                'Kyrgyzstan': '🇰🇬',
                'Tajikistan': '🇹🇯',
                'Turkmenistan': '🇹🇲',
                'Azerbaijan': '🇦🇿',
                'Armenia': '🇦🇲',
                'Georgia': '🇬🇪',
                
                // Africa
                'South Africa': '🇿🇦',
                'Nigeria': '🇳🇬',
                'Ghana': '🇬🇭',
                'Senegal': '🇸🇳',
                'Morocco': '🇲🇦',
                'Egypt': '🇪🇬',
                'Algeria': '🇩🇿',
                'Tunisia': '🇹🇳',
                'Cameroon': '🇨🇲',
                'Ivory Coast': '🇨🇮',
                'Mali': '🇲🇱',
                'Burkina Faso': '🇧🇫',
                'Guinea': '🇬🇳',
                'Congo': '🇨🇬',
                'DR Congo': '🇨🇩',
                'Kenya': '🇰🇪',
                'Ethiopia': '🇪🇹',
                'Tanzania': '🇹🇿',
                'Uganda': '🇺🇬',
                'Rwanda': '🇷🇼',
                'Burundi': '🇧🇮',
                'Angola': '🇦🇴',
                'Mozambique': '🇲🇿',
                'Zambia': '🇿🇲',
                'Zimbabwe': '🇿🇼',
                'Botswana': '🇧🇼',
                'Namibia': '🇳🇦',
                'Lesotho': '🇱🇸',
                'Eswatini': '🇸🇿',
                'Madagascar': '🇲🇬',
                'Mauritius': '🇲🇺',
                'Seychelles': '🇸🇨',
                'Cape Verde': '🇨🇻',
                'Gambia': '🇬🇲',
                'Guinea-Bissau': '🇬🇼',
                'Sierra Leone': '🇸🇱',
                'Liberia': '🇱🇷',
                'Togo': '🇹🇬',
                'Benin': '🇧🇯',
                'Niger': '🇳🇪',
                'Chad': '🇹🇩',
                'Central African Republic': '🇨🇫',
                'Gabon': '🇬🇦',
                'Equatorial Guinea': '🇬🇶',
                'Sao Tome and Principe': '🇸🇹',
                'Comoros': '🇰🇲',
                'Djibouti': '🇩🇯',
                'Eritrea': '🇪🇷',
                'Somalia': '🇸🇴',
                'Sudan': '🇸🇩',
                'South Sudan': '🇸🇸',
                'Libya': '🇱🇾',
                
                // Oceania
                'Australia': '🇦🇺',
                'New Zealand': '🇳🇿',
                'Fiji': '🇫🇯',
                'Papua New Guinea': '🇵🇬',
                'Solomon Islands': '🇸🇧',
                'Vanuatu': '🇻🇺',
                'Samoa': '🇼🇸',
                'Tonga': '🇹🇴',
                'Palau': '🇵🇼',
                'Marshall Islands': '🇲🇭',
                'Micronesia': '🇫🇲',
                'Kiribati': '🇰🇮',
                'Nauru': '🇳🇷',
                'Tuvalu': '🇹🇻'
            };
            return countryFlags[nationality] || '�';
        }

        function createPlayerCard(player) {
            const age = player.age || 'Unknown';
            const nationality = player.nationality || 'Unknown';
            
            return `
                <div class="player-card">
                    <div class="player-header">
                        <div class="player-number">${player.shirtNumber || '--'}</div>
                        <div class="player-info">
                            <div class="player-name">${player.name || 'Unknown'}</div>
                            <div class="player-meta">
                                <span>Age: ${age}</span>
                                <span>${getFlagEmoji(nationality)} ${nationality}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        document.getElementById('analyzeBtn').addEventListener('click', analyzeTeam);
        document.getElementById('teamSearch').addEventListener('input', event => populateTeams(event.target.value));
        document.getElementById('teamSelect').addEventListener('change', event => {
            document.getElementById('analyzeBtn').disabled = !event.target.value;
        });
