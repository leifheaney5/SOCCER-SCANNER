"""Pure fixture presentation analytics and legacy compatibility helpers."""

from soccer_scanner.providers.espn import normalize_event


_LEGACY_STATUS = {
    'scheduled': 'SCHEDULED',
    'delayed': 'DELAYED',
    'in_progress': 'LIVE',
    'half_time': 'HALFTIME',
    'extra_time': 'LIVE',
    'penalties': 'LIVE',
    'finished': 'FINISHED',
    'postponed': 'POSTPONED',
    'cancelled': 'CANCELLED',
    'suspended': 'SUSPENDED',
    'abandoned': 'CANCELLED',
    'unknown': 'UNKNOWN',
}


def convert_espn_to_standard_format(espn_event, league_name, league_id=None):
    """Return a non-fabricated legacy shape while v1 remains supported."""
    provider_league_id = league_id or f'legacy:{league_name.casefold().replace(" ", "-")}'
    normalized = normalize_event(espn_event, provider_league_id, league_name)
    if normalized is None:
        return None
    provider_id = normalized['providerIds']['espn']
    return {
        **normalized,
        'id': f'espn_{provider_id}',
        'status': _LEGACY_STATUS[normalized['status']['code']],
        'rawStatus': normalized['status'],
        'lastUpdated': normalized['sourceUpdatedAt'],
    }

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
