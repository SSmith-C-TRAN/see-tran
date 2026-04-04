# config.py

import os
from dotenv import load_dotenv
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Core Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = False

    # Database — SQLite for dev, PostgreSQL for prod
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
    if DB_TYPE == 'postgres':
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessions
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_REFRESH_EACH_REQUEST = True

    # CSRF
    WTF_CSRF_TIME_LIMIT = 24 * 3600
    WTF_CSRF_SSL_STRICT = False

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Email (Postmark)
    POSTMARK_API_KEY = os.getenv('POSTMARK_API_KEY')
    POSTMARK_SENDER_EMAIL = os.getenv('POSTMARK_SENDER_EMAIL')
    POSTMARK_NOTIFY_EMAIL = os.getenv('POSTMARK_NOTIFY_EMAIL')

    SUPER_ADMIN_EMAIL = os.getenv('SUPER_ADMIN_EMAIL')

    # Anthropic (primary LLM for all agents)
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')

    # Agent model configuration — override per agent type via env vars
    AGENT_MODEL_DEFAULT = os.environ.get('AGENT_MODEL_DEFAULT', 'claude-sonnet-4-20250514')
    AGENT_MODELS = {
        'agency':    os.environ.get('AGENCY_AGENT_MODEL',    AGENT_MODEL_DEFAULT),
        'vendor':    os.environ.get('VENDOR_AGENT_MODEL',    AGENT_MODEL_DEFAULT),
        'component': os.environ.get('COMPONENT_AGENT_MODEL', AGENT_MODEL_DEFAULT),
    }

    AGENT_CONFIDENCE_THRESHOLD = float(os.environ.get('AGENT_CONFIDENCE_THRESHOLD', '0.7'))

    # OAuth
    OAUTH_GOOGLE_CLIENT_ID = os.environ.get('OAUTH_GOOGLE_CLIENT_ID')
    OAUTH_GOOGLE_CLIENT_SECRET = os.environ.get('OAUTH_GOOGLE_CLIENT_SECRET')
    OAUTH_GOOGLE_DISCOVERY_URL = os.environ.get('OAUTH_GOOGLE_DISCOVERY_URL')

    OAUTH_MS_CLIENT_ID = os.environ.get('OAUTH_MS_CLIENT_ID')
    OAUTH_MS_CLIENT_SECRET = os.environ.get('OAUTH_MS_CLIENT_SECRET')
    OAUTH_MS_DISCOVERY_URL = 'https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration'


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = None


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
