import os
from pathlib import Path
from dotenv import load_dotenv


def settings():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    return {
        'SECRET_KEY': os.getenv('SECRET_KEY'),
        'SESSION_COOKIE_SECURE': os.getenv('APP_ENV', 'development') == 'production',
        'DB_NAME': os.getenv('PGDATABASE', 'university_events_raw'),
        'DB_HOST': os.getenv('PGHOST', 'localhost'),
        'DB_PORT': int(os.getenv('PGPORT', '5432')),
        'DB_USER': os.getenv('PGUSER', 'postgres'),
        'DB_PASSWORD': os.getenv('PGPASSWORD', ''),
        'DB_TIMEOUT': int(os.getenv('PGCONNECT_TIMEOUT', '3')),
    }
