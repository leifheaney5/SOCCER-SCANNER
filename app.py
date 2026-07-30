import os

from dotenv import load_dotenv

load_dotenv()

from soccer_scanner import create_app

app = create_app()


if __name__ == '__main__':
    if not app.config.get('FOOTBALL_DATA_API_KEY'):
        print('Warning: Please set FOOTBALL_DATA_API_KEY for team data.')
    app.run(
        debug=os.getenv('FLASK_DEBUG', '').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5000')),
    )
