from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
API_BASE_URL = 'https://api.football-data.org/v4'

def get_api_headers():
    return {
        'X-Auth-Token': API_KEY,
        'Content-Type': 'application/json'
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/matches-today')
def matches_today():
    return render_template('matches_today.html')

@app.route('/league-tables')
def league_tables():
    return render_template('league_tables.html')

@app.route('/api/competitions')
def get_competitions():
    """Get available competitions"""
    try:
        response = requests.get(
            f'{API_BASE_URL}/competitions',
            headers=get_api_headers()
        )
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch competitions'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams/<competition_id>')
def get_teams(competition_id):
    """Get teams for a specific competition"""
    try:
        response = requests.get(
            f'{API_BASE_URL}/competitions/{competition_id}/teams',
            headers=get_api_headers()
        )
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch teams'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/team-analysis/<team_id>')
def get_team_analysis(team_id):
    """Get comprehensive team analysis including matches, stats, squad, and info"""
    try:
        results = {}
        
        # Get team basic info (includes squad)
        team_response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}',
            headers=get_api_headers()
        )
        
        if team_response.status_code == 200:
            team_data = team_response.json()
            results['team_info'] = team_data
            
            # Extract squad information
            squad = team_data.get('squad', [])
            results['squad'] = squad
            results['formation_data'] = analyze_squad_formation(squad)
        else:
            return jsonify({'error': 'Failed to fetch team information'}), team_response.status_code
        
        # Get recent matches
        matches_response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}/matches',
            headers=get_api_headers(),
            params={'limit': 10, 'status': 'FINISHED'}
        )
        
        if matches_response.status_code == 200:
            matches_data = matches_response.json()
            recent_matches = matches_data.get('matches', [])
            results['recent_matches'] = recent_matches
            
            # Calculate recent form and stats
            results['stats'] = calculate_team_stats(recent_matches, team_id)
            
            # Get top performers from recent matches
            results['top_performers'] = get_top_performers(recent_matches, team_id, squad)
        else:
            results['recent_matches'] = []
            results['stats'] = {}
            results['top_performers'] = {}
        
        # Get upcoming matches to determine upcoming competitions
        upcoming_response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}/matches',
            headers=get_api_headers(),
            params={'limit': 20, 'status': 'SCHEDULED'}
        )
        
        if upcoming_response.status_code == 200:
            upcoming_data = upcoming_response.json()
            results['upcoming_matches'] = upcoming_data.get('matches', [])
            
            # Analyze competitions (both current and upcoming)
            all_matches_response = requests.get(
                f'{API_BASE_URL}/teams/{team_id}/matches',
                headers=get_api_headers(),
                params={'limit': 50}  # Get more matches to analyze competitions
            )
            
            if all_matches_response.status_code == 200:
                all_matches_data = all_matches_response.json()
                all_matches = all_matches_data.get('matches', [])
                results['competition_analysis'] = analyze_team_competitions(all_matches, team_id)
            else:
                results['competition_analysis'] = {'active': [], 'upcoming': [], 'completed': []}
        else:
            results['upcoming_matches'] = []
            results['competition_analysis'] = {'active': [], 'upcoming': [], 'completed': []}
        
        return jsonify(results)
        
    except Exception as e:
        print(f"DEBUG: Exception in team analysis: {e}")
        return jsonify({'error': str(e)}), 500

def analyze_squad_formation(squad):
    """Analyze squad composition and suggest typical formation"""
    if not squad:
        return {'formation': 'Unknown', 'positions': {}}
    
    positions = {}
    for player in squad:
        position = player.get('position', 'Unknown')
        if position not in positions:
            positions[position] = []
        positions[position].append(player)
    
    # Count players by position type
    goalkeepers = len(positions.get('Goalkeeper', []))
    defenders = len(positions.get('Defender', []))
    midfielders = len(positions.get('Midfielder', []))
    attackers = len(positions.get('Attacker', []))
    
    # Suggest common formation based on squad composition
    total_outfield = defenders + midfielders + attackers
    if total_outfield >= 10:
        # Common formations
        if defenders >= 4 and midfielders >= 3 and attackers >= 3:
            formation = "4-3-3"
        elif defenders >= 4 and midfielders >= 4 and attackers >= 2:
            formation = "4-4-2"
        elif defenders >= 3 and midfielders >= 5 and attackers >= 2:
            formation = "3-5-2"
        elif defenders >= 5 and midfielders >= 3 and attackers >= 2:
            formation = "5-3-2"
        else:
            formation = "4-4-2"  # Default
    else:
        formation = "Unknown"
    
    return {
        'formation': formation,
        'positions': positions,
        'count': {
            'goalkeepers': goalkeepers,
            'defenders': defenders,
            'midfielders': midfielders,
            'attackers': attackers
        }
    }

def get_top_performers(matches, team_id, squad):
    """Return comprehensive squad data organized by position and age"""
    if not squad:
        return {
            'full_squad_by_position': {},
            'young_talents': [],
            'experienced_players': [],
            'squad_summary': {},
            'nationality_breakdown': {},
            'squad_analytics': {}
        }
    
    # Calculate ages and organize squad
    squad_with_ages = []
    for player in squad:
        player_data = {
            'name': player.get('name', 'Unknown'),
            'position': player.get('position', 'Unknown'),
            'nationality': player.get('nationality', 'Unknown'),
            'age': None,
            'dateOfBirth': player.get('dateOfBirth')
        }
        
        # Calculate age if birth date is available
        if player.get('dateOfBirth'):
            try:
                from datetime import datetime
                birth_date = datetime.strptime(player['dateOfBirth'], '%Y-%m-%d')
                today = datetime.now()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                player_data['age'] = age
            except:
                pass
        
        squad_with_ages.append(player_data)
    
    # Filter out players without ages for age-based categories
    players_with_ages = [p for p in squad_with_ages if p['age'] is not None]
    
    # Organize all players by position groups
    position_groups = {
        'Goalkeepers': [],
        'Defenders': [],
        'Midfielders': [],
        'Attackers': [],
        'Other': []
    }
    
    for player in squad_with_ages:
        pos = player['position']
        if 'Goalkeeper' in pos:
            group = 'Goalkeepers'
        elif any(term in pos for term in ['Back', 'Defence']):
            group = 'Defenders'
        elif any(term in pos for term in ['Midfield']):
            group = 'Midfielders'
        elif any(term in pos for term in ['Forward', 'Winger', 'Attacker', 'Offence']):
            group = 'Attackers'
        else:
            group = 'Other'
        
        position_groups[group].append(player)
    
    # Sort players within each position group by age (youngest to oldest)
    for group in position_groups:
        position_groups[group].sort(key=lambda x: x['age'] if x['age'] is not None else 999)
    
    # Young talents (under 23)
    young_talents = [p for p in players_with_ages if p['age'] < 23]
    young_talents.sort(key=lambda x: x['age'])  # Youngest first
    
    # Experienced players (30+)
    experienced_players = [p for p in players_with_ages if p['age'] >= 30]
    experienced_players.sort(key=lambda x: x['age'], reverse=True)  # Oldest first
    
    # Nationality analysis
    nationality_counts = {}
    for player in squad_with_ages:
        nationality = player['nationality']
        if nationality != 'Unknown':
            nationality_counts[nationality] = nationality_counts.get(nationality, 0) + 1
    
    # Sort nationalities by count
    sorted_nationalities = sorted(nationality_counts.items(), key=lambda x: x[1], reverse=True)
    top_nationality = sorted_nationalities[0] if sorted_nationalities else ('Unknown', 0)
    
    # Age distribution analysis
    ages = [p['age'] for p in players_with_ages]
    age_groups = {
        'under_20': len([a for a in ages if a < 20]),
        'age_20_24': len([a for a in ages if 20 <= a <= 24]),
        'age_25_29': len([a for a in ages if 25 <= a <= 29]),
        'age_30_plus': len([a for a in ages if a >= 30])
    }
    
    # Position distribution
    position_counts = {}
    for group, players in position_groups.items():
        if players:  # Only include positions that have players
            position_counts[group] = len(players)
    
    # Squad summary statistics
    nationalities = list(set([p['nationality'] for p in squad_with_ages if p['nationality'] != 'Unknown']))
    
    squad_summary = {
        'total_players': len(squad_with_ages),
        'average_age': round(sum(ages) / len(ages), 1) if ages else 0,
        'youngest_age': min(ages) if ages else 0,
        'oldest_age': max(ages) if ages else 0,
        'total_nationalities': len(nationalities),
        'nationalities': sorted(nationalities)[:10]  # Top 10 most represented
    }
    
    # Additional squad analytics
    squad_analytics = {
        'top_nationality': {
            'country': top_nationality[0],
            'count': top_nationality[1],
            'percentage': round((top_nationality[1] / len(squad_with_ages)) * 100, 1) if squad_with_ages else 0
        },
        'age_distribution': age_groups,
        'position_distribution': position_counts,
        'international_experience': {
            'note': 'International caps data not available from current API',
            'total_caps': 'N/A'
        },
        'squad_depth': {
            'goalkeepers': len(position_groups['Goalkeepers']),
            'defenders': len(position_groups['Defenders']),
            'midfielders': len(position_groups['Midfielders']),
            'attackers': len(position_groups['Attackers'])
        }
    }
    
    return {
        'full_squad_by_position': position_groups,
        'young_talents': young_talents[:8],  # Top 8 youngest
        'experienced_players': experienced_players[:8],  # Top 8 oldest
        'squad_summary': squad_summary,
        'nationality_breakdown': dict(sorted_nationalities),
        'squad_analytics': squad_analytics
    }

def calculate_team_stats(matches, team_id):
    """Calculate team statistics from recent matches"""
    if not matches:
        return {}
    
    stats = {
        'wins': 0,
        'draws': 0,
        'losses': 0,
        'goals_for': 0,
        'goals_against': 0,
        'clean_sheets': 0,
        'form': [],  # Last 5 results
        'home_record': {'wins': 0, 'draws': 0, 'losses': 0},
        'away_record': {'wins': 0, 'draws': 0, 'losses': 0},
        'competitions': set()
    }
    
    team_id = int(team_id)
    
    for match in matches[:10]:  # Last 10 matches for stats
        home_team = match.get('homeTeam', {})
        away_team = match.get('awayTeam', {})
        score = match.get('score', {}).get('fullTime', {})
        home_score = score.get('home')
        away_score = score.get('away')
        
        if home_score is None or away_score is None:
            continue
            
        # Add competition
        competition = match.get('competition', {})
        if competition.get('name'):
            stats['competitions'].add(competition.get('name'))
        
        is_home = home_team.get('id') == team_id
        team_score = home_score if is_home else away_score
        opponent_score = away_score if is_home else home_score
        
        # Goals
        stats['goals_for'] += team_score
        stats['goals_against'] += opponent_score
        
        # Clean sheets
        if opponent_score == 0:
            stats['clean_sheets'] += 1
        
        # Results
        if team_score > opponent_score:
            result = 'W'
            stats['wins'] += 1
            if is_home:
                stats['home_record']['wins'] += 1
            else:
                stats['away_record']['wins'] += 1
        elif team_score < opponent_score:
            result = 'L'
            stats['losses'] += 1
            if is_home:
                stats['home_record']['losses'] += 1
            else:
                stats['away_record']['losses'] += 1
        else:
            result = 'D'
            stats['draws'] += 1
            if is_home:
                stats['home_record']['draws'] += 1
            else:
                stats['away_record']['draws'] += 1
        
        # Form (last 5 for visual)
        if len(stats['form']) < 5:
            stats['form'].append(result)
    
    # Convert set to list for JSON serialization
    stats['competitions'] = list(stats['competitions'])
    
    # Calculate additional metrics
    total_matches = stats['wins'] + stats['draws'] + stats['losses']
    if total_matches > 0:
        stats['win_percentage'] = round((stats['wins'] / total_matches) * 100, 1)
        stats['points'] = (stats['wins'] * 3) + stats['draws']
        stats['average_goals_for'] = round(stats['goals_for'] / total_matches, 1)
        stats['average_goals_against'] = round(stats['goals_against'] / total_matches, 1)
        stats['goal_difference'] = stats['goals_for'] - stats['goals_against']
    
    return stats

def analyze_team_competitions(matches, team_id):
    """Analyze team's competitions across the season"""
    from datetime import datetime, timedelta, timezone
    
    competitions = {}
    current_date = datetime.now(timezone.utc)  # Make timezone-aware
    
    for match in matches:
        competition = match.get('competition', {})
        comp_name = competition.get('name', 'Unknown')
        comp_id = competition.get('id')
        
        if comp_id not in competitions:
            competitions[comp_id] = {
                'name': comp_name,
                'type': competition.get('type', 'Unknown'),
                'code': competition.get('code', ''),
                'emblem': competition.get('emblem', ''),
                'matches': [],
                'status': 'unknown',
                'stage_info': {},
                'next_match': None,
                'last_match': None
            }
        
        # Add match to competition
        match_date = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        competitions[comp_id]['matches'].append({
            'date': match_date,
            'status': match.get('status'),
            'stage': match.get('stage'),
            'matchday': match.get('matchday'),
            'opponent': match.get('awayTeam') if match.get('homeTeam', {}).get('id') == int(team_id) else match.get('homeTeam')
        })
    
    # Analyze each competition
    active_competitions = []
    upcoming_competitions = []
    completed_competitions = []
    
    for comp_id, comp_data in competitions.items():
        matches = comp_data['matches']
        if not matches:
            continue
            
        # Sort matches by date
        matches.sort(key=lambda x: x['date'])
        
        # Determine competition status
        latest_match = matches[-1]
        earliest_match = matches[0]
        
        # Check for upcoming matches
        upcoming_matches = [m for m in matches if m['date'] > current_date and m['status'] in ['SCHEDULED', 'TIMED']]
        recent_matches = [m for m in matches if m['date'] <= current_date and m['status'] in ['FINISHED', 'LIVE', 'IN_PLAY']]
        
        comp_data['next_match'] = upcoming_matches[0] if upcoming_matches else None
        comp_data['last_match'] = recent_matches[-1] if recent_matches else None
        
        # Categorize competition
        if upcoming_matches and recent_matches:
            # Has both past and future matches - currently active
            comp_data['status'] = 'active'
            comp_data['matches_played'] = len(recent_matches)
            comp_data['matches_remaining'] = len(upcoming_matches)
            active_competitions.append(comp_data)
        elif upcoming_matches and not recent_matches:
            # Only future matches - upcoming competition
            comp_data['status'] = 'upcoming'
            comp_data['matches_remaining'] = len(upcoming_matches)
            comp_data['starts'] = upcoming_matches[0]['date']
            upcoming_competitions.append(comp_data)
        elif recent_matches and not upcoming_matches:
            # Only past matches - completed or eliminated
            comp_data['status'] = 'completed'
            comp_data['matches_played'] = len(recent_matches)
            comp_data['ended'] = recent_matches[-1]['date']
            completed_competitions.append(comp_data)
    
    # Sort competitions by importance and date
    def sort_competitions(comps):
        priority_order = {
            'UEFA Champions League': 1,
            'UEFA Europa League': 2,
            'UEFA Conference League': 3,
            'Premier League': 4,
            'La Liga': 4, 'Primera Division': 4,
            'Serie A': 4,
            'Bundesliga': 4,
            'Ligue 1': 4,
            'FA Cup': 5,
            'Copa del Rey': 5,
            'DFB-Pokal': 5,
            'Coppa Italia': 5,
            'EFL Cup': 6,
            'Championship': 7
        }
        return sorted(comps, key=lambda x: (
            priority_order.get(x['name'], 99),
            x.get('starts', current_date) if x['status'] == 'upcoming' else current_date
        ))
    
    return {
        'active': sort_competitions(active_competitions),
        'upcoming': sort_competitions(upcoming_competitions),
        'completed': sort_competitions(completed_competitions),
        'total_competitions': len(competitions)
    }

@app.route('/api/team/<team_id>')
def get_team_info(team_id):
    """Get team information"""
    try:
        response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}',
            headers=get_api_headers()
        )
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch team info'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-matches/<team_id>')
def debug_team_matches(team_id):
    """Debug endpoint to see what match data we can access"""
    try:
        # Test different endpoints to see what's available
        results = {}
        
        # Try team matches
        team_response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}/matches',
            headers=get_api_headers()
        )
        results['team_matches_status'] = team_response.status_code
        if team_response.status_code == 200:
            team_data = team_response.json()
            results['team_matches_count'] = len(team_data.get('matches', []))
            results['team_matches_sample'] = team_data.get('matches', [])[:3]  # First 3 matches
        else:
            results['team_matches_error'] = team_response.text
        
        # Try with different parameters
        team_response2 = requests.get(
            f'{API_BASE_URL}/teams/{team_id}/matches',
            headers=get_api_headers(),
            params={'limit': 10}
        )
        results['team_matches_limited_status'] = team_response2.status_code
        if team_response2.status_code == 200:
            team_data2 = team_response2.json()
            results['team_matches_limited_count'] = len(team_data2.get('matches', []))
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def convert_espn_to_standard_format(espn_event, league_name):
    """Convert ESPN API format to standard match format"""
    try:
        # Extract basic match information
        match_id = espn_event.get('id')
        status = espn_event.get('status', {}).get('type', {}).get('name', 'SCHEDULED')
        
        # Map ESPN status to our format
        status_mapping = {
            'STATUS_SCHEDULED': 'SCHEDULED',
            'STATUS_IN_PROGRESS': 'LIVE',
            'STATUS_FINAL': 'FINISHED',
            'STATUS_POSTPONED': 'POSTPONED',
            'STATUS_CANCELED': 'CANCELLED'
        }
        
        mapped_status = status_mapping.get(status, 'SCHEDULED')
        
        # Extract team information
        competitors = espn_event.get('competitions', [{}])[0].get('competitors', [])
        if len(competitors) < 2:
            return None
            
        home_team = None
        away_team = None
        
        for competitor in competitors:
            team_data = {
                'id': competitor.get('team', {}).get('id'),
                'name': competitor.get('team', {}).get('displayName'),
                'shortName': competitor.get('team', {}).get('abbreviation'),
                'tla': competitor.get('team', {}).get('abbreviation'),
                'crest': competitor.get('team', {}).get('logo')
            }
            
            if competitor.get('homeAway') == 'home':
                home_team = team_data
            else:
                away_team = team_data
        
        if not home_team or not away_team:
            return None
        
        # Extract score information
        home_score = None
        away_score = None
        
        if mapped_status == 'FINISHED' or mapped_status == 'LIVE':
            for competitor in competitors:
                score = competitor.get('score')
                if competitor.get('homeAway') == 'home':
                    home_score = score
                else:
                    away_score = score
        
        # Extract date and venue
        date_str = espn_event.get('date')
        venue_info = espn_event.get('competitions', [{}])[0].get('venue', {})
        venue_name = venue_info.get('fullName', 'Unknown Venue')
        
        # Build standard format match
        standard_match = {
            'id': f"espn_{match_id}",
            'utcDate': date_str,
            'status': mapped_status,
            'stage': 'REGULAR_SEASON',
            'group': None,
            'lastUpdated': espn_event.get('date'),
            'homeTeam': home_team,
            'awayTeam': away_team,
            'score': {
                'winner': None,
                'duration': 'REGULAR',
                'fullTime': {
                    'home': home_score,
                    'away': away_score
                },
                'halfTime': {
                    'home': None,
                    'away': None
                }
            },
            'competition': {
                'id': f"espn_{league_name.lower().replace(' ', '_')}",
                'name': league_name,
                'code': league_name.upper()[:3],
                'type': 'LEAGUE',
                'emblem': None
            },
            'season': {
                'id': 2024,
                'startDate': '2024-08-01',
                'endDate': '2025-05-31',
                'currentMatchday': 1
            },
            'venue': venue_name,
            'referees': []
        }
        
        # Determine winner if match is finished
        if mapped_status == 'FINISHED' and home_score is not None and away_score is not None:
            if home_score > away_score:
                standard_match['score']['winner'] = 'HOME_TEAM'
            elif away_score > home_score:
                standard_match['score']['winner'] = 'AWAY_TEAM'
            else:
                standard_match['score']['winner'] = 'DRAW'
        
        return standard_match
        
    except Exception as e:
        print(f"DEBUG: Error converting ESPN match format: {e}")
        return None

@app.route('/api/matches-today')
def get_matches_today():
    """Get all matches scheduled for today from ESPN API as primary source"""
    try:
        from datetime import datetime, timedelta
        import json
        
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Format dates for API
        date_from = today.strftime('%Y-%m-%d')
        date_to = tomorrow.strftime('%Y-%m-%d')
        
        print(f"DEBUG: Fetching matches from ESPN API for {date_from}")
        
        all_matches = []
        source_stats = {
            'espn_api': 0,
            'football_data_fallback': 0,
            'total_unique': 0
        }
        
        # Primary Source: ESPN API - Top 20 Global Competitions
        espn_leagues = {
            # Tier 1: Elite European Leagues
            'eng.1': 'Premier League',           # England - Premier League
            'esp.1': 'La Liga',                  # Spain - La Liga
            'ger.1': 'Bundesliga',               # Germany - Bundesliga
            'ita.1': 'Serie A',                  # Italy - Serie A
            'fra.1': 'Ligue 1',                  # France - Ligue 1
            
            # Tier 1: European Competitions
            'uefa.champions': 'Champions League', # UEFA Champions League
            'uefa.europa': 'Europa League',      # UEFA Europa League
            'uefa.europa.conf': 'Conference League', # UEFA Conference League
            
            # Tier 2: Major European Leagues
            'ned.1': 'Eredivisie',              # Netherlands - Eredivisie
            'por.1': 'Primeira Liga',           # Portugal - Primeira Liga
            'bel.1': 'Pro League',              # Belgium - Pro League
            'aut.1': 'Austrian Bundesliga',     # Austria - Bundesliga
            'tur.1': 'Süper Lig',               # Turkey - Süper Lig
            'sco.1': 'Scottish Premiership',    # Scotland - Premiership
            
            # Tier 2: Second Divisions
            'eng.2': 'Championship',            # England - Championship
            'esp.2': 'Segunda División',        # Spain - Segunda División
            'ger.2': '2. Bundesliga',           # Germany - 2. Bundesliga
            'ita.2': 'Serie B',                 # Italy - Serie B
            
            # Tier 3: Americas & International
            'bra.1': 'Brasileirão',             # Brazil - Série A
            'arg.1': 'Liga Profesional',        # Argentina - Liga Profesional
        }
        
        matches_found = False
        extended_search = False
        
        # Try to get today's matches from ESPN
        for league_id, league_name in espn_leagues.items():
            try:
                # ESPN API endpoint for scoreboard
                espn_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
                params = {
                    'dates': today.strftime('%Y%m%d'),
                    'limit': 50
                }
                
                response = requests.get(espn_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('events', [])
                    
                    for event in events:
                        # Convert ESPN format to our standard format
                        match = convert_espn_to_standard_format(event, league_name)
                        if match:
                            all_matches.append(match)
                            matches_found = True
                    
                    if events:
                        print(f"DEBUG: Found {len(events)} matches from ESPN {league_name}")
                        
            except Exception as e:
                print(f"DEBUG: Error fetching from ESPN {league_name}: {e}")
                continue
        
        source_stats['espn_api'] = len(all_matches)
        
        # If no matches found for today, get extended date range from ESPN
        if not matches_found:
            print("DEBUG: No matches found for today, fetching recent and upcoming from ESPN...")
            extended_search = True
            
            # Get matches from past 3 days and next 7 days
            for days_offset in range(-3, 8):
                target_date = today + timedelta(days=days_offset)
                if target_date == today:
                    continue  # Already checked today
                
                for league_id, league_name in list(espn_leagues.items())[:5]:  # Limit to major leagues for extended search
                    try:
                        espn_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
                        params = {
                            'dates': target_date.strftime('%Y%m%d'),
                            'limit': 10
                        }
                        
                        response = requests.get(espn_url, params=params, timeout=8)
                        
                        if response.status_code == 200:
                            data = response.json()
                            events = data.get('events', [])
                            
                            for event in events:
                                match = convert_espn_to_standard_format(event, league_name)
                                if match:
                                    all_matches.append(match)
                            
                            if events:
                                print(f"DEBUG: Found {len(events)} matches from ESPN {league_name} on {target_date}")
                                
                    except Exception as e:
                        continue
                
                # Break if we have enough matches
                if len(all_matches) >= 20:
                    break
        
        # Fallback: Try football-data.org if ESPN didn't return enough matches
        if len(all_matches) < 5:
            print("DEBUG: Using football-data.org as fallback...")
            try:
                fb_date_from = date_from if not extended_search else (today - timedelta(days=3)).strftime('%Y-%m-%d')
                fb_date_to = date_to if not extended_search else (today + timedelta(days=7)).strftime('%Y-%m-%d')
                
                response = requests.get(
                    f'{API_BASE_URL}/matches',
                    headers=get_api_headers(),
                    params={
                        'dateFrom': fb_date_from,
                        'dateTo': fb_date_to
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    fb_matches = data.get('matches', [])
                    all_matches.extend(fb_matches)
                    source_stats['football_data_fallback'] = len(fb_matches)
                    print(f"DEBUG: Added {len(fb_matches)} matches from football-data.org fallback")
                    
            except Exception as e:
                print(f"DEBUG: Football-data.org fallback failed: {e}")
        
        # Process and enhance matches
        final_matches = []
        today_matches = []
        future_matches = []
        
        for match in all_matches:
            try:
                # Handle both ESPN and football-data formats
                if 'date' in match:  # ESPN format
                    match_date = datetime.fromisoformat(match['date'].replace('Z', '+00:00')).date()
                else:  # football-data format
                    match_date = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00')).date()
                
                # Only include matches from today onwards
                if match_date < today:
                    continue
                
                # Enhanced match data
                enhanced_match = {
                    **match,
                    'enhanced_info': {
                        'importance_score': calculate_match_importance(match),
                        'tv_coverage': determine_tv_coverage(match),
                        'attendance_estimate': estimate_attendance(match),
                        'rivalry_factor': check_rivalry_factor(match),
                        'match_date': match_date.strftime('%Y-%m-%d'),
                        'days_from_today': (match_date - today).days,
                        'source': 'ESPN' if 'date' in match else 'football-data.org'
                    }
                }
                
                # Categorize matches
                if match_date == today:
                    today_matches.append(enhanced_match)
                else:
                    future_matches.append(enhanced_match)
                    
            except Exception as e:
                print(f"DEBUG: Error processing match: {e}")
                continue
        
        # Show today's matches first, then upcoming matches for better user experience
        final_matches = today_matches + future_matches
        
        # If no matches today, show upcoming matches with clear messaging
        if not today_matches:
            print(f"DEBUG: No matches found for today ({today}), showing upcoming matches")
        else:
            print(f"DEBUG: Found {len(today_matches)} matches for today, plus {len(future_matches)} upcoming matches")
        
        source_stats['total_unique'] = len(final_matches)
        
        # Sort all matches by importance and proximity to today
        final_matches.sort(key=lambda x: (
            -x['enhanced_info']['importance_score'],  # Higher importance first
            x['enhanced_info']['days_from_today'],    # Then by how soon they are
            x.get('utcDate', '')                      # Then by time
        ))
        
        # Create featured matches (top 6 most important from all available matches)
        featured_matches = final_matches[:6] if len(final_matches) >= 6 else final_matches
        
        # Ensure featured matches are sorted by importance
        featured_matches.sort(key=lambda x: (
            -x['enhanced_info']['importance_score'],
            x['enhanced_info']['days_from_today'],
            x.get('utcDate', '')
        ))
        
        # Add match statistics
        match_stats = analyze_daily_matches(final_matches)
        
        print(f"DEBUG: Final stats - {source_stats}")
        
        return jsonify({
            'matches': final_matches,
            'featured_matches': featured_matches,
            'total_matches': len(final_matches),
            'date': date_from,
            'source_stats': source_stats,
            'match_statistics': match_stats,
            'last_updated': datetime.now().isoformat()
        })
            
    except Exception as e:
        print(f"DEBUG: Exception in matches-today: {e}")
        return jsonify({'error': str(e)}), 500

def calculate_match_importance(match):
    """Calculate importance score for a match (0-100)"""
    score = 0
    
    # Competition importance - Updated for Top 20 competitions
    competition = match.get('competition', {}).get('name', '')
    competition_scores = {
        # Tier 1: Elite Competitions (35-50 points)
        'Premier League': 35,
        'UEFA Champions League': 40,
        'FIFA World Cup': 50,
        'European Championship': 45,
        'La Liga': 32, 'Primera Division': 32,
        'Bundesliga': 30,
        'Serie A': 30,
        'Ligue 1': 28,
        
        # Tier 2: Major Competitions (20-27 points)
        'UEFA Europa League': 25,
        'UEFA Conference League': 20,
        'Copa Libertadores': 25,
        'Eredivisie': 22,
        'Primeira Liga': 20,
        'Pro League': 18,                    # Belgium
        'Austrian Bundesliga': 16,
        'Süper Lig': 18,                    # Turkey
        'Scottish Premiership': 15,
        
        # Tier 3: Second Divisions & Regional (12-18 points)
        'Championship': 18,                  # England Championship
        'Segunda División': 15,             # Spain Segunda
        '2. Bundesliga': 16,                # Germany 2. Bundesliga
        'Serie B': 14,                      # Italy Serie B
        'Brasileirão': 20,                  # Brazil Serie A
        'Liga Profesional': 18,            # Argentina
        
        # Tier 4: Domestic Cups & Others (8-15 points)
        'Copa del Rey': 15,
        'FA Cup': 15,
        'DFB-Pokal': 12,
        'Coppa Italia': 12,
        'Coupe de France': 10,
        'MLS': 12,
        'Liga MX': 14,
        'J1 League': 10,                    # Japan
        'K League 1': 8,                    # South Korea
        'Campeonato Brasileiro Série A': 20,
    }
    score += competition_scores.get(competition, 10)
    
    # Team quality/popularity boost
    home_team = match.get('homeTeam', {}).get('name', '')
    away_team = match.get('awayTeam', {}).get('name', '')
    
    big_clubs = [
        # Premier League (England)
        'Manchester United', 'Manchester City', 'Liverpool', 'Arsenal', 'Chelsea', 'Tottenham',
        'Newcastle United', 'Aston Villa', 'West Ham United',
        
        # La Liga (Spain)
        'Real Madrid', 'Barcelona', 'Atletico Madrid', 'Sevilla', 'Real Betis', 'Villarreal',
        
        # Bundesliga (Germany)
        'Bayern Munich', 'Borussia Dortmund', 'RB Leipzig', 'Bayer Leverkusen', 'Eintracht Frankfurt',
        
        # Serie A (Italy)
        'Juventus', 'AC Milan', 'Inter Milan', 'AS Roma', 'Napoli', 'Lazio', 'Atalanta', 'Fiorentina',
        
        # Ligue 1 (France)
        'Paris Saint-Germain', 'Olympique Marseille', 'Olympique Lyon', 'AS Monaco', 'Lille',
        
        # Eredivisie (Netherlands)
        'Ajax', 'PSV Eindhoven', 'Feyenoord', 'AZ Alkmaar',
        
        # Primeira Liga (Portugal)
        'Benfica', 'FC Porto', 'Sporting CP', 'SC Braga',
        
        # Pro League (Belgium)
        'Club Brugge', 'Anderlecht', 'Standard Liège', 'Genk',
        
        # Süper Lig (Turkey)
        'Galatasaray', 'Fenerbahce', 'Besiktas', 'Trabzonspor',
        
        # Scottish Premiership
        'Celtic', 'Rangers', 'Aberdeen',
        
        # Brasileirão (Brazil)
        'Flamengo', 'Palmeiras', 'Santos', 'São Paulo', 'Corinthians', 'Grêmio', 'Internacional',
        
        # Liga Profesional (Argentina)
        'River Plate', 'Boca Juniors', 'Racing Club', 'Independiente', 'San Lorenzo'
    ]
    
    if home_team in big_clubs or away_team in big_clubs:
        score += 15
    if home_team in big_clubs and away_team in big_clubs:
        score += 10  # Both teams are big clubs
    
    # Match status boost
    status = match.get('status', '')
    if status in ['LIVE', 'IN_PLAY']:
        score += 20
    elif status == 'TIMED':  # Scheduled but not started
        score += 5
    
    # Competition stage boost
    stage = match.get('stage', '')
    stage_boosts = {
        'FINAL': 20,
        'SEMI_FINALS': 15,
        'QUARTER_FINALS': 10,
        'ROUND_OF_16': 8,
        'LAST_16': 8,
        'PLAYOFFS': 5
    }
    score += stage_boosts.get(stage, 0)
    
    return min(score, 100)  # Cap at 100

def determine_tv_coverage(match):
    """Determine likely TV coverage for a match"""
    competition = match.get('competition', {}).get('name', '')
    importance = calculate_match_importance(match)
    
    if importance >= 70:
        return 'Prime Time TV'
    elif importance >= 50:
        return 'Major Sports Networks'
    elif importance >= 30:
        return 'Sports Channels'
    elif competition in ['Premier League', 'UEFA Champions League', 'La Liga', 'Serie A', 'Bundesliga']:
        return 'League Broadcasting'
    else:
        return 'Streaming/Regional'

def estimate_attendance(match):
    """Estimate attendance category"""
    importance = calculate_match_importance(match)
    venue = match.get('venue', '')
    
    # Famous large stadiums
    large_stadiums = ['Camp Nou', 'Santiago Bernabéu', 'Old Trafford', 'Emirates Stadium', 
                     'Allianz Arena', 'San Siro', 'Anfield', 'Etihad Stadium']
    
    if any(stadium in venue for stadium in large_stadiums):
        return 'Sold Out (70,000+)'
    elif importance >= 70:
        return 'High (50,000+)'
    elif importance >= 50:
        return 'Good (30,000+)'
    elif importance >= 30:
        return 'Moderate (15,000+)'
    else:
        return 'Low (5,000+)'

def check_rivalry_factor(match):
    """Check if this is a known rivalry match"""
    home_team = match.get('homeTeam', {}).get('name', '')
    away_team = match.get('awayTeam', {}).get('name', '')
    
    rivalries = {
        # Premier League
        ('Manchester United', 'Liverpool'): 'Historic Rivalry',
        ('Manchester United', 'Manchester City'): 'Manchester Derby',
        ('Arsenal', 'Tottenham'): 'North London Derby',
        ('Liverpool', 'Everton'): 'Merseyside Derby',
        ('Chelsea', 'Arsenal'): 'London Derby',
        
        # La Liga
        ('Real Madrid', 'Barcelona'): 'El Clásico',
        ('Real Madrid', 'Atletico Madrid'): 'Madrid Derby',
        ('Barcelona', 'Espanyol'): 'Barcelona Derby',
        
        # Serie A
        ('Juventus', 'AC Milan'): 'Classic Rivalry',
        ('Inter Milan', 'AC Milan'): 'Derby della Madonnina',
        ('AS Roma', 'Lazio'): 'Derby della Capitale',
        
        # Bundesliga
        ('Bayern Munich', 'Borussia Dortmund'): 'Der Klassiker',
        ('Schalke 04', 'Borussia Dortmund'): 'Revierderby',
        
        # Others
        ('Ajax', 'Feyenoord'): 'De Klassieker',
        ('Benfica', 'FC Porto'): 'O Clássico',
    }
    
    for (team1, team2), rivalry_name in rivalries.items():
        if (home_team == team1 and away_team == team2) or (home_team == team2 and away_team == team1):
            return rivalry_name
    
    return None

def analyze_daily_matches(matches):
    """Analyze the day's matches for interesting statistics"""
    stats = {
        'total_matches': len(matches),
        'by_competition': {},
        'by_time_slots': {
            'morning': 0,    # 6 AM - 12 PM
            'afternoon': 0,  # 12 PM - 6 PM
            'evening': 0,    # 6 PM - 12 AM
            'late_night': 0  # 12 AM - 6 AM
        },
        'live_matches': 0,
        'high_importance': 0,
        'rivalries': 0,
        'major_leagues': 0
    }
    
    for match in matches:
        # Competition breakdown
        comp_name = match.get('competition', {}).get('name', 'Unknown')
        stats['by_competition'][comp_name] = stats['by_competition'].get(comp_name, 0) + 1
        
        # Time slot analysis
        try:
            from datetime import datetime
            match_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            hour = match_time.hour
            
            if 6 <= hour < 12:
                stats['by_time_slots']['morning'] += 1
            elif 12 <= hour < 18:
                stats['by_time_slots']['afternoon'] += 1
            elif 18 <= hour < 24:
                stats['by_time_slots']['evening'] += 1
            else:
                stats['by_time_slots']['late_night'] += 1
        except:
            pass
        
        # Status analysis
        if match.get('status') in ['LIVE', 'IN_PLAY']:
            stats['live_matches'] += 1
        
        # Importance analysis
        importance = match.get('enhanced_info', {}).get('importance_score', 0)
        if importance >= 60:
            stats['high_importance'] += 1
        
        # Rivalry analysis
        if match.get('enhanced_info', {}).get('rivalry_factor'):
            stats['rivalries'] += 1
        
        # Major leagues
        major_leagues = ['Premier League', 'UEFA Champions League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']
        if comp_name in major_leagues:
            stats['major_leagues'] += 1
    
    return stats

@app.route('/api/team-players/<team_id>')
def get_team_players(team_id):
    """Get detailed player roster with statistics"""
    try:
        # Get team basic info (includes squad)
        team_response = requests.get(
            f'{API_BASE_URL}/teams/{team_id}',
            headers=get_api_headers()
        )
        
        if team_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch team information'}), team_response.status_code
        
        team_data = team_response.json()
        squad = team_data.get('squad', [])
        
        # Enhance squad data with additional information
        enhanced_squad = []
        for player in squad:
            enhanced_player = {
                'id': player.get('id'),
                'name': player.get('name'),
                'position': player.get('position'),
                'dateOfBirth': player.get('dateOfBirth'),
                'nationality': player.get('nationality'),
                'shirtNumber': player.get('shirtNumber'),
                'marketValue': player.get('marketValue'),
                'contract': player.get('contract', {}),
                # Calculate age
                'age': calculate_age(player.get('dateOfBirth')),
                # Calculate time at club
                'timeAtClub': calculate_time_at_club(player.get('contract', {})),
                # Mock season stats (in a real app, you'd get these from another API)
                'seasonStats': generate_mock_season_stats(player.get('position', 'Unknown'))
            }
            enhanced_squad.append(enhanced_player)
        
        # Group players by position
        players_by_position = {
            'Goalkeeper': [],
            'Defender': [],
            'Midfielder': [],
            'Attacker': [],
            'Unknown': []
        }
        
        for player in enhanced_squad:
            position = player.get('position', 'Unknown')
            # Map specific positions to general categories
            if 'Goalkeeper' in position:
                players_by_position['Goalkeeper'].append(player)
            elif any(term in position for term in ['Back', 'Defence']):
                players_by_position['Defender'].append(player)
            elif any(term in position for term in ['Midfield', 'Central Midfield', 'Defensive Midfield', 'Attacking Midfield']):
                players_by_position['Midfielder'].append(player)
            elif any(term in position for term in ['Forward', 'Winger', 'Attacker', 'Offence']):
                players_by_position['Attacker'].append(player)
            else:
                players_by_position['Unknown'].append(player)
        
        # Sort players within each position by shirt number
        for position in players_by_position:
            players_by_position[position].sort(key=lambda x: x.get('shirtNumber') or 999)
        
        return jsonify({
            'players': enhanced_squad,
            'playersByPosition': players_by_position,
            'totalPlayers': len(enhanced_squad)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_age(date_of_birth):
    """Calculate age from date of birth"""
    if not date_of_birth:
        return None
    
    try:
        from datetime import datetime
        birth_date = datetime.strptime(date_of_birth, '%Y-%m-%d')
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except:
        return None

def calculate_time_at_club(contract):
    """Calculate time at club from contract information"""
    if not contract or not contract.get('start'):
        return 'Unknown'
    
    try:
        from datetime import datetime
        start_date = datetime.strptime(contract['start'], '%Y-%m-%d')
        today = datetime.now()
        years = today.year - start_date.year
        months = today.month - start_date.month
        
        if months < 0:
            years -= 1
            months += 12
        
        if years > 0:
            return f"{years}y {months}m"
        else:
            return f"{months}m"
    except:
        return 'Unknown'

def generate_mock_season_stats(position):
    """Generate realistic mock season statistics based on position"""
    import random
    
    base_stats = {
        'appearances': random.randint(15, 35),
        'starts': 0,
        'goals': 0,
        'assists': 0,
        'yellowCards': random.randint(0, 8),
        'redCards': random.randint(0, 1),
        'totalMinutes': 0,
        'averageRating': round(random.uniform(6.0, 8.5), 1)
    }
    
    appearances = base_stats['appearances']
    base_stats['starts'] = random.randint(max(0, appearances - 10), appearances)
    base_stats['totalMinutes'] = base_stats['starts'] * 90 + random.randint(0, (appearances - base_stats['starts']) * 30)
    
    # Position-specific stats
    if position == 'Attacker':
        base_stats['goals'] = random.randint(5, 25)
        base_stats['assists'] = random.randint(2, 15)
    elif position == 'Midfielder':
        base_stats['goals'] = random.randint(0, 10)
        base_stats['assists'] = random.randint(3, 20)
    elif position == 'Defender':
        base_stats['goals'] = random.randint(0, 5)
        base_stats['assists'] = random.randint(0, 8)
        base_stats['cleanSheets'] = random.randint(5, 20)
    elif position == 'Goalkeeper':
        base_stats['goals'] = 0
        base_stats['assists'] = random.randint(0, 2)
        base_stats['cleanSheets'] = random.randint(8, 25)
        base_stats['saves'] = random.randint(80, 150)
    
    return base_stats

if __name__ == '__main__':
    if not API_KEY or API_KEY == 'your_api_key_here':
        print("Warning: Please set your FOOTBALL_DATA_API_KEY in the .env file")
        print("You can get a free API key from https://www.football-data.org/client/register")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
