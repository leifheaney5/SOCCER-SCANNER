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

        recent = self._matches(team_id, limit=10, status='FINISHED')
        upcoming = self._matches(team_id, limit=20, status='SCHEDULED')
        all_matches = self._matches(team_id, limit=50)

        return {
            'team_info': team_info,
            'squad': squad,
            'formation_data': analyze_squad_formation(squad),
            'recent_matches': recent,
            'upcoming_matches': upcoming,
            'stats': calculate_team_stats(recent, team_id),
            'top_performers': get_top_performers(recent, team_id, squad),
            'competition_analysis': analyze_team_competitions(all_matches, team_id),
        }

    def _matches(self, team_id, **params):
        try:
            return self.football_data.get(
                f'teams/{team_id}/matches', params=params
            ).get('matches', [])
        except requests.RequestException:
            return []
