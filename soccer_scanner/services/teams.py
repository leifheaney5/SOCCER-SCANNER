import requests

from .team_analytics import (
    analyze_squad_formation,
    analyze_team_competitions,
    calculate_team_stats,
    get_top_performers,
)


class TeamAnalysisService:
    """Orchestrates provider calls and team-domain calculations."""

    def __init__(self, football_data):
        self.football_data = football_data

    def analyze(self, team_id):
        team_info = self.football_data.get(f'teams/{team_id}')
        squad = team_info.get('squad', [])
        match_payload = self._match_payload(team_id, limit=50)
        all_matches = match_payload.get('matches', [])
        recent = [
            match for match in all_matches
            if match.get('status') in {'FINISHED', 'AWARDED'}
        ][:10]
        upcoming = [
            match for match in all_matches
            if match.get('status') in {'SCHEDULED', 'TIMED'}
        ][:20]
        stats = calculate_team_stats(recent, team_id)
        provider_played = match_payload.get('resultSet', {}).get('played')
        if isinstance(provider_played, int) and provider_played >= 0:
            stats['matches_played'] = provider_played

        return {
            'team_info': team_info,
            'squad': squad,
            'formation_data': analyze_squad_formation(squad),
            'recent_matches': recent,
            'upcoming_matches': upcoming,
            'stats': stats,
            'top_performers': get_top_performers(recent, team_id, squad),
            'competition_analysis': analyze_team_competitions(all_matches, team_id),
        }

    def _match_payload(self, team_id, **params):
        try:
            payload = self.football_data.get(f'teams/{team_id}/matches', params=params)
            return payload if isinstance(payload, dict) else {'matches': []}
        except requests.RequestException:
            return {'matches': []}
