# Soccer Scanner - Deployment Guide

This guide provides step-by-step instructions to deploy Soccer Scanner to various hosting platforms, making it accessible for external users.

## Quick Deploy Options

### 1. Heroku (Recommended for Beginners)

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

**Steps:**
1. Click the button above or visit [Heroku](https://heroku.com)
2. Create a free account if you don't have one
3. Create a new app with a unique name
4. Connect to your GitHub repository
5. Set the environment variable:
   - `FOOTBALL_DATA_API_KEY` = your API key from [football-data.org](https://www.football-data.org/client/register)
6. Deploy the main branch
7. Your app will be live at `https://your-app-name.herokuapp.com`

**Command Line Deployment:**
```bash
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login to Heroku
heroku login

# Create a new app
heroku create your-app-name

# Set environment variables
heroku config:set FOOTBALL_DATA_API_KEY=your_api_key_here
heroku config:set FLASK_ENV=production

# Deploy
git push heroku main

# Open in browser
heroku open
```

### 2. Railway (Easiest Setup)

**Steps:**
1. Visit [Railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your `SOCCER-SCANNER` repository
5. Railway will auto-detect Python and deploy
6. Add environment variable in settings:
   - `FOOTBALL_DATA_API_KEY` = your API key
7. Your app will be live with an auto-generated URL

**Benefits:**
- Free tier with 500 hours/month
- Automatic HTTPS
- No credit card required for trial
- Easy custom domains

### 3. Render (Free Tier Available)

**Steps:**
1. Visit [Render.com](https://render.com)
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your repository
5. Configure:
   - **Name:** soccer-scanner
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Add environment variable:
   - `FOOTBALL_DATA_API_KEY` = your API key
7. Click "Create Web Service"
8. Your app will be live at `https://soccer-scanner.onrender.com`

### 4. DigitalOcean App Platform

**Steps:**
1. Visit [DigitalOcean Apps](https://cloud.digitalocean.com/apps)
2. Click "Create App"
3. Connect your GitHub repository
4. DigitalOcean will detect the `.do/app.yaml` configuration
5. Add the secret environment variable:
   - `FOOTBALL_DATA_API_KEY` = your API key
6. Review and create
7. Your app will deploy automatically

**Cost:** Starts at $5/month for basic tier

### 5. Docker Deployment

**Prerequisites:**
- Docker and Docker Compose installed
- Your API key ready

**Steps:**

1. **Clone the repository:**
```bash
git clone https://github.com/leifheaney5/SOCCER-SCANNER.git
cd SOCCER-SCANNER
```

2. **Create environment file:**
```bash
echo "FOOTBALL_DATA_API_KEY=your_api_key_here" > .env
```

3. **Build and run:**
```bash
docker-compose up -d
```

4. **Access the app:**
   - Open browser to `http://localhost:5000`

5. **View logs:**
```bash
docker-compose logs -f
```

6. **Stop the app:**
```bash
docker-compose down
```

**Deploy to Cloud with Docker:**

Once working locally, push to:
- **AWS ECS**
- **Google Cloud Run**
- **Azure Container Instances**
- **DigitalOcean Container Registry**

### 6. Vercel (Static Frontend Option)

While Vercel is primarily for static sites, you can deploy this as a serverless function:

1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel`
3. Follow the prompts
4. Set environment variable: `FOOTBALL_DATA_API_KEY`

Note: May require modifications for serverless deployment.

## Environment Variables

All deployment platforms require the following environment variable:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `FOOTBALL_DATA_API_KEY` | Yes | API key from football-data.org | `abc123def456...` |
| `FLASK_ENV` | No | Environment mode (production/development) | `production` |
| `PORT` | No | Port number (auto-set by most platforms) | `5000` |

## Getting Your API Key

1. Visit [football-data.org](https://www.football-data.org/client/register)
2. Register for a free account
3. Verify your email
4. Copy your API key from the dashboard
5. Use this key in your deployment configuration

**Free Tier Limits:**
- 10 requests per minute
- Access to major competitions
- Perfect for personal projects

## Post-Deployment Checklist

After deploying, verify:

- [ ] App loads successfully at the provided URL
- [ ] Environment variable is set correctly
- [ ] API calls are working (test by selecting a competition)
- [ ] All three pages are accessible:
  - [ ] Team Analysis (home page)
  - [ ] Matches Today
  - [ ] League Tables
- [ ] No errors in application logs
- [ ] SSL/HTTPS is enabled (automatic on most platforms)

## Troubleshooting

### "Failed to fetch competitions"
- **Cause:** API key not set or invalid
- **Solution:** Verify environment variable is set correctly

### App crashes on startup
- **Cause:** Missing dependencies
- **Solution:** Ensure `requirements.txt` includes all dependencies

### Port binding errors
- **Cause:** Port already in use or misconfigured
- **Solution:** Most platforms auto-assign port; ensure app uses `os.getenv('PORT')`

### API rate limit exceeded
- **Cause:** Too many requests
- **Solution:** Wait a minute or upgrade to paid API tier

## Monitoring & Maintenance

### Check Application Health

Most platforms provide:
- **Logs:** View application logs for errors
- **Metrics:** Monitor response times and uptime
- **Alerts:** Set up notifications for downtime

### Regular Maintenance

1. **Update Dependencies:**
```bash
pip list --outdated
pip install -U package_name
```

2. **Monitor API Usage:**
   - Check API key usage at football-data.org
   - Watch for rate limit warnings

3. **Keep API Key Secure:**
   - Never commit API key to repository
   - Use environment variables only
   - Rotate keys periodically

## Custom Domain Setup

Most platforms support custom domains:

1. **Purchase domain** (from Namecheap, Google Domains, etc.)
2. **Add domain in platform settings**
3. **Update DNS records** as instructed
4. **Enable SSL** (automatic on most platforms)

Example DNS records:
```
Type: CNAME
Name: www
Value: your-app.platform.com
```

## Scaling Considerations

For high traffic, consider:

1. **Upgrade hosting tier** for more resources
2. **Add caching** (Redis/Memcached) for API responses
3. **Use CDN** for static assets
4. **Database** for persistent storage (currently uses API only)
5. **Load balancing** for multiple instances

## Security Best Practices

- ✅ Use HTTPS (enabled by default on all recommended platforms)
- ✅ Keep dependencies updated
- ✅ Never expose API keys in code
- ✅ Use environment variables for secrets
- ✅ Monitor for security vulnerabilities
- ✅ Implement rate limiting if needed
- ✅ Regular backups of configuration

## Cost Estimates

| Platform | Free Tier | Paid Plans Start At |
|----------|-----------|---------------------|
| Heroku | 550 hours/month | $7/month |
| Railway | 500 hours/month | $5/month |
| Render | 750 hours/month | $7/month |
| DigitalOcean | No free tier | $5/month |
| Docker (self-hosted) | Server costs only | Varies |

## Support & Resources

- **Documentation:** [Full docs](./docs/)
- **Issues:** [GitHub Issues](https://github.com/leifheaney5/SOCCER-SCANNER/issues)
- **API Docs:** [Football-data.org](https://www.football-data.org/documentation/quickstart)

## Next Steps After Deployment

1. **Share your app URL** with users
2. **Test all features** on live site
3. **Monitor logs** for any errors
4. **Set up monitoring** for uptime
5. **Consider adding analytics** (Google Analytics, Plausible)
6. **Gather user feedback**
7. **Plan for scaling** if traffic grows

---

**Your Soccer Scanner app is now ready for external users! ⚽**

For detailed technical architecture, see [Architecture Documentation](./docs/architecture.md).
