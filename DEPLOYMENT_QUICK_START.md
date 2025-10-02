# 🚀 Quick Start Deployment Guide

This guide will help you deploy Soccer Scanner to make it publicly accessible in minutes.

## 📋 Prerequisites

1. A free API key from [football-data.org](https://www.football-data.org/client/register)
2. A GitHub account (you already have this if you're reading this!)

## 🎯 Recommended: Deploy to Render (Easiest & Free)

Render offers free hosting with automatic deployments from GitHub.

### Steps:

1. **Sign up for Render**
   - Go to [render.com](https://render.com)
   - Sign up with your GitHub account

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository: `leifheaney5/SOCCER-SCANNER`
   - Render will auto-detect the `render.yaml` configuration

3. **Set Environment Variable**
   - In the Render dashboard, go to "Environment"
   - Add: `FOOTBALL_DATA_API_KEY` with your API key value
   - Click "Save Changes"

4. **Deploy**
   - Render will automatically deploy your app
   - Your app will be live at: `https://your-app-name.onrender.com`
   - First deployment takes 2-3 minutes

**Note:** Free tier apps sleep after 15 minutes of inactivity and may take 30 seconds to wake up.

---

## 🚂 Alternative: Deploy to Railway

Railway provides simple deployment with generous free tier.

### Steps:

1. **Sign up for Railway**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project" → "Deploy from GitHub repo"
   - Select `leifheaney5/SOCCER-SCANNER`

3. **Add Environment Variable**
   - Click on your service
   - Go to "Variables" tab
   - Add: `FOOTBALL_DATA_API_KEY` = your API key

4. **Deploy**
   - Railway auto-deploys using the `railway.json` configuration
   - Your app will be live at the provided Railway URL

---

## 🟣 Alternative: Deploy to Heroku

Heroku is a traditional PaaS platform (requires credit card for free tier).

### Steps:

1. **Install Heroku CLI**
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku
   
   # Windows
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login and Create App**
   ```bash
   heroku login
   heroku create your-app-name
   ```

3. **Set Environment Variables**
   ```bash
   heroku config:set FOOTBALL_DATA_API_KEY=your_api_key_here
   heroku config:set FLASK_ENV=production
   ```

4. **Deploy**
   ```bash
   git push heroku main
   heroku open
   ```

---

## ▲ Alternative: Deploy to Vercel

Vercel offers serverless deployment (good for light traffic).

### Steps:

1. **Install Vercel CLI**
   ```bash
   npm i -g vercel
   ```

2. **Deploy**
   ```bash
   vercel
   ```

3. **Set Environment Variable**
   - Go to your project dashboard on [vercel.com](https://vercel.com)
   - Settings → Environment Variables
   - Add: `FOOTBALL_DATA_API_KEY` = your API key
   - Redeploy

---

## 🔧 After Deployment

### Update README with Live URL

Add a badge to your README.md:

```markdown
🌐 **Live Demo:** [https://your-app.onrender.com](https://your-app.onrender.com)
```

### Monitor Your App

- **Render**: Dashboard shows logs and metrics
- **Railway**: Built-in observability dashboard
- **Heroku**: Use `heroku logs --tail` or dashboard
- **Vercel**: Analytics in project dashboard

### API Rate Limits

The free tier of football-data.org has:
- 10 requests per minute
- Limited competition data

For production use, consider upgrading your API plan.

---

## 🆘 Troubleshooting

### App not loading?
1. Check environment variables are set correctly
2. View deployment logs for errors
3. Ensure API key is valid

### API errors?
1. Verify your API key at football-data.org
2. Check you haven't exceeded rate limits
3. Try the free tier competitions first

### App sleeping on Render?
- Free tier apps sleep after inactivity
- Upgrade to paid plan for always-on service
- Or use a service like UptimeRobot to ping your app

---

## 🎉 Success!

Your Soccer Scanner app is now live and accessible to anyone on the internet!

Share your deployment URL and start exploring football data! ⚽
