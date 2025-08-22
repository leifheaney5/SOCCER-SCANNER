# Soccer Scanner - API Documentation

## Overview

The Soccer Scanner API provides RESTful endpoints for accessing football team data, match information, and league statistics. All endpoints return JSON responses and follow standard HTTP status codes.

## Base URL

```
http://localhost:5000/api
```

## Authentication

API requires a Football-data.org API key configured in environment variables. No authentication required for client requests.

## Endpoints

### Get Competitions

Retrieve list of available football competitions.

**Endpoint:** `GET /api/competitions`

**Response:**
```json
{
  "competitions": [
    {
      "id": 2021,
      "name": "Premier League",
      "plan": "TIER_ONE",
      "area": {
        "name": "England"
      }
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `500` - API error

### Get Teams

Retrieve teams for a specific competition.

**Endpoint:** `GET /api/teams/{competition_id}`

**Parameters:**
- `competition_id` (required) - Competition ID from competitions endpoint

**Response:**
```json
{
  "teams": [
    {
      "id": 57,
      "name": "Arsenal FC",
      "crest": "https://crests.football-data.org/57.png"
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Competition not found
- `500` - API error

### Get Team Analysis

Retrieve comprehensive team analysis including stats, matches, and squad data.

**Endpoint:** `GET /api/team-analysis/{team_id}`

**Parameters:**
- `team_id` (required) - Team ID from teams endpoint

**Response:**
```json
{
  "team_info": {
    "id": 57,
    "name": "Arsenal FC",
    "founded": 1886,
    "venue": "Emirates Stadium",
    "clubColors": "Red / White",
    "crest": "https://crests.football-data.org/57.png"
  },
  "stats": {
    "wins": 0,
    "draws": 0,
    "losses": 0,
    "win_percentage": 0,
    "goals_for": 0,
    "goals_against": 0,
    "goal_difference": 0,
    "clean_sheets": 0,
    "form": [],
    "home_record": {"wins": 0, "draws": 0, "losses": 0},
    "away_record": {"wins": 0, "draws": 0, "losses": 0}
  },
  "recent_matches": [
    {
      "homeTeam": {"id": 57, "name": "Arsenal FC"},
      "awayTeam": {"id": 61, "name": "Chelsea FC"},
      "score": {"fullTime": {"home": 2, "away": 1}},
      "utcDate": "2025-08-22T15:00:00Z",
      "competition": {"name": "Premier League"}
    }
  ],
  "upcoming_matches": [],
  "top_performers": {
    "squad_summary": {
      "total_players": 25,
      "average_age": 26.4,
      "youngest_age": 18,
      "oldest_age": 34,
      "total_nationalities": 12
    },
    "nationality_breakdown": {
      "England": 8,
      "Brazil": 3,
      "France": 2
    },
    "full_squad_by_position": {
      "Goalkeepers": [
        {
          "name": "Aaron Ramsdale",
          "position": "Goalkeeper",
          "nationality": "England",
          "age": 25,
          "shirtNumber": 1
        }
      ]
    }
  }
}
```

**Status Codes:**
- `200` - Success
- `404` - Team not found
- `500` - API error

### Get Today's Matches

Retrieve matches scheduled for today across multiple competitions.

**Endpoint:** `GET /api/matches-today`

**Response:**
```json
{
  "matches": [
    {
      "competition": "Premier League",
      "homeTeam": "Arsenal",
      "awayTeam": "Chelsea",
      "time": "15:00",
      "status": "TIMED"
    }
  ],
  "stats": {
    "espn_api": 14,
    "football_data_fallback": 0,
    "total_unique": 14
  }
}
```

**Status Codes:**
- `200` - Success
- `500` - API error

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error message description"
}
```

## Rate Limits

- Football-data.org free tier: 10 requests per minute
- ESPN API: No documented limits
- Application implements graceful degradation when limits are reached

## Data Sources

- **Primary**: Football-data.org API for team and competition data
- **Secondary**: ESPN API for live match data
- **Embedded**: SofaScore widgets for league tables

## Response Times

- Team analysis: 2-5 seconds (multiple API calls)
- Competitions/Teams: 1-2 seconds
- Today's matches: 1-3 seconds

## Example Usage

### JavaScript Fetch Example

```javascript
// Get competitions
const response = await fetch('/api/competitions');
const data = await response.json();

// Get teams for Premier League
const teams = await fetch('/api/teams/2021');
const teamData = await teams.json();

// Analyze Arsenal
const analysis = await fetch('/api/team-analysis/57');
const teamAnalysis = await analysis.json();
```

### Python Requests Example

```python
import requests

# Get competitions
response = requests.get('http://localhost:5000/api/competitions')
competitions = response.json()

# Get team analysis
team_analysis = requests.get('http://localhost:5000/api/team-analysis/57')
data = team_analysis.json()
```

## Development Notes

- All endpoints handle CORS for development
- Debug logging available in development mode
- Environment variables required for API keys
- Fallback mechanisms implemented for API failures
