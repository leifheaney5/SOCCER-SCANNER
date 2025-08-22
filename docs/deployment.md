# Soccer Scanner - Deployment Guide

## Overview

This guide covers multiple deployment options for the Soccer Scanner application, from local development to production hosting platforms.

## Prerequisites

- Python 3.7 or higher
- Football-data.org API key (free tier available)
- Git for version control

## Local Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/soccer-comp.git
cd soccer-comp

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file:

```env
FOOTBALL_DATA_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### 3. Run Application

```bash
python app.py
```

Visit `http://localhost:5000` to see the application.

## Production Deployment Options

### Option 1: Heroku Deployment

Heroku provides simple deployment with automatic scaling and monitoring.

#### Prerequisites
- Heroku CLI installed
- Heroku account

#### Steps

1. **Prepare for Heroku**

Create `Procfile`:
```
web: python app.py
```

Create `runtime.txt`:
```
python-3.11.0
```

2. **Deploy to Heroku**

```bash
# Login to Heroku
heroku login

# Create Heroku app
heroku create your-app-name

# Set environment variables
heroku config:set FOOTBALL_DATA_API_KEY=your_api_key_here
heroku config:set FLASK_ENV=production

# Deploy
git push heroku main

# Open app
heroku open
```

#### Heroku Benefits
- Automatic SSL certificates
- Easy scaling
- Built-in monitoring
- Free tier available

### Option 2: Railway Deployment

Railway offers modern deployment with automatic previews and easy configuration.

#### Steps

1. **Connect Repository**
   - Visit [railway.app](https://railway.app)
   - Connect your GitHub repository
   - Select the soccer-comp repository

2. **Configure Environment**
   - Add environment variable: `FOOTBALL_DATA_API_KEY`
   - Railway auto-detects Python and installs dependencies

3. **Deploy**
   - Railway automatically deploys on git push
   - Custom domain available

#### Railway Benefits
- Automatic deployments
- Built-in database options
- Excellent performance
- Simple pricing

### Option 3: DigitalOcean App Platform

DigitalOcean provides robust hosting with good performance and pricing.

#### Steps

1. **Create App**
   - Login to DigitalOcean
   - Create new App
   - Connect GitHub repository

2. **Configure Build**
   ```yaml
   # .do/app.yaml
   name: soccer-scanner
   services:
   - name: web
     source_dir: /
     github:
       repo: yourusername/soccer-comp
       branch: main
     run_command: python app.py
     environment_slug: python
     instance_count: 1
     instance_size_slug: basic-xxs
     envs:
     - key: FOOTBALL_DATA_API_KEY
       value: your_api_key_here
     - key: FLASK_ENV
       value: production
   ```

3. **Deploy**
   - Automatic deployment on configuration
   - Custom domain support

### Option 4: Self-Hosted VPS

For full control, deploy to your own Virtual Private Server.

#### Prerequisites
- Ubuntu/Debian VPS
- Domain name (optional)
- SSH access

#### Steps

1. **Server Setup**

```bash
# Update server
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip python3-venv nginx -y

# Clone repository
git clone https://github.com/yourusername/soccer-comp.git
cd soccer-comp

# Setup application
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Configure Environment**

```bash
# Create environment file
cat > .env << EOF
FOOTBALL_DATA_API_KEY=your_api_key_here
FLASK_ENV=production
EOF
```

3. **Setup Systemd Service**

```bash
# Create service file
sudo cat > /etc/systemd/system/soccer-scanner.service << EOF
[Unit]
Description=Soccer Scanner Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/soccer-comp
Environment=PATH=/path/to/soccer-comp/.venv/bin
ExecStart=/path/to/soccer-comp/.venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable soccer-scanner
sudo systemctl start soccer-scanner
```

4. **Configure Nginx**

```nginx
# /etc/nginx/sites-available/soccer-scanner
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/soccer-scanner /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run application
CMD ["python", "app.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FOOTBALL_DATA_API_KEY=${FOOTBALL_DATA_API_KEY}
      - FLASK_ENV=production
    restart: unless-stopped
```

### Deploy with Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Environment Configuration

### Required Environment Variables

```env
# Required
FOOTBALL_DATA_API_KEY=your_api_key_here

# Optional
FLASK_ENV=production
FLASK_DEBUG=False
PORT=5000
```

### Production Considerations

1. **Security**
   - Use HTTPS in production
   - Keep API keys secure
   - Regular security updates

2. **Performance**
   - Enable gzip compression
   - Configure caching headers
   - Monitor API rate limits

3. **Monitoring**
   - Set up application logging
   - Monitor API usage
   - Track error rates

4. **Backup**
   - Regular code backups
   - Environment configuration backup
   - Monitor API key usage

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Change port in app.py or environment
   export PORT=8000
   ```

2. **API Key Issues**
   ```bash
   # Verify API key is set
   echo $FOOTBALL_DATA_API_KEY
   
   # Test API key
   curl -H "X-Auth-Token: your_key" https://api.football-data.org/v4/competitions
   ```

3. **Module Not Found**
   ```bash
   # Ensure virtual environment is activated
   which python
   pip list
   ```

### Performance Optimization

1. **Caching**
   - Implement Redis for API response caching
   - Use CDN for static assets
   - Enable browser caching

2. **Database**
   - Add PostgreSQL for data persistence
   - Cache frequently accessed data
   - Implement connection pooling

3. **Monitoring**
   - Use APM tools (New Relic, DataDog)
   - Monitor API response times
   - Track user engagement

## Maintenance

### Regular Tasks

1. **Dependencies**
   ```bash
   # Update dependencies
   pip list --outdated
   pip install -U package_name
   ```

2. **Logs**
   ```bash
   # Monitor application logs
   tail -f /var/log/soccer-scanner.log
   ```

3. **Backups**
   ```bash
   # Backup configuration
   tar -czf backup-$(date +%Y%m%d).tar.gz .env app.py templates/
   ```

This deployment guide provides multiple options to suit different needs and technical requirements, from simple cloud deployments to full VPS control.
