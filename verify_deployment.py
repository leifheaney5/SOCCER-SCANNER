#!/usr/bin/env python3
"""
Deployment Verification Script
Checks if the Soccer Scanner app is properly configured for deployment.
"""

import os
import sys

def check_env_variables():
    """Check if required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    api_key = os.getenv('FOOTBALL_DATA_API_KEY')
    if not api_key:
        print("  ❌ FOOTBALL_DATA_API_KEY is not set")
        print("     Set it in your .env file or environment variables")
        return False
    elif api_key == 'your_api_key_here':
        print("  ⚠️  FOOTBALL_DATA_API_KEY is set to default value")
        print("     Replace it with your actual API key from football-data.org")
        return False
    else:
        print(f"  ✅ FOOTBALL_DATA_API_KEY is set ({api_key[:10]}...)")
        return True

def check_files():
    """Check if required files exist."""
    print("\n📁 Checking required files...")
    
    required_files = [
        'app.py',
        'requirements.txt',
        'Procfile',
        'runtime.txt',
        'templates/index.html',
        '.env.example'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} is missing")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Check if dependencies are installed."""
    print("\n📦 Checking Python dependencies...")
    
    try:
        import flask
        print(f"  ✅ Flask {flask.__version__}")
    except ImportError:
        print("  ❌ Flask is not installed")
        return False
    
    try:
        import requests
        print(f"  ✅ requests {requests.__version__}")
    except ImportError:
        print("  ❌ requests is not installed")
        return False
    
    try:
        import dotenv
        print(f"  ✅ python-dotenv")
    except ImportError:
        print("  ❌ python-dotenv is not installed")
        return False
    
    try:
        import gunicorn
        print(f"  ✅ gunicorn (for production)")
    except ImportError:
        print("  ⚠️  gunicorn is not installed (needed for production)")
        print("     Run: pip install -r requirements.txt")
    
    return True

def check_deployment_files():
    """Check if deployment configuration files exist."""
    print("\n🚀 Checking deployment files...")
    
    deployment_files = {
        'Procfile': 'Heroku/Railway',
        'runtime.txt': 'Python version',
        'Dockerfile': 'Docker',
        'docker-compose.yml': 'Docker Compose',
        'app.json': 'Heroku one-click',
        'render.yaml': 'Render.com',
        '.do/app.yaml': 'DigitalOcean'
    }
    
    for file, desc in deployment_files.items():
        if os.path.exists(file):
            print(f"  ✅ {file:<20} ({desc})")
        else:
            print(f"  ⚠️  {file:<20} ({desc}) - optional")

def check_app_structure():
    """Check if app.py is properly configured."""
    print("\n⚙️  Checking app.py configuration...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
            
        if 'os.getenv(\'PORT\'' in content:
            print("  ✅ PORT configuration for cloud platforms")
        else:
            print("  ⚠️  PORT configuration might be missing")
        
        if 'FLASK_ENV' in content or 'debug_mode' in content:
            print("  ✅ Debug mode configuration")
        else:
            print("  ⚠️  Debug mode configuration might be missing")
        
        if 'gunicorn' in open('Procfile').read():
            print("  ✅ Procfile uses gunicorn")
        
        return True
    except Exception as e:
        print(f"  ❌ Error checking app.py: {e}")
        return False

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Soccer Scanner - Deployment Verification")
    print("=" * 60)
    
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass
    
    checks = [
        check_files(),
        check_dependencies(),
        check_env_variables(),
        check_deployment_files(),
        check_app_structure()
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✅ All checks passed! Your app is ready to deploy.")
        print("\n🚀 Next steps:")
        print("   1. Push your code to GitHub")
        print("   2. Choose a platform (Heroku, Railway, Render, etc.)")
        print("   3. Follow QUICK_DEPLOY.md for step-by-step instructions")
        print("   4. Set FOOTBALL_DATA_API_KEY in your platform's settings")
        print("   5. Deploy and enjoy!")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print("\n📚 Resources:")
        print("   - QUICK_DEPLOY.md - Quick deployment guide")
        print("   - DEPLOYMENT.md - Detailed deployment instructions")
        print("   - README.md - Full project documentation")
        return 1

if __name__ == '__main__':
    sys.exit(main())
