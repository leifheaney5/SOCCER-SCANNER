"""Pure functions for calculating team and squad insights."""
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
