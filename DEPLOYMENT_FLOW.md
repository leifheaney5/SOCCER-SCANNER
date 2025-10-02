# 🚀 Deployment Flow

This document illustrates the deployment process from code to live application.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOCCER SCANNER DEPLOYMENT                      │
│                  From Code to Live Application                    │
└─────────────────────────────────────────────────────────────────┘

     ┌──────────────┐
     │   GitHub     │
     │  Repository  │
     └──────┬───────┘
            │
            │ Push/Merge to main
            ▼
     ┌──────────────┐
     │   GitHub     │
     │   Actions    │  ◄── Validates deployment config
     └──────┬───────┘      Checks syntax & dependencies
            │
            │ All checks pass ✓
            ▼
  ┌─────────────────────────────────────────────┐
  │         DEPLOYMENT PLATFORMS                │
  │  (Choose one - all are configured)          │
  └─────────────────────────────────────────────┘
            │
    ┌───────┴────────┬──────────┬──────────┐
    ▼                ▼          ▼          ▼
┌────────┐      ┌─────────┐ ┌────────┐ ┌────────┐
│ Render │      │ Railway │ │ Heroku │ │ Vercel │
│        │      │         │ │        │ │        │
│ • Auto │      │ • Auto  │ │ • CLI  │ │ • Auto │
│   deploy│     │   deploy│ │   push │ │   deploy│
│ • Free │      │ • Free  │ │ • Free*│ │ • Free │
│   tier │      │   tier  │ │   tier │ │   tier │
└───┬────┘      └────┬────┘ └───┬────┘ └───┬────┘
    │                │          │          │
    │    Reads       │          │          │
    │  render.yaml   │  railway.json  Procfile  vercel.json
    │                │          │          │
    └────────┬───────┴──────────┴──────────┘
             │
             │ Builds application:
             │ 1. Install dependencies
             │ 2. Configure environment
             │ 3. Start with gunicorn
             ▼
      ┌──────────────┐
      │   Your Live  │
      │  Application │
      │              │
      │ ✓ SSL/HTTPS  │
      │ ✓ Custom URL │
      │ ✓ Auto scale │
      │ ✓ Monitoring │
      └──────┬───────┘
             │
             │ Accessible at:
             ▼
  ┌──────────────────────────────┐
  │  https://your-app.domain.com │
  │                              │
  │  🏥 /health - Health check   │
  │  🏠 /       - Main app       │
  │  ⚽ /matches-today           │
  │  📊 /league-tables          │
  └──────────────────────────────┘
```

## Deployment Steps by Platform

### 🟢 Render (Recommended)

```
1. Fork/Clone repo
   ↓
2. Create Render account
   ↓
3. Connect GitHub repo
   ↓
4. Render auto-detects render.yaml
   ↓
5. Set FOOTBALL_DATA_API_KEY
   ↓
6. Deploy! (2-3 minutes)
   ↓
7. Live at: your-app.onrender.com
```

### 🔵 Railway

```
1. Fork/Clone repo
   ↓
2. Create Railway account
   ↓
3. New Project from GitHub
   ↓
4. Railway reads railway.json
   ↓
5. Set FOOTBALL_DATA_API_KEY
   ↓
6. Auto-deploy! (2-3 minutes)
   ↓
7. Live at: your-app.up.railway.app
```

### 🟣 Heroku

```
1. Fork/Clone repo
   ↓
2. Install Heroku CLI
   ↓
3. heroku create your-app
   ↓
4. Set config vars
   ↓
5. git push heroku main
   ↓
6. heroku open
   ↓
7. Live at: your-app.herokuapp.com
```

### ▲ Vercel

```
1. Fork/Clone repo
   ↓
2. Install Vercel CLI
   ↓
3. Run: vercel
   ↓
4. Set environment variables
   ↓
5. Deploy! (1-2 minutes)
   ↓
6. Live at: your-app.vercel.app
```

## Configuration Files Explained

### render.yaml
```yaml
services:
  - type: web              # Web service
    runtime: python        # Python environment
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app  # WSGI server
    envVars:
      - FOOTBALL_DATA_API_KEY    # Your API key
      - FLASK_ENV: production    # Production mode
```

### railway.json
```json
{
  "build": {
    "builder": "NIXPACKS"   # Auto-detect build
  },
  "deploy": {
    "startCommand": "gunicorn app:app",
    "healthcheckPath": "/health"
  }
}
```

### Procfile (Heroku)
```
web: gunicorn app:app
```

### vercel.json
```json
{
  "builds": [{
    "src": "app.py",
    "use": "@vercel/python"
  }],
  "routes": [{
    "src": "/(.*)",
    "dest": "app.py"
  }]
}
```

## Application Flow

```
User Request
    ↓
  HTTPS
    ↓
Load Balancer (Platform)
    ↓
  Gunicorn (WSGI Server)
    ↓
  Flask Application (app.py)
    ↓
  Routes:
    • / → index.html
    • /health → {"status": "healthy"}
    • /matches-today → matches_today.html
    • /league-tables → league_tables.html
    • /api/* → JSON responses
    ↓
  Templates (Jinja2)
    ↓
  HTML Response
    ↓
  User Browser
```

## Environment Variables Flow

```
Deployment Platform Dashboard
    ↓
Environment Variables Set:
  • FOOTBALL_DATA_API_KEY=xxx
  • FLASK_ENV=production
  • FLASK_DEBUG=False
  • PORT=5000 (auto-set by platform)
    ↓
Available in app.py via:
  os.getenv('VARIABLE_NAME')
    ↓
Used for:
  • API authentication
  • Configuration mode
  • Port binding
```

## Health Check Flow

```
Platform Health Check Service
    ↓
GET /health every 30 seconds
    ↓
Flask Route Handler
    ↓
return {
  "status": "healthy",
  "service": "Soccer Scanner"
}
    ↓
200 OK Status
    ↓
Platform: ✓ App is healthy
```

## CI/CD Flow (GitHub Actions)

```
Push to main/PR
    ↓
GitHub Actions Triggered
    ↓
Jobs:
  ✓ Check deployment files exist
  ✓ Validate Python syntax
  ✓ Install dependencies
  ✓ Test app imports
  ✓ Check gunicorn config
    ↓
All checks pass ✓
    ↓
Ready for deployment
    ↓
Platform auto-deploys (if configured)
```

## Monitoring Flow

```
Live Application
    ↓
Platform Monitoring
    ↓
Metrics Collected:
  • Request count
  • Response times
  • Error rates
  • CPU/Memory usage
  • Health check status
    ↓
Dashboard/Logs
    ↓
Alerts (if configured)
```

## Update Flow

```
Code changes committed
    ↓
Push to GitHub
    ↓
Platform detects changes
    ↓
Automatic rebuild:
  1. Pull latest code
  2. Install dependencies
  3. Run build command
  4. Start new instance
  5. Health check passes
  6. Switch traffic
  7. Old instance terminated
    ↓
Zero-downtime deployment ✓
```

## Troubleshooting Flow

```
Deployment Issue
    ↓
Check deployment logs
    ↓
Common issues:
  1. Missing env vars?
     → Set in platform dashboard
  2. Build failing?
     → Check requirements.txt
  3. App won't start?
     → Check gunicorn command
  4. Health check failing?
     → Verify /health endpoint
    ↓
Fix issue
    ↓
Redeploy
    ↓
Success! ✓
```

## Quick Reference

| Aspect | Details |
|--------|---------|
| **Build Time** | 2-3 minutes |
| **Deploy Time** | < 5 minutes total |
| **Health Check** | GET /health |
| **Logs** | Platform dashboard |
| **SSL** | Auto-provisioned |
| **Custom Domain** | Supported on all platforms |
| **Environment** | Python 3.11 |
| **WSGI Server** | Gunicorn |
| **Auto Deploy** | Yes (GitHub integration) |

---

For step-by-step instructions, see:
- **[DEPLOYMENT_QUICK_START.md](./DEPLOYMENT_QUICK_START.md)** - Get started in 5 minutes
- **[DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md)** - Platform comparison
- **[docs/deployment.md](./docs/deployment.md)** - Detailed guide
