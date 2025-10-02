# Quick Deploy Guide 🚀

Choose your preferred platform and follow the steps below. Each option takes 5-10 minutes.

## 🎯 Fastest Options (Recommended)

### Option 1: Railway (Easiest - No Credit Card Required)

1. Go to [railway.app](https://railway.app)
2. Click "Start a New Project"
3. Click "Deploy from GitHub repo"
4. Select `SOCCER-SCANNER` repository
5. Click on your deployment → Variables tab
6. Add: `FOOTBALL_DATA_API_KEY` = `your_api_key_here`
7. Done! 🎉 Your app will be live in 2-3 minutes

**Live URL:** Railway provides an auto-generated URL like `https://soccer-scanner-production.up.railway.app`

---

### Option 2: Heroku (Most Popular)

1. Go to [heroku.com](https://heroku.com) and sign up/login
2. Click "New" → "Create new app"
3. Choose an app name (e.g., `my-soccer-scanner`)
4. Go to "Deploy" tab
5. Connect to GitHub and select `SOCCER-SCANNER` repository
6. Go to "Settings" → "Config Vars"
7. Add: `FOOTBALL_DATA_API_KEY` = `your_api_key_here`
8. Go back to "Deploy" tab
9. Click "Deploy Branch" (main)
10. Done! 🎉

**Live URL:** `https://your-app-name.herokuapp.com`

---

### Option 3: Render (Free Tier Available)

1. Go to [render.com](https://render.com) and sign up
2. Click "New +" → "Web Service"
3. Connect your GitHub account
4. Select `SOCCER-SCANNER` repository
5. Configure:
   - **Name:** `soccer-scanner`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Add Environment Variable:
   - **Key:** `FOOTBALL_DATA_API_KEY`
   - **Value:** `your_api_key_here`
7. Click "Create Web Service"
8. Done! 🎉

**Live URL:** `https://soccer-scanner.onrender.com`

---

## 🔑 Getting Your API Key

Before deploying, you need a FREE API key:

1. Visit [football-data.org/client/register](https://www.football-data.org/client/register)
2. Fill in your email and click "Register"
3. Check your email and verify
4. Login to your dashboard
5. Copy your API key (starts with a long string of characters)
6. Use this in the `FOOTBALL_DATA_API_KEY` environment variable

**Note:** Free tier gives you 10 requests/minute - perfect for personal use!

---

## 🐳 Docker (For Advanced Users)

If you have Docker installed:

```bash
# Clone the repository
git clone https://github.com/leifheaney5/SOCCER-SCANNER.git
cd SOCCER-SCANNER

# Create environment file
echo "FOOTBALL_DATA_API_KEY=your_api_key_here" > .env

# Run with Docker Compose
docker-compose up -d

# Access at http://localhost:5000
```

---

## ✅ Verify Your Deployment

After deploying, test your app:

1. Open the provided URL
2. Select a competition (e.g., "Premier League")
3. Select a team (e.g., "Manchester United")
4. Click "Analyze Team"
5. You should see team information and stats

If you see data, congratulations! 🎊 Your app is live!

---

## 🆘 Troubleshooting

### Problem: "Failed to fetch competitions"
**Solution:** Check that `FOOTBALL_DATA_API_KEY` is set correctly in environment variables

### Problem: App shows error on startup
**Solution:** Check the logs in your platform's dashboard for specific error messages

### Problem: Very slow loading
**Solution:** This is normal on free tiers - first request after inactivity takes longer

---

## 📱 Share Your App

Once deployed, share your URL with anyone:
- Friends and family
- Social media
- Portfolio/resume
- GitHub README

---

## 🔄 Updating Your App

When you push changes to GitHub:
- **Railway**: Auto-deploys on git push
- **Heroku**: Enable auto-deploy in settings or manually deploy
- **Render**: Auto-deploys on git push (if enabled)

---

## 💰 Free Tier Limits

All platforms offer free tiers:

| Platform | Free Tier | Best For |
|----------|-----------|----------|
| Railway | 500 hrs/month | Best overall free option |
| Render | 750 hrs/month | Most generous free tier |
| Heroku | 550 hrs/month | Most popular platform |

**Note:** Free tiers sleep after 30 min of inactivity - first request takes 10-15 seconds to wake up.

---

## 🎓 Next Steps

1. **Custom Domain**: Add your own domain in platform settings
2. **Analytics**: Add Google Analytics to track visitors
3. **Monitoring**: Set up UptimeRobot to monitor uptime
4. **Share**: Add your live URL to your GitHub README

---

**Need more help?** See the full [DEPLOYMENT.md](./DEPLOYMENT.md) guide.

**Your app is now live and accessible to external users worldwide! ⚽🌍**
