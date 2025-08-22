# Soccer Scanner ⚽

A modern Flask web application that provides comprehensive football team analysis, live match data, and league standings. Built with clean architecture principles and integrating multiple sports APIs for the most complete football data experience.

![Soccer Scanner](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.7%2B-green.svg)
![Flask](https://img.shields.io/badge/flask-2.0%2B-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)


https://github.com/user-attachments/assets/e3f3b3a0-4b3b-4acf-bee6-9f3e491fda6a

https://github.com/user-attachments/assets/764c560d-b922-482a-9bba-d345ac31a563

<img width="2560" height="1253" alt="Soccer-Scanner-League-Tables" src="https://github.com/user-attachments/assets/f42d4bac-695a-4fc0-8b27-4703993dc3ba" />


## Features

### Team Analysis

- **Comprehensive Team Data**: Founded date, venue, colors, and crest
- **Performance Timeline**: Visual timeline of last 10 matches with results
- **Squad Analytics**: Player demographics, nationality breakdown, age distribution
- **Match History**: Recent match results with detailed information
- **Squad Management**: Complete player roster with positions and details

### Live Match Data

- **Today's Matches**: Real-time match data across 10+ competitions
- **Multiple Data Sources**: ESPN API primary with Football-data.org fallback
- **Competition Coverage**: Premier League, La Liga, Bundesliga, Serie A, and more

### League Tables

- **Live Standings**: Real-time league tables via SofaScore widgets
- **Major European Leagues**: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Liga Portugal
- **Professional Integration**: Official SofaScore embed widgets

### Technical Features

- **Responsive Design**: Mobile-first approach with dark theme
- **Clean Architecture**: Separation of concerns with modular design
- **Error Handling**: Graceful degradation and user-friendly error messages
- **API Integration**: Robust API handling with fallback mechanisms

## Quick Start

### Prerequisites

- Python 3.7 or higher
- Free API key from [football-data.org](https://www.football-data.org/client/register)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/soccer-comp.git
   cd soccer-comp
   ```

2. **Create virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**

   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and add your API key
   # Replace 'your_api_key_here' with your actual API key from football-data.org
   ```

5. **Run the application:**

   ```bash
   python app.py
   ```

6. **Open your browser:**
   Navigate to `http://localhost:5000`

## Usage

### Team Analysis Features

1. Select a competition from the dropdown (Premier League, La Liga, etc.)
2. Choose a team from the selected competition
3. Click "Analyze Team" to view comprehensive analysis
4. Explore team stats, squad details, and match history

### Live Matches

1. Navigate to "Upcoming Matches" tab
2. View live match data from multiple competitions
3. Access SofaScore links for detailed match information

### League Standings

1. Click "League Tables" tab
2. View live standings for 6 major European leagues
3. Tables update automatically with real-time data

## Documentation

For comprehensive technical documentation, please visit our [docs folder](./docs):

- **[System Architecture](./docs/architecture.md)** - Technical architecture and design principles
- **[API Documentation](./docs/api.md)** - Complete API endpoint reference
- **[System Diagrams](./docs/diagrams.md)** - Visual system architecture and data flow
- **[Deployment Guide](./docs/deployment.md)** - Multi-platform deployment instructions

## Tech Stack

- **Backend**: Python, Flask
- **APIs**: Football-data.org, ESPN, SofaScore
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Styling**: Custom CSS with dark theme
- **Data**: JSON REST APIs

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
FOOTBALL_DATA_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### API Keys

1. **Football-data.org**: Free tier provides 10 requests/minute
   - Register at: [football-data.org](https://www.football-data.org/client/register)
   - Copy your API key from the dashboard
   - Add key to `.env` file: `FOOTBALL_DATA_API_KEY=your_actual_key_here`

2. **ESPN API**: Public API, no key required
3. **SofaScore**: Embedded widgets, no key required

### First Time Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/yourusername/soccer-comp.git
cd soccer-comp

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Setup environment variables
cp .env.example .env
# Edit .env file and add your API key

# 6. Run the application
python app.py
```

The application will be available at `http://localhost:5000`

## Deployment

The application supports multiple deployment platforms:

- **Heroku**: One-click deployment ready
- **Railway**: Simple git-based deployment
- **DigitalOcean App Platform**: Scalable cloud deployment
- **Docker**: Containerized deployment
- **VPS**: Traditional server deployment

See [Deployment Guide](./docs/deployment.md) for detailed instructions.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Football-data.org](https://www.football-data.org/) for comprehensive football data
- [ESPN](https://www.espn.com/) for live match information
- [SofaScore](https://www.sofascore.com/) for league table widgets
- Flask community for excellent documentation and examples

---

**Soccer Scanner** - Making football accessible and beautiful. ⚽

## Usage

1. **Select a Competition:** Choose from available football competitions (Premier League, La Liga, etc.)
2. **Select Team:** Pick a team from the competition to analyze
3. **Analyze:** Click "Analyze Team" to see comprehensive team statistics and information
4. **Explore Results:** View team performance metrics, recent matches, and upcoming fixtures

## API Endpoints

- `GET /` - Main application page
- `GET /api/competitions` - Get available competitions
- `GET /api/teams/<competition_id>` - Get teams for a specific competition
- `GET /api/team-analysis/<team_id>` - Get comprehensive team analysis
- `GET /api/team/<team_id>` - Get individual team information
- `GET /api/debug-matches/<team_id>` - Debug endpoint for match data access

## Project Structure

```
soccer-comp/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (API key)
├── README.md          # This file
├── templates/
│   └── index.html     # Main web interface
└── static/            # Static assets (currently empty)
```

## Free API Limitations

The free tier of football-data.org API has some limitations:
- Limited competitions available
- Rate limiting (10 requests per minute)
- Historical data may be limited

For production use, consider upgrading to a paid plan for more comprehensive data access.

## Troubleshooting

### "Failed to fetch competitions" error
- Check that your API key is correctly set in the `.env` file
- Verify your API key is valid at football-data.org
- Check your internet connection

### "These teams have never faced off" message
- This is normal for teams that haven't played against each other
- Try teams from the same competition and division
- Some smaller competitions may have limited match history

### No teams loading
- Some competitions may not be available in the free tier
- Try selecting a different competition
- Check the browser console for any JavaScript errors

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the [MIT License](LICENSE).
