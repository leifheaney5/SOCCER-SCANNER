import requests


class FootballDataClient:
    """Small, reusable client for football-data.org."""

    def __init__(self, api_key, base_url, timeout=(3.05, 8), session=None):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_key or '',
            'Accept': 'application/json',
        })

    def get(self, path, params=None):
        response = self.session.get(
            f'{self.base_url}/{path.lstrip("/")}',
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
